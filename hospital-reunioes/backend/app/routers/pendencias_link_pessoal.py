"""A página do link pessoal das Pendências (issue #1878; ADR 0098, decisão 8).

Rotas públicas, sem login: quem chega aqui veio pelo link do e-mail de
segunda, que só sai para quem nunca entrou no app. O token alcança só as
Pendências abertas em que a pessoa dona dele é responsável ou co-responsável
(sem o lembrete do Núcleo e sem as Reuniões do Núcleo que ela não alcança), e
só os quatro comandos do responsável: iniciar, anotar, concluir e repactuar.
Toda ação passa pelo mesmo módulo de ações da tela (`pendencia_acao.agir`):
anotação obrigatória e um evento no histórico, em nome da pessoa.
"""

from __future__ import annotations

import datetime as dt
import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

from app.dependencies import _PARTICIPANTE_FULL_FIELDS, foi_desligado, get_supabase_client, reunioes_ocultas
from app.limiter import limiter
from app.services import link_pessoal
from app.services.pendencia_acao import agir
from app.services.pendencia_ciclo import ABERTOS, AcaoRecusada, Comando, Papel, acoes_disponiveis, situacao
from app.services.pendencias_consulta import as_data, hoje_em_brasilia, ids_repactuados

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/minhas-pendencias", tags=["minhas-pendencias"])

LINK_INVALIDO = "Este link não existe. Confira se ele foi copiado inteiro do e-mail."
LINK_VENCIDO = (
    "Este link venceu. O e-mail de segunda traz um link novo toda semana; "
    "se precisar antes, entre no aplicativo com o seu e-mail."
)
LINK_REVOGADO = "Este link foi cancelado e não vale mais. Se precisar, fale com quem conduz a sua reunião."

# Só o que o responsável faz na própria Pendência (Refino 20 do PRD #1757).
_DO_LINK = (Comando.INICIAR, Comando.ANOTAR, Comando.CONCLUIR, Comando.REPACTUAR)
_HTTP_DA_RECUSA = {"permissao": 403, "transicao": 409, "dados": 422}
_CAMPOS = "id_acao, id_reuniao, descricao_acao, responsavel_id, co_responsavel_id, status, prazo, deleted_at"


def agora_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class AcaoPeloLink(BaseModel):
    comando: Literal["iniciar", "anotar", "concluir", "repactuar"]
    anotacao: str = Field("", max_length=5000)
    prazo: date | None = None


def _dono(supabase, token: str) -> dict:
    """A pessoa dona do token, ou a recusa com a frase de cada caso."""
    try:
        vinculo = link_pessoal.carregar(supabase, token, agora_utc())
    except link_pessoal.LinkInvalidoError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=LINK_INVALIDO) from None
    except link_pessoal.LinkVencidoError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=LINK_VENCIDO) from None
    except link_pessoal.LinkRevogadoError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=LINK_REVOGADO) from None
    pessoas = (
        supabase.table("participantes")
        .select(_PARTICIPANTE_FULL_FIELDS)
        .eq("id", vinculo["participante_id"])
        .limit(1)
        .execute()
        .data
    )
    if not pessoas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=LINK_INVALIDO)
    if foi_desligado(pessoas[0]):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=LINK_REVOGADO)
    return pessoas[0]


def _papeis(pendencia: dict, pid: str) -> set[Papel]:
    papeis: set[Papel] = set()
    if pendencia.get("responsavel_id") == pid:
        papeis.add(Papel.RESPONSAVEL)
    if pendencia.get("co_responsavel_id") == pid:
        papeis.add(Papel.CO_RESPONSAVEL)
    return papeis


def _alcanca(pendencia: dict, pessoa: dict, ocultas: set[str]) -> bool:
    """Aberta, de Reunião (o lembrete do Núcleo não entra), fora das Reuniões
    do Núcleo que a pessoa não alcança, e dela."""
    return (
        pendencia.get("deleted_at") is None
        and pendencia.get("status") in ABERTOS
        and pendencia.get("id_reuniao") is not None
        and pendencia["id_reuniao"] not in ocultas
        and bool(_papeis(pendencia, pessoa["id"]))
    )


