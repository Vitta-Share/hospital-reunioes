"""A Rotina e a Verificação no banco (ADR 0098, decisão 9; issue #1874).

A regra dos ciclos é pura e mora em `rotina_ciclo`. Aqui: o nascimento da
Rotina no envio da Ata (pela mesma porta que cria as Pendências), a marcação
de uma Verificação e o encerramento. Nenhum job cria Verificação: o ciclo
existe pela data, e a linha só é gravada quando alguém marca.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.services.pendencia_service import _e_conflito_unicidade
from app.services.pendencias_consulta import hoje_em_brasilia
from app.services.quadro_classificacao import ROTINA, frequencia_da_linha, tipo_da_linha
from app.services.rotina_ciclo import primeiro_ciclo

logger = logging.getLogger(__name__)

ATIVA = "ATIVA"
ENCERRADA = "ENCERRADA"


def nascer_rotinas(
    supabase,
    id_reuniao: str,
    quadro_resolvido: list[dict],
    filtro: Callable[[dict], bool] | None = None,
) -> int:
    """Cria uma Rotina por linha do tipo Rotina do quadro já resolvido (com
    `responsavel_id`). Idempotente pela posição no quadro: Reenviar e a
    reconciliação das 5h30 não duplicam. Devolve quantas nasceram."""
    linhas = [
        (posicao, item)
        for posicao, item in enumerate(quadro_resolvido)
        if isinstance(item, dict) and tipo_da_linha(item) == ROTINA and (filtro is None or filtro(item))
    ]
    if not linhas:
        return 0
    existentes = supabase.table("rotinas").select("quadro_pos").eq("id_reuniao", id_reuniao).execute().data or []
    ocupadas = {r.get("quadro_pos") for r in existentes}
    hoje = hoje_em_brasilia()
    criadas = 0
    for posicao, item in linhas:
        if posicao in ocupadas:
            continue
        frequencia = frequencia_da_linha(item)
        rotina = {
            "id_reuniao": id_reuniao,
            "quadro_pos": posicao,
            "descricao": item.get("acao") or item.get("descricao_acao") or "Rotina sem descrição",
            "responsavel_id": item.get("responsavel_id"),
            "responsavel_nome": item.get("responsavel") or "",
            "frequencia": frequencia,
            "comeca_em": primeiro_ciclo(hoje, frequencia).inicio.isoformat() if frequencia else None,
            "status": ATIVA,
        }
        try:
            supabase.table("rotinas").insert(rotina).execute()
            criadas += 1
        except Exception as e:
            # Dois envios ao mesmo tempo: o outro já criou esta Rotina.
            if not _e_conflito_unicidade(e):
                raise
    if criadas:
        logger.info("[Rotina] %s Rotina(s) nasceram da Reunião %s", criadas, id_reuniao)
    return criadas
