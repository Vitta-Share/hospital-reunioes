"""A observação do Validar fica no app (issue #2013, PRD #2007, ADR 0108, decisão 5).

O botão Validar da Apresentação do PRD (a função `validar.js` da Vercel) manda
a observação do diretor à ponte de automação, numa rota com chave própria
(`PLANOS_HSM_API_KEY`). O app guarda o texto original junto da Demanda do PRD,
na tabela do Envio aos desenvolvedores com a origem `validacao`, chama a mesma
interpretação do Envio e devolve só os tópicos. O GitHub recebe os tópicos; a
fala do diretor nunca sai do app.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo` e
o modelo dublado pelo `_ia` do planejamento.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_planejamento_demanda import _ia  # noqa: E402
from test_tecnologia_vinculo import _demanda, _pessoa, _SupabaseMock  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import tecnologia_automacao  # noqa: E402

CHAVE = "chave-dos-planos-do-teste-2013"
CHAVE_DA_PONTE = "chave-da-ponte-do-terminal-2013"
ROTA = "/api/automacao/tecnologia/validacoes"
DEMANDA = "7d3c2b1a-0f9e-4d8c-8b7a-6f5e4d3c2b1a"
PRD = 1757
TABELA = "tecnologia_envios_aos_desenvolvedores"

MIGRATION = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "166_tecnologia_observacao_da_validacao.sql"
)

DIRETOR = _pessoa("P3", "Diretor Geral")
PEDRO = _pessoa("P1", "Pedro Rezende", github_login="pedrorezendefig")

# A observação que o diretor escreve no Validar e que nunca pode chegar ao GitHub.
OBSERVACAO = "Quero que a enfermeira Joana do terceiro andar consiga imprimir a escala sozinha"
INTERPRETACAO = {
    "topicos": ["A enfermagem imprime a escala sem pedir ajuda.", "Avisar @lucas-vitta — o botão fica na escala."],
    "cards": [],
}


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _chaves(monkeypatch):
    monkeypatch.setattr(settings, "planos_hsm_api_key", CHAVE)
    monkeypatch.setattr(settings, "tecnologia_automacao_api_key", CHAVE_DA_PONTE)


@pytest.fixture(autouse=True)
def _llm_em_mock(monkeypatch):
    """O pytest carrega o `.env` real: sem isto, o teste que esquecesse de
    dublar o modelo chamaria o provedor de verdade."""
    from app.services import ai_processor

    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "mock")


def _demanda_do_prd(**campos) -> dict:
    base = {
        "autor_id": DIRETOR["id"],
        "responsavel_id": PEDRO["id"],
        "github_issue_numero": PRD,
        "o_que_muda": "A enfermagem monta a escala no app.",
        "partes": [{"numero": 1758, "o_que_muda": "A escala na tela.", "situacao": "planejada"}],
        "apagada_em": None,
    }
    base.update(campos)
    return _demanda(DEMANDA, titulo="Escala da enfermagem", **base)


def _cliente(demandas: list[dict] | None = None) -> tuple[TestClient, _SupabaseMock]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router_dos_planos, prefix="/api")
    sb = _SupabaseMock(
        {
            "participantes": [dict(PEDRO), dict(DIRETOR)],
            "tecnologia_demandas": [dict(d) for d in (demandas if demandas is not None else [_demanda_do_prd()])],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app), sb


def _validar(cliente: TestClient, *, chave: str | None = CHAVE, prd: int = PRD, observacao: str = OBSERVACAO):
    headers = {"X-API-Key": chave} if chave is not None else {}
    return cliente.post(ROTA, json={"prd": prd, "observacao": observacao}, headers=headers)


# ═══════════════════════════════════════════════════════════════════════════
# 1. A chave própria
# ═══════════════════════════════════════════════════════════════════════════


class TestChave:
    @pytest.mark.parametrize("chave", [None, "", "chave-errada", CHAVE_DA_PONTE])
    def test_chave_ausente_errada_ou_a_da_ponte_do_terminal_recebe_401_e_nada_e_gravado(self, chave):
        cliente, sb = _cliente()

        resposta = _validar(cliente, chave=chave)

        assert resposta.status_code == 401
        assert sb.tabelas.get(TABELA, []) == []

    def test_sem_a_variavel_configurada_a_rota_responde_503(self, monkeypatch):
        monkeypatch.setattr(settings, "planos_hsm_api_key", "")
        cliente, sb = _cliente()

        resposta = _validar(cliente)

        assert resposta.status_code == 503
        assert "PLANOS_HSM_API_KEY" in resposta.json()["detail"]
        assert sb.tabelas.get(TABELA, []) == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. O original fica no app, só os tópicos voltam
# ═══════════════════════════════════════════════════════════════════════════


class TestObservacao:
    def test_guarda_o_original_junto_da_demanda_e_devolve_so_os_topicos(self, monkeypatch):
        cliente, sb = _cliente()
        modelo = _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        resposta = _validar(cliente)

        assert resposta.status_code == 201, resposta.text
        corpo = resposta.json()
        assert corpo["guardada"] is True
        assert corpo["topicos"][0] == "A enfermagem imprime a escala sem pedir ajuda."
        # O que volta vai para o GitHub público: nada da fala do diretor, sem
        # travessão e sem menção.
        devolvido = json.dumps(corpo, ensure_ascii=False)
        assert "Joana" not in devolvido
        assert "imprimir a escala sozinha" not in devolvido
        assert "—" not in devolvido
        assert "@lucas-vitta" not in devolvido

        [linha] = sb.tabelas[TABELA]
        assert linha["demanda_id"] == DEMANDA
        assert linha["origem"] == "validacao"
        assert linha["texto_original"] == OBSERVACAO
        assert linha["topicos"][0] == "A enfermagem imprime a escala sem pedir ajuda."

        # A interpretação é a mesma do Envio, com a observação no pedido.
        [chamada] = modelo.chamadas
        assert OBSERVACAO in chamada["messages"][0]["content"]
        [custo] = sb.tabelas["tecnologia_chamadas_ia"]
        assert custo["demanda_id"] == DEMANDA
        assert custo["passo"] == "envio"

    def test_modelo_que_falha_guarda_o_original_e_devolve_sem_topico(self, monkeypatch):
        cliente, sb = _cliente()
        _ia(monkeypatch, "isto não é JSON")

        resposta = _validar(cliente)

        assert resposta.status_code == 201, resposta.text
        assert resposta.json() == {"guardada": True, "topicos": []}
        [linha] = sb.tabelas[TABELA]
        assert linha["texto_original"] == OBSERVACAO
        assert linha["topicos"] == []

    def test_prd_sem_demanda_responde_404_e_nao_chama_o_modelo(self, monkeypatch):
        cliente, sb = _cliente(demandas=[_demanda_do_prd(github_issue_numero=1800)])
        modelo = _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        resposta = _validar(cliente)

        assert resposta.status_code == 404
        assert modelo.chamadas == []
        assert sb.tabelas.get(TABELA, []) == []

    def test_demanda_de_outro_projeto_com_o_mesmo_numero_nao_serve(self, monkeypatch):
        cliente, sb = _cliente(demandas=[_demanda_do_prd(projeto="ana")])
        _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        assert _validar(cliente).status_code == 404
        assert sb.tabelas.get(TABELA, []) == []

    def test_observacao_vazia_e_recusada(self, monkeypatch):
        cliente, sb = _cliente()
        modelo = _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        resposta = _validar(cliente, observacao="   ")

        assert resposta.status_code == 422
        assert modelo.chamadas == []
        assert sb.tabelas.get(TABELA, []) == []


class TestMigration:
    def test_a_tabela_do_envio_ganha_a_origem_e_o_texto_original_com_o_recibo_166(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        assert "ALTER TABLE tecnologia_envios_aos_desenvolvedores" in sql
        assert "ADD COLUMN IF NOT EXISTS origem" in sql
        assert "'conversa'" in sql and "'validacao'" in sql
        assert "ADD COLUMN IF NOT EXISTS texto_original" in sql
        assert "CREATE POLICY" not in sql.upper()
        assert sql.rstrip().endswith(
            "INSERT INTO migracoes_aplicadas (numero) VALUES (166) ON CONFLICT (numero) DO NOTHING;"
        )
