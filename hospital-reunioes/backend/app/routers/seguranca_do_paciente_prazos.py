"""A tabela de prazos do Núcleo, na Configuração (issue #1993, PRD #1979,
ADR 0107 decisão 2).

- `GET /nsp/configuracao/prazos`: os prazos internos (faixa e marco), os
  legais (só leitura) e o histórico das alterações;
- `PUT /nsp/configuracao/prazos/{faixa}/{marco}`: muda um prazo interno. Só a
  Presidência e o Acesso pleno (o recurso `tabela_de_prazos`); o prazo legal é
  recusado.

A alteração não alcança caso já classificado: o caso guarda os vencimentos do
dia da confirmação.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from pydantic import BaseModel
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.services import limite_sem_ip
from app.services.seguranca_do_paciente import prazos

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])

RECURSO_DE_EDICAO = "tabela_de_prazos"


def _indisponivel(erro: Exception, mensagem: str) -> HTTPException:
    logger.error("Falha na tabela de prazos do Núcleo: %s", type(erro).__name__)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=mensagem)


@router.get("/configuracao/prazos")
@limite_sem_ip.limitar("60/minute")
async def ler_tabela_de_prazos_do_nucleo(
    request: Request,
    me: dict = Depends(require_recurso_nsp("configuracao")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A tabela inteira: quem só alcança a configuração lê sem editar."""
    try:
        return prazos.tabela_para_a_configuracao(supabase, pode_editar=RECURSO_DE_EDICAO in me["recursos_nsp"])
    except (APIError, httpx.HTTPError) as erro:
        raise _indisponivel(erro, "Não foi possível abrir a tabela de prazos agora. Tente de novo.") from erro


class PrazoInterno(BaseModel):
    """O prazo novo da célula. `valor` vazio é "sem prazo próprio"."""

    valor: int | None = None
    unidade: str | None = None


@router.put("/configuracao/prazos/{faixa}/{marco}")
@limite_sem_ip.limitar("30/minute")
async def alterar_prazo_interno_do_nucleo(
    request: Request,
    faixa: str,
    marco: str,
    prazo: PrazoInterno,
    me: dict = Depends(require_recurso_nsp(RECURSO_DE_EDICAO)),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Vale para os casos confirmados daqui para a frente."""
    try:
        return prazos.alterar_prazo_interno(supabase, faixa, marco, prazo.valor, prazo.unidade, autor_id=str(me["id"]))
    except prazos.PrazoRecusadoError as erro:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)) from erro
    except (APIError, httpx.HTTPError) as erro:
        raise _indisponivel(erro, "Não foi possível gravar o prazo agora. Tente de novo em instantes.") from erro
