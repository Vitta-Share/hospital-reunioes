"""A migration 181: os anexos da Notificação de incidente (issue #1988, PRD #1979).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere:

- os metadados ficam numa tabela à parte, ligada à notificação, sem o nome
  original do arquivo, e só com os tipos e o tamanho que o serviço aceita;
- o banco recusa o quarto anexo da mesma notificação;
- o bucket é privado, com o teto e os tipos no próprio Storage, e sem policy
  para `authenticated`: o arquivo só sai pelo backend;
- a tabela nova nasce com RLS ligado e sem política.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.services.ouvidoria_anexos import TIPOS_PERMITIDOS  # noqa: E402
from app.services.seguranca_do_paciente import anexos  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "181_nsp_anexos_da_notificacao.sql"
TIPOS_DO_SERVICO = {TIPOS_PERMITIDOS[extensao] for extensao in anexos.EXTENSOES_ACEITAS}


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _tabela() -> str:
    bloco = re.search(rf"CREATE TABLE IF NOT EXISTS {anexos.TABELA} \((.*?)\n\);", _sql(), re.DOTALL)
    assert bloco, anexos.TABELA
    return bloco.group(1)


def test_o_anexo_aponta_para_a_notificacao_e_nao_some_com_ela():
    assert re.search(r"notificacao_id\s+UUID NOT NULL REFERENCES nsp_notificacoes\(id\) ON DELETE RESTRICT", _tabela())
    assert re.search(rf"CREATE INDEX IF NOT EXISTS \w+\s+ON {anexos.TABELA} \(notificacao_id", _sql())


def test_o_caminho_no_bucket_e_unico_e_o_nome_original_nao_tem_coluna():
    tabela = _tabela()
    assert re.search(r"storage_path\s+TEXT NOT NULL UNIQUE", tabela)
    for coluna in ("filename", "nome_original", "nome"):
        assert not re.search(rf"\n\s+{coluna}\s", tabela), coluna


def test_o_banco_aceita_so_os_tipos_e_o_tamanho_que_o_servico_aceita():
    tabela = _tabela()
    tipos = re.search(r"content_type\s+TEXT NOT NULL CHECK \(content_type IN \(([^)]*)\)\)", tabela)
    assert tipos
    assert set(re.findall(r"'([^']+)'", tipos.group(1))) == TIPOS_DO_SERVICO
    assert re.search(
        rf"tamanho_bytes\s+BIGINT NOT NULL CHECK \(tamanho_bytes > 0 AND tamanho_bytes < {anexos.LIMITE_DA_SOMA}\)",
        tabela,
    )


def test_o_banco_recusa_o_quarto_anexo_da_mesma_notificacao():
    corpo = re.search(r"CREATE OR REPLACE FUNCTION nsp_notificacao_anexos_ate_tres\(\).*?\$\$(.*?)\$\$", _sql(), re.S)
    assert corpo
    assert re.search(
        rf"SELECT count\(\*\) FROM {anexos.TABELA} WHERE notificacao_id = NEW\.notificacao_id\) >= "
        rf"{anexos.MAXIMO_DE_ARQUIVOS}",
        corpo.group(1),
    )
    assert re.search(
        rf"BEFORE INSERT ON {anexos.TABELA}\s+FOR EACH ROW EXECUTE FUNCTION nsp_notificacao_anexos_ate_tres\(\)",
        _sql(),
    )


def test_o_bucket_e_privado_com_teto_e_tipos_no_storage():
    bucket = settings.supabase_storage_bucket_nsp_anexos
    sql = _sql()
    insercao = re.search(
        rf"INSERT INTO storage\.buckets \(id, name, public, file_size_limit, allowed_mime_types\)\s*"
        rf"VALUES \(\s*'{bucket}', '{bucket}', false, (\d+),\s*ARRAY\[([^\]]*)\]\s*\)\s*"
        rf"ON CONFLICT \(id\) DO UPDATE SET\s*public = false,\s*file_size_limit = (\d+),\s*"
        rf"allowed_mime_types = ARRAY\[([^\]]*)\];",
        sql,
    )
    assert insercao, "o bucket privado sumiu ou mudou de forma"
    assert int(insercao.group(1)) == int(insercao.group(3)) == anexos.LIMITE_DA_SOMA
    assert set(re.findall(r"'([^']+)'", insercao.group(2))) == TIPOS_DO_SERVICO
    assert set(re.findall(r"'([^']+)'", insercao.group(4))) == TIPOS_DO_SERVICO
    assert f'DROP POLICY IF EXISTS "Authenticated Access {bucket}" ON storage.objects;' in sql


def test_rls_ligado_e_nenhuma_politica():
    sql = _sql()
    assert f"ALTER TABLE {anexos.TABELA} ENABLE ROW LEVEL SECURITY;" in sql
    assert f"REVOKE ALL ON {anexos.TABELA} FROM anon, authenticated;" in sql
    assert "CREATE POLICY" not in sql


def test_o_recibo_e_o_da_181():
    assert "INSERT INTO migracoes_aplicadas (numero) VALUES (181) ON CONFLICT (numero) DO NOTHING;" in _sql()
