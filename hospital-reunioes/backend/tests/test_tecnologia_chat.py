"""Os dubles da aba Tecnologia que os testes da lista e das Entregas usam.

O chat do Assistente de Tecnologia saiu do app na issue #2279 (ADR 0113,
decisao 7), e os testes dele sairam junto. Ficam aqui o endereco da lista
(`CHAT`, o `GET /chat` que o Quadro le), os Produtos, as fixtures que deixam
o modelo em modo mock e a integracao do GitHub configurada, e o `_cenario`,
que monta a aba com o Supabase e o GitHub em memoria.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_anexos import _StorageFake  # noqa: E402
from test_tecnologia_vinculo import BASE, DIRETOR, _montar  # noqa: E402

from app.config import settings  # noqa: E402
from app.limiter import limiter  # noqa: E402

CHAT = f"{BASE}/chat"

PRODUTOS = [
    {"id": "prod-1", "nome": "Reuniões", "ativo": True, "ordem": 1, "dono_id": "P1"},
    {"id": "prod-2", "nome": "Ouvidoria", "ativo": True, "ordem": 2, "dono_id": "P1"},
]


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _llm_em_mock(monkeypatch):
    """O pytest carrega o `.env` real (chave de PROD): sem isto, o teste que
    esquecesse de dublar o modelo chamaria o provedor de verdade."""
    from app.services import ai_processor

    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "mock")
    yield


@pytest.fixture(autouse=True)
def _integracao_configurada(monkeypatch):
    monkeypatch.setattr(settings, "github_integracao_token", "token-de-teste")
    monkeypatch.setattr(settings, "github_integracao_repo", "pedrorezendefig/hospital-reunioes")


def _cenario(monkeypatch, *, logado=DIRETOR, **kw):
    client, sb, gh = _montar(logado=logado, monkeypatch=monkeypatch, **kw)
    sb.tabelas["tecnologia_produtos"] = [dict(p) for p in PRODUTOS]
    sb.storage = _StorageFake()
    return client, sb, gh


def _demandas(sb) -> list[dict]:
    return sb.tabelas["tecnologia_demandas"]


def _conversas(sb) -> list[dict]:
    return sb.tabelas.setdefault("tecnologia_planejamentos", [])


