"""A fonte de Atas do Início (issue #1936, ADR 0104, decisão 5).

A Ata a assinar é a Reunião em assinatura em que a pessoa é Signatária e
ainda não deu ciência, pela ClickSign ou pelo Aceite interno: as duas gravam o
Registro de Aceites (`reuniao_aceites`), e a Ata sai da fila assim que ele
existe. A Ata parada é a que espera o Facilitador na validação. As duas entram
em "Sem prazo", contando os dias desde o `updated_at` da Reunião, o mesmo
marco do card de Atas paradas do painel; a Ata parada conta como vencida a
partir do quarto dia (mais de 3 dias, a regra do card).

O sigilo do Núcleo é o da lista de Reuniões: Reunião do Núcleo que a pessoa
não alcança não aparece (issue #1772). Quem não tem perfil das Reuniões (ADR
0007) não recebe nada desta fonte.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.dependencies import reunioes_ocultas, tem_acesso_reunioes
from app.services.inicio.regras import FUSO

ROTULO = "as Atas"

# A Ata em validação para de esperar calada no quarto dia (o card do painel).
DIAS_ATE_A_ATA_PARAR = 3

_COLUNAS = "id_reuniao, titulo, data, status_ata, facilitador_id, updated_at"


def _data(valor: Any) -> date | None:
    return date.fromisoformat(str(valor)[:10]) if valor else None


def _dia_em_brasilia(valor: Any) -> date | None:
    if not valor:
        return None
    return datetime.fromisoformat(str(valor)).astimezone(FUSO).date()


def _origem(reuniao: dict) -> str:
    titulo = (reuniao.get("titulo") or "Reunião").strip()
    quando = _data(reuniao.get("data"))
    return f"{titulo}, de {quando.strftime('%d/%m/%Y')}." if quando else f"{titulo}."


def _vivas(supabase, status_ata: str, coluna: str, valor: Any) -> list[dict]:
    consulta = supabase.table("reunioes").select(_COLUNAS).eq("status_ata", status_ata).is_("deleted_at", "null")
    if isinstance(valor, list):
        consulta = consulta.in_(coluna, valor)
    else:
        consulta = consulta.eq(coluna, valor)
    return consulta.execute().data or []


def _ja_deu_ciencia(supabase, ids: list[str], me: dict) -> set[str]:
    """As Reuniões em que a pessoa já está no Registro de Aceites. O aceite
    casa com o Participante pelo id e, quando a ClickSign não o resolveu, pelo
    email normalizado (o mesmo fallback do `aceite_service`)."""
    email = (me.get("email") or "").strip().lower()
    aceites = (
        supabase.table("reuniao_aceites").select("id_reuniao, participante_id, email").in_("id_reuniao", ids).execute()
    )
    return {
        linha["id_reuniao"]
        for linha in aceites.data or []
        if linha.get("participante_id") == me["id"] or (email and (linha.get("email") or "").lower() == email)
    }


def _atas_a_assinar(supabase, me: dict) -> list[dict]:
    vinculos = (
        supabase.table("reuniao_participantes").select("id_reuniao").eq("participante_id", me["id"]).execute()
    )
    ids = sorted({linha["id_reuniao"] for linha in vinculos.data or []})
    if not ids:
        return []
    em_assinatura = _vivas(supabase, "AGUARDANDO_ASSINATURA", "id_reuniao", ids)
    if not em_assinatura:
        return []
    assinadas = _ja_deu_ciencia(supabase, [r["id_reuniao"] for r in em_assinatura], me)
    return [r for r in em_assinatura if r["id_reuniao"] not in assinadas]


def itens(supabase, me: dict) -> list[dict]:
    """Os itens da fonte, no formato comum do Início."""
    if not tem_acesso_reunioes(me):
        return []
    a_assinar = _atas_a_assinar(supabase, me)
    paradas = _vivas(supabase, "AGUARDANDO_VALIDACAO", "facilitador_id", me["id"])
    if not a_assinar and not paradas:
        return []
    ocultas = set(reunioes_ocultas(supabase, me))

    saida: list[dict] = []
    for reuniao in a_assinar:
        if reuniao["id_reuniao"] in ocultas:
            continue
        saida.append(
            {
                "tipo": "ata_a_assinar",
                "id": reuniao["id_reuniao"],
                "titulo": f"Ata a assinar: {(reuniao.get('titulo') or 'Reunião').strip()}",
                "origem": _origem(reuniao),
                "prazo": None,
                "chegou_em": _dia_em_brasilia(reuniao.get("updated_at")),
                "sem_prazo_no_modulo": True,
                "area": "Reuniões",
                "acao": "Assinar a Ata",
                "destino": f"/reunioes/{reuniao['id_reuniao']}",
            }
        )
    for reuniao in paradas:
        if reuniao["id_reuniao"] in ocultas:
            continue
        entrou = _dia_em_brasilia(reuniao.get("updated_at"))
        saida.append(
            {
                "tipo": "ata_parada",
                "id": reuniao["id_reuniao"],
                "titulo": f"Ata em validação: {(reuniao.get('titulo') or 'Reunião').strip()}",
                "origem": _origem(reuniao),
                "prazo": entrou + timedelta(days=DIAS_ATE_A_ATA_PARAR) if entrou else None,
                "chegou_em": entrou,
                "sem_prazo_no_modulo": True,
                "area": "Reuniões",
                "acao": "Revisar a Ata",
                "destino": f"/reunioes/{reuniao['id_reuniao']}",
            }
        )
    return saida
