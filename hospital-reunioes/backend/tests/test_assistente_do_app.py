"""O Assistente do app: tirar dúvida pelo robô do canto da tela (issue #2267,
ADR 0113, decisão 8).

A rota roda de verdade, com `get_current_user` de pé no teste do 401. Nos
outros, só o login e o Supabase são dublados, e o cliente da Anthropic é o
`ClienteFalso`, que guarda os argumentos de cada chamada: é por eles que o
teste lê o modelo, as ferramentas e o contexto que sairiam para a Anthropic.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anthropic_apoio import ClienteFalso  # noqa: E402

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import assistente_do_app as assistente_router  # noqa: E402
from app.services import assistente_do_app  # noqa: E402

ROTA = "/api/assistente-do-app/conversa"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


class _Supabase:
    """Guarda toda tabela tocada e toda escrita: a conversa de dúvida não
    pode criar Demanda nem gravar nada."""

    def __init__(self):
        self.tabelas: list[str] = []
        self.escritas: list[tuple[str, str]] = []
        self._tabela = ""

    def table(self, nome):
        self._tabela = nome
        self.tabelas.append(nome)
        return self

    def _escreve(self, operacao):
        self.escritas.append((self._tabela, operacao))
        return self

    def insert(self, *_a, **_kw):
        return self._escreve("insert")

    def upsert(self, *_a, **_kw):
        return self._escreve("upsert")

    def update(self, *_a, **_kw):
        return self._escreve("update")

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def execute(self):
        return type("R", (), {"data": []})()


@pytest.fixture
def cliente_da_ia(monkeypatch) -> ClienteFalso:
    falso = ClienteFalso("Para abrir uma Pendência, clique em Nova pendência. Fonte: Reuniões e Pendências.")
    monkeypatch.setattr(assistente_do_app, "_cliente", lambda: falso)
    return falso


def _app(supabase: _Supabase, *, logado: bool) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(assistente_router.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: supabase
    if logado:

        async def _usuario() -> dict[str, Any]:
            # Pessoa comum, sem Super admin: a rota pede só o login.
            return {"id": "auth-P22670", "email": "p22670@exemplo.test", "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
    return TestClient(app)


def _pagina(modulo: str, titulo: str, corpo: str) -> dict:
    return {"modulo": modulo, "titulo": titulo, "corpo": corpo}


def _pedido(paginas: list[dict] | None = None) -> dict:
    return {
        "mensagens": [{"role": "user", "content": "Como eu abro uma pendência?"}],
        "paginas_do_manual": paginas
        if paginas is not None
        else [_pagina("reunioes-e-pendencias", "Reuniões e Pendências", "Clique em Nova pendência.")],
    }


class TestQuemConversa:
    def test_usuario_logado_sem_super_admin_recebe_a_resposta(self, cliente_da_ia):
        resposta = _app(_Supabase(), logado=True).post(ROTA, json=_pedido())

        assert resposta.status_code == 200
        assert resposta.json() == {
            "resposta": "Para abrir uma Pendência, clique em Nova pendência. Fonte: Reuniões e Pendências."
        }
        assert len(cliente_da_ia.chamadas) == 1

    def test_sem_login_a_rota_responde_401_e_nao_chama_a_ia(self, cliente_da_ia):
        resposta = _app(_Supabase(), logado=False).post(ROTA, json=_pedido())

        assert resposta.status_code == 401
        assert cliente_da_ia.chamadas == []


class TestOQueSaiParaAAnthropic:
    def test_o_modelo_e_o_sonnet_5_5_da_constante_unica(self, cliente_da_ia):
        _app(_Supabase(), logado=True).post(ROTA, json=_pedido())

        assert cliente_da_ia.chamadas[0]["model"] == "claude-sonnet-5-5"

    def test_a_chamada_nao_leva_ferramenta_nenhuma(self, cliente_da_ia):
        _app(_Supabase(), logado=True).post(ROTA, json=_pedido())

        chamada = cliente_da_ia.chamadas[0]
        assert "tools" not in chamada
        assert "tool_choice" not in chamada

    def test_o_contexto_leva_o_kit_e_so_as_paginas_que_a_tela_mandou(self, cliente_da_ia):
        paginas = [_pagina("pops", "POPs", "MARCA-DA-PAGINA-DE-POPS")]

        _app(_Supabase(), logado=True).post(ROTA, json=_pedido(paginas))

        contexto = "\n".join(bloco["text"] for bloco in cliente_da_ia.chamadas[0]["system"])
        assert "MARCA-DA-PAGINA-DE-POPS" in contexto
        assert "## Manual: POPs" in contexto
        assert "# tecnologia.md" in contexto
        assert "Clique em Nova pendência." not in contexto


class TestNaoViraDemanda:
    def test_a_conversa_de_duvida_nao_grava_nada_nem_cria_demanda(self, cliente_da_ia):
        supabase = _Supabase()

        resposta = _app(supabase, logado=True).post(ROTA, json=_pedido())

        assert resposta.status_code == 200
        assert supabase.escritas == []
        assert "tecnologia_demandas" not in supabase.tabelas
