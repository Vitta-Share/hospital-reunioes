"""A migration 202 num Postgres de verdade (issue #1849, ADR 0097 decisão 14).

Sobe um Postgres descartável (o mesmo apoio da migration 175), aplica a 175 e
a 202 duas vezes e prova no banco que uma manifestação vira um caso só, que
só o caso da Ouvidoria leva o vínculo e que o caso que já existia fica como do
canal.

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

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "202_conduta_sinalizacao_da_ouvidoria.sql"

MANIFESTACAO = "6b1f7d1e-3c55-4a8e-9a77-0f5f1d2c9a01"
OUTRA = "6b1f7d1e-3c55-4a8e-9a77-0f5f1d2c9a02"

# O mínimo da manifestação da Ouvidoria (migration 001 em diante).
OUVIDORIA = f"""
CREATE TABLE ouvidoria_protocolos (id UUID PRIMARY KEY, status TEXT NOT NULL);
INSERT INTO ouvidoria_protocolos (id, status) VALUES
  ('{MANIFESTACAO}', 'aguardando_area'), ('{OUTRA}', 'em_classificacao');
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration 202 no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54202"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(OUVIDORIA)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        # Um caso de antes da 202, que veio pela página pública.
        pg.ok(
            "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado) "
            "VALUES ('CC-AAAA-AAAA', 'hash', 'v1:AAAA');"
        )
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso(banco, protocolo: str, colunas: str = "", valores: str = ""):
    return banco.sql(
        f"INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado{colunas}) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA'{valores});",
        papel="service_role",
    )


def test_o_caso_que_ja_existia_fica_como_do_canal(banco):
    assert banco.ok("SELECT origem FROM conduta_casos WHERE protocolo = 'CC-AAAA-AAAA';") == "canal"


def test_uma_manifestacao_vira_um_caso_so(banco):
    vinculo = ", origem, manifestacao_id"
    assert _caso(banco, "CC-BBBB-BBBB", vinculo, f", 'ouvidoria', '{MANIFESTACAO}'").returncode == 0

    segundo = _caso(banco, "CC-CCCC-CCCC", vinculo, f", 'ouvidoria', '{MANIFESTACAO}'")

    assert segundo.returncode != 0
    assert "uq_conduta_casos_manifestacao" in segundo.stderr


def test_o_caso_da_ouvidoria_precisa_do_vinculo(banco):
    sem_vinculo = _caso(banco, "CC-DDDD-DDDD", ", origem", ", 'ouvidoria'")

    assert sem_vinculo.returncode != 0
    assert "conduta_casos_vinculo_so_da_ouvidoria" in sem_vinculo.stderr


def test_o_caso_do_canal_nao_leva_vinculo(banco):
    do_canal = _caso(banco, "CC-EEEE-EEEE", ", manifestacao_id", f", '{OUTRA}'")

    assert do_canal.returncode != 0
    assert "conduta_casos_vinculo_so_da_ouvidoria" in do_canal.stderr


def test_a_manifestacao_ganha_o_carimbo_sem_mudar_de_estado(banco):
    banco.ok(f"UPDATE ouvidoria_protocolos SET conduta_sinalizada_em = now() WHERE id = '{OUTRA}';")

    assert banco.ok(f"SELECT status FROM ouvidoria_protocolos WHERE id = '{OUTRA}';") == "em_classificacao"
