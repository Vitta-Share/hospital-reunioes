"""Arquivar por Competência e desarquivar em Contas médicas (issue #1958, PRD #1933, ADR 0105).

A conta concluída ganha um carimbo de quando e quem arquivou, e a situação
fica como está (decisão 7). As Concluídas aparecem agrupadas por
Competência, o mês do fim do período da conta (decisão 6), e a etapa
Arquivadas guarda as que saíram da Esteira. A faturista arquiva as dela; quem
tem "painel completo" arquiva qualquer uma e o mês inteiro (decisão 8).

O dublê do banco é o da rota da fila. Os rótulos de paciente e os nomes de
pessoa são inventados.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_contas_medicas_envio import (  # noqa: E402
    ROTA_FILA,
    _c,
    _cenario,
    _cliente,
    _reset_rate_limiter,  # noqa: F401 (fixture autouse do envio)
)

from app.services.contas_medicas.competencia import competencia  # noqa: E402

MIGRATION_176 = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "176_contas_medicas_arquivar_por_competencia.sql"
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. A migration
# ═══════════════════════════════════════════════════════════════════════════


class TestAMigration:
    def test_acrescenta_o_carimbo_com_a_pessoa_set_null_e_o_indice_parcial_e_so_acrescenta(self):
        sql = re.sub(r"--[^\n]*", "", MIGRATION_176.read_text(encoding="utf-8"))

        assert re.findall(r"ALTER TABLE cm_conta\s+ADD COLUMN IF NOT EXISTS (\w+) ([\w()]+)", sql) == [
            ("arquivada_em", "TIMESTAMPTZ"),
            ("arquivada_por", "VARCHAR(10)"),
        ]
        assert re.search(
            r"arquivada_por VARCHAR\(10\) REFERENCES participantes\(id\) ON DELETE SET NULL;", sql
        ), "a pessoa que arquivou sai com ON DELETE SET NULL"
        assert re.search(
            r"CREATE INDEX IF NOT EXISTS \w+\s+ON cm_conta \([^)]*\)\s+WHERE arquivada_em IS NULL;", sql
        ), "falta o índice parcial das não arquivadas"
        # Só acrescenta: nada de DROP, DELETE, UPDATE, ALTER COLUMN nem CHECK novo na situação.
        sem_on_delete = sql.replace("ON DELETE SET NULL", "")
        assert not re.search(r"\b(DROP|DELETE|UPDATE|ALTER COLUMN|RENAME|TRUNCATE)\b", sem_on_delete, flags=re.I)
        assert "situacao_check" not in sql


# ═══════════════════════════════════════════════════════════════════════════
# 2. A Competência
# ═══════════════════════════════════════════════════════════════════════════


class TestACompetencia:
    def test_e_o_mes_do_fim_do_periodo_da_conta(self):
        conta = {"periodo_inicio": "2026-09-28", "periodo_fim": "2026-10-03", "concluida_em": "2026-11-04T13:00:00+00:00"}

        assert competencia(conta) == "2026-10"

    def test_sem_periodo_e_o_mes_da_conclusao_no_fuso_do_hospital_na_virada_do_mes(self):
        """Concluída às 22h de 31 de outubro em Bangu: no UTC já é 1º de novembro."""
        conta = {"periodo_inicio": None, "periodo_fim": None, "concluida_em": "2026-11-01T01:00:00+00:00"}

        assert competencia(conta) == "2026-10"

    def test_sem_periodo_nem_conclusao_nao_tem_competencia(self):
        assert competencia({"periodo_fim": None, "concluida_em": None}) is None
