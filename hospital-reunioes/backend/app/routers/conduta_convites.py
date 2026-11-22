"""Canal de Conduta, o convite do apurador e do membro da CIPA (issue #1825,
PRD #1786, ADR 0097, decisão 12).

Dentro do caso, a coordenação (ou o Grupo Especial, no caso dele) convida uma
pessoa por e-mail. As duas rotas passam pelo portão da ação, que autoriza
como o do caso: quem não abre o caso recebe a mesma recusa. Quem pode
convidar é o serviço que decide (`convites.pode_convidar`).

O convite grava a atribuição e a linha da trilha, manda o termo à ClickSign
(a falha vira `aviso_termo`) e, depois da resposta, o e-mail ao convidado.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from starlette.concurrency import run_in_threadpool
from supabase import Client

from app.dependencies import get_supabase_client
from app.limiter import limiter
from app.services.conduta import convites
from app.services.conduta.portao import CasoAberto, portao_da_acao
from app.services.conduta.triagem import AcaoRecusadaError

router = APIRouter(prefix="/comite-de-conduta/casos", tags=["canal-de-conduta"])


class Convite(BaseModel):
    email: EmailStr = Field(max_length=320)
    # Só para quem ainda não tem cadastro.
    nome: str = Field(default="", max_length=200)
    motivo: Literal["apurador", "cipa"]


@router.get("/{caso_id}/convites")
async def listar_convites(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """Quem foi convidado e o termo de cada um, para quem pode convidar."""
    if not convites.pode_convidar(aberto):
        return {"pode_convidar": False, "convites": []}
    return {"pode_convidar": True, "convites": convites.convites_do_caso(supabase, aberto.caso["id"])}


@router.post("/{caso_id}/convites", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def convidar(
    request: Request,
    corpo: Convite,
    tarefas: BackgroundTasks,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    try:
        convite = await run_in_threadpool(
            convites.convidar, supabase, aberto, email=corpo.email, nome=corpo.nome, motivo=corpo.motivo
        )
    except AcaoRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    aviso = await run_in_threadpool(convites.enviar_termo, supabase, convite)
    tarefas.add_task(convites.enviar_email_do_convite, convite["pessoa"]["email"])
    return {"convites": convites.convites_do_caso(supabase, aberto.caso["id"]), "aviso_termo": aviso}
