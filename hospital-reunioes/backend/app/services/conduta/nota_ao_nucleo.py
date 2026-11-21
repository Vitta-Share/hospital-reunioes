"""A nota do Comitê ao Núcleo de Segurança do Paciente (issue #1850; ADR 0097,
decisão 14; especificação, seção 5.3, "Sinalizar ao NSP").

Quando um caso descreve um risco ao paciente, um membro do Comitê escreve uma
nota e a coordenação a envia. O Núcleo recebe só a nota: sem protocolo, sem
relato, sem anexo e sem quem relatou.

Os dois lados ficam em tabelas separadas (migration 203):

- `conduta_notas_nsp`, do lado do Comitê: a nota do caso, cifrada como todo
  conteúdo do módulo, com quem escreveu e quem enviou;
- `nsp_notas_do_comite`, do lado do Núcleo: só o texto e a data do envio.
  Nenhuma coluna aponta para o caso, e o lado do Comitê não guarda o id da
  linha do Núcleo: nada liga uma à outra.

Escrever e enviar gravam a linha na trilha do caso antes de mudar qualquer
coisa: sem a linha, a ação não acontece.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from postgrest.exceptions import APIError

from app.services.conduta import cifra, trilha
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc
from app.services.conduta.triagem import AcaoRecusadaError

logger = logging.getLogger(__name__)

TAMANHO_DA_NOTA = 2000

_DO_COMITE = "conduta_notas_nsp"
_DO_NUCLEO = "nsp_notas_do_comite"


def _pendente(supabase, caso_id: str) -> dict | None:
    linhas = supabase.table(_DO_COMITE).select("*").eq("caso_id", caso_id).is_("enviada_em", "null").execute().data
    return (linhas or [None])[0]


def escrever_nota(supabase, aberto: CasoAberto, *, texto: str) -> dict:
    """Um membro do Comitê escreve a nota. Escrever de novo antes do envio
    troca o texto da nota que espera a coordenação."""
    caso = aberto.caso
    if aberto.pessoa.papel is None:
        raise AcaoRecusadaError(403, "Só quem é do Comitê escreve a nota ao Núcleo.")
    texto = (texto or "").strip()
    if not texto:
        raise AcaoRecusadaError(422, "Escreva a nota ao Núcleo.")
    if len(texto) > TAMANHO_DA_NOTA:
        raise AcaoRecusadaError(422, "A nota passou do tamanho que cabe.")
    if caso["protocolo"].lower() in texto.lower():
        raise AcaoRecusadaError(422, "A nota não leva o protocolo do caso.")
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "nota_ao_nsp_escrita", "escreveu a nota ao Núcleo")
    campos = {
        "texto_cifrado": cifra.cifrar_texto(texto),
        "escrita_por": aberto.autor_id,
        "escrita_em": agora_utc().isoformat(),
    }
    pendente = _pendente(supabase, caso["id"])
    if pendente:
        supabase.table(_DO_COMITE).update(campos).eq("id", pendente["id"]).is_("enviada_em", "null").execute()
    else:
        supabase.table(_DO_COMITE).insert({"caso_id": caso["id"], **campos}).execute()
    return caso


def enviar_nota(supabase, aberto: CasoAberto) -> dict:
    """A coordenação envia ao Núcleo a nota escrita. O Núcleo recebe só o
    texto; a nota do caso fica marcada como enviada."""
    caso = aberto.caso
    if aberto.pessoa.papel != "coordenacao":
        raise AcaoRecusadaError(403, "Só a coordenação envia a nota ao Núcleo.")
    pendente = _pendente(supabase, caso["id"])
    if pendente is None:
        raise AcaoRecusadaError(409, "Não há nota escrita para enviar.")
    texto = cifra.decifrar_texto(pendente["texto_cifrado"])
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "nota_ao_nsp_enviada", "enviou a nota ao Núcleo")
    marcada = (
        supabase.table(_DO_COMITE)
        .update({"enviada_por": aberto.autor_id, "enviada_em": agora_utc().isoformat()})
        .eq("id", pendente["id"])
        .is_("enviada_em", "null")
        .execute()
        .data
    )
    if not marcada:
        raise AcaoRecusadaError(409, "A nota mudou enquanto você agia. Abra de novo.")
    try:
        supabase.table(_DO_NUCLEO).insert({"texto": texto}).execute()
    except (APIError, httpx.HTTPError) as erro:
        # Sem a nota do lado do Núcleo, a do caso volta a esperar o envio.
        supabase.table(_DO_COMITE).update({"enviada_por": None, "enviada_em": None}).eq("id", pendente["id"]).execute()
        logger.error("Nota do Comitê não chegou ao Núcleo; volta a esperar o envio: %s", erro)
        raise AcaoRecusadaError(503, "A nota não chegou ao Núcleo. Tente de novo.") from erro
    return caso


def notas_do_caso(supabase, caso_id: str) -> list[dict[str, Any]]:
    """As notas do caso para a tela do Comitê, da mais antiga à mais nova."""
    linhas = supabase.table(_DO_COMITE).select("*").eq("caso_id", caso_id).execute().data or []
    return [
        {
            "texto": cifra.decifrar_texto(linha["texto_cifrado"]),
            "escrita_em": linha.get("escrita_em"),
            "enviada_em": linha.get("enviada_em"),
        }
        for linha in sorted(linhas, key=lambda x: str(x.get("escrita_em") or ""))
    ]


def notas_para_o_nucleo(supabase) -> list[dict[str, Any]]:
    """A lista "Notas do Comitê de Conduta" de Segurança do Paciente, da mais
    nova à mais antiga: o texto e a data do envio, e nada mais."""
    linhas = supabase.table(_DO_NUCLEO).select("id, texto, enviada_em").execute().data or []
    return [
        {"id": linha["id"], "texto": linha["texto"], "enviada_em": linha.get("enviada_em")}
        for linha in sorted(linhas, key=lambda x: str(x.get("enviada_em") or ""), reverse=True)
    ]
