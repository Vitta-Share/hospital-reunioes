"""Canal de Conduta, os depoimentos da Apuração (issue #1830, PRD #1786, ADR
0097, decisão 2), e o relatório de apuração com o envio para voto (issue
#1832).

O cartão de cada pessoa ouvida, os três botões de arquivo (transcrição, áudio
e termo assinado), a lista de conferência e a conclusão. Toda rota passa pelo
portão (`app.services.conduta.portao`). Arquivo nenhum sai por URL do bucket:
a rota confere o acesso, decifra e entrega.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client
from app.services import ai_processor
from app.services.conduta import assinaturas, cifra, depoimentos, relatorio
from app.services.conduta.portao import INDISPONIVEL, CasoAberto, portao_da_acao

router = APIRouter(prefix="/comite-de-conduta", tags=["canal-de-conduta"])


class PessoaAOuvir(BaseModel):
    nome: str = Field(default="", max_length=400)
    cargo: str = Field(default="", max_length=400)
    papel: Literal["acusado", "testemunha", "denunciante"]


class ItemDaLista(BaseModel):
    item: str = Field(max_length=40)


class SemGravacao(BaseModel):
    motivo: str = Field(default="", max_length=1000)
    pontos: str = Field(default="", max_length=40000)


class VersaoDoTexto(BaseModel):
    texto: str = Field(default="", max_length=20000)


def _agir(funcao, *argumentos, **nomeados):
    try:
        return funcao(*argumentos, **nomeados)
    except (depoimentos.DepoimentoRecusadoError, relatorio.RelatorioRecusadoError) as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.post("/casos/{caso_id}/depoimentos")
async def adicionar_pessoa_a_ouvir(
    corpo: PessoaAOuvir, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    depoimento = _agir(depoimentos.adicionar_pessoa, supabase, aberto, **corpo.model_dump())
    return {"depoimento": {"id": depoimento["id"]}}


async def _ler(tipo: str, enviados: list[UploadFile]) -> list[depoimentos.ArquivoRecebido]:
    """Lê cada arquivo depois de conferir o tamanho anunciado: um áudio grande
    demais é recusado antes de ir para a memória. O tamanho lido manda."""
    recebidos = []
    for enviado in enviados:
        _agir(depoimentos.conferir_arquivo, tipo, enviado.filename or "", enviado.size or 1)
        conteudo = await enviado.read()
        _agir(depoimentos.conferir_arquivo, tipo, enviado.filename or "", len(conteudo))
        recebidos.append(depoimentos.ArquivoRecebido(enviado.filename or "", conteudo))
    return recebidos


async def _anexar(supabase, aberto: CasoAberto, depoimento_id: UUID, tipo: str, enviados: list[UploadFile]) -> dict:
    recebidos = await _ler(tipo, enviados)
    return _agir(depoimentos.anexar, supabase, aberto, str(depoimento_id), tipo, recebidos)


@router.post("/casos/{caso_id}/depoimentos/{depoimento_id}/transcricao")
async def anexar_transcricao(
    depoimento_id: UUID,
    arquivo: UploadFile = File(...),
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    return await _anexar(supabase, aberto, depoimento_id, "transcricao", [arquivo])


@router.post("/casos/{caso_id}/depoimentos/{depoimento_id}/audio")
async def anexar_audio(
    depoimento_id: UUID,
    arquivo: UploadFile = File(...),
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    return await _anexar(supabase, aberto, depoimento_id, "audio", [arquivo])


@router.post("/casos/{caso_id}/depoimentos/{depoimento_id}/termo-assinado")
async def anexar_termo_assinado(
    depoimento_id: UUID,
    arquivo: list[UploadFile] = File(...),
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Arquivo ou câmera do celular: uma foto por página, até cinco."""
    return await _anexar(supabase, aberto, depoimento_id, "termo_assinado", arquivo)


