"""Segurança do Paciente (PRD #1764, ADR 0095): o módulo do Núcleo.

Esta é a fundação (issue #1765): a permissão efetiva e as duas rotas que a
primeira tela usa. As áreas seguintes (membros, documentos, reuniões,
capacitações, agenda) chegam cada uma no seu router, todas sob `/nsp` e todas
atrás de `require_recurso_nsp`.
"""

from fastapi import APIRouter, Depends, Request
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.limiter import limiter
from app.services.seguranca_do_paciente.permissao import (
    SLUG_DO_NUCLEO,
    hoje_em_sao_paulo,
    participacoes_vigentes,
)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])


def _nucleo(supabase) -> dict | None:
    linhas = (
        supabase.table("colegiados").select("id, slug, nome, setor_id").eq("slug", SLUG_DO_NUCLEO).limit(1).execute()
    ).data or []
    return linhas[0] if linhas else None


@router.get("/inicio")
@limiter.limit("60/minute")
async def pagina_inicial(
    request: Request,
    me: dict = Depends(require_recurso_nsp("ver_modulo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A página inicial do módulo: o Núcleo, quantos membros estão com a
    vigência em dia e o que a pessoa alcança. Nenhum nome de pessoa."""
    nucleo = _nucleo(supabase)
    vigentes = (
        (participacoes_vigentes(supabase, nucleo["id"], hoje_em_sao_paulo()).execute().data or []) if nucleo else []
    )
    return {
        "nucleo": nucleo["nome"] if nucleo else None,
        "membros_vigentes": len({linha["participante_id"] for linha in vigentes}),
        "recursos": me["recursos_nsp"],
    }


@router.get("/configuracao")
@limiter.limit("60/minute")
async def configuracao_tecnica(
    request: Request,
    _: dict = Depends(require_recurso_nsp("configuracao")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A configuração técnica do módulo, a única parte que o super admin
    alcança (ADR 0095, decisão 4): o registro do Núcleo como Colegiado."""
    return {"colegiado": _nucleo(supabase)}
