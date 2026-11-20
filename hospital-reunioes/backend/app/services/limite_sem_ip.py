"""Limite de envios por aparelho sem guardar o endereço (issue #1986).

A peça da decisão 10 da ADR 0097, construída como serviço comum na ADR 0107
(decisão 6): o Núcleo de Segurança do Paciente usa no formulário público, e o
Canal de Conduta reusa sem construir o dele.

O limitador conta por uma chave que é o resumo HMAC do endereço com um sal que
nasce na memória do processo e é trocado a cada 24 horas. O sal nunca é gravado:
sem ele, a chave não volta ao endereço, e depois da troca nem quem tem acesso ao
processo liga a chave de ontem ao aparelho de hoje. A rota que usa o serviço
também sai do log de requisições sem endereço (`rota_sem_endereco`).

Uso, abaixo do decorador da rota, numa função que recebe `request: Request`:

    @router.post("/publico/notificacoes")
    @limite_sem_ip.limitar("5/minute;20/hour")
    async def notificar(request: Request, ...): ...
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable

from slowapi.util import get_remote_address
from starlette.requests import Request

from app.limiter import limiter

# O sal vale por um dia. Trocar mais vezes encurta a janela em que duas chaves
# ligam o mesmo aparelho; trocar menos estica. O preço da troca é que a conta do
# limite recomeça na virada, o que dá a um aparelho no máximo um lote a mais.
DURACAO_DO_SAL = 24 * 60 * 60


class SalRotativo:
    """Um sal em memória que se renova sozinho ao passar `duracao` segundos."""

    def __init__(self, relogio: Callable[[], float] = time.monotonic, duracao: float = DURACAO_DO_SAL) -> None:
        self._relogio = relogio
        self._duracao = duracao
        self._valor = secrets.token_bytes(32)
        self._nascido_em = relogio()

    def atual(self) -> bytes:
        agora = self._relogio()
        if agora - self._nascido_em >= self._duracao:
            self._valor = secrets.token_bytes(32)
            self._nascido_em = agora
        return self._valor


_sal = SalRotativo()


def chave_do_aparelho(request: Request) -> str:
    """O que o limitador guarda no lugar do endereço."""
    endereco = get_remote_address(request).encode()
    return "sem-ip:" + hmac.new(_sal.atual(), endereco, hashlib.sha256).hexdigest()


# A marca que a rota limitada carrega e o log de requisições lê.
_MARCA = "_limite_sem_ip"


def limitar(limite: str):
    """Limita a rota por aparelho, com a chave sem endereço, e tira o endereço
    da linha de log dela."""

    def decorar(funcao):
        envolvida = limiter.limit(limite, key_func=chave_do_aparelho)(funcao)
        setattr(envolvida, _MARCA, True)
        return envolvida

    return decorar


def rota_sem_endereco(scope: dict) -> bool:
    """A requisição caiu numa rota que usa o serviço?

    Lê a rota que o roteador casou (`scope["endpoint"]`), e não o path: a rota
    nova já nasce fora do log ao usar o serviço, sem lista para lembrar de
    atualizar. Vale também para a recusa da validação (422), que acontece depois
    de o roteador casar a rota e antes de o limitador rodar.
    """
    return getattr(scope.get("endpoint"), _MARCA, False) is True
