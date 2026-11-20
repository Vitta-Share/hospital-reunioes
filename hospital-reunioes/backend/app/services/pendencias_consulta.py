"""A consulta da lista de Pendências, num lugar só (issue #1609, ADR 0085).

É a consulta da tela de Pendências (`GET /pendencias`) e da ferramenta de
pendências do Conector: as duas chamam esta função, e é por isso que a
pendência que o Claude recebe como atrasada é a que a tela mostra como
atrasada. Atrasada é o status `ATRASADO`, que o job `marcar_atrasadas` grava
na pendência PENDENTE de prazo vencido; nenhuma das duas portas recalcula.

Quem chama resolve antes quem é e passa o recorte das Pendências dessa pessoa
(`pendencias_recorte`, issue #1863): o vínculo de responsável, co-responsável
e Facilitador, a visão inteira do Super admin, e as reuniões do Núcleo que a
pessoa não alcança (`ocultas`, issue #1772).
"""

from __future__ import annotations

from datetime import date

from app.services.pendencias_recorte import RecorteDasPendencias


def sem_reunioes_ocultas(query, ocultas: list[str]):
    """Tira da consulta as pendências das reuniões do Núcleo que a pessoa não
    alcança (issue #1772) e mantém a pendência sem reunião: o `not.in` do
    banco sozinho não casa NULL e a levaria junto."""
    if not ocultas:
        return query
    return query.or_(f"id_reuniao.is.null,id_reuniao.not.in.({','.join(ocultas)})")


def no_recorte(query, recorte: RecorteDasPendencias):
    """Deixa na consulta só as pendências do recorte da pessoa (issue #1863).
    None quer dizer que nada aparece, e quem chama devolve vazio sem ir ao
    banco."""
    query = sem_reunioes_ocultas(query, list(recorte.ocultas))
    filtro = recorte.filtro()
    if filtro is None:
        return query
    if not filtro:
        return None
    return query.or_(filtro)


def consultar_pendencias(
    supabase,
    *,
    recorte: RecorteDasPendencias,
    status: str | None = None,
    responsaveis: list[str] | None = None,
    id_reuniao: str | None = None,
    prazo_de: date | None = None,
    prazo_ate: date | None = None,
    setores: list[str] | None = None,
    facilitadores: list[str] | None = None,
    limit: int,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """As pendências visíveis com os filtros, por prazo (as sem prazo no fim),
    cortadas em `limit` a partir de `offset`. Devolve as linhas e o total antes
    do corte."""
    # A Pendência sem Reunião é o lembrete da Agenda regulatória do Núcleo:
    # nenhuma lista de Pendências o mostra (`e_lembrete_do_nucleo`).
    query = no_recorte(
        supabase.table("pendencias")
        .select("*", count="exact")
        .is_("deleted_at", "null")
        .not_.is_("id_reuniao", "null"),
        recorte,
    )
    if query is None:
        return [], 0

    # Filtro de facilitador: as reuniões que cada facilitador pedido conduz.
    facilitator_meeting_ids: list[str] | None = None
    if facilitadores:
        rq = supabase.table("reunioes").select("id_reuniao").is_("deleted_at", "null")
        rq = (
            rq.in_("facilitador_id", facilitadores)
            if len(facilitadores) > 1
            else rq.eq("facilitador_id", facilitadores[0])
        )
        rq_res = rq.execute()
        facilitator_meeting_ids = [r["id_reuniao"] for r in (rq_res.data or [])]
        if not facilitator_meeting_ids:
            return [], 0

    # O filtro de facilitador vale junto com o recorte: "as do facilitador X"
    # é a parte do recorte que está nas reuniões dele.
    if facilitator_meeting_ids is not None:
        query = query.in_("id_reuniao", facilitator_meeting_ids)

    # Filtro por setor (super user only)
    if setores and recorte.reunioes is None:
        has_sem_setor = "Sem Setor" in setores
        setores_real = [s for s in setores if s != "Sem Setor"]
        pq = supabase.table("participantes").select("id")
        if has_sem_setor and setores_real:
            in_list = ",".join(setores_real)
            pq = pq.or_(f"setor.is.null,setor.in.({in_list})")
        elif has_sem_setor:
            pq = pq.is_("setor", "null")
        elif len(setores_real) == 1:
            pq = pq.eq("setor", setores_real[0])
        else:
            pq = pq.in_("setor", setores_real)
        p_res = pq.execute()
        sector_ids = [p["id"] for p in (p_res.data or [])]
        if sector_ids:
            query = query.in_("responsavel_id", sector_ids)
        else:
            return [], 0

    # Filtro por responsável específico
    if responsaveis:
        if len(responsaveis) == 1:
            query = query.eq("responsavel_id", responsaveis[0])
        else:
            query = query.in_("responsavel_id", responsaveis)

    if status:
        query = query.eq("status", status)
    if id_reuniao:
        query = query.eq("id_reuniao", id_reuniao)
    if prazo_de:
        query = query.gte("prazo", str(prazo_de))
    if prazo_ate:
        query = query.lte("prazo", str(prazo_ate))

    result = query.order("prazo", desc=False, nullsfirst=False).range(offset, offset + limit - 1).execute()
    return result.data or [], result.count or 0
