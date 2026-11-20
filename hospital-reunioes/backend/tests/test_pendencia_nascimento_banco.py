"""O evento de nascimento no Histórico da Pendência, num Postgres de verdade (issue #1867).

ADR 0098, decisão 1: no envio da Ata nascem todas as Pendências do quadro,
cada uma com o evento de nascimento no histórico. O evento vem de um trigger
da migration 171, no mesmo INSERT da Pendência: nenhum caminho do backend
(envio, reconciliação, aprovação sem assinatura) cria Pendência sem ele.

Usa o Postgres descartável de `test_pendencia_historico_banco.py`: aplica a
169 e a 171 (duas vezes, para provar que rodar de novo é inofensivo).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from test_pendencia_historico_banco import (  # noqa: E402
    ESQUEMA_ANTERIOR,
    MIGRATION,
    _bin_do_postgres,
    _Postgres,
)

MIGRATION_171 = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "171_nascimento_da_pendencia.sql"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar o trigger no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54171"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok("INSERT INTO reunioes (id_reuniao, json_ata) VALUES ('R9', '{}');")
        pg.ok(MIGRATION.read_text(encoding="utf-8"))
        nascimento = MIGRATION_171.read_text(encoding="utf-8")
        pg.ok(nascimento)
        pg.ok(nascimento)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def test_pendencia_que_nasce_da_ata_ganha_o_evento_de_nascimento(banco):
    banco.ok(
        "INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, prazo, status, quadro_pos) VALUES "
        "('A201', 'R9', 'Comprar luvas', '2026-12-10', 'PENDENTE', 0), "
        "('A202', 'R9', 'Treinar equipe', NULL, 'PENDENTE', 1);",
        papel="service_role",
    )

    eventos = banco.ok(
        "SELECT id_acao, comando, autor_nome, status_antes IS NULL, status_depois, prazo_depois "
        "FROM pendencia_historico WHERE id_acao IN ('A201', 'A202') ORDER BY id_acao;"
    ).splitlines()

    assert eventos == [
        "A201|nascimento|Sistema|t|PENDENTE|2026-12-10",
        "A202|nascimento|Sistema|t|PENDENTE|",
    ]
    anotacao = banco.ok("SELECT anotacao FROM pendencia_historico WHERE id_acao = 'A201';")
    assert "R9" in anotacao


def test_o_nascimento_e_um_so_mesmo_que_a_pendencia_mude_depois(banco):
    banco.ok(
        "INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, prazo, status) "
        "VALUES ('A203', 'R9', 'Pintar sala', '2026-12-01', 'PENDENTE');"
    )
    r = banco.sql(
        "SELECT registrar_acao_da_pendencia('A203', 'iniciar', 'comecei', 'P01', 'Ana', "
        "'PENDENTE', 'EM_PROGRESSO', NULL, NULL, false);",
        papel="service_role",
    )
    assert r.returncode == 0, r.stderr

    assert banco.ok("SELECT comando FROM pendencia_historico WHERE id_acao = 'A203' ORDER BY id;").splitlines() == [
        "nascimento",
        "iniciar",
    ]


def test_o_lembrete_do_nucleo_tambem_nasce_com_o_evento(banco):
    banco.ok(
        "INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, prazo, status) "
        "VALUES ('A204', NULL, 'Renovar alvará', '2027-01-10', 'PENDENTE');"
    )

    assert banco.ok("SELECT comando FROM pendencia_historico WHERE id_acao = 'A204';") == "nascimento"
