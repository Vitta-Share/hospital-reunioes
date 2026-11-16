"""As reuniões do Núcleo (issue #1772, PRD #1764, ADR 0095, decisão 4).

A reunião do Núcleo é uma reunião como as outras, com `colegiado_id`
preenchido (migration 148). O que muda é quem a vê: só quem a permissão do
módulo libera, e nunca o super admin pelo simples fato de ser super admin.

Aqui mora a leitura de quais reuniões são do Núcleo. Quem decide o que cada
pessoa alcança é `app.dependencies.visibilidade_das_reunioes`, que toda leitura
de reunião do app usa.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from postgrest.exceptions import APIError

from app.services.seguranca_do_paciente.permissao import SLUG_DO_NUCLEO

logger = logging.getLogger(__name__)


class TipoReuniaoNsp(StrEnum):
    """Os quatro tipos de reunião do Núcleo (o CHECK da migration 148)."""

    ORDINARIA_MENSAL = "Ordinária mensal"
    ANALISE_DE_EVENTO = "Análise de evento"
    APRESENTACAO_A_DIRETORIA = "Apresentação à Diretoria"
    REUNIAO_RAPIDA = "Reunião rápida de segurança"


# O texto da reunião rápida de segurança (issue #1777): até três linhas, e um
# teto de caracteres para as três linhas não virarem um parágrafo.
TETO_DE_LINHAS = 3
TETO_DO_TEXTO = 500

# Coluna (42703) ou tabela (42P01) que o banco ainda não tem.
_AINDA_SEM_MIGRATION = ("42703", "42P01")


def reunioes_do_nucleo(supabase) -> list[str]:
    """Os ids das reuniões do Núcleo.

    Entre o deploy e a migration 148 colada no Studio, a coluna não existe e
    ainda não há reunião do Núcleo nenhuma: a lista vazia é a verdade, e o
    resto do app segue de pé. Qualquer outra falha sobe, e a leitura que dependia
    dela cai inteira, em vez de mostrar reunião do Núcleo a quem não podia.
    """
    try:
        # O slug é único: sem `limit`, a consulta fica no mínimo que toda
        # leitura de reunião do app passa a fazer.
        nucleos = supabase.table("colegiados").select("id").eq("slug", SLUG_DO_NUCLEO).execute().data or []
        if not nucleos:
            return []
        linhas = supabase.table("reunioes").select("id_reuniao").eq("colegiado_id", nucleos[0]["id"]).execute().data
    except APIError as erro:
        if getattr(erro, "code", None) not in _AINDA_SEM_MIGRATION:
            raise
        logger.warning("Reuniões do Núcleo ilegíveis: a migration 148 ainda não rodou (%s).", erro)
        return []
    return [linha["id_reuniao"] for linha in (linhas or [])]
