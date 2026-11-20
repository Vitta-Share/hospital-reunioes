"""
Reconciliação ativa com a ClickSign (issue #279, ADR 0030 decisão 4).

Webhook perdido nunca trava uma Ata: a mesma função serve o job diário do
scheduler e o botão "Sincronizar" do card de Signatários. Para uma Reunião em
AGUARDANDO_ASSINATURA com Envelope, consulta o status do Envelope na ClickSign
e aplica o mesmo fluxo do webhook, idempotente:

- Envelope `closed` (todas as assinaturas, fechamento manual ou deadline com
  parciais): `aceite_service.finalizar_documento` (Pendências restantes +
  registro de faltantes + ASSINADA + PDF best-effort).
- Envelope `canceled` (cancelamento manual, recusa ou deadline sem
  assinaturas): `aceite_service.abrir_modo_interno` (Envelope morto, sem
  reenvio; a Reunião permanece em AGUARDANDO_ASSINATURA com flag).
- Envelope `running`/`draft`: nada a fazer.

Antes da consulta, o job cria as Pendências que faltam em toda Ata em
AGUARDANDO_ASSINATURA (ADR 0098, decisão 3; issue #1867). A primeira execução
resolve o passivo de Atas já travadas e faz a carga das que já estavam em
assinatura antes de a Pendência nascer no envio.
"""

import logging

from app.services import aceite_service, clicksign_service

logger = logging.getLogger(__name__)

DESFECHO_FINALIZADA = "finalizada"
DESFECHO_MODO_INTERNO = "modo_interno"
DESFECHO_SEM_MUDANCA = "sem_mudanca"
DESFECHO_INDISPONIVEL = "indisponivel"


def _recuperar_envelope_id(supabase, reuniao: dict) -> str | None:
    """Self-heal de Ata pré-039: localiza o Envelope pelo nome determinístico
    + document_id e persiste o `envelope_id_clicksign` (mesmo padrão do card
    de Signatários). None = não recuperou."""
    id_reuniao = reuniao["id_reuniao"]
    envelope_id = clicksign_service.find_envelope_id(
        clicksign_service.envelope_name(id_reuniao), reuniao["envelope_key_clicksign"]
    )
    if not envelope_id:
        return None
    supabase.table("reunioes").update({"envelope_id_clicksign": envelope_id}).eq("id_reuniao", id_reuniao).execute()
    reuniao["envelope_id_clicksign"] = envelope_id
    return envelope_id


def reconciliar_reuniao(supabase, reuniao: dict) -> str:
    """Reconcilia UMA Reunião com a ClickSign e devolve o desfecho.

    Idempotente: Reunião já resolvida (ASSINADA ou modo interno aberto) sai em
    `sem_mudanca` sem consultar a ClickSign; a finalização é idempotente por
    ação do quadro e o modo interno só abre uma vez (aceite_service).
    """
    id_reuniao = reuniao["id_reuniao"]
    if reuniao.get("status_ata") != "AGUARDANDO_ASSINATURA" or reuniao.get("modo_interno_desde"):
        return DESFECHO_SEM_MUDANCA
    envelope_key = reuniao.get("envelope_key_clicksign")
    if not envelope_key:
        return DESFECHO_SEM_MUDANCA

    envelope_id = reuniao.get("envelope_id_clicksign") or _recuperar_envelope_id(supabase, reuniao)
    if not envelope_id:
        logger.warning(f"[Reconciliacao] {id_reuniao} sem envelope_id recuperável; consulta indisponível.")
        return DESFECHO_INDISPONIVEL

    status = clicksign_service.get_envelope_status(envelope_id)
    if status is None:
        return DESFECHO_INDISPONIVEL

    if status == "closed":
        aceite_service.finalizar_documento(supabase, reuniao, envelope_key=envelope_key)
        logger.info(f"[Reconciliacao] Envelope de {id_reuniao} fechado na ClickSign: Reunião finalizada.")
        return DESFECHO_FINALIZADA

    if status in ("canceled", "cancelled"):
        aceite_service.abrir_modo_interno(supabase, id_reuniao, evento="reconciliacao")
        return DESFECHO_MODO_INTERNO

    return DESFECHO_SEM_MUDANCA


def criar_pendencias_que_faltam(supabase) -> int:
    """Cria as Pendências que faltam em toda Ata em AGUARDANDO_ASSINATURA
    (ADR 0098, decisão 3), com ou sem Envelope, no modo interno ou não. A
    criação é idempotente por ação do quadro: a primeira execução faz a carga
    das Atas que já estavam em assinatura, e as seguintes cobrem o envio que
    falhou no meio. A Ata do Núcleo fica de fora: as Pendências dela nascem na
    validação, pelo fluxo próprio. Falha em uma Ata não interrompe as demais.
    Devolve quantas Pendências nasceram."""
    from app.services import pendencia_service
    from app.services.seguranca_do_paciente.permissao import id_do_nucleo

    atas = (
        supabase.table("reunioes")
        .select("id_reuniao, colegiado_id")
        .eq("status_ata", "AGUARDANDO_ASSINATURA")
        .is_("deleted_at", "null")
        .execute()
        .data
        or []
    )
    nucleo = id_do_nucleo(supabase) if any(a.get("colegiado_id") for a in atas) else None
    criadas = 0
    for ata in atas:
        if nucleo and ata.get("colegiado_id") == nucleo:
            continue
        try:
            criadas += pendencia_service.liberar_pendencias(supabase, ata["id_reuniao"], origem="RECONCILIACAO")
        except Exception as e:
            logger.error(f"[Reconciliacao] Erro ao criar as Pendências de {ata['id_reuniao']}: {e}", exc_info=True)
    if criadas:
        logger.info(f"[Reconciliacao] {criadas} Pendência(s) criada(s) em Atas em assinatura.")
    return criadas


def reconciliar_pendentes(supabase) -> dict[str, int]:
    """Cria as Pendências que faltam nas Atas em assinatura e depois varre as
    Reuniões em AGUARDANDO_ASSINATURA com Envelope (fora do modo interno, cujo
    Envelope já morreu) e reconcilia uma a uma com a ClickSign. Falha em uma
    Reunião não interrompe as demais. Devolve contadores por desfecho."""
    pendencias_criadas = criar_pendencias_que_faltam(supabase)
    res = (
        supabase.table("reunioes")
        .select(
            "id_reuniao, status_ata, envelope_key_clicksign, envelope_id_clicksign, "
            "url_pdf_assinado, modo_interno_desde"
        )
        .eq("status_ata", "AGUARDANDO_ASSINATURA")
        .is_("modo_interno_desde", "null")
        .is_("deleted_at", "null")
        .execute()
    )
    contadores = {
        DESFECHO_FINALIZADA: 0,
        DESFECHO_MODO_INTERNO: 0,
        DESFECHO_SEM_MUDANCA: 0,
        DESFECHO_INDISPONIVEL: 0,
        "erro": 0,
        "pendencias_criadas": pendencias_criadas,
    }
    for reuniao in res.data or []:
        if not reuniao.get("envelope_key_clicksign"):
            continue
        try:
            desfecho = reconciliar_reuniao(supabase, reuniao)
        except Exception as e:
            logger.error(f"[Reconciliacao] Erro em {reuniao.get('id_reuniao')}: {e}", exc_info=True)
            contadores["erro"] += 1
            continue
        contadores[desfecho] += 1
    logger.info(f"[Reconciliacao] Varredura concluída: {contadores}")
    return contadores
