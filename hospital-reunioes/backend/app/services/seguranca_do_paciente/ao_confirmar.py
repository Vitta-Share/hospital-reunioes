"""O que acontece ao confirmar a triagem (issue #1994, PRD #1979, ADR 0107 decisão 1).

Na mesma operação que congela os prazos do caso:

- **a reunião de análise**: nas faixas A e B, a reunião de análise de evento
  nasce Programada na data-limite (o prazo `reuniao_de_analise` já congelado,
  7 dias úteis na A e 15 na B, contados da confirmação), com o protocolo no
  bloco Casos da pauta. A lesão por pressão dos itens 8 a 10 sem óbito não tem
  esse prazo nem reunião própria: entra na pauta da ordinária seguinte (art.
  24, parágrafo único);
- **a comunicação à Direção**: nas faixas A e B, um e-mail urgente e nominal à
  Diretoria e à Diretoria Executiva, com o protocolo e o link, sem o relato;
- **o aviso a quem notificou**: quem se identificou com e-mail fica sabendo
  que o caso está em análise. O anônimo vê o estado novo na página de
  acompanhamento.

Tudo aqui é repetível: a confirmação que caiu no meio conclui na nova
tentativa sem segunda reunião nem segundo aviso. A reunião é uma por caso
(`reunioes.nsp_caso_id`, migration 218) e o aviso, um por caso, marco e
destinatário (a chave do registro de e-mail).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from postgrest.exceptions import APIError

from app.config import settings
from app.dependencies import selecionar_participantes
from app.services.ouvidoria_contato import email_utilizavel
from app.services.ouvidoria_notificacoes import ler_diretoria_executiva
from app.services.seguranca_do_paciente import emails, pauta, prazos
from app.services.seguranca_do_paciente.permissao import FAIXAS_DA_DIRETORIA, ROLES_DA_DIRETORIA, id_do_nucleo
from app.services.seguranca_do_paciente.reunioes import TipoReuniaoNsp
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

_FUSO = ZoneInfo("America/Sao_Paulo")
MODELO = "email_nsp_aviso.html"
MARCO_DA_DIRECAO = "comunicacao_a_direcao"
MARCO_DO_EM_ANALISE = "caso_em_analise"
MARCOS = (MARCO_DA_DIRECAO, MARCO_DO_EM_ANALISE)

ANALISE_DE_EVENTO = TipoReuniaoNsp.ANALISE_DE_EVENTO.value

_CAMPOS_DO_CASO = "id, protocolo, anonimo, notificante_nome, notificante_contato"
_CAMPOS_DA_REUNIAO = "id_reuniao, data, tipo, colegiado_id, status_ata, nsp_caso_id"


def _agora() -> datetime:
    return datetime.now(_FUSO)


def _instante(bruto: Any) -> datetime:
    momento = datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def _caso(supabase, caso_id: str) -> dict[str, Any] | None:
    linhas = supabase.table("nsp_notificacoes").select(_CAMPOS_DO_CASO).eq("id", caso_id).limit(1).execute().data
    return linhas[0] if linhas else None


# ═══════════════════════════════════════════════════════════════════════════
# A reunião de análise
# ═══════════════════════════════════════════════════════════════════════════


def _data_limite(supabase, caso_id: str) -> date | None:
    """O dia em que vence a reunião de análise do caso, em São Paulo, ou None
    quando o caso não tem esse prazo (faixas C, D e E, e a lesão por pressão
    dos itens 8 a 10 sem óbito)."""
    linhas = (
        supabase.table(prazos.PRAZOS_DO_CASO)
        .select("marco, vence_em")
        .eq("notificacao_id", caso_id)
        .eq("marco", prazos.REUNIAO_DE_ANALISE)
        .limit(1)
        .execute()
        .data
    ) or []
    return _instante(linhas[0]["vence_em"]).astimezone(_FUSO).date() if linhas else None


def _reuniao_do_caso(supabase, caso_id: str) -> dict[str, Any] | None:
    linhas = supabase.table("reunioes").select(_CAMPOS_DA_REUNIAO).eq("nsp_caso_id", caso_id).limit(1).execute().data
    return linhas[0] if linhas else None


def _criar_a_reuniao(supabase, caso: dict, dia: date, nucleo_id: str, autor_id: str) -> dict[str, Any]:
    from app.routers.reunioes import _generate_reuniao_id

    linha = {
        "id_reuniao": _generate_reuniao_id(dia),
        "titulo": f"Análise do caso {caso['protocolo']}",
        "data": dia.isoformat(),
        "hora_inicio": None,
        "hora_fim": None,
        "tipo": ANALISE_DE_EVENTO,
        "objetivo": f"Analisar o caso {caso['protocolo']}, confirmado na triagem.",
        "status_ata": "PROGRAMADA",
        "fonte": "MOCK",
        "facilitador_id": autor_id,
        "criada_por": autor_id,
        "colegiado_id": nucleo_id,
        "nsp_caso_id": caso["id"],
    }
    try:
        supabase.table("reunioes").insert(linha).execute()
    except APIError as erro:
        # Outra tentativa criou primeiro (uma reunião por caso, migration 218).
        if erro.code != "23505":
            raise
        existente = _reuniao_do_caso(supabase, caso["id"])
        if existente is None:
            raise
        return existente
    supabase.table("reuniao_participantes").insert([{"id_reuniao": linha["id_reuniao"], "participante_id": autor_id}]).execute()
    logger.info("Reunião de análise %s do caso %s criada na confirmação", linha["id_reuniao"], caso["id"])
    return linha


def _agendar_a_analise(supabase, caso: dict, autor_id: str, agora: datetime) -> None:
    dia = _data_limite(supabase, caso["id"])
    if dia is None:
        return
    reuniao = _reuniao_do_caso(supabase, caso["id"])
    if reuniao is None:
        nucleo_id = id_do_nucleo(supabase)
        if not nucleo_id:
            logger.error("[Confirmação NSP] Sem o Núcleo cadastrado: a reunião de %s não foi criada.", caso["id"])
            return
        reuniao = _criar_a_reuniao(supabase, caso, dia, nucleo_id, autor_id)
    gravada = pauta.garantir_pauta(supabase, reuniao, agora)
    pauta.incluir_caso(supabase, gravada, caso["protocolo"], f"Análise do caso {caso['protocolo']}")


def _levar_a_ordinaria_seguinte(supabase, caso: dict, confirmada_em: datetime) -> None:
    """A lesão por pressão sem reunião própria entra na ordinária seguinte. Se
    a pauta dela já foi montada, o caso entra agora; senão, a montagem o traz
    (`pauta.montar`)."""
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return
    seguinte = pauta.ordinaria_seguinte(supabase, nucleo_id, confirmada_em.astimezone(_FUSO).date())
    gravada = pauta.pauta_gravada(supabase, seguinte["id_reuniao"]) if seguinte else None
    if gravada:
        pauta.incluir_caso(supabase, gravada, caso["protocolo"], pauta.texto_da_lesao_por_pressao(caso["protocolo"]))


# ═══════════════════════════════════════════════════════════════════════════
# A operação
# ═══════════════════════════════════════════════════════════════════════════


def ao_confirmar(supabase, notificacao: dict[str, Any], decisao: dict[str, Any], autor_id: str) -> None:
    """Cria a reunião de análise e registra os avisos que a confirmação pede.
    Chamada depois de os prazos estarem congelados no caso."""
    caso = _caso(supabase, notificacao["id"])
    if caso is None:
        return
    agora = _agora()
    if prazos.sem_reuniao_extraordinaria(decisao.get("evento_item"), decisao.get("grau_de_dano")):
        confirmada_em = _instante(decisao["criado_em"]) if decisao.get("criado_em") else agora
        _levar_a_ordinaria_seguinte(supabase, caso, confirmada_em)
    else:
        _agendar_a_analise(supabase, caso, autor_id, agora)