def _as_minhas(supabase, pessoa: dict) -> dict:
    pid = pessoa["id"]
    ocultas = set(reunioes_ocultas(supabase, pessoa))
    linhas: dict[str, dict] = {}
    for coluna in ("responsavel_id", "co_responsavel_id"):
        for p in (
            supabase.table("pendencias")
            .select(_CAMPOS)
            .eq(coluna, pid)
            .in_("status", list(ABERTOS))
            .is_("deleted_at", "null")
            .execute()
            .data
            or []
        ):
            if _alcanca(p, pessoa, ocultas):
                linhas[p["id_acao"]] = p

    ids_reunioes = sorted({p["id_reuniao"] for p in linhas.values()})
    titulos = {
        r["id_reuniao"]: r.get("titulo") or ""
        for r in (
            supabase.table("reunioes").select("id_reuniao, titulo").in_("id_reuniao", ids_reunioes).execute().data
            if ids_reunioes
            else []
        )
    }
    repactuadas = ids_repactuados(supabase, list(linhas))
    hoje = hoje_em_brasilia()
    itens = []
    for p in linhas.values():
        prazo = as_data(p.get("prazo"))
        acoes = acoes_disponiveis(_papeis(p, pid), p["status"])
        itens.append(
            {
                "id_acao": p["id_acao"],
                "descricao": p.get("descricao_acao") or "",
                "reuniao": titulos.get(p["id_reuniao"], ""),
                "prazo": prazo.isoformat() if prazo else None,
                "situacao": situacao(p["status"], prazo, hoje, repactuada=p["id_acao"] in repactuadas),
                "acoes": [c.value for c in acoes if c in _DO_LINK],
            }
        )
    itens.sort(key=lambda i: (i["prazo"] is None, i["prazo"] or "", i["descricao"]))
    return {"pessoa": pessoa.get("nome_completo") or "", "pendencias": itens}


@router.get("/{token}")
@limiter.limit("30/minute")
async def abrir(request: Request, token: str, supabase=Depends(get_supabase_client)):
    """As Pendências abertas da pessoa dona do link."""
    return _as_minhas(supabase, _dono(supabase, token))


@router.post("/{token}/pendencias/{id_acao}/acoes")
@limiter.limit("20/minute")
async def agir_pelo_link(
    request: Request,
    token: str,
    id_acao: str,
    body: AcaoPeloLink,
    supabase=Depends(get_supabase_client),
):
    """Iniciar, anotar, concluir ou repactuar, sempre com anotação. Devolve a
    lista atualizada."""
    pessoa = _dono(supabase, token)
    linhas = (
        supabase.table("pendencias").select(_CAMPOS).eq("id_acao", id_acao).is_("deleted_at", "null").execute().data
    )
    ocultas = set(reunioes_ocultas(supabase, pessoa))
    # Pendência de outra pessoa, fechada ou do Núcleo fora do alcance: 404,
    # sem dizer se ela existe.
    if not linhas or not _alcanca(linhas[0], pessoa, ocultas):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pendência não encontrada")
    pendencia = linhas[0]
    try:
        agir(
            supabase,
            pendencia,
            Comando(body.comando),
            _papeis(pendencia, pessoa["id"]),
            anotacao=body.anotacao.strip(),
            autor_id=pessoa["id"],
            autor_nome=pessoa.get("nome_completo") or "Sem nome",
            hoje=hoje_em_brasilia(),
            prazo_novo=body.prazo,
        )
    except AcaoRecusada as recusa:
        raise HTTPException(status_code=_HTTP_DA_RECUSA[recusa.tipo], detail=recusa.motivo) from recusa
    except APIError as erro:
        if erro.code == "PT409":
            raise HTTPException(status_code=409, detail=erro.message) from erro
        if erro.code == "PT404":
            raise HTTPException(status_code=404, detail="Pendência não encontrada") from erro
        raise
    logger.info("[Link pessoal] %s: %s por %s", id_acao, body.comando, pessoa["id"])
    return _as_minhas(supabase, pessoa)
