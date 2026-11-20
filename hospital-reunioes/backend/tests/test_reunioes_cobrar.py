"""O Cobrar da lista de Atas que aguardam assinatura (issue #1868, decisão 36
do diretor no PRD #1757).

O Facilitador vê quem falta assinar e, no Cobrar, o aplicativo manda de novo o
pedido de assinatura da ClickSign só para quem ainda não assinou. Quem não é o
Facilitador da Reunião nem Super admin não cobra.
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

from app.dependencies import (  # noqa: E402
    barrar_reuniao_do_nucleo,
    get_current_user,
    get_supabase_client,
    require_acesso_reunioes,
)
from app.routers import reunioes as reunioes_router  # noqa: E402
from app.services import clicksign_service  # noqa: E402


@dataclass
class _Result:
    data: Any


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def execute(self):
        return _Result([dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)])


@dataclass
class _Banco:
    reunioes: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


def _reuniao(**campos) -> dict:
    base = {
        "id_reuniao": "R1",
        "status_ata": "AGUARDANDO_ASSINATURA",
        "envelope_id_clicksign": "env-1",
        "envelope_key_clicksign": "key-1",
        "facilitador_id": "P_FABIO",
        "tipo": "Gerencial",
        "data": "2026-11-10",
        "modo_interno_desde": None,
    }
    return {**base, **campos}


SIGNATARIOS = [
    {"signer_id": "s-ana", "nome": "Ana", "email": "ana@x", "status": "signed", "signed_at": "2026-11-11"},
    {"signer_id": "s-bruno", "nome": "Bruno", "email": "bruno@x", "status": "pending", "signed_at": None},
    {"signer_id": "s-carla", "nome": "Carla", "email": "carla@x", "status": "pending", "signed_at": None},
]

PESSOAS = {
    "fabio": {"id": "P_FABIO", "access_profile": "regular"},
    "admin": {"id": "P_ADMIN", "access_profile": "super_admin"},
    "otto": {"id": "P_OTTO", "access_profile": "regular"},
    "selma": {"id": "P_SELMA", "access_profile": "secretaria"},
}


@pytest.fixture
def cobrar(monkeypatch):
    estado: dict = {"quem": "fabio", "banco": _Banco(reunioes=[_reuniao()]), "lembretes": []}

    async def _participante(*_a, **_kw):
        return PESSOAS[estado["quem"]]

    async def _todas(*_a, **_kw):
        return None

    def _lembrar(envelope_id, signer_id, message=None):
        estado["lembretes"].append((envelope_id, signer_id))
        return True

    monkeypatch.setattr(reunioes_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(reunioes_router, "get_allowed_reuniao_ids", _todas)
    monkeypatch.setattr(clicksign_service, "list_signers", lambda _env: [dict(s) for s in SIGNATARIOS])
    monkeypatch.setattr(clicksign_service, "remind_signer", _lembrar)

    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.limiter import limiter

    limiter.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(reunioes_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "email": "x@x"}
    app.dependency_overrides[get_supabase_client] = lambda: estado["banco"]
    app.dependency_overrides[require_acesso_reunioes] = lambda: None
    app.dependency_overrides[barrar_reuniao_do_nucleo] = lambda: None
    client = TestClient(app)

    def pedir(quem: str):
        estado["quem"] = quem
        return client.post("/api/reunioes/R1/signatarios/cobrar")

    return pedir, estado


def test_cobrar_reenvia_o_pedido_so_para_quem_ainda_nao_assinou(cobrar):
    pedir, estado = cobrar

    resposta = pedir("fabio")

    assert resposta.status_code == 200
    assert estado["lembretes"] == [("env-1", "s-bruno"), ("env-1", "s-carla")]
    assert resposta.json()["cobrados"] == ["Bruno", "Carla"]


def test_super_admin_tambem_cobra(cobrar):
    pedir, estado = cobrar

    assert pedir("admin").status_code == 200
    assert [s for _e, s in estado["lembretes"]] == ["s-bruno", "s-carla"]


def test_quem_nao_facilita_a_reuniao_nao_cobra(cobrar):
    pedir, estado = cobrar

    assert pedir("otto").status_code == 403
    assert estado["lembretes"] == []


def test_secretaria_nao_cobra(cobrar):
    pedir, estado = cobrar

    assert pedir("selma").status_code == 403
    assert estado["lembretes"] == []


def test_ata_fora_da_assinatura_nao_e_cobrada(cobrar):
    pedir, estado = cobrar
    estado["banco"] = _Banco(reunioes=[_reuniao(status_ata="ASSINADA")])

    assert pedir("fabio").status_code == 400
    assert estado["lembretes"] == []
