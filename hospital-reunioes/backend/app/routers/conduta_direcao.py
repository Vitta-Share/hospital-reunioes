"""Canal de Conduta, a Recomendação do Comitê para a Direção (issue #1835, PRD
#1786; especificação, 6.8).

O Presidente e a diretoria executiva, cada um com o perfil nominal do módulo,
leem a página de conclusão e a ata assinada dos casos que o Comitê enviou. A
diretoria executiva registra a decisão do Presidente sobre a medida e anexa a
cópia da comunicação da medida. Toda rota passa pelo portão da Direção
(`app.services.conduta.portao`), e cada leitura entra na trilha do caso.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services.conduta import cifra, direcao
from app.services.conduta.acesso import hoje_em_sao_paulo
from app.services.conduta.portao import (
    INDISPONIVEL,
    NaDirecao,
    RecomendacaoAberta,
    portao_da_direcao,
    portao_da_recomendacao,
)

router = APIRouter(prefix="/comite-de-conduta/direcao", tags=["canal-de-conduta"])


class DecisaoDaMedida(BaseModel):
    decisao: Literal["aplicada", "aplicada_com_ajuste", "nao_aplicada"]
    justificativa: str = Field(default="", max_length=direcao.TAMANHO_DA_JUSTIFICATIVA + 200)
    decidida_em: date


def _agir(funcao, *argumentos, **nomeados):
    try:
        return funcao(*argumentos, **nomeados)
    except direcao.DirecaoRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.get("/recomendacoes")
async def listar_recomendacoes(
    direcao_logada: NaDirecao = Depends(portao_da_direcao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """Os casos que o Comitê enviou à Direção, só com os metadados."""
    return {
        "recomendacoes": direcao.lista_da_direcao(supabase, direcao_logada.autor_id),
        "registra_decisao": direcao_logada.perfil == direcao.DIRETORIA_EXECUTIVA,
    }


@router.get("/recomendacoes/{caso_id}")
async def ler_recomendacao(
    aberta: RecomendacaoAberta = Depends(portao_da_recomendacao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """A página de conclusão, com a leitura gravada na trilha."""
    return _agir(direcao.ler_recomendacao, supabase, aberta)


@router.get("/recomendacoes/{caso_id}/ata")
async def abrir_ata(
    aberta: RecomendacaoAberta = Depends(portao_da_recomendacao), supabase: Client = Depends(get_supabase_client)
) -> Response:
    """A ata assinada, entregue pelo backend, sem cache."""
    conteudo = _agir(direcao.abrir_ata_da_recomendacao, supabase, aberta)
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


@router.post("/recomendacoes/{caso_id}/decisao")
async def registrar_decisao(
    corpo: DecisaoDaMedida,
    aberta: RecomendacaoAberta = Depends(portao_da_recomendacao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A diretoria executiva registra a decisão do Presidente."""
    linha = _agir(
        direcao.registrar_decisao,
        supabase,
        aberta,
        decisao=corpo.decisao,
        justificativa=corpo.justificativa,
        decidida_em=corpo.decidida_em,
        hoje=hoje_em_sao_paulo(),
    )
    return {"decisao": linha["decisao"]}


@router.post("/recomendacoes/{caso_id}/comunicacao")
async def anexar_comunicacao(
    arquivo: UploadFile = File(...),
    aberta: RecomendacaoAberta = Depends(portao_da_recomendacao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A cópia da comunicação da medida, anexada à trilha."""
    _agir(direcao.conferir_comunicacao, arquivo.filename or "", arquivo.size or 1)
    conteudo = await arquivo.read()
    return _agir(direcao.anexar_comunicacao, supabase, aberta, arquivo.filename or "", conteudo)
