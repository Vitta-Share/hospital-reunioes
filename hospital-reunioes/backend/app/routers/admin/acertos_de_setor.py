"""Router /admin/acertos-de-setor: quem ficou sem setor, e o Super admin acerta.

Desde a issue #1861 toda Reunião nova nasce com setor, mas as antigas e boa
parte dos responsáveis (Colaboradores) não têm, e no gráfico por setor do painel
isso vira a barra "Sem setor" (decisões 11 e 62 do PRD #1757). Esta tela lista
os dois grupos e deixa o Super admin preencher cada um; preenchido, sai da lista.

A resposta é um objeto com uma lista por grupo.

- Reuniões: vivas, sem `setor_id` e fora do Núcleo. A reunião do Núcleo é
  sigilosa até para o Super admin (issue #1772), então não aparece nem se
  acerta por aqui.
- Responsáveis: Colaboradores internos sem `setor_id` que respondem por alguma
  pendência, porque é o setor do responsável que o gráfico de atrasos usa
  (decisão 62). O externo é só um nome e não tem setor a acertar.
- Pendências sem prazo (issue #1877): abertas, vivas e sem prazo, de Reunião
  viva e fora do Núcleo. O fluxo contínuo que casou com o quadro da Ata virou
  Rotina (migration 190) e foi encerrado; o que sobra aqui não casou e espera
  um prazo, que se dá na própria Pendência. Só leitura nesta tela.

Preencher grava `setor_id` e a TEXT `setor` juntos, em sincronia (migrations
028 e 168), e grava no `audit_log`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client, require_super_admin
from app.services import audit
from app.services.setor_ativo import setor_ativo

router = APIRouter(
    prefix="/admin/acertos-de-setor",
    tags=["admin", "acertos-de-setor"],
    dependencies=[Depends(require_super_admin)],
)

_DETALHE_SETOR_INVALIDO = "Escolha um setor da lista de setores ativos."


class PreencherSetorRequest(BaseModel):
    setor: str = Field(..., max_length=255)


def _setor_ou_422(supabase: Client, nome: str) -> dict:
    setor = setor_ativo(supabase, nome)
    if setor is None:
        raise HTTPException(status_code=422, detail=_DETALHE_SETOR_INVALIDO)
    return setor


@router.get("")
async def listar_sem_setor(supabase: Client = Depends(get_supabase_client)):
    reunioes = (
        supabase.table("reunioes")
        .select("id_reuniao, titulo, data, tipo")
        .is_("setor_id", "null")
        .is_("deleted_at", "null")
        .is_("colegiado_id", "null")
        .order("data", desc=True)
        .execute()
        .data
        or []
    )

    sem_setor = (
        supabase.table("participantes")
        .select("id, nome_completo, cargo, email")
        .is_("setor_id", "null")
        .eq("is_externo", False)
        .order("nome_completo")
        .execute()
        .data
        or []
    )
    responsaveis: list[dict] = []
    if sem_setor:
        com_pendencia = {
            p["responsavel_id"]
            for p in (
                supabase.table("pendencias")
                .select("responsavel_id")
                .in_("responsavel_id", [p["id"] for p in sem_setor])
                .execute()
                .data
                or []
            )
        }
        responsaveis = [p for p in sem_setor if p["id"] in com_pendencia]

    return {
        "reunioes": reunioes,
        "responsaveis": responsaveis,
        "pendencias_sem_prazo": _pendencias_sem_prazo(supabase),
    }


def _pendencias_sem_prazo(supabase: Client) -> list[dict]:
    abertas = (
        supabase.table("pendencias")
        .select("id_acao, id_reuniao, descricao_acao, responsavel_nome, status")
        .in_("status", ["PENDENTE", "EM_PROGRESSO"])
        .is_("prazo", "null")
        .is_("deleted_at", "null")
        .not_.is_("id_reuniao", "null")
        .order("id_acao")
        .execute()
        .data
        or []
    )
    if not abertas:
        return []
    visiveis = {
        r["id_reuniao"]: r
        for r in (
            supabase.table("reunioes")
            .select("id_reuniao, titulo")
            .in_("id_reuniao", sorted({p["id_reuniao"] for p in abertas}))
            .is_("deleted_at", "null")
            .is_("colegiado_id", "null")
            .execute()
            .data
            or []
        )
    }
    return [
        {**p, "reuniao_titulo": visiveis[p["id_reuniao"]].get("titulo")} for p in abertas if p["id_reuniao"] in visiveis
    ]


@router.patch("/reunioes/{id_reuniao}")
async def preencher_setor_da_reuniao(
    id_reuniao: str,
    req: PreencherSetorRequest,
    request: Request,
    actor: dict = Depends(require_super_admin),
    supabase: Client = Depends(get_supabase_client),
):
    achada = (
        supabase.table("reunioes")
        .select("id_reuniao")
        .eq("id_reuniao", id_reuniao)
        .is_("deleted_at", "null")
        .is_("colegiado_id", "null")
        .limit(1)
        .execute()
        .data
    )
    if not achada:
        raise HTTPException(status_code=404, detail="Reunião não encontrada")
    setor = _setor_ou_422(supabase, req.setor)

    supabase.table("reunioes").update({"setor_id": setor["id"], "setor": setor["nome"]}).eq(
        "id_reuniao", id_reuniao
    ).execute()
    audit.log_action(
        supabase,
        actor=actor,
        action="reuniao_setor_preenchido",
        target_type="reuniao",
        target_id=id_reuniao,
        metadata={"setor": setor["nome"]},
        request=request,
    )
    return {"id_reuniao": id_reuniao, "setor": setor["nome"]}


@router.patch("/responsaveis/{participante_id}")
async def preencher_setor_do_responsavel(
    participante_id: str,
    req: PreencherSetorRequest,
    request: Request,
    actor: dict = Depends(require_super_admin),
    supabase: Client = Depends(get_supabase_client),
):
    achado = supabase.table("participantes").select("id").eq("id", participante_id).limit(1).execute().data
    if not achado:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    setor = _setor_ou_422(supabase, req.setor)

    supabase.table("participantes").update({"setor_id": setor["id"], "setor": setor["nome"]}).eq(
        "id", participante_id
    ).execute()
    audit.log_action(
        supabase,
        actor=actor,
        action="participante_setor_preenchido",
        target_type="participante",
        target_id=participante_id,
        metadata={"setor": setor["nome"]},
        request=request,
    )
    return {"id": participante_id, "setor": setor["nome"]}
