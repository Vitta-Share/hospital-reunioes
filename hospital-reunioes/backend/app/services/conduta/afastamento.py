"""O afastamento cautelar do Canal de Conduta (issue #1836; especificação,
seção 6.5; decisões 20 a 23, 35 e 36 do diretor no PRD #1786).

Disponível em qualquer etapa, enquanto o caso está aberto, para um Citado do
caso e nunca para quem relatou:

- no caso comum, quem decide é o Comitê, pelo coordenador: ele registra a
  decisão de afastar, e o aplicativo gera o pedido ao DP e ao Jurídico. O DP
  faz as notificações formais, e o parecer do Jurídico é consultivo;
- na Rota Especial, o grupo pede o afastamento à coordenação, que vê só o
  pedido e nada mais do caso (`portao.portao_do_afastamento`). A coordenação
  pede o parecer ao Jurídico com urgência e o anexa, com ciência dos membros
  do grupo, e é o parecer que define se haverá afastamento.

O pedido leva só quem afastar e o motivo: nem relato, nem protocolo, nem
quem relatou. Ele é entregue fora do aplicativo, e a coordenação registra a
entrega ao DP e ao Jurídico. O parecer entra cifrado no bucket do Canal e só
sai pela rota que confere o acesso.

Toda ação grava a sua linha na trilha antes de mudar qualquer coisa.
"""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from postgrest.exceptions import APIError

from app.services import storage
from app.services.conduta import cifra, impedimento, membros, trilha
from app.services.conduta.acesso import PessoaNoComite
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc, data_do_envio
from app.services.conduta.rota_especial import DO_GRUPO, no_grupo
from app.services.conduta.triagem import AcaoRecusadaError

logger = logging.getLogger(__name__)

TABELA = "conduta_afastamentos"
BUCKET = "conduta-arquivos"
AVISO = "O afastamento cautelar é remunerado e não é punição."
RESULTADOS = {"afastar": "afastar", "nao_afastar": "não afastar"}
DESTINOS = {"dp": "ao DP", "juridico": "ao Jurídico"}
TAMANHO_DO_MOTIVO = 1000
LIMITE_DO_PARECER = 20 * 1024 * 1024
_PROTOCOLO = re.compile(r"CC-[A-Z0-9]{4}-[A-Z0-9]{4}", re.IGNORECASE)


@dataclass(frozen=True)
class PedidoAberto:
    """O afastamento que a pessoa abre. `so_o_pedido` é a coordenação na Rota
    Especial: ela vê o pedido e nada mais do caso, e `caso` não leva conteúdo."""

    autor_id: str
    pessoa: PessoaNoComite
    caso: dict
    atribuicoes: list[dict]
    afastamento: dict
    so_o_pedido: bool


# ── Quem relatou ────────────────────────────────────────────────────────────


def _normal(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.casefold().split())


def _nomes_de_quem_relatou(supabase, caso: dict) -> set[str]:
    """Quem relatou, quando o caso sabe: o denunciante identificado ouvido na
    Apuração e, no caso que a Ouvidoria sinalizou, o nome da manifestação."""
    nomes = {
        cifra.decifrar_texto(d["nome_cifrado"])
        for d in supabase.table("conduta_depoimentos").select("*").eq("caso_id", caso["id"]).execute().data or []
        if d.get("papel") == "denunciante"
    }
    if caso.get("manifestacao_id"):
        manifestacao = (
            supabase.table("ouvidoria_protocolos")
            .select("manifestante_nome")
            .eq("id", caso["manifestacao_id"])
            .limit(1)
            .execute()
            .data
            or []
        )
        nomes |= {m.get("manifestante_nome") or "" for m in manifestacao}
    return {_normal(n) for n in nomes if _normal(n)}


# ── O registro ──────────────────────────────────────────────────────────────


def _do_caso(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(TABELA).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda x: str(x.get("registrado_em") or ""))


def pode_registrar(aberto: CasoAberto) -> bool:
    caso = aberto.caso
    if caso.get("encerrado_em"):
        return False
    if caso.get("rota") == "especial":
        return no_grupo(aberto)
    return aberto.pessoa.papel == "coordenacao"


