"""A fotografia semanal do painel de Reuniões (issue #1873; ADR 0098, decisão 10;
decisões 30 e 34 do diretor no PRD #1757).

O job de segunda grava os cards do painel de cada pessoa que entra no app e vê
o painel, com a mesma conta e o mesmo recorte do endpoint (`montar_painel`,
sem filtro). A fotografia é uma linha por pessoa e por semana, e a semana é a
segunda-feira dela, no fuso de São Paulo. Quem já tem a fotografia da semana
não é fotografado de novo, e a chave da tabela garante isso também no banco:
rodar duas vezes grava uma fotografia só.

A tabela alimenta duas coisas do painel:
- a evolução: as atrasadas das últimas 8 semanas, só as fotografadas;
- a seta dos cards: a fotografia da semana anterior, sem a qual não há seta.

Nada é recalculado do histórico (ADR 0098): a semana sem fotografia não aparece.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.dependencies import (
    _PARTICIPANTE_FULL_FIELDS,
    foi_desligado,
    is_secretaria,
    recorte_das_pendencias_de,
    tem_acesso_reunioes,
)
from app.services.paginacao import ler_tudo
from app.services.painel_reunioes import CardsDoPainel, SemanaDaEvolucao, montar_painel

TABELA = "painel_fotografias"
SEMANAS_DA_EVOLUCAO = 8
CAMPOS_DOS_CARDS = tuple(CardsDoPainel.model_fields)


def segunda_da_semana(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def _ve_o_painel(participante: dict) -> bool:
    return (
        bool(participante.get("auth_user_id"))
        and tem_acesso_reunioes(participante)
        and not is_secretaria(participante)
        and not foi_desligado(participante)
    )


def fotografar_semana(supabase, *, hoje: date, agora: datetime) -> int:
    """Grava a fotografia da semana de `hoje` de quem ainda não tem. Devolve
    quantas gravou."""
    semana = segunda_da_semana(hoje).isoformat()
    ja_tem = {
        linha["participante_id"]
        for linha in ler_tudo(
            lambda: supabase.table(TABELA).select("participante_id").eq("semana", semana).order("participante_id"),
            rotulo="fotografias da semana",
        )
    }
    pessoas = ler_tudo(
        lambda: (
            supabase.table("participantes")
            .select(_PARTICIPANTE_FULL_FIELDS)
            .not_.is_("auth_user_id", "null")
            .order("id")
        ),
        rotulo="quem tem o painel",
    )
    gravadas = 0
    for pessoa in pessoas:
        if pessoa["id"] in ja_tem or not _ve_o_painel(pessoa):
            continue
        cards = montar_painel(
            supabase, recorte_das_pendencias_de(supabase, pessoa), hoje=hoje, agora=agora
        ).cards.model_dump()
        resposta = (
            supabase.table(TABELA)
            .upsert(
                [{"participante_id": pessoa["id"], "semana": semana, **cards}],
                on_conflict="participante_id,semana",
                ignore_duplicates=True,
            )
            .execute()
        )
        gravadas += len(resposta.data or [])
    return gravadas


def ler_fotografias(
    supabase, participante_id: str, *, hoje: date
) -> tuple[list[SemanaDaEvolucao], CardsDoPainel | None]:
    """A evolução das últimas 8 semanas (da mais antiga à mais nova) e os cards
    da semana anterior, se ela foi fotografada."""
    segunda = segunda_da_semana(hoje)
    desde = segunda - timedelta(weeks=SEMANAS_DA_EVOLUCAO - 1)
    linhas = (
        supabase.table(TABELA)
        .select("semana, " + ", ".join(CAMPOS_DOS_CARDS))
        .eq("participante_id", participante_id)
        .gte("semana", desde.isoformat())
        .lte("semana", segunda.isoformat())
        .order("semana")
        .execute()
        .data
        or []
    )
    linhas = sorted(linhas, key=lambda linha: str(linha["semana"]))
    evolucao = [SemanaDaEvolucao(semana=str(linha["semana"]), atrasadas=linha["atrasadas"]) for linha in linhas]
    anterior_iso = (segunda - timedelta(weeks=1)).isoformat()
    anterior = next((linha for linha in linhas if str(linha["semana"]) == anterior_iso), None)
    cards = CardsDoPainel(**{campo: anterior[campo] for campo in CAMPOS_DOS_CARDS}) if anterior else None
    return evolucao, cards
