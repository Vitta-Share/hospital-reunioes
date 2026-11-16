"""A Mensagem pelo terminal (issue #1805, PRD #1803, ADR 0096).

A ponte de automação (a mesma chave da leitura dos anexos) ganha duas rotas:
achar a Demanda de uma issue-raiz pelo projeto e número, e escrever na
Conversa da Demanda no perfil de quem roda a sessão, pelo login do GitHub. O
app só aceita login de Desenvolvedor ativo (o Super admin com login do GitHub
no cadastro) e grava a mensagem com a origem `terminal`.

O aviso segue a regra dos avisos de entrega: no card da Vitta, a diretoria
(Super admins ativos sem login do GitHub); no card do diretor, quem abriu a
Demanda. Sino e e-mail, dublados.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

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

CHAVE = "chave-de-automacao-do-teste-1805"
DEMANDA = "5c1e7a2b-3d4f-4a6b-9c8d-1e2f3a4b5c6d"
INEXISTENTE = "0b9a8c7d-6e5f-4a3b-8c2d-1e0f9a8b7c6d"
BASE = "/api/automacao/tecnologia"
ESCREVER = f"{BASE}/demandas/{DEMANDA}/conversa"

# Os Desenvolvedores da Vitta (Super admin com login do GitHub).
PEDRO = _pessoa("P1", "Pedro Rezende", github_login="pedrorezendefig")
LUCAS = _pessoa("P2", "Lucas Sampaio", github_login="lucas-vitta")
# A diretoria do hospital (Super admin sem login do GitHub).
DIRETOR = _pessoa("P3", "Diretor Geral")
DIRETORA = _pessoa("P4", "Diretora Clínica")
# Fora de quem pode escrever ou ser avisado.
DESLIGADO = {**_pessoa("P5", "Diretor Antigo"), "ativo": False}
EX_DESENVOLVEDOR = {**_pessoa("P6", "Ex Vitta", github_login="ex-vitta"), "ativo": False}
GESTOR_COM_LOGIN = _pessoa("P7", "Gestor Curioso", github_login="gestor-curioso", access_profile="gestor")

CADASTRO = [PEDRO, LUCAS, DIRETOR, DIRETORA, DESLIGADO, EX_DESENVOLVEDOR, GESTOR_COM_LOGIN]


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
        enviados.append({"para": destinatario, "assunto": assunto})
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


def _demanda_da_vitta(**campos) -> dict:
    return _demanda_do_diretor(autor_id=PEDRO["id"], responsavel_id=PEDRO["id"], origem="vitta", **campos)


def _cliente(
    demandas: list[dict] | None = None, conversa: list[dict] | None = None
) -> tuple[TestClient, _SupabaseMock]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = _SupabaseMock(
        {
            "participantes": [dict(p) for p in CADASTRO],
            "tecnologia_demandas": [dict(d) for d in (demandas if demandas is not None else [_demanda_do_diretor()])],
            "tecnologia_conversa_da_demanda": [dict(m) for m in (conversa or [])],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app), sb


def _escrever(cliente: TestClient, *, login: str = "pedrorezendefig", texto: str = "E aí, qual das duas?", **kw):
    return cliente.post(
        kw.pop("rota", ESCREVER),
        json={"texto": texto, "github_login": login},
        headers=kw.pop("headers", {"X-API-Key": CHAVE}),
    )


def _avisados(sb) -> list[str]:
    return sorted(n["destinatario_id"] for n in sb.tabelas.get("notificacoes", []))


# ═══════════════════════════════════════════════════════════════════════════
# A mensagem gravada
# ═══════════════════════════════════════════════════════════════════════════


class TestAMensagemGravada:
    def test_a_mensagem_pela_ponte_sai_no_perfil_do_dono_do_login_com_origem_terminal(self):
        cliente, sb = _cliente()

        resposta = _escrever(cliente, login="lucas-vitta", texto="E aí, o senhor prefere a opção A ou a B?")

        assert resposta.status_code == 201, resposta.text
        [linha] = sb.tabelas["tecnologia_conversa_da_demanda"]
        assert linha["demanda_id"] == DEMANDA
        assert linha["autor_id"] == LUCAS["id"]
        assert linha["texto"] == "E aí, o senhor prefere a opção A ou a B?"
        assert linha["origem"] == "terminal"
        assert resposta.json()["id"] == linha["id"]
