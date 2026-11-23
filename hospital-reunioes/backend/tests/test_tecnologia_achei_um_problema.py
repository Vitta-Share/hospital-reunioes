"""Achei um problema no Pedido de implantação (issue #2210, PRD #2205, ADR
0111, decisão 9).

O cartão do Pedido de implantação abre o Assistente de Tecnologia em modo bug,
com o texto inicial que nomeia o Pedido e a entrega. No Criar o card desse
bug, a Demanda nova guarda de qual Demanda veio, a issue cita o PRD de origem
na parte técnica, e o Pedido passa a esperar a Demanda de bug: o cartão mostra
"Espera a Demanda N" e o Concluir recusa com o motivo até ela ficar Entregue.
O PRD de origem não reabre.

Pela ROTA de verdade (ponte e tela), com o Supabase em memória, o modelo e o
GitHub dublados.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_kit_conhecimento import ARQUIVO_DA_ABA  # noqa: E402
from test_kit_conhecimento import _texto as _texto_do_kit  # noqa: E402
from test_planejamento_demanda import _ia  # noqa: E402
from test_tecnologia_anexos import _StorageFake  # noqa: E402
from test_tecnologia_chat import CAMPOS_RESPONDIDOS, CRITERIOS, _turno  # noqa: E402
from test_tecnologia_passo_a_passo_da_vitta import _concluir, _marcar, emails  # noqa: E402, F401
from test_tecnologia_pedido_de_implantacao import CARD, IMPLANTACAO, PASSOS, github  # noqa: E402, F401
from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    CRIAR,
    DEMANDA,
    DIRETORA,
    TABELA,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
)
from test_tecnologia_vinculo import BASE, _GithubFalso, _integracao_configurada, _montar  # noqa: E402, F401

from app.services import tecnologia_perguntas  # noqa: E402

CHAT = f"{BASE}/chat"
ESPERANDO = f"{BASE}/perguntas/esperando"
# O PRD da entrega: o card da Demanda de origem (`_a_demanda` da Pergunta da Vitta).
PRD = 1700


@pytest.fixture(autouse=True)
def _llm_em_mock(monkeypatch):
    from app.services import ai_processor

    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "mock")


def _pedido_de_implantacao():
    """O Pedido de implantação nasce pela ponte, na Demanda da entrega."""
    ponte, sb = _ponte()
    sb.storage = _StorageFake()
    resposta = ponte.post(CRIAR, json=IMPLANTACAO, headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 201, resposta.text
    return sb, resposta.json()["id"]


def _na_tela(sb, monkeypatch, logado=DIRETORA):
    cliente, _, gh = _montar(logado=logado, supabase=sb, github=_GithubFalso({}), monkeypatch=monkeypatch)
    return cliente, gh


def _achei_um_problema(cliente, monkeypatch, pedido_id):
    _ia(monkeypatch, _turno(mensagem="Em qual passo deu errado?"))
    return cliente.post(CHAT, json={"escolha": "bug", "pedido_id": pedido_id})


def _demanda(sb, demanda_id) -> dict:
    return next(d for d in sb.tabelas["tecnologia_demandas"] if d["id"] == demanda_id)


def _pedido(sb, pedido_id) -> dict:
    return next(p for p in sb.tabelas[TABELA] if p["id"] == pedido_id)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Achei um problema abre o Assistente em modo bug
# ═══════════════════════════════════════════════════════════════════════════


class TestAbreOAssistente:
    def test_achei_um_problema_abre_o_bug_com_o_texto_inicial_do_pedido(self, monkeypatch):
        sb, pedido_id = _pedido_de_implantacao()
        cliente, _ = _na_tela(sb, monkeypatch)

        resposta = _achei_um_problema(cliente, monkeypatch, pedido_id)

        assert resposta.status_code == 201, resposta.text
        corpo = resposta.json()
        demanda = _demanda(sb, corpo["demanda_id"])
        assert demanda["tipo"] == "defeito"
        falas = [(m["autor"], m["texto"]) for m in corpo["mensagens"]]
        assert falas[1:] == [
            ("diretor", "Bug"),
            (
                "diretor",
                'Achei um problema no Pedido de implantação "testar o anonimato do Canal de Conduta",'
                ' da entrega "A Ata assinada no app".',
            ),
            ("ia", "Em qual passo deu errado?"),
        ]

    def test_so_o_pedido_de_implantacao_aberto_tem_o_achei_um_problema(self, monkeypatch):
        sb, pedido_id = _pedido_de_implantacao()
        _pedido(sb, pedido_id)["tipo"] = "passo_a_passo"
        cliente, _ = _na_tela(sb, monkeypatch)
        antes = len(sb.tabelas["tecnologia_demandas"])

        resposta = _achei_um_problema(cliente, monkeypatch, pedido_id)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_PROBLEMA_SO_NA_IMPLANTACAO}
        assert len(sb.tabelas["tecnologia_demandas"]) == antes


# ═══════════════════════════════════════════════════════════════════════════
# 2. O Criar o card liga o bug à Demanda de origem e ao Pedido
# ═══════════════════════════════════════════════════════════════════════════


def _bug_ate_o_resumo(sb, monkeypatch, pedido_id):
    cliente, gh = _na_tela(sb, monkeypatch)
    bug_id = _achei_um_problema(cliente, monkeypatch, pedido_id).json()["demanda_id"]
    _ia(
        monkeypatch,
        _turno(pronto=True, mensagem="Montei o resumo. Confere?", campos=CAMPOS_RESPONDIDOS, criterios=CRITERIOS),
    )
    resposta = cliente.post(f"{CHAT}/{bug_id}", json={"texto": "O relato de teste saiu com o meu nome."})
    assert resposta.json()["estado"] == "resumido", resposta.text
    return cliente, gh, bug_id


def _bug_com_card(monkeypatch):
    sb, pedido_id = _pedido_de_implantacao()
    cliente, gh, bug_id = _bug_ate_o_resumo(sb, monkeypatch, pedido_id)
    resposta = cliente.post(f"{CHAT}/{bug_id}/criar-card")
    assert resposta.status_code == 200, resposta.text
    return sb, gh, pedido_id, bug_id


class TestCriarOCardDoBug:
    def test_o_criar_o_card_grava_a_demanda_de_origem_e_liga_o_pedido_ao_bug(self, monkeypatch):
        sb, _, pedido_id, bug_id = _bug_com_card(monkeypatch)

        assert _demanda(sb, bug_id)["demanda_origem_id"] == DEMANDA
        assert _pedido(sb, pedido_id)["espera_demanda_id"] == bug_id

    def test_a_issue_do_bug_cita_o_prd_de_origem_na_parte_tecnica(self, monkeypatch):
        _, gh, _, _ = _bug_com_card(monkeypatch)

        [issue] = gh.criadas
        _, tecnica = issue["corpo"].split("\n---\n", 1)
        assert f"## PRD de origem\n\n#{PRD}" in tecnica

    def test_antes_do_criar_o_card_o_pedido_nao_espera_o_bug(self, monkeypatch):
        sb, pedido_id = _pedido_de_implantacao()
        _, _, bug_id = _bug_ate_o_resumo(sb, monkeypatch, pedido_id)

        assert _pedido(sb, pedido_id).get("espera_demanda_id") is None
        assert _demanda(sb, bug_id).get("demanda_origem_id") is None
