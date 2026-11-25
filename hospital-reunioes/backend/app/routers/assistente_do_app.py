"""Router /assistente-do-app: a conversa do robô do canto da tela (issue #2267,
ADR 0113, decisão 8) e o Roteiro do bug (issue #2275).

Só pede usuário logado, de qualquer papel: o assistente de manual só serve se
todos o veem. A dúvida não grava nada; a conversa vive na tela. O bug vira
Demanda (`services/relato_de_bug.py`).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import barrar_desligado, get_current_user, get_participante_for_user, get_supabase_client
from app.limiter import limiter
from app.services import assistente_do_app, relato_de_bug
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


# ─── O Roteiro do bug (issue #2275) ─────────────────────────────────────────

MOTIVO_SEM_CADASTRO = "O seu cadastro não foi encontrado no aplicativo. Avise a equipe de Tecnologia."


async def pessoa_logada(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O cadastro de quem relata, de qualquer papel: o autor da Demanda."""
    pessoa = await get_participante_for_user(current_user, supabase)
    barrar_desligado(pessoa)
    if not pessoa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MOTIVO_SEM_CADASTRO)
    return pessoa


class RespostasDoBug(BaseModel):
    onde: str = Field(default="", max_length=2000)
    o_que_aconteceu: str = Field(default="", max_length=2000)
    o_que_esperava: str = Field(default="", max_length=2000)
    como_repetir: str = Field(default="", max_length=2000)


class ResumoDoBug(BaseModel):
    titulo: str
    onde: str
    o_que_aconteceu: str
    o_que_esperava: str
    como_repetir: str
    criterios: list[str]


class RelatoRegistrado(BaseModel):
    demanda_id: str
    resumo: ResumoDoBug


class PrintsDoRelato(BaseModel):
    prints: int


class RelatoEnviado(BaseModel):
    demanda_id: str


def _recusa(recusa: relato_de_bug.RelatoRecusadoError) -> HTTPException:
    return HTTPException(status_code=recusa.status_code, detail=str(recusa))


@router.post("/bug", response_model=RelatoRegistrado)
@limiter.limit(LIMITE_DA_CONVERSA)
def registrar_o_bug(
    request: Request,
    payload: RespostasDoBug,
    pessoa: dict = Depends(pessoa_logada),
    supabase: Client = Depends(get_supabase_client),
) -> RelatoRegistrado:
    """As quatro respostas viram a Demanda Registrada e o resumo."""
    try:
        demanda, resumo = relato_de_bug.registrar(
            supabase, pessoa=pessoa, respostas=relato_de_bug.Respostas(**payload.model_dump())
        )
    except relato_de_bug.RelatoRecusadoError as recusa:
        raise _recusa(recusa) from recusa
    return RelatoRegistrado(demanda_id=str(demanda["id"]), resumo=ResumoDoBug(**resumo))


@router.post("/bug/{demanda_id}/print", response_model=PrintsDoRelato)
@limiter.limit(LIMITE_DA_CONVERSA)
async def anexar_o_print(
    request: Request,
    demanda_id: str,
    imagem: UploadFile = File(...),
    pessoa: dict = Depends(pessoa_logada),
    supabase: Client = Depends(get_supabase_client),
) -> PrintsDoRelato:
    """O print vira Anexo da Demanda, e nunca vai ao GitHub."""
    conteudo = await imagem.read()
    try:
        prints = relato_de_bug.anexar_print(
            supabase, demanda_id=demanda_id, pessoa=pessoa, nome=imagem.filename or "", conteudo=conteudo
        )
    except relato_de_bug.RelatoRecusadoError as recusa:
        raise _recusa(recusa) from recusa
    return PrintsDoRelato(prints=prints)


@router.post("/bug/{demanda_id}/enviar", response_model=RelatoEnviado)
@limiter.limit(LIMITE_DA_CONVERSA)
def enviar_o_bug(
    request: Request,
    demanda_id: str,
    pessoa: dict = Depends(pessoa_logada),
    supabase: Client = Depends(get_supabase_client),
) -> RelatoEnviado:
    """O clique de envio: cria a issue. A falha sai com o motivo, e só outro
    clique tenta de novo."""
    try:
        demanda = relato_de_bug.enviar(supabase, demanda_id=demanda_id, pessoa=pessoa)
    except relato_de_bug.RelatoRecusadoError as recusa:
        raise _recusa(recusa) from recusa
    return RelatoEnviado(demanda_id=str(demanda["id"]))
