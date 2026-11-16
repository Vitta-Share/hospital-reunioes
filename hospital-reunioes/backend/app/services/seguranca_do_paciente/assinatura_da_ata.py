"""A assinatura da ata do Núcleo, o encerramento e a limpeza da transcrição
(issue #1776, PRD #1764, ADR 0095).

A ata validada pela Presidência vai para a assinatura eletrônica dos presentes
(e só deles), num envelope próprio, sobre as mesmas primitivas das Reuniões e
do Termo (`clicksign_service`). O envelope fica em `json_ata.assinatura`, e não
nas colunas de envelope da reunião: assim o retorno genérico da assinatura e a
reconciliação das Reuniões não alcançam a ata do Núcleo, que vive em bucket
privado e sai só pela rota do módulo.

Dois jobs diários, sem IA:

- `encerrar_atas`: 5 dias úteis depois do envio (com os feriados cadastrados),
  ou antes, se todos já assinaram, finaliza o envelope com as assinaturas que
  ele tem, grava na ata quem não assinou e guarda o PDF assinado nos
  Documentos do Núcleo, com número sequencial. Também tenta de novo o envio
  que falhou na validação.
- `apagar_transcricoes`: 30 dias corridos depois da ata assinada, apaga a
  transcrição importada da reunião do Núcleo. A de outras reuniões não entra.

Rodar os dois de novo não muda nada: cada passo confere o que já foi feito.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

from app.config import settings
from app.services import clicksign_service, storage
from app.services.paginacao import ler_tudo
from app.services.seguranca_do_paciente import ata as ata_do_nucleo
from app.services.seguranca_do_paciente import pauta, permissao
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

DIAS_UTEIS_PARA_ASSINAR = 5
DIAS_ATE_APAGAR_A_TRANSCRICAO = 30
# `closed`: todos assinaram (ou alguém finalizou); `canceled`: recusa. Nos
# dois, esperar o prazo não traz assinatura nova.
ENVELOPE_FECHADO = frozenset({"closed", "canceled", "cancelled"})

# O link do PDF assinado vale 10 minutos, como o do Termo.
VALIDADE_DO_LINK = 600

FALHA_DO_ENVIO = "A assinatura eletrônica não respondeu. O aplicativo tenta de novo amanhã."
SEM_EMAIL = "Nenhum presente tem e-mail no cadastro. Corrija o cadastro: o aplicativo tenta de novo amanhã."


class _EnvioFalhou(Exception):
    pass


def _bucket() -> str:
    return settings.supabase_storage_bucket_nsp_documentos


# ---------------------------------------------------------------------------
# O PDF
# ---------------------------------------------------------------------------


def gerar_pdf_da_ata(reuniao: dict, ata: dict) -> bytes:
    """O PDF da ata nos dez blocos (WeasyPrint, como a Ata e o Termo)."""
    from weasyprint import HTML

    from app.services.pdf_generator import env
    from app.services.pdf_url_fetcher import criar_pdf_url_fetcher

    base = os.path.join(os.path.dirname(__file__), "..", "..", "static")
    logo_path = os.path.abspath(os.path.join(base, "images", "logo_hospital.png"))
    font_path = os.path.abspath(os.path.join(base, "fonts", "HPSimplified_Rg.ttf"))
    logo_uri = f"file://{logo_path}" if os.path.exists(logo_path) else None
    font_uri = f"file://{font_path}" if os.path.exists(font_path) else None

    html = env.get_template("nsp_ata_do_nucleo.html").render(
        reuniao=reuniao, ata=ata, logo_path=logo_uri, font_path=font_uri
    )
    alvo = io.BytesIO()
    permitidos = frozenset(uri for uri in (logo_uri, font_uri) if uri)
    HTML(string=html, url_fetcher=criar_pdf_url_fetcher(permitidos)).write_pdf(target=alvo)
    return alvo.getvalue()


# ---------------------------------------------------------------------------
# O envio
# ---------------------------------------------------------------------------


def presentes(supabase, id_reuniao: str) -> list[dict]:
    """Os presentes da reunião, com nome e e-mail, por id."""
    from app.dependencies import selecionar_participantes

    ids = sorted(pid for pid, s in ata_do_nucleo._presenca(supabase, id_reuniao).items() if s == "presente")
    if not ids:
        return []
    linhas = selecionar_participantes(supabase, "id, nome_completo, email", lambda q: q.in_("id", ids)).data or []
    por_id = {linha["id"]: linha for linha in linhas}
    return [
        {
            "participante_id": pid,
            "nome": (por_id.get(pid) or {}).get("nome_completo") or pid,
            "email": ((por_id.get(pid) or {}).get("email") or "").strip() or None,
        }
        for pid in ids
    ]


def _criar_envelope(id_reuniao: str, pdf: bytes, signatarios: list[dict]) -> tuple[str, str]:
    """O envelope com a ata e um signatário por presente. Qualquer passo que
    falha derruba o envio inteiro: a ata não sai sem um dos presentes."""
    envelope_id = clicksign_service.create_envelope(f"Ata do Núcleo - {id_reuniao}")
    if not envelope_id:
        raise _EnvioFalhou(FALHA_DO_ENVIO)
    documento_key = clicksign_service.add_document(envelope_id, pdf, f"Ata_do_Nucleo_{id_reuniao}.pdf")
    if not documento_key:
        raise _EnvioFalhou(FALHA_DO_ENVIO)
    for pessoa in signatarios:
        signatario_id = clicksign_service.add_signer(envelope_id, nome=pessoa["nome"], email=pessoa["email"])
        if not (
            signatario_id
            and clicksign_service.create_qualification_requirement(envelope_id, documento_key, signatario_id)
            and clicksign_service.create_auth_requirement(envelope_id, documento_key, signatario_id)
        ):
            raise _EnvioFalhou(FALHA_DO_ENVIO)
    if not clicksign_service.activate_envelope(envelope_id):
        raise _EnvioFalhou(FALHA_DO_ENVIO)
    # A própria assinatura eletrônica também avisa; falhar aqui não derruba um
    # envelope já ativo (como nas Reuniões e no Termo).
    clicksign_service.notify_signers(envelope_id)
    return envelope_id, documento_key


def enviar_para_assinatura(supabase, id_reuniao: str, agora: datetime) -> dict[str, Any] | None:
    """Manda a ata validada para os presentes. Só a ata do Núcleo aprovada e
    sem envelope sai; a que já saiu fica como está. Falha deixa a ata
    aprovada, com o erro em `assinatura.erro`, e o job tenta de novo."""
    reuniao = ata_do_nucleo.reuniao_do_nucleo(supabase, id_reuniao)
    if not reuniao:
        return None
    json_ata = dict(reuniao.get("json_ata") or {})
    anterior = json_ata.get("assinatura") or {}
    if (
        reuniao.get("status_ata") != "APROVADA"
        or json_ata.get("modelo") != ata_do_nucleo.MODELO_DA_ATA
        or anterior.get("envelope_id")
    ):
        return anterior or None
    lista = presentes(supabase, id_reuniao)
    com_email = [p for p in lista if p["email"]]
    try:
        if not com_email:
            raise _EnvioFalhou(SEM_EMAIL)
        pdf = gerar_pdf_da_ata(reuniao, json_ata)
        envelope_id, documento_key = _criar_envelope(id_reuniao, pdf, com_email)
    except Exception as erro:  # a ata validada não volta atrás: o job tenta de novo
        mensagem = str(erro) if isinstance(erro, _EnvioFalhou) else FALHA_DO_ENVIO
        logger.warning("Ata do Núcleo %s validada e não enviada para assinatura: %s", id_reuniao, erro)
        json_ata["assinatura"] = {"erro": mensagem, "tentativa_em": agora.isoformat()}
        supabase.table("reunioes").update({"json_ata": json_ata}).eq("id_reuniao", id_reuniao).execute()
        return json_ata["assinatura"]
    json_ata["assinatura"] = {
        "enviada_em": agora.isoformat(),
        "envelope_id": envelope_id,
        "documento_key": documento_key,
        "signatarios": com_email,
        "sem_email": [p for p in lista if not p["email"]],
        "erro": None,
    }
    supabase.table("reunioes").update({"json_ata": json_ata, "status_ata": "AGUARDANDO_ASSINATURA"}).eq(
        "id_reuniao", id_reuniao
    ).execute()
    logger.info("Ata do Núcleo %s enviada para assinatura de %d presente(s)", id_reuniao, len(com_email))
    return json_ata["assinatura"]


# ---------------------------------------------------------------------------
# O encerramento
# ---------------------------------------------------------------------------


def prazo_do_encerramento(enviada_em: date, feriados: frozenset[date]) -> date:
    """O quinto dia útil depois do envio (o próprio dia não conta)."""
    dia = enviada_em
    for _ in range(DIAS_UTEIS_PARA_ASSINAR):
        dia += timedelta(days=1)
        while not pauta.e_dia_util(dia, feriados):
            dia += timedelta(days=1)
    return dia


def _feriados(supabase, inicio: date, fim: date) -> frozenset[date]:
    """Os feriados cadastrados. Aqui a falha de leitura sobe: encerrar antes
    do prazo tiraria a assinatura de quem ainda tinha tempo, e o job tenta de
    novo amanhã."""
    linhas = (
        supabase.table("ouvidoria_feriados")
        .select("data")
        .gte("data", inicio.isoformat())
        .lte("data", fim.isoformat())
        .execute()
        .data
    ) or []
    return frozenset(date.fromisoformat(str(linha["data"])[:10]) for linha in linhas if linha.get("data"))


def _atas_do_nucleo(supabase, situacoes: list[str]) -> list[dict]:
    nucleo_id = permissao.id_do_nucleo(supabase)
    if not nucleo_id:
        return []
    return ler_tudo(
        lambda: (
            supabase.table("reunioes")
            .select("id_reuniao, data, tipo, status_ata, data_assinatura, colegiado_id, json_ata")
            .eq("colegiado_id", nucleo_id)
            .in_("status_ata", situacoes)
            .is_("deleted_at", "null")
            .order("id_reuniao")
        ),
        rotulo="atas do Núcleo",
    )


def _lista(nomes: list[str]) -> str:
    return ", ".join(nomes) + "."


def _encerrar(supabase, reuniao: dict, hoje: date) -> bool:
    """Encerra a ata no prazo (ou antes, com o envelope já fechado). Devolve
    se encerrou. Qualquer resposta que falta da assinatura eletrônica deixa
    para amanhã."""
    json_ata = dict(reuniao["json_ata"])
    assinatura = json_ata.get("assinatura") or {}
    envelope_id = assinatura.get("envelope_id")
    if not envelope_id:
        return False
    situacao = clicksign_service.get_envelope_status(envelope_id)
    if situacao is None:
        return False
    fechado = situacao in ENVELOPE_FECHADO
    if not fechado:
        enviada_em = datetime.fromisoformat(assinatura["enviada_em"]).astimezone(pauta.FUSO).date()
        prazo = prazo_do_encerramento(enviada_em, _feriados(supabase, enviada_em, enviada_em + timedelta(days=60)))
        if hoje < prazo:
            return False
    signatarios = clicksign_service.list_signers(envelope_id)
    if signatarios is None:
        return False
    if not fechado and not clicksign_service.close_envelope(envelope_id):
        return False

    assinados = {(s.get("email") or "").strip().lower() for s in signatarios if s.get("status") == "signed"}
    convidados = assinatura.get("signatarios") or []
    assinaram = sorted(p["nome"] for p in convidados if p["email"].lower() in assinados)
    nao_assinaram = sorted(
        [p["nome"] for p in convidados if p["email"].lower() not in assinados]
        + [p["nome"] for p in assinatura.get("sem_email") or []]
    )
    itens = [f"Assinaram: {_lista(assinaram)}" if assinaram else "Nenhum presente assinou."]
    if nao_assinaram:
        itens.append(f"Presentes que não assinaram: {_lista(nao_assinaram)}")
    json_ata["blocos"] = [
        {**bloco, "itens": itens} if bloco.get("chave") == "assinaturas" else bloco for bloco in json_ata["blocos"]
    ]
    json_ata["encerramento"] = {"em": hoje.isoformat(), "assinaram": assinaram, "nao_assinaram": nao_assinaram}
    supabase.table("reunioes").update(
        {
            "json_ata": json_ata,
            "status_ata": "ASSINADA",
            "data_assinatura": hoje.isoformat(),
            "signatarios_total": len(assinaram) + len(nao_assinaram),
            "signatarios_assinaram": len(assinaram),
        }
    ).eq("id_reuniao", reuniao["id_reuniao"]).eq("status_ata", "AGUARDANDO_ASSINATURA").execute()
    logger.info(
        "Ata do Núcleo %s encerrada: %d assinatura(s), %d presente(s) sem assinar",
        reuniao["id_reuniao"],
        len(assinaram),
        len(nao_assinaram),
    )
    return True


# ---------------------------------------------------------------------------
# A ata encerrada nos Documentos do Núcleo
# ---------------------------------------------------------------------------


def documento_da_ata(supabase, id_reuniao: str) -> dict | None:
    linhas = (
        supabase.table("nsp_documentos")
        .select("id, versao, arquivo_assinado_path")
        .eq("reuniao_id", id_reuniao)
        .limit(1)
        .execute()
        .data
    ) or []
    return linhas[0] if linhas else None


def link_do_arquivo(supabase, caminho: str) -> str | None:
    return storage.signed_url(supabase, _bucket(), caminho, VALIDADE_DO_LINK)


def _proxima_versao_da_ata(supabase) -> int:
    linhas = (
        supabase.table("nsp_documentos")
        .select("versao")
        .eq("tipo", "ata")
        .order("versao", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    return int(linhas[0]["versao"]) + 1 if linhas else 1


def _titulo(reuniao: dict) -> str:
    dia = date.fromisoformat(str(reuniao["data"])[:10]).strftime("%d/%m/%Y")
    return sanitizar_estrutura(f"Ata da reunião {reuniao.get('tipo') or 'do Núcleo'} de {dia}")[:200]


def _guardar_nos_documentos(supabase, reuniao: dict) -> bool:
    """O PDF assinado nos Documentos, uma vez por reunião, com o número
    seguinte das atas. Sem o PDF pronto, a rodada seguinte tenta de novo."""
    json_ata = reuniao.get("json_ata") or {}
    envelope_id = (json_ata.get("assinatura") or {}).get("envelope_id")
    if not envelope_id or not json_ata.get("encerramento") or documento_da_ata(supabase, reuniao["id_reuniao"]):
        return False
    pdf = clicksign_service.get_signed_document(envelope_id)
    if not pdf:
        logger.warning("PDF assinado da ata do Núcleo %s ainda indisponível", reuniao["id_reuniao"])
        return False
    caminho = f"atas/{reuniao['id_reuniao']}-assinada.pdf"
    if not storage.upload_private(supabase, _bucket(), caminho, pdf, "application/pdf"):
        return False
    supabase.table("nsp_documentos").insert(
        {
            "tipo": "ata",
            "versao": _proxima_versao_da_ata(supabase),
            "titulo": _titulo(reuniao),
            "vigente": False,
            "arquivo_assinado_path": caminho,
            "publicado_por": (json_ata.get("validacao") or {}).get("por"),
            "reuniao_id": reuniao["id_reuniao"],
        }
    ).execute()
    logger.info("Ata do Núcleo %s guardada nos Documentos", reuniao["id_reuniao"])
    return True


def encerrar_atas(supabase, hoje: date, agora: datetime | None = None) -> dict[str, int]:
    """O job diário: tenta de novo o envio que falhou, encerra a ata no
    quinto dia útil e guarda a encerrada nos Documentos. Uma ata que falha
    não segura as outras."""
    agora = agora or datetime.now(tz=pauta.FUSO)
    contagem = {"enviadas": 0, "encerradas": 0, "documentos": 0}
    for reuniao in _atas_do_nucleo(supabase, ["APROVADA", "AGUARDANDO_ASSINATURA", "ASSINADA"]):
        try:
            if reuniao["status_ata"] == "APROVADA":
                if (enviar_para_assinatura(supabase, reuniao["id_reuniao"], agora) or {}).get("envelope_id"):
                    contagem["enviadas"] += 1
                continue
            if reuniao["status_ata"] == "AGUARDANDO_ASSINATURA":
                if not _encerrar(supabase, reuniao, hoje):
                    continue
                contagem["encerradas"] += 1
                reuniao = ata_do_nucleo.reuniao_do_nucleo(supabase, reuniao["id_reuniao"]) or reuniao
            if _guardar_nos_documentos(supabase, reuniao):
                contagem["documentos"] += 1
        except Exception:  # noqa: BLE001 (uma ata não segura as outras; amanhã tem outra rodada)
            logger.exception("Ata do Núcleo %s: o encerramento falhou nesta rodada", reuniao["id_reuniao"])
    return contagem


# ---------------------------------------------------------------------------
# A limpeza da transcrição
# ---------------------------------------------------------------------------


def _remover_do_storage(supabase, bucket: str, caminhos: list[str]) -> list:
    """Remove os arquivos e devolve o que o Storage confirmou. Levanta na falha."""
    return supabase.storage.from_(bucket).remove(caminhos) or []


def _hoje(valor: Any) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])
