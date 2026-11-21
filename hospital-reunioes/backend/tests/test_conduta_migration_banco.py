"""A migration 175 do Canal de Conduta num Postgres de verdade (issue #1820).

Sobe um Postgres descartável (o mesmo apoio da migration 169), monta o mínimo
das tabelas de antes, aplica a migration duas vezes e prova no banco:

- toda tabela nova tem RLS ligada e nenhuma policy;
- a trilha recusa UPDATE, DELETE e TRUNCATE, inclusive para a `service_role`;
- a trilha recusa a linha que não aponta para a última do caso;
- o protocolo não vem de sequência, e a numeração da Ouvidoria não é tocada;
- o relato só entra cifrado.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "175_conduta_fundacao.sql"

TABELAS_NOVAS = ("conduta_casos", "conduta_atribuicoes", "conduta_citados", "conduta_trilha")

# O mínimo de antes da 175 (migrations 001, 102, 114, 146, 150 e o schema
# `storage` do Supabase), mais a sequência do protocolo da Ouvidoria, para
# provar que ela fica onde estava.
ESQUEMA_ANTERIOR = """
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN NOSUPERUSER BYPASSRLS;

CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);
CREATE TABLE participantes (id VARCHAR(10) PRIMARY KEY, nome_completo TEXT);
CREATE TABLE setores (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), nome TEXT);
CREATE TABLE colegiados (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  setor_id UUID REFERENCES setores(id)
);
CREATE TABLE participacoes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  colegiado_id UUID NOT NULL REFERENCES colegiados(id),
  participante_id VARCHAR(10) NOT NULL REFERENCES participantes(id),
  papel TEXT NOT NULL CHECK (papel IN ('presidencia', 'suplente', 'membro')),
  vigencia_inicio DATE NOT NULL,
  vigencia_fim DATE NOT NULL
);
CREATE TABLE tecnologia_produtos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome TEXT NOT NULL,
  ordem INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX tecnologia_produtos_nome_lower_idx ON tecnologia_produtos (lower(nome));
CREATE SEQUENCE ouvidoria_protocolo_seq START 41;

CREATE SCHEMA storage;
CREATE TABLE storage.buckets (id TEXT PRIMARY KEY, name TEXT, public BOOLEAN, file_size_limit BIGINT);
CREATE TABLE storage.objects (id UUID PRIMARY KEY DEFAULT gen_random_uuid());

INSERT INTO participantes (id, nome_completo) VALUES ('P1', 'Pessoa de Teste');
INSERT INTO colegiados (slug, nome) VALUES ('nsp', 'Núcleo de Segurança do Paciente');

GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
"""

CODIGO_A = "a" * 64
CODIGO_B = "b" * 64
CODIGO_C = "c" * 64


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a trilha no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54175"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso(banco, protocolo: str) -> str:
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _linha(banco, caso: str, codigo: str, anterior: str | None, *, papel="service_role"):
    anterior_sql = f"'{anterior}'" if anterior else "NULL"
    return banco.sql(
        "INSERT INTO conduta_trilha (caso_id, autor_id, acao, registrado_em, codigo_anterior, codigo) "
        f"VALUES ('{caso}', 'P1', 'leitura', now(), {anterior_sql}, '{codigo}');",
        papel=papel,
    )


# ── RLS ─────────────────────────────────────────────────────────────────────


def test_a_migration_cria_as_quatro_tabelas_do_modulo():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql)) == sorted(TABELAS_NOVAS)


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_toda_tabela_nova_tem_rls_ligada(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"


def test_nenhuma_policy_nas_tabelas_do_modulo(banco):
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename LIKE 'conduta_%';") == "0"


def test_o_bucket_e_privado(banco):
    assert banco.ok("SELECT public FROM storage.buckets WHERE id = 'conduta-arquivos';") == "f"


# ── A trilha ────────────────────────────────────────────────────────────────


@pytest.fixture
def caso_com_trilha(banco):
    caso = _caso(banco, f"CC-{os.urandom(2).hex().upper()}-TRIL")
    r = _linha(banco, caso, os.urandom(32).hex(), None)
    assert r.returncode == 0, r.stderr
    return caso


@pytest.mark.parametrize("papel", ["service_role", None])
def test_update_na_trilha_falha_no_banco(banco, caso_com_trilha, papel):
    r = banco.sql(f"UPDATE conduta_trilha SET acao = 'outra' WHERE caso_id = '{caso_com_trilha}';", papel=papel)
    assert r.returncode != 0
    assert "imutável" in r.stderr
    assert banco.ok(f"SELECT acao FROM conduta_trilha WHERE caso_id = '{caso_com_trilha}';") == "leitura"


@pytest.mark.parametrize("papel", ["service_role", None])
def test_delete_na_trilha_falha_no_banco(banco, caso_com_trilha, papel):
    r = banco.sql(f"DELETE FROM conduta_trilha WHERE caso_id = '{caso_com_trilha}';", papel=papel)
    assert r.returncode != 0
    assert "imutável" in r.stderr
    assert banco.ok(f"SELECT count(*) FROM conduta_trilha WHERE caso_id = '{caso_com_trilha}';") == "1"


def test_truncate_na_trilha_falha_no_banco(banco, caso_com_trilha):
    r = banco.sql("TRUNCATE conduta_trilha CASCADE;")
    assert r.returncode != 0
    assert "imutável" in r.stderr


def test_a_linha_nova_tem_que_apontar_para_a_ultima_do_caso(banco):
    caso = _caso(banco, "CC-CADE-IA01")
    assert _linha(banco, caso, CODIGO_A, None).returncode == 0
    assert _linha(banco, caso, CODIGO_B, CODIGO_A).returncode == 0

    # Aponta para a primeira, e não para a última: é uma bifurcação.
    recusada = _linha(banco, caso, CODIGO_C, CODIGO_A)
    assert recusada.returncode != 0
    assert "cadeia" in recusada.stderr
    # Começar de novo do zero num caso que já tem trilha também é recusado.
    assert _linha(banco, caso, CODIGO_C, None).returncode != 0
    assert _linha(banco, caso, CODIGO_C, CODIGO_B).returncode == 0


def test_cada_caso_tem_a_propria_cadeia(banco):
    outro = _caso(banco, "CC-CADE-IA02")
    assert _linha(banco, outro, "d" * 64, None).returncode == 0


# ── Protocolo e conteúdo ────────────────────────────────────────────────────


def test_o_protocolo_nao_vem_de_sequencia(banco):
    padrao = banco.ok(
        "SELECT coalesce(column_default, '') FROM information_schema.columns "
        "WHERE table_name = 'conduta_casos' AND column_name = 'protocolo';"
    )
    assert padrao == ""
    assert "SEQUENCE" not in MIGRATION.read_text(encoding="utf-8").upper()


def test_a_numeracao_da_ouvidoria_nao_e_tocada(banco):
    assert banco.ok("SELECT last_value FROM ouvidoria_protocolo_seq;") == "41"
    sem_comentarios = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert "ouvidoria" not in sem_comentarios.lower()


def test_o_banco_recusa_relato_sem_a_marca_da_cifra(banco):
    r = banco.sql(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado) "
        "VALUES ('CC-CLAR-O001', 'hash', 'relato em claro');",
        papel="service_role",
    )
    assert r.returncode != 0


# ── Comitê, perfil e Produto ────────────────────────────────────────────────


def test_o_comite_nasce_sem_nenhuma_pessoa(banco):
    assert banco.ok("SELECT nome FROM colegiados WHERE slug = 'conduta';") == "Comitê de Conduta"
    sql = MIGRATION.read_text(encoding="utf-8")
    assert re.search(r"INSERT INTO (participacoes|participantes)", sql, re.IGNORECASE) is None


def test_a_participacao_aceita_a_coordenacao(banco):
    banco.ok(
        "INSERT INTO participacoes (colegiado_id, participante_id, papel, vigencia_inicio, vigencia_fim) "
        "SELECT id, 'P1', 'coordenacao', current_date, current_date + 700 FROM colegiados WHERE slug = 'conduta';"
    )


def test_o_perfil_do_modulo_so_aceita_o_cadastro_de_membros(banco):
    banco.ok("UPDATE participantes SET perfil_conduta = 'cadastro_de_membros' WHERE id = 'P1';")
    assert banco.sql("UPDATE participantes SET perfil_conduta = 'tudo' WHERE id = 'P1';").returncode != 0


def test_o_produto_entra_uma_vez_na_aba_tecnologia(banco):
    assert banco.ok("SELECT count(*) FROM tecnologia_produtos WHERE nome = 'Canal de Conduta';") == "1"


def test_o_recibo_e_o_175(banco):
    assert banco.ok("SELECT max(numero) FROM migracoes_aplicadas;") == "175"
