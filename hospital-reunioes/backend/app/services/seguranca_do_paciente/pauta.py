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
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from postgrest.exceptions import APIError

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
    pouco antes, e a tela não cai."""
    try:
        linhas = (
            supabase.table("ouvidoria_feriados")
            .select("data")
            .gte("data", inicio.isoformat())
            .lte("data", fim.isoformat())
            .execute()
            .data
            or []
        )
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Feriados ilegíveis; o calendário do Núcleo conta sem eles: %s", erro)
        return frozenset()
    return frozenset(_data(linha["data"]) for linha in linhas if linha.get("data"))


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
