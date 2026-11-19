"""Quem responde a você (issue #1943, PRD #1932, ADR 0104 decisão 9).

O bloco do Início de quem acompanha outras pessoas, em pedido separado do
resto do Início. Quem aparece segue o vínculo da ADR 0098, decisão 7: o Super
admin vê todas as pessoas com item aberto, e o Facilitador vê os responsáveis
das Pendências das Reuniões que conduziu. Cada linha traz nome, cargo,
vencidos agora, em aberto e o último acesso (Registro de acesso, issue #1941).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers import inicio as inicio_router  # noqa: E402
from app.services.inicio import quem_responde  # noqa: E402

BRT = ZoneInfo("America/Sao_Paulo")
# Quarta-feira, 18/11/2026, 10h em Brasília.
AGORA = datetime(2026, 11, 18, 10, 0, tzinfo=BRT)
HOJE = AGORA.date()


# ─── O banco de mentira ───────────────────────────────────────────────────


@dataclass
class _Result:
    data: list


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []
        self._recorte: tuple[int, int] | None = None

    def select(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def range(self, inicio, fim):
        self._recorte = (inicio, fim)
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        valores = set(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def execute(self):
        linhas = [dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._recorte:
            linhas = linhas[self._recorte[0] : self._recorte[1] + 1]
        return _Result(linhas)


@dataclass
class _Banco:
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    participantes: list = field(default_factory=list)
    registro_de_acesso: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


def _pendencia(id_acao: str, responsavel_id: str, **campos) -> dict:
    base = {
        "id_acao": id_acao,
        "descricao_acao": f"Ação {id_acao}",
        "responsavel_id": responsavel_id,
        "co_responsavel_id": None,
        "id_reuniao": "R1",
        "prazo": (HOJE + timedelta(days=3)).isoformat(),
        "status": "PENDENTE",
        "deleted_at": None,
    }
    return {**base, **campos}


def _vencida(id_acao: str, responsavel_id: str, dias: int, **campos) -> dict:
    return _pendencia(id_acao, responsavel_id, prazo=(HOJE - timedelta(days=dias)).isoformat(), **campos)


def _pessoa(pid: str, nome: str, cargo: str) -> dict:
    return {"id": pid, "nome_completo": nome, "cargo": cargo, "role": "gerente", "email": f"{pid}@hsm"}


SUPER = {"id": "P_SUPER", "nome_completo": "Sara Admin", "access_profile": "super_admin"}
FACILITADOR = {"id": "P_FAC", "nome_completo": "Fábio Lima", "access_profile": "regular"}
NINGUEM = {"id": "P_NADA", "nome_completo": "Nara Silva", "access_profile": "regular"}
SECRETARIA = {"id": "P_SEC", "nome_completo": "Selma Souza", "access_profile": "secretaria"}

ANA = _pessoa("P_ANA", "Ana Souza", "Enfermeira")
BRUNO = _pessoa("P_BRUNO", "Bruno Reis", "Farmacêutico")
CAIO = _pessoa("P_CAIO", "Caio Melo", "Coordenador de Hotelaria")

REUNIOES = [
    {"id_reuniao": "R1", "titulo": "Reunião de Atendimento", "data": "2026-10-28", "facilitador_id": "P_FAC"},
    {"id_reuniao": "R2", "titulo": "Reunião de Hotelaria", "data": "2026-10-29", "facilitador_id": "P_OUTRO"},
    {"id_reuniao": "RN", "titulo": "Reunião do Núcleo", "data": "2026-10-21", "facilitador_id": "P_OUTRO"},
]


def _banco(*pendencias, acessos=()) -> _Banco:
    return _Banco(
        pendencias=list(pendencias),
        reunioes=[dict(r, deleted_at=None) for r in REUNIOES],
        participantes=[ANA, BRUNO, CAIO],
        registro_de_acesso=[{"participante_id": pid, "dia": dia} for pid, dia in acessos],
    )


@pytest.fixture
def nucleo(monkeypatch):
    """O que a pessoa alcança do Núcleo: nada, por padrão. A regra de verdade
    mora em `dependencies` e tem teste próprio; aqui ela é a entrada."""
    estado = {"ocultas": ["RN"], "recursos": frozenset()}
    monkeypatch.setattr(quem_responde, "reunioes_ocultas", lambda _sb, _me: list(estado["ocultas"]))
    monkeypatch.setattr(quem_responde, "recursos_nsp_da_pessoa", lambda _sb, _me: estado["recursos"])
    return estado


def _rota(monkeypatch, me: dict | None, banco: _Banco):
    async def _participante(_user, _sb, fields=None):
        return me

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: AGORA)
    return asyncio.run(inicio_router.get_quem_responde(current_user={"id": "u1"}, supabase=banco))


def _nomes(resposta) -> list[str]:
    return [pessoa.nome for pessoa in resposta.pessoas]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quem aparece, por papel
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemAparece:
    def test_super_admin_ve_todas_as_pessoas_com_item_aberto(self, monkeypatch, nucleo):
        banco = _banco(
            _pendencia("A1", "P_ANA", id_reuniao="R1"),
            _pendencia("B1", "P_BRUNO", id_reuniao="R2"),
            _pendencia("C1", "P_CAIO", id_reuniao="R2", status="CONCLUIDO"),
        )

        resposta = _rota(monkeypatch, SUPER, banco)

        assert sorted(_nomes(resposta)) == ["Ana Souza", "Bruno Reis"]
