"""A tela de triagem do Núcleo (issue #1992, PRD #1979, ADR 0095 e 0107).

O agente sugere (`agente_de_triagem`) e a Presidência decide aqui. Três peças:

- a fila: as notificações sem triagem confirmada, da mais antiga para a mais
  nova, com a faixa e o assunto sugeridos. Nada do relato nem de quem
  notificou: o assunto do agente já sai sem nome de pessoa;
- a tela de um caso: a notificação, a sugestão (ou nenhuma, quando ficou para
  classificar manualmente), a regra de conferência e o que o sistema calcula
  (recorrência, casos parecidos, frequência e prioridade pela matriz do Anexo
  A, seção 7.2);
- a decisão: confirmar a sugestão como veio, ou ajustar. Grava a linha da
  pessoa em `nsp_triagens` ao lado da sugestão, que fica como está, com as
  divergências campo a campo, e leva o caso a Classificada, ou a Em análise
  agregada na faixa E e na D sem dano.

Nas faixas A e B, com menção a morte, com evento da lista "possível" ou quando
quem notificou marcou grave e o agente sugeriu menos, confirmar exige cada
campo conferido: não existe "aceitar tudo". O banco guarda uma decisão de
pessoa por notificação (migration 189).
"""

from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from postgrest.exceptions import APIError

from app.services.seguranca_do_paciente import notificacoes
from app.services.seguranca_do_paciente.triagem_do_agente import (
    CANAIS,
    CATEGORIAS,
    GRAUS_DE_DANO,
    ITENS_DA_LISTA,
    NATUREZAS,
    PROTOCOLOS_BASICOS,
    SITUACOES_DA_LISTA,
    faixa_esperada,
    menciona_morte,
)

LOTE_DE_IDS = notificacoes.LOTE_DE_IDS
TAMANHO_DA_PAGINA = notificacoes.TAMANHO_DA_PAGINA

ESTADOS_DA_FILA = ("recebida", "em_triagem")
CLASSIFICADA = "classificada"
EM_ANALISE_AGREGADA = "em_analise_agregada"

# Os campos que a Presidência confere um a um quando a revisão é campo a campo.
CAMPOS_DA_CONFERENCIA = (
    "assunto",
    "natureza",
    "grau_de_dano",
    "categoria",
    "incidente",
    "evento",
    "iras",
    "risco_de_imagem",
    "protocolo_basico",
    "canais",
    "faixa",
)

# Por que a revisão é campo a campo.
MOTIVO_FAIXA = "faixa"
MOTIVO_MORTE = "morte"
MOTIVO_EVENTO_POSSIVEL = "evento_possivel"
MOTIVO_GRAVE_MARCADO = "grave_marcado"
MOTIVO_AGENTE = "agente"

# A recorrência da tela: "3ª ocorrência desta categoria neste setor em 60 dias".
JANELA_DA_RECORRENCIA_DIAS = 60

# Os cortes de frequência (Configuração), com a sugestão da issue #2005 como
# padrão: em 12 meses, nenhuma anterior = remoto, 1 = incomum, 2 ou 3 =
# ocasional, 4 ou mais = frequente.
CORTES_PADRAO = {"janela_meses": 12, "incomum_a_partir": 1, "ocasional_a_partir": 2, "frequente_a_partir": 4}
_CAMPOS_DOS_CORTES = tuple(CORTES_PADRAO)

# A matriz de prioridade do Anexo A, seção 7.2: gravidade por frequência.
_MATRIZ = {
    "frequente": {"catastrofico": "alta", "grave": "alta", "moderado": "moderada", "leve": "baixa"},
    "ocasional": {"catastrofico": "alta", "grave": "moderada", "moderado": "baixa", "leve": "baixa"},
    "incomum": {"catastrofico": "alta", "grave": "moderada", "moderado": "baixa", "leve": "baixa"},
    "remoto": {"catastrofico": "alta", "grave": "moderada", "moderado": "baixa", "leve": "baixa"},
}
# A gravidade da matriz pela faixa: A é óbito ou evento que nunca deveria
# ocorrer (catastrófico), B dano grave, C moderado, D e E leve ou sem dano.
_GRAVIDADE_DA_FAIXA = {"A": "catastrofico", "B": "grave", "C": "moderado", "D": "leve", "E": "leve"}

_SEM_DANO = ("circunstancia_de_risco", "quase_erro", "incidente_sem_dano")
_DANO_DE_EVENTO_ADVERSO = ("leve", "moderado", "grave", "obito")
_TAMANHO_DO_ASSUNTO = 300


class TriagemIndisponivel(Exception):
    """A decisão não pode ser gravada; a mensagem vai para a tela."""


