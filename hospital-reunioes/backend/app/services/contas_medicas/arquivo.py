"""O arquivar de Contas médicas (issue #1958, PRD #1933, ADR 0105, decisões 6 a 10).

Arquivar é um carimbo, não uma situação: a Conta Concluída ou Concluída com
pendência ganha a data e a pessoa que arquivou (`arquivada_em`,
`arquivada_por`), e a `situacao` fica como está. Painel, Retorno e reenvio
continuam lendo a situação. Desarquivar limpa o carimbo; o Retorno da
Validação também (em `validacao._decidir_as_linhas`).

Quem arquiva (decisão 8): a faturista arquiva as contas em que é a
`faturista_id`, uma a uma ou todas as dela de uma Competência; quem tem
"painel completo" arquiva qualquer uma e a Competência inteira. Desarquivar
segue a mesma regra.
"""

from __future__ import annotations

from app.services.contas_medicas.competencia import competencia
from app.services.contas_medicas.fila import CONCLUIDAS, _concluidas, _trocar_id_por_nome, ve_todas
from app.services.paginacao import ler_tudo

COM_PENDENCIA = "CONCLUIDA_COM_PENDENCIA"
# Quantos ids cabem num `in_` por vez: a lista vai na querystring.
LOTE_DE_IDS = 100

SO_A_CONCLUIDA = "Só a conta concluída se arquiva."
JA_ARQUIVADA = "Esta conta já está arquivada."
NAO_ARQUIVADA = "Esta conta não está arquivada."
DE_OUTRA = "Esta conta é de outra faturista. Só quem tem o painel completo arquiva."
DE_OUTRA_DESARQUIVAR = "Esta conta é de outra faturista. Só quem tem o painel completo desarquiva."
MUDOU = "A conta mudou enquanto você arquivava. Atualize a tela."


class ContaNaoEncontradaError(Exception):
    pass


class SemPermissaoError(Exception):
    pass


class NaoArquivavelError(Exception):
    pass


def pode_mexer(conta: dict, me: dict) -> bool:
    """A faturista mexe nas dela; quem tem "painel completo", em qualquer uma."""
    return ve_todas(me) or conta.get("faturista_id") == me.get("id")


def _ler(supabase, conta_id: str) -> dict:
    linhas = supabase.table("cm_conta").select("*").eq("id", conta_id).limit(1).execute().data or []
    if not linhas:
        raise ContaNaoEncontradaError(conta_id)
    return linhas[0]


def arquivar(supabase, conta_id: str, me: dict, agora: str) -> None:
    """Carimba a conta. O UPDATE é condicional na situação e no carimbo vazio:
    a conta que voltou em Retorno ou foi arquivada por outra pessoa entre a
    leitura e a escrita não é carimbada."""
    conta = _ler(supabase, conta_id)
    if not pode_mexer(conta, me):
        raise SemPermissaoError(DE_OUTRA)
    if conta.get("situacao") not in CONCLUIDAS:
        raise NaoArquivavelError(SO_A_CONCLUIDA)
    if conta.get("arquivada_em"):
        raise NaoArquivavelError(JA_ARQUIVADA)
    gravadas = (
        supabase.table("cm_conta")
        .update({"arquivada_em": agora, "arquivada_por": me.get("id")})
        .eq("id", conta_id)
        .in_("situacao", list(CONCLUIDAS))
        .is_("arquivada_em", "null")
        .execute()
        .data
    )
    if not gravadas:
        raise NaoArquivavelError(MUDOU)


def desarquivar(supabase, conta_id: str, me: dict) -> None:
    """Limpa o carimbo: a conta volta para as Concluídas da Competência dela."""
    conta = _ler(supabase, conta_id)
    if not pode_mexer(conta, me):
        raise SemPermissaoError(DE_OUTRA_DESARQUIVAR)
    if not conta.get("arquivada_em"):
        raise NaoArquivavelError(NAO_ARQUIVADA)
    (
        supabase.table("cm_conta")
        .update({"arquivada_em": None, "arquivada_por": None})
        .eq("id", conta_id)
        .eq("arquivada_em", conta["arquivada_em"])
        .execute()
    )


def arquivar_competencia(supabase, mes: str, me: dict, agora: str) -> dict:
    """ "Arquivar o mês": as Concluídas fora do arquivo daquela Competência, só
    as da pessoa ou todas para quem tem "painel completo". Leva as Concluídas
    com pendência (decisão 9). Devolve quantas arquivou e quantas delas tinham
    pendência."""
    todas = ve_todas(me)

    def consulta():
        q = (
            supabase.table("cm_conta")
            .select("id, situacao, periodo_fim, concluida_em, faturista_id")
            .in_("situacao", list(CONCLUIDAS))
            .is_("arquivada_em", "null")
        )
        if not todas:
            q = q.eq("faturista_id", me.get("id"))
        return q.order("id")

    do_mes = [c["id"] for c in ler_tudo(consulta, rotulo="concluídas do mês") if competencia(c) == mes]
    gravadas: list[dict] = []
    for i in range(0, len(do_mes), LOTE_DE_IDS):
        q = (
            supabase.table("cm_conta")
            .update({"arquivada_em": agora, "arquivada_por": me.get("id")})
            .in_("id", do_mes[i : i + LOTE_DE_IDS])
            .in_("situacao", list(CONCLUIDAS))
            .is_("arquivada_em", "null")
        )
        if not todas:
            q = q.eq("faturista_id", me.get("id"))
        gravadas += q.execute().data or []
    return {
        "arquivadas": len(gravadas),
        "com_pendencia": sum(1 for c in gravadas if c.get("situacao") == COM_PENDENCIA),
    }


def arquivadas_da_pessoa(supabase, me: dict) -> dict:
    """A etapa Arquivadas: as arquivadas de todas, as mais recentes primeiro,
    cada uma com quem está com ela e se é da própria pessoa, como as
    Concluídas."""
    contas = _concluidas(supabase, arquivadas=True)
    for conta in contas:
        conta["com_quem"] = conta.get("faturista_id")
        conta["minha"] = conta.get("faturista_id") == me.get("id")
    _trocar_id_por_nome(supabase, contas)
    return {"todas": ve_todas(me), "arquivadas": contas, "contagem": {"arquivadas": len(contas)}}
