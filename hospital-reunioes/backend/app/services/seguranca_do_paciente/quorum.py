"""O quórum da reunião do Núcleo (issue #1774, PRD #1764, ADR 0095).

Função pura, sem banco nem relógio: entram as Participações do Núcleo, a
presença registrada e o dia da reunião; sai a apuração. Conta para quórum quem
estava em Ativo, A vencer ou Em carência no dia da reunião. O quórum é metade
deles (arredondada para cima), com a Presidência ou o suplente presente.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.services.seguranca_do_paciente.membros import _data, estado_do_membro

# A presença de cada pessoa na reunião (o CHECK da migration 153).
SITUACOES_DE_PRESENCA = ("presente", "ausente", "ausente_justificado", "convidado")

ESTADOS_QUE_CONTAM = frozenset({"ativo", "a_vencer", "em_carencia"})

_FUSO = ZoneInfo("America/Sao_Paulo")


def _dia_do_termo(valor: Any) -> date:
    """O dia (em São Paulo) em que o Termo foi assinado."""
    if isinstance(valor, datetime):
        instante = valor
    else:
        instante = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    if instante.tzinfo is None:
        return instante.date()
    return instante.astimezone(_FUSO).date()


def conta_para_quorum(participacao: Mapping[str, Any], dia: date) -> bool:
    """A Participação contava para quórum no dia da reunião.

    O estado é o daquele dia: a Participação já tinha começado, o Termo já
    estava assinado e o encerramento (se houve) ainda não tinha chegado.
    """
    if _data(participacao["vigencia_inicio"]) > dia:
        return False
    termo = participacao.get("termo_assinado_em")
    if not termo or _dia_do_termo(termo) > dia:
        return False
    encerrada = participacao.get("encerrada_em")
    naquele_dia = dict(participacao)
    if encerrada and _data(encerrada) >= dia:
        # Encerrada depois: no dia da reunião ainda valia.
        naquele_dia["encerrada_em"] = None
    return estado_do_membro(naquele_dia, dia) in ESTADOS_QUE_CONTAM


@dataclass(frozen=True)
class Quorum:
    total: int
    presentes: int
    minimo: int
    presidencia_ou_suplente: bool
    instalada: bool

    def como_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "presentes": self.presentes,
            "minimo": self.minimo,
            "presidencia_ou_suplente": self.presidencia_ou_suplente,
            "instalada": self.instalada,
        }


def apurar_quorum(participacoes: Iterable[Mapping[str, Any]], presenca: Mapping[str, str], dia: date) -> Quorum:
    """A apuração do quórum. `presenca` vai do participante à situação."""
    contam = [p for p in participacoes if conta_para_quorum(p, dia)]
    pessoas = {p["participante_id"]: p for p in contam}
    presentes = [pid for pid in pessoas if presenca.get(pid) == "presente"]
    comando = any(pessoas[pid]["papel"] in ("presidencia", "suplente") for pid in presentes)
    total = len(pessoas)
    minimo = (total + 1) // 2
    instalada = total > 0 and len(presentes) >= minimo and comando
    return Quorum(
        total=total,
        presentes=len(presentes),
        minimo=minimo,
        presidencia_ou_suplente=comando,
        instalada=instalada,
    )
