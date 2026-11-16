"""Segurança do Paciente: a Agenda regulatória do Núcleo (issue #1779, PRD #1764).

Ler é do recurso `agenda` (inclusive quem ainda não assinou o Termo e a
Diretoria); incluir, editar, desativar e registrar o resultado são da
Presidência, pelo recurso `gerir_nucleo`. O super admin sem papel no Núcleo
não alcança nenhuma das duas (ADR 0095, decisão 4).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.limiter import limiter
from app.services.seguranca_do_paciente import agenda
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo

router = APIRouter(prefix="/nsp/agenda", tags=["seguranca-do-paciente"])

Periodicidade = Literal["mensal", "anual", "bienal", "avulsa"]
_LINK = r"^https?://\S+$"


class EventoNovo(BaseModel):
    evento: str = Field(min_length=1, max_length=200)
    periodicidade: Periodicidade
    regra: str | None = Field(None, max_length=200)
    proxima_data: date | None = None
    link: str | None = Field(None, max_length=500, pattern=_LINK)
    antecedencia_dias: int = Field(7, ge=0, le=agenda.ANTECEDENCIA_MAXIMA)


class EventoEditado(BaseModel):
    evento: str | None = Field(None, min_length=1, max_length=200)
    periodicidade: Periodicidade | None = None
    regra: str | None = Field(None, max_length=200)
    proxima_data: date | None = None
    link: str | None = Field(None, max_length=500, pattern=_LINK)
    antecedencia_dias: int | None = Field(None, ge=0, le=agenda.ANTECEDENCIA_MAXIMA)
    ativo: bool | None = None


class Resultado(BaseModel):
    resultado: str = Field(min_length=1, max_length=2000)
    realizada_em: date | None = None


def _gravavel(campos: dict) -> dict:
    return {chave: valor.isoformat() if isinstance(valor, date) else valor for chave, valor in campos.items()}


def _limpo(texto: str | None) -> str | None:
    return (texto or "").strip() or None


@router.get("")
@limiter.limit("60/minute")
async def listar_agenda(
    request: Request,
    me: dict = Depends(require_recurso_nsp("agenda")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    return {"itens": agenda.listar(supabase), "pode_editar": "gerir_nucleo" in me["recursos_nsp"]}


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def incluir_evento(
    request: Request,
    corpo: EventoNovo,
    _: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    evento = _limpo(corpo.evento)
    if not evento:
        raise HTTPException(status_code=422, detail="Diga qual é o evento.")
    linha = _gravavel({**corpo.model_dump(), "evento": evento, "regra": _limpo(corpo.regra), "ativo": True})
    return (supabase.table(agenda.TABELA).insert(linha).execute().data or [linha])[0]


@router.patch("/{item_id}")
@limiter.limit("30/minute")
async def editar_evento(
    request: Request,
    item_id: str,
    corpo: EventoEditado,
    _: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    campos = corpo.model_dump(exclude_unset=True)
    for nulo_proibido in ("evento", "periodicidade", "antecedencia_dias", "ativo"):
        if nulo_proibido in campos and campos[nulo_proibido] is None:
            raise HTTPException(status_code=422, detail="Esse campo não pode ficar em branco.")
    if "evento" in campos:
        campos["evento"] = _limpo(campos["evento"])
        if not campos["evento"]:
            raise HTTPException(status_code=422, detail="Diga qual é o evento.")
    if "regra" in campos:
        campos["regra"] = _limpo(campos["regra"])
    existe = supabase.table(agenda.TABELA).select("id, proxima_data").eq("id", item_id).limit(1).execute().data
    if not existe:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    if not campos:
        return existe[0]
    campos["updated_at"] = datetime.now().astimezone()
    gravavel = _gravavel(campos)
    atualizado = supabase.table(agenda.TABELA).update(gravavel).eq("id", item_id).execute().data[0]
    # A data mudou antes do resultado: o lembrete da data antiga se encerra,
    # senão vira ATRASADO e nada o fecha.
    data_antiga = existe[0].get("proxima_data")
    if "proxima_data" in gravavel and data_antiga and str(data_antiga)[:10] != gravavel["proxima_data"]:
        agenda.encerrar_lembrete(supabase, item_id, data_antiga)
    return atualizado


@router.post("/{item_id}/resultado")
@limiter.limit("30/minute")
async def registrar_resultado(
    request: Request,
    item_id: str,
    corpo: Resultado,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    resultado = _limpo(corpo.resultado)
    if not resultado:
        raise HTTPException(status_code=422, detail="Escreva o resultado.")
    try:
        return agenda.registrar_resultado(
            supabase,
            item_id,
            resultado=resultado,
            realizada_em=corpo.realizada_em or hoje_em_sao_paulo(),
            autor_id=me.get("id"),
            agora=datetime.now().astimezone(),
        )
    except agenda.EventoNaoEncontradoError:
        raise HTTPException(status_code=404, detail="Evento não encontrado") from None
    except agenda.SemProximaDataError:
        raise HTTPException(
            status_code=409, detail="Marque a próxima data do evento antes de registrar o resultado."
        ) from None
