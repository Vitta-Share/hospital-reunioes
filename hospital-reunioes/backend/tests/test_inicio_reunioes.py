"""O Início com as Atas e as próximas Reuniões (issue #1936, PRD #1932, ADR 0104).

A fonte de Atas traz a Ata a assinar (a Reunião em assinatura em que a pessoa é
Signatária e ainda não deu ciência, pela ClickSign ou pelo Aceite interno) e a
Ata parada (a que espera o Facilitador na validação). As duas entram no grupo
"Sem prazo", com há quantos dias esperam; a Ata parada passa a contar como
vencida a partir do quarto dia. O trilho traz as próximas Reuniões em que a
pessoa é Facilitadora ou Participante.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers import inicio as inicio_router  # noqa: E402
from app.services import inicio  # noqa: E402
from app.services.inicio import fonte_pendencias, fonte_reunioes  # noqa: E402

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

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def neq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and linha.get(coluna) != valor)
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha.get(coluna)) >= str(valor))
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
        return _Result([dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)])


@dataclass
class _Banco:
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    reuniao_participantes: list = field(default_factory=list)
    reuniao_aceites: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


def _reuniao(id_reuniao: str, **campos) -> dict:
    base = {
        "id_reuniao": id_reuniao,
        "titulo": f"Reunião {id_reuniao}",
        "data": "2026-11-10",
        "hora_inicio": "09:00:00",
        "hora_fim": "10:00:00",
        "facilitador_id": "P_FACI",
        "status_ata": "PROGRAMADA",
        "deleted_at": None,
        "updated_at": "2026-11-12T15:00:00+00:00",
    }
    return {**base, **campos}


def _na_reuniao(id_reuniao: str, *pessoas: str) -> list[dict]:
    return [{"id_reuniao": id_reuniao, "participante_id": p, "sequence_assinatura": 2} for p in pessoas]


def _quando(dias_atras: int) -> str:
    """O `updated_at` de quem entrou no estado há N dias, às 15h de Brasília."""
    return datetime.combine(HOJE - timedelta(days=dias_atras), datetime.min.time().replace(hour=15), BRT).isoformat()


AURORA = {"id": "P_AURORA", "nome_completo": "Aurora Lima", "email": "aurora@exemplo.org", "access_profile": "regular"}
FACILITADOR = {"id": "P_FACI", "nome_completo": "Fabio Castro", "email": "fabio@exemplo.org", "access_profile": "regular"}
DE_FORA = {"id": "P_FORA", "nome_completo": "Olga Reis", "email": "olga@exemplo.org", "access_profile": "regular"}


@pytest.fixture
def nucleo(monkeypatch):
    """As reuniões do Núcleo que a pessoa não alcança: nenhuma, por padrão. A
    regra de verdade mora em `dependencies` e tem teste próprio; aqui ela é a
    entrada."""
    estado = {"ocultas": [], "recursos": frozenset()}
    for modulo in (fonte_pendencias, fonte_reunioes):
        monkeypatch.setattr(modulo, "reunioes_ocultas", lambda _sb, _me: list(estado["ocultas"]))
    monkeypatch.setattr(fonte_pendencias, "recursos_nsp_da_pessoa", lambda _sb, _me: estado["recursos"])
    return estado


def _rota(monkeypatch, me: dict | None, banco: _Banco, agora: datetime = AGORA):
    async def _participante(_user, _sb, fields=None):
        return me

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: agora)
    return asyncio.run(inicio_router.get_inicio(current_user={"id": "u1"}, supabase=banco))


def _atas(resposta) -> list[tuple[str, str, str | None]]:
    return [(item.tipo, item.id, item.grupo) for item in resposta.itens if item.tipo.startswith("ata_")]


# ═══════════════════════════════════════════════════════════════════════════
# 1. A Ata a assinar, para o Signatário que ainda não deu ciência
# ═══════════════════════════════════════════════════════════════════════════


class TestAtaAAssinar:
    def test_signatario_ve_a_ata_em_assinatura_sem_prazo_com_os_dias_de_espera(self, monkeypatch, nucleo):
        banco = _Banco(
            reunioes=[
                _reuniao(
                    "R2",
                    titulo="Reunião de Enfermagem",
                    data="2026-11-09",
                    status_ata="AGUARDANDO_ASSINATURA",
                    updated_at=_quando(5),
                )
            ],
            reuniao_participantes=_na_reuniao("R2", "P_AURORA", "P_FACI"),
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _atas(resposta) == [("ata_a_assinar", "R2", "sem_prazo")]
        item = resposta.itens[0]
        assert item.prazo is None
        assert item.dias_esperando == 5
        assert item.titulo == "Ata a assinar: Reunião de Enfermagem"
        assert item.origem == "Reunião de Enfermagem, de 09/11/2026."
        assert item.area == "Reuniões"
        assert item.acao == "Assinar a Ata"
        assert item.destino == "/reunioes/R2"
        # Sem prazo não é vencido nem entra na frase.
        assert resposta.contadores.passou_do_prazo == 0
        assert resposta.frase.titulo == "Aurora, você está em dia."
