"""Segurança do Paciente: as Capacitações do Núcleo (issue #1778, PRD #1764).

Ler é do recurso `capacitacoes` (membro com Termo, Presidência e Acesso pleno);
cadastrar a capacitação e editar a lista de temas mínimos são da Presidência,
pelo recurso `gerir_nucleo`. O super admin sem papel no Núcleo não alcança
nenhuma das duas (ADR 0095, decisão 4).

Confirmar a presença é da própria pessoa, e de mais ninguém: a rota não recebe
de quem é a presença, ela vale para quem está logado, e só se essa pessoa está
na lista da capacitação. Quem não está na lista (a Presidência inclusive)
recebe a mesma recusa do módulo.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import (
    RECUSA_DO_NSP,
    barrar_desligado,
    get_current_user,
    get_participante_for_user,
    get_supabase_client,
    require_recurso_nsp,
)
from app.limiter import limiter
from app.services.seguranca_do_paciente import capacitacoes
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo

router = APIRouter(prefix="/nsp/capacitacoes", tags=["seguranca-do-paciente"])

Publico = Literal["membros", "profissionais"]


class CapacitacaoNova(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    data: date
    carga_horaria: float = Field(gt=0, le=999)
    instrutor: str = Field(min_length=1, max_length=200)
    publico: Publico
    tema_ids: list[str] = Field(default_factory=list, max_length=100)
    participantes: list[str] = Field(min_length=1, max_length=500)


class TemaNovo(BaseModel):
    nome: str = Field(min_length=1, max_length=200)


class TemaEditado(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=200)
    ativo: bool | None = None


def _limpo(texto: str | None) -> str:
    return (texto or "").strip()


def _sem_branco(texto: str, mensagem: str) -> str:
    limpo = _limpo(texto)
    if not limpo:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=mensagem)
    return limpo


@router.get("")
@limiter.limit("60/minute")
async def listar_capacitacoes(
    request: Request,
    me: dict = Depends(require_recurso_nsp("capacitacoes")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    return {
        **capacitacoes.listar(supabase, hoje_em_sao_paulo()),
        "pode_editar": "gerir_nucleo" in me["recursos_nsp"],
        "eu": me.get("id"),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def cadastrar_capacitacao(
    request: Request,
    corpo: CapacitacaoNova,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    titulo = _sem_branco(corpo.titulo, "Diga o título da capacitação.")
    instrutor = _sem_branco(corpo.instrutor, "Diga quem deu a capacitação.")
    tema_ids = list(dict.fromkeys(corpo.tema_ids))
    participantes = list(dict.fromkeys(p.strip() for p in corpo.participantes if p.strip()))
    if not participantes:
        raise HTTPException(status_code=422, detail="Inclua pelo menos um participante.")
    ativos = {t["id"] for t in capacitacoes.temas(supabase) if t.get("ativo")}
    if any(t not in ativos for t in tema_ids):
        raise HTTPException(status_code=422, detail="Escolha os temas na lista de temas mínimos.")
    encontrados = (
        supabase.table("participantes").select("id").in_("id", participantes).eq("ativo", True).execute().data
    ) or []
    if {linha["id"] for linha in encontrados} != set(participantes):
        raise HTTPException(status_code=422, detail="Algum participante não está no cadastro de pessoas.")
    nova = (
        supabase.table(capacitacoes.TABELA)
        .insert(
            {
                "titulo": titulo,
                "data": corpo.data.isoformat(),
                "carga_horaria": corpo.carga_horaria,
                "instrutor": instrutor,
                "publico": corpo.publico,
                "tema_ids": tema_ids,
                "criado_por": me.get("id"),
            }
        )
        .execute()
        .data
    )[0]
    supabase.table(capacitacoes.TABELA_PARTICIPANTES).insert(
        [{"capacitacao_id": nova["id"], "participante_id": pid} for pid in participantes]
    ).execute()
    return nova


@router.post("/temas", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def incluir_tema(
    request: Request,
    corpo: TemaNovo,
    _: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    nome = _sem_branco(corpo.nome, "Diga o nome do tema.")
    _nome_livre(supabase, nome)
    return (supabase.table(capacitacoes.TABELA_TEMAS).insert({"nome": nome, "ativo": True}).execute().data)[0]


def _nome_livre(supabase, nome: str, exceto: str | None = None) -> None:
    for tema in capacitacoes.temas(supabase):
        if tema["id"] != exceto and _limpo(tema.get("nome")).lower() == nome.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esse tema já está na lista.")


@router.patch("/temas/{tema_id}")
@limiter.limit("30/minute")
async def editar_tema(
    request: Request,
    tema_id: str,
    corpo: TemaEditado,
    _: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    campos = corpo.model_dump(exclude_unset=True)
    if any(valor is None for valor in campos.values()):
        raise HTTPException(status_code=422, detail="Esse campo não pode ficar em branco.")
    existe = supabase.table(capacitacoes.TABELA_TEMAS).select("id").eq("id", tema_id).limit(1).execute().data
    if not existe:
        raise HTTPException(status_code=404, detail="Tema não encontrado")
    if "nome" in campos:
        campos["nome"] = _sem_branco(campos["nome"], "Diga o nome do tema.")
        _nome_livre(supabase, campos["nome"], exceto=tema_id)
    if not campos:
        return existe[0]
    campos["updated_at"] = datetime.now().astimezone().isoformat()
    return supabase.table(capacitacoes.TABELA_TEMAS).update(campos).eq("id", tema_id).execute().data[0]


@router.post("/{capacitacao_id}/presenca")
@limiter.limit("30/minute")
async def confirmar_minha_presenca(
    request: Request,
    capacitacao_id: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    me = await get_participante_for_user(current_user, supabase)
    barrar_desligado(me)
    if not me:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=RECUSA_DO_NSP)
    linhas = (
        supabase.table(capacitacoes.TABELA_PARTICIPANTES)
        .select("id, presenca_confirmada_em")
        .eq("capacitacao_id", capacitacao_id)
        .eq("participante_id", me["id"])
        .limit(1)
        .execute()
        .data
    ) or []
    if not linhas:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=RECUSA_DO_NSP)
    linha = linhas[0]
    if not linha.get("presenca_confirmada_em"):
        agora = datetime.now().astimezone().isoformat()
        supabase.table(capacitacoes.TABELA_PARTICIPANTES).update({"presenca_confirmada_em": agora}).eq(
            "id", linha["id"]
        ).is_("presenca_confirmada_em", "null").execute()
        linha = {**linha, "presenca_confirmada_em": agora}
    return {"capacitacao_id": capacitacao_id, "presenca_confirmada_em": linha["presenca_confirmada_em"]}
