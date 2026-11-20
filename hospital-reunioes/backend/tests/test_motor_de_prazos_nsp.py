"""Motor de prazos para os prazos legais do Núcleo (issue #1984, ADR 0107 decisão 2).

O cálculo puro da Ouvidoria (`ouvidoria_prazos`) ganha duas regras que os
prazos do Regimento e da ANVISA pedem: a unidade de dias corridos e o 15º dia
útil do mês seguinte. A Ouvidoria não usa nenhuma das duas; os testes dela
(`test_ouvidoria_prazos.py`) seguem sem mudança.

Calendário de referência: 20/11/2026 é sexta (Consciência Negra), 02/11/2026 é
segunda (Finados) e 01/01/2027 é sexta (Confraternização).
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
UTC = ZoneInfo("UTC")

SEM_FERIADO: frozenset[date] = frozenset()


def _sp(ano: int, mes: int, dia: int, hora: int = 0, minuto: int = 0, segundo: int = 0) -> datetime:
    return datetime(ano, mes, dia, hora, minuto, segundo, tzinfo=FUSO)


class TestDiasCorridos:
    """Dia corrido é dia de calendário: fim de semana e feriado contam."""

    def test_tres_dias_corridos_de_sexta_vencem_na_segunda_mesmo_com_feriado_no_caminho(self):
        """Sexta 20/11 10h mais 3 dias corridos é segunda 23/11, no fim do dia.
        Sábado, domingo e o feriado da própria segunda entram na conta; em dias
        úteis o mesmo prazo cairia na quinta 26/11."""
        from app.services.ouvidoria_prazos import DIAS_CORRIDOS, Prazo, calcular_vencimento

        feriados = frozenset({date(2026, 11, 20), date(2026, 11, 23)})

        vencimento = calcular_vencimento(_sp(2026, 11, 20, 10), Prazo(3, DIAS_CORRIDOS), feriados)

        assert vencimento == _sp(2026, 11, 23, 23, 59, 59)

    def test_sessenta_dias_corridos_atravessam_a_virada_de_ano(self):
        """O prazo legal de 60 dias corridos, contado de 20/11/2026, vence em
        19/01/2027."""
        from app.services.ouvidoria_prazos import DIAS_CORRIDOS, Prazo, calcular_vencimento

        vencimento = calcular_vencimento(_sp(2026, 11, 20, 10), Prazo(60, DIAS_CORRIDOS), SEM_FERIADO)

        assert vencimento == _sp(2027, 1, 19, 23, 59, 59)

    def test_dias_corridos_nao_viram_minutos_de_expediente(self):
        """Como as horas corridas, não existe conversão honesta para tempo útil."""
        import pytest

        from app.services.ouvidoria_prazos import DIAS_CORRIDOS, Prazo, minutos_do_prazo

        with pytest.raises(ValueError):
            minutos_do_prazo(Prazo(60, DIAS_CORRIDOS))
