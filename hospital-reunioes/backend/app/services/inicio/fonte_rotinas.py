"""A fonte de Rotinas do Início (issue #1874; ADR 0098, decisão 9).

Uma linha por ciclo em aberto das Rotinas de que a pessoa é responsável: o
ciclo de agora e os que fecharam sem marcação. O ciclo vem da data, nada é
gravado para ele existir. O prazo é o último dia do ciclo, então o ciclo que
fechou cai em "Passou do prazo" sozinho. Realizada é um clique, ali mesmo;
Não realizada pede anotação e fica na tela das Rotinas. O sigilo do Núcleo
segue o das Pendências.
"""

from __future__ import annotations

from datetime import datetime

from app.dependencies import reunioes_ocultas, tem_acesso_reunioes
from app.services import rotina_service
from app.services.inicio.regras import FUSO

ROTULO = "as Rotinas"

_FREQUENCIA = {"SEMANAL": "semanal", "QUINZENAL": "quinzenal", "MENSAL": "mensal"}


def _origem(rotina: dict, reuniao: dict | None) -> str:
    frequencia = _FREQUENCIA.get(rotina.get("frequencia") or "", "")
    titulo = ((reuniao or {}).get("titulo") or "").strip()
    rotina_de = f"Rotina {frequencia}".strip()
    return f"{rotina_de} da {titulo}." if titulo else f"{rotina_de}."


def itens(supabase, me: dict, agora: datetime | None = None) -> list[dict]:
    """Os itens da fonte, no formato comum do Início, sem grupo."""
    if not tem_acesso_reunioes(me):
        return []
    rotinas = supabase.table("rotinas").select("*").eq("responsavel_id", me["id"]).execute().data or []
    if not rotinas:
        return []
    ocultas = set(reunioes_ocultas(supabase, me))
    rotinas = [r for r in rotinas if r["id_reuniao"] not in ocultas]
    if not rotinas:
        return []
    hoje = (agora or datetime.now(FUSO)).astimezone(FUSO).date()
    marcadas = rotina_service.verificacoes_de(supabase, [r["id"] for r in rotinas])
    ids_reunioes = sorted({r["id_reuniao"] for r in rotinas})
    reunioes = {
        r["id_reuniao"]: r
        for r in supabase.table("reunioes").select("id_reuniao, titulo").in_("id_reuniao", ids_reunioes).execute().data
        or []
    }
    saida: list[dict] = []
    for rotina in rotinas:
        origem = _origem(rotina, reunioes.get(rotina["id_reuniao"]))
        for ciclo in rotina_service.ciclos_em_aberto(rotina, marcadas.get(rotina["id"], []), hoje):
            inicio = ciclo.inicio.isoformat()
            saida.append(
                {
                    "tipo": "verificacao_da_rotina",
                    "id": f"{rotina['id']}:{inicio}",
                    "titulo": rotina.get("descricao") or "Rotina sem descrição",
                    "origem": origem,
                    "prazo": ciclo.fim,
                    "chegou_em": ciclo.inicio,
                    "area": "Reuniões",
                    "acao": "Abrir as Rotinas",
                    "destino": "/rotinas",
                    "contexto": (
                        f"Ciclo de {ciclo.inicio.strftime('%d/%m')} a {ciclo.fim.strftime('%d/%m')}. "
                        "Se não foi feita, marque Não realizada na tela das Rotinas, com uma anotação."
                    ),
                    "acao_de_um_clique": {
                        "rotulo": "Realizada",
                        "endpoint": f"/api/rotinas/{rotina['id']}/ciclos/{inicio}/realizada",
                    },
                }
            )
    return saida
