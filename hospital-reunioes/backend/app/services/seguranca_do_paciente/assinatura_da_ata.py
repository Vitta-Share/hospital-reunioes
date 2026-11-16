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
from datetime import date, datetime
from typing import Any

from app.config import settings
from app.services import clicksign_service
from app.services.seguranca_do_paciente import ata as ata_do_nucleo

logger = logging.getLogger(__name__)

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
# A limpeza da transcrição
# ---------------------------------------------------------------------------


def _remover_do_storage(supabase, bucket: str, caminhos: list[str]) -> list:
    """Remove os arquivos e devolve o que o Storage confirmou. Levanta na falha."""
    return supabase.storage.from_(bucket).remove(caminhos) or []


def _hoje(valor: Any) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])
