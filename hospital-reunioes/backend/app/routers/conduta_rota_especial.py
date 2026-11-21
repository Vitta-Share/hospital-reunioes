"""Canal de Conduta, a Rota Especial (issue #1829, PRD #1786; especificação,
seção 10).

O desvio confirmado por um membro da fila comum, a entrega do parecer
registrada pelo grupo e a contagem, que é tudo o que se vê da Rota Especial
de fora do grupo. As rotas do caso passam pelo portão da ação, e a contagem
pelo da lista: quem não está no Comitê nem nela chega.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services.conduta import avisos, cifra, rota_especial
from app.services.conduta.acesso import CAMPOS_DA_LISTA, hoje_em_sao_paulo
from app.services.conduta.portao import INDISPONIVEL, CasoAberto, NoComite, portao_da_acao, portao_da_lista
from app.services.conduta.triagem import AcaoRecusadaError

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class EntregaDoParecer(BaseModel):
    destinatario: str = Field(default="", max_length=600)
    entregue_em: date


def _agir(funcao, supabase, aberto: CasoAberto, **argumentos) -> dict:
    antes = avisos.tarefas_antes(supabase, aberto.caso["id"])
    try:
        caso = funcao(supabase, aberto, **argumentos)
    except AcaoRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro
    avisos.avisar_tarefas_novas(supabase, aberto.caso["id"], antes)
    return {"caso": {campo: caso.get(campo) for campo in CAMPOS_DA_LISTA}}


@router.get("/rota-especial/contagem")
async def contagem(_comite: NoComite = Depends(portao_da_lista), supabase: Client = Depends(get_supabase_client)):
    """Casos da Rota Especial recebidos, concluídos e em aberto. Nada além."""
    return rota_especial.contagem(supabase)


@router.post("/casos/{caso_id}/desvio-especial")
async def confirmar_desvio(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    return _agir(rota_especial.confirmar_desvio, supabase, aberto)


@router.post("/casos/{caso_id}/entrega-do-parecer")
async def registrar_entrega(
    corpo: EntregaDoParecer,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    return _agir(
        rota_especial.registrar_entrega,
        supabase,
        aberto,
        destinatario=corpo.destinatario,
        entregue_em=corpo.entregue_em,
        hoje=hoje_em_sao_paulo(),
    )