class NaoEncontrada(TriagemIndisponivel):
    pass


class JaConfirmada(TriagemIndisponivel):
    pass


class ConferenciaIncompleta(TriagemIndisponivel):
    pass


class ClassificacaoInvalida(TriagemIndisponivel):
    pass


# ═══════════════════════════════════════════════════════════════════════════
# Leituras
# ═══════════════════════════════════════════════════════════════════════════


def _paginas(consulta: Callable[[], Any]) -> list[dict[str, Any]]:
    """Toda linha da consulta, página a página, abaixo do teto do PostgREST.
    O id descarta a repetição de uma linha que mudou de lugar no meio."""
    linhas: list[dict[str, Any]] = []
    vistas: set[str] = set()
    inicio = 0
    while True:
        pagina = consulta().range(inicio, inicio + TAMANHO_DA_PAGINA - 1).execute().data or []
        for linha in pagina:
            if linha["id"] not in vistas:
                vistas.add(linha["id"])
                linhas.append(linha)
        if len(pagina) < TAMANHO_DA_PAGINA:
            return linhas
        inicio += TAMANHO_DA_PAGINA


def _triagens_por_notificacao(supabase, notificacao_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """As linhas de triagem de cada notificação, lidas em lotes de ids."""
    por_notificacao: dict[str, list[dict[str, Any]]] = {}
    for inicio in range(0, len(notificacao_ids), LOTE_DE_IDS):
        lote = notificacao_ids[inicio : inicio + LOTE_DE_IDS]
        for linha in supabase.table("nsp_triagens").select("*").in_("notificacao_id", lote).execute().data or []:
            por_notificacao.setdefault(linha["notificacao_id"], []).append(linha)
    return por_notificacao


def _sugestao(linhas: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A última rodada do agente."""
    do_agente = [linha for linha in linhas if linha.get("autor_tipo") == "agente"]
    return max(do_agente, key=lambda linha: linha["versao"]) if do_agente else None


def _decisao(linhas: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A linha da pessoa: a triagem confirmada."""
    return next((linha for linha in linhas if linha.get("autor_tipo") == "pessoa"), None)


def _vigente(linhas: list[dict[str, Any]]) -> dict[str, Any] | None:
    """O que vale para o caso: a decisão, ou a sugestão enquanto não há decisão."""
    return _decisao(linhas) or _sugestao(linhas)


def _nomes_dos_setores(supabase, setor_ids: set[str]) -> dict[str, str]:
    if not setor_ids:
        return {}
    linhas = supabase.table("setores").select("id, nome").in_("id", sorted(setor_ids)).execute().data or []
    return {linha["id"]: linha["nome"] for linha in linhas}


# ═══════════════════════════════════════════════════════════════════════════
# A fila
# ═══════════════════════════════════════════════════════════════════════════

_CAMPOS_DA_FILA = (
    "id, protocolo, numero, criado_em, setor_id, data_ocorrencia, grave_ou_morte, "
    "classificar_manualmente, motivo_classificar_manualmente"
)


def fila(supabase) -> list[dict[str, Any]]:
    """As notificações sem triagem confirmada, da mais antiga para a mais nova.
    Sem relato e sem quem notificou: a fila mostra o protocolo, o setor, a data,
    a faixa e o assunto sugeridos."""
    linhas = _paginas(
        lambda: supabase.table("nsp_notificacoes")
        .select(_CAMPOS_DA_FILA)
        .in_("estado", list(ESTADOS_DA_FILA))
        .order("criado_em")
    )
    linhas.sort(key=lambda linha: (str(linha.get("criado_em")), linha.get("numero") or 0))
    triagens = _triagens_por_notificacao(supabase, [linha["id"] for linha in linhas])
    setores = _nomes_dos_setores(supabase, {linha["setor_id"] for linha in linhas if linha.get("setor_id")})
    itens = []
    for linha in linhas:
        das_linhas = triagens.get(linha["id"], [])
        if _decisao(das_linhas):
            continue
        sugestao = _sugestao(das_linhas)
        itens.append(
            {
                "id": linha["id"],
                "protocolo": linha["protocolo"],
                "criado_em": linha.get("criado_em"),
                "data_ocorrencia": linha.get("data_ocorrencia"),
                "setor": setores.get(linha.get("setor_id")),
                "grave_ou_morte": linha.get("grave_ou_morte"),
                "faixa": sugestao["faixa"] if sugestao else None,
                "assunto": sugestao["assunto"] if sugestao else None,
                "classificar_manualmente": bool(linha.get("classificar_manualmente")),
            }
        )
    return itens
