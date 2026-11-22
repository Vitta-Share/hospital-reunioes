"""O relato em passos do Canal de Conduta, pela rota pública (issue #1843).

Sem login. Quem relata passa pelos passos P1 a P5 e o envio chega aqui de uma
vez: a ciência do passo 1, a identificação, o "sobre o quê" e o "o que
aconteceu". A resposta traz o protocolo e o código, uma vez só, e a data para
voltar. Tudo é exercitado pela rota (TestClient), com o limitador, o
middleware de log e o tratamento do 429 de produção.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import sys
from datetime import date

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import JsonFormatter, RequestContextMiddleware  # noqa: E402
from app.routers import conduta_publico  # noqa: E402
from app.services.conduta import agente_de_triagem, cifra, relato_publico  # noqa: E402
from app.services.ouvidoria_acompanhamento import codigo_confere  # noqa: E402

RELATOS = "/api/conduta/relatos"
CONFIANCA = "/api/conduta/relatos/confianca"
IP_DE_QUEM_RELATA = "203.0.113.45"
APARELHO = "Mozilla/5.0 (Linux; Android 10; SM-A105M) Celular-de-Entrada/77"
TEXTO = "A supervisora do almoxarifado gritou com a equipe e ameaçou cortar o turno de quem reclamasse."
NOME = "Joana Prudente"

CIENCIA = {"ciente": True, "versoes": {"aviso_p1_anonimato": 1, "aviso_p1_protocolo": None, "aviso_p1_boa_fe": 2}}


def envio(**mudar) -> dict:
    base = {
        "ciencia": CIENCIA,
        "identificacao": "anonimo",
        "nome": None,
        "assunto": "A",
        "direcao": "nao",
        "posicao": "presenciou",
        "relato": TEXTO,
        "quando": "Semana passada",
        "ainda_acontece": True,
        "onde": "Almoxarifado",
        "quem": "A supervisora do turno da tarde",
        "testemunhas": "Dois auxiliares",
        "lideranca_sabe": "sim",
        "o_que_foi_feito": "Nada até agora",
        "evidencias": "Mensagens no grupo do setor",
    }
    return base | mudar


def _versoes(chave: str, quantas: int) -> list[dict]:
    return [
        {"id": f"{chave}-{n}", "chave": chave, "versao": n, "texto": f"texto {n}", "autor_id": "P1", "criado_em": "x"}
        for n in range(1, quantas + 1)
    ]


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "conduta_canal_aberto", True)
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def triagens(monkeypatch):
    """O agente de triagem é chamado depois da resposta; aqui só se anota."""
    chamadas: list[str] = []
    monkeypatch.setattr(agente_de_triagem, "agendar_triagem_do_caso", lambda _t, _s, caso_id: chamadas.append(caso_id))
    return chamadas


@pytest.fixture
def banco():
    return Banco(
        {
            "conduta_configuracoes": _versoes("aviso_p1_anonimato", 1) + _versoes("aviso_p1_boa_fe", 2),
        }
    )


@pytest.fixture
def cliente(banco, triagens):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(conduta_publico.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app, client=(IP_DE_QUEM_RELATA, 50123), raise_server_exceptions=False)


def _relatar(cliente, corpo=None, **cabecalhos):
    return cliente.post(RELATOS, json=corpo if corpo is not None else envio(), headers={"User-Agent": APARELHO, **cabecalhos})


def _o_caso(banco) -> dict:
    (caso,) = banco.tabelas["conduta_casos"]
    return caso


class TestEnvio:
    def test_o_relato_enviado_devolve_protocolo_e_codigo_e_fica_cifrado(self, cliente, banco):
        resposta = _relatar(cliente)

        assert resposta.status_code == 201
        corpo = resposta.json()
        caso = _o_caso(banco)
        assert corpo["protocolo"] == caso["protocolo"]
        assert codigo_confere(corpo["codigo"], caso["codigo_hash"])
        assert TEXTO not in repr(banco.tabelas)
        assert TEXTO in cifra.decifrar_texto(caso["relato_cifrado"])
