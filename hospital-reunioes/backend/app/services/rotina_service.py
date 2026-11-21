"""A Rotina e a Verificação no banco (ADR 0098, decisão 9; issue #1874).

A regra dos ciclos é pura e mora em `rotina_ciclo`. Aqui: o nascimento da
Rotina no envio da Ata (pela mesma porta que cria as Pendências), a marcação
de uma Verificação e o encerramento. Nenhum job cria Verificação: o ciclo
existe pela data, e a linha só é gravada quando alguém marca.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from app.services.pendencia_service import _e_conflito_unicidade
from app.services.pendencias_consulta import as_data, hoje_em_brasilia
from app.services.quadro_classificacao import ROTINA, frequencia_da_linha, tipo_da_linha
from app.services.rotina_ciclo import (
    Ciclo,
    VerificacaoRecusada,
    ciclos_devidos,
    marcada_com_atraso,
    primeiro_ciclo,
    validar_marcacao,
)

logger = logging.getLogger(__name__)

ATIVA = "ATIVA"
ENCERRADA = "ENCERRADA"


def nascer_rotinas(
    supabase,
    id_reuniao: str,
    quadro_resolvido: list[dict],
    filtro: Callable[[dict], bool] | None = None,
) -> int:
    """Cria uma Rotina por linha do tipo Rotina do quadro já resolvido (com
    `responsavel_id`). Idempotente pela posição no quadro: Reenviar e a
    reconciliação das 5h30 não duplicam. Devolve quantas nasceram."""
    linhas = [
        (posicao, item)
        for posicao, item in enumerate(quadro_resolvido)
        if isinstance(item, dict) and tipo_da_linha(item) == ROTINA and (filtro is None or filtro(item))
    ]
    if not linhas:
        return 0
    existentes = supabase.table("rotinas").select("quadro_pos").eq("id_reuniao", id_reuniao).execute().data or []
    ocupadas = {r.get("quadro_pos") for r in existentes}
    hoje = hoje_em_brasilia()
    criadas = 0
    for posicao, item in linhas:
        if posicao in ocupadas:
            continue
        frequencia = frequencia_da_linha(item)
        rotina = {
            "id_reuniao": id_reuniao,
            "quadro_pos": posicao,
            "descricao": item.get("acao") or item.get("descricao_acao") or "Rotina sem descrição",
            "responsavel_id": item.get("responsavel_id"),
            "responsavel_nome": item.get("responsavel") or "",
            "frequencia": frequencia,
            "comeca_em": primeiro_ciclo(hoje, frequencia).inicio.isoformat() if frequencia else None,
            "status": ATIVA,
        }
        try:
            supabase.table("rotinas").insert(rotina).execute()
            criadas += 1
        except Exception as e:
            # Dois envios ao mesmo tempo: o outro já criou esta Rotina.
            if not _e_conflito_unicidade(e):
                raise
    if criadas:
        logger.info("[Rotina] %s Rotina(s) nasceram da Reunião %s", criadas, id_reuniao)
    return criadas


# ─── O que é devido, o que foi marcado ───────────────────────────────────────


def devidos(rotina: dict, hoje: date) -> list[Ciclo]:
    """Os ciclos que existem pela data para esta Rotina. Sem frequência (o
    fluxo contínuo antigo ainda não acertado), nenhum."""
    frequencia = rotina.get("frequencia")
    comeca_em = as_data(rotina.get("comeca_em"))
    if not frequencia or comeca_em is None:
        return []
    return ciclos_devidos(comeca_em, frequencia, hoje=hoje, encerrada_em=as_data(rotina.get("encerrada_em")))


def verificacoes_de(supabase, ids: list[str]) -> dict[str, list[dict]]:
    """As Verificações gravadas, por Rotina."""
    if not ids:
        return {}
    linhas = supabase.table("rotina_verificacoes").select("*").in_("rotina_id", ids).execute().data or []
    por_rotina: dict[str, list[dict]] = {}
    for linha in linhas:
        por_rotina.setdefault(linha["rotina_id"], []).append(linha)
    return por_rotina


def ciclos_em_aberto(rotina: dict, marcadas: list[dict], hoje: date) -> list[Ciclo]:
    """Os ciclos devidos que ninguém marcou, do mais antigo ao de hoje."""
    feitos = {str(v.get("ciclo_inicio"))[:10] for v in marcadas}
    return [c for c in devidos(rotina, hoje) if c.inicio.isoformat() not in feitos]


# ─── Marcar e encerrar ───────────────────────────────────────────────────────


class CicloInexistente(ValueError):  # noqa: N818, o nome do domínio
    """O ciclo pedido não existe pela data para esta Rotina."""


class JaMarcada(ValueError):  # noqa: N818, o nome do domínio
    """O ciclo já tem Verificação."""


class JaEncerrada(ValueError):  # noqa: N818, o nome do domínio
    """A Rotina já foi encerrada."""


def marcar(
    supabase,
    rotina: dict,
    ciclo_inicio: date,
    resultado: str,
    anotacao: str | None,
    *,
    autor_id: str | None,
    autor_nome: str,
) -> dict:
    """Grava a Verificação de um ciclo devido. Marcada depois do último dia do
    ciclo, fica registrada como atrasada."""
    texto = validar_marcacao(resultado, anotacao)
    hoje = hoje_em_brasilia()
    ciclo = next((c for c in devidos(rotina, hoje) if c.inicio == ciclo_inicio), None)
    if ciclo is None:
        raise CicloInexistente("Esse ciclo não existe para esta Rotina, ou ainda não começou.")
    ja = (
        supabase.table("rotina_verificacoes")
        .select("id")
        .eq("rotina_id", rotina["id"])
        .eq("ciclo_inicio", ciclo.inicio.isoformat())
        .execute()
        .data
    )
    if ja:
        raise JaMarcada("Esse ciclo já foi marcado.")
    verificacao = {
        "rotina_id": rotina["id"],
        "ciclo_inicio": ciclo.inicio.isoformat(),
        "ciclo_fim": ciclo.fim.isoformat(),
        "resultado": resultado,
        "anotacao": texto,
        "atrasada": marcada_com_atraso(ciclo, hoje),
        "marcada_por_id": autor_id,
        "marcada_por_nome": autor_nome,
    }
    try:
        gravada = supabase.table("rotina_verificacoes").insert(verificacao).execute().data or [verificacao]
    except Exception as e:
        if _e_conflito_unicidade(e):
            raise JaMarcada("Esse ciclo já foi marcado.") from e
        raise
    return gravada[0]


def encerrar(supabase, rotina: dict, anotacao: str | None, *, autor_id: str | None, autor_nome: str) -> dict:
    """Encerra a Rotina com anotação: o ciclo em curso e os seguintes deixam
    de existir. Os que já fecharam continuam devidos."""
    texto = (anotacao or "").strip()
    if not texto:
        raise VerificacaoRecusada("Encerrar a Rotina pede uma anotação dizendo por quê.")
    if rotina.get("status") == ENCERRADA:
        raise JaEncerrada("Esta Rotina já foi encerrada.")
    mudanca = {
        "status": ENCERRADA,
        "encerrada_em": hoje_em_brasilia().isoformat(),
        "encerrada_por_id": autor_id,
        "encerrada_por_nome": autor_nome,
        "anotacao_encerramento": texto,
    }
    # Só encerra a que ainda está ativa: dois cliques não sobrescrevem a anotação.
    gravada = supabase.table("rotinas").update(mudanca).eq("id", rotina["id"]).eq("status", ATIVA).execute().data
    if not gravada:
        raise JaEncerrada("Esta Rotina já foi encerrada.")
    return gravada[0]
