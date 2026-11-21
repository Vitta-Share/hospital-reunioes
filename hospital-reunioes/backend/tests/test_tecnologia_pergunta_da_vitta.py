"""A Pergunta da Vitta nasce pela ponte e aparece como cartão na Conversa da
Demanda (issue #2116, PRD #2112, ADR 0109, decisões 1 e 3).

A Pergunta vira registro do app: ligada a uma Demanda, com Destinatário,
Assunto, o texto, as quatro linhas do cartão (por que precisa da pessoa, o que
está parado, o que anda depois e o ganho), as opções com a recomendada e o
porquê, e o estado. Nasce aberta. A ponte ganha duas rotas, com a mesma chave
e o mesmo teto: criar e ler. A mensagem pela rota de antes, com ou sem "pede
resposta", segue igual e não cria Pergunta.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_vinculo import _demanda, _montar, _pessoa, _SupabaseMock  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import tecnologia_automacao  # noqa: E402
from app.services import tecnologia_email  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

CHAVE = "chave-de-automacao-do-teste-2116"
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
CRIAR = f"/api/automacao/tecnologia/demandas/{DEMANDA}/perguntas"
MENSAGEM_DE_ANTES = f"/api/automacao/tecnologia/demandas/{DEMANDA}/conversa"

PEDRO = _pessoa("P001", "Pedro Rezende", github_login="pedrorezendefig")
DIRETOR = _pessoa("P003", "Diretor Geral")
DIRETORA = _pessoa("P004", "Diretora Clínica")
GESTORA = _pessoa("P012", "Gestora da Recepção", access_profile="gestor")
DESLIGADO = {**_pessoa("P006", "Diretor Antigo"), "ativo": False}
NINGUEM = "P999"

CADASTRO = [PEDRO, DIRETOR, DIRETORA, GESTORA, DESLIGADO]

TABELA = "tecnologia_perguntas"
CONVERSA = "tecnologia_conversa_da_demanda"

QUATRO_LINHAS = {
    "por_que_precisa": "Só a diretoria decide quem assina a ata em nome do hospital.",
    "o_que_esta_parado": "A tela de assinatura da Ata espera essa regra para sair.",
    "o_que_anda_depois": "A Vitta termina a tela e ela entra na próxima subida.",
    "ganho": "A ata sai assinada no mesmo dia da reunião.",
}
PERGUNTA = {
    "github_login": "pedrorezendefig",
    "destinatario_id": DIRETORA["id"],
    "assunto": "quem assina a Ata pela diretoria",
    "texto": "Quem assina a Ata em nome da diretoria quando a senhora não está?",
    **QUATRO_LINHAS,
    "opcoes": ["O diretor geral", "Quem presidiu a reunião"],
    "recomendada": "B",
    "porque": "Quem presidiu esteve na reunião e conhece o que foi decidido.",
}


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def chave_configurada(monkeypatch):
    monkeypatch.setattr(settings, "tecnologia_automacao_api_key", CHAVE)


@pytest.fixture(autouse=True)
def emails(monkeypatch) -> list[dict]:
    """Cada e-mail que sairia, gravado na porta do transporte."""
    enviados: list[dict] = []

    def _gravar(destinatario, assunto, html_content, texto_fallback, *a, **kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html_content, "texto": texto_fallback})
        return True

    monkeypatch.setattr(tecnologia_email, "_enviar_email", _gravar)
    monkeypatch.setattr(settings, "frontend_url", "https://app.hsm.test")
    return enviados


def _a_demanda() -> dict:
    """Um card que a Vitta abriu (Origem Vitta): toda a diretoria o vê."""
    return _demanda(
        DEMANDA,
        titulo="A Ata assinada no app",
        autor_id=PEDRO["id"],
        responsavel_id=PEDRO["id"],
        github_issue_numero=1700,
        origem="vitta",
        apagada_em=None,
    )


def _ponte(sb: _SupabaseMock | None = None) -> tuple[TestClient, _SupabaseMock]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = sb or _SupabaseMock(
        {
            "participantes": [dict(p) for p in CADASTRO],
            "tecnologia_produtos": [{"id": "prod-1", "nome": "Reuniões", "ativo": True, "ordem": 1, "dono_id": "P001"}],
            "tecnologia_demandas": [_a_demanda()],
            CONVERSA: [],
            TABELA: [],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app), sb


def _criar(cliente: TestClient, **campos):
    return cliente.post(CRIAR, json={**PERGUNTA, **campos}, headers={"X-API-Key": CHAVE})


def _avisados(sb) -> list[str]:
    return sorted(n["destinatario_id"] for n in sb.tabelas.get("notificacoes", []))


# ═══════════════════════════════════════════════════════════════════════════
# Criar pela ponte
# ═══════════════════════════════════════════════════════════════════════════


class TestCriar:
    def test_criar_grava_a_pergunta_aberta_com_as_quatro_linhas_e_as_opcoes_e_devolve_o_id(self):
        cliente, sb = _ponte()

        resposta = _criar(cliente)

        assert resposta.status_code == 201, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert resposta.json()["id"] == pergunta["id"]
        assert resposta.json()["estado"] == "aberta"
        assert pergunta["estado"] == "aberta"
        assert pergunta["demanda_id"] == DEMANDA
        assert pergunta["destinatario_id"] == DIRETORA["id"]
        assert pergunta["autor_id"] == PEDRO["id"]
        assert pergunta["assunto"] == "quem assina a Ata pela diretoria"
        assert pergunta["texto"] == "Quem assina a Ata em nome da diretoria quando a senhora não está?"
        assert {chave: pergunta[chave] for chave in QUATRO_LINHAS} == QUATRO_LINHAS
        assert pergunta["opcoes"] == [
            {"letra": "A", "texto": "O diretor geral"},
            {"letra": "B", "texto": "Quem presidiu a reunião"},
        ]
        assert pergunta["recomendada"] == "B"
        assert pergunta["porque_da_recomendada"] == "Quem presidiu esteve na reunião e conhece o que foi decidido."

    def test_criar_sem_opcoes_tambem_vale(self):
        cliente, sb = _ponte()

        resposta = _criar(cliente, opcoes=[], recomendada=None, porque=None)

        assert resposta.status_code == 201, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert (pergunta["opcoes"], pergunta["recomendada"]) == ([], None)
