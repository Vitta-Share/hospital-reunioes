"""A migration 173: o registro de e-mail do Núcleo, com retentativa (issue #1985).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere: o
banco aceita os marcos e as situações que o serviço grava, a linha ganha o
caso, as tentativas e a próxima tentativa, a Participação deixa de ser
obrigatória sem deixar a linha órfã, e nenhuma pessoa entra por migration.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.seguranca_do_paciente import avisos, convocacao, emails  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "173_nsp_registro_de_email.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _check(nome: str) -> set[str]:
    bloco = re.search(rf"ADD CONSTRAINT {nome}\s+CHECK \((.*?)\);", _sql(), re.DOTALL)
    assert bloco, nome
    return set(re.findall(r"'(\w+)'", bloco.group(1)))


def test_o_banco_aceita_os_marcos_dos_avisos_e_da_convocacao():
    assert _check("nsp_avisos_marco_check") == set(avisos.DESTINATARIOS) | {convocacao.MARCO}


def test_o_banco_aceita_as_situacoes_do_registro():
    assert _check("nsp_avisos_situacao_check") == {emails.PENDENTE, emails.ENVIANDO, emails.ENVIADO, emails.FALHOU}


def test_a_linha_ganha_caso_urgencia_tentativas_e_a_proxima_tentativa():
    sql = _sql()
    for coluna, tipo in (
        ("caso_id", "UUID"),
        ("urgente", "BOOLEAN NOT NULL DEFAULT false"),
        ("tentativas", "SMALLINT NOT NULL DEFAULT 0"),
        ("enviar_a_partir_de", "TIMESTAMPTZ"),
        ("assunto", "TEXT"),
        ("texto", "TEXT"),
        ("modelo", "TEXT"),
        ("contexto", "JSONB"),
    ):
        assert re.search(rf"ADD COLUMN IF NOT EXISTS {coluna}\s+{tipo}", sql), coluna


def test_a_participacao_vira_opcional_mas_a_linha_tem_dono():
    sql = _sql()
    assert "ALTER COLUMN participacao_id DROP NOT NULL" in sql
    assert re.search(r"CHECK \(participacao_id IS NOT NULL OR caso_id IS NOT NULL\)", sql)
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON nsp_avisos \(caso_id, marco, referencia, destinatario_id\)"
        r"\s+WHERE participacao_id IS NULL",
        sql,
    )


def test_o_modelo_do_banco_e_o_mesmo_que_o_servico_aceita():
    assert "modelo ~ '^email_nsp_[a-z_]+\\.html$'" in _sql()
    assert emails._MODELO.pattern == r"^email_nsp_[a-z_]+\.html$"


def test_nenhuma_tabela_nova_nem_politica_nem_pessoa():
    sql = _sql()
    assert re.search(r"CREATE TABLE", sql, re.IGNORECASE) is None
    assert re.search(r"CREATE\s+POLICY", sql, re.IGNORECASE) is None
    assert re.search(r"INSERT INTO (participacoes|participantes|nsp_avisos)\b", sql, re.IGNORECASE) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_o_recibo_e_o_173():
    assert (
        _sql()
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (173) ON CONFLICT (numero) DO NOTHING;")
    )
