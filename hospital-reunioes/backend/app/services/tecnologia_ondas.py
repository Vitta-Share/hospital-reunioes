"""A Onda de cada parte da Demanda (issue #1902, ADR 0100, decisao 3).

Puro: recebe as partes como a foto as guarda (numero e bloqueadoras) e devolve
a Onda de cada uma, na mesma ordem. Nao le banco nem GitHub.

A regra:

- Onda 1 e a parte que nao espera outra parte da MESMA Demanda.
- As demais ficam uma Onda depois da maior Onda das partes que elas esperam.
- O bloqueio ja resolvido conta: a sequencia nao muda quando uma parte fecha.
- Bloqueadora de outro pedido nao muda a Onda.
- Ciclo nao quebra a tela: as partes do ciclo ficam na Onda 1, e quem espera
  uma delas fica uma Onda depois.
"""

from __future__ import annotations

from typing import Any


def _esperadas(partes: list[dict[str, Any]]) -> dict[int, set[int]]:
    """Para cada parte, os numeros das partes da mesma Demanda que ela espera."""
    numeros = {p.get("numero") for p in partes if isinstance(p.get("numero"), int)}
    esperadas: dict[int, set[int]] = {}
    for parte in partes:
        numero = parte.get("numero")
        if not isinstance(numero, int):
            continue
        esperadas[numero] = {
            b["numero"]
            for b in (parte.get("bloqueadoras") or [])
            if isinstance(b, dict) and b.get("da_demanda") and b.get("numero") in numeros
        }
    return esperadas


def _no_ciclo(esperadas: dict[int, set[int]]) -> set[int]:
    """As partes que, seguindo o que esperam, voltam a si mesmas."""
    ciclo: set[int] = set()
    for inicio in esperadas:
        vistos: set[int] = set()
        pilha = list(esperadas[inicio])
        while pilha:
            atual = pilha.pop()
            if atual == inicio:
                ciclo.add(inicio)
                break
            if atual in vistos:
                continue
            vistos.add(atual)
            pilha.extend(esperadas.get(atual, ()))
    return ciclo


def ondas_das_partes(partes: list[dict[str, Any]]) -> list[int]:
    """A Onda de cada parte, na ordem da lista. Parte sem numero fica na Onda 1."""
    esperadas = _esperadas(partes)
    ciclo = _no_ciclo(esperadas)
    ondas: dict[int, int] = {}

    def onda(numero: int) -> int:
        if numero not in ondas:
            if numero in ciclo:
                ondas[numero] = 1
            else:
                # Sem ciclo fora de `ciclo`, a recursao sempre termina: quem
                # voltasse a si mesmo estaria nele.
                ondas[numero] = 1 + max((onda(b) for b in esperadas[numero]), default=0)
        return ondas[numero]

    return [onda(p["numero"]) if isinstance(p.get("numero"), int) else 1 for p in partes]
