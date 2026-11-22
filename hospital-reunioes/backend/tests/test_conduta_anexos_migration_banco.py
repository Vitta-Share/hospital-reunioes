"""A migration 233 num Postgres de verdade (issue #1844).

Sobe um Postgres descartável (o mesmo apoio da migration 175), aplica a 175 e
a 233 duas vezes e prova no banco que a tabela dos anexos não tem onde guardar
o nome original do arquivo, que o anexo não muda nem se apaga e que só o
backend lê.

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

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "233_conduta_anexos_do_relato.sql"
INTEGRIDADE = "a" * 64


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration 233 no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54233"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        pg.ok(
            "INSERT INTO conduta_casos (id, protocolo, codigo_hash, relato_cifrado) "
            "VALUES ('00000000-0000-0000-0000-000000001844', 'CC-AAAA-1844', 'hash', 'v1:AAAA');",
            papel="service_role",
        )
        yield pg
    finally:
        pg.descer()


def _anexo(banco, caminho: str, tipo: str = "imagem", papel: str | None = "service_role"):
    return banco.sql(
        "INSERT INTO conduta_relato_anexos "
        "(caso_id, tipo, content_type, tamanho_bytes, storage_path, codigo_integridade) "
        f"VALUES ('00000000-0000-0000-0000-000000001844', '{tipo}', 'image/jpeg', 10, '{caminho}', '{INTEGRIDADE}') "
        "RETURNING id;",
        papel=papel,
    )


def test_o_anexo_do_relato_entra_pelo_backend(banco):
    gravado = _anexo(banco, "anexos/um")

    assert gravado.returncode == 0, gravado.stderr


def test_a_tabela_nao_tem_coluna_para_o_nome_do_arquivo(banco):
    colunas = banco.ok(
        "SELECT string_agg(column_name, ',') FROM information_schema.columns "
        "WHERE table_name = 'conduta_relato_anexos';"
    )

    assert "storage_path" in colunas, "controle: a consulta acha as colunas da tabela"
    assert "nome" not in colunas
    assert "filename" not in colunas


def test_so_imagem_pdf_e_audio(banco):
    video = _anexo(banco, "anexos/video", tipo="video")

    assert video.returncode != 0
    assert "conduta_relato_anexos_tipo_check" in video.stderr


@pytest.mark.parametrize(
    "comando", ["UPDATE conduta_relato_anexos SET tamanho_bytes = 1", "DELETE FROM conduta_relato_anexos"]
)
def test_o_anexo_guardado_nao_muda_nem_se_apaga(banco, comando):
    _anexo(banco, f"anexos/{len(comando)}")

    recusado = banco.sql(f"{comando};", papel="service_role")

    assert recusado.returncode != 0
    assert "O anexo do relato fica guardado" in recusado.stderr


def test_so_o_backend_le_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok("SELECT relrowsecurity FROM pg_class WHERE relname = 'conduta_relato_anexos';") == "t"
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename = 'conduta_relato_anexos';") == "0"


def test_o_recibo_e_o_233(banco):
    assert banco.ok("SELECT count(*) FROM migracoes_aplicadas WHERE numero = 233;") == "1"
