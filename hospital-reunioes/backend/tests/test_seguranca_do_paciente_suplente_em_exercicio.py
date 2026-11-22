"""O suplente em exercício e a Diretoria nos casos graves (issue #1999, PRD #1979, ADR 0107).

Um bloco por critério de aceite:

1. registrar a ausência da Presidência exige início e fim e grava trilha; só a
   Presidência e o Acesso pleno registram (decisão 4);
2. dentro do período, o suplente confirma a triagem e vê quem notificou; fora
   dele, recebe recusa nas duas coisas;
3. a Diretoria lê os casos das faixas A e B sem quem notificou; C, D, E e
   qualquer edição recebem recusa (decisão 5);
4. cada recusa é afirmada pelo código e pelo corpo da resposta;
5. o texto do Produto no Kit de conhecimento diz o comportamento novo.

A migration é lida como texto, do arquivo que o humano cola no Studio. O banco
das rotas é o dublê em memória dos testes da notificação e da triagem.
Nenhum dado de pessoa real.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import (  # noqa: E402
    DIRETOR,
    DIRETOR_EXECUTIVO,
    HOJE,
    MEMBRO,
    NUCLEO,
    PRESIDENTE,
    SETOR,
    _pessoa,
)
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    GRAVE,
    MODERADO,
    OBITO,
    QUASE_ERRO,
    _BancoDaTriagem,
    _notificacao,
    _sugestao,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_membros as membros_router  # noqa: E402
from app.routers import seguranca_do_paciente_notificacoes as notificacoes_router  # noqa: E402
from app.routers import seguranca_do_paciente_triagem as triagem_router  # noqa: E402

RECUSA = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}
MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "212_nsp_suplente_em_exercicio.sql"

SUPLENTE = _pessoa("P7")
# Faixa D sem dano: a confirmação simples, um clique.
SEM_DANO = {"faixa": "D"}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _participacao(participante: str, papel: str) -> dict[str, Any]:
    return {
        "id": f"part-{participante}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": participante,
        "papel": papel,
        "area": None,
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": (HOJE + timedelta(days=300)).isoformat(),
        "encerrada_em": None,
        "termo_gerado_em": "2026-01-05T12:00:00+00:00",
        "termo_enviado_em": "2026-01-05T12:00:00+00:00",
        "termo_assinado_em": "2026-01-10T12:00:00+00:00",
    }


def _ausencia(inicio, fim) -> dict[str, Any]:
    return {
        "id": f"aus-{inicio}",
        "participacao_id": "part-P7",
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "autor_id": "P1",
    }


def _banco(notificacoes=(), triagens=(), ausencias=()) -> _BancoDaTriagem:
    return _BancoDaTriagem(
        {
            "participantes": [dict(p) for p in (PRESIDENTE, MEMBRO, DIRETOR_EXECUTIVO, DIRETOR, SUPLENTE)],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [
                _participacao("P1", "presidencia"),
                _participacao("P2", "membro"),
                _participacao("P7", "suplente"),
            ],
            "participacoes_trilha": [],
            "setores": [dict(SETOR)],
            "nsp_notificacoes": [dict(n) for n in notificacoes],
            "nsp_triagens": [dict(t) for t in triagens],
            "nsp_notificacoes_anexos": [],
            "nsp_categorias": [{"codigo": "EQP", "nome": "Equipamentos e materiais", "ordem": 11}],
            "nsp_eventos_que_nunca_deveriam_ocorrer": [],
            "nsp_cortes_de_frequencia": [],
            "nsp_ausencias_da_presidencia": [dict(a) for a in ausencias],
        }
    )


def _cliente(banco: _BancoDaTriagem, pessoa: dict[str, Any]) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    for router in (membros_router.router, notificacoes_router.router, triagem_router.router):
        app.include_router(router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Registrar a ausência da Presidência
# ═══════════════════════════════════════════════════════════════════════════

AUSENCIA = "/api/nsp/membros/part-P7/ausencia-da-presidencia"
PERIODO = {"inicio": "2026-12-01", "fim": "2026-12-15"}


@pytest.mark.parametrize("pessoa", [PRESIDENTE, DIRETOR_EXECUTIVO], ids=["Presidência", "Acesso pleno"])
def test_a_presidencia_e_o_acesso_pleno_registram_a_ausencia_com_trilha(pessoa):
    banco = _banco()

    resposta = _cliente(banco, pessoa).post(AUSENCIA, json=PERIODO)

    assert resposta.status_code == 201, resposta.text
    [linha] = banco.tabelas["nsp_ausencias_da_presidencia"]
    assert (linha["participacao_id"], linha["inicio"], linha["fim"], linha["autor_id"]) == (
        "part-P7",
        "2026-12-01",
        "2026-12-15",
        pessoa["id"],
    )
    [trilha] = banco.tabelas["participacoes_trilha"]
    assert trilha["participacao_id"] == "part-P7"
    assert trilha["autor_id"] == pessoa["id"]
    assert trilha["acao"] == "ausencia_da_presidencia"
    assert trilha["valor_novo"] == "de 01/12/2026 a 15/12/2026"
    assert resposta.json()["ausencia"] == {"inicio": "2026-12-01", "fim": "2026-12-15"}


@pytest.mark.parametrize("falta", ["inicio", "fim"])
def test_registrar_a_ausencia_exige_inicio_e_fim(falta):
    banco = _banco()
    corpo = {k: v for k, v in PERIODO.items() if k != falta}

    resposta = _cliente(banco, PRESIDENTE).post(AUSENCIA, json=corpo)

    assert resposta.status_code == 422
    assert resposta.json()["detail"][0]["loc"] == ["body", falta]
    assert banco.tabelas["nsp_ausencias_da_presidencia"] == []
    assert banco.tabelas["participacoes_trilha"] == []


def test_o_fim_da_ausencia_nao_vem_antes_do_inicio():
    banco = _banco()

    resposta = _cliente(banco, PRESIDENTE).post(AUSENCIA, json={"inicio": "2026-12-15", "fim": "2026-12-01"})

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "O fim da ausência não pode ser antes do início"}
    assert banco.tabelas["nsp_ausencias_da_presidencia"] == []


def test_a_ausencia_se_registra_so_na_ficha_do_suplente():
    banco = _banco()

    resposta = _cliente(banco, PRESIDENTE).post("/api/nsp/membros/part-P2/ausencia-da-presidencia", json=PERIODO)

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "A ausência da Presidência se registra na ficha do suplente"}
    assert banco.tabelas["nsp_ausencias_da_presidencia"] == []


@pytest.mark.parametrize(
    ("pessoa", "ausencias"),
    [
        (MEMBRO, ()),
        (DIRETOR, ()),
        (SUPLENTE, ()),
        (SUPLENTE, (_ausencia(HOJE - timedelta(days=1), HOJE + timedelta(days=1)),)),
    ],
    ids=["membro", "Diretoria", "suplente", "suplente em exercício"],
)
def test_quem_nao_e_presidencia_nem_acesso_pleno_nao_registra_a_ausencia(pessoa, ausencias):
    banco = _banco(ausencias=ausencias)

    resposta = _cliente(banco, pessoa).post(AUSENCIA, json=PERIODO)

    assert resposta.status_code == 403
    assert resposta.json() == RECUSA
    assert len(banco.tabelas["nsp_ausencias_da_presidencia"]) == len(ausencias)
    assert banco.tabelas["participacoes_trilha"] == []


class TestMigration:
    def _sql(self) -> str:
        return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))

    def test_a_ausencia_nasce_com_inicio_fim_e_autor_obrigatorios(self):
        corpo = re.search(r"CREATE TABLE IF NOT EXISTS nsp_ausencias_da_presidencia\s*\((.*?)\n\);", self._sql(), re.S)
        assert corpo
        for coluna in ("participacao_id", "inicio", "fim", "autor_id"):
            assert re.search(rf"^\s*{coluna}\s+\w+(\(\d+\))?\s+NOT NULL", corpo.group(1), re.M), coluna
        assert "CHECK (fim >= inicio)" in corpo.group(1)

    def test_a_ausencia_tem_rls_sem_politica_e_nao_muda(self):
        assert "ALTER TABLE nsp_ausencias_da_presidencia ENABLE ROW LEVEL SECURITY;" in self._sql()
        assert re.search(r"CREATE\s+POLICY", self._sql(), re.I) is None
        assert re.search(r"BEFORE UPDATE OR DELETE ON nsp_ausencias_da_presidencia\s", self._sql())

    def test_a_trilha_aceita_a_ausencia_sem_perder_as_acoes_antigas(self):
        acoes = re.search(r"participacoes_trilha_acao_check\s+CHECK \(acao IN \(([^)]*)\)\)", self._sql())
        assert acoes
        assert set(re.findall(r"'(\w+)'", acoes.group(1))) == {
            "cadastro",
            "edicao",
            "renovacao",
            "mudanca_de_papel",
            "encerramento",
            "termo_enviado",
            "termo_reenviado",
            "termo_assinado",
            "liberacao_manual",
            "ausencia_da_presidencia",
        }

    def test_o_recibo_e_o_212(self):
        assert (
            self._sql()
            .rstrip()
            .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (212) ON CONFLICT (numero) DO NOTHING;")
        )
