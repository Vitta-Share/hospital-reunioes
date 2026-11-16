"""A migration 160: a ata do Núcleo assinada nos Documentos (issue #1776).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere: a
coluna que o serviço grava existe e é única (o encerramento repetido não
duplica a ata), nenhuma tabela nem policy nova, nenhuma pessoa entra por
migration, e o recibo é o 160.
"""

from __future__ import annotations

import re
from pathlib import Path

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION = PASTA / "160_nsp_ata_assinada.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def test_a_ata_assinada_aponta_para_a_reuniao_uma_vez_so():
    assert re.search(
        r"ALTER TABLE nsp_documentos\s+ADD COLUMN IF NOT EXISTS reuniao_id VARCHAR\(20\) UNIQUE "
        r"REFERENCES reunioes\(id_reuniao\) ON DELETE RESTRICT;",
        _sql(),
    )


def test_nenhuma_tabela_nem_policy_nova():
    assert re.search(r"CREATE\s+TABLE", _sql(), re.IGNORECASE) is None
    assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None


def test_nenhuma_pessoa_na_migration():
    assert re.search(r"INSERT INTO (participacoes|participantes|nsp_documentos)\b", _sql(), re.IGNORECASE) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_o_recibo_e_o_160():
    assert (
        _sql()
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (160) ON CONFLICT (numero) DO NOTHING;")
    )
