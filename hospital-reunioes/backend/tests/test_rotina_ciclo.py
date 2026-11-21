"""Os ciclos de calendário da Rotina (ADR 0098, decisão 9; issue #1874).

Função pura, sem banco: semana de segunda a domingo, quinzena de 1 a 15 e de
16 ao fim do mês, e mês fechado. A Rotina começa no ciclo seguinte ao do
nascimento, o primeiro inteiro, e a Verificação vale até o último dia do ciclo.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.rotina_ciclo import (  # noqa: E402
    Ciclo,
    VerificacaoRecusada,
    ciclo_de,
    ciclos_devidos,
    marcada_com_atraso,
    primeiro_ciclo,
    validar_marcacao,
)

D = date.fromisoformat


@pytest.mark.parametrize(
    ("dia", "frequencia", "inicio", "fim"),
    [
        # Quinzena: o dia 15 fecha a primeira, o dia 16 abre a segunda.
        ("2026-11-15", "QUINZENAL", "2026-11-01", "2026-11-15"),
        ("2026-11-16", "QUINZENAL", "2026-11-16", "2026-11-30"),
        ("2026-11-01", "QUINZENAL", "2026-11-01", "2026-11-15"),
        # Fim de mês: 30, 31, fevereiro comum e bissexto.
        ("2026-11-30", "QUINZENAL", "2026-11-16", "2026-11-30"),
        ("2026-12-31", "QUINZENAL", "2026-12-16", "2026-12-31"),
        ("2027-02-28", "QUINZENAL", "2027-02-16", "2027-02-28"),
        ("2028-02-29", "MENSAL", "2028-02-01", "2028-02-29"),
        ("2026-11-30", "MENSAL", "2026-11-01", "2026-11-30"),
        ("2026-12-31", "MENSAL", "2026-12-01", "2026-12-31"),
        # Semana de segunda a domingo, inclusive na virada do ano.
        ("2026-11-19", "SEMANAL", "2026-11-16", "2026-11-22"),
        ("2026-11-16", "SEMANAL", "2026-11-16", "2026-11-22"),
        ("2026-11-22", "SEMANAL", "2026-11-16", "2026-11-22"),
        ("2026-12-31", "SEMANAL", "2026-12-28", "2027-01-03"),
        ("2027-01-01", "SEMANAL", "2026-12-28", "2027-01-03"),
    ],
)
def test_o_ciclo_de_um_dia_segue_o_calendario(dia, frequencia, inicio, fim):
    assert ciclo_de(D(dia), frequencia) == Ciclo(D(inicio), D(fim))


@pytest.mark.parametrize(
    ("nascimento", "frequencia", "inicio", "fim"),
    [
        # Ata enviada numa quinta: a semana já pela metade não conta.
        ("2026-11-19", "SEMANAL", "2026-11-23", "2026-11-29"),
        ("2026-11-15", "QUINZENAL", "2026-11-16", "2026-11-30"),
        ("2026-11-16", "QUINZENAL", "2026-12-01", "2026-12-15"),
        # Virada do ano.
        ("2026-12-20", "QUINZENAL", "2027-01-01", "2027-01-15"),
        ("2026-12-31", "MENSAL", "2027-01-01", "2027-01-31"),
        ("2026-12-29", "SEMANAL", "2027-01-04", "2027-01-10"),
        # Mesmo no primeiro dia do ciclo, começa no seguinte.
        ("2026-11-01", "MENSAL", "2026-12-01", "2026-12-31"),
    ],
)
def test_a_rotina_comeca_no_ciclo_seguinte_ao_nascimento(nascimento, frequencia, inicio, fim):
    assert primeiro_ciclo(D(nascimento), frequencia) == Ciclo(D(inicio), D(fim))


def test_os_ciclos_devidos_vao_do_primeiro_ao_de_hoje():
    ciclos = ciclos_devidos(D("2026-11-01"), "QUINZENAL", hoje=D("2026-12-02"))

    assert ciclos == [
        Ciclo(D("2026-11-01"), D("2026-11-15")),
        Ciclo(D("2026-11-16"), D("2026-11-30")),
        Ciclo(D("2026-12-01"), D("2026-12-15")),
    ]


def test_antes_do_primeiro_ciclo_nada_e_devido():
    assert ciclos_devidos(D("2026-12-01"), "MENSAL", hoje=D("2026-11-30")) == []


def test_encerrada_os_ciclos_seguintes_ao_encerramento_param():
    # Encerrada no dia 10/12: o ciclo de 07/12 a 13/12 ainda não tinha
    # terminado e sai junto com os seguintes; os anteriores continuam devidos.
    ciclos = ciclos_devidos(D("2026-11-23"), "SEMANAL", hoje=D("2027-01-20"), encerrada_em=D("2026-12-10"))

    assert ciclos == [
        Ciclo(D("2026-11-23"), D("2026-11-29")),
        Ciclo(D("2026-11-30"), D("2026-12-06")),
    ]


def test_marcada_depois_do_ultimo_dia_do_ciclo_fica_atrasada():
    ciclo = Ciclo(D("2026-11-16"), D("2026-11-30"))

    assert marcada_com_atraso(ciclo, D("2026-11-30")) is False
    assert marcada_com_atraso(ciclo, D("2026-12-01")) is True


@pytest.mark.parametrize("anotacao", [None, "", "   "])
def test_nao_realizada_sem_anotacao_e_recusada(anotacao):
    with pytest.raises(VerificacaoRecusada):
        validar_marcacao("NAO_REALIZADA", anotacao)


def test_realizada_e_um_clique_e_nao_realizada_com_anotacao_passa():
    assert validar_marcacao("REALIZADA", None) is None
    assert validar_marcacao("NAO_REALIZADA", "Faltou a equipe da noite.") == "Faltou a equipe da noite."
