"""A fonte da Ouvidoria no Início (issue #1937, ADR 0099 e ADR 0104).

Titular, substituto e gestor vigentes veem o caso acionado para o setor deles
que ainda espera a área, com o prazo do setor. O recorte é o da porta do login
da Tela do responsável (`ouvidoria_papel.setores_de`), que é para onde o botão
leva: o Início não mostra caso que aquela porta recusaria.

O item não carrega relato, resumo nem quem manifestou. O título é o Assunto do
caso; sem Assunto, ou com sigilo reforçado (a Tela do responsável só mostra a
nota da ouvidoria), é o protocolo. O caso com pedido de prorrogação esperando a
decisão da Ouvidoria sai da fila: a bola está com ela.
"""

from __future__ import annotations

from datetime import date, datetime

from app.services import ouvidoria_papel
from app.services.ouvidoria_blocos import sob_sigilo
from app.services.ouvidoria_prazos import FUSO, esta_vencido, ler_instante
from app.services.ouvidoria_prorrogacao import PENDENTE
from app.services.paginacao import ler_tudo

ROTULO = "os casos da Ouvidoria"

AGUARDANDO_AREA = "aguardando_area"

_COLUNAS = "id, protocolo, setor, status, assunto, sigilo_reforcado, prazo_area_em, validada_em, arquivada_em"


def _titulo(caso: dict) -> str:
    assunto = (caso.get("assunto") or "").strip()
    if assunto and not sob_sigilo(caso):
        return assunto
    return f"Manifestação {caso.get('protocolo')}"


def _com_prorrogacao_pedida(supabase, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    linhas = (
        supabase.table("ouvidoria_prorrogacoes")
        .select("manifestacao_id, status")
        .in_("manifestacao_id", ids)
        .eq("status", PENDENTE)
        .execute()
        .data
    )
    return {linha["manifestacao_id"] for linha in linhas or []}


def itens(supabase, me: dict, agora: datetime) -> list[dict]:
    setores = ouvidoria_papel.setores_de(supabase, me, agora.astimezone(FUSO).date())
    if not setores:
        return []
    casos = (
        supabase.table("ouvidoria_protocolos")
        .select(_COLUNAS)
        .in_("setor", sorted(setores))
        .eq("status", AGUARDANDO_AREA)
        .is_("arquivada_em", "null")
        .execute()
        .data
        or []
    )
    # Acionado é o caso que a validação carimbou (ADR 0099, decisão 2).
    casos = [caso for caso in casos if caso.get("validada_em")]
    pedidos = _com_prorrogacao_pedida(supabase, sorted(caso["id"] for caso in casos))

    saida: list[dict] = []
    for caso in casos:
        if caso["id"] in pedidos:
            continue
        vencimento = ler_instante(caso.get("prazo_area_em"))
        acionado = ler_instante(caso.get("validada_em"))
        saida.append(
            {
                "tipo": "caso_da_ouvidoria",
                "id": caso["id"],
                "titulo": _titulo(caso),
                "origem": f"Ouvidoria, protocolo {caso.get('protocolo')}, setor {caso.get('setor')}.",
                "prazo": vencimento.astimezone(FUSO).date() if vencimento else None,
                "chegou_em": acionado.astimezone(FUSO).date() if acionado else None,
                "area": "Ouvidoria",
                "acao": "Responder",
                "destino": f"/ouvidoria/responder/{caso['id']}",
            }
        )
    return saida


# A Fila do papel (ADR 0104, decisão 6): a fila da Ouvidoria não tem
# responsável nomeado, e para quem tem Perfil da Ouvidoria vira uma linha de
# resumo. Conta como o topo da própria fila: em andamento é o que ainda corre
# (`EM_ANDAMENTO` de `lib/ouvidoria/prazo.ts`), fora do arquivo, e vencida é a
# que estourou o prazo da área ou, sem ele, o prazo de referência. O elogio não
# vence (ADR 0088).
EM_ANDAMENTO = ("novo", "em_classificacao", AGUARDANDO_AREA)

ROTULO_DA_FILA = "a fila da Ouvidoria"


def _vencida(caso: dict, agora: datetime) -> bool:
    if caso.get("tipo_manifestacao") == "elogio":
        return False
    vencimento = ler_instante(caso.get("prazo_area_em"))
    if vencimento is not None:
        return esta_vencido(vencimento, agora)
    referencia = caso.get("prazo_resposta")
    return bool(referencia) and date.fromisoformat(str(referencia)[:10]) < agora.astimezone(FUSO).date()


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def fila_do_papel(supabase, me: dict, agora: datetime) -> list[dict]:
    if me.get("perfil_ouvidoria") not in ouvidoria_papel.PERFIS_OUVIDORIA:
        return []

    def consulta():
        return (
            supabase.table("ouvidoria_protocolos")
            .select("numero, status, tipo_manifestacao, prazo_area_em, prazo_resposta")
            .in_("status", list(EM_ANDAMENTO))
            .is_("arquivada_em", "null")
            .order("numero")
        )

    casos = ler_tudo(consulta, rotulo="a fila da Ouvidoria no Início")
    esperam = len(casos)
    vencidas = sum(1 for caso in casos if _vencida(caso, agora))
    return [
        {
            "fila": "ouvidoria",
            "titulo": "Fila da Ouvidoria",
            "esperam": esperam,
            "vencidas": vencidas,
            "resumo": (
                f"{_plural(esperam, 'manifestação espera', 'manifestações esperam')}, "
                f"{_plural(vencidas, 'vencida', 'vencidas')}."
            ),
            "destino": "/ouvidoria",
        }
    ]