def registrar(supabase, aberto: CasoAberto, *, citado_id: str, motivo: str) -> dict:
    """No caso comum, a decisão do coordenador; na Rota Especial, o pedido do
    grupo à coordenação."""
    caso = aberto.caso
    especial = caso.get("rota") == "especial"
    if caso.get("encerrado_em"):
        raise AcaoRecusadaError(409, "O caso está encerrado.")
    if not pode_registrar(aberto):
        quem = "o Grupo Especial pede" if especial else "o coordenador do Comitê registra"
        raise AcaoRecusadaError(403, f"Só {quem} o afastamento cautelar.")
    citado = next((c for c in impedimento.citados_para_a_tela(supabase, caso["id"]) if c["id"] == citado_id), None)
    if citado is None:
        raise AcaoRecusadaError(422, "Escolha quem afastar entre os Citados do caso.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise AcaoRecusadaError(422, "Diga o motivo do afastamento.")
    if len(motivo) > TAMANHO_DO_MOTIVO:
        raise AcaoRecusadaError(422, "O motivo passou do tamanho que cabe.")
    if _PROTOCOLO.search(motivo):
        raise AcaoRecusadaError(422, "O motivo não leva protocolo de caso.")
    if _normal(citado["nome"] or "") in _nomes_de_quem_relatou(supabase, caso):
        raise AcaoRecusadaError(422, "Nenhuma medida cautelar recai sobre quem relatou.")
    if any(a["citado_id"] == citado_id for a in _do_caso(supabase, caso["id"])):
        raise AcaoRecusadaError(409, "Já há afastamento registrado para esta pessoa neste caso.")
    acao, detalhe = (
        ("afastamento_pedido", "o Grupo Especial pediu o afastamento cautelar à coordenação")
        if especial
        else ("afastamento_decidido", "o coordenador decidiu o afastamento cautelar")
    )
    trilha.registrar(supabase, caso["id"], aberto.autor_id, acao, detalhe)
    supabase.table(TABELA).insert(
        {
            "caso_id": caso["id"],
            "citado_id": citado_id,
            "rota": "especial" if especial else "comum",
            "quem_cifrado": cifra.cifrar_texto(citado["nome"] or ""),
            "motivo_cifrado": cifra.cifrar_texto(motivo),
            "registrado_por": aberto.autor_id,
            "registrado_em": agora_utc().isoformat(),
        }
    ).execute()
    return caso


# ── O que se vê ─────────────────────────────────────────────────────────────


def resultado(afastamento: dict) -> str | None:
    """No caso comum, a decisão do coordenador é afastar. Na Rota Especial,
    quem define é o parecer: sem ele, ainda não há resultado."""
    if afastamento["rota"] == "comum":
        return "afastar"
    return afastamento.get("parecer_resultado")


def _vista(supabase, afastamento: dict, coordena: bool) -> dict[str, Any]:
    parecer = None
    if afastamento.get("parecer_anexado_em"):
        ciencia = afastamento.get("ciencia_de")
        nomes = membros.nomes(supabase, list(ciencia or []))
        parecer = {
            "anexado_em": afastamento["parecer_anexado_em"],
            "ciencia_de": [nomes.get(pid) or "" for pid in ciencia] if ciencia is not None else None,
        }
    return {
        "id": afastamento["id"],
        "rota": afastamento["rota"],
        "quem": cifra.decifrar_texto(afastamento["quem_cifrado"]),
        "motivo": cifra.decifrar_texto(afastamento["motivo_cifrado"]),
        "registrado_em": afastamento["registrado_em"],
        "resultado": resultado(afastamento),
        "entregas": {"dp": afastamento.get("entregue_ao_dp_em"), "juridico": afastamento.get("entregue_ao_juridico_em")},
        "parecer": parecer,
        "pode_registrar_entrega": coordena,
        "pode_anexar_parecer": coordena and not afastamento.get("parecer_anexado_em"),
    }


def para_a_tela(supabase, aberto: CasoAberto) -> dict[str, Any]:
    """O que a tela do caso mostra a quem abre o caso inteiro."""
    coordena = aberto.caso.get("rota") == "comum" and aberto.pessoa.papel == "coordenacao"
    return {
        "aviso_do_afastamento": AVISO,
        "afastamentos": [_vista(supabase, a, coordena) for a in _do_caso(supabase, aberto.caso["id"])],
        "pode_registrar_afastamento": pode_registrar(aberto),
    }
