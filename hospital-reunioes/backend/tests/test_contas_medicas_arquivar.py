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
        assert re.search(r"arquivada_por VARCHAR\(10\) REFERENCES participantes\(id\) ON DELETE SET NULL;", sql), (
            "a pessoa que arquivou sai com ON DELETE SET NULL"
        )
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
        conta = {
            "periodo_inicio": "2026-09-28",
            "periodo_fim": "2026-10-03",
            "concluida_em": "2026-11-04T13:00:00+00:00",
        }

        assert competencia(conta) == "2026-10"

    def test_sem_periodo_e_o_mes_da_conclusao_no_fuso_do_hospital_na_virada_do_mes(self):
        """Concluída às 22h de 31 de outubro em Bangu: no UTC já é 1º de novembro."""
        conta = {"periodo_inicio": None, "periodo_fim": None, "concluida_em": "2026-11-01T01:00:00+00:00"}

        assert competencia(conta) == "2026-10"

    def test_sem_periodo_nem_conclusao_nao_tem_competencia(self):
        assert competencia({"periodo_fim": None, "concluida_em": None}) is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. As Concluídas por Competência
# ═══════════════════════════════════════════════════════════════════════════

ARQUIVADA_EM = "2026-11-10T12:00:00+00:00"


def _concluida(id_: str, ordem: int, fim: str | None, faturista="F1", situacao="CONCLUIDA", **campos) -> dict:
    return _c(
        id_,
        situacao,
        ordem,
        faturista=faturista,
        periodo_inicio=fim and fim[:8] + "01",
        periodo_fim=fim,
        concluida_em="2026-11-05T15:00:00+00:00",
        **campos,
    )


def _esteira_com_arquivadas():
    """Concluídas de outubro e de novembro, de F1 e de F2. A "out-arquivada"
    já saiu da Esteira; a "sem-periodo" cai no mês da conclusão (novembro)."""
    contas = [
        _concluida("out-f1", 1, "2026-10-20"),
        _concluida("out-f2-pendencia", 2, "2026-10-28", faturista="F2", situacao="CONCLUIDA_COM_PENDENCIA"),
        _concluida("out-arquivada", 3, "2026-10-15", arquivada_em=ARQUIVADA_EM, arquivada_por="F1"),
        _concluida("nov-f1", 4, "2026-11-02"),
        _concluida("sem-periodo", 5, None, faturista="F2"),
        _c("em-correcao", "EM_CORRECAO", 6, faturista="F1"),
    ]
    atendimentos = [{"id": c["atendimento_id"], "numero_atendimento": f"40{n:03d}"} for n, c in enumerate(contas)]
    return _cenario(cm_conta=contas, cm_atendimento=atendimentos)


def _conta(banco, id_: str) -> dict:
    return next(c for c in banco.tabelas["cm_conta"] if c["id"] == id_)


class TestAsConcluidasPorCompetencia:
    def test_vem_sem_as_arquivadas_cada_uma_com_a_competencia(self):
        corpo = _cliente("faturista", _esteira_com_arquivadas()).get(ROTA_FILA).json()

        assert [(c["id"], c["competencia"]) for c in corpo["concluidas"]] == [
            ("sem-periodo", "2026-11"),
            ("nov-f1", "2026-11"),
            ("out-f2-pendencia", "2026-10"),
            ("out-f1", "2026-10"),
        ]

    def test_a_contagem_das_concluidas_nao_conta_as_arquivadas_e_a_das_arquivadas_conta(self):
        corpo = _cliente("faturista", _esteira_com_arquivadas()).get(ROTA_FILA).json()

        assert corpo["contagem"]["concluidas"] == 4
        assert corpo["contagem"]["arquivadas"] == 1
        assert corpo["contagem_minhas"]["concluidas"] == 2

    def test_sem_o_teto_das_100_mais_recentes_mesmo_com_o_max_rows_do_banco(self):
        banco = _esteira_com_arquivadas()
        banco.tabelas["cm_conta"] += [
            _concluida(f"muitas-{n}", 100 + n, "2026-09-10", faturista="F2") for n in range(150)
        ]
        banco.max_rows = 100

        corpo = _cliente("faturista", banco).get(ROTA_FILA).json()

        assert len(corpo["concluidas"]) == 154

    def test_a_lista_sem_teto_le_os_dados_de_cada_conta_em_lotes_que_cabem_na_url(self):
        """Centenas de UUIDs num `in_` estouram o header do proxy: sem o teto da
        lista, os atendimentos, as linhas e os prontuários vêm em lotes."""
        banco = _esteira_com_arquivadas()
        novas = [_concluida(f"muitas-{n}", 100 + n, "2026-09-10", faturista="F2") for n in range(250)]
        banco.tabelas["cm_conta"] += novas
        banco.tabelas["cm_atendimento"] += [
            {"id": c["atendimento_id"], "numero_atendimento": f"5{n:04d}"} for n, c in enumerate(novas)
        ]
        banco.teto_do_in = 100

        resposta = _cliente("faturista", banco).get(ROTA_FILA)

        assert resposta.status_code == 200, resposta.text
        numeros = {c["id"]: c["numero_atendimento"] for c in resposta.json()["concluidas"]}
        assert numeros["muitas-249"] == "50249"
