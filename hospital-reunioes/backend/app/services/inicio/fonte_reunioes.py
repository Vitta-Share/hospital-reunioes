"""A fonte de Atas e o trilho de Reuniões do Início (issue #1936, ADR 0104).

A Ata a assinar é a Reunião em assinatura em que a pessoa é Signatária e
ainda não deu ciência, pela ClickSign ou pelo Aceite interno: as duas gravam o
Registro de Aceites (`reuniao_aceites`), e a Ata sai da fila assim que ele
existe. A Ata do Núcleo fica de fora da Ata a assinar: ela vai num envelope
próprio (`json_ata.assinatura`), assinam só os presentes, e a assinatura dela
não grava o Registro de Aceites, então o Início não sabe quem já assinou. A
Ata parada é a que espera o Facilitador na validação. As duas entram
em "Sem prazo", contando os dias desde o `updated_at` da Reunião, o mesmo
marco do card de Atas paradas do painel; a Ata parada conta como vencida a
partir do quarto dia (mais de 3 dias, a regra do card). O trilho traz as
próximas Reuniões da pessoa, fora da fila e da contagem da frase.

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

_COLUNAS = "id_reuniao, titulo, data, status_ata, facilitador_id, colegiado_id, updated_at"


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


def _em_que_participa(supabase, me: dict) -> list[str]:
    """As Reuniões em que a pessoa é Participante, que são as que ela assina."""
    vinculos = supabase.table("reuniao_participantes").select("id_reuniao").eq("participante_id", me["id"]).execute()
    return sorted({linha["id_reuniao"] for linha in vinculos.data or []})


def _atas_a_assinar(supabase, me: dict) -> list[dict]:
    ids = _em_que_participa(supabase, me)
    if not ids:
        return []
    em_assinatura = [
        r for r in _vivas(supabase, "AGUARDANDO_ASSINATURA", "id_reuniao", ids) if not r.get("colegiado_id")
    ]
    if not em_assinatura:
        return []
    assinadas = _ja_deu_ciencia(supabase, [r["id_reuniao"] for r in em_assinatura], me)
    return [r for r in em_assinatura if r["id_reuniao"] not in assinadas]


def itens(supabase, me: dict, _agora: datetime | None = None) -> list[dict]:
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


ROTULO_DO_TRILHO = "as próximas Reuniões"

# O trilho é um lembrete ao lado da fila, não a agenda inteira.
PROXIMAS_NO_TRILHO = 5


def _futuras(supabase, coluna: str, valor: Any, hoje: date) -> list[dict]:
    consulta = (
        supabase.table("reunioes")
        .select("id_reuniao, titulo, data, hora_inicio, facilitador_id")
        .gte("data", hoje.isoformat())
        .neq("status_ata", "CANCELADA")
        .is_("deleted_at", "null")
    )
    consulta = consulta.in_(coluna, valor) if isinstance(valor, list) else consulta.eq(coluna, valor)
    return consulta.execute().data or []


def proximas(supabase, me: dict, hoje: date) -> list[dict]:
    """As próximas Reuniões em que a pessoa é Facilitadora ou Participante, de
    hoje em diante, sem a cancelada e sem a do Núcleo que ela não alcança."""
    if not tem_acesso_reunioes(me):
        return []
    ids = _em_que_participa(supabase, me)
    reunioes = {r["id_reuniao"]: r for r in _futuras(supabase, "facilitador_id", me["id"], hoje)}
    if ids:
        for reuniao in _futuras(supabase, "id_reuniao", ids, hoje):
            reunioes.setdefault(reuniao["id_reuniao"], reuniao)
    if not reunioes:
        return []
    ocultas = set(reunioes_ocultas(supabase, me))
    visiveis = sorted(
        (r for r in reunioes.values() if r["id_reuniao"] not in ocultas),
        key=lambda r: (str(r["data"])[:10], r.get("hora_inicio") or "99", r["id_reuniao"]),
    )
    return [
        {
            "tipo": "reuniao",
            "id": reuniao["id_reuniao"],
            "titulo": (reuniao.get("titulo") or "Reunião").strip(),
            "data": _data(reuniao["data"]),
            "hora": str(reuniao["hora_inicio"])[:5] if reuniao.get("hora_inicio") else None,
            "papel": "facilitador" if reuniao.get("facilitador_id") == me["id"] else "participante",
            "destino": f"/reunioes/{reuniao['id_reuniao']}",
        }
        for reuniao in visiveis[:PROXIMAS_NO_TRILHO]
    ]
