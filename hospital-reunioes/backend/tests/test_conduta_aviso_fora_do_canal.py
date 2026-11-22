"""O aviso de assunto fora do canal na revisão do relato (issue #1848, PRD
#1786, especificação seções 4.1 e P5, Anexo A saída reduzida; ADR 0097
decisões 6 e 7).

Ao abrir a revisão, a tela pública pergunta uma vez à rota
`POST /api/conduta/relatos/aviso` se o texto parece de outro destino. A rota
devolve só o destino do aviso (`DP`, `OUVIDORIA`, `NSP`, `GESTAO`) ou nada.
O aviso só existe quando o agente diz que parece fora e que não há termo da
regra de proteção. Teto, falha ou agente desligado: sem aviso, e o envio
segue.

O banco é o dublê de `conduta_apoio`, com a função da cota; o modelo é um
dublê que guarda o que recebeu. Nenhum teste chama a IA de verdade.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import RequestContextMiddleware  # noqa: E402
from app.routers import conduta_publico  # noqa: E402
from app.services.conduta import agente_de_triagem, aviso_fora_do_canal  # noqa: E402

AVISO = "/api/conduta/relatos/aviso"
KIT = Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "canal-de-conduta.md"
CONTRACHEQUE = "Meu contracheque veio sem o adicional noturno de outubro."
EMERGENCIA = "Esperei quatro horas na emergência com minha mãe e ninguém deu informação."


def saida(parece_fora="SIM", destino="DP", termo="NAO") -> dict:
    return {"parece_fora": parece_fora, "destino": destino, "tem_termo_de_protecao": termo}


class Modelo:
    """O dublê do cliente da Anthropic: guarda cada chamada e devolve a saída
    combinada, ou levanta quando `falha` é uma exceção."""

    def __init__(self, resposta: dict | str | None = None, falha: Exception | None = None):
        self.resposta = resposta if resposta is not None else saida()
        self.falha = falha
        self.chamadas: list[dict] = []
        self.messages = self

    def create(self, **argumentos):
        self.chamadas.append(argumentos)
        if self.falha:
            raise self.falha
        texto = self.resposta if isinstance(self.resposta, str) else json.dumps(self.resposta)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=texto)])

    def texto_enviado(self) -> str:
        return "\n".join(m["content"] for chamada in self.chamadas for m in chamada["messages"])


class BancoComCota(Banco):
    """O dublê com a função da cota do agente (migration 200), a mesma da
    triagem do caso."""

    def __init__(self, *, teto_atingido: bool = False):
        super().__init__()
        self.teto_atingido = teto_atingido
        self.reservas = 0

    def rpc(self, nome, parametros):
        assert nome == agente_de_triagem.FUNCAO_DA_COTA
        assert parametros == {"p_teto": agente_de_triagem.TETO_DIARIO}
        self.reservas += 1
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[{"reservada": not self.teto_atingido}]))


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "conduta_canal_aberto", True)
    monkeypatch.setattr(settings, "conduta_agente_ligado", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def modelo(monkeypatch) -> Modelo:
    duble = Modelo()
    monkeypatch.setattr(aviso_fora_do_canal, "_cliente", lambda: duble)
    return duble


@pytest.fixture
def banco() -> BancoComCota:
    return BancoComCota()


def _cliente(banco) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(conduta_publico.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app, raise_server_exceptions=False)


def _aviso(banco, relato: str) -> dict:
    resposta = _cliente(banco).post(AVISO, json={"relato": relato})
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["cache-control"] == "no-store"
    return resposta.json()


# ═══════════════════════════════════════════════════════════════════════════
# 1 e 2. Assunto de DP e de atendimento a paciente mostram o aviso
# ═══════════════════════════════════════════════════════════════════════════


def test_relato_de_assunto_de_dp_recebe_o_aviso_do_dp(banco, modelo):
    assert _aviso(banco, CONTRACHEQUE) == {"aviso": "DP"}
    assert len(modelo.chamadas) == 1


def test_relato_de_atendimento_a_paciente_recebe_o_aviso_da_ouvidoria(banco, modelo):
    modelo.resposta = saida(destino="OUVIDORIA")

    assert _aviso(banco, EMERGENCIA) == {"aviso": "OUVIDORIA"}


@pytest.mark.parametrize("destino", ["NSP", "GESTAO"])
def test_os_outros_destinos_tambem_viram_aviso(banco, modelo, destino):
    modelo.resposta = saida(destino=destino)

    assert _aviso(banco, "Não concordo com minha avaliação de desempenho.") == {"aviso": destino}


def test_o_que_parece_do_canal_nao_tem_aviso(banco, modelo):
    modelo.resposta = saida(parece_fora="NAO", destino="")

    assert _aviso(banco, "Minha coordenadora me chama de incompetente na frente da equipe.") == {"aviso": None}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Termo da regra de proteção: sem aviso (casos 7 e 11 do Anexo B)
# ═══════════════════════════════════════════════════════════════════════════


def test_caso_7_com_o_agente_vendo_retaliacao_nao_tem_aviso(banco, modelo):
    """Caso 7: o assunto aparente é de DP, mas há retaliação pelos fatos."""
    modelo.resposta = saida(parece_fora="SIM", destino="DP", termo="SIM")

    relato = "Cortaram minhas horas extras depois que recusei um convite do meu chefe para jantar."
    assert _aviso(banco, relato) == {"aviso": None}


def test_caso_11_com_a_palavra_da_regra_nao_tem_aviso_nem_se_o_agente_errar(banco, modelo):
    """O app confere os termos da regra por conta própria: com "ameaçou" no
    texto, nem uma resposta errada do agente vira aviso, e a cota não é gasta."""
    modelo.resposta = saida(parece_fora="SIM", destino="DP", termo="NAO")

    relato = "Meu vale-transporte não foi creditado e o supervisor ameaçou me mandar embora se eu reclamar."
    assert _aviso(banco, relato) == {"aviso": None}
    assert modelo.chamadas == []
    assert banco.reservas == 0


@pytest.mark.parametrize(
    "palavra",
    ["assédio", "discriminação", "ameaça", "violência", "retaliação", "fraude", "desvio", "falsificação"],
)
def test_cada_termo_da_regra_de_protecao_e_reconhecido_pelo_app(palavra):
    assert aviso_fora_do_canal.tem_termo_de_protecao(f"Meu contracheque veio errado e houve {palavra.upper()}.")
    assert not aviso_fora_do_canal.tem_termo_de_protecao(CONTRACHEQUE)


@pytest.mark.parametrize(
    "verbo",
    [
        "assediou",
        "discriminou",
        "ameaçou",
        "violentou",
        "retaliou",
        "retaliei",
        "retaliem",
        "retaliar",
        "fraudou",
        "desviou",
        "falsificou",
    ],
)
def test_o_verbo_da_regra_de_protecao_tambem_e_reconhecido_pelo_app(verbo):
    """O relato conta o fato com o verbo, não com o substantivo: "o chefe
    retaliou" tem de calar o aviso como "houve retaliação"."""
    assert aviso_fora_do_canal.tem_termo_de_protecao(f"O chefe {verbo} cortando meu plantão.")


