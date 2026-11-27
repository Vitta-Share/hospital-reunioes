"""Canal de Conduta, o Dossiê do caso (issue #1837, PRD #1786; especificação,
seções 9.1 e 9.2; ADR 0097, decisões 2 e 9) e o papel original e a guarda
(issue #1838; seções 9.3 e 9.4 e Anexo E.2).

"BAIXAR DOSSIÊ": o pacote do caso inteiro, decifrado, só para os membros do
Comitê no caso. A rota passa pelo portão (`app.services.conduta.portao`), e o
download entra na trilha antes de o pacote ser montado. A trilha com as
gavetas vem na tela do caso (`conduta_comite.abrir_caso`).

"ARQUIVAR PAPEL": a etiqueta do envelope em PDF e o registro do lacre, do
Comitê no caso. "Congelar caso" e "Descongelar", só da coordenação. A
eliminação ao fim da guarda é do job diário (`app.services.conduta.guarda`).
"""

import io
import logging
from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services.conduta import cifra, dossie, guarda
from app.services.conduta.acesso import CAMPOS_DA_LISTA, hoje_em_sao_paulo
from app.services.conduta.portao import INDISPONIVEL, RECUSA, CasoAberto, portao_da_acao
from app.services.conduta.triagem import AcaoRecusadaError
from app.services.conduta.trilha_do_caso import pode_baixar_dossie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


def _indisponivel() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL)


@router.get("/casos/{caso_id}/dossie")
async def baixar_dossie(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> StreamingResponse:
    """BAIXAR DOSSIÊ: o pacote ZIP do caso, sem cache. 403 a quem não é do
    Comitê no caso, com a mesma recusa do portão."""
    if not pode_baixar_dossie(aberto):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=RECUSA)
    if aberto.caso.get("eliminado_em"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=guarda.ELIMINADO)
    try:
        dossie.registrar_download(supabase, aberto)
    except (APIError, httpx.HTTPError) as erro:
        logger.error("Download do Dossiê do caso sem registro na trilha; o pacote não sai: %s", erro)
        raise _indisponivel() from erro
    try:
        arquivo, nome = await run_in_threadpool(dossie.montar, supabase, aberto)
    except cifra.CifraIndisponivelError as erro:
        raise _indisponivel() from erro
    return StreamingResponse(
        arquivo,
        media_type="application/zip",
        headers={"Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="{nome}"'},
    )


class Lacre(BaseModel):
    data: date | None = None
    local: str = Field(default="", max_length=300)


def _guarda(funcao, supabase, aberto: CasoAberto, **argumentos) -> dict:
    try:
        caso = funcao(supabase, aberto, **argumentos)
    except AcaoRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    return {"caso": {campo: caso.get(campo) for campo in CAMPOS_DA_LISTA}}


@router.get("/casos/{caso_id}/etiqueta")
async def imprimir_etiqueta(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> StreamingResponse:
    """IMPRIMIR ETIQUETA: a folha A4 do envelope, sem nome, setor nem assunto."""
    try:
        pdf, nome = await run_in_threadpool(guarda.etiqueta, supabase, aberto)
    except AcaoRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.post("/casos/{caso_id}/lacre")
async def registrar_lacre(
    corpo: Lacre, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    hoje = hoje_em_sao_paulo()
    return _guarda(guarda.registrar_lacre, supabase, aberto, dia=corpo.data or hoje, local=corpo.local, hoje=hoje)


@router.post("/casos/{caso_id}/congelamento")
async def congelar_caso(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    return _guarda(guarda.congelar, supabase, aberto)


@router.post("/casos/{caso_id}/descongelamento")
async def descongelar_caso(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    return _guarda(guarda.descongelar, supabase, aberto)
