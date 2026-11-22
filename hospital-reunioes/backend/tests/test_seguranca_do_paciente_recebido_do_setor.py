"""Encaminhar à Segurança do Trabalho e à queixa técnica com "Recebido"
(issue #1996, PRD #1979, ADR 0107 decisão 8).

Um bloco por critério de aceite:

1. o e-mail vai ao titular vigente do setor; sem titular, vai ao gestor e a
   Presidência é avisada;
2. o link abre a tela com o resumo e o botão "Recebido"; depois do clique,
   recusa nova abertura; vencido, recusa;
3. o banco guarda só o hash do token;
4. sem o clique no prazo, o e-mail é reenviado uma única vez;
5. o caso mostra o recebido com data e hora;
6. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória da triagem. Nenhum dado de pessoa real.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_triagem import (  # noqa: E402
    PRESIDENTE,
    SETOR,
    _banco,
    _BancoDaTriagem,
    _cliente,
    _ConsultaDaTriagem,
    _notificacao,
    _secao_do_kit,
    _sugestao,
)

from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_recebimento as recebimento_router  # noqa: E402
from app.services.seguranca_do_paciente import emails, encaminhamento, recebimento  # noqa: E402

SEGURANCA_DO_TRABALHO = {"id": "55555555-5555-5555-5555-555555555555", "nome": "Segurança do Trabalho", "ativo": True}
FARMACIA = {"id": "66666666-6666-6666-6666-666666666666", "nome": "Farmácia Hospitalar", "ativo": True}
MOTIVO = "A técnica se feriu com a agulha ao descartar o material."
RELATO = "Relato com o nome da paciente Maria de Teste, que não pode sair no link."
# Uma terça-feira às 10h de Brasília: dentro do expediente.
AGORA = datetime(2026, 11, 10, 13, 0, tzinfo=UTC)


def _responsavel(rid: str, setor: str, papel: str, **campos) -> dict[str, Any]:
    base = {
        "id": rid,
        "setor": setor,
        "papel": papel,
        "nome": f"Responsável {rid}",
        "email": f"{rid.lower()}@hsm.test",
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": None,
    }
    return {**base, **campos}


class _ConsultaComIs(_ConsultaDaTriagem):
    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self


class _Banco(_BancoDaTriagem):
    def table(self, nome: str):
        return _ConsultaComIs(self, nome)


def _cenario(responsaveis: list[dict] | None = None) -> tuple[_Banco, dict]:
    caso = _notificacao(1, relato=RELATO)
    base = _banco([caso], [_sugestao(caso)])
    banco = _Banco(base.tabelas)
    banco.tabelas["setores"] += [dict(SEGURANCA_DO_TRABALHO), dict(FARMACIA)]
    banco.tabelas["ouvidoria_setor_responsaveis"] = (
        responsaveis
        if responsaveis is not None
        else [
            _responsavel("R1", SEGURANCA_DO_TRABALHO["nome"], "titular"),
            _responsavel("R2", SEGURANCA_DO_TRABALHO["nome"], "gestor"),
            _responsavel("R3", FARMACIA["nome"], "titular"),
        ]
    )
    return banco, caso


def _encaminhar(banco, caso, **corpo):
    corpo.setdefault("motivo", MOTIVO)
    return _cliente(banco, PRESIDENTE).post(f"/api/nsp/triagem/{caso['id']}/encaminhamento", json=corpo)


def _a_seguranca_do_trabalho(banco, caso):
    return _encaminhar(
        banco, caso, destinos=["seguranca_do_trabalho"], setores={"seguranca_do_trabalho": SEGURANCA_DO_TRABALHO["id"]}
    )


@pytest.fixture
def enviados(monkeypatch) -> list[dict]:
    """O que o provedor de e-mail recebeu, sem sair nada de verdade."""
    caixa: list[dict] = []

    def _enviar(para, assunto, html, texto):
        caixa.append({"para": para, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(emails, "_enviar_email", _enviar)
    return caixa


def _do_setor(banco) -> list[dict]:
    return [a for a in banco.tabelas.get("nsp_avisos", []) if a["marco"] == recebimento.MARCO_DO_SETOR]


def _token(email: dict) -> str:
    [token] = re.findall(r"/notificar/recebido/([A-Za-z0-9_-]+)", email["texto"])
    return token


def _publico(banco) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(recebimento_router.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


@pytest.fixture(autouse=True)
def _relogio(monkeypatch):
    """O encaminhamento acontece em AGORA, dentro do expediente."""
    monkeypatch.setattr(encaminhamento, "_agora", lambda: AGORA)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


# ═══════════════════════════════════════════════════════════════════════════
# 1. O e-mail vai ao titular vigente; sem titular, ao gestor, e a Presidência
#    é avisada
# ═══════════════════════════════════════════════════════════════════════════


def test_encaminhar_a_seguranca_do_trabalho_manda_o_email_ao_titular_vigente(enviados):
    banco, caso = _cenario()

    resposta = _a_seguranca_do_trabalho(banco, caso)

    assert resposta.status_code == 201, resposta.text
    [registro] = _do_setor(banco)
    assert registro["caso_id"] == caso["id"]
    emails.despachar_pendentes(banco, AGORA)
    [email] = enviados
    assert email["para"] == "r1@hsm.test"
    assert "NSP-2026-0001" in email["assunto"]
    assert MOTIVO in email["texto"]
    assert banco.notificacoes[0]["estado"] == "encaminhada"
