"""A migration 228: a formação do instrutor na capacitação (issue #1927).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere é o
que a issue promete: uma coluna nova em `nsp_capacitacoes`, nula para as
capacitações já cadastradas (a regra de "obrigatória nas novas" é do backend),
com o mesmo teto de 200 caracteres do nome do instrutor quando preenchida, e
nenhuma linha existente alterada.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "228_nsp_capacitacao_formacao_do_instrutor.sql"
)


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _coluna() -> str:
    achada = re.search(
        r"ALTER TABLE nsp_capacitacoes\s+ADD COLUMN IF NOT EXISTS instrutor_formacao\s+([^;]*);",
        _sql(),
    )
    assert achada, "a coluna instrutor_formacao não entra em nsp_capacitacoes"
    return achada.group(1)


def test_a_coluna_nova_entra_em_nsp_capacitacoes():
    assert _coluna().startswith("TEXT")


def test_a_coluna_nasce_nula_para_as_capacitacoes_antigas():
    """Mutante: NOT NULL, que recusaria toda capacitação já cadastrada."""
    assert "NOT NULL" not in _coluna().upper()
    assert "DEFAULT" not in _coluna().upper()


def test_preenchida_vai_de_1_a_200_caracteres():
    assert re.search(
        r"CHECK\s*\(\s*instrutor_formacao IS NULL OR char_length\(btrim\(instrutor_formacao\)\) BETWEEN 1 AND 200\s*\)",
        _coluna(),
    )


def test_nenhuma_linha_existente_e_alterada():
    assert re.search(r"\b(UPDATE|DELETE|INSERT INTO nsp_)", _sql(), re.IGNORECASE) is None


def test_o_recibo_e_o_228():
    assert "INSERT INTO migracoes_aplicadas (numero) VALUES (228) ON CONFLICT (numero) DO NOTHING;" in _sql()
