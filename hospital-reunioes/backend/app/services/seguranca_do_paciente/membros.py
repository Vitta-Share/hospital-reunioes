"""Os membros do Núcleo (issue #1766, PRD #1764, ADR 0095).

O estado do membro é calculado, nunca gravado: sai de uma função pura a partir
das datas da Participação e do Termo de Adesão. Quem compunha o Núcleo num dia
qualquer sai da vigência, que é inclusiva nas duas pontas.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

# A janela antes do fim em que o membro aparece como "A vencer", e a carência
# depois do fim, em dias corridos (PRD #1764).
DIAS_A_VENCER = 60
DIAS_DE_CARENCIA = 30

ESTADOS = (
    "cadastrado",
    "documento_gerado",
    "aguardando_assinatura",
    "ativo",
    "a_vencer",
    "em_carencia",
    "vencido",
    "encerrado",
)


def _data(valor: Any) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def estado_do_membro(participacao: Mapping[str, Any], hoje: date) -> str:
    """Um dos `ESTADOS`, para a Participação no dia `hoje`.

    O Termo entra por três carimbos: gerado, enviado e assinado (o serviço
    `termo`, issue #1768). Carência é de quem assinou: sem assinatura, o membro
    espera a assinatura até vencer.
    """
    if participacao.get("encerrada_em"):
        return "encerrado"
    fim = _data(participacao["vigencia_fim"])
    if hoje > fim + timedelta(days=DIAS_DE_CARENCIA):
        return "vencido"
    if not participacao.get("termo_assinado_em"):
        if participacao.get("termo_enviado_em"):
            return "aguardando_assinatura"
        if participacao.get("termo_gerado_em"):
            return "documento_gerado"
        return "cadastrado"
    if hoje > fim:
        return "em_carencia"
    if hoje >= fim - timedelta(days=DIAS_A_VENCER):
        return "a_vencer"
    return "ativo"


def vigente_em(participacao: Mapping[str, Any], dia: date) -> bool:
    """A Participação valia no dia: início e fim inclusivos."""
    return _data(participacao["vigencia_inicio"]) <= dia <= _data(participacao["vigencia_fim"])
