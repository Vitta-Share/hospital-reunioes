"""A Pergunta da Vitta (issue #2116, PRD #2112, ADR 0109, decisoes 1 e 3).

A pergunta que a Vitta manda a alguem do Hospital, pela ponte de automacao,
vira um registro do app ligado a uma Demanda: Destinatario, Assunto, o texto,
as quatro linhas do cartao (por que precisa da pessoa, o que esta parado, o
que anda depois e o ganho), as opcoes com a recomendada e o porque, e o
estado. Nasce aberta.

Todas as regras da Pergunta moram aqui (criar, e nas proximas Fatias
responder, resolver, cancelar, listar e lembrar); as rotas nao repetem regra.

Criar grava a entrada da Pergunta na Conversa da Demanda, pelo mesmo servico
das mensagens (`tecnologia_conversa.escrever`), que avisa so o Destinatario
com "Pede sua resposta" e o Assunto (ADR 0106). Depois vem a linha de sistema
"Pergunta aberta", pela mesma origem `sistema` da linha do Envio aos
desenvolvedores (ADR 0108).

O nome e Pergunta da Vitta, nunca Pendencia (ADR 0109, decisao 2): Pendencia e
a Acao da Ata.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.services import tecnologia_conversa
from app.services.tecnologia import TABELA_CONVERSA_DA_DEMANDA

TABELA_PERGUNTAS = "tecnologia_perguntas"

# Os estados da Pergunta (CHECK da migration 211, ADR 0109, decisao 1).
ESTADO_ABERTA = "aberta"

# A origem da linha de sistema na Conversa (CHECK da migration 165): a mesma
# da linha do Envio aos desenvolvedores, para a tela mostrar do mesmo jeito.
ORIGEM_SISTEMA = "sistema"

# As quatro linhas do cartao, com o nome que o motivo da recusa usa.
LINHAS_DO_CARTAO: tuple[tuple[str, str], ...] = (
    ("por_que_precisa", "por que precisa da pessoa"),
    ("o_que_esta_parado", "o que está parado"),
    ("o_que_anda_depois", "o que anda depois"),
    ("ganho", "o ganho"),
)

# As letras das opcoes, na ordem em que chegam. Quatro no maximo.
LETRAS = ("A", "B", "C", "D")

MOTIVO_DESTINATARIO = "O Destinatário não é um participante ativo do aplicativo."
MOTIVO_SEM_ASSUNTO = "Falta o Assunto da Pergunta."
MOTIVO_SEM_TEXTO = "Falta o texto da Pergunta."
MOTIVO_OPCOES = "A Pergunta com opções precisa de duas a quatro, todas com texto."
MOTIVO_RECOMENDADA = "A recomendada precisa ser a letra de uma das opções."


class PerguntaRecusadaError(ValueError):
    """A Pergunta nao pode nascer assim. A mensagem e o motivo, para a ponte
    devolver como esta; nada foi gravado."""


def _limpo(valor: str | None) -> str:
    return (valor or "").strip()


def _opcoes(opcoes: Sequence[str], recomendada: str | None) -> list[dict[str, str]]:
    textos = [_limpo(texto) for texto in opcoes]
    if not textos:
        if recomendada:
            raise PerguntaRecusadaError(MOTIVO_RECOMENDADA)
        return []
    if not 2 <= len(textos) <= len(LETRAS) or not all(textos):
        raise PerguntaRecusadaError(MOTIVO_OPCOES)
    letras = LETRAS[: len(textos)]
    if recomendada not in letras:
        raise PerguntaRecusadaError(MOTIVO_RECOMENDADA)
    return [{"letra": letra, "texto": texto} for letra, texto in zip(letras, textos, strict=True)]


def criar(
    supabase,
    demanda: dict[str, Any],
    *,
    autor: dict[str, Any],
    destinatario_id: str | None,
    assunto: str | None,
    texto: str | None,
    linhas: dict[str, str | None],
    opcoes: Sequence[str] = (),
    recomendada: str | None = None,
    porque: str | None = None,
) -> dict[str, Any]:
    """Grava a Pergunta aberta, a entrada dela na Conversa da Demanda e a
    linha de sistema "Pergunta aberta", e avisa so o Destinatario. Devolve a
    linha da Pergunta. Tudo e conferido antes da primeira escrita: a recusa
    (`PerguntaRecusadaError`) nao deixa nada gravado nem avisado."""
    assunto, texto = _limpo(assunto), _limpo(texto)
    if not assunto:
        raise PerguntaRecusadaError(MOTIVO_SEM_ASSUNTO)
    if not texto:
        raise PerguntaRecusadaError(MOTIVO_SEM_TEXTO)
    cartao = {chave: _limpo(linhas.get(chave)) for chave, _ in LINHAS_DO_CARTAO}
    for chave, nome in LINHAS_DO_CARTAO:
        if not cartao[chave]:
            raise PerguntaRecusadaError(f"Falta a linha do cartão: {nome}.")
    lista = _opcoes(opcoes, recomendada)
    if not destinatario_id or not tecnologia_conversa.e_participante_ativo(supabase, destinatario_id):
        raise PerguntaRecusadaError(MOTIVO_DESTINATARIO)

    entrada = tecnologia_conversa.escrever(
        supabase,
        demanda,
        autor=autor,
        texto=texto,
        origem=tecnologia_conversa.ORIGEM_TERMINAL,
        destinatario_id=destinatario_id,
        pede_resposta_sobre=assunto,
    )
    [pergunta] = (
        supabase.table(TABELA_PERGUNTAS)
        .insert(
            {
                "demanda_id": demanda["id"],
                "mensagem_id": entrada["id"],
                "autor_id": autor["id"],
                "destinatario_id": destinatario_id,
                "assunto": assunto,
                "texto": texto,
                **cartao,
                "opcoes": lista,
                "recomendada": recomendada if lista else None,
                "porque_da_recomendada": (_limpo(porque) or None) if lista else None,
                "estado": ESTADO_ABERTA,
            }
        )
        .execute()
        .data
    )
    supabase.table(TABELA_CONVERSA_DA_DEMANDA).insert(
        {
            "demanda_id": demanda["id"],
            "autor_id": autor["id"],
            "texto": f"Pergunta aberta: {assunto}",
            "mencoes": [],
            "origem": ORIGEM_SISTEMA,
        }
    ).execute()
    return pergunta
