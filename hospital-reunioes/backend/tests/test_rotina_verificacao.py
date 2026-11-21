"""Rotina e Verificação por ciclo de calendário (ADR 0098, decisão 9; issue #1874).

A Rotina nasce do envio da Ata (linha do tipo Rotina), com responsável e
frequência, e começa no primeiro ciclo inteiro depois do envio. A Verificação
não é criada por job: o ciclo vem da data e a linha só é gravada quando alguém
marca. O responsável marca; o Facilitador marca por ele. Não realizada pede
anotação, a marcação depois do ciclo fica atrasada, e encerrar pede anotação e
para os ciclos seguintes. A Verificação em aberto aparece na Minha Fila do
responsável.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# O `make_client` importado registra a fábrica de TestClient do envio aqui.
from test_pendencia_nasce_no_envio import _sb, make_client  # noqa: E402, F401

from app.services import rotina_service  # noqa: E402

D = date.fromisoformat


@pytest.fixture
def hoje(monkeypatch):
    """O dia do servidor, em Brasília, controlado pelo teste."""
    dia = {"valor": D("2026-11-19")}  # uma quinta-feira
    monkeypatch.setattr(rotina_service, "hoje_em_brasilia", lambda: dia["valor"])
    return dia


def _sem_clicksign(monkeypatch):
    from app.services import clicksign_service

    monkeypatch.setattr(clicksign_service, "start_signature_flow", lambda *_a, **_kw: None)


QUADRO = [
    {"acao": "Comprar insumos", "responsavel": "Pedro Rezende", "prazo": "2026-12-10", "tipo": "ACAO"},
    {"acao": "Reunir a equipe", "responsavel": "Ana Lima", "tipo": "ROTINA", "frequencia": "SEMANAL"},
    {"acao": "Conferir o carrinho de parada", "responsavel": "Pedro Rezende", "tipo": "ROTINA", "frequencia": "QUINZENAL"},
    {"acao": "Toda alta passa pelo checklist", "responsavel": None, "tipo": "PROCESSO"},
]


def _sb_com_quadro():
    sb = _sb()
    sb.reunioes[0]["json_ata"] = {"quadro_atribuicoes": [dict(a) for a in QUADRO]}
    return sb


# ─── 1. A Rotina nasce do envio da Ata ───────────────────────────────────────


@pytest.mark.parametrize("rota", ["aprovar", "aprovar-sem-assinatura"])
def test_enviar_a_ata_cria_a_rotina_com_responsavel_frequencia_e_primeiro_ciclo(
    make_client, monkeypatch, hoje, rota
):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro()

    r = make_client(sb).post(f"/api/reunioes/R1/{rota}")

    assert r.status_code == 200, r.text
    rotinas = sorted(sb.rotinas, key=lambda x: x["quadro_pos"])
    assert [
        (x["quadro_pos"], x["descricao"], x["responsavel_id"], x["frequencia"], x["comeca_em"], x["status"])
        for x in rotinas
    ] == [
        # Enviada numa quinta: a semana pela metade não conta.
        (1, "Reunir a equipe", "P2", "SEMANAL", "2026-11-23", "ATIVA"),
        (2, "Conferir o carrinho de parada", "P1", "QUINZENAL", "2026-12-01", "ATIVA"),
    ]
    # A Rotina não é Pendência.
    assert sorted(p["quadro_pos"] for p in sb.pendencias) == [0]


def test_reenviar_nao_cria_a_rotina_duas_vezes(make_client, monkeypatch, hoje):
    from app.services.pendencia_service import liberar_pendencias

    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro()
    assert make_client(sb).post("/api/reunioes/R1/aprovar").status_code == 200

    liberar_pendencias(sb, "R1", origem="RECONCILIACAO")

    assert len(sb.rotinas) == 2
