"""A tela de triagem do Núcleo (issue #1992, PRD #1979, ADR 0095 e 0107).

- `GET /nsp/triagem`: a fila, da mais antiga para a mais nova;
- `GET /nsp/triagem/{id}`: a tela de um caso, com a sugestão e o que o
  sistema calcula;
- `GET /nsp/triagem/{id}/contexto`: o cálculo de novo, para a categoria e a
  faixa que a pessoa escolheu ao ajustar;
- `POST /nsp/triagem/{id}`: confirmar (sem classificação, vale a sugestão) ou
  ajustar (com a classificação da pessoa);
- `GET` e `PUT /nsp/configuracao/cortes-de-frequencia`: os cortes da matriz
  de prioridade, na Configuração do módulo.

A triagem é da Presidência e do Acesso pleno (o recurso `triagem`); os cortes,
de quem alcança a configuração.
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.services import limite_sem_ip
from app.services.seguranca_do_paciente import triagem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])

FALHA_DE_LEITURA = "Não foi possível abrir a triagem agora. Tente de novo em instantes."
FALHA_DE_GRAVACAO = "Não foi possível gravar a triagem agora. Tente de novo em instantes."


def _indisponivel(erro: Exception, mensagem: str) -> HTTPException:
    logger.error("Falha na triagem do Núcleo: %s", type(erro).__name__)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=mensagem)


@router.get("/triagem")
@limite_sem_ip.limitar("60/minute")
async def fila_de_triagem(
    request: Request,
    _: dict = Depends(require_recurso_nsp("triagem")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A fila de triagem: sem relato e sem quem notificou."""
    try:
        return {"fila": triagem.fila(supabase)}
    except (APIError, httpx.HTTPError) as erro:
        raise _indisponivel(erro, FALHA_DE_LEITURA) from erro
