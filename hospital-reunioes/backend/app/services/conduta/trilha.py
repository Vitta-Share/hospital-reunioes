"""A trilha do caso do Canal de Conduta, em cadeia (ADR 0097, decisão 9).

Cada linha guarda quem (autor), quando (registrado_em) e o quê (ação e
detalhe), e um código que cobre esses campos mais o código da linha anterior
do mesmo caso. Quem tem o banco e troca ou apaga uma linha quebra a cadeia, e
`linhas_adulteradas` aponta onde.

O código é calculado aqui, e o banco (migration 175) garante o resto: recusa
UPDATE, DELETE e TRUNCATE, e recusa a linha que não aponta para a última do
caso. Duas gravações simultâneas no mesmo caso: a segunda é recusada pelo
banco, e `registrar` lê a última de novo e refaz.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from postgrest.exceptions import APIError

logger = logging.getLogger(__name__)

_TENTATIVAS = 3


def _data_canonica(valor: str) -> str:
    """A mesma data, escrita sempre do mesmo jeito: em UTC, com microssegundos.
    O PostgREST devolve no fuso do banco e corta os zeros."""
    return datetime.fromisoformat(valor).astimezone(UTC).isoformat(timespec="microseconds")


def codigo_da_linha(linha: dict[str, Any], anterior: str | None) -> str:
    conteudo = [
        anterior or "",
        str(linha["caso_id"]),
        linha.get("autor_id") or "",
        linha["acao"],
        linha.get("detalhe") or "",
        _data_canonica(linha["registrado_em"]),
    ]
    return hashlib.sha256(json.dumps(conteudo, ensure_ascii=False).encode("utf-8")).hexdigest()


def _ultimo_codigo(supabase, caso_id: str) -> str | None:
    linhas = (
        supabase.table("conduta_trilha")
        .select("codigo")
        .eq("caso_id", caso_id)
        .order("seq", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return linhas[0]["codigo"] if linhas else None


def registrar(supabase, caso_id: str, autor_id: str | None, acao: str, detalhe: str = "") -> dict[str, Any]:
    """Grava uma linha na trilha do caso. Levanta se não conseguir: quem chama
    não segue sem o registro."""
    for tentativa in range(1, _TENTATIVAS + 1):
        anterior = _ultimo_codigo(supabase, caso_id)
        linha = {
            "caso_id": caso_id,
            "autor_id": autor_id,
            "acao": acao,
            "detalhe": detalhe,
            "registrado_em": datetime.now(UTC).isoformat(timespec="microseconds"),
            "codigo_anterior": anterior,
        }
        linha["codigo"] = codigo_da_linha(linha, anterior)
        try:
            return supabase.table("conduta_trilha").insert(linha).execute().data[0]
        except APIError as erro:
            if tentativa == _TENTATIVAS or getattr(erro, "code", None) != "23514":
                raise
            logger.info("Trilha do caso disputada por outra gravação; refazendo a linha.")
    raise AssertionError("inalcançável")


def codigo_de_integridade(conteudo: bytes) -> str:
    """O código de integridade de um arquivo do caso: o SHA-256 do arquivo
    decifrado, em hexadecimal (issue #1837). Gravado no envio, ele mostra se o
    arquivo entregue depois é o mesmo."""
    return hashlib.sha256(conteudo).hexdigest()


def linhas_adulteradas(linhas: list[dict[str, Any]]) -> list[int]:
    """As `seq` das linhas em que a cadeia quebra, na ordem da trilha.

    Uma linha trocada não bate com o próprio código; a linha logo depois de uma
    apagada não aponta para a que ficou antes dela.
    """
    quebradas: list[int] = []
    anterior: str | None = None
    for linha in sorted(linhas, key=lambda x: x["seq"]):
        if linha.get("codigo_anterior") != anterior or linha["codigo"] != codigo_da_linha(linha, anterior):
            quebradas.append(linha["seq"])
        anterior = linha["codigo"]
    return quebradas
