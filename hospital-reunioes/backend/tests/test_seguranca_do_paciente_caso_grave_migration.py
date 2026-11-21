"""A migration 182: o alerta de caso grave e a confirmação de recebimento (issue #1989).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere: o
banco aceita todos os marcos que o serviço grava, os de antes e os dois da
chegada; o destinatário só fica vazio na confirmação de um caso; uma
confirmação por caso; e nenhuma pessoa entra por migration.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.seguranca_do_paciente import avisos, caso_grave, convocacao  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "182_nsp_caso_grave_e_confirmacao.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def test_o_banco_aceita_os_marcos_de_antes_e_os_da_chegada():
    bloco = re.search(r"ADD CONSTRAINT nsp_avisos_marco_check\s+CHECK \((.*?)\);", _sql(), re.DOTALL)
    assert bloco
    assert set(re.findall(r"'(\w+)'", bloco.group(1))) == set(avisos.DESTINATARIOS) | {
        convocacao.MARCO,
        caso_grave.MARCO_DO_ALERTA,
        caso_grave.MARCO_DA_CONFIRMACAO,
    }


def test_o_destinatario_so_fica_vazio_na_confirmacao_de_um_caso():
    sql = _sql()
    assert "ALTER COLUMN destinatario_id DROP NOT NULL" in sql
    assert re.search(
        r"CHECK \(destinatario_id IS NOT NULL OR \(marco = 'confirmacao_de_recebimento' AND caso_id IS NOT NULL\)\)",
        sql,
    )


def test_uma_confirmacao_por_caso():
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS uq_nsp_avisos_confirmacao\s+ON nsp_avisos \(caso_id, marco, referencia\)"
        r"\s+WHERE destinatario_id IS NULL;",
        _sql(),
    )


def test_nenhuma_tabela_nova_nem_politica_nem_pessoa():
    sql = _sql().upper()
    assert "CREATE TABLE" not in sql
    assert "CREATE POLICY" not in sql
    assert "INSERT INTO PARTICIPANTES" not in sql


def test_o_recibo_e_o_182():
    assert (
        MIGRATION.read_text(encoding="utf-8")
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (182) ON CONFLICT (numero) DO NOTHING;")
    )
