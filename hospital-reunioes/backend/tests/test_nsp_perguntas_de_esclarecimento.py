"""As perguntas de esclarecimento do agente do Núcleo (issue #1991, PRD #1979).

Um bloco por critério de aceite:

1. as perguntas aparecem só depois do registro e nunca bloqueiam o envio;
2. a página de acompanhamento mostra as perguntas sem resposta e aceita a
   resposta pelo protocolo e o código, ou o contato;
3. a resposta antes da confirmação gera nova linha de triagem do agente;
   depois da confirmação, fica gravada e não chama o agente;
4. sem pergunta proposta, não há pergunta a mostrar;
5. o texto do Produto no Kit de conhecimento diz o comportamento novo.

O modelo é sempre um dublê, como nos testes do agente (issue #1990).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_agente_de_triagem import (  # noqa: E402
    SUGESTAO_DA_BOMBA,
    _BancoComCota,
    _com_modelo,
)
from test_seguranca_do_paciente_notificacoes import (  # noqa: E402
    ANONIMO,
    IDENTIFICADO,
    PUBLICO,
    _banco,
    _cliente,
)

from app.config import settings  # noqa: E402
from app.limiter import limiter  # noqa: E402

PERGUNTAS = "/api/nsp/publico/perguntas"
RESPOSTAS = "/api/nsp/publico/respostas"

DUAS_PERGUNTAS = [
    "A bomba foi reprogramada por alguém depois do alarme?",
    "O paciente precisou de transfusão?",
]
COM_PERGUNTAS = {**SUGESTAO_DA_BOMBA, "perguntas_ao_notificante": DUAS_PERGUNTAS}


@pytest.fixture(autouse=True)
def _limite_zerado():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def ligado(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "nsp_agente_ligado", True)


def _notificar(banco: _BancoComCota, envio: dict = ANONIMO) -> dict:
    resposta = _cliente(banco).post(PUBLICO, json={**envio, "origem": "endereco"})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _chave(recibo: dict) -> dict:
    return {"protocolo": recibo["protocolo"], "codigo": recibo["codigo_acompanhamento"]}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Depois do registro, sem bloquear o envio
# ═══════════════════════════════════════════════════════════════════════════


def test_as_perguntas_do_agente_aparecem_depois_do_registro(monkeypatch, ligado):
    _com_modelo(monkeypatch, COM_PERGUNTAS)
    banco = _BancoComCota(_banco().tabelas)

    recibo = _notificar(banco)
    resposta = _cliente(banco).post(PERGUNTAS, json=_chave(recibo))

    assert "perguntas" not in recibo
    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"perguntas": DUAS_PERGUNTAS, "aguardando": False}
