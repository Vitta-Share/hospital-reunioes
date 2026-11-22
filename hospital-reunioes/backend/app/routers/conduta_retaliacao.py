"""Canal de Conduta, a verificação de retaliação no lado do Comitê (issue
#1839, PRD #1786; especificação, 6.11 e 18).

A coordenação registra cada verificação (30, 90 e 180 dias depois do
encerramento) com um clique, houve ou não houve, e a observação se quiser.
Quando houve, abre um caso novo de retaliação. Toda rota passa pelo portão
(`app.services.conduta.portao`).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services.conduta import cifra, retaliacao
from app.services.conduta.acesso import hoje_em_sao_paulo
from app.services.conduta.portao import INDISPONIVEL, CasoAberto, portao_da_acao

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class Verificacao(BaseModel):
    marco: Literal[30, 90, 180]
    houve: bool
    observacao: str = Field(default="", max_length=retaliacao.TAMANHO_DA_OBSERVACAO + 200)


def _agir(funcao, *argumentos, **nomeados):
    try:
        return funcao(*argumentos, **nomeados)
    except retaliacao.VerificacaoRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.post("/casos/{caso_id}/verificacoes-de-retaliacao")
async def registrar_verificacao(
    corpo: Verificacao, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """REGISTRAR VERIFICAÇÃO: um clique, houve ou não houve."""
    linha = _agir(
        retaliacao.registrar,
        supabase,
        aberto,
        marco=corpo.marco,
        houve=corpo.houve,
        observacao=corpo.observacao,
        hoje=hoje_em_sao_paulo(),
    )
    return {"marco": linha["marco"], "houve": linha["houve"]}
