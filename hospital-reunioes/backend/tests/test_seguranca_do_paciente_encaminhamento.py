"""Encaminhar da tela de triagem (issue #1995, PRD #1979, ADR 0095 decisão 11
e ADR 0107 decisão 8).

Um bloco por critério de aceite:

1. encaminhar exige ao menos um destino e o motivo; o protocolo não muda;
2. o destino Ouvidoria registra o e-mail ao ouvidor com protocolo, motivo e
   relato;
3. o destino Canal de Conduta não envia nem grava conteúdo fora do Núcleo;
4. fora de escopo leva o caso a Fora de escopo, e a orientação aparece no
   acompanhamento;
5. Núcleo e Ouvidoria juntos mantêm o caso na triagem e registram o e-mail;
6. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória da triagem. Nenhum dado de pessoa real.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import _pessoa  # noqa: E402
from test_seguranca_do_paciente_notificacoes import _cliente as _cliente_publico  # noqa: E402
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    PRESIDENTE,
    _banco,
    _cliente,
    _notificacao,
    _secao_do_kit,
    _sugestao,
)

OUVIDOR = _pessoa("P7", perfil_ouvidoria="ouvidor")
OUVIDOR_DESLIGADO = _pessoa("P8", perfil_ouvidoria="ouvidor", ativo=False)
DIRETORIA_DA_OUVIDORIA = _pessoa("P9", perfil_ouvidoria="diretoria_executiva")
MOTIVO = "Reclamação de atendimento na recepção, sem incidente com o paciente."
RELATO = "A recepção demorou duas horas para chamar a paciente e ninguém explicou o motivo."


def _cenario(**campos) -> tuple[Any, dict]:
    caso = _notificacao(1, relato=RELATO, **campos)
    banco = _banco([caso], [_sugestao(caso)])
    banco.tabelas["participantes"] += [dict(OUVIDOR), dict(OUVIDOR_DESLIGADO), dict(DIRETORIA_DA_OUVIDORIA)]
    return banco, caso


def _encaminhar(banco, caso, pessoa=PRESIDENTE, **corpo):
    return _cliente(banco, pessoa).post(f"/api/nsp/triagem/{caso['id']}/encaminhamento", json=corpo)


def _escritas_fora_do_nucleo(banco) -> list[str]:
    """O que foi gravado em tabela que não é do Núcleo, nem o registro de
    e-mail do Núcleo."""
    return [nome for nome, _ in banco.escritas if not nome.startswith("nsp_")]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Destino e motivo obrigatórios; o protocolo não muda
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "corpo",
    [
        {"destinos": [], "motivo": MOTIVO},
        {"destinos": ["ouvidoria"], "motivo": "   "},
        {"destinos": ["ouvidoria"]},
        {"destinos": ["vigilancia"], "motivo": MOTIVO},
    ],
    ids=["sem destino", "motivo em branco", "sem motivo", "destino fora da lista"],
)
def test_encaminhar_sem_destino_ou_sem_motivo_e_recusado_sem_gravar(corpo):
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, **corpo)

    assert resposta.status_code == 422, resposta.text
    assert banco.tabelas.get("nsp_encaminhamentos", []) == []
    assert banco.tabelas.get("nsp_avisos", []) == []
    assert banco.notificacoes[0]["estado"] == "recebida"


def test_encaminhar_grava_o_destino_e_o_motivo_e_o_protocolo_nao_muda():
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, destinos=["canal_de_conduta"], motivo=MOTIVO)

    assert resposta.status_code == 201, resposta.text
    [encaminhamento] = banco.tabelas["nsp_encaminhamentos"]
    assert encaminhamento["notificacao_id"] == caso["id"]
    assert encaminhamento["destinos"] == ["canal_de_conduta"]
    assert encaminhamento["motivo"] == MOTIVO
    assert encaminhamento["autor_id"] == "P1"
    assert banco.notificacoes[0]["protocolo"] == "NSP-2026-0001"
    assert banco.notificacoes[0]["estado"] == "encaminhada"
