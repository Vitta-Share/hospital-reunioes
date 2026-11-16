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


def texto_da_reuniao_rapida(texto: str) -> str:
    """O texto como fica gravado: quebra de linha única, sem espaço nas
    pontas. Mais de três linhas é recusado; a linha em branco conta."""
    limpo = texto.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not limpo:
        raise ValueError("Escreva o que foi conversado")
    if len(limpo.split("\n")) > TETO_DE_LINHAS:
        raise ValueError("O texto da reunião rápida tem no máximo três linhas")
    return limpo


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


def reunioes_rapidas(supabase, nucleo_id: str, *, com_conteudo: bool) -> list[dict]:
    """As reuniões rápidas do Núcleo no formato da lista do módulo (issue #1777).

    O setor faz as vezes de título. O texto e os nomes de quem participou só
    vão a quem abre a ata das outras reuniões do Núcleo (`com_conteudo`); quem
    ainda não assinou o Termo vê a data, o tipo e o setor, como nas outras.
    Entre o deploy e a migration 154 colada no Studio, a lista vazia é a verdade.
    """
    try:
        linhas = (
            supabase.table("nsp_reunioes_rapidas")
            .select("id, data, setor, participantes, texto")
            .eq("colegiado_id", nucleo_id)
            .execute()
            .data
        ) or []
    except APIError as erro:
        if getattr(erro, "code", None) not in _AINDA_SEM_MIGRATION:
            raise
        logger.warning("Reuniões rápidas ilegíveis: a migration 154 ainda não rodou (%s).", erro)
        return []
    nomes: dict[str, str] = {}
    ids = sorted({pid for linha in linhas for pid in (linha.get("participantes") or [])})
    if com_conteudo and ids:
        pessoas = supabase.table("participantes").select("id, nome_completo").in_("id", ids).execute().data or []
        nomes = {p["id"]: p["nome_completo"] for p in pessoas}
    itens = []
    for linha in linhas:
        item = {
            "id_reuniao": linha["id"],
            "data": linha["data"],
            "hora_inicio": None,
            "tipo": TipoReuniaoNsp.REUNIAO_RAPIDA.value,
            "titulo": linha["setor"],
            "status_ata": None,
            "rapida": True,
        }
        if com_conteudo:
            item["texto"] = linha["texto"]
            item["participantes"] = [nomes.get(pid, "Pessoa sem cadastro") for pid in linha.get("participantes") or []]
        itens.append(item)
    return itens
