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
