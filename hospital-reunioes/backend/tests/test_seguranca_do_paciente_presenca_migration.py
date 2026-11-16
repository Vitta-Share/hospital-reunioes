"""A migration 153: presença, quórum e reunião não instalada (issue #1774).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere: a
situação NAO_INSTALADA entra sem derrubar nenhuma das de antes, a reunião
reagendada aponta para a original, a presença nasce com as quatro situações,
uma linha por pessoa, RLS e nenhuma política, e nenhuma pessoa entra por
migration (decisão 12).
"""

from __future__ import annotations

import re
from pathlib import Path

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION = PASTA / "153_nsp_presenca_e_quorum.sql"


def _sem_comentario(texto: str) -> str:
    return re.sub(r"--[^\n]*", "", texto)


def _sql() -> str:
    return _sem_comentario(MIGRATION.read_text(encoding="utf-8"))


def _situacoes(sql: str) -> set[str]:
    bloco = re.findall(r"reunioes_status_ata_check\s+CHECK \(status_ata IN \((.*?)\)\)", sql, re.DOTALL)
    assert bloco
    return set(re.findall(r"'(\w+)'", bloco[-1]))


def test_nao_instalada_entra_sem_derrubar_nenhuma_situacao_de_antes():
    antes = _situacoes(_sem_comentario((PASTA / "040_add_aprovada_status.sql").read_text(encoding="utf-8")))

    assert _situacoes(_sql()) == antes | {"NAO_INSTALADA"}


def test_a_reagendada_aponta_para_a_original():
    assert re.search(r"ADD COLUMN IF NOT EXISTS reagendada_de VARCHAR\(20\) REFERENCES reunioes\(id_reuniao\)", _sql())


def test_a_presenca_nasce_com_as_quatro_situacoes_e_uma_linha_por_pessoa():
    corpo = re.search(r"CREATE TABLE IF NOT EXISTS reuniao_presencas\s*\((.*?)\n\);", _sql(), re.DOTALL)
    assert corpo
    assert set(re.findall(r"'(\w+)'", corpo.group(1))) == {"presente", "ausente", "ausente_justificado", "convidado"}
    assert "UNIQUE (id_reuniao, participante_id)" in corpo.group(1)


def test_a_presenca_nasce_com_rls_e_sem_politica():
    assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql()) == ["reuniao_presencas"]
    assert "ALTER TABLE reuniao_presencas ENABLE ROW LEVEL SECURITY;" in _sql()
    assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None


def test_nenhuma_pessoa_na_migration():
    assert re.search(r"INSERT INTO (participacoes|participantes|reuniao_presencas)\b", _sql(), re.IGNORECASE) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_o_recibo_e_o_153():
    assert (
        _sql()
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (153) ON CONFLICT (numero) DO NOTHING;")
    )
