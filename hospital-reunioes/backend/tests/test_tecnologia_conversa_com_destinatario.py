"""A mensagem pela ponte com Destinatário, Assunto e "pede resposta" (issue
#1965, PRD #1964, ADR 0106).

A escrita na Conversa da Demanda pela ponte de automação (ADR 0096) ganha três
campos opcionais. Com Destinatário, o aviso (sino e e-mail) vai só para ele,
em qualquer Origem, e não pela regra das entregas. Com "pede resposta", o sino
diz "Pede sua resposta" com o Assunto, e o e-mail tem o assunto "<Nome> pede
sua resposta: <Assunto>". Sem os campos, tudo segue como hoje.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo`.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_vinculo import _demanda, _pessoa, _SupabaseMock  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import tecnologia_automacao  # noqa: E402
from app.services import tecnologia_email  # noqa: E402

CHAVE = "chave-de-automacao-do-teste-1965"
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
ESCREVER = f"/api/automacao/tecnologia/demandas/{DEMANDA}/conversa"

# O id do participante é UUID no banco: o Destinatário chega como UUID.
PEDRO = _pessoa("11111111-1111-4111-8111-111111111111", "Pedro Rezende", github_login="pedrorezendefig")
LUCAS = _pessoa("22222222-2222-4222-8222-222222222222", "Lucas Sampaio", github_login="lucas-vitta")
DIRETOR = _pessoa("33333333-3333-4333-8333-333333333333", "Diretor Geral")
DIRETORA = _pessoa("44444444-4444-4444-8444-444444444444", "Diretora Clínica")
# Fora da diretoria e fora da regra das entregas: só o Destinatário o alcança.
GESTORA = _pessoa("55555555-5555-4555-8555-555555555555", "Gestora da Recepção", access_profile="gestor")
DESLIGADO = {**_pessoa("66666666-6666-4666-8666-666666666666", "Diretor Antigo"), "ativo": False}
NINGUEM = "77777777-7777-4777-8777-777777777777"

CADASTRO = [PEDRO, LUCAS, DIRETOR, DIRETORA, GESTORA, DESLIGADO]


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


def _demanda_do_diretor(**campos) -> dict:
    base = {
        "autor_id": DIRETOR["id"],
        "responsavel_id": LUCAS["id"],
        "github_issue_numero": 1700,
        "origem": "diretor",
        "apagada_em": None,
    }
    base.update(campos)
    return _demanda(DEMANDA, titulo="O relatório some", **base)


def _demanda_da_vitta() -> dict:
    return _demanda_do_diretor(autor_id=PEDRO["id"], responsavel_id=PEDRO["id"], origem="vitta")


def _cliente(demanda: dict | None = None) -> tuple[TestClient, _SupabaseMock]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = _SupabaseMock(
        {
            "participantes": [dict(p) for p in CADASTRO],
            "tecnologia_demandas": [dict(demanda or _demanda_do_diretor())],
            "tecnologia_conversa_da_demanda": [],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app), sb


def _escrever(cliente: TestClient, **campos):
    corpo = {"texto": "E aí, a reunião de quinta fica às 10h?", "github_login": "pedrorezendefig", **campos}
    return cliente.post(ESCREVER, json=corpo, headers={"X-API-Key": CHAVE})


def _avisados(sb) -> list[str]:
    return sorted(n["destinatario_id"] for n in sb.tabelas.get("notificacoes", []))


# ═══════════════════════════════════════════════════════════════════════════
# Quem o Destinatário avisa
# ═══════════════════════════════════════════════════════════════════════════


class TestODestinatario:
    @pytest.mark.parametrize("demanda", [_demanda_do_diretor(), _demanda_da_vitta()], ids=["do-diretor", "da-vitta"])
    def test_com_destinatario_o_aviso_vai_so_para_ele_por_sino_e_email(self, demanda, emails):
        """Nem quem abriu a Demanda (card do diretor) nem a diretoria (card da
        Vitta): só a gestora, que a regra das entregas nunca avisaria."""
        cliente, sb = _cliente(demanda)

        resposta = _escrever(cliente, destinatario_id=GESTORA["id"])

        assert resposta.status_code == 201, resposta.text
        assert _avisados(sb) == [GESTORA["id"]]
        assert [e["para"] for e in emails] == [GESTORA["email"]]
