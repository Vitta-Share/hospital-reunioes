"""A migration 178 dos membros do Comitê de Conduta num Postgres de verdade (issue #1822).

Sobe um Postgres descartável (o mesmo apoio da migration 169), monta o mínimo
das tabelas de antes, aplica a migration duas vezes e prova no banco:

- a cadeira de segundo leitor e a marcação de diretor na Participação;
- o registro do módulo tem RLS ligada, nenhuma policy e recusa UPDATE,
  DELETE e TRUNCATE, inclusive para a `service_role`;
- o aviso do Comitê entra no sino sem tirar nenhum tipo antigo;
- nenhuma pessoa entra pela migration.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "178_conduta_membros_do_comite.sql"

TIPOS_ANTIGOS_DO_SINO = (
    "MENCAO",
    "STATUS_ALTERADO",
    "COMENTARIO",
    "PRAZO_PROXIMO",
    "RESPONSAVEL_ATRIBUIDO",
    "ACEITE_INTERNO",
    "CONTAS_MEDICAS",
    "TECNOLOGIA",
)

# O mínimo de antes da 178 (migrations 001, 008, 129, 146, 150 e 175).
ESQUEMA_ANTERIOR = """
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN NOSUPERUSER BYPASSRLS;

CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);
CREATE TABLE participantes (id VARCHAR(10) PRIMARY KEY, nome_completo TEXT);
CREATE TABLE colegiados (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL
);
CREATE TABLE participacoes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  colegiado_id UUID NOT NULL REFERENCES colegiados(id),
  participante_id VARCHAR(10) NOT NULL REFERENCES participantes(id),
  papel TEXT NOT NULL,
  vigencia_inicio DATE NOT NULL,
  vigencia_fim DATE NOT NULL,
  CONSTRAINT participacoes_papel_check CHECK (papel IN ('presidencia', 'suplente', 'membro', 'coordenacao'))
);
CREATE TABLE notificacoes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  destinatario_id VARCHAR(10) NOT NULL REFERENCES participantes(id),
  tipo TEXT NOT NULL,
  titulo TEXT NOT NULL,
  CONSTRAINT notificacoes_tipo_check CHECK (tipo IN (
    'MENCAO', 'STATUS_ALTERADO', 'COMENTARIO', 'PRAZO_PROXIMO', 'RESPONSAVEL_ATRIBUIDO',
    'ACEITE_INTERNO', 'CONTAS_MEDICAS', 'TECNOLOGIA'
  ))
);

INSERT INTO participantes (id, nome_completo) VALUES ('P1', 'Pessoa de Teste'), ('P2', 'Outra Pessoa');
INSERT INTO colegiados (slug, nome) VALUES ('nsp', 'Núcleo de Segurança do Paciente'), ('conduta', 'Comitê de Conduta');

GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar o registro no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54178"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _participacao(banco, pid: str, papel: str, diretor: str | None = None):
    coluna, valor = (", e_diretor", f", {diretor}") if diretor else ("", "")
    return banco.sql(
        f"INSERT INTO participacoes (colegiado_id, participante_id, papel, vigencia_inicio, vigencia_fim{coluna}) "
        f"SELECT id, '{pid}', '{papel}', current_date, current_date + 729{valor} "
        "FROM colegiados WHERE slug = 'conduta';"
    )


def _registro(banco, acao: str = "inclusao", *, papel="service_role"):
    return banco.sql(
        "INSERT INTO conduta_registro (acao, participante_id, autor_id, detalhe) "
        f"VALUES ('{acao}', 'P1', 'P2', 'Membro');",
        papel=papel,
    )


# ── A Participação ──────────────────────────────────────────────────────────


def test_a_participacao_aceita_o_segundo_leitor(banco):
    r = _participacao(banco, "P1", "segundo_leitor")
    assert r.returncode == 0, r.stderr


def test_a_participacao_segue_recusando_cadeira_inventada(banco):
    assert _participacao(banco, "P1", "relator").returncode != 0


def test_o_membro_nasce_marcado_como_nao_diretor(banco):
    assert _participacao(banco, "P2", "membro").returncode == 0
    assert banco.ok("SELECT e_diretor FROM participacoes WHERE participante_id = 'P2';") == "f"
    assert _participacao(banco, "P2", "suplente", "true").returncode == 0
    assert banco.ok("SELECT count(*) FROM participacoes WHERE e_diretor;") == "1"


# ── O registro do módulo ────────────────────────────────────────────────────


def test_o_registro_tem_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok("SELECT relrowsecurity FROM pg_class WHERE relname = 'conduta_registro';") == "t"
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename = 'conduta_registro';") == "0"


def test_o_registro_guarda_autor_e_data(banco):
    r = _registro(banco, "perfil_dado")
    assert r.returncode == 0, r.stderr
    assert (
        banco.ok(
            "SELECT autor_id, registrado_em IS NOT NULL FROM conduta_registro WHERE acao = 'perfil_dado';"
        ).replace(" ", "")
        == "P2|t"
    )


def test_o_registro_recusa_acao_desconhecida(banco):
    assert _registro(banco, "qualquer").returncode != 0


@pytest.mark.parametrize("papel", ["service_role", None])
def test_o_registro_nao_se_altera_nem_se_apaga(banco, papel):
    assert _registro(banco, "encerramento").returncode == 0
    antes = banco.ok("SELECT count(*) FROM conduta_registro;")
    update = banco.sql("UPDATE conduta_registro SET detalhe = 'outro';", papel=papel)
    delete = banco.sql("DELETE FROM conduta_registro;", papel=papel)
    assert update.returncode != 0 and "imutável" in update.stderr
    assert delete.returncode != 0 and "imutável" in delete.stderr
    assert banco.ok("SELECT count(*) FROM conduta_registro;") == antes


def test_o_registro_nao_aceita_truncate(banco):
    r = banco.sql("TRUNCATE conduta_registro;")
    assert r.returncode != 0 and "imutável" in r.stderr


# ── O sino ──────────────────────────────────────────────────────────────────


def test_o_sino_aceita_o_aviso_do_comite_e_os_tipos_antigos(banco):
    for tipo in (*TIPOS_ANTIGOS_DO_SINO, "CONDUTA"):
        r = banco.sql(f"INSERT INTO notificacoes (destinatario_id, tipo, titulo) VALUES ('P1', '{tipo}', 't');")
        assert r.returncode == 0, (tipo, r.stderr)


# ── Nenhuma pessoa por migration ou seed ────────────────────────────────────


def _sem_comentarios(caminho: Path) -> str:
    return re.sub(r"--[^\n]*", "", caminho.read_text(encoding="utf-8"))


def test_nenhuma_migration_do_canal_poe_pessoa_no_comite():
    """Os membros entram pela tela. Nenhuma migration do Canal insere pessoa,
    Participação ou perfil, e nenhuma dá o perfil de cadastro a alguém."""
    do_canal = sorted(MIGRATIONS.glob("*conduta*.sql"))
    assert MIGRATION in do_canal
    for caminho in do_canal:
        sql = _sem_comentarios(caminho)
        assert re.search(r"INSERT\s+INTO\s+(participacoes|participantes)\b", sql, re.IGNORECASE) is None, caminho
        assert re.search(r"perfil_conduta\s*=", sql, re.IGNORECASE) is None, caminho


def test_o_seed_nao_poe_ninguem_no_comite():
    seed = (MIGRATIONS.parent / "seed.sql").read_text(encoding="utf-8").lower()
    assert "conduta" not in seed


def test_o_recibo_e_o_178(banco):
    assert banco.ok("SELECT max(numero) FROM migracoes_aplicadas;") == "178"
