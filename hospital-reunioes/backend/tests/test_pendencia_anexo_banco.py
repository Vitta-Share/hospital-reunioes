"""O anexo da conclusão e a migration 174 num Postgres de verdade (issue #1865).

Sobe um Postgres descartável como o teste da 169, aplica a 169 e a 174 (a 174
duas vezes) e prova no banco que:

- o bucket `anexos-pendencias` nasce privado, com o teto de 10 MB e só imagem
  e PDF, mesmo se alguém o criou aberto à mão;
- a conclusão com anexo grava a Pendência, o evento e o anexo juntos, e o
  anexo fica ligado ao evento de conclusão;
- a conclusão recusada não deixa anexo nenhum;
- a tabela dos anexos e a função de gravação não abrem para `anon`.

Sem `initdb` na máquina o teste pula; no CI ele falha.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from test_pendencia_historico_banco import (  # noqa: E402
    ESQUEMA_ANTERIOR,
    _bin_do_postgres,
    _Postgres,
)
from test_pendencia_historico_banco import MIGRATION as MIGRATION_169  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "174_anexo_da_conclusao_da_pendencia.sql"

# O mínimo do schema `storage` do Supabase que a 174 toca.
STORAGE = """
CREATE SCHEMA storage;
CREATE TABLE storage.buckets (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  public BOOLEAN DEFAULT false,
  file_size_limit BIGINT,
  allowed_mime_types TEXT[]
);
CREATE TABLE storage.objects (id UUID PRIMARY KEY, bucket_id TEXT);
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;
-- O bucket criado aberto à mão no Studio, com a policy que o abriria.
INSERT INTO storage.buckets (id, name, public) VALUES ('anexos-pendencias', 'anexos-pendencias', true);
CREATE POLICY "Authenticated Access anexos-pendencias" ON storage.objects FOR SELECT USING (true);
"""

CARGA = """
INSERT INTO reunioes (id_reuniao) VALUES ('R1');
INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, prazo, status) VALUES
  ('A200', 'R1', 'Comprar luvas', '2026-12-10', 'EM_PROGRESSO'),
  ('A201', 'R1', 'Pintar sala',   '2026-12-10', 'CANCELADO');
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration 174 no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(STORAGE)
        pg.ok(MIGRATION_169.read_text(encoding="utf-8"))
        pg.ok(CARGA)
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _concluir_com_anexo(banco, id_acao: str, status_esperado: str, *, papel="service_role"):
    return banco.sql(
        "SELECT registrar_conclusao_com_anexo("
        f"'{id_acao}', 'entreguei ao setor', 'P01', 'Rita', '{status_esperado}', 'CONCLUIDO', true, false, "
        f"'pendencia-{id_acao}/abc.jpg', 'foto do almoxarifado.jpg', 'image/jpeg', 2048);",
        papel=papel,
    )


def test_o_bucket_e_privado_com_teto_de_10_mb_e_so_imagem_e_pdf(banco):
    linha = banco.ok(
        "SELECT public, file_size_limit, array_to_string(allowed_mime_types, ',') "
        "FROM storage.buckets WHERE id = 'anexos-pendencias';"
    )
    publico, teto, tipos = linha.split("|")
    assert publico == "f"
    assert int(teto) == 10 * 1024 * 1024
    assert set(tipos.split(",")) == {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    policies = banco.ok(
        "SELECT count(*) FROM pg_policies WHERE schemaname = 'storage' "
        "AND policyname = 'Authenticated Access anexos-pendencias';"
    )
    assert policies == "0"


def test_conclusao_com_anexo_grava_o_anexo_ligado_ao_evento_de_conclusao(banco):
    r = _concluir_com_anexo(banco, "A200", "EM_PROGRESSO")
    assert r.returncode == 0, r.stderr

    assert banco.ok("SELECT status FROM pendencias WHERE id_acao = 'A200';") == "CONCLUIDO"
    ligado = banco.ok(
        "SELECT h.comando, a.id_acao, a.nome_original, a.content_type, a.tamanho_bytes "
        "FROM pendencia_anexos a JOIN pendencia_historico h ON h.id = a.evento_id "
        "WHERE a.id_acao = 'A200';"
    )
    assert ligado == "concluir|A200|foto do almoxarifado.jpg|image/jpeg|2048"


def test_conclusao_recusada_nao_deixa_anexo(banco):
    r = _concluir_com_anexo(banco, "A201", "EM_PROGRESSO")

    assert r.returncode != 0
    assert banco.ok("SELECT status FROM pendencias WHERE id_acao = 'A201';") == "CANCELADO"
    assert banco.ok("SELECT count(*) FROM pendencia_anexos WHERE id_acao = 'A201';") == "0"
    assert banco.ok("SELECT count(*) FROM pendencia_historico WHERE id_acao = 'A201';") == "0"


def test_anexos_e_gravacao_nao_abrem_para_anon(banco):
    assert "pendencia_anexos" in MIGRATION.read_text(encoding="utf-8")
    assert banco.ok("SELECT relrowsecurity FROM pg_class WHERE relname = 'pendencia_anexos';") == "t"
    r = banco.sql("SELECT count(*) FROM pendencia_anexos;", papel="anon")
    assert r.returncode != 0
    assert "permission denied" in r.stderr
    r = _concluir_com_anexo(banco, "A200", "CONCLUIDO", papel="anon")
    assert r.returncode != 0
    assert "permission denied" in r.stderr
