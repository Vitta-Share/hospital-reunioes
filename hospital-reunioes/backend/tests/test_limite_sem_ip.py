"""Limite de envios sem IP (issue #1986, ADR 0107 decisão 6, ADR 0097 decisão 10).

O formulário público do Núcleo (e, depois, o do Canal de Conduta) precisa de
limite de envios por aparelho sem que nada guarde o endereço de quem envia. O
que o limitador guarda é um resumo do endereço com um sal que só existe na
memória do processo e é trocado a cada 24 horas; a linha do log das rotas que
usam o serviço sai sem endereço nenhum.

Tudo é exercitado pela rota (TestClient), com o limitador, o middleware de log
e o tratamento do 429 de produção: testar só a função da chave deixaria verde
uma rota que esquecesse de usá-la.
"""

from __future__ import annotations

import logging
import os
import sys
import types

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from limits.storage import memory as armazenamento_em_memoria
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import JsonFormatter, RequestContextMiddleware  # noqa: E402
from app.services import limite_sem_ip  # noqa: E402

IP_DO_APARELHO = "203.0.113.9"
OUTRO_APARELHO = "198.51.100.77"
UM_DIA = 24 * 60 * 60


class _Relogio:
    """Relógio que só anda quando o teste manda."""

    def __init__(self, inicio: float = 1_000_000.0) -> None:
        self.agora = inicio

    def __call__(self) -> float:
        return self.agora

    def andar(self, segundos: float) -> None:
        self.agora += segundos


class _CapturaJson(logging.Handler):
    """A linha que sai no stdout do container, já formatada pelo JsonFormatter."""

    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.linhas: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.linhas.append(self.format(record))


@pytest.fixture
def relogio_do_limite(monkeypatch):
    """O tempo que a janela do limitador enxerga (o armazenamento em memória do
    `limits` lê `time.time()` do próprio módulo)."""
    relogio = _Relogio()
    monkeypatch.setattr(armazenamento_em_memoria, "time", types.SimpleNamespace(time=relogio))
    return relogio


@pytest.fixture
def relogio_do_sal(monkeypatch):
    relogio = _Relogio()
    monkeypatch.setattr(limite_sem_ip, "_sal", limite_sem_ip.SalRotativo(relogio=relogio))
    return relogio


@pytest.fixture(autouse=True)
def _limitador_zerado():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def log():
    captura = _CapturaJson()
    raiz = logging.getLogger()
    nivel = raiz.level
    raiz.addHandler(captura)
    raiz.setLevel(logging.INFO)
    yield captura
    raiz.removeHandler(captura)
    raiz.setLevel(nivel)


def _montar_app() -> FastAPI:
    """Montada uma vez: o slowapi acumula os limites por nome de função, e
    decorar de novo a cada teste contaria cada envio duas vezes."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestContextMiddleware)

    @app.post("/api/publico/notificar")
    @limite_sem_ip.limitar("2/minute")
    async def notificar(request: Request):
        return {"ok": True}

    @app.post("/api/interno/outra")
    async def outra(request: Request):
        return {"ok": True}

    return app


_APP = _montar_app()


def _cliente(ip: str = IP_DO_APARELHO) -> TestClient:
    return TestClient(_APP, client=(ip, 44321))


def test_mesmo_aparelho_e_barrado_na_janela_e_liberado_depois_dela(relogio_do_limite, relogio_do_sal):
    cliente = _cliente()

    assert cliente.post("/api/publico/notificar").status_code == 200
    assert cliente.post("/api/publico/notificar").status_code == 200
    assert cliente.post("/api/publico/notificar").status_code == 429

    # Outro aparelho tem a conta dele: o limite é por aparelho, não da rota.
    assert _cliente(OUTRO_APARELHO).post("/api/publico/notificar").status_code == 200

    relogio_do_limite.andar(61)
    assert cliente.post("/api/publico/notificar").status_code == 200
