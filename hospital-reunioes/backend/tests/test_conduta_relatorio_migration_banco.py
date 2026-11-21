"""A migration 209, o relatório de apuração, num Postgres de verdade (issue
#1832).

Sobe um Postgres descartável, aplica a 175, a 192, a 193 e a 209 (a 209 duas
vezes) sobre o mínimo de antes e prova no banco:

- a edição entra como versão nova: a versão guardada não se altera nem se
  apaga, nem pela `service_role`;
- só entra versão em caso na etapa Apuração, e o texto entra cifrado;
- a Apuração não vai a voto sem o relatório;
- a assinatura do relatório aponta para a versão assinada;
- a tabela nova tem RLS ligada, nenhuma policy, e o anon não lê.

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

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
ANTERIORES = ("192_conduta_assinaturas.sql", "193_conduta_depoimentos.sql")
MIGRATION = PASTA / "209_conduta_relatorio_de_apuracao.sql"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar as travas do relatório no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54209"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        for nome in ANTERIORES:
            pg.ok((PASTA / nome).read_text(encoding="utf-8"))
        pg.ok("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;")
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso(banco, etapa: str = "apuracao") -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', '{etapa}') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _versao(banco, caso: str, versao: int = 1, texto: str = "v1:TEXTO"):
    return banco.sql(
        "INSERT INTO conduta_relatorios (caso_id, tipo, versao, texto_cifrado, origem, autor_id) "
        f"VALUES ('{caso}', 'relatorio', {versao}, '{texto}', 'agente', 'P1') RETURNING id;",
        papel="service_role",
    )


def test_a_versao_guardada_nao_se_altera_nem_se_apaga(banco):
    caso = _caso(banco)
    assert _versao(banco, caso).returncode == 0
    assert _versao(banco, caso, versao=2).returncode == 0

    troca = banco.sql(
        f"UPDATE conduta_relatorios SET texto_cifrado = 'v1:OUTRO' WHERE caso_id = '{caso}';", papel="service_role"
    )
    apaga = banco.sql(f"DELETE FROM conduta_relatorios WHERE caso_id = '{caso}';", papel="service_role")

    assert "fica guardada" in troca.stderr
    assert "fica guardada" in apaga.stderr
    assert banco.ok(f"SELECT count(*) FROM conduta_relatorios WHERE caso_id = '{caso}';") == "2"


def test_a_mesma_versao_nao_entra_duas_vezes(banco):
    caso = _caso(banco)
    _versao(banco, caso)

    assert "duplicate key" in _versao(banco, caso).stderr


def test_so_entra_versao_na_apuracao_e_cifrada(banco):
    assert "etapa Apuração" in _versao(banco, _caso(banco, etapa="triagem")).stderr
    assert "check" in _versao(banco, _caso(banco), texto="em claro").stderr.lower()


def test_a_apuracao_nao_vai_a_voto_sem_o_relatorio(banco):
    caso = _caso(banco)
    para_voto = f"UPDATE conduta_casos SET etapa = 'voto' WHERE id = '{caso}';"

    assert "relatório" in banco.sql(para_voto, papel="service_role").stderr
    _versao(banco, caso)
    banco.ok(para_voto, papel="service_role")


def test_a_assinatura_do_relatorio_aponta_para_a_versao(banco):
    caso = _caso(banco)
    versao = _versao(banco, caso).stdout.strip().splitlines()[-1]
    sem_versao = banco.sql(
        "INSERT INTO conduta_assinaturas (tipo, caso_id, signatarios) "
        f"VALUES ('relatorio_de_apuracao', '{caso}', ARRAY['P1']);",
        papel="service_role",
    )

    assert "conduta_assinaturas_relatorio_da_versao" in sem_versao.stderr
    banco.ok(
        "INSERT INTO conduta_assinaturas (tipo, caso_id, signatarios, relatorio_id) "
        f"VALUES ('relatorio_de_apuracao', '{caso}', ARRAY['P1'], '{versao}');",
        papel="service_role",
    )


def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok("SELECT relrowsecurity FROM pg_class WHERE relname = 'conduta_relatorios';") == "t"
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename = 'conduta_relatorios';") == "0"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_o_anon_nao_le(banco, papel):
    assert "permission denied" in banco.sql("SELECT * FROM conduta_relatorios;", papel=papel).stderr
