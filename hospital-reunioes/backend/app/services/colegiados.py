"""O Colegiado e as Participações nele (ADR 0095 decisão 3, ADR 0097 decisão 3).

O Núcleo de Segurança do Paciente e o Comitê de Conduta são Colegiados sobre
as mesmas tabelas (`colegiados` e `participacoes`). Este serviço recebe o
Colegiado como parâmetro e não sabe qual é: o que muda de um para outro (o
slug, a sigla do envelope, as tabelas e o modelo do Termo de Adesão) vem no
`Colegiado`. Cada módulo declara o seu (o Núcleo, em
`seguranca_do_paciente.permissao.NUCLEO`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

COLUNAS_DA_PARTICIPACAO = (
    "id, participante_id, papel, area, vigencia_inicio, vigencia_fim, encerrada_em, "
    "termo_gerado_em, termo_enviado_em, termo_assinado_em"
)


@dataclass(frozen=True)
class Colegiado:
    # O slug na tabela `colegiados`.
    slug: str
    # Como as mensagens o chamam ("participações do <nome>").
    nome: str
    # No nome do envelope e do arquivo do Termo na assinatura eletrônica.
    sigla: str
    # Os papéis da Participação, do mais alto ao mais baixo.
    papeis: tuple[str, ...]
    # Uma linha por envio do Termo de Adesão; o webhook acha o envio por ela.
    termos_envios: str
    # Os documentos do Colegiado: o Regimento, o ato de designação e o Termo assinado.
    documentos: str
    # Os envios desses documentos para assinatura.
    documentos_envios: str
    # O campo de `settings` com o bucket privado dos documentos.
    bucket_dos_documentos: str
    # O modelo HTML do Termo de Adesão.
    modelo_do_termo: str


def id_do_colegiado(supabase, colegiado: Colegiado) -> str | None:
    """O id do Colegiado em `colegiados`, ou None quando a migration não rodou."""
    linhas = supabase.table("colegiados").select("id").eq("slug", colegiado.slug).limit(1).execute().data or []
    return linhas[0]["id"] if linhas else None


def participacoes_vigentes(supabase, colegiado_id: str, hoje: date) -> Any:
    """A consulta das Participações do Colegiado vigentes no dia, sem executar."""
    return (
        supabase.table("participacoes")
        .select("id, participante_id, papel, termo_assinado_em")
        .eq("colegiado_id", colegiado_id)
        .lte("vigencia_inicio", hoje.isoformat())
        .gte("vigencia_fim", hoje.isoformat())
    )


def participacoes_do_colegiado(supabase, colegiado_id: str) -> list[dict]:
    """Todas as Participações do Colegiado, encerradas inclusive."""
    return (
        supabase.table("participacoes").select(COLUNAS_DA_PARTICIPACAO).eq("colegiado_id", colegiado_id).execute().data
    ) or []


def participacao_do_colegiado(supabase, colegiado_id: str, participacao_id: str) -> dict | None:
    """A Participação, só se ela for deste Colegiado."""
    linhas = (
        supabase.table("participacoes")
        .select(COLUNAS_DA_PARTICIPACAO)
        .eq("id", participacao_id)
        .eq("colegiado_id", colegiado_id)
        .limit(1)
        .execute()
        .data
    ) or []
    return linhas[0] if linhas else None


def vinculo_vigente(supabase, colegiado: Colegiado, participante_id: str, hoje: date) -> tuple[str | None, bool]:
    """O papel vigente da pessoa no Colegiado e se o Termo dela vale.

    Com mais de uma Participação vigente, vale a de Termo assinado e, entre
    elas, a de papel mais alto. Erro de leitura sobe para quem chama."""
    colegiado_id = id_do_colegiado(supabase, colegiado)
    if not colegiado_id:
        return None, False
    linhas = (
        participacoes_vigentes(supabase, colegiado_id, hoje).eq("participante_id", participante_id).execute().data
    ) or []
    if not linhas:
        return None, False
    ordem = {papel: i for i, papel in enumerate(colegiado.papeis)}
    melhor = min(
        linhas,
        key=lambda linha: (not linha.get("termo_assinado_em"), ordem.get(linha.get("papel"), 99)),
    )
    return melhor.get("papel"), bool(melhor.get("termo_assinado_em"))