# ═══════════════════════════════════════════════════════════════════════════
# 6. Teto estourado, agente fora do ar ou desligado: sem aviso, sem erro
# ═══════════════════════════════════════════════════════════════════════════


def test_com_o_teto_estourado_nao_ha_aviso_e_o_modelo_nao_e_chamado(modelo):
    banco = BancoComCota(teto_atingido=True)

    assert _aviso(banco, CONTRACHEQUE) == {"aviso": None}
    assert banco.reservas == 1
    assert modelo.chamadas == []


def test_com_o_agente_fora_do_ar_nao_ha_aviso(banco, modelo):
    modelo.falha = TimeoutError("o provedor não respondeu")

    assert _aviso(banco, CONTRACHEQUE) == {"aviso": None}


@pytest.mark.parametrize("resposta", ["não sei dizer", {"parece_fora": "TALVEZ", "destino": "DP"}, saida(destino="RH")])
def test_resposta_fora_do_formato_nao_vira_aviso(banco, modelo, resposta):
    modelo.resposta = resposta

    assert _aviso(banco, CONTRACHEQUE) == {"aviso": None}


def test_com_o_agente_desligado_nao_ha_leitura_nem_aviso(banco, modelo, monkeypatch):
    monkeypatch.setattr(settings, "conduta_agente_ligado", False)

    assert _aviso(banco, CONTRACHEQUE) == {"aviso": None}
    assert modelo.chamadas == []
    assert banco.reservas == 0


