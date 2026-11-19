"""As regras puras do Início (ADR 0104): o grupo de cada item, os dias de
atraso e a frase do topo. Só data e número, sem banco e sem IA (ADR 0082).

O atraso sai da data, nunca do status gravado: um item aberto com o prazo
vencido está atrasado mesmo que o job ainda não o tenha marcado, e o status
`ATRASADO` de um item com prazo futuro não o põe no grupo vencido.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")

PASSOU_DO_PRAZO = "passou_do_prazo"
ATE_48_HORAS = "ate_48_horas"
PROXIMOS_7_DIAS = "proximos_7_dias"
GRUPOS = (PASSOU_DO_PRAZO, ATE_48_HORAS, PROXIMOS_7_DIAS)
# O item a que o módulo de origem não dá prazo (a Ata a assinar, a Ata parada até
# o terceiro dia, a conta com a faturista): fica no fim, com há quantos dias
# espera, e não é vencido.
SEM_PRAZO = "sem_prazo"


def _fim_do_dia(prazo: date) -> datetime:
    """O prazo é um dia: ele só vence quando o dia acaba em Brasília."""
    return datetime.combine(prazo + timedelta(days=1), time(0), tzinfo=FUSO)


def grupo_do_prazo(prazo: date | None, agora: datetime) -> str | None:
    """Em qual dos três grupos o item cai. Sem prazo, ou além de 7 dias,
    nenhum: o item existe, e a tela não o mostra na fila."""
    if prazo is None:
        return None
    restante = _fim_do_dia(prazo) - agora
    if restante <= timedelta(0):
        return PASSOU_DO_PRAZO
    if restante <= timedelta(hours=48):
        return ATE_48_HORAS
    if restante <= timedelta(days=7):
        return PROXIMOS_7_DIAS
    return None


def grupo_do_item(prazo: date | None, sem_prazo_no_modulo: bool, agora: datetime) -> str | None:
    """O grupo de um item. O item a que o módulo não dá prazo fica em Sem prazo, e só
    sai de lá se o prazo que a fonte calculou vencer (a Ata parada, a partir do
    quarto dia)."""
    grupo = grupo_do_prazo(prazo, agora)
    if sem_prazo_no_modulo and grupo != PASSOU_DO_PRAZO:
        return SEM_PRAZO
    return grupo


def dias_esperando(chegou_em: date | None, agora: datetime) -> int | None:
    """Há quantos dias, no calendário de Brasília, o item espera."""
    if chegou_em is None:
        return None
    return max((agora.astimezone(FUSO).date() - chegou_em).days, 0)


def dias_de_atraso(prazo: date | None, agora: datetime) -> int | None:
    """Quantos dias, no calendário de Brasília, o prazo ficou para trás.
    Prazo de ontem é um dia; prazo de hoje ainda não atrasou."""
    if prazo is None:
        return None
    dias = (agora.astimezone(FUSO).date() - prazo).days
    return dias if dias > 0 else None


_EXTENSO = ("nenhum", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez")


def _numero(n: int) -> str:
    return _EXTENSO[n] if n < len(_EXTENSO) else str(n)


def _dias(n: int) -> str:
    return "1 dia" if n == 1 else f"{n} dias"


def _com_nome(nome: str | None, resto: str) -> str:
    if nome:
        return f"{nome}, {resto}"
    return resto[0].upper() + resto[1:]


def frase_do_inicio(
    *,
    nome: str | None,
    vencidos: int,
    maior_atraso: int,
    em_48_horas: int,
    proximo_prazo: date | None,
) -> tuple[str, str]:
    """A frase do topo (título e apoio), escrita por regra a partir dos
    números (ADR 0104, decisão 7). Três casos: com prazo vencido, sem vencido
    e com item em 48 horas, e em dia."""
    if vencidos:
        if vencidos == 1:
            titulo = _com_nome(nome, "um prazo seu venceu.")
            apoio = f"Ele espera há {_dias(maior_atraso)}."
        else:
            titulo = _com_nome(nome, f"{_numero(vencidos)} prazos seus venceram.")
            apoio = f"O mais antigo espera há {_dias(maior_atraso)}."
        if em_48_horas == 1:
            apoio += " Mais um vence em até 48 horas."
        elif em_48_horas > 1:
            apoio += f" Mais {_numero(em_48_horas)} vencem em até 48 horas."
        return titulo, apoio
    if em_48_horas:
        titulo = _com_nome(nome, "nada atrasado.")
        if em_48_horas == 1:
            return titulo, "Um prazo vence em até 48 horas."
        quantos = _numero(em_48_horas)
        return titulo, f"{quantos[0].upper()}{quantos[1:]} prazos vencem em até 48 horas."
    titulo = _com_nome(nome, "você está em dia.")
    if proximo_prazo is None:
        return titulo, "Nenhum prazo aberto no seu nome."
    return titulo, f"O próximo prazo é {proximo_prazo.strftime('%d/%m')}."
