"""Limpeza dos testes da Ouvidoria (issue #1962, PRD #1913, ADR 0102)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

# A janela é fixa no código, de propósito (ADR 0102, decisão 3): o script não
# aceita parâmetro de data. 19/10/2026 à 0h de Brasília até 17/11/2026 às
# 18h31min43s de Brasília, o instante em que o pedido nasceu, inclusive. O
# segundo final entra inteiro, com as frações dele.
INICIO_DA_JANELA = datetime(2026, 10, 19, 3, 0, 0, tzinfo=UTC)
FIM_DA_JANELA = datetime(2026, 11, 17, 21, 31, 43, tzinfo=UTC)
_DEPOIS_DA_JANELA = FIM_DA_JANELA + timedelta(seconds=1)


def na_janela(instante: datetime) -> bool:
    return INICIO_DA_JANELA <= instante < _DEPOIS_DA_JANELA


@dataclass(frozen=True)
class Avaliacao:
    id: str
    criada_em: datetime


@dataclass(frozen=True)
class Caso:
    id: str
    protocolo: str
    canal: str
    t0: datetime
    estado: str
    anonimo: bool


@dataclass
class Escolha:
    avaliacoes: list[Avaliacao] = field(default_factory=list)
    saem: list[Caso] = field(default_factory=list)


def escolher(avaliacoes: list[Avaliacao], casos: list[Caso]) -> Escolha:
    return Escolha(
        avaliacoes=[a for a in avaliacoes if na_janela(a.criada_em)],
        saem=[c for c in casos if na_janela(c.t0)],
    )
