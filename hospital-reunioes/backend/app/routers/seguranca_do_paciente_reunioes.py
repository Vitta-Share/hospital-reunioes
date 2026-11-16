"""As reuniões do Núcleo, no módulo Segurança do Paciente (issue #1772).

O item Reuniões do módulo: o calendário e a lista das reuniões do Núcleo, e a
criação à mão pela Presidência, num dos quatro tipos do Núcleo. A reunião nasce
na mesma tabela das outras, com `colegiado_id` do Núcleo, e daí em diante segue
o caminho de sempre (transcrição, ata, assinatura) pela tela da reunião, que o
sigilo do Núcleo guarda (`barrar_reuniao_do_nucleo`).

Quem vê o calendário é quem tem `calendario` (o membro sem Termo inclusive);
quem cria é quem tem `gerir_nucleo` (a Presidência e o Acesso pleno).
"""

import logging
from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.limiter import limiter
from app.routers.reunioes import _generate_reuniao_id
from app.services.seguranca_do_paciente.permissao import id_do_nucleo
from app.services.seguranca_do_paciente.reunioes import TipoReuniaoNsp

router = APIRouter(prefix="/nsp/reunioes", tags=["seguranca-do-paciente"])
logger = logging.getLogger(__name__)

# Só o que o calendário mostra: nada da ata. O membro sem Termo também lê esta
# lista, e a ata é o que ele não abre.
_COLUNAS_DO_CALENDARIO = "id_reuniao, data, hora_inicio, hora_fim, tipo, titulo, status_ata"


class ReuniaoDoNucleoRequest(BaseModel):
    titulo: str = Field(..., min_length=1, max_length=255)
    data: date
    hora_inicio: time | None = None
    hora_fim: time | None = None
    tipo: TipoReuniaoNsp
    objetivo: str | None = Field(None, max_length=500)


def _nucleo_ou_503(supabase) -> str:
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        raise HTTPException(status_code=503, detail="O Núcleo ainda não está cadastrado.")
    return nucleo_id


@router.get("")
@limiter.limit("60/minute")
async def listar_reunioes_do_nucleo(
    request: Request,
    me: dict = Depends(require_recurso_nsp("calendario")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """As reuniões do Núcleo, por data, sem as canceladas, e o que a pessoa
    pode fazer com elas (abrir a ata, criar reunião)."""
    nucleo_id = id_do_nucleo(supabase)
    linhas = (
        (
            supabase.table("reunioes")
            .select(_COLUNAS_DO_CALENDARIO)
            .eq("colegiado_id", nucleo_id)
            .is_("deleted_at", "null")
            .neq("status_ata", "CANCELADA")
            .order("data", desc=False)
            .execute()
        ).data
        or []
        if nucleo_id
        else []
    )
    return {
        "reunioes": linhas,
        "tipos": [t.value for t in TipoReuniaoNsp],
        "pode_abrir": "reunioes" in me["recursos_nsp"],
        "pode_criar": "gerir_nucleo" in me["recursos_nsp"],
    }


@router.post("", status_code=201)
@limiter.limit("30/minute")
async def criar_reuniao_do_nucleo(
    request: Request,
    req: ReuniaoDoNucleoRequest,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A Presidência cria a reunião à mão, programada, e fica como
    facilitadora. Sem convite por e-mail: a pauta e o convite do Núcleo chegam
    nas próximas fatias."""
    nucleo_id = _nucleo_ou_503(supabase)
    id_reuniao = _generate_reuniao_id(req.data)
    linha = {
        "id_reuniao": id_reuniao,
        "titulo": req.titulo.strip(),
        "data": req.data.isoformat(),
        "hora_inicio": req.hora_inicio.isoformat() if req.hora_inicio else None,
        "hora_fim": req.hora_fim.isoformat() if req.hora_fim else None,
        "tipo": req.tipo.value,
        "objetivo": req.objetivo,
        "status_ata": "PROGRAMADA",
        "fonte": "MOCK",
        "facilitador_id": me["id"],
        "criada_por": me["id"],
        "colegiado_id": nucleo_id,
    }
    supabase.table("reunioes").insert(linha).execute()
    supabase.table("reuniao_participantes").insert([{"id_reuniao": id_reuniao, "participante_id": me["id"]}]).execute()
    logger.info("Reunião do Núcleo %s (%s) criada por %s", id_reuniao, req.tipo.value, me["id"])
    return {"id_reuniao": id_reuniao, "tipo": req.tipo.value, "status": "PROGRAMADA"}
