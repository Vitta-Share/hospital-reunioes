"""Canal de Conduta, o voto e a trava de robustez (issue #1833, PRD #1786;
especificação, seções 6.6 e 6.7).

O voto de cada membro, a trava preenchida pelo agente num clique e confirmada
pelos membros, a ciência do Código anexada e a conclusão da votação. Toda rota
passa pelo portão (`app.services.conduta.portao`). O voto dos outros não sai
por rota nenhuma antes de todos votarem: a tela do caso é a única leitura.
"""

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services import ai_processor
from app.services.conduta import avisos, cifra, trava, voto
from app.services.conduta.acesso import CAMPOS_DA_LISTA
from app.services.conduta.portao import INDISPONIVEL, CasoAberto, portao_da_acao

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class Voto(BaseModel):
    resultado: str = Field(max_length=40)
    medida: str | None = Field(default=None, max_length=40)
    dias_de_suspensao: int | None = None
    justificativa: str = Field(default="", max_length=2000)


class Confirmacao(BaseModel):
    item: Literal["fato", "prova", "defesa", "regra", "ciencia", "medida", "votos"]


def _agir(funcao, *argumentos, **nomeados):
    try:
        return funcao(*argumentos, **nomeados)
    except (voto.VotoRecusadoError, trava.TravaRecusadaError) as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.post("/casos/{caso_id}/voto")
async def votar(
    corpo: Voto, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """VOTAR: o voto do membro, oculto até todos votarem."""
    linha = _agir(voto.votar, supabase, aberto, **corpo.model_dump())
    return {"voto": {"rodada": linha["rodada"]}}


@router.post("/casos/{caso_id}/trava/preenchimento")
async def preencher_trava(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """PREENCHER TRAVA: o agente preenche a lista. Roda no executor da IA
    (issue #773)."""
    try:
        linha = await ai_processor.chamar_ia_fora_do_loop(trava.preencher_trava_de_robustez, supabase, aberto)
    except trava.TravaRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro
    return {"versao": linha["versao"]}


@router.post("/casos/{caso_id}/trava/confirmacao")
async def confirmar_item_da_trava(
    corpo: Confirmacao, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    _agir(trava.confirmar, supabase, aberto, corpo.item)
    return {"ok": True}


@router.post("/casos/{caso_id}/trava/ciencia")
async def anexar_ciencia_do_codigo(
    arquivo: UploadFile = File(...),
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A ciência do Código que o DP registrou fora do aplicativo."""
    _agir(trava.conferir_ciencia, arquivo.filename or "", arquivo.size or 1)
    conteudo = await arquivo.read()
    return _agir(trava.anexar_ciencia, supabase, aberto, arquivo.filename or "", conteudo)


@router.get("/casos/{caso_id}/trava/ciencia")
async def abrir_ciencia_do_codigo(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> Response:
    """A ciência decifrada, entregue pelo backend, sem cache."""
    conteudo, content_type = _agir(trava.abrir_ciencia, supabase, aberto)
    return Response(
        content=conteudo,
        media_type=content_type,
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


@router.post("/casos/{caso_id}/conclusao-da-votacao")
async def concluir_votacao(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """CONCLUIR VOTAÇÃO: o resultado da maioria, e o caso vai à Ata."""
    antes = avisos.tarefas_antes(supabase, aberto.caso["id"])
    caso = _agir(voto.concluir_votacao, supabase, aberto)
    avisos.avisar_tarefas_novas(supabase, aberto.caso["id"], antes)
    return {"caso": {campo: caso.get(campo) for campo in CAMPOS_DA_LISTA}}
