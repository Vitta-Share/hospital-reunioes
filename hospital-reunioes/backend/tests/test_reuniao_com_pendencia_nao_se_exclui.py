"""Nada apaga Pendência: Reunião com Pendência não se exclui (issue #1864).

ADR 0098, decisão 6, e decisão 74 da #1757. A Reunião deixava de existir
levando as Pendências junto (a FK era ON DELETE CASCADE) e o super admin
tinha um `DELETE /reunioes/{id}/force` que apagava em qualquer status. Agora a
FK recusa, o force de exclusão sai, e as rotas de exclusão respondem com a
explicação em vez do erro cru do banco. Reunião com todas as Pendências
canceladas também não se exclui (confirmado pelo diretor em 16/11/2026, #1859).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_reunioes import _Banco, _cliente, _pessoa  # noqa: E402

MIGRATION = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "172_pendencia_nao_cai_com_a_reuniao.sql"
)


def _sql_sem_comentarios() -> str:
    return "\n".join(linha.split("--", 1)[0] for linha in MIGRATION.read_text(encoding="utf-8").splitlines())


class TestFkDaPendencia:
    def test_a_fk_da_pendencia_para_a_reuniao_recusa_em_vez_de_apagar(self):
        sql = _sql_sem_comentarios()
        fk = re.search(
            r"ADD\s+CONSTRAINT\s+pendencias_id_reuniao_fkey\s+FOREIGN\s+KEY\s*\(\s*id_reuniao\s*\)\s+"
            r"REFERENCES\s+reunioes\s*\(\s*id_reuniao\s*\)\s+ON\s+DELETE\s+(\w+)",
            sql,
            re.IGNORECASE,
        )
        assert fk, "a migration não recria a FK pendencias.id_reuniao -> reunioes"
        assert fk.group(1).upper() == "RESTRICT"
        # A FK antiga sai seja qual for o nome: a CASCADE não pode sobrar ao lado da nova.
        assert re.search(
            r"conrelid\s*=\s*'public\.pendencias'::regclass.*confrelid\s*=\s*'public\.reunioes'::regclass"
            r".*DROP\s+CONSTRAINT",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert "CASCADE" not in sql.upper()
