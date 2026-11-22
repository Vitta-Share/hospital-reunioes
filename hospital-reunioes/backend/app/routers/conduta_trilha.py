"""Canal de Conduta, o Dossiê do caso (issue #1837, PRD #1786; especificação,
seções 9.1 e 9.2; ADR 0097, decisões 2 e 9).

"BAIXAR DOSSIÊ": o pacote do caso inteiro, decifrado, só para os membros do
Comitê no caso. A rota passa pelo portão (`app.services.conduta.portao`), e o
download entra na trilha antes de o pacote ser montado. A trilha com as
gavetas vem na tela do caso (`conduta_comite.abrir_caso`).
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from postgrest.exceptions import APIError
from supabase import Client

from app.dependencies import get_supabase_client
from app.services.conduta import cifra, dossie
from app.services.conduta.portao import INDISPONIVEL, RECUSA, CasoAberto, portao_da_acao
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
