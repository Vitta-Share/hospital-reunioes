"""A migration 230 num Postgres de verdade (issue #1843).

Sobe um Postgres descartável (o mesmo apoio da migration 175), aplica a 175 e
a 230 duas vezes e prova no banco que o nome de quem relata só entra cifrado,
que a ciência leva o momento e a versão juntos e que a confiança vai de 1 a 5.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from test_conduta_migration_banco import ESQUEMA_ANTERIOR
from test_conduta_migration_banco import MIGRATION as MIGRATION_175
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "230_conduta_relato_em_passos.sql"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration 230 no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54230"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso(banco, protocolo: str, colunas: str, valores: str):
    return banco.sql(
        f"INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, {colunas}) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', {valores});",
        papel="service_role",
    )


def test_o_relato_completo_cabe_nas_colunas_novas(banco):
    gravado = _caso(
        banco,
        "CC-AAAA-AAAA",
        "relator_nome_cifrado, ciencia_em, ciencia_versoes, confianca",
        "'v1:BBBB', now(), '{\"aviso_p1_boa_fe\": 2}', 4",
    )

    assert gravado.returncode == 0, gravado.stderr


def test_o_nome_de_quem_relata_so_entra_cifrado(banco):
    em_claro = _caso(banco, "CC-BBBB-BBBB", "relator_nome_cifrado", "'Maria da Silva'")

    assert em_claro.returncode != 0
    assert "conduta_casos_relator_nome_check" in em_claro.stderr


def test_a_ciencia_leva_o_momento_e_a_versao_juntos(banco):
    sem_versao = _caso(banco, "CC-CCCC-CCCC", "ciencia_em", "now()")

    assert sem_versao.returncode != 0
    assert "conduta_casos_ciencia_check" in sem_versao.stderr


@pytest.mark.parametrize("nota", [0, 6])
def test_a_confianca_vai_de_1_a_5(banco, nota):
    fora = _caso(banco, f"CC-DDDD-DDD{nota}", "confianca", str(nota))

    assert fora.returncode != 0
    assert "conduta_casos_confianca_check" in fora.stderr
