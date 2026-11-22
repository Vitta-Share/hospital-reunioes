"""Resolver e cancelar a Pergunta da Vitta pela ponte (issue #2121, PRD #2112,
ADR 0109, decisão 6).

A resposta não solta o trabalho sozinha: a Vitta lê e dá o ok no PedroOS, e
só então a ponte marca a Pergunta como resolvida, com o que foi decidido e o
que destravou. A Pergunta que deixou de ser necessária vira cancelada, com o
motivo. As duas passagens põem uma linha de sistema na Conversa da Demanda, e
a Pergunta resolvida ou cancelada não muda mais.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo`.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    CONVERSA,
    CONVERSA_DA_TELA,
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
from test_tecnologia_vinculo import _integracao_configurada, _montar  # noqa: E402, F401

from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

DECIDIDO = "Quem presidiu a reunião assina a Ata pela diretoria."
DESTRAVOU = "A tela de assinatura da Ata volta a andar e entra na próxima subida."
MOTIVO = "A diretoria decidiu na reunião de quinta, não precisa mais perguntar."


def _url(pergunta_id: str, acao: str) -> str:
    return f"/api/automacao/tecnologia/perguntas/{pergunta_id}/{acao}"


def _resolver(ponte, pergunta_id: str, **campos):
    corpo = {"github_login": "pedrorezendefig", "decidido": DECIDIDO, "destravou": DESTRAVOU, **campos}
    return ponte.post(_url(pergunta_id, "resolver"), json=corpo, headers={"X-API-Key": CHAVE})


def _cancelar(ponte, pergunta_id: str, **campos):
    corpo = {"github_login": "pedrorezendefig", "motivo": MOTIVO, **campos}
    return ponte.post(_url(pergunta_id, "cancelar"), json=corpo, headers={"X-API-Key": CHAVE})


def _pergunta(estado: str = "aberta"):
    """A Pergunta da Vitta para a Diretora, já no estado pedido. A resposta é
    gravada direto na linha, com as colunas da migration (o responder pela
    tela tem o próprio teste, #2119)."""
    ponte, sb = _ponte()
    pergunta_id = _criar(ponte).json()["id"]
    [linha] = sb.tabelas[TABELA]
    if estado != "aberta":
        linha.update(
            {
                "estado": estado,
                "resposta_opcao": "B",
                "respondida_por": DIRETORA["id"],
                "respondida_em": "2026-11-22T09:30:00Z",
            }
        )
    if estado == "resolvida":
        linha.update({"resolucao_decidido": "Outra decisão.", "resolucao_destravou": "Outra coisa.", "resolvida_em": "x"})
    if estado == "cancelada":
        linha.update({"resolucao_decidido": "Outro motivo.", "cancelada_em": "x"})
    return ponte, sb, pergunta_id


def _linhas_de_sistema(sb) -> list[str]:
    return [m["texto"] for m in sb.tabelas[CONVERSA] if m.get("origem") == "sistema"]


# ═══════════════════════════════════════════════════════════════════════════
# Resolver
# ═══════════════════════════════════════════════════════════════════════════


class TestResolver:
    def test_resolver_a_respondida_grava_a_decisao_e_o_que_destravou(self):
        ponte, sb, pergunta_id = _pergunta("respondida")

        resposta = _resolver(ponte, pergunta_id)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["estado"] == "resolvida"
        [linha] = sb.tabelas[TABELA]
        assert linha["estado"] == "resolvida"
        assert (linha["resolucao_decidido"], linha["resolucao_destravou"]) == (DECIDIDO, DESTRAVOU)
        assert linha["resolvida_em"]
        assert not linha.get("cancelada_em")

    def test_resolver_poe_na_conversa_a_linha_de_sistema_com_a_decisao_e_o_que_destravou(self):
        ponte, sb, pergunta_id = _pergunta("respondida")

        _resolver(ponte, pergunta_id)

        assert _linhas_de_sistema(sb)[-1] == (
            "Pergunta resolvida: quem assina a Ata pela diretoria\n"
            f"O que foi decidido: {DECIDIDO}\n"
            f"O que destravou: {DESTRAVOU}"
        )
