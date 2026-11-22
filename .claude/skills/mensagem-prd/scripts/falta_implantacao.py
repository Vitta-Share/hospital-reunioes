#!/usr/bin/env python3
"""O que falta para usar a entrega do PRD (issue #2213, ADR 0111, decisão 11).

Uso:
  python3 .claude/skills/mensagem-prd/scripts/falta_implantacao.py <PRD>

Pede à ponte de automação os Pedidos de implantação abertos da Demanda do PRD
e imprime a linha da mensagem, com o Assunto de cada um:

  Para começar a usar, falta: testar o Canal, treinar a recepção e divulgar.

Saída 0 com a linha, ou sem imprimir nada quando não há Pedido de
implantação aberto ou o PRD não tem Demanda no app (a mensagem fica como era).
Saída 1 com o motivo no stderr quando não deu para perguntar ao app (chave
ausente, ponte desligada, app fora do ar): quem chama não pode tratar isso como
"nada falta". Saída 2 no uso errado.

Mesmo endereço e mesma chave do `pegar-issue/scripts/anexos.py`
(`HOSPITAL_API_URL` e `TECNOLOGIA_AUTOMACAO_API_KEY`). A chave nunca é impressa.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pegar-issue" / "scripts"))
import anexos  # noqa: E402
import conversa  # noqa: E402

ABERTURA = "Para começar a usar, falta:"


def juntar(itens: list[str]) -> str:
    """"a", "a e b", "a, b e c"."""
    if len(itens) == 1:
        return itens[0]
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


def main(argv: list[str], env=os.environ) -> int:
    if len(argv) != 1 or not argv[0].isdigit():
        print("uso: falta_implantacao.py <PRD>", file=sys.stderr)
        return 2
    chave_api = anexos.chave(env)
    if not chave_api:
        print(f"Não deu para ler a implantação: falta {anexos.CHAVE} no tokens/.env.", file=sys.stderr)
        return 1
    caminho = f"/automacao/tecnologia/projetos/{conversa.PROJETO}/issues/{argv[0]}/implantacao"
    try:
        lida = conversa.pedir(anexos.base_da_api(env), caminho, chave_api)
    except conversa.Falha as falha:
        print(f"Não deu para ler a implantação: {falha}.", file=sys.stderr)
        return 1
    assuntos = [p["assunto"].strip() for p in (lida or {}).get("pedidos", []) if (p.get("assunto") or "").strip()]
    if assuntos:
        print(f"{ABERTURA} {juntar(assuntos)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
