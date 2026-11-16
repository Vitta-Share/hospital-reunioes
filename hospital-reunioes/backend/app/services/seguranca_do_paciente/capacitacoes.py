"""As Capacitações do Núcleo (issue #1778, PRD #1764, ADR 0095).

A leitura junta três tabelas (migration 155): as capacitações, quem participou
de cada uma (com a hora em que a própria pessoa confirmou a presença) e a lista
de temas mínimos, que é configuração da Presidência e nasce vazia.

A cobertura por membro é a regra do critério 3 da issue: um tema mínimo está
coberto para o membro quando ele CONFIRMOU presença numa capacitação que tratou
o tema. Estar na lista sem confirmar não conta, tema desativado não conta, e
"membro" é quem tem Participação vigente hoje no Núcleo.

Nada aqui chama IA nem manda e-mail.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services.seguranca_do_paciente.permissao import PAPEIS_DO_NUCLEO, id_do_nucleo, participacoes_vigentes

TABELA = "nsp_capacitacoes"
TABELA_PARTICIPANTES = "nsp_capacitacao_participantes"
TABELA_TEMAS = "nsp_temas_minimos"

_ORDEM_DO_PAPEL = {papel: i for i, papel in enumerate(PAPEIS_DO_NUCLEO)}


def _nomes(supabase, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    linhas = (supabase.table("participantes").select("id, nome_completo").in_("id", sorted(ids)).execute().data) or []
    return {linha["id"]: linha["nome_completo"] for linha in linhas}


def temas(supabase) -> list[dict[str, Any]]:
    linhas = supabase.table(TABELA_TEMAS).select("id, nome, ativo").execute().data or []
    return sorted(linhas, key=lambda t: (not t.get("ativo"), (t.get("nome") or "").lower()))


def cobertura(
    presencas: list[dict], capacitacoes: list[dict], temas_ativos: list[str], membros: list[dict]
) -> list[dict[str, Any]]:
    """Os temas mínimos ativos que cada membro já cobriu, com presença confirmada.

    `membros` traz `participante_id`, `nome` e `papel`; a ordem dos temas
    cobertos é a da lista de temas."""
    temas_da_capacitacao = {c["id"]: set(c.get("tema_ids") or []) for c in capacitacoes}
    cobertos: dict[str, set[str]] = {}
    for presenca in presencas:
        if not presenca.get("presenca_confirmada_em"):
            continue
        cobertos.setdefault(presenca["participante_id"], set()).update(
            temas_da_capacitacao.get(presenca["capacitacao_id"], set())
        )
    return [
        {**membro, "temas_cobertos": [t for t in temas_ativos if t in cobertos.get(membro["participante_id"], set())]}
        for membro in membros
    ]


def _membros_vigentes(supabase, hoje: date) -> list[dict]:
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return []
    linhas = participacoes_vigentes(supabase, nucleo_id, hoje).execute().data or []
    # Uma linha por pessoa, no papel mais alto.
    por_pessoa: dict[str, str] = {}
    for linha in linhas:
        atual = por_pessoa.get(linha["participante_id"])
        if atual is None or _ORDEM_DO_PAPEL.get(linha["papel"], 99) < _ORDEM_DO_PAPEL.get(atual, 99):
            por_pessoa[linha["participante_id"]] = linha["papel"]
    return [{"participante_id": pid, "papel": papel} for pid, papel in por_pessoa.items()]


def listar(supabase, hoje: date) -> dict[str, Any]:
    """O que a tela Capacitações mostra: as capacitações (mais nova primeiro),
    com os participantes e a presença, a lista de temas e a cobertura por membro."""
    capacitacoes = supabase.table(TABELA).select("*").order("data", desc=True).execute().data or []
    presencas = (
        supabase.table(TABELA_PARTICIPANTES)
        .select("capacitacao_id, participante_id, presenca_confirmada_em")
        .execute()
        .data
    ) or []
    lista_de_temas = temas(supabase)
    membros = _membros_vigentes(supabase, hoje)
    nomes = _nomes(supabase, {p["participante_id"] for p in presencas} | {m["participante_id"] for m in membros})

    por_capacitacao: dict[str, list[dict]] = {}
    for presenca in presencas:
        por_capacitacao.setdefault(presenca["capacitacao_id"], []).append(
            {
                "participante_id": presenca["participante_id"],
                "nome": nomes.get(presenca["participante_id"]),
                "presenca_confirmada_em": presenca.get("presenca_confirmada_em"),
            }
        )

    membros_com_nome = sorted(
        ({**m, "nome": nomes.get(m["participante_id"])} for m in membros),
        key=lambda m: (_ORDEM_DO_PAPEL.get(m["papel"], 99), (m["nome"] or "").lower()),
    )
    return {
        "capacitacoes": [
            {
                "id": c["id"],
                "titulo": c["titulo"],
                "data": c["data"],
                "carga_horaria": c["carga_horaria"],
                "instrutor": c["instrutor"],
                "publico": c["publico"],
                "tema_ids": c.get("tema_ids") or [],
                "participantes": sorted(
                    por_capacitacao.get(c["id"], []), key=lambda p: ((p["nome"] or "").lower(), p["participante_id"])
                ),
            }
            for c in capacitacoes
        ],
        "temas": lista_de_temas,
        "cobertura": cobertura(
            presencas, capacitacoes, [t["id"] for t in lista_de_temas if t.get("ativo")], membros_com_nome
        ),
    }