def test_com_o_canal_fechado_a_rota_nao_existe(banco, modelo, monkeypatch):
    monkeypatch.setattr(settings, "conduta_canal_aberto", False)

    assert _cliente(banco).post(AVISO, json={"relato": CONTRACHEQUE}).status_code == 404
    assert modelo.chamadas == []


@pytest.mark.parametrize("corpo", [{}, {"relato": "   "}, {"relato": 42}, {"relato": "x" * 10_001}])
def test_envio_sem_texto_e_recusado_sem_chamar_o_agente(banco, modelo, corpo):
    resposta = _cliente(banco).post(AVISO, json=corpo)

    assert resposta.status_code == 422
    assert modelo.chamadas == []


# ═══════════════════════════════════════════════════════════════════════════
# A leitura conta no teto e manda o texto pseudonimizado; nada fica gravado
# ═══════════════════════════════════════════════════════════════════════════


def test_a_leitura_gasta_uma_vaga_do_teto_do_agente(banco, modelo):
    _aviso(banco, CONTRACHEQUE)

    assert banco.reservas == 1
    assert modelo.chamadas[0]["model"] == settings.conduta_agente_modelo


def test_o_modelo_recebe_o_texto_pseudonimizado(banco, modelo):
    relato = "Sou Joana Prudente, telefone (21) 98765-4321, e meu contracheque veio sem o adicional noturno."

    _aviso(banco, relato)

    enviado = modelo.texto_enviado()
    assert "contracheque veio sem o adicional noturno" in enviado
    assert "Joana" not in enviado and "Prudente" not in enviado
    assert "98765" not in enviado


def test_nenhum_texto_fica_gravado_pela_leitura(banco, modelo):
    _aviso(banco, "Sou Joana Prudente e meu contracheque veio sem o adicional noturno.")

    assert all(linhas == [] for linhas in banco.tabelas.values())


def test_o_texto_do_relato_nao_vai_ao_log(banco, modelo, caplog):
    modelo.falha = TimeoutError("o provedor não respondeu")
    with caplog.at_level("DEBUG"):
        _aviso(banco, "Meu contracheque do mês de outubro veio sem o adicional noturno.")

    assert "contracheque" not in caplog.text


# ═══════════════════════════════════════════════════════════════════════════
# 9. O texto do Produto Canal de Conduta no kit diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "frase",
    [
        "Ao abrir a revisão, o agente lê o texto uma vez",
        "O relato nunca é bloqueado",
        "Ver contato do DP mostra o contato salvo nas Configurações, sem enviar nada",
        "Ir para a Ouvidoria abre o formulário da Ouvidoria com o texto já escrito",
        "Se o texto fala de assédio, discriminação, ameaça, violência, retaliação, fraude, desvio ou falsificação",
        "Com o teto de leituras do dia estourado ou o agente fora do ar, a revisão abre sem aviso",
    ],
)
def test_o_kit_diz_o_que_o_aviso_na_revisao_faz(frase):
    assert frase in KIT.read_text(encoding="utf-8")


def test_o_kit_nao_diz_mais_que_o_aviso_chega_depois():
    assert "o aviso de assunto fora do canal na revisão chegam numa próxima entrega" not in KIT.read_text(
        encoding="utf-8"
    )
