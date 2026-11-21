"""A migration 195 do agente de triagem do Canal num Postgres de verdade (issue #1827).

Sobe um Postgres descartável, aplica a 175 e a 195 (a 195 duas vezes) sobre o
mínimo de antes e prova no banco:

- a cota do agente para no teto do dia, e só a `service_role` a chama;
- a sugestão é uma por caso, e a discordância sem motivo não entra;
- toda tabela nova tem RLS ligada e nenhuma policy.

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

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "195_conduta_agente_de_triagem.sql"

TABELAS_NOVAS = ("conduta_sugestoes", "conduta_sugestao_respostas", "conduta_agente_cota")


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a cota do agente no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54195"
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


def _caso(banco) -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _sugerida(banco) -> str:
    caso = _caso(banco)
    banco.ok(
        "INSERT INTO conduta_sugestoes (caso_id, situacao, sugestao_cifrada, modelo, prompt_versao) "
        f"VALUES ('{caso}', 'sugerida', 'v1:BBBB', 'claude-sonnet-5-5', '1');",
        papel="service_role",
    )
    return caso


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_toda_tabela_nova_tem_rls_ligada(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"


def test_nenhuma_policy_nas_tabelas_do_modulo(banco):
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename LIKE 'conduta_%';") == "0"


def test_a_cota_para_no_teto_do_dia(banco):
    banco.ok("DELETE FROM conduta_agente_cota;")
    respostas = [
        banco.ok("SELECT reservada FROM conduta_agente_reservar_chamada(2);", papel="service_role") for _ in range(3)
    ]
    assert respostas == ["t", "t", "f"]
    assert banco.ok("SELECT chamadas FROM conduta_agente_cota;") == "2"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_so_o_backend_chama_a_cota(banco, papel):
    r = banco.sql("SELECT reservada FROM conduta_agente_reservar_chamada(100);", papel=papel)
    assert r.returncode != 0
    assert "permission denied" in r.stderr


def test_o_caso_tem_uma_leitura_so(banco):
    caso = _sugerida(banco)
    r = banco.sql(
        "INSERT INTO conduta_sugestoes (caso_id, situacao, motivo_manual, modelo, prompt_versao) "
        f"VALUES ('{caso}', 'manual', 'teto', 'claude-sonnet-5-5', '1');",
        papel="service_role",
    )
    assert r.returncode != 0


def test_triagem_manual_exige_o_motivo(banco):
    caso = _caso(banco)
    r = banco.sql(
        "INSERT INTO conduta_sugestoes (caso_id, situacao, modelo, prompt_versao) "
        f"VALUES ('{caso}', 'manual', 'claude-sonnet-5-5', '1');",
        papel="service_role",
    )
    assert r.returncode != 0


def test_discordar_sem_motivo_nao_entra_no_banco(banco):
    caso = _sugerida(banco)
    sem = banco.sql(
        "INSERT INTO conduta_sugestao_respostas (caso_id, item, resposta, autor_id) "
        f"VALUES ('{caso}', 'rito', 'discordo', 'P1');",
        papel="service_role",
    )
    assert sem.returncode != 0
    banco.ok(
        "INSERT INTO conduta_sugestao_respostas (caso_id, item, resposta, motivo_cifrado, autor_id) "
        f"VALUES ('{caso}', 'rito', 'discordo', 'v1:CCCC', 'P1');",
        papel="service_role",
    )
    de_novo = banco.sql(
        "INSERT INTO conduta_sugestao_respostas (caso_id, item, resposta, autor_id) "
        f"VALUES ('{caso}', 'rito', 'confirmo', 'P1');",
        papel="service_role",
    )
    assert de_novo.returncode != 0
