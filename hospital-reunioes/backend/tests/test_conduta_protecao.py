"""A página "Como este canal protege você" do Canal de Conduta (issue #1846,
PRD #1786, especificação seção 4.3).

Pública, sem login. Mostra os textos vigentes das Configurações, bloco a
bloco, e o contato do encarregado de dados quando ele está preenchido. Bloco
que a coordenação ainda não salvou mostra o texto inicial, o da especificação
com as decisões do diretor (6, 10 e 38). Cada versão da página fica arquivada
pela data: dado um dia, a rota devolve a página como ela estava.

As pessoas daqui são de teste. O banco é o dublê de `conduta_apoio`.
"""

from __future__ import annotations

import re

import pytest
from test_conduta_configuracoes import (  # noqa: F401 (fixtures)
    COORDENACAO,
    ROTA,
    _ambiente,
    _cliente,
    banco,
    canal_aberto,
)

ROTA_DA_PAGINA = "/api/conduta/protecao"


def _bloco(corpo: dict, chave: str) -> dict:
    return next(b for b in corpo["blocos"] if b["chave"] == chave)


def _versao_salva_em(banco, chave: str, versao: int, texto: str, criado_em: str) -> None:
    banco.tabelas.setdefault("conduta_configuracoes", []).append(
        {
            "id": f"{chave}-v{versao}",
            "chave": chave,
            "versao": versao,
            "texto": texto,
            "autor_id": COORDENACAO["id"],
            "criado_em": criado_em,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os textos vigentes das Configurações
# ═══════════════════════════════════════════════════════════════════════════


def test_a_pagina_mostra_o_texto_vigente_das_configuracoes(banco, canal_aberto):
    coordenacao = _cliente(banco, COORDENACAO)
    coordenacao.post(f"{ROTA}/protecao_prazos", json={"texto": "Leitura em até 5 dias úteis."})
    vigente = coordenacao.post(f"{ROTA}/protecao_prazos", json={"texto": "Leitura em até 3 dias úteis."}).json()

    resposta = _cliente(banco).get(ROTA_DA_PAGINA)

    assert resposta.status_code == 200, resposta.text
    assert _bloco(resposta.json(), "protecao_prazos") == {
        "chave": "protecao_prazos",
        "titulo": "Prazos",
        "texto": "Leitura em até 3 dias úteis.",
        "versao": 2,
        "versao_id": vigente["id"],
    }
