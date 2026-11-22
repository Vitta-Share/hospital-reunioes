"""Canal de Conduta, o caminho do caso depois da votação, no lado do Comitê
(issue #1835, PRD #1786; especificação, 6.3, 6.8, 6.9 e 6.10).

"ENVIAR À DIREÇÃO", a cópia da comunicação da medida que a Direção anexou, o
retorno (gerado pelo agente num clique, revisado e aprovado pela coordenação)
e a correção de processo (sugerida pelo agente e escolhida pelo Comitê, com
responsável e prazo). Toda rota passa pelo portão
(`app.services.conduta.portao`).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services import ai_processor
from app.services.conduta import avisos, cifra, direcao, retorno
from app.services.conduta.acesso import hoje_em_sao_paulo
from app.services.conduta.portao import INDISPONIVEL, CasoAberto, portao_da_acao

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class VersaoDoRetorno(BaseModel):
    denunciante: str = Field(default="", max_length=retorno.TAMANHO_DO_TEXTO + 200)
    acusado: str = Field(default="", max_length=retorno.TAMANHO_DO_TEXTO + 200)


class CorrecaoEscolhida(BaseModel):
    texto: str = Field(default="", max_length=retorno.TAMANHO_DO_TEXTO)
    responsavel: str = Field(default="", max_length=retorno.TAMANHO_DO_RESPONSAVEL + 50)
    prazo_em: date


def _agir(funcao, *argumentos, **nomeados):
    try:
        return funcao(*argumentos, **nomeados)
    except (direcao.DirecaoRecusadaError, retorno.RetornoRecusadoError) as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


async def _com_a_ia(funcao, supabase, aberto: CasoAberto):
    try:
        return await ai_processor.chamar_ia_fora_do_loop(funcao, supabase, aberto)
    except retorno.RetornoRecusadoError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.post("/casos/{caso_id}/direcao")
async def enviar_a_direcao(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """ENVIAR À DIREÇÃO: libera a Recomendação do Comitê ao Presidente e à
    diretoria executiva."""
    antes = avisos.tarefas_antes(supabase, aberto.caso["id"])
    linha = _agir(direcao.enviar_a_direcao, supabase, aberto)
    avisos.avisar_tarefas_novas(supabase, aberto.caso["id"], antes)
    return {"etapa": linha["etapa"]}


@router.get("/casos/{caso_id}/medida/comunicacao")
async def abrir_comunicacao_da_medida(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> Response:
    """A última cópia da comunicação da medida, entregue pelo backend, sem cache."""
    conteudo, content_type = _agir(direcao.abrir_comunicacao, supabase, aberto.caso["id"], aberto.autor_id)
    return Response(
        content=conteudo,
        media_type=content_type,
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


@router.post("/casos/{caso_id}/retorno")
async def gerar_retorno(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """GERAR RETORNO: o agente redige. Roda no executor da IA (issue #773)."""
    linha = await _com_a_ia(retorno.redigir_retorno_do_caso, supabase, aberto)
    return {"versao": linha["versao"]}


@router.post("/casos/{caso_id}/retorno/versoes")
async def editar_retorno(
    corpo: VersaoDoRetorno,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    linha = _agir(retorno.editar_retorno, supabase, aberto, denunciante=corpo.denunciante, acusado=corpo.acusado)
    return {"versao": linha["versao"]}


@router.post("/casos/{caso_id}/retorno/aprovacao")
async def aprovar_retorno(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """APROVAR RETORNO: a última versão sai, e o caso é concluído."""
    linha = await run_in_threadpool(_agir, retorno.aprovar_retorno, supabase, aberto)
    return {"etapa": linha["etapa"]}


@router.get("/casos/{caso_id}/retorno/comunicacao-ao-acusado")
async def abrir_comunicacao_ao_acusado(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """A comunicação ao acusado, só depois da aprovação."""
    return {"texto": _agir(retorno.comunicacao_ao_acusado, supabase, aberto)}


@router.post("/casos/{caso_id}/correcoes/sugestao")
async def sugerir_correcoes(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """SUGERIR CORREÇÕES: o agente sugere de uma a três. Roda no executor da IA."""
    return {"correcoes": await _com_a_ia(retorno.sugerir_correcoes_de_processo, supabase, aberto)}


@router.post("/casos/{caso_id}/correcoes")
async def escolher_correcao(
    corpo: CorrecaoEscolhida,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O Comitê escolhe a correção de processo, com responsável e prazo."""
    _agir(
        retorno.escolher_correcao,
        supabase,
        aberto,
        texto=corpo.texto,
        responsavel=corpo.responsavel,
        prazo_em=corpo.prazo_em,
        hoje=hoje_em_sao_paulo(),
    )
    return {"ok": True}
