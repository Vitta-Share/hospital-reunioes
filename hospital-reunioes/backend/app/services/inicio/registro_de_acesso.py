"""O Registro de acesso (issue #1941, ADR 0104 decisão 10).

A marca de que a pessoa abriu o Início num dia: uma por pessoa por dia, sem
trilha de cliques, guardada por 90 dias. Aqui só se grava e se apaga; nesta
fatia ninguém lê. Quem lê é o bloco Quem responde a você, e só para quem já
vê os itens da pessoa.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

TABELA = "registro_de_acesso"
DIAS_GUARDADOS = 90


def marcar(supabase, participante_id: str, dia: date) -> None:
    """Grava o dia da pessoa. A segunda abertura do dia bate na chave e não
    grava nada. Falha aqui não pode derrubar o Início: vira log e segue."""
    try:
        supabase.table(TABELA).upsert(
            {"participante_id": participante_id, "dia": dia.isoformat()},
            on_conflict="participante_id,dia",
            ignore_duplicates=True,
        ).execute()
    except Exception as e:
        logger.warning("[Início] Não gravou o Registro de acesso de %s: %s", participante_id, type(e).__name__)


def apagar_antigas(supabase, hoje: date) -> int:
    """Apaga as marcas com mais de 90 dias. Devolve quantas saíram."""
    limite = hoje - timedelta(days=DIAS_GUARDADOS)
    result = supabase.table(TABELA).delete().lt("dia", limite.isoformat()).execute()
    return len(result.data or [])
