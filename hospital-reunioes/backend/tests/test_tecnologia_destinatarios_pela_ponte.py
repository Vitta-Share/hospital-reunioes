"""Quem pode ser Destinatário, lido pela ponte (issue #1966, PRD #1964).

A ponte de automação (a mesma chave e o mesmo teto das outras rotas dela)
ganha a lista dos participantes ativos, com id e nome, para o PedroOS saber se
a pessoa tem login no app e escolher o Canal (app ou WhatsApp). E-mail,
telefone e qualquer outro dado do cadastro não saem.

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

from test_tecnologia_conversa_lida_pela_ponte import _SupabaseQueRegistra  # noqa: E402
from test_tecnologia_vinculo import _pessoa  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import tecnologia_automacao  # noqa: E402
from app.services import paginacao  # noqa: E402

CHAVE = "chave-de-automacao-do-teste-1966"
ROTA = "/api/automacao/tecnologia/destinatarios"


def _com_telefone(pessoa: dict, telefone: str) -> dict:
    return {**pessoa, "telefone": telefone}


DIRETOR = _com_telefone(_pessoa("P3", "Diretor Geral"), "21999990003")
LUCAS = _com_telefone(_pessoa("P2", "Lucas Sampaio", github_login="lucas-vitta"), "21999990002")
ANA = _com_telefone(_pessoa("P5", "ana Beatriz", access_profile="gestor"), "21999990005")
DESLIGADA = {**_com_telefone(_pessoa("P4", "Carla Desligada"), "21999990004"), "ativo": False}
CADASTRO = [DIRETOR, LUCAS, DESLIGADA, ANA]


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def chave_configurada(monkeypatch):
    monkeypatch.setattr(settings, "tecnologia_automacao_api_key", CHAVE)


def _cliente(cadastro: list[dict] | None = None) -> tuple[TestClient, _SupabaseQueRegistra]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = _SupabaseQueRegistra({"participantes": [dict(p) for p in (cadastro if cadastro is not None else CADASTRO)]})
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app, raise_server_exceptions=False), sb


def _listar(cliente: TestClient, *, headers: dict | None = None):
    return cliente.get(ROTA, headers={"X-API-Key": CHAVE} if headers is None else headers)


class TestQuemPodeSerDestinatario:
    def test_a_ponte_devolve_id_e_nome_de_cada_participante_ativo_em_ordem_de_nome(self):
        cliente, _ = _cliente()

        resposta = _listar(cliente)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {
            "destinatarios": [
                {"id": "P5", "nome": "ana Beatriz"},
                {"id": "P3", "nome": "Diretor Geral"},
                {"id": "P2", "nome": "Lucas Sampaio"},
            ]
        }

    def test_nenhum_dado_pessoal_sai_alem_de_id_e_nome(self):
        cliente, _ = _cliente()

        resposta = _listar(cliente)

        corpo = resposta.text
        for pessoa in (DIRETOR, LUCAS, ANA):
            assert pessoa["email"] not in corpo
            assert pessoa["telefone"] not in corpo
            assert pessoa["auth_user_id"] not in corpo
        assert {chave for d in resposta.json()["destinatarios"] for chave in d} == {"id", "nome"}

    def test_cadastro_maior_que_uma_pagina_volta_inteiro(self):
        total = paginacao.PAGINA + 3
        cadastro = [_pessoa(f"Q{i:05d}", f"Pessoa {i:05d}") for i in range(total)]
        cliente, _ = _cliente(cadastro=cadastro)

        resposta = _listar(cliente)

        nomes = [d["nome"] for d in resposta.json()["destinatarios"]]
        assert len(nomes) == total
        assert nomes[-1] == f"Pessoa {total - 1:05d}"


class TestParticipanteInativo:
    def test_participante_inativo_nao_aparece(self):
        cliente, _ = _cliente()

        resposta = _listar(cliente)

        ids = [d["id"] for d in resposta.json()["destinatarios"]]
        assert "P4" not in ids
        assert "Carla Desligada" not in resposta.text

    def test_ativo_sem_valor_conta_como_ativo_como_no_resto_do_app(self):
        # A coluna nasce com default TRUE; linha antiga com nulo não é desligada.
        sem_valor = {**_pessoa("P6", "Bruno Antigo"), "ativo": None}
        cliente, _ = _cliente(cadastro=[sem_valor, DESLIGADA])

        resposta = _listar(cliente)

        assert resposta.json() == {"destinatarios": [{"id": "P6", "nome": "Bruno Antigo"}]}


class TestAChave:
    @pytest.mark.parametrize(
        "cabecalhos", [{}, {"X-API-Key": ""}, {"X-API-Key": CHAVE + "x"}], ids=["ausente", "vazia", "errada"]
    )
    def test_chave_ausente_ou_errada_recusa_com_401_como_as_outras_rotas(self, cabecalhos):
        cliente, _ = _cliente()

        resposta = _listar(cliente, headers=cabecalhos)

        assert resposta.status_code == 401
        assert resposta.json() == {"detail": "API key inválida ou ausente"}
        assert "Diretor Geral" not in resposta.text

    def test_sem_chave_configurada_responde_503(self, monkeypatch):
        monkeypatch.setattr(settings, "tecnologia_automacao_api_key", "")
        cliente, _ = _cliente()

        resposta = _listar(cliente)

        assert resposta.status_code == 503
        assert "TECNOLOGIA_AUTOMACAO_API_KEY" in resposta.json()["detail"]

    def test_a_chave_errada_gasta_o_mesmo_teto_por_endereco(self):
        cliente, _ = _cliente()

        for _ in range(60):
            assert _listar(cliente, headers={"X-API-Key": "errada"}).status_code == 401

        assert _listar(cliente).status_code == 429


class TestSoLe:
    def test_listar_nao_grava_nada_no_banco(self):
        cliente, sb = _cliente()
        antes = {nome: [dict(linha) for linha in linhas] for nome, linhas in sb.tabelas.items()}

        resposta = _listar(cliente)

        assert resposta.status_code == 200
        assert sb.escritas == []
        assert sb.tabelas == antes
