"""A linha de "Todos os participantes" no banco (issue #2327, migration 242).

A chave única da Pendência e da Rotina era a posição no quadro: uma por linha.
Desdobrada por pessoa, a mesma posição recebe uma para cada Participante. O
Postgres descartável de `test_pendencia_historico_banco.py` prova que a chave
nova aceita uma por pessoa na mesma posição e continua recusando a repetida,
inclusive a linha sem vínculo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from test_pendencia_historico_banco import ESQUEMA_ANTERIOR, _bin_do_postgres, _Postgres  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION_177 = MIGRATIONS / "177_rotina_e_verificacao.sql"
MIGRATION_242 = MIGRATIONS / "242_pendencia_por_participante_na_linha_de_todos.sql"

# O índice da migration 057, a chave antiga da Pendência.
INDICE_057 = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_pendencias_reuniao_quadro_pos
  ON pendencias (id_reuniao, quadro_pos) WHERE quadro_pos IS NOT NULL;
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a chave da Pendência no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54242"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(INDICE_057)
        pg.ok(MIGRATION_177.read_text(encoding="utf-8"))
        pg.ok("INSERT INTO reunioes (id_reuniao, json_ata) VALUES ('R9', '{}');")
        pg.ok("INSERT INTO participantes (id, nome_completo) VALUES ('P1', 'Pedro Rezende'), ('P2', 'Ana Lima');")
        sql = MIGRATION_242.read_text(encoding="utf-8")
        pg.ok(sql)
        pg.ok(sql)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _pendencia(banco, id_acao: str, posicao: int, responsavel: str | None):
    valor = "NULL" if responsavel is None else f"'{responsavel}'"
    return banco.sql(
        "INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, responsavel_id, quadro_pos) "
        f"VALUES ('{id_acao}', 'R9', 'Zerar as pendências', {valor}, {posicao});",
        papel="service_role",
    )


def _rotina(banco, posicao: int, responsavel: str | None):
    valor = "NULL" if responsavel is None else f"'{responsavel}'"
    return banco.sql(
        "INSERT INTO rotinas (id_reuniao, quadro_pos, descricao, responsavel_id, frequencia) "
        f"VALUES ('R9', {posicao}, 'Tratar o ponto', {valor}, 'SEMANAL');",
        papel="service_role",
    )


def test_a_mesma_linha_do_quadro_tem_uma_pendencia_por_participante(banco):
    assert _pendencia(banco, "A001", 0, "P1").returncode == 0
    assert _pendencia(banco, "A002", 0, "P2").returncode == 0

    repetida = _pendencia(banco, "A003", 0, "P1")

    assert repetida.returncode != 0
    assert "duplicate key" in repetida.stderr


def test_a_linha_sem_vinculo_continua_uma_so(banco):
    assert _pendencia(banco, "A010", 5, None).returncode == 0

    repetida = _pendencia(banco, "A011", 5, None)

    assert repetida.returncode != 0
    assert "duplicate key" in repetida.stderr


def test_a_mesma_linha_do_quadro_tem_uma_rotina_por_participante(banco):
    assert _rotina(banco, 1, "P1").returncode == 0
    assert _rotina(banco, 1, "P2").returncode == 0

    repetida = _rotina(banco, 1, "P2")

    assert repetida.returncode != 0
    assert "duplicate key" in repetida.stderr


def test_a_rotina_sem_vinculo_continua_uma_so(banco):
    assert _rotina(banco, 7, None).returncode == 0

    repetida = _rotina(banco, 7, None)

    assert repetida.returncode != 0
    assert "duplicate key" in repetida.stderr


def test_a_migration_deixa_o_recibo(banco):
    assert banco.ok("SELECT count(*) FROM migracoes_aplicadas WHERE numero = 242;") == "1"
