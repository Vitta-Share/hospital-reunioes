"""Canal de Conduta, a página de acompanhamento (issue #1845; especificação,
P7; ADR 0097, decisões 10 e 11).

Sem login, como o resto do lado público: nasce fechada pela mesma chave de
abertura e sai do log sem endereço. Protocolo, código e texto viajam só no
corpo, nunca no endereço. O limite de tentativas conta por aparelho com a
chave embaralhada, sem guardar o endereço (`limite_sem_ip`): é o que segura
quem tenta adivinhar um código.

Toda recusa é a mesma 404, no mesmo tempo (`acompanhamento.conferir`).
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from postgrest.exceptions import APIError
from supabase import Client

from app.dependencies import get_supabase_client
from app.routers.conduta_publico import SEM_CACHE, _corpo, exigir_canal_aberto
from app.services import limite_sem_ip
from app.services.conduta import acompanhamento, cifra

router = APIRouter(prefix="/conduta", tags=["canal-de-conduta-publico"], dependencies=[Depends(exigir_canal_aberto)])

LIMITE_DA_CONSULTA = "5/minute;30/hour"
LIMITE_DO_COMPLEMENTO = "5/minute;20/hour"
NAO_ENCONTRADO = "Não encontramos um relato com esse protocolo e esse código. Confira os dois e tente de novo."
FALHA = "Não deu para abrir o acompanhamento agora. Tente de novo em alguns minutos."


async def _caso_conferido(request: Request, supabase) -> tuple[dict, dict]:
    try:
        dados = await _corpo(request)
    except HTTPException:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    try:
        caso = acompanhamento.conferir(supabase, dados.get("protocolo"), dados.get("codigo"))
    except (APIError, httpx.HTTPError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=FALHA) from None
    if caso is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NAO_ENCONTRADO)
    return caso, dados


def _pagina(supabase, caso: dict) -> dict:
    try:
        return acompanhamento.pagina_publica(supabase, caso)
    except (cifra.CifraIndisponivelError, APIError, httpx.HTTPError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=FALHA) from None


@router.post("/acompanhamento")
@limite_sem_ip.limitar(LIMITE_DA_CONSULTA)
async def acompanhar(request: Request, response: Response, supabase: Client = Depends(get_supabase_client)) -> dict:
    """A situação do caso e as mensagens do Comitê, com o protocolo e o
    código no corpo."""
    response.headers.update(SEM_CACHE)
    caso, _ = await _caso_conferido(request, supabase)
    return _pagina(supabase, caso)


@router.post("/acompanhamento/complemento")
@limite_sem_ip.limitar(LIMITE_DO_COMPLEMENTO)
async def complementar(request: Request, response: Response, supabase: Client = Depends(get_supabase_client)) -> dict:
    """O complemento de quem relatou. Devolve a página já com ele."""
    response.headers.update(SEM_CACHE)
    caso, dados = await _caso_conferido(request, supabase)
    try:
        acompanhamento.complementar(supabase, caso, dados.get("texto"))
    except acompanhamento.MensagemRecusadaError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from None
    except (cifra.CifraIndisponivelError, APIError, httpx.HTTPError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não deu para enviar o complemento agora. Tente de novo em alguns minutos.",
        ) from None
    return _pagina(supabase, caso)
