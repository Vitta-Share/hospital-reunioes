"""Segurança do Paciente: a assinatura dos documentos do Núcleo (issue #1771).

A Presidência e o Acesso pleno (`gerir_nucleo`) mandam para assinatura uma
versão nova do ato de designação, do Regimento ou do Plano de Segurança do
Paciente, reconsultam o status e reenviam. Quem lê Documentos (`documentos`)
vê quem já assinou e baixa o arquivo assinado. O super admin sem Acesso pleno
não alcança nada daqui (ADR 0095, decisão 4).

A versão enviada só vira a vigente quando todas as assinaturas chegam; o
retorno automático da assinatura mora no webhook. Os dois caminhos usam o
mesmo serviço (`assinatura_dos_documentos`).
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field, model_validator
from starlette.concurrency import run_in_threadpool
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.limiter import limiter
from app.services.seguranca_do_paciente import assinatura_dos_documentos as assinatura
from app.services.seguranca_do_paciente import termo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])

TipoAssinado = Literal["ato_designacao", "regimento", "plano_seguranca_paciente"]

_INDISPONIVEL = "Os documentos do Núcleo estão indisponíveis agora. Tente de novo em instantes."
_NAO_ENCONTRADO = "Documento não encontrado."


class VersaoParaAssinatura(BaseModel):
    tipo: TipoAssinado
    titulo: str = Field(min_length=1, max_length=200)
    texto: str = Field(max_length=200_000)
    natureza_revisao: Literal["material", "redacao"] | None = None

    @model_validator(mode="after")
    def _completa(self) -> VersaoParaAssinatura:
        self.titulo = self.titulo.strip()
        if not self.titulo:
            raise ValueError("Dê um título ao documento.")
        self.texto = self.texto.strip()
        if not self.texto:
            raise ValueError("Escreva o texto do documento: é ele que vai para assinatura.")
        if self.tipo == "regimento" and self.natureza_revisao is None:
            raise ValueError("Diga se a revisão do Regimento é material ou só de redação.")
        return self


def _documento(supabase, documento_id: str) -> dict:
    try:
        linhas = (
            supabase.table("nsp_documentos")
            .select("id, tipo, versao, vigente, arquivo_assinado_path")
            .eq("id", documento_id)
            .limit(1)
            .execute()
            .data
        ) or []
    except APIError as erro:
        # Id que não é UUID (22P02), de link velho ou URL digitada, é documento
        # que não existe; o resto é o banco.
        if getattr(erro, "code", None) == "22P02":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADO) from erro
        logger.warning("Documento do Núcleo ilegível: %s", erro)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_INDISPONIVEL) from erro
    except httpx.HTTPError as erro:
        logger.warning("Documento do Núcleo ilegível: %s", erro)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_INDISPONIVEL) from erro
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADO)
    return linhas[0]


def _situacao(supabase, documento: dict, envio: dict) -> dict:
    """A situação do envio com a versão relida: a reconsulta pode tê-la
    tornado vigente."""
    documento = _documento(supabase, documento["id"])
    mais_nova = assinatura.tem_versao_mais_nova(supabase, documento)
    return assinatura.situacao_do_envio(supabase, documento, envio, mais_nova=mais_nova)


@router.post("/documentos/assinatura", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def enviar_para_assinatura(
    request: Request,
    corpo: VersaoParaAssinatura,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Grava a versão seguinte do tipo fora da vigência e a manda para os
    signatários do tipo. A anterior continua vigente até todos assinarem."""
    try:
        documento, envio = await run_in_threadpool(
            assinatura.enviar_versao_para_assinatura,
            supabase,
            tipo=corpo.tipo,
            titulo=corpo.titulo,
            texto=corpo.texto,
            natureza_revisao=corpo.natureza_revisao,
            autor_id=me["id"],
        )
    except assinatura.AssinaturaNaoEnviadaError as erro:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)) from erro
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Envio de documento do Núcleo para assinatura falhou: %s", erro)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_INDISPONIVEL) from erro
    return {
        "documento": {
            "id": documento["id"],
            "tipo": documento["tipo"],
            "versao": documento["versao"],
            "titulo": documento["titulo"],
            "vigente": bool(documento.get("vigente")),
        },
        "assinatura": assinatura.situacao_do_envio(supabase, documento, envio, mais_nova=False),
        "aviso": envio.get("erro"),
    }


