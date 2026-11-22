"""A aprovação em lote das faixas D e E (issue #2002, PRD #1979, ADR 0107
decisão 10; Anexo F, seção 5, item 13).

Nasce desligada. Liga quando a Diretoria conclui a pendência de recalibração
com a decisão "ligar a aprovação em lote" (a conferência dos 90% é da
recalibração, na hora da decisão). Ligada, a Presidência confirma de uma vez
vários casos sugeridos nas faixas D e E, cada um com a própria linha de
triagem e os próprios prazos, pelo mesmo caminho da confirmação de um caso.

O pedido é conferido inteiro antes de gravar: um caso fora do lote recusa o
pedido todo, e nada é gravado.
"""

from __future__ import annotations

from typing import Any

from app.services.seguranca_do_paciente import triagem

TABELA_DAS_RECALIBRACOES = "nsp_recalibracoes"
DECISAO_QUE_LIGA = "ligar_lote"

# O teto de um pedido: um lote de ids na leitura.
TAMANHO_MAXIMO = triagem.LOTE_DE_IDS


class LoteDesligadoError(triagem.TriagemRecusadaError):
    pass


class ForaDoLoteError(triagem.TriagemRecusadaError):
    pass


def ligado(supabase) -> bool:
    """Ligado quando alguma recalibração foi concluída com "ligar a aprovação
    em lote"."""
    linhas = (
        supabase.table(TABELA_DAS_RECALIBRACOES).select("marco").eq("decisao", DECISAO_QUE_LIGA).limit(1).execute().data
    )
    return bool(linhas)


def _notificacoes(supabase, ids: list[str]) -> dict[str, dict[str, Any]]:
    casos: dict[str, dict[str, Any]] = {}
    for inicio in range(0, len(ids), triagem.LOTE_DE_IDS):
        lote = ids[inicio : inicio + triagem.LOTE_DE_IDS]
        consulta = supabase.table("nsp_notificacoes").select("id, protocolo, estado, relato, grave_ou_morte")
        for linha in consulta.in_("id", lote).execute().data or []:
            casos[linha["id"]] = linha
    return casos


def confirmar(supabase, ids: list[str], *, autor_id: str) -> list[dict[str, Any]]:
    """Confirma a sugestão de cada caso como veio. Devolve o id e o estado novo
    de cada um, na ordem do pedido."""
    if not ligado(supabase):
        raise LoteDesligadoError("A aprovação em lote está desligada. Confirme cada caso na tela dele.")
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise ForaDoLoteError("Marque ao menos um caso para confirmar em lote.")
    if len(ids) > TAMANHO_MAXIMO:
        raise ForaDoLoteError(f"Confirme no máximo {TAMANHO_MAXIMO} casos de cada vez.")
    casos = _notificacoes(supabase, ids)
    if len(casos) < len(ids):
        raise triagem.CasoNaoEncontradoError("Caso não encontrado. Atualize a fila e marque de novo.")
    triagens = triagem._triagens_por_notificacao(supabase, ids)
    ja_confirmados, fora = [], []
    for notificacao_id in ids:
        caso, linhas = casos[notificacao_id], triagens.get(notificacao_id, [])
        if caso.get("estado") not in triagem.ESTADOS_DA_FILA:
            ja_confirmados.append(caso["protocolo"])
        elif not triagem.cabe_no_lote(caso, triagem._sugestao(linhas)):
            fora.append(caso["protocolo"])
    if ja_confirmados:
        raise triagem.JaConfirmadaError(
            f"A triagem já foi confirmada: {', '.join(ja_confirmados)}. Atualize a fila e marque de novo."
        )
    if fora:
        raise ForaDoLoteError(
            "O lote aceita só casos das faixas D e E que não pedem conferência campo a campo. "
            f"Confirme na tela de cada um: {', '.join(fora)}."
        )
    confirmados = []
    for notificacao_id in ids:
        feita = triagem.decidir(supabase, notificacao_id, autor_id=autor_id, classificacao=None, conferidos=[])
        confirmados.append({"id": notificacao_id, "estado": feita["estado"]})
    return confirmados
