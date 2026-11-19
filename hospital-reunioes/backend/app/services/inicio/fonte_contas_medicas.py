"""A fonte de Contas médicas do Início (issue #1940, ADR 0104).

Na Minha Fila entram as contas que a faturista puxou e ainda não concluiu, em
correção ou em retorno da Validação (`fila.COM_A_FATURISTA`), só as que estão
no nome dela (`cm_conta.faturista_id`): nem a coordenação, que vê as contas de
todas na tela do módulo, recebe aqui a conta de outra pessoa. O módulo não dá
prazo à conta, e o item fica em Sem prazo, com há quantos dias a conta foi
puxada. O botão abre o Guia da conta.

A Fila de contas (as livres, com Guia pronto e sem dono) é de um papel e não
de uma pessoa (decisão 6): vira uma linha da Fila do papel para quem a
enxerga no módulo, quem tem "Analisar contas".

O portão é o do módulo: sem perfil de Contas médicas (e sem ser Super admin),
nada, e sem "Analisar contas", nem conta nem Fila.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.dependencies import PERFIS_CONTAS_MEDICAS, is_super_admin, permissoes_contas_medicas
from app.services.contas_medicas.fila import COM_A_FATURISTA, EM_CORRECAO, LIVRE
from app.services.inicio.regras import FUSO

ROTULO = "as contas médicas"
ROTULO_DA_FILA = "a Fila de contas"

# A permissão que dá a Fila, "Minhas" e o Guia (`_PODE_ANALISAR` das rotas).
ANALISAR_CONTAS = "enviar_corrigir_contas"


def _data(valor: Any) -> date | None:
    """O dia de Brasília do `aberta_em` (TIMESTAMPTZ gravado em UTC): a conta
    puxada às 22h30 de 12/11 chegou em 12/11, não em 13/11."""
    if not valor:
        return None
    momento = valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor))
    if momento.tzinfo is None:
        return momento.date()
    return momento.astimezone(FUSO).date()


def _analisa_contas(supabase, me: dict) -> bool:
    if not is_super_admin(me) and me.get("perfil_contas_medicas") not in PERFIS_CONTAS_MEDICAS:
        return False
    return ANALISAR_CONTAS in permissoes_contas_medicas(supabase, me)


def _atendimentos(supabase, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    linhas = supabase.table("cm_atendimento").select("id, numero_atendimento").in_("id", ids).execute().data
    return {linha["id"]: linha for linha in linhas or []}


def _titulo(conta: dict, atendimento: dict | None) -> str:
    """A conta é identificada pelo atendimento, com a conta como complemento,
    como na Fila do módulo."""
    numero = (atendimento or {}).get("numero_atendimento")
    partes = [f"Atendimento {numero}"] if numero else []
    if conta.get("numero_conta"):
        partes.append(f"conta {conta['numero_conta']}")
    return ", ".join(partes) if partes else "Conta sem número"


def itens(supabase, me: dict, _agora: datetime | None = None) -> list[dict]:
    """As contas com a pessoa, no formato comum do Início, sem grupo."""
    if not _analisa_contas(supabase, me):
        return []
    contas = (
        supabase.table("cm_conta")
        .select("id, situacao, faturista_id, atendimento_id, numero_conta, aberta_em, ordem_fila")
        .eq("faturista_id", me["id"])
        .in_("situacao", list(COM_A_FATURISTA))
        .execute()
        .data
        or []
    )
    atendimentos = _atendimentos(supabase, sorted({c["atendimento_id"] for c in contas if c.get("atendimento_id")}))
    return [
        {
            "tipo": "conta_medica",
            "id": conta["id"],
            "titulo": _titulo(conta, atendimentos.get(conta.get("atendimento_id"))),
            "origem": "Contas médicas, em correção."
            if conta["situacao"] == EM_CORRECAO
            else "Contas médicas, em retorno da Validação.",
            "prazo": None,
            "chegou_em": _data(conta.get("aberta_em")),
            "sem_prazo_no_modulo": True,
            "area": "Contas médicas",
            "acao": "Abrir o Guia",
            "destino": f"/contas-medicas/guia/{conta['id']}",
        }
        for conta in contas
    ]


def fila_do_papel(supabase, me: dict, _agora: datetime | None = None) -> list[dict]:
    """A linha da Fila de contas: quantas contas livres esperam alguém pegar.
    A conta não tem prazo no módulo, então nenhuma conta como vencida."""
    if not _analisa_contas(supabase, me):
        return []
    livres = supabase.table("cm_conta").select("id", count="exact").eq("situacao", LIVRE).limit(1).execute().count
    if not livres:
        return []
    resumo = "1 conta sem dono espera na Fila." if livres == 1 else f"{livres} contas sem dono esperam na Fila."
    return [
        {
            "fila": "contas_medicas",
            "titulo": "Fila de contas",
            "esperam": livres,
            "vencidas": 0,
            "resumo": resumo,
            "destino": "/contas-medicas",
        }
    ]
