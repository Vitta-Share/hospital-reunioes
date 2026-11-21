"""A migration 203, a nota do Comitê ao Núcleo, num Postgres de verdade
(issue #1850).

Sobe um Postgres descartável, aplica a 175 e a 203 (a 203 duas vezes) sobre o
mínimo de antes e prova no banco:

- a linha do lado do Núcleo não tem coluna que leve ao caso nem a quem agiu;
- uma nota só esperando o envio por caso;
- as duas tabelas têm RLS ligada, nenhuma policy, e nem o anon nem o
  authenticated leem, mesmo com o GRANT padrão do Supabase.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from test_conduta_migration_banco import ESQUEMA_ANTERIOR
from test_conduta_migration_banco import MIGRATION as MIGRATION_175
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "203_conduta_nota_ao_nucleo.sql"

TABELAS_NOVAS = ("conduta_notas_nsp", "nsp_notas_do_comite")


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a nota do Comitê no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54203"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        # O GRANT padrão do Supabase: toda tabela nova nasce aberta ao anon e ao
        # authenticated. Sem ele o `permission denied` viria de graça e o teste
        # de acesso não provaria o REVOKE da 203.
        pg.ok("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;")
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso(banco) -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def test_a_migration_cria_as_duas_tabelas():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql)) == sorted(TABELAS_NOVAS)


def test_a_nota_do_nucleo_nao_tem_coluna_que_leve_ao_caso(banco):
    colunas = banco.ok(
        "SELECT string_agg(column_name, ',' ORDER BY column_name) FROM information_schema.columns "
        "WHERE table_name = 'nsp_notas_do_comite';"
    )
    assert colunas.split(",") == ["enviada_em", "id", "texto"]


def test_uma_nota_so_esperando_o_envio_por_caso(banco):
    caso = _caso(banco)
    nota = f"INSERT INTO conduta_notas_nsp (caso_id, texto_cifrado, escrita_por) VALUES ('{caso}', 'v1:AAAA', 'P1');"
    banco.ok(nota, papel="service_role")

    segunda = banco.sql(nota, papel="service_role")

    assert "uq_conduta_notas_nsp_pendente" in segunda.stderr
    banco.ok(
        f"UPDATE conduta_notas_nsp SET enviada_por = 'P1', enviada_em = now() WHERE caso_id = '{caso}';",
        papel="service_role",
    )
    banco.ok(nota, papel="service_role")  # enviada a primeira, cabe outra


def test_a_nota_sem_cifra_e_recusada(banco):
    caso = _caso(banco)
    r = banco.sql(
        f"INSERT INTO conduta_notas_nsp (caso_id, texto_cifrado, escrita_por) VALUES ('{caso}', 'em claro', 'P1');",
        papel="service_role",
    )
    assert "check" in r.stderr.lower()


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_toda_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{tabela}';") == "0"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_o_anon_nao_le(banco, tabela, papel):
    r = banco.sql(f"SELECT * FROM {tabela};", papel=papel)
    assert "permission denied" in r.stderr
