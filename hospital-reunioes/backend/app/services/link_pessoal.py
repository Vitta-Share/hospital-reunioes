"""O link pessoal das Pendências (issue #1878; ADR 0098, decisão 8).

Quem nunca entrou no app recebe, no e-mail de segunda, um link com token para
atualizar as próprias Pendências sem senha, no padrão do portal do setor da
Ouvidoria (`ouvidoria_setor_tokens`): o token em claro vive só no e-mail, o
banco guarda o hash SHA-256, o link vence e pode ser revogado.

Diferente do portal do setor, o link não é de uso único: a pessoa age em
várias Pendências, em dias diferentes, pelo mesmo link. O que o prende é o
dono: ele só alcança as Pendências em que essa pessoa é responsável ou
co-responsável. A emissão não revoga os links anteriores, porque o envio que
falha tenta de novo na hora seguinte e o e-mail da tentativa anterior pode ter
chegado; a validade curta (14 dias) e o desligamento é que derrubam o link.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import secrets
from collections.abc import Iterable

logger = logging.getLogger(__name__)

TABELA = "pendencias_links_pessoais"
VALIDADE = dt.timedelta(days=14)
CAMINHO = "/minhas-pendencias"


class LinkInvalidoError(Exception):
    """Token que não existe: link adulterado ou copiado pela metade."""


class LinkVencidoError(Exception):
    """Passou da validade."""


class LinkRevogadoError(Exception):
    """Cancelado: a pessoa foi desligada do hospital."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def emitir(supabase, participante_id: str, agora: dt.datetime) -> str:
    """Emite o link de uma pessoa e devolve o token em claro."""
    token = secrets.token_urlsafe(32)
    supabase.table(TABELA).insert(
        {
            "participante_id": participante_id,
            "token_hash": _hash(token),
            "criado_em": agora.isoformat(),
            "expira_em": (agora + VALIDADE).isoformat(),
        }
    ).execute()
    return token


def carregar(supabase, token: str, agora: dt.datetime) -> dict:
    """O vínculo do token, ou a recusa: inválido, vencido ou revogado."""
    linhas = (
        supabase.table(TABELA)
        .select("id, participante_id, expira_em, revogado_em")
        .eq("token_hash", _hash(token))
        .limit(1)
        .execute()
        .data
    )
    if not linhas:
        raise LinkInvalidoError()
    vinculo = linhas[0]
    if vinculo.get("revogado_em"):
        raise LinkRevogadoError()
    if dt.datetime.fromisoformat(str(vinculo["expira_em"])) <= agora:
        raise LinkVencidoError()
    return vinculo


def revogar_da_pessoa(supabase, participante_id: str, agora: dt.datetime) -> int:
    """Cancela todo link vivo da pessoa e devolve quantos caíram."""
    result = (
        supabase.table(TABELA)
        .update({"revogado_em": agora.isoformat()})
        .eq("participante_id", participante_id)
        .is_("revogado_em", "null")
        .execute()
    )
    return len(result.data or [])