@router.post("/casos/{caso_id}/depoimentos/{depoimento_id}/conferencia")
async def marcar_item_da_lista(
    depoimento_id: UUID,
    corpo: ItemDaLista,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    _agir(depoimentos.marcar_item, supabase, aberto, str(depoimento_id), corpo.item)
    return {"ok": True}


@router.post("/casos/{caso_id}/depoimentos/{depoimento_id}/sem-gravacao")
async def registrar_sem_gravacao(
    depoimento_id: UUID,
    corpo: SemGravacao,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    _agir(depoimentos.registrar_sem_gravacao, supabase, aberto, str(depoimento_id), **corpo.model_dump())
    return {"ok": True}


@router.post("/casos/{caso_id}/depoimentos/{depoimento_id}/conclusao")
async def concluir_depoimento(
    depoimento_id: UUID,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    _agir(depoimentos.concluir, supabase, aberto, str(depoimento_id))
    return {"ok": True}


@router.get("/casos/{caso_id}/depoimentos/{depoimento_id}/arquivos/{arquivo_id}")
async def abrir_arquivo(
    depoimento_id: UUID,
    arquivo_id: UUID,
    aberto: CasoAberto = Depends(portao_da_acao),
    supabase: Client = Depends(get_supabase_client),
) -> Response:
    """O arquivo decifrado, entregue pelo backend. Nada de cache no navegador
    nem no caminho."""
    conteudo, content_type = _agir(depoimentos.abrir_arquivo, supabase, aberto, str(depoimento_id), str(arquivo_id))
    return Response(
        content=conteudo,
        media_type=content_type,
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


# ── O relatório de apuração e o envio para voto (issue #1832) ───────────────


async def _redigir(supabase, aberto: CasoAberto, tipo: str) -> dict:
    """O agente roda no executor da IA, fora do loop (issue #773)."""
    try:
        linha = await ai_processor.chamar_ia_fora_do_loop(
            relatorio.redigir_documento_da_apuracao, supabase, aberto, tipo
        )
    except relatorio.RelatorioRecusadoError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from recusa
    except cifra.CifraIndisponivelError as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro
    return {"versao": linha["versao"]}


@router.post("/casos/{caso_id}/relatorio")
async def gerar_relatorio(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """GERAR RELATÓRIO: o agente redige o relatório de uma página."""
    return await _redigir(supabase, aberto, "relatorio")


@router.post("/casos/{caso_id}/cronologia")
async def montar_cronologia(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """MONTAR CRONOLOGIA: o agente monta a cronologia dos fatos."""
    return await _redigir(supabase, aberto, "cronologia")


@router.post("/casos/{caso_id}/relatorio/versoes")
async def editar_relatorio(
    corpo: VersaoDoTexto, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    linha = _agir(relatorio.editar, supabase, aberto, "relatorio", corpo.texto)
    return {"versao": linha["versao"]}


@router.post("/casos/{caso_id}/cronologia/versoes")
async def editar_cronologia(
    corpo: VersaoDoTexto, aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    linha = _agir(relatorio.editar, supabase, aberto, "cronologia", corpo.texto)
    return {"versao": linha["versao"]}


@router.post("/casos/{caso_id}/relatorio/assinatura")
async def enviar_relatorio_para_assinatura(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """No rito Completo, a última versão vai à ClickSign para os apuradores."""
    linha = await run_in_threadpool(_agir, relatorio.enviar_para_assinatura, supabase, aberto)
    return {"situacao": linha["situacao"], "erro": linha.get("erro")}


@router.post("/casos/{caso_id}/relatorio/reconsulta")
async def reconsultar_relatorio(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """Reconsultar status: pergunta à ClickSign sem depender do webhook."""
    linha = _agir(relatorio.assinatura_aberta, supabase, aberto)
    try:
        await run_in_threadpool(assinaturas.reconsultar, supabase, linha)
    except assinaturas.AssinaturaIndisponivelError as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="A assinatura eletrônica não respondeu agora."
        ) from erro
    return {"ok": True}


@router.get("/casos/{caso_id}/relatorio/assinado")
async def abrir_relatorio_assinado(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> Response:
    """A cópia do relatório assinado, entregue pelo backend."""
    conteudo = _agir(relatorio.abrir_assinado, supabase, aberto)
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )


@router.post("/casos/{caso_id}/envio-para-voto")
async def enviar_para_voto(
    aberto: CasoAberto = Depends(portao_da_acao), supabase: Client = Depends(get_supabase_client)
) -> dict:
    """ENVIAR PARA VOTO: fecha a Apuração."""
    caso = _agir(relatorio.enviar_para_voto, supabase, aberto)
    return {"caso": {"id": caso["id"], "etapa": caso["etapa"]}}
