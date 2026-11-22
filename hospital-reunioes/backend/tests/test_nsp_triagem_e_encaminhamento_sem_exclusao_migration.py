"""A migration 225: triagem e encaminhamento do Núcleo não se apagam (issue #2153, PRD #1979).

Lida como texto, do arquivo que o humano cola no Studio, no molde de
`test_delete_na_notificacao_e_recusado_pelo_banco`. Cada tabela é conferida
pela sua própria regex: o par função com `RAISE EXCEPTION` e trigger
`BEFORE DELETE ... FOR EACH ROW` de uma não cobre a outra. A prova contra o
banco real é a conferência em `pg_trigger` depois de aplicar a migration.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "225_nsp_triagem_e_encaminhamento_sem_exclusao.sql"
)


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _funcao(nome: str) -> str:
    bloco = re.search(rf"CREATE OR REPLACE FUNCTION {nome}\(\).*?\$\$(.*?)\$\$", _sql(), re.DOTALL)
    assert bloco, nome
    return bloco.group(1)


@pytest.mark.parametrize("tabela", ["nsp_triagens", "nsp_encaminhamentos"])
def test_delete_na_triagem_e_no_encaminhamento_e_recusado_pelo_banco(tabela):
    assert re.search(
        r"RAISE EXCEPTION '[^']+'\s+USING ERRCODE = 'check_violation';",
        _funcao(f"{tabela}_sem_exclusao"),
    ), tabela
    assert re.search(
        rf"DROP TRIGGER IF EXISTS trg_{tabela}_sem_exclusao ON {tabela};\s*"
        rf"CREATE TRIGGER trg_{tabela}_sem_exclusao\s+"
        rf"BEFORE DELETE ON {tabela}\s+"
        rf"FOR EACH ROW EXECUTE FUNCTION {tabela}_sem_exclusao\(\)",
        _sql(),
    ), tabela
