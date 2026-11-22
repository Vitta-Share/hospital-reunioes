"""A migration 217, o afastamento cautelar, num Postgres de verdade (issue #1836).

Sobe um Postgres descartável, aplica a 175, a 185 e a 217 (a 217 duas vezes)
sobre o mínimo de antes e prova no banco:

- um afastamento por Citado e por caso, com quem afastar e o motivo só
  cifrados;
- a entrega e o parecer, uma vez gravados, não mudam, e o afastamento não se
  apaga, nem pela `service_role`;
- na Rota Especial o parecer leva o resultado e a ciência; no caso comum, não;
- a tabela nova tem RLS ligada e nenhuma policy.

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

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION = PASTA / "217_conduta_afastamento_cautelar.sql"
ANTERIORES = (PASTA / "185_conduta_triagem_e_ritos.sql",)
TABELA = "conduta_afastamentos"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar o afastamento cautelar no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54217"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        for anterior in ANTERIORES:
            pg.ok(anterior.read_text(encoding="utf-8"))
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso_e_citado(banco, rota: str = "comum") -> tuple[str, str]:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    caso = banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, rota) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', '{rota}') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]
    citado = banco.ok(
        f"INSERT INTO conduta_citados (caso_id, nome_cifrado) VALUES ('{caso}', 'v1:NOME') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]
    return caso, citado


def _afastamento(banco, rota: str = "comum") -> str:
    caso, citado = _caso_e_citado(banco, rota)
    return banco.ok(
        f"INSERT INTO {TABELA} (caso_id, citado_id, rota, quem_cifrado, motivo_cifrado, registrado_por) "
        f"VALUES ('{caso}', '{citado}', '{rota}', 'v1:QUEM', 'v1:MOTIVO', 'P1') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _parecer(resultado: str | None = None, ciencia: str | None = None) -> str:
    campos = "parecer_storage_path = 'afastamentos/x', parecer_anexado_por = 'P1', parecer_anexado_em = now()"
    if resultado:
        campos += f", parecer_resultado = '{resultado}'"
    if ciencia:
        campos += f", ciencia_de = {ciencia}"
    return campos


def test_a_migration_cria_so_a_tabela_do_afastamento():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql) == [TABELA]


def test_a_tabela_tem_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{TABELA}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{TABELA}';") == "0"


def test_quem_afastar_e_o_motivo_so_entram_cifrados(banco):
    caso, citado = _caso_e_citado(banco)
    r = banco.sql(
        f"INSERT INTO {TABELA} (caso_id, citado_id, rota, quem_cifrado, motivo_cifrado, registrado_por) "
        f"VALUES ('{caso}', '{citado}', 'comum', 'Carlos Pereira', 'v1:MOTIVO', 'P1');",
        papel="service_role",
    )
    assert r.returncode != 0


def test_um_afastamento_por_citado_e_por_caso(banco):
    caso, citado = _caso_e_citado(banco)
    insere = (
        f"INSERT INTO {TABELA} (caso_id, citado_id, rota, quem_cifrado, motivo_cifrado, registrado_por) "
        f"VALUES ('{caso}', '{citado}', 'comum', 'v1:QUEM', 'v1:MOTIVO', 'P1');"
    )
    banco.ok(insere, papel="service_role")
    assert banco.sql(insere, papel="service_role").returncode != 0


def test_a_entrega_se_grava_uma_vez_e_nao_muda(banco):
    afastamento = _afastamento(banco)
    banco.ok(
        f"UPDATE {TABELA} SET entregue_ao_dp_em = '2026-11-20', entregue_ao_dp_por = 'P1' WHERE id = '{afastamento}';",
        papel="service_role",
    )
    r = banco.sql(
        f"UPDATE {TABELA} SET entregue_ao_dp_em = '2026-11-01' WHERE id = '{afastamento}';", papel="service_role"
    )
    assert r.returncode != 0
    assert "não muda" in r.stderr


def test_a_entrega_sem_quem_registrou_e_recusada(banco):
    afastamento = _afastamento(banco)
    r = banco.sql(f"UPDATE {TABELA} SET entregue_ao_juridico_em = '2026-11-20' WHERE id = '{afastamento}';")
    assert r.returncode != 0


def test_o_motivo_nunca_muda(banco):
    afastamento = _afastamento(banco)
    r = banco.sql(f"UPDATE {TABELA} SET motivo_cifrado = 'v1:OUTRO' WHERE id = '{afastamento}';", papel="service_role")
    assert r.returncode != 0


@pytest.mark.parametrize("papel", ["service_role", None])
def test_o_afastamento_nao_se_apaga(banco, papel):
    afastamento = _afastamento(banco)
    r = banco.sql(f"DELETE FROM {TABELA} WHERE id = '{afastamento}';", papel=papel)
    assert r.returncode != 0
    assert banco.ok(f"SELECT count(*) FROM {TABELA} WHERE id = '{afastamento}';") == "1"


def test_o_parecer_anexado_nao_se_troca(banco):
    afastamento = _afastamento(banco)
    banco.ok(f"UPDATE {TABELA} SET {_parecer()} WHERE id = '{afastamento}';", papel="service_role")
    r = banco.sql(
        f"UPDATE {TABELA} SET parecer_storage_path = 'afastamentos/y' WHERE id = '{afastamento}';", papel="service_role"
    )
    assert r.returncode != 0


def test_no_caso_comum_o_parecer_nao_leva_resultado(banco):
    afastamento = _afastamento(banco)
    r = banco.sql(f"UPDATE {TABELA} SET {_parecer('afastar')} WHERE id = '{afastamento}';", papel="service_role")
    assert r.returncode != 0


def test_na_rota_especial_o_parecer_leva_resultado_e_ciencia(banco):
    sem = _afastamento(banco, "especial")
    assert banco.sql(f"UPDATE {TABELA} SET {_parecer()} WHERE id = '{sem}';", papel="service_role").returncode != 0
    com = _afastamento(banco, "especial")
    r = banco.sql(
        f"UPDATE {TABELA} SET {_parecer('nao_afastar', "ARRAY['P1']")} WHERE id = '{com}';", papel="service_role"
    )
    assert r.returncode == 0, r.stderr
