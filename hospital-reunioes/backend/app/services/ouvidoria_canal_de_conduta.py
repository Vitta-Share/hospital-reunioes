"""A sinalização da Ouvidoria ao Canal de Conduta (issue #1849, PRD #1786,
ADR 0097 decisão 14, emenda à ADR 0088).

Manifestação de paciente sobre conduta grave de um profissional continua na
Ouvidoria. O ouvidor ganha o botão "Sinalizar ao Canal de Conduta", que abre um
caso no Canal com o relato integral, na fila de triagem do Comitê e com a
origem Ouvidoria. É a segunda exceção ao sigilo do relato, por decisão do
diretor.

Três regras que só valem aqui:

- O caso leva o relato e nada de quem manifestou: o nome, o e-mail e o
  telefone nem são lidos.
- A manifestação não muda de estado. Ganha o carimbo da sinalização e um
  movimento na trilha, e a resposta e o encerramento seguem o caminho de
  sempre.
- Uma manifestação vira um caso só. O índice único da migration 202 recusa o
  segundo, e a nova tentativa de uma sinalização que parou depois do caso
  termina com o que ficou, sem abrir outro.

O ouvidor não passa a ver o caso: nada do caso volta para ele, e o portão do
Comitê o recusa como recusa qualquer pessoa sem designação.
"""

from __future__ import annotations

import datetime as dt
import logging

from postgrest.exceptions import APIError

from app.services.conduta import casos

logger = logging.getLogger(__name__)

_VIOLACAO_DE_UNICIDADE = "23505"

OBSERVACAO = (
    "Sinalizado ao Canal de Conduta. O Comitê de Conduta recebeu o relato, sem o nome "
    "nem o contato de quem manifestou. A manifestação segue aberta na Ouvidoria."
)


class JaSinalizadaError(Exception):
    """A manifestação já foi sinalizada ao Canal."""


def _caso_da_manifestacao(supabase, manifestacao_id: str) -> dict | None:
    lido = supabase.table("conduta_casos").select("id").eq("manifestacao_id", manifestacao_id).limit(1).execute()
    return lido.data[0] if lido.data else None


def sinalizar(supabase, *, manifestacao: dict, autor: dict, agora: dt.datetime) -> None:
    """Abre o caso no Canal e carimba a manifestação. `manifestacao` traz o id,
    o status, o relato integral e o carimbo `conduta_sinalizada_em`.

    Levanta `JaSinalizadaError` quando a manifestação já estava sinalizada, e
    `cifra.CifraIndisponivelError` sem a chave do Canal, antes de gravar."""
    if manifestacao.get("conduta_sinalizada_em"):
        raise JaSinalizadaError()
    manifestacao_id = manifestacao["id"]
    if _caso_da_manifestacao(supabase, manifestacao_id) is None:
        try:
            casos.registrar_caso(
                supabase,
                relato=manifestacao.get("relato_integral") or "",
                categoria=None,
                manifestacao_id=manifestacao_id,
            )
        except APIError as erro:
            # Outra sinalização gravou o caso no meio do caminho.
            if getattr(erro, "code", None) != _VIOLACAO_DE_UNICIDADE or not _caso_da_manifestacao(
                supabase, manifestacao_id
            ):
                raise
    carimbado = (
        supabase.table("ouvidoria_protocolos")
        .update({"conduta_sinalizada_em": agora.isoformat()})
        .eq("id", manifestacao_id)
        .is_("conduta_sinalizada_em", "null")
        .execute()
    )
    if not carimbado.data:
        raise JaSinalizadaError()
    _registrar_na_trilha(supabase, manifestacao, autor)


def _registrar_na_trilha(supabase, manifestacao: dict, autor: dict) -> None:
    """O fato entra na trilha da manifestação, sem transição de estado.
    Melhor esforço: a trilha não desfaz a sinalização."""
    try:
        supabase.table("ouvidoria_movimentos").insert(
            {
                "manifestacao_id": manifestacao["id"],
                "estado_anterior": manifestacao.get("status"),
                "estado_novo": manifestacao.get("status"),
                "autor_id": autor.get("id"),
                "autor_nome": autor.get("nome_completo") or autor.get("id") or "Sistema",
                "observacao": OBSERVACAO,
            }
        ).execute()
    except Exception:  # noqa: BLE001
        logger.warning("Falha ao gravar a sinalização ao Canal na trilha do caso %s", manifestacao.get("id"))
