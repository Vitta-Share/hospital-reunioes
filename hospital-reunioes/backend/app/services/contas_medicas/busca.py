"""A busca da tela de contas de Contas médicas (issue #1956, ADR 0105, decisão 4).

Procura parte do número do atendimento e parte do rótulo do paciente, sem
diferenciar maiúscula nem acento, em todas as etapas da conta e de quem quer
que esteja com ela (decisão 1). O número da conta não entra na busca. Cada
conta volta com a etapa, com quem está e se a pessoa pode abrir o Guia dela:
ver não é abrir (decisão 2).
"""

from __future__ import annotations

import unicodedata

from app.services.contas_medicas.fila import (
    COM_A_FATURISTA,
    CONCLUIDAS,
    LIVRE,
    NAO_PRONTAS,
    _quem_enviou,
    _trocar_id_por_nome,
    ve_todas,
)

MINIMO_DE_CARACTERES = 2
# A tela mostra no máximo 50 contas e pede para refinar quando há mais.
TETO = 50
# Quantos atendimentos cada coluna lê antes da conferência sem acento: o
# padrão do banco casa um pouco a mais (ver `_padrao`).
CANDIDATOS = 500
# Letras que levam acento em português: no banco viram curinga.
_COM_ACENTO = set("aeiouc")


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn").casefold()


def _padrao(termo: str) -> str:
    """O padrão do `ilike`, que não diferencia maiúscula mas diferencia
    acento: cada letra que pode ter acento vira `_` (um caractere qualquer), e
    o que não é letra nem algarismo também, para `%`, `_` e a vírgula do
    PostgREST não entrarem crus. O banco devolve um pouco a mais, e a
    conferência exata é em Python."""
    letras = ("_" if c in _COM_ACENTO or not (c.isascii() and c.isalnum()) else c for c in termo)
    return f"%{''.join(letras)}%"


def etapa_da(situacao: str) -> str:
    if situacao == LIVRE:
        return "fila"
    if situacao in COM_A_FATURISTA:
        return "em_analise"
    if situacao in CONCLUIDAS:
        return "concluidas"
    return "envios"


def _atendimentos(supabase, termo: str) -> list[dict]:
    """Os atendimentos cujo número ou rótulo contém o termo, o mais recente primeiro."""
    achados: dict[str, dict] = {}
    for coluna in ("numero_atendimento", "paciente_rotulo"):
        linhas = (
            supabase.table("cm_atendimento")
            .select("id, numero_atendimento, paciente_rotulo")
            .ilike(coluna, _padrao(termo))
            .order("criado_em", desc=True)
            .limit(CANDIDATOS)
            .execute()
            .data
            or []
        )
        for atendimento in linhas:
            if termo in sem_acento(atendimento.get(coluna) or ""):
                achados.setdefault(atendimento["id"], atendimento)
    return list(achados.values())


def buscar(supabase, me: dict, texto: str) -> dict:
    """As contas achadas (no máximo `TETO`), com `etapa`, `com_quem`, `minha`
    e `pode_abrir`, e `mais` quando passou do teto. A conta cujo número do
    atendimento é o digitado vem primeiro; o resto, a mais recente primeiro."""
    termo = sem_acento(texto.strip())
    atendimentos = _atendimentos(supabase, termo)
    if not atendimentos:
        return {"todas": ve_todas(me), "contas": [], "mais": False}
    contas = (
        supabase.table("cm_conta")
        .select("*")
        .in_("atendimento_id", [a["id"] for a in atendimentos[: TETO + 1]])
        .order("ordem_fila", desc=True)
        .limit(TETO + 1)
        .execute()
        .data
        or []
    )
    mais = len(contas) > TETO or len(atendimentos) > TETO
    numero = {a["id"]: sem_acento(a.get("numero_atendimento") or "") for a in atendimentos}
    contas = sorted(contas[:TETO], key=lambda c: numero.get(c["atendimento_id"]) != termo)
    _quem_esta_com_cada(supabase, me, contas)
    return {"todas": ve_todas(me), "contas": contas, "mais": mais}


def _quem_esta_com_cada(supabase, me: dict, contas: list[dict]) -> None:
    """Na Fila, ninguém; em análise e concluída, a faturista; em Envios, quem
    enviou, que é quem tem o PDF que falta."""
    em_envio = [c for c in contas if c.get("situacao") in NAO_PRONTAS]
    enviou, _ = _quem_enviou(supabase, em_envio)
    todas = ve_todas(me)
    for conta in contas:
        situacao = conta.get("situacao")
        conta["etapa"] = etapa_da(situacao)
        conta["minha"] = situacao not in NAO_PRONTAS and conta.get("faturista_id") == me.get("id")
        if situacao == LIVRE:
            conta["com_quem"] = None
        elif situacao in NAO_PRONTAS:
            conta["com_quem"] = enviou.get(conta["id"])
        else:
            conta["com_quem"] = conta.get("faturista_id")
        # A mesma regra do Guia: a livre é de quem pegar, a sua abre, e quem
        # tem "painel completo" abre qualquer uma que tenha Guia.
        conta["pode_abrir"] = situacao not in NAO_PRONTAS and (situacao == LIVRE or conta["minha"] or todas)
    _trocar_id_por_nome(supabase, contas)
