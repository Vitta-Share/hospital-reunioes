"""Canal de Conduta, o afastamento cautelar (issue #1836, PRD #1786;
especificação, seção 6.5).

Registrar passa pelo portão da ação do caso. O pedido, a entrega e o parecer
passam pelo portão do afastamento, que também deixa a coordenação abrir o
pedido de um caso da Rota Especial sem abrir o caso. A lista dos pedidos da
Rota Especial é da coordenação, e só com o que não é do caso.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services.conduta import afastamento, cifra
from app.services.conduta.acesso import CAMPOS_DA_LISTA
from app.services.conduta.portao import INDISPONIVEL, CasoAberto, portao_da_acao
from app.services.conduta.triagem import AcaoRecusadaError

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class Afastamento(BaseModel):
    citado_id: str = Field(max_length=40)
    motivo: str = Field(default="", max_length=2 * afastamento.TAMANHO_DO_MOTIVO)


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
