"""Segurança do Paciente (PRD #1764, ADR 0095): o módulo do Núcleo.

Esta é a fundação (issue #1765): a permissão efetiva e as duas rotas que a
primeira tela usa. As áreas seguintes (membros, documentos, reuniões,
capacitações, agenda) chegam cada uma no seu router, todas sob `/nsp` e todas
atrás de `require_recurso_nsp`.
"""

from fastapi import APIRouter, Depends, Request, Response
from supabase import Client

from app.config import settings
from app.dependencies import get_supabase_client, require_recurso_nsp
from app.limiter import limiter
from app.services import ouvidoria_pontos
from app.services.seguranca_do_paciente import caso_grave
from app.services.seguranca_do_paciente.permissao import (
    SLUG_DO_NUCLEO,
    hoje_em_sao_paulo,
    participacoes_vigentes,
)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])

# As duas portas sem login da notificação (issue #1987): o QR grava a origem
# QR, o endereço grava a origem endereço. São páginas do app, sem `/api`.
CAMINHO_DO_QR_DA_NOTIFICACAO = "/notificar/qr"
CAMINHO_DO_ENDERECO_DA_NOTIFICACAO = "/notificar"


def _no_app(caminho: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{caminho}"


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
    vigência em dia, o que a pessoa alcança e, para quem abre os casos, os
    casos graves que esperam a triagem (issue #1989). Nenhum nome de pessoa."""
    nucleo = _nucleo(supabase)
    vigentes = (
        (participacoes_vigentes(supabase, nucleo["id"], hoje_em_sao_paulo()).execute().data or []) if nucleo else []
    )
    return {
        "nucleo": nucleo["nome"] if nucleo else None,
        "membros_vigentes": len({linha["participante_id"] for linha in vigentes}),
        "recursos": me["recursos_nsp"],
        "casos_graves": caso_grave.casos_graves_em_espera(supabase) if "casos" in me["recursos_nsp"] else [],
    }


@router.get("/configuracao")
@limiter.limit("60/minute")
async def configuracao_tecnica(
    request: Request,
    _: dict = Depends(require_recurso_nsp("configuracao")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A configuração técnica do módulo, a única parte que o super admin
    alcança (ADR 0095, decisão 4): o registro do Núcleo como Colegiado e o
    endereço completo da notificação, para a TI criar o ícone nos computadores
    (issue #2046)."""
    return {
        "colegiado": _nucleo(supabase),
        "endereco_da_notificacao": _no_app(CAMINHO_DO_ENDERECO_DA_NOTIFICACAO),
    }


@router.get("/configuracao/qr-da-notificacao.png")
@limiter.limit("60/minute")
async def baixar_qr_da_notificacao(
    request: Request,
    _: dict = Depends(require_recurso_nsp("configuracao")),
) -> Response:
    """O QR único da notificação (issue #2046), para o cartaz e o papel de
    parede. Aponta para `/notificar/qr`, a porta que grava a origem QR."""
    return Response(
        content=ouvidoria_pontos.png_de_url(_no_app(CAMINHO_DO_QR_DA_NOTIFICACAO)),
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="qr-notificacao-nsp.png"'},
    )
