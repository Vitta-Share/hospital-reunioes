#!/usr/bin/env python3
"""O que falta para usar a entrega do PRD (issue #2271, ADR 0113, decisão 9).

Uso:
  python3 .claude/skills/mensagem-prd/scripts/falta_implantacao.py <PRD>

Lê no GitHub os Cards de implantação abertos do PRD (sub-issues abertas com a
label `implantacao`) e imprime a linha da mensagem, com o título de cada um:

  Para começar a usar, falta: Testar o Canal, Treinar a recepção e Divulgar.

Saída 0 com a linha, ou sem imprimir nada quando não há Card de implantação
aberto (a mensagem fica como era). Saída 1 com o motivo no stderr quando o
`gh` falhou: quem chama não pode tratar isso como "nada falta". Saída 2 no uso
errado.
"""

from __future__ import annotations

import json
import subprocess
import sys

ABERTURA = "Para começar a usar, falta:"
LABEL = "implantacao"


def juntar(itens: list[str]) -> str:
    """"a", "a e b", "a, b e c"."""
    if len(itens) == 1:
        return itens[0]
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print("uso: falta_implantacao.py <PRD>", file=sys.stderr)
        return 2
    feito = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", f"repos/{{owner}}/{{repo}}/issues/{argv[0]}/sub_issues"],
        capture_output=True,
        text=True,
    )
    if feito.returncode != 0:
        print(f"Não deu para ler os Cards de implantação: {feito.stderr.strip()}", file=sys.stderr)
        return 1
    cards = [card for pagina in json.loads(feito.stdout) for card in pagina]
    titulos = [
        card["title"].strip()
        for card in cards
        if card.get("state") == "open" and any(label.get("name") == LABEL for label in card.get("labels", []))
    ]
    if titulos:
        print(f"{ABERTURA} {juntar(titulos)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
