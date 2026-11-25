"""Router /assistente-do-app: a conversa do robô do canto da tela (issue #2267,
ADR 0113, decisão 8).

Só pede usuário logado, de qualquer papel: o assistente de manual só serve se
todos o veem. Não grava nada; a conversa vive na tela.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.dependencies import get_current_user
from app.limiter import limiter
from app.services import assistente_do_app
from app.services.conhecimento import carregar_kit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistente-do-app", tags=["assistente-do-app"])

# Por endereço, como o limiter do app conta em todo lugar: protege a cota do
# provedor de IA contra uma tela esquecida mandando de novo.
LIMITE_DA_CONVERSA = "10/minute"

SEM_IA = "O assistente está fora do ar agora. Tente de novo mais tarde."
FALHOU = "O assistente não conseguiu responder. Mande a pergunta de novo."


class Fala(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class Pagina(BaseModel):
    modulo: str = Field(max_length=80)
    titulo: str = Field(max_length=200)
    corpo: str = Field(max_length=60000)


class PedidoDaConversa(BaseModel):
    mensagens: list[Fala] = Field(min_length=1, max_length=40)
    paginas_do_manual: list[Pagina] = Field(default_factory=list, max_length=20)


class RespostaDaConversa(BaseModel):
    resposta: str


@router.post("/conversa", response_model=RespostaDaConversa)
@limiter.limit(LIMITE_DA_CONVERSA)
def conversa(
    request: Request,
    payload: PedidoDaConversa,
    _usuario: dict = Depends(get_current_user),
) -> RespostaDaConversa:
    if payload.mensagens[-1].role != "user":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A última fala é da pessoa.")
    cliente = assistente_do_app._cliente()
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SEM_IA)
    paginas = [assistente_do_app.PaginaDoManual(p.modulo, p.titulo, p.corpo) for p in payload.paginas_do_manual]
    try:
        texto = assistente_do_app.responder_a_duvida(
            cliente,
            mensagens=[f.model_dump() for f in payload.mensagens],
            paginas=paginas,
            kit=carregar_kit(),
        )
    except Exception as exc:
        logger.warning("[Assistente do app] a IA não respondeu (%s)", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=FALHOU) from exc
    if not texto:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=FALHOU)
    return RespostaDaConversa(resposta=texto)
