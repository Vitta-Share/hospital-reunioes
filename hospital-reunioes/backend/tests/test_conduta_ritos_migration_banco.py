"""A migration 185 do Canal de Conduta num Postgres de verdade (issue #1824).

Sobe um Postgres descartável, aplica a 175 e a 185 (a 185 duas vezes) sobre o
mínimo de antes e prova no banco:

- o prazo vencido não se altera nem se apaga, nem pela `service_role`;
- o rito Completo prorroga uma vez só, e só com a justificativa cifrada;
- a Participação aceita o segundo leitor;
- toda tabela nova tem RLS ligada e nenhuma policy.

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

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "185_conduta_triagem_e_ritos.sql"

TABELAS_NOVAS = ("conduta_contestacoes", "conduta_contestacao_votos", "conduta_prazos_vencidos")


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar o prazo vencido no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54179"
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


def _caso(banco, rito: str = "completo") -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, rito) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', '{rito}') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def test_a_migration_cria_as_tres_tabelas():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql)) == sorted(TABELAS_NOVAS)


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_toda_tabela_nova_tem_rls_ligada(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"


def test_nenhuma_policy_nas_tabelas_do_modulo(banco):
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename LIKE 'conduta_%';") == "0"


# ── O prazo vencido ─────────────────────────────────────────────────────────


@pytest.fixture
def vencido(banco):
    caso = _caso(banco)
    banco.ok(
        f"INSERT INTO conduta_prazos_vencidos (caso_id, rito, prazo_em) VALUES ('{caso}', 'completo', '2026-10-01');",
        papel="service_role",
    )
    return caso


@pytest.mark.parametrize("papel", ["service_role", None])
def test_prazo_vencido_nao_se_altera(banco, vencido, papel):
    r = banco.sql(
        f"UPDATE conduta_prazos_vencidos SET prazo_em = '2027-01-01' WHERE caso_id = '{vencido}';", papel=papel
    )
    assert r.returncode != 0
    assert "para sempre" in r.stderr
    assert banco.ok(f"SELECT prazo_em FROM conduta_prazos_vencidos WHERE caso_id = '{vencido}';") == "2026-10-01"


@pytest.mark.parametrize("papel", ["service_role", None])
def test_prazo_vencido_nao_se_apaga(banco, vencido, papel):
    r = banco.sql(f"DELETE FROM conduta_prazos_vencidos WHERE caso_id = '{vencido}';", papel=papel)
    assert r.returncode != 0
    assert banco.ok(f"SELECT count(*) FROM conduta_prazos_vencidos WHERE caso_id = '{vencido}';") == "1"


def test_prazo_vencido_nao_se_trunca(banco, vencido):
    r = banco.sql("TRUNCATE conduta_prazos_vencidos;")
    assert r.returncode != 0
    assert "para sempre" in r.stderr


def test_o_mesmo_prazo_vencido_entra_uma_vez(banco, vencido):
    r = banco.sql(
        "INSERT INTO conduta_prazos_vencidos (caso_id, rito, prazo_em) "
        f"VALUES ('{vencido}', 'completo', '2026-10-01');",
        papel="service_role",
    )
    assert r.returncode != 0


# ── A prorrogação ───────────────────────────────────────────────────────────


def _prorrogar(banco, caso: str, cifrada: str = "v1:BBBB"):
    return banco.sql(
        f"UPDATE conduta_casos SET prorrogado_em = now(), prorrogacao_cifrada = '{cifrada}' WHERE id = '{caso}';",
        papel="service_role",
    )


def test_o_completo_prorroga_uma_vez_so(banco):
    caso = _caso(banco)
    assert _prorrogar(banco, caso).returncode == 0

    segunda = _prorrogar(banco, caso, "v1:CCCC")
    assert segunda.returncode != 0
    assert "uma vez" in segunda.stderr
    desfazer = banco.sql(f"UPDATE conduta_casos SET prorrogado_em = NULL WHERE id = '{caso}';", papel="service_role")
    assert desfazer.returncode != 0
    # O resto do caso continua mudando: a trava é só da prorrogação.
    assert (
        banco.sql(f"UPDATE conduta_casos SET etapa = 'apuracao' WHERE id = '{caso}';", papel="service_role").returncode
        == 0
    )


def test_so_o_completo_prorroga(banco):
    assert _prorrogar(banco, _caso(banco, "rapido")).returncode != 0


def test_a_prorrogacao_exige_a_justificativa_cifrada(banco):
    assert _prorrogar(banco, _caso(banco), "justificativa em claro").returncode != 0


# ── O segundo leitor e o recibo ─────────────────────────────────────────────


def test_a_participacao_aceita_o_segundo_leitor(banco):
    banco.ok(
        "INSERT INTO participacoes (colegiado_id, participante_id, papel, vigencia_inicio, vigencia_fim) "
        "SELECT id, 'P1', 'segundo_leitor', current_date, current_date + 700 FROM colegiados WHERE slug = 'conduta';"
    )


def test_nenhum_dado_de_pessoa_entra_pela_migration():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert re.search(r"INSERT INTO (participacoes|participantes)", sql, re.IGNORECASE) is None


def test_o_recibo_e_o_179(banco):
    assert banco.ok("SELECT max(numero) FROM migracoes_aplicadas;") == "185"
