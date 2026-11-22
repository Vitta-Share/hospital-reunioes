"""O aviso de assunto fora do canal na revisão do relato (issue #1848, PRD
#1786, especificação seções 4.1 e P5, Anexo A saída reduzida; ADR 0097
decisões 6 e 7).

Ao abrir a revisão, a tela pública pergunta uma vez à rota
`POST /api/conduta/relatos/aviso` se o texto parece de outro destino. A rota
devolve só o destino do aviso (`DP`, `OUVIDORIA`, `NSP`, `GESTAO`) ou nada.
O aviso só existe quando o agente diz que parece fora e que não há termo da
regra de proteção. Teto, falha ou agente desligado: sem aviso, e o envio
segue.

O banco é o dublê de `conduta_apoio`, com a função da cota; o modelo é um
dublê que guarda o que recebeu. Nenhum teste chama a IA de verdade.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

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
from app.middleware.request_context import RequestContextMiddleware  # noqa: E402
from app.routers import conduta_publico  # noqa: E402
from app.services.conduta import agente_de_triagem, aviso_fora_do_canal  # noqa: E402

AVISO = "/api/conduta/relatos/aviso"
CONTRACHEQUE = "Meu contracheque veio sem o adicional noturno de outubro."
EMERGENCIA = "Esperei quatro horas na emergência com minha mãe e ninguém deu informação."


def saida(parece_fora="SIM", destino="DP", termo="NAO") -> dict:
    return {"parece_fora": parece_fora, "destino": destino, "tem_termo_de_protecao": termo}


class Modelo:
    """O dublê do cliente da Anthropic: guarda cada chamada e devolve a saída
    combinada, ou levanta quando `falha` é uma exceção."""

    def __init__(self, resposta: dict | str | None = None, falha: Exception | None = None):
        self.resposta = resposta if resposta is not None else saida()
        self.falha = falha
        self.chamadas: list[dict] = []
        self.messages = self

    def create(self, **argumentos):
        self.chamadas.append(argumentos)
        if self.falha:
            raise self.falha
        texto = self.resposta if isinstance(self.resposta, str) else json.dumps(self.resposta)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=texto)])

    def texto_enviado(self) -> str:
        return "\n".join(m["content"] for chamada in self.chamadas for m in chamada["messages"])


class BancoComCota(Banco):
    """O dublê com a função da cota do agente (migration 200), a mesma da
    triagem do caso."""

    def __init__(self, *, teto_atingido: bool = False):
        super().__init__()
        self.teto_atingido = teto_atingido
        self.reservas = 0

    def rpc(self, nome, parametros):
        assert nome == agente_de_triagem.FUNCAO_DA_COTA
        assert parametros == {"p_teto": agente_de_triagem.TETO_DIARIO}
        self.reservas += 1
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[{"reservada": not self.teto_atingido}]))


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "conduta_canal_aberto", True)
    monkeypatch.setattr(settings, "conduta_agente_ligado", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def modelo(monkeypatch) -> Modelo:
    duble = Modelo()
    monkeypatch.setattr(aviso_fora_do_canal, "_cliente", lambda: duble)
    return duble


@pytest.fixture
def banco() -> BancoComCota:
    return BancoComCota()


def _cliente(banco) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(conduta_publico.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app, raise_server_exceptions=False)


def _aviso(banco, relato: str) -> dict:
    resposta = _cliente(banco).post(AVISO, json={"relato": relato})
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["cache-control"] == "no-store"
    return resposta.json()


# ═══════════════════════════════════════════════════════════════════════════
# 1 e 2. Assunto de DP e de atendimento a paciente mostram o aviso
# ═══════════════════════════════════════════════════════════════════════════


def test_relato_de_assunto_de_dp_recebe_o_aviso_do_dp(banco, modelo):
    assert _aviso(banco, CONTRACHEQUE) == {"aviso": "DP"}
    assert len(modelo.chamadas) == 1
