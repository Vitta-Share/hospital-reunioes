"""Chave de API reserva quando o crédito da principal acaba (issue #1925).

O SDK `anthropic` é o de verdade: só o transporte HTTP é trocado
(`httpx2.MockTransport`), e o dublê responde conforme a chave que veio no
pedido. Assim o teste lê o que sairia para a Anthropic e qual chave foi usada,
pelos mesmos pontos que o app usa (`ai_processor._get_llm`, `ia._cliente` de
Contas médicas e `ouvidoria_agente_triagem._cliente`). Nenhum chega à rede.
"""

from __future__ import annotations

import json
import logging
import os
import sys

import anthropic
import httpx2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anthropic_apoio import erro, mensagem  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import ai_processor, ia_chaves, ouvidoria_agente_triagem  # noqa: E402
from app.services.contas_medicas import ia as contas_ia  # noqa: E402

PRINCIPAL = "sk-ant-principal-plantada"
RESERVA_1 = "sk-ant-reserva-um-plantada"
RESERVA_2 = "sk-ant-reserva-dois-plantada"
TODAS = (PRINCIPAL, RESERVA_1, RESERVA_2)

SEM_SALDO_402 = ("billing_error", 402, "Your credit balance is too low to access the Anthropic API.")
SEM_SALDO_400 = (
    "invalid_request_error",
    400,
    "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade.",
)


class Relogio:
    """O relógio das chaves esgotadas, que o teste anda à mão."""

    def __init__(self):
        self.agora = 1_000_000.0

    def __call__(self) -> float:
        return self.agora

    def andar(self, segundos: float) -> None:
        self.agora += segundos


class Anthropic:
    """A API de mentira: cada chave responde do jeito que o teste mandar.
    Guarda a chave de cada pedido, na ordem."""

    def __init__(self):
        self.respostas: dict[str, httpx2.Response] = {}
        self.chaves_usadas: list[str] = []

    def sem_saldo(self, chave: str, forma=SEM_SALDO_402) -> None:
        tipo, status, texto = forma
        self.respostas[chave] = erro(status, tipo, texto)

    def falhar(self, chave: str, status: int, tipo: str, texto: str) -> None:
        self.respostas[chave] = erro(status, tipo, texto)

    def __call__(self, pedido: httpx2.Request) -> httpx2.Response:
        cabecalhos = pedido.headers
        chave = cabecalhos.get("x-api-key") or cabecalhos.get("authorization", "").removeprefix("Bearer ")
        self.chaves_usadas.append(chave)
        resposta = self.respostas.get(chave)
        if resposta is not None:
            return httpx2.Response(resposta.status_code, content=resposta.content, headers=resposta.headers)
        corpo = mensagem(f"resposta da {_apelido(chave)}")
        if json.loads(pedido.content or b"{}").get("stream"):
            from anthropic_apoio import _eventos_do_stream

            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_eventos_do_stream(corpo))
        return httpx2.Response(200, json=corpo)


def _apelido(chave: str) -> str:
    return {PRINCIPAL: "principal", RESERVA_1: "reserva 1", RESERVA_2: "reserva 2"}.get(chave, "outra")


@pytest.fixture
def api(monkeypatch) -> Anthropic:
    """Todo `anthropic.Anthropic(...)` construído no teste fala com a API de
    mentira, mantendo os argumentos de quem construiu."""
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    falsa = Anthropic()
    original = anthropic.Anthropic

    def construir(**kwargs):
        kwargs.pop("max_retries", None)
        transporte = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(falsa))
        return original(**kwargs, http_client=transporte, max_retries=0)

    monkeypatch.setattr(anthropic, "Anthropic", construir)
    return falsa


@pytest.fixture
def relogio(monkeypatch) -> Relogio:
    """As chaves esgotadas começam vazias em cada teste, no relógio do teste."""
    relogio = Relogio()
    monkeypatch.setattr(ia_chaves, "ESGOTADAS", ia_chaves.ChavesEsgotadas(relogio=relogio))
    return relogio


@pytest.fixture
def com_reservas(monkeypatch, relogio):
    monkeypatch.setattr(settings, "anthropic_api_key", PRINCIPAL)
    monkeypatch.setattr(settings, "anthropic_api_keys_reserva", f"{RESERVA_1}, {RESERVA_2}")


def _chat() -> str:
    client, model = ai_processor._get_llm()
    return ai_processor._pedir_texto(client, model, system="instrucao", conteudo="oi")


class TestReservaAssumeQuandoOSaldoAcaba:
    def test_saldo_acabado_na_principal_refaz_a_chamada_na_reserva(self, api, com_reservas):
        api.sem_saldo(PRINCIPAL)

        assert _chat() == "resposta da reserva 1"
        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1]
