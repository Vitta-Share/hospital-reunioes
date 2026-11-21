"""Os avisos por e-mail do Canal de Conduta (issue #1840, PRD #1786).

Uma classe por critério de aceite da issue:

1. tarefa nova gera e-mail ao membro responsável, com o texto fixo e o link
   para MINHA VEZ;
2. o e-mail e o link não contêm protocolo, nome, rito nem trecho de relato;
3. caso do rito Completo ou da Rota Especial avisa na hora;
4. os lembretes saem a cinco dias e a um dia do prazo;
5. nenhum e-mail é enviado a quem relatou;
6. o job não chama IA;
7. o texto do Produto no kit de conhecimento diz o comportamento novo.

O banco é o dublê de `conduta_apoio`, o Comitê é o de `test_conduta_triagem`
e o e-mail é sempre dublado. As pessoas são de teste.
"""

from __future__ import annotations

import base64
import inspect
import os
import secrets
import sys
from datetime import timedelta

import pytest
from test_conduta_triagem import (
    COORDENACAO,
    DE_FORA,
    DENTRO_COMPLETO,
    DENTRO_RAPIDO,
    FORA_DP,
    HOJE,
    MEMBRO,
    RELATO,
    SEGUNDO_LEITOR,
    Comite,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.services.conduta import avisos  # noqa: E402

FRASE = "Há uma tarefa no Canal de Conduta."


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "frontend_url", "https://app.hsm.test")


@pytest.fixture
def emails(monkeypatch) -> list[dict]:
    enviados: list[dict] = []

    def _enviar(destinatario, assunto, html, texto, **kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html, "texto": texto, **kw})
        return True

    monkeypatch.setattr(avisos, "_enviar_email", _enviar)
    return enviados


@pytest.fixture
def comite() -> Comite:
    return Comite()


def _para(emails: list[dict]) -> list[str]:
    return sorted(e["para"] for e in emails)


def _email(pid: str) -> str:
    return f"{pid.lower()}@hsm.test"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Tarefa nova gera e-mail ao membro responsável
# ═══════════════════════════════════════════════════════════════════════════


class TestTarefaNova:
    def test_caso_recebido_avisa_a_coordenacao_que_confirma_a_triagem(self, comite, emails):
        comite.caso()

        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _para(emails) == [_email(COORDENACAO)]
        assert emails[0]["assunto"] == FRASE
        assert FRASE in emails[0]["texto"]
        assert "https://app.hsm.test/comite-de-conduta\n" in emails[0]["texto"]
        assert 'href="https://app.hsm.test/comite-de-conduta"' in emails[0]["html"]
