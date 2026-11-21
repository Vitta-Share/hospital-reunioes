"""O período de sombra e a recalibração do agente do Núcleo (issue #2001,
PRD #1979, ADR 0107 decisão 10).

- `GET /nsp/configuracao/concordancia`: a concordância por eixo, os erros
  para baixo e as versões do prompt e da base, na Configuração;
- `GET /nsp/recalibracao`: a tela da pendência "Recalibrar o agente do NSP",
  com os itens do Anexo F (seções 4 e 5) e os marcos de 30 e 60 dias;
- `POST /nsp/recalibracao/{marco}`: concluir a recalibração com uma das três
  decisões (manter, ajustar ou ligar a aprovação em lote).

A leitura é da Presidência e do Acesso pleno (o recurso `triagem`): os erros
para baixo trazem o protocolo do caso, que o super admin não alcança. A
decisão é só de quem tem Acesso pleno: a pendência nasce para a Diretoria, e a
concordância medida é a da Presidência.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.services import limite_sem_ip
from app.services.seguranca_do_paciente import recalibracao
from app.services.seguranca_do_paciente.permissao import PERFIL_ACESSO_PLENO, hoje_em_sao_paulo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])

FALHA_DE_LEITURA = "Não foi possível abrir a recalibração agora. Tente de novo em instantes."
FALHA_DE_GRAVACAO = "Não foi possível gravar a decisão agora. Tente de novo em instantes."
SO_ACESSO_PLENO = "Só quem tem Acesso pleno registra a decisão da recalibração."


def _indisponivel(erro: Exception, mensagem: str) -> HTTPException:
    logger.error("Falha na recalibração do agente do Núcleo: %s", type(erro).__name__)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=mensagem)


def agora_utc() -> datetime:
    return datetime.now(UTC)


def _decide(me: dict) -> bool:
    return me.get("perfil_nsp") == PERFIL_ACESSO_PLENO


@router.get("/configuracao/concordancia")
@limite_sem_ip.limitar("60/minute")
async def concordancia_do_agente(
    request: Request,
    _: dict = Depends(require_recurso_nsp("triagem")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    try:
        return recalibracao.concordancia(supabase)
    except (APIError, httpx.HTTPError) as erro:
        raise _indisponivel(erro, FALHA_DE_LEITURA) from erro


@router.get("/recalibracao")
@limite_sem_ip.limitar("60/minute")
async def tela_da_recalibracao(
    request: Request,
    me: dict = Depends(require_recurso_nsp("triagem")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    try:
        return {**recalibracao.tela(supabase, hoje_em_sao_paulo()), "pode_decidir": _decide(me)}
    except (APIError, httpx.HTTPError) as erro:
        raise _indisponivel(erro, FALHA_DE_LEITURA) from erro


class DecisaoDaRecalibracao(BaseModel):
    """Quem confere a decisão é o serviço, para a recusa sair em palavras."""

    decisao: str | None = Field(default=None, max_length=40)


@router.post("/recalibracao/{marco}")
@limite_sem_ip.limitar("30/minute")
async def decidir_a_recalibracao(
    request: Request,
    marco: int,
    corpo: DecisaoDaRecalibracao,
    me: dict = Depends(require_recurso_nsp("triagem")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Grava a decisão, quem decidiu e quando, e conclui as pendências do marco."""
    if not _decide(me):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SO_ACESSO_PLENO)
    try:
        recalibracao.decidir(supabase, marco, corpo.decisao, autor=me, agora=agora_utc())
        return {"recalibracoes": recalibracao.recalibracoes(supabase)}
    except recalibracao.MarcoNaoChegouError as erro:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(erro)) from erro
    except recalibracao.JaDecididaError as erro:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(erro)) from erro
    except recalibracao.RecalibracaoRecusadaError as erro:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)) from erro
    except (APIError, httpx.HTTPError) as erro:
        raise _indisponivel(erro, FALHA_DE_GRAVACAO) from erro
