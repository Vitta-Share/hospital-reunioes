"""A resposta do diretor lida pela ponte (issue #1806, PRD #1803, ADR 0096 decisão 6).

A ponte de automação (a mesma chave e o mesmo teto da leitura dos anexos)
ganha a rota que lê a Conversa da Demanda: as mensagens depois de um instante
pedido, com autor (nome), data e texto, na ordem em que chegaram. A sessão do
terminal passa a data da própria pergunta e recebe só o que veio depois. A
leitura não grava nada e não muda a Etapa.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo`,
ganhando aqui o filtro `gt` e o registro de toda escrita.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_vinculo import _demanda, _pessoa, _SupabaseMock, _TableQuery  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import tecnologia_automacao  # noqa: E402
from app.services import paginacao  # noqa: E402

CHAVE = "chave-de-automacao-do-teste-1806"
DEMANDA = "7d2e8b3c-4e5f-4b7c-8d9e-2f3a4b5c6d7e"
OUTRA_DEMANDA = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
INEXISTENTE = "0b9a8c7d-6e5f-4a3b-8c2d-1e0f9a8b7c6d"
BASE = "/api/automacao/tecnologia"
LER = f"{BASE}/demandas/{DEMANDA}/conversa"

LUCAS = _pessoa("P2", "Lucas Sampaio", github_login="lucas-vitta")
DIRETOR = _pessoa("P3", "Diretor Geral")
CADASTRO = [LUCAS, DIRETOR]

# A pergunta do terminal, a resposta do diretor e o agradecimento, fora de
# ordem na tabela de propósito: quem ordena é a rota.
PERGUNTA = {
    "id": "m1",
    "demanda_id": DEMANDA,
    "autor_id": LUCAS["id"],
    "texto": "O senhor prefere a opção A ou a B?",
    "criado_em": "2026-11-16T14:00:00+00:00",
    "origem": "terminal",
}
RESPOSTA = {
    "id": "m2",
    "demanda_id": DEMANDA,
    "autor_id": DIRETOR["id"],
    "texto": "A opção B, por favor.",
    "criado_em": "2026-11-16T14:05:00+00:00",
    "origem": "app",
}
COMPLEMENTO = {
    "id": "m3",
    "demanda_id": DEMANDA,
    "autor_id": DIRETOR["id"],
    "texto": "E manda o relatório na segunda.",
    "criado_em": "2026-11-16T14:07:30+00:00",
    "origem": "app",
}
DE_OUTRA_DEMANDA = {
    "id": "m9",
    "demanda_id": OUTRA_DEMANDA,
    "autor_id": DIRETOR["id"],
    "texto": "Isto é de outra Demanda.",
    "criado_em": "2026-11-16T14:06:00+00:00",
    "origem": "app",
}
CONVERSA = [COMPLEMENTO, PERGUNTA, DE_OUTRA_DEMANDA, RESPOSTA]


class _ConsultaComGt(_TableQuery):
    """O dublê da casa com o `gt` do PostgREST (instante comparado como data,
    não como texto) e o registro de toda escrita que alguém tentar."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._gt: dict[str, str] = {}

    def gt(self, coluna, valor):
        self._gt[coluna] = valor
        return self

    def _casa(self, linha: dict) -> bool:
        if not super()._casa(linha):
            return False
        return all(
            linha.get(c) is not None and datetime.fromisoformat(linha[c]) > datetime.fromisoformat(v)
            for c, v in self._gt.items()
        )

    def insert(self, payload):
        self._dono.escritas.append(("insert", self._nome))
        return super().insert(payload)

    def update(self, payload):
        self._dono.escritas.append(("update", self._nome))
        return super().update(payload)

    def upsert(self, payload, **_kw):
        self._dono.escritas.append(("upsert", self._nome))
        return super().insert(payload)

    def delete(self):
        self._dono.escritas.append(("delete", self._nome))
        return super().delete()


class _SupabaseQueRegistra(_SupabaseMock):
    def __init__(self, tabelas):
        super().__init__(tabelas)
        self.escritas: list[tuple[str, str]] = []

    def table(self, nome: str):
        return _ConsultaComGt(self.tabelas.setdefault(nome, []), nome, dono=self)


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def chave_configurada(monkeypatch):
    monkeypatch.setattr(settings, "tecnologia_automacao_api_key", CHAVE)


def _cliente(
    demandas: list[dict] | None = None, conversa: list[dict] | None = None
) -> tuple[TestClient, _SupabaseQueRegistra]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = _SupabaseQueRegistra(
        {
            "participantes": [dict(p) for p in CADASTRO],
            "tecnologia_demandas": [
                dict(d)
                for d in (
                    demandas
                    if demandas is not None
                    else [_demanda(DEMANDA, titulo="O relatório some", autor_id=DIRETOR["id"], apagada_em=None)]
                )
            ],
            "tecnologia_conversa_da_demanda": [dict(m) for m in (conversa if conversa is not None else CONVERSA)],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app, raise_server_exceptions=False), sb


def _ler(cliente: TestClient, *, rota: str = LER, params: dict | None = None, headers: dict | None = None):
    return cliente.get(rota, params=params, headers={"X-API-Key": CHAVE} if headers is None else headers)


# ═══════════════════════════════════════════════════════════════════════════
# O que volta
# ═══════════════════════════════════════════════════════════════════════════


class TestAsMensagensDepoisDoInstante:
    def test_a_sessao_le_so_o_que_o_diretor_escreveu_depois_da_pergunta_em_ordem(self):
        cliente, _ = _cliente()

        resposta = _ler(cliente, params={"depois": PERGUNTA["criado_em"]})

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {
            "mensagens": [
                {"autor": "Diretor Geral", "criado_em": "2026-11-16T14:05:00+00:00", "texto": "A opção B, por favor."},
                {
                    "autor": "Diretor Geral",
                    "criado_em": "2026-11-16T14:07:30+00:00",
                    "texto": "E manda o relatório na segunda.",
                },
            ]
        }
