"""O calendário anual e a pauta das reuniões do Núcleo (issue #1773, PRD #1764).

Três regras moram aqui, todas sem IA (a pauta é montada pelo sistema):

- o calendário: as doze ordinárias do ano, uma por mês, no dia que a
  Presidência escolhe. Dia que cai em fim de semana ou feriado cadastrado vai
  para o próximo dia útil do mesmo mês;
- a antecedência: a pauta da ordinária aparece 5 dias úteis antes, e a
  convocação vale até esse mesmo dia (ordinária) ou até 24 horas antes
  (qualquer outro tipo, a extraordinária);
- a montagem: as pendências da reunião anterior e a agenda regulatória, com os
  blocos das fases seguintes como "sem dados nesta fase".

Os feriados são os da tabela administrável do app (`ouvidoria_feriados`), a
mesma do Calendário útil.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from postgrest.exceptions import APIError

from app.services import feriados as servico_de_feriados
from app.services.pendencia_ciclo import situacao
from app.services.pendencias_consulta import as_data, hoje_em_brasilia, ids_repactuados
from app.services.seguranca_do_paciente.reunioes import TipoReuniaoNsp

logger = logging.getLogger(__name__)

FUSO = ZoneInfo("America/Sao_Paulo")

DIAS_UTEIS_DA_ORDINARIA = 5
HORAS_DA_EXTRAORDINARIA = 24

# A agenda regulatória entra na pauta quando a próxima data cai até um mês
# depois da reunião (até a ordinária seguinte), vencidas inclusive.
DIAS_DA_AGENDA_NA_PAUTA = 31

ORDINARIA = TipoReuniaoNsp.ORDINARIA_MENSAL.value

TABELA_PAUTAS = "nsp_pautas"

# Os blocos das fases seguintes: aparecem na pauta, vazios, até a fase que os
# cria entrar.
BLOCOS_SEM_DADOS = (
    ("indicadores", "Indicadores"),
    ("casos", "Casos"),
    ("planos_vencidos", "Planos de ação vencidos"),
    ("alertas_sanitarios", "Alertas sanitários"),
)

_SITUACAO = {
    "PENDENTE": "Pendente",
    "EM_PROGRESSO": "Em andamento",
    "ATRASADO": "Atrasada",
    "REPACTUADA": "Repactuada",
    "CONCLUIDO": "Concluída",
    "CANCELADO": "Cancelada",
}

# Coluna (42703) ou tabela (42P01) que o banco ainda não tem.
_AINDA_SEM_MIGRATION = ("42703", "42P01")


# ---------------------------------------------------------------------------
# Dia útil
# ---------------------------------------------------------------------------


def e_dia_util(dia: date, feriados: frozenset[date]) -> bool:
    return dia.weekday() < 5 and dia not in feriados


def dias_uteis_antes(dia: date, quantos: int, feriados: frozenset[date]) -> date:
    """O enésimo dia útil antes de `dia` (o próprio dia não conta)."""
    atual = dia
    for _ in range(quantos):
        atual -= timedelta(days=1)
        while not e_dia_util(atual, feriados):
            atual -= timedelta(days=1)
    return atual


def _dia_util_do_mes(dia: date, feriados: frozenset[date]) -> date:
    """O próprio dia, se útil; senão o próximo útil do mês, ou o anterior
    quando o mês acaba antes."""
    adiante = dia
    while not e_dia_util(adiante, feriados):
        adiante += timedelta(days=1)
    if adiante.month == dia.month:
        return adiante
    atras = dia
    while not e_dia_util(atras, feriados):
        atras -= timedelta(days=1)
    return atras


def datas_do_calendario(ano: int, dia: int, feriados: frozenset[date]) -> list[date]:
    """As doze datas das ordinárias do ano, uma por mês."""
    return [_dia_util_do_mes(date(ano, mes, dia), feriados) for mes in range(1, 13)]


def data_da_pauta(tipo: str, data_reuniao: date, feriados: frozenset[date]) -> date | None:
    """O dia em que a pauta aparece: 5 dias úteis antes da ordinária. Os
    outros tipos são marcados perto da data e têm a pauta desde a criação
    (None)."""
    if tipo != ORDINARIA:
        return None
    return dias_uteis_antes(data_reuniao, DIAS_UTEIS_DA_ORDINARIA, feriados)


def recusa_da_convocacao(
    tipo: str, data_reuniao: date, hora_inicio: time | None, agora: datetime, feriados: frozenset[date]
) -> str | None:
    """A mensagem de recusa quando a convocação sai fora da antecedência
    mínima do tipo, ou None quando ela pode sair."""
    if hora_inicio is None:
        return "Defina a hora da reunião antes de convocar: o e-mail leva a data e a hora."
    agora = agora.astimezone(FUSO)
    if tipo == ORDINARIA:
        limite = dias_uteis_antes(data_reuniao, DIAS_UTEIS_DA_ORDINARIA, feriados)
        if agora.date() > limite:
            return (
                "A reunião ordinária precisa ser convocada com 5 dias úteis de antecedência. "
                f"O último dia para convocar esta era {limite.strftime('%d/%m/%Y')}."
            )
        return None
    inicio = datetime.combine(data_reuniao, hora_inicio, tzinfo=FUSO)
    if inicio - agora < timedelta(hours=HORAS_DA_EXTRAORDINARIA):
        return "A reunião extraordinária precisa ser convocada com pelo menos 24 horas de antecedência."
    return None


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------


def _data(valor: Any) -> date:
    return date.fromisoformat(str(valor)[:10])


def feriados_entre(supabase, inicio: date, fim: date) -> frozenset[date]:
    """Os feriados cadastrados no intervalo. Falha de leitura conta como
    nenhum feriado: a conta erra para o lado de convocar e mostrar a pauta um
    pouco antes, e a tela não cai. A leitura é a do serviço comum de feriados
    (issue #1984)."""
    try:
        return servico_de_feriados.feriados_entre(supabase, inicio, fim)
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Feriados ilegíveis; o calendário do Núcleo conta sem eles: %s", erro)
        return frozenset()


def ordinarias_do_ano(supabase, nucleo_id: str, ano: int) -> list[dict]:
    """As ordinárias do Núcleo marcadas no ano, sem as canceladas."""
    return (
        supabase.table("reunioes")
        .select("id_reuniao, data")
        .eq("colegiado_id", nucleo_id)
        .eq("tipo", ORDINARIA)
        .gte("data", date(ano, 1, 1).isoformat())
        .lte("data", date(ano, 12, 31).isoformat())
        .is_("deleted_at", "null")
        .neq("status_ata", "CANCELADA")
        .execute()
        .data
        or []
    )


# ---------------------------------------------------------------------------
# A montagem (sem IA)
# ---------------------------------------------------------------------------


def _dd_mm_aaaa(valor: Any) -> str:
    return _data(valor).strftime("%d/%m/%Y")


def _reuniao_anterior(supabase, reuniao: dict) -> dict | None:
    """A ordinária do Núcleo imediatamente antes desta, sem as canceladas."""
    linhas = (
        supabase.table("reunioes")
        .select("id_reuniao, data")
        .eq("colegiado_id", reuniao["colegiado_id"])
        .eq("tipo", ORDINARIA)
        .lt("data", str(reuniao["data"])[:10])
        .is_("deleted_at", "null")
        .neq("status_ata", "CANCELADA")
        .order("data", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return linhas[0] if linhas else None


def _itens_das_pendencias(supabase, reuniao: dict) -> list[dict]:
    anterior = _reuniao_anterior(supabase, reuniao)
    if not anterior:
        return []
    pendencias = (
        supabase.table("pendencias")
        .select("id_acao, descricao_acao, responsavel_nome, prazo")
        .eq("id_reuniao", anterior["id_reuniao"])
        .is_("deleted_at", "null")
        .order("id_acao")
        .execute()
        .data
        or []
    )
    itens = []
    for p in pendencias:
        responsavel = p.get("responsavel_nome") or "sem responsável"
        prazo = _dd_mm_aaaa(p["prazo"]) if p.get("prazo") else "sem prazo"
        itens.append(
            {"texto": f"{p['descricao_acao']}. Responsável: {responsavel}; prazo: {prazo}.", "id_acao": p["id_acao"]}
        )
    return itens


def _itens_da_agenda(supabase, reuniao: dict) -> list[dict]:
    teto = _data(reuniao["data"]) + timedelta(days=DIAS_DA_AGENDA_NA_PAUTA)
    try:
        eventos = (
            supabase.table("nsp_agenda_regulatoria")
            .select("evento, proxima_data")
            .eq("ativo", True)
            .lte("proxima_data", teto.isoformat())
            .order("proxima_data")
            .execute()
            .data
            or []
        )
    except APIError as erro:
        if getattr(erro, "code", None) not in _AINDA_SEM_MIGRATION:
            raise
        return []
    return [
        {"texto": f"{e['evento']}, prevista para {_dd_mm_aaaa(e['proxima_data'])}"}
        for e in eventos
        if e.get("proxima_data")
    ]


def montar(supabase, reuniao: dict) -> list[dict]:
    """Os blocos da pauta, montados pelo sistema a partir do banco."""
    return [
        {
            "chave": "pendencias",
            "titulo": "Pendências da reunião anterior",
            "sem_dados": False,
            "itens": _itens_das_pendencias(supabase, reuniao),
        },
        {
            "chave": "agenda",
            "titulo": "Agenda regulatória",
            "sem_dados": False,
            "itens": _itens_da_agenda(supabase, reuniao),
        },
        *({"chave": chave, "titulo": titulo, "sem_dados": True, "itens": []} for chave, titulo in BLOCOS_SEM_DADOS),
    ]


def pauta_gravada(supabase, id_reuniao: str) -> dict | None:
    linhas = supabase.table(TABELA_PAUTAS).select("*").eq("id_reuniao", id_reuniao).limit(1).execute().data or []
    return linhas[0] if linhas else None


def garantir_pauta(supabase, reuniao: dict, agora: datetime) -> dict:
    """A pauta gravada da reunião, montada agora se ainda não existe. Duas
    leituras ao mesmo tempo montam uma pauta só: a chave é a reunião."""
    existente = pauta_gravada(supabase, reuniao["id_reuniao"])
    if existente:
        return existente
    linha = {"id_reuniao": reuniao["id_reuniao"], "blocos": montar(supabase, reuniao), "montada_em": agora.isoformat()}
    try:
        supabase.table(TABELA_PAUTAS).insert(linha).execute()
    except APIError as erro:
        if getattr(erro, "code", None) != "23505":
            raise
        return pauta_gravada(supabase, reuniao["id_reuniao"]) or linha
    return linha


CASOS = "casos"
_TITULO_DOS_CASOS = "Casos"


def _cita(blocos: list[dict], protocolo: str) -> bool:
    padrao = re.compile(rf"(?<![\w-]){re.escape(protocolo)}(?![\w-])")
    return any(padrao.search(item.get("texto") or "") for bloco in blocos for item in bloco.get("itens", []))


def incluir_caso(supabase, pauta_da_reuniao: dict, protocolo: str, texto: str) -> None:
    """Põe o caso no bloco Casos de uma pauta já gravada, uma vez só. Se a
    Presidência tirou o bloco, ele volta com o caso."""
    blocos = [dict(bloco) for bloco in pauta_da_reuniao.get("blocos") or []]
    if _cita(blocos, protocolo):
        return
    bloco = next((b for b in blocos if b.get("chave") == CASOS), None)
    if bloco is None:
        bloco = {"chave": CASOS, "titulo": _TITULO_DOS_CASOS, "sem_dados": False, "itens": []}
        blocos.append(bloco)
    bloco["itens"] = [*bloco.get("itens", []), {"texto": texto}]
    bloco["sem_dados"] = False
    supabase.table(TABELA_PAUTAS).update({"blocos": blocos}).eq("id_reuniao", pauta_da_reuniao["id_reuniao"]).execute()


def com_situacao_atual(supabase, blocos: list[dict]) -> list[dict]:
    """Os blocos com a situação de hoje de cada pendência citada. Atrasada e
    Repactuada são calculadas, como na tela de Pendências (issue #1862)."""
    ids = sorted({item["id_acao"] for bloco in blocos for item in bloco.get("itens", []) if item.get("id_acao")})
    status = {}
    if ids:
        hoje = hoje_em_brasilia()
        repactuados = ids_repactuados(supabase, ids)
        status = {
            p["id_acao"]: situacao(
                p.get("status") or "", as_data(p.get("prazo")), hoje, repactuada=p["id_acao"] in repactuados
            )
            for p in (
                supabase.table("pendencias")
                .select("id_acao, status, prazo")
                .in_("id_acao", ids)
                .is_("deleted_at", "null")
                .execute()
                .data
                or []
            )
        }
    return [
        {
            **bloco,
            "itens": [
                {**item, "situacao": _SITUACAO.get(status.get(item["id_acao"]), "Removida")}
                if item.get("id_acao")
                else item
                for item in bloco.get("itens", [])
            ],
        }
        for bloco in blocos
    ]