@router.get("/assinaturas-dos-documentos")
@limiter.limit("60/minute")
async def assinaturas_dos_documentos(
    request: Request,
    _: dict = Depends(require_recurso_nsp("documentos")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O último envio de cada versão assinada: quem já assinou e quem falta."""
    try:
        return {"assinaturas": assinatura.situacao_das_assinaturas(supabase)}
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Assinaturas dos documentos do Núcleo ilegíveis: %s", erro)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_INDISPONIVEL) from erro


@router.post("/documentos/{documento_id}/assinatura/reconsultar")
@limiter.limit("30/minute")
async def reconsultar_assinatura(
    request: Request,
    documento_id: str,
    tarefas: BackgroundTasks,
    _: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Pergunta à assinatura eletrônica quem já assinou e aplica o mesmo
    tratamento do retorno automático. A revisão material do Regimento que
    vigorou agora gera o Termo novo dos membros depois da resposta, com o
    autor do envio (issue #1800)."""
    documento = _documento(supabase, documento_id)

    def _termos_da_revisao(autor_id):
        tarefas.add_task(termo.termos_da_revisao_material, supabase, autor_id=autor_id)

    try:
        envio = await run_in_threadpool(
            assinatura.reconsultar_assinaturas, supabase, documento, ao_vigorar_revisao_material=_termos_da_revisao
        )
    except assinatura.AssinaturaIndisponivelError as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A assinatura eletrônica não respondeu. Tente de novo em instantes.",
        ) from erro
    if envio is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta versão não tem envio para assinatura. Use Reenviar para assinatura.",
        )
    return _situacao(supabase, documento, envio)


@router.post("/documentos/{documento_id}/assinatura/reenviar")
@limiter.limit("10/minute")
async def reenviar_para_assinatura(
    request: Request,
    documento_id: str,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Cancela o envio aberto da versão e manda outro, com os signatários de
    agora. Só a versão que ainda espera assinatura aceita."""
    documento = _documento(supabase, documento_id)
    mais_nova = assinatura.tem_versao_mais_nova(supabase, documento)
    if not assinatura.pode_reenviar(documento, assinatura.ultimo_envio(supabase, documento["id"]), mais_nova):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Só a versão mais nova, ainda sem todas as assinaturas, vai de novo para assinatura.",
        )
    try:
        envio = await run_in_threadpool(assinatura.refazer_envio, supabase, documento, autor_id=me["id"])
    except assinatura.AssinaturaNaoEnviadaError as erro:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)) from erro
    return {**_situacao(supabase, documento, envio), "aviso": envio.get("erro")}


@router.get("/documentos/{documento_id}/arquivo-assinado")
@limiter.limit("60/minute")
async def arquivo_assinado(
    request: Request,
    documento_id: str,
    _: dict = Depends(require_recurso_nsp("documentos")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O link do PDF assinado da versão, válido por 10 minutos. Só dos tipos que
    vão para assinatura aqui: o Termo de Adesão assinado de cada membro sai só
    pela ficha do membro, com `gerir_nucleo`."""
    documento = _documento(supabase, documento_id)
    if documento.get("tipo") not in assinatura.SIGNATARIOS_POR_TIPO:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADO)
    if not documento.get("arquivo_assinado_path"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Esta versão não tem arquivo assinado.")
    url = assinatura.link_do_arquivo_assinado(supabase, documento)
    if not url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_INDISPONIVEL)
    return {"url": url}
