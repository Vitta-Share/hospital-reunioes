"""O Me explique da Pergunta da Vitta (issue #2122, PRD #2112, ADR 0109, decisao 8).

O botao do cartao abre o Assistente de Tecnologia em particular: uma conversa
por Pergunta e por pessoa (`tecnologia_conversas_do_me_explique`, migration
211), que ja comeca com a Demanda e a Pergunta no contexto. O Assistente
explica na lingua do Kit e propoe um rascunho de resposta.

Nada daqui entra na Conversa da Demanda, cria resposta ou vai ao GitHub: o
rascunho so vai para o campo do cartao com o clique da pessoa, e quem responde
e a rota da resposta, pelo clique de enviar. A IA so roda pelo clique (o botao
ou a pergunta da pessoa), nunca por job.

A chamada passa pela mesma porta do chat (`planejamento_demanda.chamar_o_modelo`):
o modelo padrao do Assistente (ADR 0103), as ferramentas de leitura dele e o
custo gravado na conta da Demanda, como um turno do Assistente.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.services import ai_processor, ferramentas_do_codigo, planejamento_demanda
from app.services.tecnologia import nome_do_projeto, recuar_continuacao
from app.utils.text_sanitizer import sanitizar_travessao

logger = logging.getLogger(__name__)

TABELA = "tecnologia_conversas_do_me_explique"
PROMPT = "me_explique_system"

# O CHECK de `tecnologia_chamadas_ia.passo` (migration 165) conhece pergunta,
# resumo e envio. O Me explique e um turno do Assistente, como o do chat.
PASSO_DO_CUSTO = "pergunta"

PAPEL_PESSOA = "pessoa"
PAPEL_ASSISTENTE = "assistente"

LIMITE_DA_FALA = 4000

MOTIVO_FALHOU = "O assistente não conseguiu responder agora. Tente de novo."

FALA_MOCK = {"mensagem": "[MOCK] O Me explique exige a IA configurada.", "rascunho": None}


class _Saida(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mensagem: str
    rascunho: str | None = None

    @field_validator("mensagem")
    @classmethod
    def _com_texto(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("fala sem texto")
        return valor


# ─── Sem jargao do repositorio ──────────────────────────────────────────────
#
# O Assistente le o codigo e as issues pelas ferramentas, e a fala dele vai a
# quem nao e da Vitta. O prompt proibe numero de issue, label e nome de tabela;
# isto garante: o que escapar sai da fala antes de gravar.

_NUMERO_DE_ISSUE = re.compile(r"\s*\(?#\d+\)?")
_LABEL = re.compile(
    r"\s*\b(?:ready-for-agent|ready-for-human|needs-triage|needs-info|in-progress|wontfix|fatia:[a-z]+)\b",
    re.IGNORECASE,
)
_NOME_DE_TABELA = re.compile(r"\s*\b[a-z0-9]+(?:_[a-z0-9]+)+\b")
_ESPACO_ANTES_DA_PONTUACAO = re.compile(r"[ \t]+([.,;:!?)])")
_ESPACOS = re.compile(r"[ \t]{2,}")


def sem_jargao(texto: str) -> str:
    """A fala sem numero de issue, label nem nome de tabela, e sem travessao."""
    limpo = (texto or "").replace("`", "")
    for padrao in (_NUMERO_DE_ISSUE, _LABEL, _NOME_DE_TABELA):
        limpo = padrao.sub("", limpo)
    limpo = _ESPACOS.sub(" ", _ESPACO_ANTES_DA_PONTUACAO.sub(r"\1", limpo))
    return sanitizar_travessao(limpo.strip())


# ─── A conversa guardada ─────────────────────────────────────────────────────


def _linha(supabase, pergunta_id: str, participante_id: str) -> dict[str, Any] | None:
    linhas = (
        supabase.table(TABELA)
        .select("*")
        .eq("pergunta_id", pergunta_id)
        .eq("participante_id", participante_id)
        .execute()
        .data
        or []
    )
    return linhas[0] if linhas else None


def ler(supabase, pergunta_id: str, participante_id: str) -> list[dict[str, Any]]:
    """A conversa de `participante_id` sobre a Pergunta. So a dele: a de outra
    pessoa nunca sai daqui."""
    linha = _linha(supabase, pergunta_id, participante_id)
    return list((linha or {}).get("mensagens") or [])


def _gravar(supabase, pergunta_id: str, participante_id: str, mensagens: list[dict[str, Any]]) -> None:
    agora = datetime.now(UTC).isoformat()
    if _linha(supabase, pergunta_id, participante_id) is None:
        supabase.table(TABELA).insert(
            {"pergunta_id": pergunta_id, "participante_id": participante_id, "mensagens": mensagens}
        ).execute()
        return
    (
        supabase.table(TABELA)
        .update({"mensagens": mensagens, "atualizado_em": agora})
        .eq("pergunta_id", pergunta_id)
        .eq("participante_id", participante_id)
        .execute()
    )


# ─── O pedido ao modelo ──────────────────────────────────────────────────────


def pedido(demanda: dict[str, Any], pergunta: dict[str, Any], mensagens: list[dict[str, Any]]) -> str:
    """A Demanda, a Pergunta e a conversa ate aqui. Texto de gente entra
    recuado: nenhuma linha dele chega a coluna zero. O numero do card fica de
    fora: a fala e para quem nao e da Vitta."""
    opcoes = pergunta.get("opcoes") or []
    linhas_das_opcoes = [recuar_continuacao(f"{o.get('letra')}) {o.get('texto') or ''}") for o in opcoes] or [
        "(sem opções prontas: a resposta é livre)"
    ]
    if opcoes and pergunta.get("recomendada"):
        linhas_das_opcoes.append(
            recuar_continuacao(
                f"Recomendada: {pergunta['recomendada']}, porque {pergunta.get('porque_da_recomendada') or ''}"
            )
        )
    conversa = [
        recuar_continuacao(f"{'Pessoa' if m.get('papel') == PAPEL_PESSOA else 'Assistente'}: {m.get('texto') or ''}")
        for m in mensagens
    ] or ["(a conversa começa agora: explique a Demanda e a Pergunta e proponha um rascunho)"]
    return "\n".join(
        [
            "PEDIDO: ME EXPLIQUE",
            "",
            "A DEMANDA",
            recuar_continuacao(f"Projeto: {nome_do_projeto(demanda)}"),
            recuar_continuacao(f"Título: {demanda.get('titulo') or ''}"),
            recuar_continuacao(f"O que muda: {demanda.get('o_que_muda') or '(sem texto)'}"),
            "",
            "A PERGUNTA DA VITTA",
            recuar_continuacao(f"Assunto: {pergunta.get('assunto') or ''}"),
            recuar_continuacao(f"Pergunta: {pergunta.get('texto') or ''}"),
            recuar_continuacao(f"Por que precisa da pessoa: {pergunta.get('por_que_precisa') or ''}"),
            recuar_continuacao(f"O que está parado: {pergunta.get('o_que_esta_parado') or ''}"),
            recuar_continuacao(f"O que anda depois: {pergunta.get('o_que_anda_depois') or ''}"),
            recuar_continuacao(f"O que o hospital ganha: {pergunta.get('ganho') or ''}"),
            "Opções:",
            *linhas_das_opcoes,
            "",
            "A CONVERSA ATÉ AQUI",
            *conversa,
        ]
    )


def _fala_do_modelo(demanda: dict[str, Any], conteudo: str, *, kit: str, supabase) -> _Saida | None:
    if ai_processor._llm_provider() == "mock":
        logger.warning("Modo MOCK ativo para o Me explique (sem chave LLM)")
        return _Saida.model_validate(FALA_MOCK)
    saida, chamada = planejamento_demanda.chamar_o_modelo(
        demanda=demanda,
        passo=PASSO_DO_CUSTO,
        conteudo=conteudo,
        kit=kit,
        validar=_Saida.model_validate,
        prompt=PROMPT,
        consultas=ferramentas_do_codigo.Consultas(),
    )
    planejamento_demanda.gravar_chamada(supabase, chamada)
    return saida


def conversar(
    supabase,
    pergunta: dict[str, Any],
    demanda: dict[str, Any],
    *,
    ator: dict[str, Any],
    texto: str | None,
    kit: str,
) -> list[dict[str, Any]] | None:
    """Um turno do Me explique de `ator`. Sem `texto`, abre: a conversa que ja
    existe volta como esta, sem chamar a IA, e a nova comeca com a explicacao.
    Com `texto`, a pergunta da pessoa entra e a fala do Assistente volta.

    Devolve a conversa inteira, ou `None` quando o modelo falhou (nada e
    gravado; a chamada fica na conta do mesmo jeito)."""
    pergunta_id, participante_id = str(pergunta["id"]), str(ator["id"])
    mensagens = ler(supabase, pergunta_id, participante_id)
    texto = (texto or "").strip()
    if not texto and mensagens:
        return mensagens
    if texto:
        mensagens.append({"papel": PAPEL_PESSOA, "texto": texto, "rascunho": None})

    saida = _fala_do_modelo(demanda, pedido(demanda, pergunta, mensagens), kit=kit, supabase=supabase)
    if saida is None:
        return None
    rascunho = sem_jargao(saida.rascunho or "")[:LIMITE_DA_FALA] or None
    mensagens.append(
        {"papel": PAPEL_ASSISTENTE, "texto": sem_jargao(saida.mensagem)[:LIMITE_DA_FALA], "rascunho": rascunho}
    )
    _gravar(supabase, pergunta_id, participante_id, mensagens)
    return mensagens
