"""Encaminhar da tela de triagem (issue #1995, PRD #1979, ADR 0095 decisão 11
e ADR 0107 decisão 8).

A Presidência manda o caso a um ou mais destinos, com o motivo em uma frase,
e o protocolo do Núcleo fica como está:

- **Núcleo**: o caso continua na triagem do Núcleo, junto do outro destino;
- **Ouvidoria**: um e-mail ao ouvidor, pelo registro de e-mail do Núcleo, com
  o protocolo, o motivo e o relato. A criação automática da manifestação é da
  Fase 4;
- **Canal de Conduta**: só a orientação na tela. Nada é enviado e nada do
  caso é gravado fora do Núcleo, nem link (ADR 0095, decisão 11);
- **Fora de escopo**: encerra o caso com a orientação de uma frase, que quem
  notificou vê na página de acompanhamento. Não se soma a outro destino.

Sem o Núcleo entre os destinos, o caso sai da fila: vai a Encaminhada, ou a
Fora de escopo.
"""

from __future__ import annotations

from typing import Any

from app.services.seguranca_do_paciente.triagem import (
    ESTADOS_DA_FILA,
    CasoNaoEncontradoError,
    JaConfirmadaError,
    TriagemRecusadaError,
)

NUCLEO = "nucleo"
OUVIDORIA = "ouvidoria"
CANAL_DE_CONDUTA = "canal_de_conduta"
FORA_DE_ESCOPO = "fora_de_escopo"
DESTINOS = (NUCLEO, OUVIDORIA, CANAL_DE_CONDUTA, FORA_DE_ESCOPO)

ENCAMINHADA = "encaminhada"
ESTADO_FORA_DE_ESCOPO = "fora_de_escopo"

TAMANHO_DA_FRASE = 300


class EncaminhamentoInvalidoError(TriagemRecusadaError):
    pass


def _frase(valor: str | None, recusa: str) -> str:
    texto = " ".join((valor or "").split())
    if not texto:
        raise EncaminhamentoInvalidoError(recusa)
    if len(texto) > TAMANHO_DA_FRASE:
        raise EncaminhamentoInvalidoError(f"Escreva em uma frase, até {TAMANHO_DA_FRASE} caracteres.")
    return texto


def _destinos(destinos: list[str]) -> list[str]:
    escolhidos = list(dict.fromkeys(destinos or []))
    if not escolhidos:
        raise EncaminhamentoInvalidoError("Escolha ao menos um destino.")
    if any(destino not in DESTINOS for destino in escolhidos):
        raise EncaminhamentoInvalidoError("Escolha o destino na lista.")
    return escolhidos


def estado_depois_do_encaminhamento(destinos: list[str]) -> str | None:
    """None quando o Núcleo fica com o caso: ele continua na triagem."""
    if NUCLEO in destinos:
        return None
    return ESTADO_FORA_DE_ESCOPO if FORA_DE_ESCOPO in destinos else ENCAMINHADA


def _notificacao(supabase, notificacao_id: str) -> dict[str, Any] | None:
    linhas = (
        supabase.table("nsp_notificacoes")
        .select("id, protocolo, estado, relato")
        .eq("id", notificacao_id)
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


def encaminhar_da_triagem(
    supabase,
    notificacao_id: str,
    *,
    autor_id: str,
    destinos: list[str],
    motivo: str | None,
) -> dict[str, Any]:
    """Grava o encaminhamento e leva o caso ao estado que os destinos pedem.
    Devolve o estado do caso e o encaminhamento gravado."""
    escolhidos = _destinos(destinos)
    motivo = _frase(motivo, "Escreva o motivo do encaminhamento em uma frase.")
    notificacao = _notificacao(supabase, notificacao_id)
    if notificacao is None:
        raise CasoNaoEncontradoError("Caso não encontrado.")
    if notificacao.get("estado") not in ESTADOS_DA_FILA:
        raise JaConfirmadaError("Este caso já saiu da triagem.")
    gravado = (
        supabase.table("nsp_encaminhamentos")
        .insert(
            {
                "notificacao_id": notificacao_id,
                "destinos": escolhidos,
                "motivo": motivo,
                "autor_id": autor_id,
            }
        )
        .execute()
        .data[0]
    )
    estado = estado_depois_do_encaminhamento(escolhidos)
    if estado is not None:
        supabase.table("nsp_notificacoes").update({"estado": estado, "editado_por": autor_id}).eq(
            "id", notificacao_id
        ).in_("estado", list(ESTADOS_DA_FILA)).execute()
    return {"estado": estado or notificacao["estado"], "encaminhamento": gravado}
