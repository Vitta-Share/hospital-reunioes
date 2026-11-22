"""O Me explique no cartão da Pergunta da Vitta (issue #2122, PRD #2112, ADR
0109, decisão 8).

O botão abre uma conversa particular com o Assistente de Tecnologia, uma por
Pergunta e por pessoa, que já começa com a Demanda e a Pergunta no contexto.
O Assistente explica na língua do Kit e propõe um rascunho de resposta. Nada
daqui entra na Conversa da Demanda, cria resposta ou vai ao GitHub. O custo
entra na conta do Assistente, no modelo padrão.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo` e
o modelo trocado pelo dublê dos testes do Assistente (`_ia`).
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_planejamento_demanda import _ia, _llm_em_mock  # noqa: E402, F401
from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    CONVERSA,
    DIRETOR,
    DIRETORA,
    PEDRO,
    TABELA,
    _criar,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
    emails,
)

from app.config import settings  # noqa: E402
from app.services import github_client  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

CONVERSAS = "tecnologia_conversas_do_me_explique"
CHAMADAS = "tecnologia_chamadas_ia"

EXPLICACAO = "A Vitta quer saber quem assina a ata quando a diretora clínica não está na reunião."
RASCUNHO = "Quem presidiu a reunião assina."


def _url(pergunta_id: str) -> str:
    return f"/api/admin/tecnologia/perguntas/{pergunta_id}/me-explique"


def _fala(mensagem: str = EXPLICACAO, rascunho: str | None = RASCUNHO) -> str:
    return json.dumps({"mensagem": mensagem, "rascunho": rascunho}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def chamadas_ao_github(monkeypatch) -> list[tuple]:
    """Toda ida ao GitHub fica gravada aqui, em vez de sair para a rede."""
    chamadas: list[tuple] = []

    def _gravar(*a, **kw):
        chamadas.append((a, kw))
        raise AssertionError("O Me explique foi ao GitHub.")

    monkeypatch.setattr(github_client.httpx, "request", _gravar)
    return chamadas


def _uma_pergunta():
    ponte, sb = _ponte()
    pergunta_id = _criar(ponte).json()["id"]
    return sb, pergunta_id


def _abrir(sb, logado, pergunta_id, monkeypatch, **corpo):
    return _tela(sb, logado, monkeypatch).post(_url(pergunta_id), json=corpo)


def _ler(sb, logado, pergunta_id, monkeypatch):
    return _tela(sb, logado, monkeypatch).get(_url(pergunta_id))


def _pedido_ao_modelo(cliente) -> str:
    """O texto que variou na chamada: o último pedido da pessoa ao modelo."""
    conteudo = cliente.chamadas[-1]["messages"][0]["content"]
    return conteudo if isinstance(conteudo, str) else "".join(b.get("text", "") for b in conteudo)


# ═══════════════════════════════════════════════════════════════════════════
# O botão abre a conversa já com a explicação
# ═══════════════════════════════════════════════════════════════════════════


class TestAbrir:
    def test_o_botao_abre_a_conversa_com_a_explicacao_da_demanda_e_da_pergunta(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        cliente = _ia(monkeypatch, _fala())

        resposta = _abrir(sb, DIRETORA, pergunta_id, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["mensagens"] == [{"papel": "assistente", "texto": EXPLICACAO, "rascunho": RASCUNHO}]
        pedido = _pedido_ao_modelo(cliente)
        assert "A Ata assinada no app" in pedido
        assert "Quem assina a Ata em nome da diretoria quando a senhora não está?" in pedido
        assert "A tela de assinatura da Ata espera essa regra para sair." in pedido
        assert "Quem presidiu a reunião" in pedido
