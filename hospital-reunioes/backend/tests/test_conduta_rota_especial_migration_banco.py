"""A migration 210, a Rota Especial, num Postgres de verdade (issue #1829).

Sobe um Postgres descartável, aplica a 175, a 185, a 199 e a 210 (a 210 duas
vezes) sobre o mínimo de antes e prova no banco:

- o registro selado e a entrega do parecer não se alteram nem se apagam, nem
  pela `service_role`, e entram uma vez por caso;
- a resposta sobre a Direção só aceita as três do passo 3;
- o caso encerra com o desfecho `parecer_entregue`, e o `encaminhado` segue;
- o aviso aceita os marcos de 15, 30 e 60 dias;
- as tabelas novas têm RLS ligada e nenhuma policy.

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
MIGRATION = PASTA / "210_conduta_rota_especial.sql"
ANTERIORES = (PASTA / "185_conduta_triagem_e_ritos.sql", PASTA / "199_conduta_avisos_por_email.sql")

TABELAS_NOVAS = ("conduta_entregas_do_parecer", "conduta_selos")
CODIGO = "c" * 64


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a Rota Especial no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54210"
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


def _caso(banco) -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, rota, rito) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', 'especial', 'especial') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def test_a_migration_cria_as_duas_tabelas():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql)) == sorted(TABELAS_NOVAS)


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_toda_tabela_nova_tem_rls_ligada(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"


def test_nenhuma_policy_nas_tabelas_do_modulo(banco):
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename LIKE 'conduta_%';") == "0"


# ── O registro selado ───────────────────────────────────────────────────────


@pytest.fixture
def selado(banco):
    caso = _caso(banco)
    banco.ok(
        "INSERT INTO conduta_selos (caso_id, relato_cifrado, selado_em, codigo) "
        f"VALUES ('{caso}', 'v1:SELO', now(), '{CODIGO}');",
        papel="service_role",
    )
    return caso


@pytest.mark.parametrize("papel", ["service_role", None])
def test_o_selo_nao_se_altera(banco, selado, papel):
    r = banco.sql(f"UPDATE conduta_selos SET relato_cifrado = 'v1:OUTRO' WHERE caso_id = '{selado}';", papel=papel)
    assert r.returncode != 0
    assert "imutável" in r.stderr
    assert banco.ok(f"SELECT relato_cifrado FROM conduta_selos WHERE caso_id = '{selado}';") == "v1:SELO"


@pytest.mark.parametrize("papel", ["service_role", None])
def test_o_selo_nao_se_apaga(banco, selado, papel):
    r = banco.sql(f"DELETE FROM conduta_selos WHERE caso_id = '{selado}';", papel=papel)
    assert r.returncode != 0
    assert banco.ok(f"SELECT count(*) FROM conduta_selos WHERE caso_id = '{selado}';") == "1"


def test_um_selo_por_caso(banco, selado):
    r = banco.sql(
        "INSERT INTO conduta_selos (caso_id, relato_cifrado, selado_em, codigo) "
        f"VALUES ('{selado}', 'v1:DE_NOVO', now(), '{CODIGO}');",
        papel="service_role",
    )
    assert r.returncode != 0


# ── A entrega do parecer ────────────────────────────────────────────────────


@pytest.fixture
def entregue(banco):
    caso = _caso(banco)
    banco.ok(
        "INSERT INTO conduta_entregas_do_parecer (caso_id, destinatario_cifrado, entregue_em, autor_id) "
        f"VALUES ('{caso}', 'v1:QUEM', '2026-11-20', 'P1');",
        papel="service_role",
    )
    return caso


@pytest.mark.parametrize("papel", ["service_role", None])
def test_a_entrega_nao_se_altera(banco, entregue, papel):
    r = banco.sql(
        f"UPDATE conduta_entregas_do_parecer SET entregue_em = '2026-11-01' WHERE caso_id = '{entregue}';",
        papel=papel,
    )
    assert r.returncode != 0
    assert "imutável" in r.stderr


@pytest.mark.parametrize("papel", ["service_role", None])
def test_a_entrega_nao_se_apaga(banco, entregue, papel):
    r = banco.sql(f"DELETE FROM conduta_entregas_do_parecer WHERE caso_id = '{entregue}';", papel=papel)
    assert r.returncode != 0
    assert banco.ok(f"SELECT count(*) FROM conduta_entregas_do_parecer WHERE caso_id = '{entregue}';") == "1"


def test_a_entrega_guarda_o_destinatario_so_cifrado(banco):
    caso = _caso(banco)
    r = banco.sql(
        "INSERT INTO conduta_entregas_do_parecer (caso_id, destinatario_cifrado, entregue_em, autor_id) "
        f"VALUES ('{caso}', 'Presidente do Conselho', '2026-11-20', 'P1');",
        papel="service_role",
    )
    assert r.returncode != 0


# ── O caso ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("resposta", ["sim", "nao", "nao_sei"])
def test_a_direcao_aceita_as_tres_respostas_do_passo_3(banco, resposta):
    caso = _caso(banco)
    r = banco.sql(f"UPDATE conduta_casos SET direcao_envolvida = '{resposta}' WHERE id = '{caso}';")
    assert r.returncode == 0, r.stderr


def test_a_direcao_recusa_outra_resposta(banco):
    caso = _caso(banco)
    assert banco.sql(f"UPDATE conduta_casos SET direcao_envolvida = 'talvez' WHERE id = '{caso}';").returncode != 0


@pytest.mark.parametrize("desfecho", ["parecer_entregue", "encaminhado"])
def test_o_desfecho_aceita_o_parecer_entregue_e_o_encaminhado(banco, desfecho):
    caso = _caso(banco)
    r = banco.sql(f"UPDATE conduta_casos SET desfecho = '{desfecho}' WHERE id = '{caso}';")
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("motivo", ["marco_15", "marco_30", "marco_60", "tarefa", "lembrete_1"])
def test_o_aviso_aceita_os_marcos_e_os_motivos_de_antes(banco, motivo):
    caso = _caso(banco)
    r = banco.sql(
        "INSERT INTO conduta_avisos (caso_id, participante_id, motivo, referencia) "
        f"VALUES ('{caso}', 'P1', '{motivo}', '2026-11-01');"
    )
    assert r.returncode == 0, r.stderr


def test_o_aviso_recusa_motivo_desconhecido(banco):
    caso = _caso(banco)
    r = banco.sql(
        "INSERT INTO conduta_avisos (caso_id, participante_id, motivo, referencia) "
        f"VALUES ('{caso}', 'P1', 'marco_45', '2026-11-01');"
    )
    assert r.returncode != 0
