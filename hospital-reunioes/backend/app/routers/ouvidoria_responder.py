"""A porta do login da Tela do responsável (issue #1886, ADR 0099, decisões 4 a 6).

O Responsável do setor que entra no app com a própria senha abre o caso pelo id
da manifestação e responde, pede prorrogação ou devolve à Ouvidoria pelo MESMO
serviço da porta do token (`ouvidoria_tela_do_responsavel`), com as mesmas
guardas e as mesmas frases. Muda só quem resolve o caso e o ator:

- o caso tem de estar acionado para um setor em que quem está logado é titular,
  substituto ou gestor vigente. Fora disso, 403, inclusive para o caso do setor
  que ainda não saiu da classificação ou que o ouvidor redirecionou;
- o ator é o nome do login, e a porta que vai para a trilha é `app`;
- o uso único é dos links vivos do caso: responder e devolver pelo app os
  consomem, e o link aberto depois diz que já foi usado. O pedido de prazo não
  gasta nada, como no link.
"""

from __future__ import annotations

import datetime as dt
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.dependencies import barrar_desligado, get_current_user, get_participante_for_user, get_supabase_client
from app.limiter import limiter
from app.routers.ouvidoria_setor import DevolucaoAOuvidoria, PedidoDeProrrogacao
from app.services import ouvidoria_papel, ouvidoria_porta, ouvidoria_setor_tokens, ouvidoria_tela_do_responsavel
from app.services.ouvidoria_prazos import FUSO as FUSO_HOSPITAL
from app.services.ouvidoria_tela_do_responsavel import FALHAS_DO_POSTGREST, indisponivel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ouvidoria/responder", tags=["ouvidoria-responder"])

# A leitura da tela mais o carimbo da validação: é ele que prova que o caso foi
# acionado para o setor, como na fila do responsável.
_CAMPOS = ouvidoria_tela_do_responsavel.CAMPOS_DO_CASO + ", validada_em"

FORA_DO_SETOR = "Este caso não está com um setor pelo qual você responde"


def agora_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def _caso_e_ator(
    supabase, current_user: dict, manifestacao_id: str, agora: dt.datetime
) -> tuple[dict, ouvidoria_tela_do_responsavel.Ator]:
    """O caso do setor de quem está logado, e o ator dele. Recusa com 403 tudo
    o que não é caso acionado para um setor em que a pessoa está vigente, sem
    dizer se o caso existe."""
    from app.routers.ouvidoria import ESTADOS_ACIONADOS

    me = await get_participante_for_user(current_user, supabase)
    barrar_desligado(me)
    if not me:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORA_DO_SETOR)
    try:
        setores = ouvidoria_papel.setores_de(supabase, me, agora.astimezone(FUSO_HOSPITAL).date())
        lidos = (
            supabase.table("ouvidoria_protocolos").select(_CAMPOS).eq("id", manifestacao_id).limit(1).execute().data
            if setores
            else []
        )
    except FALHAS_DO_POSTGREST as exc:
        logger.error("Falha ao ler o caso %s pela porta do login", manifestacao_id)
        raise indisponivel() from exc
    caso = lidos[0] if lidos else None
    if (
        caso is None
        or caso.get("setor") not in setores
        or caso.get("status") not in ESTADOS_ACIONADOS
        or not caso.get("validada_em")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORA_DO_SETOR)
    ator = ouvidoria_tela_do_responsavel.Ator(
        nome=me.get("nome_completo") or me.get("email") or "Responsável do setor",
        email=me.get("email"),
        porta=ouvidoria_porta.APP,
    )
    return caso, ator


class _TravaDoLogin:
    """O uso único pela porta do login: os links vivos do caso, carimbados com
    o instante deste request e soltos só por ele."""

    def __init__(self, supabase, manifestacao_id: str, agora: dt.datetime):
        self._supabase = supabase
        self._manifestacao_id = manifestacao_id
        self._agora = agora

    def consumir(self) -> bool:
        return ouvidoria_setor_tokens.consumir_os_vivos(self._supabase, self._manifestacao_id, self._agora)

    def devolver(self) -> None:
        try:
            ouvidoria_setor_tokens.devolver_os_do_carimbo(
                self._supabase, self._manifestacao_id, self._agora.isoformat()
            )
        except FALHAS_DO_POSTGREST:
            logger.error("Falha ao devolver os links da manifestação %s pela porta do login", self._manifestacao_id)


@router.get("/{manifestacao_id}")
@limiter.limit("30/minute")
async def abrir(
    request: Request,
    manifestacao_id: str,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """A Tela do responsável aberta pelo app, com o mesmo conteúdo do link."""
    agora = agora_utc()
    caso, ator = await _caso_e_ator(supabase, current_user, manifestacao_id, agora)
    return await ouvidoria_tela_do_responsavel.abrir(supabase, caso=caso, ator=ator, agora=agora)


@router.post("/{manifestacao_id}/responder")
@limiter.limit("10/minute")
async def responder(
    request: Request,
    manifestacao_id: str,
    resposta: str = Form(...),
    arquivos: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """A resposta da área pelo app. Consome os links vivos do caso."""
    agora = agora_utc()
    caso, ator = await _caso_e_ator(supabase, current_user, manifestacao_id, agora)
    return await ouvidoria_tela_do_responsavel.responder(
        supabase,
        caso=caso,
        ator=ator,
        trava=_TravaDoLogin(supabase, caso["id"], agora),
        agora=agora,
        resposta=resposta,
        arquivos=arquivos,
    )


@router.post("/{manifestacao_id}/devolver")
@limiter.limit("10/minute")
async def devolver_a_ouvidoria(
    request: Request,
    manifestacao_id: str,
    devolucao: DevolucaoAOuvidoria,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """A Devolução à Ouvidoria pelo app. Consome os links vivos do caso."""
    agora = agora_utc()
    caso, ator = await _caso_e_ator(supabase, current_user, manifestacao_id, agora)
    return await ouvidoria_tela_do_responsavel.devolver_a_ouvidoria(
        supabase,
        caso=caso,
        ator=ator,
        trava=_TravaDoLogin(supabase, caso["id"], agora),
        agora=agora,
        motivo=devolucao.motivo,
    )


@router.post("/{manifestacao_id}/prorrogacao", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def pedir_prorrogacao(
    request: Request,
    manifestacao_id: str,
    pedido: PedidoDeProrrogacao,
    current_user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """O pedido de mais prazo pelo app. Como no link, não gasta o uso único:
    quem pede prazo ainda precisa responder depois."""
    justificativa = ouvidoria_tela_do_responsavel.justificativa_valida(pedido.justificativa)
    agora = agora_utc()
    caso, ator = await _caso_e_ator(supabase, current_user, manifestacao_id, agora)
    return await ouvidoria_tela_do_responsavel.pedir_prorrogacao(
        supabase,
        caso=caso,
        ator=ator,
        agora=agora,
        justificativa=justificativa,
        dias_uteis=pedido.dias_uteis,
    )
