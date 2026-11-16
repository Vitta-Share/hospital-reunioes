"""A migration 150: os membros do Núcleo (issue #1766, ADR 0095).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere: a
Participação ganha área e encerramento, a trilha nasce com RLS e sem política,
o banco recusa apagar Participação e mexer na trilha, e nenhuma pessoa entra
por migration (decisão 12).
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "150_nsp_membros.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def test_a_participacao_ganha_area_e_encerramento():
    for coluna in ("area", "encerrada_em"):
        assert re.search(rf"ALTER TABLE participacoes\s+ADD COLUMN IF NOT EXISTS {coluna}\b", _sql()), coluna


def test_a_trilha_nasce_com_rls_e_sem_politica():
    assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql()) == ["participacoes_trilha"]
    assert "ALTER TABLE participacoes_trilha ENABLE ROW LEVEL SECURITY;" in _sql()
    assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None


def test_a_trilha_guarda_autor_campo_e_os_dois_valores():
    corpo = re.search(r"CREATE TABLE IF NOT EXISTS participacoes_trilha\s*\((.*?)\n\);", _sql(), re.DOTALL)
    assert corpo
    for coluna in ("participacao_id", "autor_id", "acao", "campo", "valor_anterior", "valor_novo", "created_at"):
        assert re.search(rf"^\s*{coluna}\s", corpo.group(1), re.MULTILINE), coluna


def test_o_banco_recusa_apagar_participacao():
    """Mutante: tirar a trigger de DELETE em participacoes."""
    assert re.search(r"BEFORE DELETE ON participacoes\s", _sql())


def test_a_trilha_nao_aceita_update_nem_delete():
    assert re.search(r"BEFORE UPDATE OR DELETE ON participacoes_trilha\s", _sql())


def test_uma_participacao_aberta_por_pessoa_no_colegiado():
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON participacoes\s*\(colegiado_id, participante_id\)\s+"
        r"WHERE encerrada_em IS NULL",
        _sql(),
    )


def test_nenhuma_pessoa_na_migration():
    assert re.search(r"INSERT INTO (participacoes|participantes)\b", _sql(), re.IGNORECASE) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_o_recibo_e_o_150():
    assert (
        _sql()
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (150) ON CONFLICT (numero) DO NOTHING;")
    )
