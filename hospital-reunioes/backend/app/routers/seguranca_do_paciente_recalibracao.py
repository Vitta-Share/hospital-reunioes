"""O período de sombra e a recalibração do agente do Núcleo (issue #2001,
PRD #1979, ADR 0107 decisão 10).

- `GET /nsp/configuracao/concordancia`: a concordância por eixo, os erros
  para baixo e as versões do prompt e da base, na Configuração;

A leitura é da Presidência e do Acesso pleno (o recurso `triagem`): os erros
para baixo trazem o protocolo do caso, que o super admin não alcança.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.services import limite_sem_ip
from app.services.seguranca_do_paciente import recalibracao

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])

FALHA_DE_LEITURA = "Não foi possível abrir a recalibração agora. Tente de novo em instantes."


def _indisponivel(erro: Exception, mensagem: str) -> HTTPException:
    logger.error("Falha na recalibração do agente do Núcleo: %s", type(erro).__name__)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=mensagem)


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
