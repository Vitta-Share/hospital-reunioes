"""O cliente da Anthropic do app inteiro, com chave reserva (issue #1925).

Quando o crédito de uma conta acaba, a API recusa a chamada com o erro de
saldo (`billing_error`, 402, ou o 400 "credit balance is too low"), e a
recusa não é cobrada. Aqui a mesma chamada é refeita com a próxima chave
(`ANTHROPIC_API_KEY` primeiro, depois as de `ANTHROPIC_API_KEYS_RESERVA` na
ordem cadastrada), e a chave sem saldo fica esgotada por uma hora, em
memória do processo: passada a hora, volta a ser tentada na sua vez, porque
o crédito renova em datas diferentes em cada conta.

Só o erro de saldo troca de chave. Rede, 429, 5xx e validação sobem como
sempre subiram, para o chamador tratar como hoje. Sem chave com saldo, a
esgotada ainda é tentada por último: assim sobe o mesmo erro de hoje, e a
conta que recebeu crédito volta na hora, sem esperar o fim da hora.

O cliente expõe `messages.create` e `messages.stream`, que é o que os
chamadores usam (chamada simples, streaming e laço de ferramentas, onde cada
volta é um `create`). O log diz o apelido da chave, nunca a chave.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

ESGOTADA_POR_S = 60 * 60


def sem_saldo(erro: BaseException) -> bool:
    """O erro de saldo da Anthropic: `billing_error` (402) ou o 400 com a
    mensagem de crédito baixo."""
    if not isinstance(erro, anthropic.APIStatusError):
        return False
    if erro.status_code == 402 or erro.type == "billing_error":
        return True
    return erro.status_code == 400 and "credit balance is too low" in str(erro.message).lower()


def _apelido(posicao: int) -> str:
    return "principal" if posicao == 0 else f"reserva {posicao}"


def _chaves() -> list[str]:
    reservas = [chave.strip() for chave in settings.anthropic_api_keys_reserva.split(",")]
    return [settings.anthropic_api_key, *(chave for chave in reservas if chave)]


class ChavesEsgotadas:
    """As chaves sem saldo e até quando ficam de lado. O relógio é injetável
    para o teste andar a hora."""

    def __init__(self, relogio: Callable[[], float] = time.monotonic):
        self._relogio = relogio
        self._ate: dict[str, float] = {}
        self._trava = threading.Lock()

    def marcar(self, chave: str) -> None:
        with self._trava:
            self._ate[chave] = self._relogio() + ESGOTADA_POR_S

    def esgotada(self, chave: str) -> bool:
        with self._trava:
            return self._ate.get(chave, 0.0) > self._relogio()


ESGOTADAS = ChavesEsgotadas()


class _Mensagens:
    def __init__(self, cliente: ClienteDaAnthropic):
        self._cliente = cliente

    def create(self, **kwargs: Any) -> Any:
        return self._cliente._com_reserva(lambda sdk: sdk.messages.create(**kwargs))

    def stream(self, **kwargs: Any) -> _StreamComReserva:
        return _StreamComReserva(self._cliente, kwargs)


class _StreamComReserva:
    """O `with client.messages.stream(...)`: o pedido sai na entrada do
    `with`, e é ali que o erro de saldo aparece e a chave troca."""

    def __init__(self, cliente: ClienteDaAnthropic, kwargs: dict[str, Any]):
        self._cliente = cliente
        self._kwargs = kwargs
        self._gerente: Any = None

    def __enter__(self) -> Any:
        def abrir(sdk: anthropic.Anthropic) -> Any:
            gerente = sdk.messages.stream(**self._kwargs)
            fluxo = gerente.__enter__()
            self._gerente = gerente
            return fluxo

        return self._cliente._com_reserva(abrir)

    def __exit__(self, *excecao: Any) -> None:
        if self._gerente is not None:
            self._gerente.__exit__(*excecao)


class ClienteDaAnthropic:
    """O lugar do `anthropic.Anthropic(...)` no app. `opcoes` vão para o SDK
    de cada chave (`max_retries`, `timeout`)."""

    def __init__(self, **opcoes: Any):
        self._opcoes = opcoes
        self._sdks: dict[int, anthropic.Anthropic] = {}
        self.messages = _Mensagens(self)

    def _sdk(self, posicao: int, chave: str) -> anthropic.Anthropic:
        if posicao not in self._sdks:
            self._sdks[posicao] = anthropic.Anthropic(api_key=chave, **self._opcoes)
        return self._sdks[posicao]

    def _com_reserva(self, chamar: Callable[[anthropic.Anthropic], Any]) -> Any:
        chaves = list(enumerate(_chaves()))
        com_saldo = [(p, c) for p, c in chaves if not ESGOTADAS.esgotada(c)]
        esgotadas = [(p, c) for p, c in chaves if ESGOTADAS.esgotada(c)]
        ordem = com_saldo + esgotadas
        for indice, (posicao, chave) in enumerate(ordem):
            try:
                return chamar(self._sdk(posicao, chave))
            except anthropic.APIStatusError as erro:
                if not sem_saldo(erro):
                    raise
                ESGOTADAS.marcar(chave)
                if indice + 1 == len(ordem):
                    raise
                logger.warning(
                    "[IA] Chave %s sem saldo (HTTP %s): esgotada por 1 hora, a chamada vai para a %s",
                    _apelido(posicao),
                    erro.status_code,
                    _apelido(ordem[indice + 1][0]),
                )
        raise AssertionError("sem chave da Anthropic")  # pragma: no cover, há sempre a principal


def cliente_da_anthropic(**opcoes: Any) -> ClienteDaAnthropic:
    """O cliente da Anthropic com as chaves reserva. Quem chama confere antes
    que `ANTHROPIC_API_KEY` não está vazia."""
    return ClienteDaAnthropic(**opcoes)
