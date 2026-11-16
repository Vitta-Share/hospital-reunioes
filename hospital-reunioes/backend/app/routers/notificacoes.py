"""
Router de notificações.

Endpoints para listar, contar e gerenciar notificações do usuário.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import (
    get_current_user,
    get_participante_for_user,
    get_supabase_client,
    visibilidade_das_reunioes,
)
from app.models.schemas import NotificacaoCount, NotificacaoResponse

router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])
logger = logging.getLogger(__name__)


def _sem_avisos_do_nucleo(query, supabase, participante: dict):
    """Tira do sino o aviso que aponta para reunião do Núcleo que a pessoa não
    alcança, ou para pendência dela (issue #1772). A referência do aviso é a
    reunião (aceite interno) ou a pendência (menção, responsável, comentário).
    O aviso sem referência fica: o `not.in` sozinho não casa NULL."""
    ocultas = visibilidade_das_reunioes(supabase, participante).ocultas
    if not ocultas:
        return query
    pendencias = supabase.table("pendencias").select("id_acao").in_("id_reuniao", ocultas).execute().data or []
    referencias = ocultas + [p["id_acao"] for p in pendencias]
    return query.or_(f"referencia_id.is.null,referencia_id.not.in.({','.join(referencias)})")


@router.get("", response_model=list[NotificacaoResponse])
async def list_notificacoes(
    lida: bool | None = Query(None),
    limit: int = Query(30, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """Lista notificações do usuário autenticado."""
    participante = await get_participante_for_user(current_user, supabase, fields="id")
    if not participante:
        return []

    participante_id = participante["id"]

    query = _sem_avisos_do_nucleo(
        supabase.table("notificacoes").select("*").eq("destinatario_id", participante_id), supabase, participante
    )

    if lida is not None:
        query = query.eq("lida", lida)

    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    return result.data or []


@router.get("/count", response_model=NotificacaoCount)
async def count_notificacoes(
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """Retorna a contagem de notificações não lidas."""
    participante = await get_participante_for_user(current_user, supabase, fields="id")
    if not participante:
        return NotificacaoCount(nao_lidas=0)

    participante_id = participante["id"]
    query = (
        supabase.table("notificacoes")
        .select("id", count="exact")
        .eq("destinatario_id", participante_id)
        .eq("lida", False)
    )
    result = _sem_avisos_do_nucleo(query, supabase, participante).execute()

    return NotificacaoCount(nao_lidas=result.count or 0)


@router.patch("/{notificacao_id}/lida", response_model=NotificacaoResponse)
async def marcar_lida(
    notificacao_id: str,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """Marca uma notificação como lida."""
    participante = await get_participante_for_user(current_user, supabase, fields="id")
    if not participante:
        raise HTTPException(status_code=403, detail="Participante não encontrado")
    participante_id = participante["id"]

    result = (
        supabase.table("notificacoes")
        .update({"lida": True})
        .eq("id", notificacao_id)
        .eq("destinatario_id", participante_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    return result.data[0]


@router.patch("/ler-todas", status_code=200)
async def marcar_todas_lidas(
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """Marca todas as notificações do usuário como lidas."""
    participante = await get_participante_for_user(current_user, supabase, fields="id")
    if not participante:
        raise HTTPException(status_code=403, detail="Participante não encontrado")
    participante_id = participante["id"]

    supabase.table("notificacoes").update({"lida": True}).eq("destinatario_id", participante_id).eq(
        "lida", False
    ).execute()

    logger.info(f"[Notificacoes] Todas marcadas como lidas para {participante_id}")
    return {"detail": "Todas as notificações foram marcadas como lidas"}
