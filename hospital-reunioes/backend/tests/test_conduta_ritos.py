"""O prazo de cada rito do Canal de Conduta (issue #1824; especificação, seção 6).

O prazo conta do envio do relato, nunca da triagem: Encaminhamento em 5 dias
úteis, Rápido em 20 corridos, Completo em 30 corridos (60 com a prorrogação
única). As datas esperadas foram contadas no calendário, à mão.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.conduta.ritos import prazo_do_rito  # noqa: E402

# Segunda-feira, 02/11/2026, às 23h30 em São Paulo (já é dia 03 em UTC).
ENVIO_NA_SEGUNDA_A_NOITE = "2026-11-03T02:30:00+00:00"


@pytest.mark.parametrize(
    ("rito", "prorrogado", "esperado"),
    [
        ("rapido", False, date(2026, 11, 22)),
        ("completo", False, date(2026, 12, 2)),
        ("completo", True, date(2027, 1, 1)),
        # 03 (ter), 04, 05, 06 (sex), pula sábado e domingo, 09 (seg).
        ("encaminhamento", False, date(2026, 11, 9)),
    ],
)
def test_o_prazo_conta_do_envio_do_relato_no_fuso_de_sao_paulo(rito, prorrogado, esperado):
    assert prazo_do_rito(rito, ENVIO_NA_SEGUNDA_A_NOITE, prorrogado=prorrogado) == esperado


def test_o_encaminhamento_pula_o_feriado_cadastrado():
    # 02/11 é feriado (Finados) e o relato chegou no domingo, 01/11.
    envio = "2026-11-01T15:00:00-03:00"

    assert prazo_do_rito("encaminhamento", envio, feriados=frozenset({date(2026, 11, 2)})) == date(2026, 11, 9)
    assert prazo_do_rito("encaminhamento", envio) == date(2026, 11, 6)
