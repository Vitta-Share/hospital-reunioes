"""Segurança do Paciente: o Termo de Adesão na ficha do membro (issue #1768).

A Presidência e o Acesso pleno (`gerir_nucleo`) reconsultam o status da
assinatura, reenviam o documento e liberam o membro à mão, com justificativa.
A Diretoria lê a composição, mas não mexe no Termo; o super admin sem Acesso
pleno não alcança nada daqui (ADR 0095, decisão 4).

O membro sem Termo válido pergunta pelo próprio documento pendente
(`/nsp/meu-termo`), para a faixa das telas bloqueadas.

O gerar e enviar do cadastro mora no router dos membros; o retorno automático
da assinatura, no webhook. Os três caminhos usam o mesmo serviço (`termo`).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.limiter import limiter
from app.routers.seguranca_do_paciente_membros import _aberta, _nucleo_id, _participacao, _responder
from app.services.seguranca_do_paciente import termo
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo, id_do_nucleo, participacoes_vigentes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])

_JA_ASSINADO = "O Termo deste membro já está assinado."


class Liberacao(BaseModel):
    justificativa: str = Field(max_length=1000)

    @field_validator("justificativa")
    @classmethod
    def _preenchida(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Escreva a justificativa da liberação.")
        return valor


def _pendente(participacao: dict) -> None:
    _aberta(participacao)
    if participacao.get("termo_assinado_em"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_JA_ASSINADO)


@router.post("/membros/{participacao_id}/termo/reconsultar")
@limiter.limit("30/minute")
async def reconsultar_status(
    request: Request,
    participacao_id: str,
    _: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Pergunta à assinatura eletrônica e aplica o mesmo tratamento do
    retorno automático."""
    nucleo_id = _nucleo_id(supabase)
    participacao = _participacao(supabase, nucleo_id, participacao_id)
    try:
        envio = await run_in_threadpool(termo.reconsultar, supabase, participacao)
    except termo.AssinaturaIndisponivelError as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A assinatura eletrônica não respondeu. Tente de novo em instantes.",
        ) from erro
    if envio is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este membro ainda não tem Termo enviado. Use Reenviar o Termo.",
        )
    return _responder(supabase, participacao_id, nucleo_id)


@router.post("/membros/{participacao_id}/termo/reenviar")
@limiter.limit("10/minute")
async def reenviar_termo(
    request: Request,
    participacao_id: str,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Cancela o envio anterior e gera outro documento, com outro identificador."""
    nucleo_id = _nucleo_id(supabase)
    participacao = _participacao(supabase, nucleo_id, participacao_id)
    _pendente(participacao)
    try:
        envio = await run_in_threadpool(termo.reenviar, supabase, participacao, autor_id=me["id"])
    except termo.TermoNaoGeradoError as erro:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)) from erro
    return {**_responder(supabase, participacao_id, nucleo_id), "aviso_termo": envio.get("erro")}


@router.post("/membros/{participacao_id}/termo/liberar")
@limiter.limit("10/minute")
async def liberar_sem_assinatura(
    request: Request,
    participacao_id: str,
    body: Liberacao,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Libera o membro sem a assinatura eletrônica. Justificativa obrigatória,
    gravada na trilha com o autor e a data."""
    nucleo_id = _nucleo_id(supabase)
    participacao = _participacao(supabase, nucleo_id, participacao_id)
    _pendente(participacao)
    termo.liberar(supabase, participacao, autor_id=me["id"], justificativa=body.justificativa)
    return _responder(supabase, participacao_id, nucleo_id)


@router.get("/membros/{participacao_id}/termo")
@limiter.limit("60/minute")
async def termo_do_membro(
    request: Request,
    participacao_id: str,
    _: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O último envio do membro: situação, erro e o link do documento."""
    participacao = _participacao(supabase, _nucleo_id(supabase), participacao_id)
    envio = termo.ultimo_envio(supabase, participacao["id"])
    if not envio:
        return {"situacao": None, "erro": None, "enviado_em": None, "documento_url": None}
    return {
        "situacao": envio.get("situacao"),
        "erro": envio.get("erro"),
        "enviado_em": envio.get("enviado_em"),
        "documento_url": termo.link_do_documento(supabase, envio),
    }


@router.get("/meu-termo")
@limiter.limit("60/minute")
async def meu_termo(
    request: Request,
    me: dict = Depends(require_recurso_nsp("ver_modulo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Para a faixa das telas bloqueadas: a pessoa tem Termo pendente numa
    Participação vigente, e o link do documento, quando ele já foi gerado."""
    nucleo_id = id_do_nucleo(supabase)
    linhas = (
        (
            participacoes_vigentes(supabase, nucleo_id, hoje_em_sao_paulo())
            .eq("participante_id", me["id"])
            .execute()
            .data
        )
        if nucleo_id
        else []
    ) or []
    if not linhas or any(linha.get("termo_assinado_em") for linha in linhas):
        return {"pendente": False, "documento_url": None}
    envio = termo.ultimo_envio(supabase, linhas[0]["id"])
    if envio and envio.get("situacao") == "cancelado":
        envio = None
    return {"pendente": True, "documento_url": termo.link_do_documento(supabase, envio)}
