"""Os prazos do caso e a tabela de prazos do Núcleo (issue #1993, PRD #1979,
ADR 0107 decisões 1 e 2).

Um bloco por critério de aceite do backend:

1. confirmar um caso de cada faixa grava os prazos do art. 26 do Regimento,
   com data e hora absolutas;
2. os prazos legais não aparecem como editáveis, e a rota recusa alterá-los;
3. editar um prazo interno grava o histórico (quem, quando, de e para) e não
   muda caso já classificado;
4. confirmar cria a linha de notificação externa: VigiMed para medicação,
   NOTIVISA para o resto, e nenhuma na circunstância de risco;
5. só a Presidência e o Acesso pleno editam a tabela;
6. o kit de conhecimento diz o comportamento novo.

Os vencimentos esperados são contados à mão, no calendário de novembro de
2026: o caso chega na terça 10/11 às 10h de São Paulo, e o incidente foi na
segunda 09/11 às 22h. Úteis são os dias de segunda a sexta, das 8h às 17h.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import _participacao, _pessoa  # noqa: E402
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    DIRETOR_EXECUTIVO,
    GRAVE,
    MEMBRO,
    MODERADO,
    OBITO,
    PRESIDENTE,
    QUASE_ERRO,
    SUPER_ADMIN,
    TODOS_OS_CAMPOS,
    _BancoDaTriagem,
    _ConsultaDaTriagem,
    _notificacao,
    _sugestao,
)
from test_seguranca_do_paciente_triagem import _banco as _banco_da_triagem  # noqa: E402

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_notificacoes as notificacoes_router  # noqa: E402
from app.routers import seguranca_do_paciente_prazos as prazos_router  # noqa: E402
from app.routers import seguranca_do_paciente_triagem as triagem_router  # noqa: E402

SP = ZoneInfo("America/Sao_Paulo")

# Chegou na terça 10/11/2026 às 10h de São Paulo; o incidente foi na segunda
# 09/11 às 22h.
CHEGADA = "2026-11-10T13:00:00+00:00"
DO_CASO = {"criado_em": CHEGADA, "data_ocorrencia": "2026-11-09", "hora_aproximada": "22:00:00"}
# A triagem foi confirmada na quinta 12/11 às 15h de São Paulo: a reunião de
# análise conta daí (art. 24 do Regimento), e não da chegada.
CONFIRMACAO = "2026-11-12T18:00:00+00:00"

SUPLENTE = _pessoa("P7")

LEVE = {"natureza": "evento_adverso", "grau_de_dano": "leve", "faixa": "D"}
CIRCUNSTANCIA = {"natureza": "circunstancia_de_risco", "grau_de_dano": "nenhum", "faixa": "E"}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _cliente(banco, pessoa: dict[str, Any] = PRESIDENTE) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(triagem_router.router, prefix="/api")
    app.include_router(notificacoes_router.router, prefix="/api")
    app.include_router(prazos_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


class _ConsultaDoNucleo(_ConsultaDaTriagem):
    """O DEFAULT now() da 188: a linha da triagem nasce com a hora em que a
    pessoa confirmou."""

    def _inserir(self) -> list[dict]:
        if self._nome == "nsp_triagens":
            novas = self._valores if isinstance(self._valores, list) else [self._valores]
            for valores in novas:
                valores.setdefault("criado_em", self._banco.confirmacao_em)
        return super()._inserir()


class _BancoDoNucleo(_BancoDaTriagem):
    confirmacao_em = CONFIRMACAO

    def table(self, nome: str):
        return _ConsultaDoNucleo(self, nome)


def _banco(notificacoes: list[dict] | None = None, triagens: list[dict] | None = None) -> _BancoDoNucleo:
    return _BancoDoNucleo(_banco_da_triagem(notificacoes, triagens).tabelas)


def _caso_confirmado(sugestao: dict, **campos) -> tuple[Any, dict]:
    caso = _notificacao(1, **{**DO_CASO, **campos})
    banco = _banco([caso], [_sugestao(caso, **sugestao)])
    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})
    assert resposta.status_code == 201, resposta.text
    return banco, caso


def _prazos_na_tela(banco, caso, pessoa=PRESIDENTE) -> dict[str, tuple[str, str]]:
    """O que o caso mostra: marco -> (legal ou interno, data e hora em São Paulo)."""
    resposta = _cliente(banco, pessoa).get(f"/api/nsp/notificacoes/{caso['id']}")
    assert resposta.status_code == 200, resposta.text
    return {
        p["marco"]: (p["tipo"], datetime.fromisoformat(p["vence_em"]).astimezone(SP).strftime("%d/%m/%Y %H:%M"))
        for p in resposta.json()["prazos"]
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Confirmar grava os prazos do art. 26, com data e hora absolutas
# ═══════════════════════════════════════════════════════════════════════════

PRAZOS_ESPERADOS = {
    # Faixa A, óbito: 72 horas corridas do incidente, 60 dias corridos para a
    # complementação, e os internos da coluna "Evento que nunca deveria
    # ocorrer / Óbito".
    "A": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),  # 24h corridas
        "comunicacao_a_direcao": ("interno", "10/11/2026 12:00"),  # 2h corridas
        "triagem": ("interno", "10/11/2026 14:00"),  # 4h úteis
        "inicio_da_investigacao": ("interno", "12/11/2026 16:00"),  # 24h úteis: 7 + 9 + 8
        "conclusao_da_investigacao": ("interno", "25/12/2026 23:59"),  # 45 dias corridos
        "reuniao_de_analise": ("interno", "23/11/2026 17:00"),  # 7 dias úteis da confirmação (12/11)
        "notificacao_externa": ("legal", "12/11/2026 22:00"),  # 72h corridas do incidente
        "complementacao_da_notificacao_externa": ("legal", "08/01/2027 23:59"),  # 60 dias corridos
    },
    # Faixa B, dano grave: 15º dia útil de dezembro (21/12).
    "B": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),
        "comunicacao_a_direcao": ("interno", "11/11/2026 10:00"),  # 24h corridas
        "triagem": ("interno", "11/11/2026 17:00"),  # 1 dia útil
        "inicio_da_investigacao": ("interno", "13/11/2026 17:00"),  # 3 dias úteis
        "conclusao_da_investigacao": ("interno", "10/12/2026 23:59"),  # 30 dias corridos
        "reuniao_de_analise": ("interno", "03/12/2026 17:00"),  # 15 dias úteis da confirmação (12/11)
        "notificacao_externa": ("legal", "21/12/2026 17:00"),
    },
    # Faixa C, dano moderado: sem comunicação à Direção e reunião na pauta
    # ordinária, sem data.
    "C": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),
        "triagem": ("interno", "12/11/2026 17:00"),  # 2 dias úteis
        "inicio_da_investigacao": ("interno", "17/11/2026 17:00"),  # 5 dias úteis
        "conclusao_da_investigacao": ("interno", "08/12/2026 17:00"),  # 20 dias úteis
        "notificacao_externa": ("legal", "21/12/2026 17:00"),
    },
    # Faixa D, dano leve.
    "D": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),
        "triagem": ("interno", "13/11/2026 17:00"),  # 3 dias úteis
        "conclusao_da_investigacao": ("interno", "24/11/2026 17:00"),  # 10 dias úteis
        "notificacao_externa": ("legal", "21/12/2026 17:00"),
    },
    # Faixa E, quase erro: a análise é agregada no mês, sem data própria.
    "E": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),
        "triagem": ("interno", "17/11/2026 17:00"),  # 5 dias úteis
        "notificacao_externa": ("legal", "21/12/2026 17:00"),
    },
}

SUGESTAO_DA_FAIXA = {"A": OBITO, "B": GRAVE, "C": MODERADO, "D": LEVE, "E": QUASE_ERRO}


@pytest.mark.parametrize("faixa", list(PRAZOS_ESPERADOS))
def test_confirmar_grava_os_prazos_do_art_26_da_faixa(faixa):
    banco, caso = _caso_confirmado(SUGESTAO_DA_FAIXA[faixa])

    assert _prazos_na_tela(banco, caso) == PRAZOS_ESPERADOS[faixa]


# A lesão por pressão estágio 3, estágio 4 ou não classificável (itens 8 a 10
# da lista), sem óbito, vai para a reunião ordinária seguinte, sem reunião
# extraordinária (art. 24, parágrafo único; ADR 0107, decisão 1).
LESAO_POR_PRESSAO = {
    "natureza": "evento_adverso",
    "grau_de_dano": "grave",
    "faixa": "A",
    "evento_situacao": "sim",
    "evento_item": 9,
    "protocolo_basico": "lesao_por_pressao",
    "revisao": "campo_a_campo",
}


@pytest.mark.parametrize("item", [8, 9, 10])
def test_a_lesao_por_pressao_dos_itens_8_a_10_sem_obito_nao_ganha_reuniao_extraordinaria(item):
    banco, caso = _caso_confirmado({**LESAO_POR_PRESSAO, "evento_item": item})

    na_tela = _prazos_na_tela(banco, caso)

    assert "reuniao_de_analise" not in na_tela
    assert na_tela["conclusao_da_investigacao"] == ("interno", "25/12/2026 23:59")
    assert na_tela["notificacao_externa"] == ("legal", "12/11/2026 22:00")


@pytest.mark.parametrize(
    "sugestao",
    [{**LESAO_POR_PRESSAO, "grau_de_dano": "obito"}, {**LESAO_POR_PRESSAO, "evento_item": 11}],
    ids=["lesão por pressão com óbito", "outro evento que nunca deveria ocorrer"],
)
def test_o_evento_da_faixa_a_fora_da_excecao_tem_a_reuniao_extraordinaria(sugestao):
    banco, caso = _caso_confirmado(sugestao)

    assert _prazos_na_tela(banco, caso)["reuniao_de_analise"] == ("interno", "23/11/2026 17:00")


def test_os_prazos_internos_da_notificacao_tardia_pulam_os_feriados_do_periodo():
    """Busca ativa em prontuário: o incidente foi em 01/09 e a notificação
    chegou na quinta 10/12, às 10h. Os 20 dias úteis da faixa C contam da
    chegada e pulam o Natal e o 1º de janeiro: 11/12 é o dia 1, e o dia 20 cai
    na segunda 11/01/2027."""
    caso = _notificacao(1, criado_em="2026-12-10T13:00:00+00:00", data_ocorrencia="2026-09-01")
    banco = _banco([caso], [_sugestao(caso, **MODERADO)])
    banco.confirmacao_em = "2026-12-10T15:00:00+00:00"
    banco.tabelas["ouvidoria_feriados"] = [{"data": "2026-12-25"}, {"data": "2027-01-01"}]

    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})

    assert resposta.status_code == 201, resposta.text
    assert _prazos_na_tela(banco, caso)["conclusao_da_investigacao"] == ("interno", "11/01/2027 17:00")


def test_a_tabela_de_prazos_ilegivel_nao_congela_os_valores_de_fabrica(monkeypatch):
    """A leitura da tabela cai: a confirmação devolve 503 sem gravar prazo, e
    a nova tentativa conclui com a tabela que a Presidência editou."""
    caso = _notificacao(1, **DO_CASO)
    banco = _banco_com_tabela([caso], [_sugestao(caso, **OBITO)])
    assert _alterar(banco, "A", "triagem", {"valor": 2, "unidade": "horas_uteis"}).status_code == 200
    executar = _ConsultaComHistorico.execute

    def _a_tabela_nao_responde(self):
        if self._nome == "nsp_tabela_de_prazos" and self._acao not in ("insert", "update"):
            raise APIError({"code": "57014", "message": "canceling statement due to statement timeout"})
        return executar(self)

    monkeypatch.setattr(_ConsultaComHistorico, "execute", _a_tabela_nao_responde)
    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})
    assert resposta.status_code == 503, resposta.text
    assert banco.tabelas.get("nsp_prazos_do_caso", []) == []
    monkeypatch.undo()

    nova = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})

    assert nova.status_code == 201, nova.text
    assert _prazos_na_tela(banco, caso)["triagem"] == ("interno", "10/11/2026 12:00")


# ═══════════════════════════════════════════════════════════════════════════
# 4. A linha de notificação externa: VigiMed para medicação, NOTIVISA para o
#    resto, nenhuma na circunstância de risco
# ═══════════════════════════════════════════════════════════════════════════


def _notificacao_externa(banco, caso) -> dict | None:
    resposta = _cliente(banco).get(f"/api/nsp/notificacoes/{caso['id']}")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["notificacao_externa"]


def _em_sao_paulo(instante: str) -> str:
    return datetime.fromisoformat(instante).astimezone(SP).strftime("%d/%m/%Y %H:%M")


@pytest.mark.parametrize(
    ("sugestao", "sistema", "prazo"),
    [
        ({**OBITO, "categoria": "MED"}, "vigimed", "12/11/2026 22:00"),
        ({**MODERADO, "categoria": "MED"}, "vigimed", "21/12/2026 17:00"),
        (OBITO, "notivisa", "12/11/2026 22:00"),
        (QUASE_ERRO, "notivisa", "21/12/2026 17:00"),
    ],
    ids=["óbito por medicação", "medicação, dano moderado", "óbito por equipamento", "quase erro"],
)
def test_confirmar_cria_a_linha_de_notificacao_externa_com_o_sistema_e_o_prazo_legal(sugestao, sistema, prazo):
    banco, caso = _caso_confirmado(sugestao)

    externa = _notificacao_externa(banco, caso)

    assert externa is not None
    assert externa["sistema"] == sistema
    assert _em_sao_paulo(externa["prazo_legal"]) == prazo
    assert externa["estado"] == "pendente"


def test_circunstancia_de_risco_nao_cria_linha_de_notificacao_externa():
    banco, caso = _caso_confirmado(CIRCUNSTANCIA)

    assert _notificacao_externa(banco, caso) is None
    assert banco.tabelas.get("nsp_notificacoes_externas", []) == []
    assert "notificacao_externa" not in _prazos_na_tela(banco, caso)


def test_a_nova_tentativa_da_confirmacao_nao_grava_os_prazos_de_novo():
    """A confirmação que caiu entre os prazos e a mudança de estado conclui na
    nova tentativa sem duplicar prazo nem linha externa."""
    banco, caso = _caso_confirmado(OBITO)
    prazos_gravados = list(banco.tabelas["nsp_prazos_do_caso"])
    banco.notificacoes[0]["estado"] = "recebida"

    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})

    assert resposta.status_code == 201, resposta.text
    assert banco.tabelas["nsp_prazos_do_caso"] == prazos_gravados
    assert len(banco.tabelas["nsp_notificacoes_externas"]) == 1


def test_a_confirmacao_que_chega_depois_de_outra_fica_com_os_prazos_da_primeira(monkeypatch):
    """Duas tentativas ao mesmo tempo: a segunda esbarra no um prazo por marco
    do banco e conclui com os prazos que a primeira gravou."""
    caso = _notificacao(1, **DO_CASO)
    banco = _banco([caso], [_sugestao(caso, **OBITO)])
    inserir = _ConsultaDaTriagem._inserir

    def _a_outra_gravou_primeiro(self):
        if self._nome == "nsp_prazos_do_caso":
            inserir(self)
            raise APIError({"code": "23505", "message": "duplicate key value"})
        return inserir(self)

    monkeypatch.setattr(_ConsultaDaTriagem, "_inserir", _a_outra_gravou_primeiro)

    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})

    assert resposta.status_code == 201, resposta.text
    assert _prazos_na_tela(banco, caso) == PRAZOS_ESPERADOS["A"]
    assert len(banco.tabelas["nsp_notificacoes_externas"]) == 1


def test_o_caso_antes_da_confirmacao_nao_tem_prazo_nem_linha_externa():
    caso = _notificacao(1, **DO_CASO)
    banco = _banco([caso], [_sugestao(caso, **OBITO)])

    assert _prazos_na_tela(banco, caso) == {}
    assert _notificacao_externa(banco, caso) is None


# ═══════════════════════════════════════════════════════════════════════════
# A tabela de prazos na Configuração. O dublê faz o que a migration 208 faz:
# a carga do art. 26 e o trigger que grava o histórico a cada alteração.
# ═══════════════════════════════════════════════════════════════════════════

TABELA = "/api/nsp/configuracao/prazos"


class _ConsultaComHistorico(_ConsultaDoNucleo):
    def execute(self):
        if self._nome != "nsp_tabela_de_prazos" or self._acao != "update":
            return super().execute()
        antes = [dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)]
        resposta = super().execute()
        historico = self._banco.tabelas.setdefault("nsp_tabela_de_prazos_historico", [])
        for velha, nova in zip(antes, resposta.data, strict=True):
            if (velha["valor"], velha["unidade"]) != (nova["valor"], nova["unidade"]):
                historico.append(
                    {
                        "id": f"h{len(historico) + 1}",
                        "faixa": nova["faixa"],
                        "marco": nova["marco"],
                        "de_valor": velha["valor"],
                        "de_unidade": velha["unidade"],
                        "para_valor": nova["valor"],
                        "para_unidade": nova["unidade"],
                        "alterado_por": nova["atualizado_por"],
                        "alterado_em": f"2026-11-21T1{len(historico)}:00:00+00:00",
                    }
                )
        return resposta


class _BancoComTabela(_BancoDoNucleo):
    def table(self, nome: str):
        return _ConsultaComHistorico(self, nome)


def _carga_do_art_26() -> list[dict]:
    from app.services.seguranca_do_paciente import prazos

    return [
        {
            "faixa": faixa,
            "marco": marco,
            "valor": prazos.ART_26[(faixa, marco)].valor if (faixa, marco) in prazos.ART_26 else None,
            "unidade": prazos.ART_26[(faixa, marco)].unidade if (faixa, marco) in prazos.ART_26 else None,
        }
        for faixa in prazos.FAIXAS
        for marco in prazos.MARCOS_INTERNOS
    ]


def _banco_com_tabela(notificacoes=(), triagens=()) -> _BancoComTabela:
    banco = _BancoComTabela(_banco(list(notificacoes), list(triagens)).tabelas)
    banco.tabelas["participacoes"].append(_participacao("P7", "suplente"))
    banco.tabelas["participantes"].append(dict(SUPLENTE))
    banco.tabelas["nsp_tabela_de_prazos"] = _carga_do_art_26()
    banco.tabelas["nsp_tabela_de_prazos_historico"] = []
    return banco


def _alterar(banco, faixa, marco, corpo, pessoa=PRESIDENTE):
    return _cliente(banco, pessoa).put(f"{TABELA}/{faixa}/{marco}", json=corpo)


# ── 2. O prazo legal não é editável ────────────────────────────────────────


def test_a_tabela_mostra_os_prazos_legais_como_nao_editaveis():
    corpo = _cliente(_banco_com_tabela()).get(TABELA).json()

    legais = {linha["marco"]: linha for linha in corpo["legais"]}
    assert set(legais) == {"notificacao_externa", "complementacao_da_notificacao_externa"}
    assert all(linha["editavel"] is False for linha in legais.values())
    assert legais["notificacao_externa"]["celulas"]["A"] == "72 horas corridas do incidente"
    assert legais["notificacao_externa"]["celulas"]["C"] == "Até o 15º dia útil do mês seguinte"
    assert legais["complementacao_da_notificacao_externa"]["celulas"]["A"] == "60 dias corridos do incidente"
    assert {linha["marco"] for linha in corpo["internos"]}.isdisjoint(legais)
    assert corpo["pode_editar"] is True


@pytest.mark.parametrize("marco", ["notificacao_externa", "complementacao_da_notificacao_externa"])
def test_a_rota_recusa_alterar_o_prazo_legal(marco):
    banco = _banco_com_tabela()
    antes = [dict(linha) for linha in banco.tabelas["nsp_tabela_de_prazos"]]

    resposta = _alterar(banco, "A", marco, {"valor": 96, "unidade": "horas_corridas"})

    assert resposta.status_code == 422
    assert "Prazo legal" in resposta.json()["detail"]
    assert banco.tabelas["nsp_tabela_de_prazos"] == antes
    assert banco.tabelas["nsp_tabela_de_prazos_historico"] == []


# ── 3. Editar o interno grava o histórico e não alcança o caso classificado ──


def test_editar_um_prazo_interno_grava_quem_quando_de_e_para():
    banco = _banco_com_tabela()

    resposta = _alterar(banco, "A", "triagem", {"valor": 2, "unidade": "horas_uteis"})

    assert resposta.status_code == 200, resposta.text
    corpo = _cliente(banco).get(TABELA).json()
    celula = next(c for c in corpo["internos"] if (c["faixa"], c["marco"]) == ("A", "triagem"))
    assert (celula["valor"], celula["unidade"]) == (2, "horas_uteis")
    [registro] = corpo["historico"]
    assert registro["faixa"] == "A"
    assert registro["marco"] == "triagem"
    assert (registro["de"]["valor"], registro["de"]["unidade"]) == (4, "horas_uteis")
    assert (registro["para"]["valor"], registro["para"]["unidade"]) == (2, "horas_uteis")
    assert registro["quem"] == PRESIDENTE["nome_completo"]
    assert registro["quando"]


def test_mudar_a_tabela_nao_muda_o_caso_ja_classificado():
    caso = _notificacao(1, **DO_CASO)
    banco = _banco_com_tabela([caso], [_sugestao(caso, **OBITO)])
    confirmar = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})
    assert confirmar.status_code == 201, confirmar.text

    assert _alterar(banco, "A", "triagem", {"valor": 8, "unidade": "horas_uteis"}).status_code == 200

    assert _prazos_na_tela(banco, caso) == PRAZOS_ESPERADOS["A"]


def test_o_caso_confirmado_depois_da_mudanca_usa_a_tabela_nova():
    caso = _notificacao(1, **DO_CASO)
    banco = _banco_com_tabela([caso], [_sugestao(caso, **OBITO)])
    assert _alterar(banco, "A", "triagem", {"valor": 2, "unidade": "horas_uteis"}).status_code == 200

    confirmar = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})

    assert confirmar.status_code == 201, confirmar.text
    assert _prazos_na_tela(banco, caso)["triagem"] == ("interno", "10/11/2026 12:00")


@pytest.mark.parametrize(
    "corpo",
    [
        {"valor": 0, "unidade": "horas_uteis"},
        {"valor": 400, "unidade": "dias_corridos"},
        {"valor": 3, "unidade": "dia_util_do_mes_seguinte"},
        {"valor": 3, "unidade": None},
    ],
    ids=["zero", "acima do teto", "regra legal", "sem unidade"],
)
def test_o_prazo_interno_fora_das_regras_e_recusado_sem_historico(corpo):
    banco = _banco_com_tabela()

    assert _alterar(banco, "B", "triagem", corpo).status_code == 422
    assert banco.tabelas["nsp_tabela_de_prazos_historico"] == []


def test_o_prazo_interno_pode_ficar_sem_prazo_proprio():
    banco = _banco_com_tabela()

    resposta = _alterar(banco, "B", "comunicacao_a_direcao", {"valor": None, "unidade": None})

    assert resposta.status_code == 200, resposta.text
    [registro] = _cliente(banco).get(TABELA).json()["historico"]
    assert registro["de"] == {"valor": 24, "unidade": "horas_corridas"}
    assert registro["para"] == {"valor": None, "unidade": None}


# ── 5. Só a Presidência e o Acesso pleno editam a tabela ──────────────────


@pytest.mark.parametrize("pessoa", [PRESIDENTE, DIRETOR_EXECUTIVO], ids=["Presidência", "Acesso pleno"])
def test_a_presidencia_e_o_acesso_pleno_editam_a_tabela(pessoa):
    banco = _banco_com_tabela()

    assert _cliente(banco, pessoa).get(TABELA).json()["pode_editar"] is True
    assert _alterar(banco, "C", "triagem", {"valor": 1, "unidade": "dias_uteis"}, pessoa).status_code == 200


@pytest.mark.parametrize(
    "pessoa", [MEMBRO, SUPER_ADMIN, SUPLENTE], ids=["membro do Núcleo", "super admin sem Acesso pleno", "suplente"]
)
def test_quem_nao_e_presidencia_nem_acesso_pleno_nao_edita_a_tabela(pessoa):
    banco = _banco_com_tabela()
    antes = [dict(linha) for linha in banco.tabelas["nsp_tabela_de_prazos"]]

    resposta = _alterar(banco, "C", "triagem", {"valor": 1, "unidade": "dias_uteis"}, pessoa)

    assert resposta.status_code == 403
    assert banco.tabelas["nsp_tabela_de_prazos"] == antes
    assert banco.tabelas["nsp_tabela_de_prazos_historico"] == []


def test_o_super_admin_le_a_tabela_na_configuracao_sem_poder_editar():
    corpo = _cliente(_banco_com_tabela(), SUPER_ADMIN).get(TABELA).json()

    assert corpo["pode_editar"] is False
    assert all(linha["editavel"] is False for linha in corpo["internos"])


# ═══════════════════════════════════════════════════════════════════════════
# 6. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def _secao_do_kit(titulo: str) -> str:
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "seguranca-do-paciente.md").read_text(encoding="utf-8")
    partes = texto.split(f"## {titulo}\n", 1)
    assert len(partes) == 2, f"a seção {titulo!r} sumiu do kit"
    return partes[1].split("\n## ", 1)[0]


def test_o_kit_diz_os_prazos_do_caso_e_a_tabela_de_prazos():
    no_ar = _secao_do_kit("O que já está no ar")
    for termo in (
        "todos os prazos do Regimento",
        "data e hora",
        "72 horas corridas do incidente",
        "15º dia útil do mês seguinte",
        "60 dias corridos",
        "não se alteram pela tela",
        "VigiMed",
        "NOTIVISA",
        "Circunstância de risco não é notificada",
        "**Tabela de prazos**",
        "Só a Presidência e o Acesso pleno mudam um prazo",
        "histórico",
        "caso já classificado guarda os prazos",
    ):
        assert termo in no_ar, termo
    assert "os prazos," not in _secao_do_kit("O que ele ainda não faz")
