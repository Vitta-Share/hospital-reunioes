"""A fonte de POPs do Início (issue #1938, ADR 0104).

A Versão que está parada com a pessoa: a elaborar ou em elaboração para o
Elaborador, em revisão para o Revisor, em validação para o Validador. A regra
de quem é o dono da etapa é a do módulo (`papel_da_etapa_ativa`), e o portão é
o perfil de POPs (`require_perfil_pop`): sem ele, as telas do POP recusam a
pessoa, e o Início também. POP publicado ou em assinatura não aparece.

O módulo não dá prazo à etapa: o item fica em "Sem prazo", com a data em que a
Versão entrou na etapa. Essa data vem da trilha de auditoria (a transição mais
recente que levou a Versão ao estado atual); na etapa "a elaborar", é a criação
da Versão. Sem trilha, o item aparece sem a contagem de dias.
"""

from __future__ import annotations

from datetime import date, datetime

from app.models.pops_schemas import PERFIS_POP
from app.services.inicio.regras import FUSO
from app.services.pops_dominio import papel_da_etapa_ativa

ROTULO = "os POPs"

# Em assinatura o POP espera o ClickSign, não uma pessoa da etapa.
ESTADOS_COM_DONO = ("A_ELABORAR", "EM_ELABORACAO", "EM_REVISAO", "EM_VALIDACAO")

_PAPEIS = ("elaborador_id", "revisor_id", "validador_id")

_ACAO_E_TELA = {
    "elaborador_id": ("Elaborar", "elaboracao"),
    "revisor_id": ("Revisar", "versao"),
    "validador_id": ("Validar", "versao"),
}

_ETAPA = {
    "A_ELABORAR": "a elaborar",
    "EM_ELABORACAO": "em elaboração",
    "EM_REVISAO": "em revisão",
    "EM_VALIDACAO": "em validação",
}


def _dia_em_brasilia(valor) -> date | None:
    if not valor:
        return None
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).astimezone(FUSO).date()


def _pops_designados(supabase, pessoa_id: str) -> dict[str, dict]:
    """Uma consulta por papel, juntas pelo id (o mesmo jeito da fonte de
    Pendências: sem o OR do PostgREST)."""
    pops: dict[str, dict] = {}
    for papel in _PAPEIS:
        resultado = supabase.table("pops").select("*").eq(papel, pessoa_id).execute()
        for linha in resultado.data or []:
            pops.setdefault(linha["id"], linha)
    return pops


def _entrou_na_etapa(supabase, versoes: list[dict]) -> dict[str, date]:
    """{versao_id: dia em que a Versão entrou no estado em que está}."""
    estado_de = {versao["id"]: versao["estado"] for versao in versoes}
    resultado = (
        supabase.table("audit_log")
        .select("target_id, timestamp, metadata")
        .eq("target_type", "pop_versao")
        .in_("target_id", sorted(estado_de))
        .execute()
    )
    mais_recente: dict[str, str] = {}
    for linha in resultado.data or []:
        versao_id = linha.get("target_id")
        quando = linha.get("timestamp")
        if not quando or (linha.get("metadata") or {}).get("para") != estado_de.get(versao_id):
            continue
        if versao_id not in mais_recente or quando > mais_recente[versao_id]:
            mais_recente[versao_id] = quando
    datas = {versao_id: _dia_em_brasilia(quando) for versao_id, quando in mais_recente.items()}
    for versao in versoes:
        if versao["estado"] == "A_ELABORAR" and versao["id"] not in datas:
            datas[versao["id"]] = _dia_em_brasilia(versao.get("created_at"))
    return datas


def itens(supabase, me: dict) -> list[dict]:
    """Os itens da fonte, no formato comum do Início."""
    if me.get("perfil_pop") not in PERFIS_POP:
        return []
    pops = _pops_designados(supabase, me["id"])
    if not pops:
        return []

    versoes = (
        supabase.table("pops_versoes")
        .select("id, pop_id, estado, numero_versao, created_at")
        .in_("pop_id", sorted(pops))
        .in_("estado", list(ESTADOS_COM_DONO))
        .execute()
        .data
        or []
    )
    minhas = [
        (versao, papel)
        for versao in versoes
        if (papel := papel_da_etapa_ativa(versao)) and pops[versao["pop_id"]].get(papel) == me["id"]
    ]
    if not minhas:
        return []

    datas = _entrou_na_etapa(supabase, [versao for versao, _ in minhas])
    saida: list[dict] = []
    for versao, papel in minhas:
        pop = pops[versao["pop_id"]]
        acao, tela = _ACAO_E_TELA[papel]
        saida.append(
            {
                "tipo": "pop",
                "id": pop["id"],
                "titulo": pop.get("nome") or pop.get("codigo") or "POP sem nome",
                "origem": f"{pop.get('codigo')}, versão {versao.get('numero_versao')}, {_ETAPA[versao['estado']]}.",
                "prazo": None,
                "chegou_em": datas.get(versao["id"]),
                "sem_prazo_no_modulo": True,
                "area": "POPs",
                "acao": acao,
                "destino": f"/pops/{pop['id']}/{tela}",
            }
        )
    return saida
