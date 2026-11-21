# As fixtures importadas de test_rotina_verificacao entram como parâmetro.
# ruff: noqa: F811
"""A Rotina sem frequência, o fluxo contínuo antigo convertido (issue #1877).

A migration 190 converte a Pendência de fluxo contínuo em Rotina sem
frequência. Ela espera o Facilitador da Reunião escolher a frequência, na
Minha Fila dele, e até lá não gera Verificação nenhuma. Escolhida a
frequência, a Rotina começa no primeiro ciclo inteiro depois da escolha.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

# Fixtures e dados da fatia da Rotina (#1874), reaproveitados.
from test_rotina_verificacao import (  # noqa: E402, F401
    ADMIN,
    ANA,
    OUTRO,
    PEDRO,
    RT1,
    D,
    _sb_com_rotina,
    cliente_das_rotinas,
    fila,
    hoje,
)


def _sem_frequencia(**extra):
    """A Rotina convertida: de Ana (P2), na R1 que Pedro (P1) facilita."""
    return _sb_com_rotina(frequencia=None, comeca_em=None, created_at="2026-11-20T09:00:00+00:00", **extra)


def _da_frequencia(resposta) -> list[tuple]:
    return [(i.titulo, i.grupo, i.acao, i.destino) for i in resposta.itens if i.tipo == "frequencia_da_rotina"]


# ─── Na Minha Fila do Facilitador, sem Verificação ───────────────────────────


def test_rotina_sem_frequencia_aparece_na_minha_fila_do_facilitador(fila):
    resposta = fila(_sem_frequencia(), PEDRO, "2026-11-25")

    assert [a for a in resposta.avisos if a.fonte == "rotinas"] == []
    assert _da_frequencia(resposta) == [("Reunir a equipe", "sem_prazo", "Escolher a frequência", "/rotinas")]


def test_rotina_sem_frequencia_nao_gera_verificacao_nem_na_fila_do_responsavel(fila):
    resposta = fila(_sem_frequencia(), ANA, "2027-03-10")

    assert [a for a in resposta.avisos if a.fonte == "rotinas"] == []
    # Meses depois, nenhum ciclo cobrado: sem frequência não há Verificação.
    assert [i for i in resposta.itens if i.tipo == "verificacao_da_rotina"] == []
    # Escolher a frequência é do Facilitador, não do responsável.
    assert _da_frequencia(resposta) == []


def test_rotina_sem_frequencia_nao_aparece_na_fila_de_quem_nao_facilita(fila):
    assert _da_frequencia(fila(_sem_frequencia(), OUTRO, "2026-11-25")) == []


def test_rotina_com_frequencia_nao_pede_escolha_na_fila(fila):
    assert _da_frequencia(fila(_sb_com_rotina(), PEDRO, "2026-11-25")) == []


def test_rotina_encerrada_sem_frequencia_sai_da_fila(fila):
    sb = _sem_frequencia(status="ENCERRADA", encerrada_em="2026-11-21", anotacao_encerramento="Não vale mais.")

    assert _da_frequencia(fila(sb, PEDRO, "2026-11-25")) == []


def test_rotina_sem_frequencia_de_reuniao_do_nucleo_oculta_nao_aparece(fila):
    fila.estado["ocultas"] = ["R1"]

    assert _da_frequencia(fila(_sem_frequencia(), PEDRO, "2026-11-25")) == []


def test_a_lista_das_rotinas_nao_traz_ciclo_sem_frequencia(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2027-03-10")

    [rotina] = cliente_das_rotinas(_sem_frequencia(), PEDRO).get("/api/rotinas").json()

    assert rotina["ciclos_em_aberto"] == []
    assert rotina["pode_escolher_frequencia"] is True
    [da_ana] = cliente_das_rotinas(_sem_frequencia(), ANA).get("/api/rotinas").json()
    assert da_ana["pode_escolher_frequencia"] is False


def test_a_verificacao_sem_frequencia_e_recusada(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-25")
    sb = _sem_frequencia()

    r = cliente_das_rotinas(sb, ANA).post(f"/api/rotinas/{RT1}/ciclos/2026-11-23/realizada")

    assert r.status_code == 422, r.text
    assert sb.rotina_verificacoes == []


# ─── O Facilitador escolhe a frequência ──────────────────────────────────────


def test_o_facilitador_escolhe_a_frequencia_e_a_rotina_comeca_no_ciclo_seguinte(cliente_das_rotinas, fila, hoje):
    hoje["valor"] = D("2026-11-19")  # uma quinta-feira
    sb = _sem_frequencia()

    r = cliente_das_rotinas(sb, PEDRO).post(f"/api/rotinas/{RT1}/frequencia", json={"frequencia": "SEMANAL"})

    assert r.status_code == 200, r.text
    assert (sb.rotinas[0]["frequencia"], sb.rotinas[0]["comeca_em"]) == ("SEMANAL", "2026-11-23")
    # Sai da fila do Facilitador, e o ciclo passa a ser cobrado do responsável.
    assert _da_frequencia(fila(sb, PEDRO, "2026-11-25")) == []
    assert [i.prazo.isoformat() for i in fila(sb, ANA, "2026-11-25").itens if i.tipo == "verificacao_da_rotina"] == [
        "2026-11-29"
    ]


def test_o_super_admin_escolhe_a_frequencia(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-19")
    sb = _sem_frequencia()

    r = cliente_das_rotinas(sb, ADMIN).post(f"/api/rotinas/{RT1}/frequencia", json={"frequencia": "MENSAL"})

    assert r.status_code == 200, r.text
    assert (sb.rotinas[0]["frequencia"], sb.rotinas[0]["comeca_em"]) == ("MENSAL", "2026-12-01")


def test_o_responsavel_nao_escolhe_a_frequencia(cliente_das_rotinas, hoje):
    sb = _sem_frequencia()

    r = cliente_das_rotinas(sb, ANA).post(f"/api/rotinas/{RT1}/frequencia", json={"frequencia": "SEMANAL"})

    assert r.status_code == 403, r.text
    assert sb.rotinas[0]["frequencia"] is None


def test_a_frequencia_escolhida_nao_se_troca_por_aqui(cliente_das_rotinas, hoje):
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, PEDRO).post(f"/api/rotinas/{RT1}/frequencia", json={"frequencia": "MENSAL"})

    assert r.status_code == 409, r.text
    assert (sb.rotinas[0]["frequencia"], sb.rotinas[0]["comeca_em"]) == ("SEMANAL", "2026-11-23")


@pytest.mark.parametrize("frequencia", ["DIARIA", "", "semanal"])
def test_frequencia_fora_da_lista_e_recusada(cliente_das_rotinas, hoje, frequencia):
    sb = _sem_frequencia()

    r = cliente_das_rotinas(sb, PEDRO).post(f"/api/rotinas/{RT1}/frequencia", json={"frequencia": frequencia})

    assert r.status_code == 422, r.text
    assert sb.rotinas[0]["frequencia"] is None


def test_rotina_encerrada_nao_ganha_frequencia(cliente_das_rotinas, hoje):
    sb = _sem_frequencia(status="ENCERRADA", encerrada_em="2026-11-21", anotacao_encerramento="Não vale mais.")

    r = cliente_das_rotinas(sb, PEDRO).post(f"/api/rotinas/{RT1}/frequencia", json={"frequencia": "SEMANAL"})

    assert r.status_code == 409, r.text
    assert sb.rotinas[0]["frequencia"] is None
