"""Canal de Conduta, a ata de deliberação e a reunião do Comitê (issue #1834,
PRD #1786; especificação, seções 7.3, 8 e Anexo D).

A transcrição da reunião (só ela: sem seletor de tipo e sem áudio), a lista
de conferência e o "CONCLUIR REUNIÃO", a ata gerada pelo agente num clique, o
envio aos três votantes pela ClickSign, a reconsulta e a cópia assinada. Toda
rota passa pelo portão (`app.services.conduta.portao`). Arquivo nenhum sai por
URL do bucket: a rota confere o acesso, decifra e entrega.
"""

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from supabase import Client

from app.dependencies import get_supabase_client
from app.services import ai_processor
from app.services.conduta import assinaturas, ata, cifra
from app.services.conduta.portao import INDISPONIVEL, CasoAberto, portao_da_acao

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class DeclaracaoDaReuniao(BaseModel):
    item: Literal["gravacao_apagada", "arquivos_apagados"]


def _agir(funcao, *argumentos, **nomeados):
    try:
        return funcao(*argumentos, **nomeados)
    except ata.AtaRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.post("/casos/{caso_id}/reuniao/transcricao")
async def anexar_transcricao_da_reuniao(
    arquivo: UploadFile = File(...),
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """ANEXAR TRANSCRIÇÃO DA REUNIÃO DO COMITÊ, na etapa Voto do rito Completo."""
    _agir(ata.conferir_transcricao, arquivo.filename or "", arquivo.size or 1)
    conteudo = await arquivo.read()
    return _agir(ata.anexar_transcricao_da_reuniao, supabase, aberto, arquivo.filename or "", conteudo)


@router.post("/casos/{caso_id}/reuniao/conferencia")
async def marcar_item_da_reuniao(
    corpo: DeclaracaoDaReuniao,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    _agir(ata.marcar_item_da_reuniao, supabase, aberto, corpo.item)
    return {"ok": True}


@router.post("/casos/{caso_id}/reuniao/conclusao")
async def concluir_reuniao(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """CONCLUIR REUNIÃO: com os quatro itens, e a transcrição é eliminada."""
    await run_in_threadpool(_agir, ata.concluir_reuniao, supabase, aberto)
    return {"ok": True}


@router.post("/casos/{caso_id}/ata")
async def gerar_ata(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """GERAR ATA: o agente do Anexo D redige. Roda no executor da IA (issue #773)."""
    try:
        linha = await ai_processor.chamar_ia_fora_do_loop(ata.gerar_ata_de_deliberacao, supabase, aberto)
    except ata.AtaRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro
    return {"versao": linha["versao"]}


@router.post("/casos/{caso_id}/ata/assinatura")
async def enviar_ata_para_assinatura(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """A última versão da ata vai à ClickSign para os três votantes."""
    linha = await run_in_threadpool(_agir, ata.enviar_para_assinatura, supabase, aberto)
    return {"situacao": linha["situacao"], "erro": linha.get("erro")}


@router.post("/casos/{caso_id}/ata/reconsulta")
async def reconsultar_ata(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """Reconsultar status: pergunta à ClickSign sem depender do webhook."""
    linha = _agir(ata.assinatura_aberta, supabase, aberto)
    try:
        await run_in_threadpool(assinaturas.reconsultar, supabase, linha)
    except assinaturas.AssinaturaIndisponivelError as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="A assinatura eletrônica não respondeu agora."
        ) from erro
    return {"ok": True}


@router.get("/casos/{caso_id}/ata/assinada")
async def abrir_ata_assinada(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> Response:
    """A cópia da ata assinada, entregue pelo backend, sem cache."""
    conteudo = _agir(ata.abrir_assinada, supabase, aberto)
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )
