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
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.limiter import limiter
from app.routers.reunioes import _generate_reuniao_id
from app.services.seguranca_do_paciente import convocacao, pauta
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


class CalendarioRequest(BaseModel):
    ano: int = Field(..., ge=2020, le=2100)
    # Até 28: todo mês tem o dia.
    dia: int = Field(..., ge=1, le=28)
    hora_inicio: time
    hora_fim: time | None = None


_MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


@router.post("/calendario", status_code=201)
@limiter.limit("10/minute")
async def gerar_calendario_anual(
    request: Request,
    req: CalendarioRequest,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """As doze ordinárias do ano, uma por mês, programadas. Mês que já tem
    ordinária (não cancelada) fica como está: pedir de novo não duplica."""
    nucleo_id = _nucleo_ou_503(supabase)
    ja_existiam = sorted({int(str(r["data"])[5:7]) for r in pauta.ordinarias_do_ano(supabase, nucleo_id, req.ano)})
    criadas = []
    for dia in pauta.datas_do_calendario(
        req.ano, req.dia, pauta.feriados_entre(supabase, date(req.ano, 1, 1), date(req.ano, 12, 31))
    ):
        if dia.month in ja_existiam:
            continue
        id_reuniao = _generate_reuniao_id(dia)
        supabase.table("reunioes").insert(
            {
                "id_reuniao": id_reuniao,
                "titulo": f"Reunião ordinária de {_MESES[dia.month - 1]} de {dia.year}",
                "data": dia.isoformat(),
                "hora_inicio": req.hora_inicio.isoformat(),
                "hora_fim": req.hora_fim.isoformat() if req.hora_fim else None,
                "tipo": pauta.ORDINARIA,
                "status_ata": "PROGRAMADA",
                "fonte": "MOCK",
                "facilitador_id": me["id"],
                "criada_por": me["id"],
                "colegiado_id": nucleo_id,
            }
        ).execute()
        supabase.table("reuniao_participantes").insert(
            [{"id_reuniao": id_reuniao, "participante_id": me["id"]}]
        ).execute()
        criadas.append({"id_reuniao": id_reuniao, "data": dia.isoformat()})
    logger.info("Calendário %s do Núcleo: %d ordinária(s) criada(s) por %s", req.ano, len(criadas), me["id"])
    return {"ano": req.ano, "criadas": criadas, "ja_existiam": ja_existiam}


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


# ---------------------------------------------------------------------------
# A pauta e a convocação (issue #1773)
# ---------------------------------------------------------------------------


def _agora() -> datetime:
    return datetime.now(tz=pauta.FUSO)


def _reuniao_do_nucleo(supabase, id_reuniao: str) -> dict:
    """A reunião, se for do Núcleo; senão 404 (a reunião comum tem a tela dela)."""
    nucleo_id = id_do_nucleo(supabase)
    linhas = (
        (
            supabase.table("reunioes")
            .select("id_reuniao, data, hora_inicio, hora_fim, tipo, titulo, status_ata, colegiado_id")
            .eq("id_reuniao", id_reuniao)
            .eq("colegiado_id", nucleo_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        ).data
        or []
        if nucleo_id
        else []
    )
    if not linhas:
        raise HTTPException(status_code=404, detail="Reunião do Núcleo não encontrada.")
    return linhas[0]


def _feriados_da_reuniao(supabase, reuniao: dict) -> frozenset:
    dia = date.fromisoformat(str(reuniao["data"])[:10])
    return pauta.feriados_entre(supabase, dia - timedelta(days=60), dia)


class ItemDaPauta(BaseModel):
    texto: str = Field(..., min_length=1, max_length=1000)
    id_acao: str | None = Field(None, max_length=10)


class BlocoDaPauta(BaseModel):
    chave: str | None = Field(None, max_length=40)
    titulo: str = Field(..., min_length=1, max_length=200)
    sem_dados: bool = False
    itens: list[ItemDaPauta] = Field(default_factory=list, max_length=100)


class PautaRequest(BaseModel):
    blocos: list[BlocoDaPauta] = Field(..., max_length=30)


def _disponivel_em(supabase, reuniao: dict) -> date | None:
    data_reuniao = date.fromisoformat(str(reuniao["data"])[:10])
    return pauta.data_da_pauta(reuniao["tipo"], data_reuniao, _feriados_da_reuniao(supabase, reuniao))


@router.put("/{id_reuniao}/pauta")
@limiter.limit("30/minute")
async def editar_pauta(
    request: Request,
    id_reuniao: str,
    req: PautaRequest,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A Presidência ajusta a pauta montada: muda texto, tira, inclui item ou
    bloco. Vale enquanto a reunião está programada."""
    reuniao = _reuniao_do_nucleo(supabase, id_reuniao)
    if reuniao.get("status_ata") != "PROGRAMADA":
        raise HTTPException(status_code=409, detail="A reunião já aconteceu: a pauta não muda mais.")
    agora = _agora()
    disponivel_em = _disponivel_em(supabase, reuniao)
    if disponivel_em and agora.date() < disponivel_em:
        raise HTTPException(
            status_code=409,
            detail=f"A pauta desta reunião aparece em {disponivel_em.strftime('%d/%m/%Y')}.",
        )
    atual = pauta.garantir_pauta(supabase, reuniao, agora)
    # Só a pendência que a montagem trouxe fica presa ao item: o id vindo da
    # tela não abre a situação de outra pendência.
    citadas = {i.get("id_acao") for b in atual.get("blocos", []) for i in b.get("itens", []) if i.get("id_acao")}
    blocos = [
        {
            "chave": bloco.chave,
            "titulo": bloco.titulo.strip(),
            "sem_dados": bloco.sem_dados and not bloco.itens,
            "itens": [
                {"texto": item.texto.strip(), **({"id_acao": item.id_acao} if item.id_acao in citadas else {})}
                for item in bloco.itens
            ],
        }
        for bloco in req.blocos
    ]
    supabase.table(pauta.TABELA_PAUTAS).update(
        {"blocos": blocos, "editada_em": agora.isoformat(), "editada_por": me["id"]}
    ).eq("id_reuniao", id_reuniao).execute()
    logger.info("Pauta da reunião do Núcleo %s editada por %s", id_reuniao, me["id"])
    return {"id_reuniao": id_reuniao, "blocos": pauta.com_situacao_atual(supabase, blocos)}


@router.get("/{id_reuniao}/pauta")
@limiter.limit("60/minute")
async def ver_pauta(
    request: Request,
    id_reuniao: str,
    me: dict = Depends(require_recurso_nsp("reunioes")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A pauta da reunião. Da data da pauta em diante ela é montada pelo
    sistema (uma vez) e mostrada com a situação de hoje de cada pendência;
    antes, a resposta diz quando ela aparece."""
    reuniao = _reuniao_do_nucleo(supabase, id_reuniao)
    agora = _agora()
    disponivel_em = _disponivel_em(supabase, reuniao)
    disponivel =disponivel_em is None or agora.date() >= disponivel_em
    gravada = pauta.garantir_pauta(supabase, reuniao, agora) if disponivel else None
    gerir = "gerir_nucleo" in me["recursos_nsp"]
    lista = convocacao.convocados(supabase, id_reuniao)
    return {
        "id_reuniao": reuniao["id_reuniao"],
        "titulo": reuniao.get("titulo"),
        "tipo": reuniao["tipo"],
        "data": reuniao["data"],
        "hora_inicio": reuniao.get("hora_inicio"),
        "disponivel": disponivel,
        "disponivel_em": disponivel_em.isoformat() if disponivel_em else None,
        "blocos": pauta.com_situacao_atual(supabase, gravada["blocos"]) if gravada else [],
        "editada_em": gravada.get("editada_em") if gravada else None,
        "pode_editar": disponivel and gerir and reuniao.get("status_ata") == "PROGRAMADA",
        "convocacao": {"convocada_em": lista[0].get("convocado_em"), "convocados": lista} if lista else None,
        "pode_convocar": gerir and not lista and reuniao.get("status_ata") == "PROGRAMADA",
        # O que a tela diz antes do clique, quando o prazo já passou.
        "recusa_da_convocacao": None if lista else _recusa(supabase, reuniao, agora),
    }


def _recusa(supabase, reuniao: dict, agora: datetime) -> str | None:
    hora = time.fromisoformat(str(reuniao["hora_inicio"])[:8]) if reuniao.get("hora_inicio") else None
    data_reuniao = date.fromisoformat(str(reuniao["data"])[:10])
    return pauta.recusa_da_convocacao(
        reuniao["tipo"], data_reuniao, hora, agora, _feriados_da_reuniao(supabase, reuniao)
    )


@router.post("/{id_reuniao}/convocacao", status_code=201)
@limiter.limit("10/minute")
async def convocar(
    request: Request,
    id_reuniao: str,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Um clique: e-mail nominal a quem conta para quórum, com data e hora
    absolutas, e a lista de convocados gravada. Fora da antecedência mínima do
    tipo, recusa com a mensagem."""
    reuniao = _reuniao_do_nucleo(supabase, id_reuniao)
    if reuniao.get("status_ata") != "PROGRAMADA":
        raise HTTPException(status_code=409, detail="A reunião já aconteceu: não há o que convocar.")
    agora = _agora()
    recusa = _recusa(supabase, reuniao, agora)
    if recusa:
        raise HTTPException(status_code=422, detail=recusa)
    try:
        lista = convocacao.convocar(
            supabase, reuniao, nucleo_id=reuniao["colegiado_id"], autor_id=me["id"], agora=agora
        )
    except convocacao.JaConvocadaError as erro:
        quando = f" em {erro.convocada_em[8:10]}/{erro.convocada_em[5:7]}/{erro.convocada_em[:4]}" if erro.convocada_em else ""
        raise HTTPException(status_code=409, detail=f"Esta reunião já foi convocada{quando}.") from erro
    except convocacao.NinguemParaConvocarError as erro:
        raise HTTPException(status_code=409, detail="Nenhum membro conta para quórum hoje.") from erro
    logger.info("Reunião do Núcleo %s convocada por %s: %d pessoa(s)", id_reuniao, me["id"], len(lista))
    return {"id_reuniao": id_reuniao, "convocada_em": agora.isoformat(), "convocados": lista}
