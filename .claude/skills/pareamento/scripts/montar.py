#!/usr/bin/env python3
"""Monta a página do pareamento a partir do estado.json e do descricoes.json.

Junta o estado coletado com as descrições funcionais, calcula as filas de bloqueio
(o que solta o quê) e grava `pareamento.html` na pasta do pareamento, pronto para
publicar como Artifact. O corpo das issues não vai para a página.

Uso: python3 .claude/skills/pareamento/scripts/montar.py [--pasta DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MODELO = AQUI.parent / "references" / "modelo.html"
RAIZ = Path(__file__).resolve().parents[4]
PASTA = RAIZ / "local" / "pareamento"
CAMPOS = ("para_que_serve", "o_que_muda", "como_acaba", "por_que_com_quem")


def filas(cards: dict) -> list[dict]:
    """Componentes ligados por bloqueio, com 2 cards ou mais, em camadas.

    A camada de um card é 0 se nada do componente o segura, senão 1 mais a maior
    camada de quem o segura. O título da fila é o PRD mais comum dos cards dela.
    """
    vizinhos: dict[str, set[str]] = {k: set() for k in cards}
    for k, c in cards.items():
        for o in c["espera"] + c["segura"]:
            if o in cards:
                vizinhos[k].add(o)
                vizinhos[o].add(k)
    vistos: set[str] = set()
    saida = []
    for k in sorted(cards, key=lambda x: (x.split("#")[0], int(x.split("#")[1]))):
        if k in vistos or not vizinhos[k]:
            continue
        comp, pilha = set(), [k]
        while pilha:
            x = pilha.pop()
            if x in comp:
                continue
            comp.add(x)
            pilha.extend(vizinhos[x] - comp)
        vistos |= comp
        camada: dict[str, int] = {}

        def nivel(x: str, caminho: frozenset = frozenset()) -> int:
            if x in camada:
                return camada[x]
            antes = [e for e in cards[x]["espera"] if e in comp and e not in caminho]
            camada[x] = 0 if not antes else 1 + max(nivel(e, caminho | {x}) for e in antes)
            return camada[x]

        for x in comp:
            nivel(x)
        n = max(camada.values()) + 1
        camadas = [sorted((x for x in comp if camada[x] == i), key=lambda s: int(s.split("#")[1])) for i in range(n)]
        prds = Counter(cards[x]["prd"] for x in comp if cards[x].get("prd"))
        saida.append({"prd": prds.most_common(1)[0][0] if prds else None, "camadas": camadas})
    return saida


def dados_da_pagina(estado: dict, descricoes: dict) -> tuple[dict, list[str]]:
    cards = {}
    sem = []
    for k, c in estado["cards"].items():
        d = descricoes.get(k) or {}
        if not c.get("satelite") and not d:
            sem.append(k)
        cards[k] = {**{x: y for x, y in c.items() if x != "corpo"}, "desc": {f: d.get(f, "") for f in CAMPOS}}
    prds = []
    for p in estado["projetos"]:
        for prd in p["prds"]:
            d = descricoes.get(prd["chave"]) or {}
            prds.append({**{x: y for x, y in prd.items() if x != "corpo"}, "projeto": p["nome"],
                         "desc": {f: d.get(f, "") for f in CAMPOS}})
    projetos = [{x: y for x, y in p.items() if x != "prds"} for p in estado["projetos"]]
    return {
        "gerado_em": estado["gerado_em"],
        "eu": estado["eu"],
        "diretor": estado["diretor"],
        "projetos": projetos,
        "prds": prds,
        "cards": cards,
        "filas": filas(estado["cards"]),
    }, sem


def html(dados: dict) -> str:
    modelo = MODELO.read_text(encoding="utf-8")
    bruto = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    return modelo.replace("/*DADOS*/null", bruto)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", type=Path, default=PASTA)
    args = ap.parse_args()
    estado = json.loads((args.pasta / "estado.json").read_text(encoding="utf-8"))
    arq = args.pasta / "descricoes.json"
    descricoes = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    dados, sem = dados_da_pagina(estado, descricoes)
    saida = args.pasta / "pareamento.html"
    saida.write_text(html(dados), encoding="utf-8")
    print(f"página: {saida}")
    if sem:
        print(f"atenção: {len(sem)} cards sem descrição: {', '.join(sem)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
