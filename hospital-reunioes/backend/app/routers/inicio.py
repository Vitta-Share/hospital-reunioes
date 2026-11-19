"""O Início de quem pede (issue #1934, ADR 0104).

Todo mundo que entra no app tem Início, menos a Secretária, que continua na
tela dela e não vê Pendência (decisão 53 do diretor no PRD #1757): para ela a
rota recusa e não devolve dado nenhum.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import (
    barrar_desligado,
    get_current_user,
    get_participante_for_user,
    get_supabase_client,
    is_secretaria,
)
from app.services.inicio import Inicio, montar_inicio
from app.services.inicio.regras import FUSO

router = APIRouter(prefix="/inicio", tags=["inicio"])


def agora_em_brasilia() -> datetime:
    return datetime.now(tz=FUSO)


@router.get("", response_model=Inicio)
async def get_inicio(
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
) -> Inicio:
    me = await get_participante_for_user(current_user, supabase)
    barrar_desligado(me)
    if is_secretaria(me):
        raise HTTPException(status_code=403, detail="A Secretária não tem Início")
    return montar_inicio(supabase, me, agora_em_brasilia())
