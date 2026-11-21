"""O portão único do lado do Comitê do Canal de Conduta (ADR 0097, decisão 4).

Toda rota do Comitê depende de `portao_da_lista` ou de `portao_do_caso`, e
`tests/test_conduta_varredura.py` reprova a rota do módulo que não dependa.

Na ordem: a chave de cifra (sem ela, 503 e nada é lido nem gravado), a pessoa
logada e não desligada, a designação dela (`acesso`) e, no caso, a leitura
gravada na trilha antes de o caso sair. Se a trilha não grava, o caso não sai.

Toda recusa é a mesma recusa, com o mesmo texto: caso que não existe e caso
fechado para a pessoa não se distinguem. O super admin não passa por cima.
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from postgrest.exceptions import APIError
from supabase import Client

from app.dependencies import barrar_desligado, get_current_user, get_participante_for_user, get_supabase_client
from app.services.conduta import cifra, trilha
from app.services.conduta.acesso import (
    PessoaNoComite,
    caso_se_a_pessoa_abre,
    casos_da_pessoa,
    pessoa_no_comite,
)

logger = logging.getLogger(__name__)

RECUSA = "Sem acesso a este conteúdo do Canal de Conduta"
INDISPONIVEL = "O Canal de Conduta está indisponível no momento"


def _recusar() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=RECUSA)


def _indisponivel() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=INDISPONIVEL)


async def _pessoa(current_user: dict, supabase) -> tuple[dict, PessoaNoComite]:
    if not cifra.chave_configurada():
        raise _indisponivel()
    me = await get_participante_for_user(current_user, supabase)
    barrar_desligado(me)
    if not me:
        raise _recusar()
    return me, pessoa_no_comite(supabase, me["id"])


async def portao_da_lista(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
) -> list[dict]:
    """Os casos que a pessoa abre, só com os metadados. 403 a quem não tem
    designação nenhuma no Canal."""
    _, pessoa = await _pessoa(current_user, supabase)
    casos = casos_da_pessoa(supabase, pessoa)
    if casos is None:
        raise _recusar()
    return casos


async def portao_do_caso(
    caso_id: UUID,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O caso inteiro, ainda cifrado, depois de gravada a leitura na trilha."""
    me, pessoa = await _pessoa(current_user, supabase)
    caso = caso_se_a_pessoa_abre(supabase, pessoa, str(caso_id))
    if caso is None:
        raise _recusar()
    try:
        trilha.registrar(supabase, caso["id"], me["id"], "leitura", "abriu o caso")
    except (APIError, httpx.HTTPError) as erro:
        logger.error("Leitura de caso do Canal de Conduta sem registro na trilha; o caso não sai: %s", erro)
        raise _indisponivel() from erro
    return caso
