"""A porta por onde a ação da Tela do responsável entrou (issue #1885, ADR 0099).

A mesma Tela do responsável abre por duas portas: o link do email (token, sem
login) e, depois da ADR 0099, o login do app. O ouvidor precisa ler na trilha
por qual delas a resposta, a devolução ou o pedido de prazo veio, e a trilha não
ganha coluna nova (PRD #1883, "sem migration"): a porta viaja na última linha da
observação do movimento.

Este módulo é o único lugar que sabe escrever e tirar essa linha. Quem lê o
texto do movimento para mostrar ou desmontar (o histórico de respostas, a linha
do tempo) tira a porta antes, e por isso a frase de cada ato continua igual à
de antes desta fatia.
"""

from __future__ import annotations

LINK_DE_EMAIL = "link de e-mail"
# O login do app (issue #1886, ADR 0099, decisão 4).
APP = "app"

# As portas que a última linha pode nomear. Só uma porta conhecida é tirada:
# texto livre antigo que por acaso termine numa linha "Porta: ..." continua
# inteiro.
PORTAS = (LINK_DE_EMAIL, APP)

_ROTULO = "Porta: "


def com_porta(observacao: str, porta: str) -> str:
    """A observação do movimento com a porta na última linha."""
    return f"{observacao}\n{_ROTULO}{porta}"


def separar(observacao: str | None) -> tuple[str | None, str | None]:
    """A observação sem a linha da porta, e a porta (ou None quando não há).

    Movimento anterior a esta fatia volta inteiro e sem porta."""
    if not observacao:
        return observacao, None
    resto, quebra, ultima = observacao.rpartition("\n")
    if quebra and ultima.startswith(_ROTULO) and ultima[len(_ROTULO) :] in PORTAS:
        return resto, ultima[len(_ROTULO) :]
    return observacao, None
