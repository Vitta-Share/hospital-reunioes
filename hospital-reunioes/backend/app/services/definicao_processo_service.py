"""As Definições de processo do setor (ADR 0098, decisão 9; issue #1875).

A linha do tipo Processo do quadro da Ata entra, no envio, na lista do setor
da Reunião, com o trecho da Ata copiado: a lista não muda se a Ata for
corrigida depois. Sem responsável, sem prazo e sem lembrete.

Quem vê sai do vínculo, até o organograma (decisões 85 e 86 da #1757): o
Facilitador vê a lista de todo setor em que conduz alguma Reunião, e os itens
das Reuniões que ele mesmo conduz; o Super admin vê todas. Tirar da lista pede
anotação e cabe ao Facilitador da Reunião de origem e ao Super admin; o item
fica registrado como retirado.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.services.quadro_classificacao import PROCESSO, tipo_da_linha

logger = logging.getLogger(__name__)

ATIVA = "ATIVA"
RETIRADA = "RETIRADA"


class RetiradaRecusada(ValueError):  # noqa: N818, o nome do domínio
    """Tirar da lista sem anotação."""


class JaRetirada(ValueError):  # noqa: N818, o nome do domínio
    """O item já saiu da lista."""


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def nascer_definicoes(supabase, id_reuniao: str, quadro: list[dict]) -> int:
    """Cria um item por linha de Processo do quadro. Idempotente pela posição
    no quadro: Reenviar e a reconciliação das 5h30 não duplicam."""
    from app.services.pendencia_service import _e_conflito_unicidade

    linhas = [
        (posicao, item)
        for posicao, item in enumerate(quadro or [])
        if isinstance(item, dict) and tipo_da_linha(item) == PROCESSO
    ]
    if not linhas:
        return 0
    existentes = (
        supabase.table("definicoes_processo").select("quadro_pos").eq("id_reuniao", id_reuniao).execute().data or []
    )
    ocupadas = {r.get("quadro_pos") for r in existentes}
    criadas = 0
    for posicao, item in linhas:
        if posicao in ocupadas:
            continue
        definicao = {
            "id_reuniao": id_reuniao,
            "quadro_pos": posicao,
            "trecho": _texto(item.get("acao")) or _texto(item.get("descricao_acao")) or "Processo sem descrição",
            "objetivo": _texto(item.get("objetivo_meta")) or None,
            "status": ATIVA,
        }
        try:
            supabase.table("definicoes_processo").insert(definicao).execute()
            criadas += 1
        except Exception as e:
            # Dois envios ao mesmo tempo: o outro já criou este item.
            if not _e_conflito_unicidade(e):
                raise
    if criadas:
        logger.info("[Processo] %s definição(ões) de processo da Reunião %s", criadas, id_reuniao)
    return criadas
