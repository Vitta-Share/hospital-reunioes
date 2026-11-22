"""O `.like()` do PostgREST para os dublês do banco (issue #2085).

A numeração `A###` das Pendências procura o último id por largura com
`like("id_acao", "A____")`. Os dublês que criam Pendência precisam do mesmo
LIKE do Postgres: `_` casa um caractere, `%` (ou `*`, o apelido do PostgREST)
casa qualquer trecho, e o resto é literal e sensível a maiúsculas.
"""

from __future__ import annotations

import re


def casa_like(valor, padrao: str) -> bool:
    if not isinstance(valor, str):
        return False
    regex = "".join("." if c == "_" else ".*" if c in "%*" else re.escape(c) for c in padrao)
    return re.fullmatch(regex, valor, flags=re.DOTALL) is not None
