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


def test_bloco_ainda_nao_salvo_mostra_o_texto_inicial_com_as_decisoes_do_diretor(banco, canal_aberto):
    corpo = _cliente(banco).get(ROTA_DA_PAGINA).json()

    quem_le = _bloco(corpo, "protecao_quem_le")
    ia = _bloco(corpo, "protecao_ia")
    assert (quem_le["versao"], quem_le["versao_id"]) == (None, None)
    # Decisão 10: a Direção só lê a conclusão e a ata. Decisão 6: a frase da empresa fica.
    assert "A Direção só lê a conclusão e a ata do caso, nunca o relato." in quem_le["texto"]
    assert "nem a empresa que desenvolve o sistema" in quem_le["texto"]
    # Decisão 38: a IA guarda até 30 dias e não treina.
    assert "guarda o texto por até 30 dias e não o usa para treinar" in ia["texto"]
    assert [b["titulo"] for b in corpo["blocos"]] == [
        "Frase de abertura",
        "Para quem relata",
        "Para quem é citado",
        "Quem lê e quem não lê",
        "Inteligência artificial",
        "Se envolver a Direção ou a família",
        "Prazos",
        "O que o canal não garante",
    ]


def test_com_o_canal_fechado_a_pagina_responde_404(banco):
    assert _cliente(banco).get(ROTA_DA_PAGINA).status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 2. Cada versão da página fica arquivada com a data
# ═══════════════════════════════════════════════════════════════════════════


def test_cada_versao_da_pagina_fica_arquivada_com_a_data(banco, canal_aberto):
    _versao_salva_em(banco, "protecao_prazos", 1, "Leitura em até 5 dias úteis.", "2026-11-10T13:00:00+00:00")
    # 01h de 16/11 em UTC ainda é 15/11 em São Paulo.
    _versao_salva_em(banco, "protecao_prazos", 2, "Leitura em até 3 dias úteis.", "2026-11-16T01:00:00+00:00")
    _versao_salva_em(banco, "protecao_direcao", 1, "Vai à Rota Especial.", "2026-11-10T18:00:00+00:00")
    cliente = _cliente(banco)

    hoje = cliente.get(ROTA_DA_PAGINA).json()
    em_12 = cliente.get(ROTA_DA_PAGINA, params={"em": "2026-11-12"}).json()
    em_15 = cliente.get(ROTA_DA_PAGINA, params={"em": "2026-11-15"}).json()
    em_09 = cliente.get(ROTA_DA_PAGINA, params={"em": "2026-11-09"}).json()

    assert hoje["versoes"] == ["2026-11-15", "2026-11-10"]
    assert _bloco(hoje, "protecao_prazos")["texto"] == "Leitura em até 3 dias úteis."
    assert _bloco(em_12, "protecao_prazos")["texto"] == "Leitura em até 5 dias úteis."
    assert _bloco(em_12, "protecao_direcao")["texto"] == "Vai à Rota Especial."
    assert _bloco(em_15, "protecao_prazos")["texto"] == "Leitura em até 3 dias úteis."
    assert _bloco(em_09, "protecao_prazos")["versao"] is None
    assert (hoje["em"], em_12["em"], em_09["em"]) == (None, "2026-11-12", "2026-11-09")


def test_dia_que_nao_e_data_responde_422(banco, canal_aberto):
    assert _cliente(banco).get(ROTA_DA_PAGINA, params={"em": "ontem"}).status_code == 422
