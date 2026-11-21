"""A Competência de uma Conta de Contas médicas (issue #1958, ADR 0105, decisão 6).

O mês do fim do período da Conta, que é o mês do faturamento. A Conta sem
período cai no mês em que foi concluída, no fuso do hospital. É calculada,
sem coluna: quem agrupa as Concluídas e quem arquiva o mês chamam daqui.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

FUSO_DO_HOSPITAL = ZoneInfo("America/Sao_Paulo")


def competencia(conta: dict) -> str | None:
    """O mês no formato `AAAA-MM`, ou nulo sem período e sem conclusão."""
    if conta.get("periodo_fim"):
        return str(conta["periodo_fim"])[:7]
    if conta.get("concluida_em"):
        return datetime.fromisoformat(conta["concluida_em"]).astimezone(FUSO_DO_HOSPITAL).strftime("%Y-%m")
    return None
