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

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "172_pendencia_nao_cai_com_a_reuniao.sql"


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


# ─── As rotas de exclusão ────────────────────────────────────────────────────

SUPER_ADMIN = _pessoa("SA1", access_profile="super_admin", is_super_admin=True)
REUNIAO = "RD_PROG_01"
OUTRA = "RD_PROG_02"

RECUSA = (
    "Esta reunião não pode ser excluída porque já tem pendências, mesmo que canceladas. "
    "As pendências e o histórico delas ficam guardados; para tirar uma pendência da cobrança, "
    "cancele-a com uma anotação."
)


def _reuniao(rid: str) -> dict:
    return {
        "id_reuniao": rid,
        "data": "2026-11-20",
        "titulo": f"Reunião {rid}",
        "status_ata": "PROGRAMADA",
        "facilitador_id": "SA1",
        "criada_por": "SA1",
        "colegiado_id": None,
        "id_grupo_recorrencia": "SERIE1",
        "deleted_at": None,
    }


def _pendencia(pid: str, rid: str, status: str) -> dict:
    return {"id_acao": pid, "id_reuniao": rid, "status": status, "deleted_at": None}


def _banco(*pendencias: dict) -> _Banco:
    return _Banco(
        {
            "participantes": [dict(SUPER_ADMIN)],
            "reunioes": [_reuniao(REUNIAO), _reuniao(OUTRA)],
            "pendencias": [dict(p) for p in pendencias],
        }
    )


def _ids_das_reunioes(banco: _Banco) -> set[str]:
    return {r["id_reuniao"] for r in banco.tabelas["reunioes"]}


class TestExcluirReuniao:
    def test_reuniao_com_pendencia_toda_cancelada_nao_se_exclui_e_a_tela_recebe_o_motivo(self):
        banco = _banco(_pendencia("PEND_1", REUNIAO, "CANCELADO"), _pendencia("PEND_2", REUNIAO, "CANCELADO"))

        resposta = _cliente(SUPER_ADMIN, banco).delete(f"/api/reunioes/{REUNIAO}")

        assert resposta.status_code == 409, resposta.text
        assert resposta.json() == {"detail": RECUSA}
        assert _ids_das_reunioes(banco) == {REUNIAO, OUTRA}

    def test_reuniao_sem_pendencia_continua_se_excluindo(self):
        banco = _banco(_pendencia("PEND_1", OUTRA, "PENDENTE"))

        resposta = _cliente(SUPER_ADMIN, banco).delete(f"/api/reunioes/{REUNIAO}")

        assert resposta.status_code == 200, resposta.text
        assert _ids_das_reunioes(banco) == {OUTRA}

    def test_serie_com_uma_reuniao_com_pendencia_nao_se_exclui_e_nada_sai(self):
        banco = _banco(_pendencia("PEND_1", OUTRA, "CANCELADO"))

        resposta = _cliente(SUPER_ADMIN, banco).delete("/api/reunioes/grupo/SERIE1")

        assert resposta.status_code == 409, resposta.text
        assert resposta.json() == {
            "detail": "A exclusão do grupo foi bloqueada: 1 reunião(ões) desta série já têm pendências, "
            "mesmo que canceladas, e as pendências ficam guardadas."
        }
        assert _ids_das_reunioes(banco) == {REUNIAO, OUTRA}

    def test_serie_sem_pendencia_continua_se_excluindo(self):
        banco = _banco()

        resposta = _cliente(SUPER_ADMIN, banco).delete("/api/reunioes/grupo/SERIE1")

        assert resposta.status_code == 200, resposta.text
        assert _ids_das_reunioes(banco) == set()
