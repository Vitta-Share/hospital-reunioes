"""Canal de Conduta, as Mensagens do caso no lado do Comitê (issue #1845;
especificação, 5.3 e 6.1, passo 4).

A coordenação pergunta a quem relatou pela página de acompanhamento,
arquiva por falta de elementos o caso com pedido sem resposta há 15 dias e
reabre o arquivado quando a informação chega. A área aparece na tela do caso
(`acompanhamento.para_a_tela`). Toda rota passa pelo portão
(`app.services.conduta.portao`).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services.conduta import acompanhamento, avisos, cifra
from app.services.conduta.acesso import CAMPOS_DA_LISTA, hoje_em_sao_paulo
from app.services.conduta.portao import INDISPONIVEL, CasoAberto, portao_da_acao

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class Pergunta(BaseModel):
    texto: str = Field(default="", max_length=acompanhamento.TAMANHO_DA_PERGUNTA + 200)


def _agir(funcao, supabase, aberto: CasoAberto, **argumentos):
    antes = avisos.tarefas_antes(supabase, aberto.caso["id"])
    try:
        resultado = funcao(supabase, aberto, **argumentos)
    except acompanhamento.MensagemRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro
    avisos.avisar_tarefas_novas(supabase, aberto.caso["id"], antes)
    return resultado


@router.post("/casos/{caso_id}/mensagens", status_code=status.HTTP_201_CREATED)
async def enviar_pergunta(
    corpo: Pergunta, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """ENVIAR PERGUNTA: aparece para quem relatou na página de acompanhamento."""
    linha = _agir(acompanhamento.perguntar, supabase, aberto, texto=corpo.texto)
    return {"id": linha["id"], "enviada_em": linha["enviada_em"]}


@router.post("/casos/{caso_id}/arquivamento")
async def arquivar(aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)) -> dict:
    """ARQUIVAR POR FALTA DE ELEMENTOS."""
    caso = _agir(acompanhamento.arquivar, supabase, aberto, hoje=hoje_em_sao_paulo())
    return {"caso": {campo: caso.get(campo) for campo in CAMPOS_DA_LISTA}}


@router.post("/casos/{caso_id}/reabertura")
async def reabrir(aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)) -> dict:
    """REABRIR CASO, com o complemento que chegou depois do arquivamento."""
    caso = _agir(acompanhamento.reabrir, supabase, aberto)
    return {"caso": {campo: caso.get(campo) for campo in CAMPOS_DA_LISTA}}
