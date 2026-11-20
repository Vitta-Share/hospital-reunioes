"""A regra do ciclo de vida da Pendência (ADR 0098, decisões 4 e 5; issue #1862).

Função pura: recebe quem age, o comando e o estado atual, e devolve a mudança
(estado, prazo, conclusão e se conta atraso) ou recusa. Não lê nem grava
nada; quem grava é a função `registrar_acao_da_pendencia` do Postgres
(migration 169), que atualiza a Pendência e insere o evento no Histórico na
mesma transação.

O banco guarda quatro estados. Atrasada é calculada (aberta com prazo
vencido) e Repactuada também (há Repactuação no histórico).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Comando(StrEnum):
    INICIAR = "iniciar"
    ANOTAR = "anotar"
    CONCLUIR = "concluir"
    REPACTUAR = "repactuar"
    CANCELAR = "cancelar"
    REABRIR = "reabrir"


class Papel(StrEnum):
    RESPONSAVEL = "responsavel"
    CO_RESPONSAVEL = "co_responsavel"
    FACILITADOR = "facilitador"
    SUPER_ADMIN = "super_admin"


ABERTOS = frozenset({"PENDENTE", "EM_PROGRESSO"})
FECHADOS = frozenset({"CONCLUIDO", "CANCELADO"})

_DO_RESPONSAVEL = frozenset({Comando.INICIAR, Comando.ANOTAR, Comando.CONCLUIR, Comando.REPACTUAR})

PERMISSOES: dict[Papel, frozenset[Comando]] = {
    Papel.RESPONSAVEL: _DO_RESPONSAVEL,
    Papel.CO_RESPONSAVEL: _DO_RESPONSAVEL,
    Papel.FACILITADOR: frozenset({Comando.REPACTUAR, Comando.CANCELAR, Comando.REABRIR}),
    Papel.SUPER_ADMIN: frozenset(Comando),
}

# De onde cada comando parte.
_PARTIDA: dict[Comando, frozenset[str]] = {
    Comando.INICIAR: frozenset({"PENDENTE"}),
    Comando.ANOTAR: ABERTOS,
    Comando.CONCLUIR: ABERTOS,
    Comando.REPACTUAR: ABERTOS,
    Comando.CANCELAR: ABERTOS,
    Comando.REABRIR: FECHADOS,
}

_COM_PRAZO_NOVO = frozenset({Comando.REPACTUAR, Comando.REABRIR})


class AcaoRecusada(Exception):  # noqa: N818, o nome do domínio
    """`tipo`: `permissao` (quem age não pode), `transicao` (não parte deste
    estado) ou `dados` (anotação vazia, prazo novo ausente ou no passado)."""

    def __init__(self, tipo: str, motivo: str):
        super().__init__(motivo)
        self.tipo = tipo
        self.motivo = motivo


@dataclass(frozen=True)
class Mudanca:
    status: str
    prazo: date | None
    # True grava a data de conclusão, False a apaga, None não mexe.
    concluida: bool | None
    # Repactuação ou Reabertura feita com o prazo já vencido (ranking).
    conta_atraso: bool


def esta_atrasada(status: str, prazo: date | None, hoje: date) -> bool:
    """O prazo de um dia só vence quando esse dia acaba."""
    return status in ABERTOS and prazo is not None and prazo < hoje


def situacao(status: str, prazo: date | None, hoje: date, *, repactuada: bool) -> str:
    """O que a tela mostra: o estado gravado, ou ATRASADO e REPACTUADA,
    calculados, para a Pendência aberta."""
    if esta_atrasada(status, prazo, hoje):
        return "ATRASADO"
    if status in ABERTOS and repactuada:
        return "REPACTUADA"
    return status


def _permitidos(papeis: Iterable[Papel]) -> frozenset[Comando]:
    return frozenset().union(*(PERMISSOES[p] for p in papeis))


def acoes_disponiveis(papeis: Iterable[Papel], status: str) -> list[Comando]:
    """Os comandos que quem age pode dar agora, na ordem do enum."""
    permitidos = _permitidos(papeis)
    return [c for c in Comando if c in permitidos and status in _PARTIDA[c]]


def decidir(
    comando: Comando,
    papeis: Iterable[Papel],
    *,
    status: str,
    prazo: date | None,
    hoje: date,
    anotacao: str | None,
    prazo_novo: date | None = None,
) -> Mudanca:
    if comando not in _permitidos(papeis):
        raise AcaoRecusada("permissao", "Você não pode fazer esta ação nesta pendência.")
    if not (anotacao or "").strip():
        raise AcaoRecusada("dados", "Escreva a anotação: toda ação na pendência pede uma.")
    if status not in _PARTIDA[comando]:
        raise AcaoRecusada("transicao", f"Esta ação não vale para uma pendência {status}.")

    if comando in _COM_PRAZO_NOVO:
        if prazo_novo is None:
            raise AcaoRecusada("dados", "Informe o prazo novo.")
        if prazo_novo < hoje:
            raise AcaoRecusada("dados", "O prazo novo não pode estar no passado.")
    elif prazo_novo is not None:
        raise AcaoRecusada("dados", "Só repactuar e reabrir mudam o prazo.")

    vencido = prazo is not None and prazo < hoje

    if comando is Comando.INICIAR:
        return Mudanca("EM_PROGRESSO", prazo, None, False)
    if comando is Comando.ANOTAR:
        return Mudanca(status, prazo, None, False)
    if comando is Comando.CONCLUIR:
        return Mudanca("CONCLUIDO", prazo, True, False)
    if comando is Comando.CANCELAR:
        return Mudanca("CANCELADO", prazo, None, False)
    if comando is Comando.REPACTUAR:
        return Mudanca(status, prazo_novo, None, vencido)
    # REABRIR
    return Mudanca("PENDENTE", prazo_novo, False, vencido)
