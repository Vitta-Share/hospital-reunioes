"""Canal de Conduta, o afastamento cautelar (issue #1836, PRD #1786;
especificação, seção 6.5).

Registrar passa pelo portão da ação do caso. O pedido, a entrega e o parecer
passam pelo portão do afastamento, que também deixa a coordenação abrir o
pedido de um caso da Rota Especial sem abrir o caso. A lista dos pedidos da
Rota Especial é da coordenação, e só com o que não é do caso.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services.conduta import afastamento, cifra
from app.services.conduta.acesso import CAMPOS_DA_LISTA, hoje_em_sao_paulo
from app.services.conduta.portao import (
    INDISPONIVEL,
    CasoAberto,
    PedidoAberto,
    portao_da_acao,
    portao_do_afastamento,
)
from app.services.conduta.triagem import AcaoRecusadaError

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class Afastamento(BaseModel):
    citado_id: str = Field(max_length=40)
    motivo: str = Field(default="", max_length=2 * afastamento.TAMANHO_DO_MOTIVO)


class Entrega(BaseModel):
    destino: Literal["dp", "juridico"]
    entregue_em: date


def _executar(funcao, *argumentos, **nomeados):
    try:
        return funcao(*argumentos, **nomeados)
    except AcaoRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.post("/casos/{caso_id}/afastamentos")
async def registrar_afastamento(
    corpo: Afastamento, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """No caso comum, a decisão do coordenador; na Rota Especial, o pedido do
    grupo à coordenação."""
    caso = _executar(afastamento.registrar, supabase, aberto, citado_id=corpo.citado_id, motivo=corpo.motivo)
    return {"caso": {campo: caso.get(campo) for campo in CAMPOS_DA_LISTA}}


@router.get("/casos/{caso_id}/afastamentos/{afastamento_id}")
async def abrir_pedido(
    aberto: PedidoAberto = Depends(portao_do_afastamento), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """O pedido ao DP e ao Jurídico: só quem afastar e o motivo."""
    return _executar(afastamento.abrir_pedido, supabase, aberto)


@router.post("/casos/{caso_id}/afastamentos/{afastamento_id}/entrega")
async def registrar_entrega(
    corpo: Entrega,
    aberto: PedidoAberto = Depends(portao_do_afastamento),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    _executar(
        afastamento.registrar_entrega,
        supabase,
        aberto,
        destino=corpo.destino,
        entregue_em=corpo.entregue_em,
        hoje=hoje_em_sao_paulo(),
    )
    return {"ok": True}


@router.post("/casos/{caso_id}/afastamentos/{afastamento_id}/parecer")
async def anexar_parecer(
    arquivo: UploadFile = File(...),
    resultado: Literal["afastar", "nao_afastar"] | None = Form(None),
    aberto: PedidoAberto = Depends(portao_do_afastamento),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O parecer do Jurídico em PDF. Na Rota Especial, com o resultado que ele
    define."""
    if (arquivo.size or 0) > afastamento.LIMITE_DO_PARECER:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O parecer passou de 20 MB.")
    conteudo = await arquivo.read()
    _executar(afastamento.anexar_parecer, supabase, aberto, conteudo=conteudo, resultado_do_parecer=resultado)
    return {"ok": True}


@router.get("/casos/{caso_id}/afastamentos/{afastamento_id}/parecer")
async def abrir_parecer(
    aberto: PedidoAberto = Depends(portao_do_afastamento), supabase: Client = Depends(get_supabase_client)
) -> Response:
    """O parecer decifrado, entregue pelo backend. Nada de cache."""
    conteudo = _executar(afastamento.abrir_parecer, supabase, aberto)
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )
