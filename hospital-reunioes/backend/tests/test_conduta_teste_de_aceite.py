"""O comando do teste do Anexo B e a trava de IA no CI (issue #1827, ADR 0097
decisão 15).

O que se confere:

- os 12 casos do Anexo B estão no repositório e o comando não entra no CI;
- sem a palavra de confirmação, o comando não cria cliente nem chama a IA;
- com respostas iguais ao gabarito, as metas batem; um caso com termo da
  regra de proteção respondido como FORA derruba a meta;
- o agente nasce desligado, e com ele desligado nenhum caso chega ao modelo;
- o kit de conhecimento diz o comportamento novo.

O modelo é sempre um dublê: nenhum teste chama a IA de verdade.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from conduta_apoio import Banco

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import Settings, settings  # noqa: E402
from app.services.conduta import agente_de_triagem as agente  # noqa: E402
from app.services.conduta import casos  # noqa: E402
from scripts import conduta_teste_de_aceite as comando  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
KIT = Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "canal-de-conduta.md"


def _gabarito_como_saida(caso: dict) -> dict:
    g = caso["gabarito"]

    def item(valor, **extra):
        return {"valor": valor, "justificativa": "Pelo gabarito.", "trecho": "", **extra}

    return {
        "escopo": item(g["escopo"], destino=g["destino"]),
        "categoria": item(g["categoria"]),
        "rito": item(g["rito"]),
        "especial": item(g["especial"], citados="diretora" if g["especial"] == "SIM" else ""),
        "risco_imediato": item(g["risco_imediato"]),
        "assunto_para_lista": item("Assunto do caso"),
        "resumo": item("Resumo do caso."),
        "lacunas": item([]),
        "perguntas_ao_denunciante": item([]),
        "casos_parecidos": item([]),
        "relatos_repetidos_improcedentes": item("NAO"),
        "sinalizar_nsp": item(g.get("sinalizar_nsp", "NAO")),
        "confianca": item("ALTA"),
    }


class ModeloDoGabarito:
    """Responde a cada relato com o gabarito do caso, menos as trocas pedidas."""

    def __init__(self, trocas: dict[int, dict] | None = None):
        self.trocas = trocas or {}
        self.chamadas = 0
        self.messages = self
        self._por_mensagem = {comando.mensagem(caso): caso for caso in comando.carregar_casos()}

    def create(self, **argumentos):
        self.chamadas += 1
        caso = self._por_mensagem[argumentos["messages"][0]["content"]]
        saida = {**_gabarito_como_saida(caso), **self.trocas.get(caso["id"], {})}
        return SimpleNamespace(
            stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(saida, ensure_ascii=False))]
        )


def test_os_12_casos_do_anexo_b_estao_no_repositorio_e_o_comando_fica_fora_do_ci():
    casos_do_anexo = comando.carregar_casos()
    assert [caso["id"] for caso in casos_do_anexo] == list(range(1, 13))
    assert all(agente.validar_saida(_gabarito_como_saida(caso)) == [] for caso in casos_do_anexo)
    for workflow in (RAIZ / ".github" / "workflows").glob("*.yml"):
        assert "conduta_teste_de_aceite" not in workflow.read_text(encoding="utf-8"), workflow.name


def test_sem_a_confirmacao_o_comando_nao_chama_a_ia(monkeypatch, capsys):
    def _nao_pode(*_a, **_kw):
        raise AssertionError("o cliente da IA foi criado sem confirmação")

    monkeypatch.setattr(comando, "ClienteDaAnthropic", _nao_pode)
    # Com chave: sem ela o comando pararia por outro motivo, e o teste não diria nada.
    monkeypatch.setattr(comando.settings, "anthropic_api_key", "chave-de-teste")

    saida = comando.main([], perguntar=lambda _pergunta: "sim")

    assert saida == 1
    impresso = capsys.readouterr().out
    assert "36 chamadas" in impresso
    assert "Estimativa: US$" in impresso
    assert "Nada foi chamado." in impresso


def test_com_o_gabarito_as_metas_batem_pela_funcao_do_app(tmp_path, capsys):
    modelo = ModeloDoGabarito()

    saida = comando.main(["--saida", str(tmp_path / "r.json")], perguntar=lambda _p: "rodar", cliente=modelo)

    assert saida == 0
    assert modelo.chamadas == 36
    assert "Metas do Anexo B: batidas." in capsys.readouterr().out


def test_caso_com_termo_de_protecao_como_fora_derruba_a_meta(tmp_path, capsys):
    """Caso 11: o assunto parece de DP, mas há ameaça. FORA aqui reprova."""
    fora = {
        "escopo": {"valor": "FORA", "destino": "DP", "justificativa": "Vale-transporte.", "trecho": ""},
        "categoria": {"valor": "", "justificativa": "Fora.", "trecho": ""},
        "rito": {"valor": "ENCAMINHAMENTO", "justificativa": "Fora.", "trecho": ""},
    }
    modelo = ModeloDoGabarito({11: fora})

    saida = comando.main(["--saida", str(tmp_path / "r.json")], perguntar=lambda _p: "rodar", cliente=modelo)

    impresso = capsys.readouterr().out
    assert saida == 2
    assert "| Caso com termo da regra de proteção classificado como FORA | 1 (11) | 0 | não |" in impresso
    assert "Metas do Anexo B: NÃO batidas." in impresso


def test_dois_ritos_errados_numa_rodada_ainda_batem_e_tres_nao():
    casos_do_anexo = comando.carregar_casos()
    errado = {"rito": {"valor": "RAPIDO", "justificativa": "x", "trecho": ""}}
    for trocados, bate in (((3, 4), True), ((3, 4, 5), False)):
        resultados = comando.rodar(ModeloDoGabarito(dict.fromkeys(trocados, errado)), casos_do_anexo, "m", vezes=1)
        linha = next(x for x in comando.metricas(casos_do_anexo, resultados) if x["criterio"] == "Rito certo")
        assert linha["bateu"] is bate


# ═══════════════════════════════════════════════════════════════════════════
# 8. Nenhuma chamada de IA roda no CI
# ═══════════════════════════════════════════════════════════════════════════


def test_o_agente_nasce_desligado():
    assert Settings.model_fields["conduta_agente_ligado"].default is False


def test_com_o_agente_desligado_o_caso_novo_nao_chega_ao_modelo(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "conduta_agente_ligado", False)
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")

    def _nao_pode(*_a, **_kw):
        raise AssertionError("o cliente da IA foi criado com o agente desligado")

    monkeypatch.setattr(agente, "ClienteDaAnthropic", _nao_pode)
    banco = Banco()
    caso = casos.registrar_caso(banco, relato="Um relato qualquer.", categoria=None)

    agente.triar_caso(banco, caso["id"])

    [linha] = banco.tabelas["conduta_sugestoes"]
    assert linha["situacao"] == "manual" and linha["motivo_manual"] == "desligado"
    assert banco.tabelas["conduta_trilha"][-1]["detalhe"] == "sem sugestão do agente: o agente está desligado"


# ═══════════════════════════════════════════════════════════════════════════
# 9. O texto do Produto Canal de Conduta no kit diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "frase",
    [
        "Cada relato novo é lido uma vez pelo agente de triagem",
        "cada item aparece como Sugestão, com a justificativa ao lado",
        "Discordar pede o motivo em uma linha",
        "O possível impedimento é conferido pelo aplicativo, sem inteligência artificial",
        "o caso entra na fila para triagem manual",
    ],
)
def test_o_kit_diz_o_que_o_agente_de_triagem_faz(frase):
    assert frase in KIT.read_text(encoding="utf-8")
