"""Os ciclos de calendário da Rotina (ADR 0098, decisão 9; issue #1874).

Regra pura, sem banco e sem job: o ciclo existe pela data. Não há nada que crie
Verificação; a linha só é gravada quando alguém marca.

- Semana: de segunda a domingo.
- Quinzena: do dia 1 ao 15 e do 16 ao fim do mês.
- Mês: do dia 1 ao último dia.

A Rotina começa no ciclo seguinte ao do nascimento (o envio da Ata), o primeiro
inteiro. A Verificação vale até o último dia do ciclo: marcada depois disso,
fica registrada como atrasada. Encerrada a Rotina, o ciclo em curso e os
seguintes deixam de existir; os que já tinham terminado continuam devidos.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

SEMANAL = "SEMANAL"
QUINZENAL = "QUINZENAL"
MENSAL = "MENSAL"

REALIZADA = "REALIZADA"
NAO_REALIZADA = "NAO_REALIZADA"
RESULTADOS = (REALIZADA, NAO_REALIZADA)


@dataclass(frozen=True)
class Ciclo:
    inicio: date
    fim: date


class VerificacaoRecusada(ValueError):
    """A marcação que a regra não aceita, com a frase para quem marcou."""


def _ultimo_dia(dia: date) -> date:
    return dia.replace(day=calendar.monthrange(dia.year, dia.month)[1])


def ciclo_de(dia: date, frequencia: str) -> Ciclo:
    """O ciclo que contém o dia."""
    if frequencia == SEMANAL:
        inicio = dia - timedelta(days=dia.weekday())
        return Ciclo(inicio, inicio + timedelta(days=6))
    if frequencia == QUINZENAL:
        if dia.day <= 15:
            return Ciclo(dia.replace(day=1), dia.replace(day=15))
        return Ciclo(dia.replace(day=16), _ultimo_dia(dia))
    if frequencia == MENSAL:
        return Ciclo(dia.replace(day=1), _ultimo_dia(dia))
    raise ValueError(f"Frequência desconhecida: {frequencia!r}")


def proximo_ciclo(ciclo: Ciclo, frequencia: str) -> Ciclo:
    return ciclo_de(ciclo.fim + timedelta(days=1), frequencia)


def primeiro_ciclo(nascimento: date, frequencia: str) -> Ciclo:
    """O primeiro ciclo cobrado: o seguinte ao do nascimento."""
    return proximo_ciclo(ciclo_de(nascimento, frequencia), frequencia)


def ciclos_devidos(
    comeca_em: date,
    frequencia: str,
    *,
    hoje: date,
    encerrada_em: date | None = None,
) -> list[Ciclo]:
    """Do primeiro ciclo ao de hoje, em ordem. Com a Rotina encerrada, só os
    ciclos que terminaram antes do dia do encerramento."""
    devidos: list[Ciclo] = []
    ciclo = ciclo_de(comeca_em, frequencia)
    while ciclo.inicio <= hoje:
        if encerrada_em is not None and ciclo.fim >= encerrada_em:
            break
        devidos.append(ciclo)
        ciclo = proximo_ciclo(ciclo, frequencia)
    return devidos


def marcada_com_atraso(ciclo: Ciclo, dia_da_marcacao: date) -> bool:
    """A Verificação vale até o último dia do ciclo; depois, conta o atraso."""
    return dia_da_marcacao > ciclo.fim


def validar_marcacao(resultado: str, anotacao: str | None) -> str | None:
    """Realizada é um clique; Não realizada pede anotação. Devolve a anotação
    limpa (ou None)."""
    if resultado not in RESULTADOS:
        raise VerificacaoRecusada("O resultado é Realizada ou Não realizada.")
    texto = (anotacao or "").strip() or None
    if resultado == NAO_REALIZADA and texto is None:
        raise VerificacaoRecusada("Não realizada pede uma anotação dizendo o que aconteceu.")
    return texto
