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


class TestDecimoQuintoDiaUtilDoMesSeguinte:
    """O 15º dia útil do mês que vem, pelo calendário útil e pelos feriados.
    Dia útil é dia de expediente: vence no fechamento, às 17h."""

    def test_sem_feriado_o_decimo_quinto_dia_util_de_novembro_e_o_dia_20(self):
        from app.services.ouvidoria_prazos import DIA_UTIL_DO_MES_SEGUINTE, Prazo, calcular_vencimento

        vencimento = calcular_vencimento(_sp(2026, 10, 10, 9), Prazo(15, DIA_UTIL_DO_MES_SEGUINTE), SEM_FERIADO)

        assert vencimento == _sp(2026, 11, 20, 17)

    def test_fim_de_semana_e_feriado_empurram_o_decimo_quinto_dia_util(self):
        """Com Finados (02/11) e Consciência Negra (20/11) cadastrados, o 15º
        dia útil de novembro de 2026 passa de sexta 20 para terça 24."""
        from app.services.ouvidoria_prazos import DIA_UTIL_DO_MES_SEGUINTE, Prazo, calcular_vencimento

        feriados = frozenset({date(2026, 11, 2), date(2026, 11, 20)})

        vencimento = calcular_vencimento(_sp(2026, 10, 10, 9), Prazo(15, DIA_UTIL_DO_MES_SEGUINTE), feriados)

        assert vencimento == _sp(2026, 11, 24, 17)

    def test_ocorrido_em_dezembro_vence_em_janeiro_do_ano_seguinte(self):
        """Com o feriado de 01/01/2027, o 15º dia útil de janeiro é sexta 22."""
        from app.services.ouvidoria_prazos import DIA_UTIL_DO_MES_SEGUINTE, Prazo, calcular_vencimento

        feriados = frozenset({date(2027, 1, 1)})

        vencimento = calcular_vencimento(_sp(2026, 12, 15, 9), Prazo(15, DIA_UTIL_DO_MES_SEGUINTE), feriados)

        assert vencimento == _sp(2027, 1, 22, 17)

    def test_o_mes_do_ocorrido_e_o_de_sao_paulo_e_nao_o_do_utc(self):
        """31/12 às 22h em São Paulo já é 01/01 em UTC. O mês seguinte é janeiro,
        e não fevereiro."""
        from app.services.ouvidoria_prazos import DIA_UTIL_DO_MES_SEGUINTE, Prazo, calcular_vencimento

        feriados = frozenset({date(2027, 1, 1)})
        ocorrido_em_utc = datetime(2027, 1, 1, 1, 0, tzinfo=UTC)

        vencimento = calcular_vencimento(ocorrido_em_utc, Prazo(15, DIA_UTIL_DO_MES_SEGUINTE), feriados)

        assert vencimento == _sp(2027, 1, 22, 17)
