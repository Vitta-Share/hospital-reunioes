"""O link de uso único do Núcleo, sem login (issue #1996, ADR 0107 decisão 8).

Quem chega aqui veio pelo e-mail do encaminhamento à Segurança do Trabalho ou
à queixa técnica:

- `GET /nsp/recebimento/{token}`: o resumo do caso, sem o relato e sem quem
  notificou;
- `POST /nsp/recebimento/{token}/recebido`: o botão "Recebido", uma vez só.

Abrir não confirma: é POST, e não o GET do link, porque leitor de e-mail que
abre link sozinho gastaria o uso único. Depois do clique, e depois da
validade, as duas rotas recusam. As duas ficam fora do gate de recurso de
propósito (a varredura do módulo as lista como exceção).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from supabase import Client

from app.dependencies import get_supabase_client
from app.limiter import limiter
from app.services.seguranca_do_paciente import recebimento

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp/recebimento", tags=["seguranca-do-paciente"])

LINK_INVALIDO = "Link inválido."
JA_RECEBIDO = "Este link já foi usado: o recebimento deste caso já foi confirmado."
VENCIDO = "Este link venceu. Peça ao Núcleo de Segurança do Paciente um envio novo."
INDISPONIVEL = "Não foi possível abrir o caso agora. Tente de novo em instantes."


def agora_utc() -> datetime:
    return datetime.now(UTC)


def _carregar(supabase, token: str, agora: datetime) -> dict:
    try:
        return recebimento.carregar_pelo_token(supabase, token, agora)
    except recebimento.LinkInvalidoError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=LINK_INVALIDO) from None
    except recebimento.JaRecebidoError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=JA_RECEBIDO) from None
    except recebimento.LinkVencidoError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=VENCIDO) from None
    except (APIError, httpx.HTTPError) as erro:
        logger.error("Falha ao ler o link do Recebido do Núcleo: %s", type(erro).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.get("/{token}")
@limiter.limit("30/minute")
async def abrir_o_link(request: Request, token: str, supabase: Client = Depends(get_supabase_client)) -> dict:
    """O resumo do caso encaminhado ao setor."""
    linha = _carregar(supabase, token, agora_utc())
    try:
        return recebimento.resumo(supabase, linha)
    except (APIError, httpx.HTTPError) as erro:
        logger.error("Falha ao ler o resumo do caso pelo link do Recebido: %s", type(erro).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro


@router.post("/{token}/recebido")
@limiter.limit("10/minute")
async def confirmar_o_recebido(request: Request, token: str, supabase: Client = Depends(get_supabase_client)) -> dict:
    """O clique em Recebido. O segundo clique, ou o que cruza com outro, é 410."""
    agora = agora_utc()
    linha = _carregar(supabase, token, agora)
    try:
        carimbo = recebimento.confirmar(supabase, linha, agora)
    except (APIError, httpx.HTTPError) as erro:
        logger.error("Falha ao gravar o Recebido do setor: %s", type(erro).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL) from erro
    if carimbo is None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=JA_RECEBIDO)
    return {"recebido_em": carimbo}
