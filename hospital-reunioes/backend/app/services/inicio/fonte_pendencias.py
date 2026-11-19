"""A fonte de Pendências do Início (issue #1934, ADR 0104, decisão 5).

As Pendências abertas em que a pessoa é responsável ou co-responsável. Entra
também a Pendência sem Reunião, o lembrete da Agenda regulatória do Núcleo,
que nenhuma lista de Pendências mostra (`e_lembrete_do_nucleo`): ela aparece a
quem a tem no nome e alcança a Agenda regulatória. O sigilo do Núcleo segue o
da lista de Pendências: a Pendência de uma Reunião do Núcleo que a pessoa não
alcança não aparece (issue #1772).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.dependencies import recursos_nsp_da_pessoa, reunioes_ocultas
from app.services.pendencia_service import e_lembrete_do_nucleo

ROTULO = "as Pendências"

STATUS_ABERTOS = ("PENDENTE", "EM_PROGRESSO", "ATRASADO", "REPACTUADA")

_COLUNAS = "id_acao, descricao_acao, prazo, status, id_reuniao, responsavel_id, co_responsavel_id, created_at"


def _data(valor: Any) -> date | None:
    return date.fromisoformat(str(valor)[:10]) if valor else None


def _abertas_no_nome(supabase, pessoa_id: str) -> list[dict]:
    """Duas consultas simples, uma por coluna, juntas pelo id: o OR do
    PostgREST com `in` e `is` junto fica frágil e não ganha nada aqui."""
    linhas: dict[str, dict] = {}
    for coluna in ("responsavel_id", "co_responsavel_id"):
        resultado = (
            supabase.table("pendencias")
            .select(_COLUNAS)
            .eq(coluna, pessoa_id)
            .in_("status", list(STATUS_ABERTOS))
            .is_("deleted_at", "null")
            .execute()
        )
        for linha in resultado.data or []:
            linhas.setdefault(linha["id_acao"], linha)
    return list(linhas.values())


def _reunioes(supabase, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    resultado = supabase.table("reunioes").select("id_reuniao, titulo, data").in_("id_reuniao", ids).execute()
    return {linha["id_reuniao"]: linha for linha in resultado.data or []}


def _origem_da_reuniao(reuniao: dict | None) -> str:
    if not reuniao:
        return "Pendência de Reunião."
    titulo = (reuniao.get("titulo") or "Reunião").strip()
    quando = _data(reuniao.get("data"))
    return f"{titulo}, de {quando.strftime('%d/%m/%Y')}." if quando else f"{titulo}."


def itens(supabase, me: dict) -> list[dict]:
    """Os itens da fonte, no formato comum do Início, sem grupo: o grupo e o
    atraso são calculados por quem monta (`montar_inicio`)."""
    linhas = _abertas_no_nome(supabase, me["id"])
    if not linhas:
        return []

    ocultas = set(reunioes_ocultas(supabase, me))
    das_reunioes = [linha for linha in linhas if not e_lembrete_do_nucleo(linha) and linha["id_reuniao"] not in ocultas]
    lembretes = [linha for linha in linhas if e_lembrete_do_nucleo(linha)]
    if lembretes and "agenda" not in recursos_nsp_da_pessoa(supabase, me):
        lembretes = []

    reunioes = _reunioes(supabase, sorted({linha["id_reuniao"] for linha in das_reunioes}))
    saida: list[dict] = []
    for linha in das_reunioes:
        origem = _origem_da_reuniao(reunioes.get(linha["id_reuniao"]))
        if linha.get("co_responsavel_id") == me["id"] and linha.get("responsavel_id") != me["id"]:
            origem += " Você é co-responsável."
        saida.append(
            {
                "tipo": "pendencia",
                "id": linha["id_acao"],
                "titulo": linha.get("descricao_acao") or "Pendência sem descrição",
                "origem": origem,
                "prazo": _data(linha.get("prazo")),
                "chegou_em": _data(linha.get("created_at")),
                "area": "Reuniões",
                "acao": "Abrir a Pendência",
                "destino": f"/pendencias/kanban?highlight={linha['id_acao']}",
            }
        )
    for linha in lembretes:
        saida.append(
            {
                "tipo": "lembrete_da_agenda",
                "id": linha["id_acao"],
                "titulo": linha.get("descricao_acao") or "Lembrete da Agenda regulatória",
                "origem": "Lembrete da Agenda regulatória do Núcleo.",
                "prazo": _data(linha.get("prazo")),
                "chegou_em": _data(linha.get("created_at")),
                "area": "Segurança do Paciente",
                "acao": "Abrir na agenda",
                "destino": "/seguranca-do-paciente/agenda",
            }
        )
    return saida
