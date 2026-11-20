"""A Pendência nasce no envio da Ata para assinatura (ADR 0098, decisões 1 a 3; issue #1867).

No clique de enviar, a Reunião vai para AGUARDANDO_ASSINATURA e nascem todas
as Pendências do quadro. A ClickSign roda em seguida; se falhar, fica o
Reenviar, sem voltar o estado e sem criar dois Envelopes. Depois do envio,
reprocessar e corrigir a Ata ficam bloqueados. O Aceite interno é só ciência.
A reconciliação das 5h30 cria o que falta.

O evento de nascimento no Histórico vem do banco (trigger da migration 171),
provado em `test_pendencia_historico_banco.py`.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.routers import reunioes as reunioes_router  # noqa: E402

# ─── Mock Supabase ───────────────────────────────────────────────────────────


@dataclass
class _Result:
    data: Any


class _Not:
    def __init__(self, query: _TableQuery):
        self._q = query

    def is_(self, col, _value):
        self._q._filtros.append(lambda r, c=col: r.get(c) is not None)
        return self._q


class _TableQuery:
    def __init__(self, rows_ref: list):
        self._rows = rows_ref
        self._op = "select"
        self._payload: Any = None
        self._filtros: list = []
        self._limit: int | None = None

    def select(self, *_a, **_kw):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, value):
        self._filtros.append(lambda r, c=col, v=value: r.get(c) == v)
        return self

    def neq(self, col, value):
        self._filtros.append(lambda r, c=col, v=value: r.get(c) != v)
        return self

    def in_(self, col, values):
        vals = list(values)
        self._filtros.append(lambda r, c=col: r.get(c) in vals)
        return self

    def is_(self, col, _value):
        self._filtros.append(lambda r, c=col: r.get(c) is None)
        return self

    @property
    def not_(self):
        return _Not(self)

    def ilike(self, col, pattern):
        needle = pattern.strip("%").lower()
        self._filtros.append(lambda r, c=col: needle in str(r.get(c) or "").lower())
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        if self._op == "insert":
            items = self._payload if isinstance(self._payload, list) else [self._payload]
            for it in items:
                self._rows.append(dict(it))
            return _Result(data=[dict(it) for it in items])
        matched = [r for r in self._rows if all(f(r) for f in self._filtros)]
        if self._limit is not None:
            matched = matched[: self._limit]
        if self._op == "update":
            for r in matched:
                r.update(self._payload or {})
        if self._op == "delete":
            for r in list(matched):
                self._rows.remove(r)
        return _Result(data=[dict(r) for r in matched])


@dataclass
class _SupabaseMock:
    participantes: list = field(default_factory=list)
    reuniao_participantes: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    pendencias: list = field(default_factory=list)
    reuniao_aceites: list = field(default_factory=list)
    reuniao_aceite_tokens: list = field(default_factory=list)
    audit_log: list = field(default_factory=list)
    colegiados: list = field(default_factory=list)

    def table(self, name: str):
        rows = getattr(self, name, None)
        if rows is None:
            raise AssertionError(f"Tabela inesperada: {name}")
        return _TableQuery(rows)


def _acao(acao: str, responsavel: str, prazo: str | None = None) -> dict:
    return {"acao": acao, "responsavel": responsavel, "prazo": prazo}


def _sb(status: str = "AGUARDANDO_VALIDACAO", **reuniao) -> _SupabaseMock:
    return _SupabaseMock(
        participantes=[
            {"id": "P1", "nome_completo": "Pedro Rezende", "cargo": "Diretor", "email": "pedro@hsm.com", "ativo": True},
            {"id": "P2", "nome_completo": "Ana Lima", "cargo": "Coordenadora", "email": "ana@hsm.com", "ativo": True},
        ],
        reuniao_participantes=[
            {"id_reuniao": "R1", "participante_id": "P1", "sequence_assinatura": 1},
            {"id_reuniao": "R1", "participante_id": "P2", "sequence_assinatura": 2},
        ],
        reunioes=[
            {
                "id_reuniao": "R1",
                "status_ata": status,
                "tipo": "Gerencial",
                "objetivo": "Acompanhamento",
                "data": "2026-11-10",
                "facilitador_id": "P1",
                "envelope_key_clicksign": None,
                "envelope_id_clicksign": None,
                "falha_envio_assinatura": None,
                "modo_interno_desde": None,
                "colegiado_id": None,
                "deleted_at": None,
                "json_ata": {
                    "quadro_atribuicoes": [
                        _acao("Comprar insumos", "Pedro Rezende", "2026-12-10"),
                        _acao("Revisar protocolo", "Ana Lima", "10/12/2026"),
                        _acao("Ligar para o fornecedor", "Fulano de Fora"),
                    ]
                },
                **reuniao,
            }
        ],
    )


CURRENT_USER = {"id": "auth-uid-1", "email": "pedro@hsm.com"}
FACILITADOR = {"id": "P1", "email": "pedro@hsm.com", "access_profile": "regular"}


@pytest.fixture
def make_client(monkeypatch):
    def _factory(supabase: _SupabaseMock) -> TestClient:
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded

        from app.limiter import limiter

        limiter._storage.reset()
        app = FastAPI()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.include_router(reunioes_router.router, prefix="/api")
        app.dependency_overrides[get_current_user] = lambda: CURRENT_USER
        app.dependency_overrides[get_supabase_client] = lambda: supabase

        async def _fake_get_participante(*_a, **_kw):
            return dict(FACILITADOR)

        async def _fake_allowed(*_a, **_kw):
            return None

        monkeypatch.setattr(reunioes_router, "get_participante_for_user", _fake_get_participante)
        monkeypatch.setattr(reunioes_router, "get_allowed_reuniao_ids", _fake_allowed)
        monkeypatch.setattr(reunioes_router, "is_secretaria", lambda _me: False)
        return TestClient(app)

    return _factory


def _clicksign(monkeypatch, *, cria_envelope: bool = True) -> dict:
    """A ClickSign de mentira: conta Envelopes criados e anota o que tinha no
    banco quando o Envelope foi criado. Sem `cria_envelope`, a criação falha."""
    from app.services import clicksign_service, pdf_generator, storage

    estado: dict = {"envelopes": 0, "pdf_do_quadro": None}

    def _gerar_pdf(_reuniao, json_ata):
        estado["pdf_do_quadro"] = [a["acao"] for a in json_ata["quadro_atribuicoes"]]
        return b"PDF_DO_QUADRO_FINAL"

    def _criar(_nome):
        if not cria_envelope:
            return None
        estado["envelopes"] += 1
        return f"env-{estado['envelopes']}"

    monkeypatch.setattr(pdf_generator, "gerar_pdf_ata", _gerar_pdf)
    monkeypatch.setattr(storage, "upload_file", lambda *_a, **_kw: "https://x/ata_preliminar.pdf")
    monkeypatch.setattr(storage, "download_file", lambda *_a, **_kw: b"PDF_ANTIGO")
    monkeypatch.setattr(clicksign_service, "create_envelope", _criar)
    monkeypatch.setattr(clicksign_service, "add_document", lambda *_a, **_kw: "doc-id")
    monkeypatch.setattr(clicksign_service, "add_signer", lambda *_a, **_kw: "signer-id")
    monkeypatch.setattr(clicksign_service, "create_qualification_requirement", lambda *_a, **_kw: "q")
    monkeypatch.setattr(clicksign_service, "create_auth_requirement", lambda *_a, **_kw: "a")
    monkeypatch.setattr(clicksign_service, "activate_envelope", lambda _e: True)
    monkeypatch.setattr(clicksign_service, "notify_signers", lambda _e: True)
    return estado


# ─── 1. Enviar cria todas as Pendências no mesmo ato ───────────────────────────


def test_enviar_para_assinatura_cria_todas_as_pendencias_no_mesmo_ato(make_client, monkeypatch):
    """Sem esperar ninguém assinar: as três ações do quadro viram Pendência no
    clique, inclusive a de quem está fora do Envelope, e a Reunião já está em
    AGUARDANDO_ASSINATURA quando a ClickSign começa."""
    from app.services import clicksign_service

    sb = _sb()
    visto_pela_clicksign: dict = {}

    def _fluxo(supabase, id_reuniao, _reuniao):
        visto_pela_clicksign["status"] = supabase.reunioes[0]["status_ata"]
        visto_pela_clicksign["pendencias"] = len(supabase.pendencias)

    monkeypatch.setattr(clicksign_service, "start_signature_flow", _fluxo)

    r = make_client(sb).post("/api/reunioes/R1/aprovar")

    assert r.status_code == 200, r.text
    assert r.json()["total_pendencias"] == 3
    assert sb.reunioes[0]["status_ata"] == "AGUARDANDO_ASSINATURA"
    assert sorted(p["quadro_pos"] for p in sb.pendencias) == [0, 1, 2]
    assert {p["descricao_acao"] for p in sb.pendencias} == {
        "Comprar insumos",
        "Revisar protocolo",
        "Ligar para o fornecedor",
    }
    assert visto_pela_clicksign == {"status": "AGUARDANDO_ASSINATURA", "pendencias": 3}
