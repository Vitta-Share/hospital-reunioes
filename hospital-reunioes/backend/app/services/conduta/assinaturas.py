"""As assinaturas do Canal de Conduta pela ClickSign (issue #1823, ADR 0097,
decisões 2 e 13).

Todo documento do módulo que vai à ClickSign é uma linha de
`conduta_assinaturas` (migration 192): o tipo, o caso quando houver, os
signatários e a situação. O webhook acha a linha pela chave do documento, e o
"Reconsultar status" chega ao mesmo `processar_evento`. A assinatura conta no
fechamento do envelope (todos assinaram), e a cópia do PDF assinado, que traz
o log das assinaturas na última página, fica no bucket do Canal cifrada pela
aplicação, para a prova não depender da conta da ClickSign.

O primeiro documento é o Termo de Confidencialidade e Posse do membro do
Comitê, com o Regimento do Comitê como parte integrante. Assinado, ele carimba
a Participação, e só então o membro abre caso (`acesso`).

O segundo é o termo de confidencialidade de quem foi convidado para um caso,
o apurador designado ou o membro da CIPA (issue #1825). Assinado, ele carimba
a atribuição do convidado naquele caso, e a assinatura entra na trilha.

O terceiro é o relatório de apuração do rito Completo, assinado pelos
apuradores (issue #1832). A linha aponta para a versão que foi assinada, e a
assinatura entra na trilha do caso.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from app.services import clicksign_service, storage
from app.services.conduta import cifra, trilha
from app.services.conduta.membros import CADEIRAS
from app.services.seguranca_do_paciente.termo import gerar_pdf_do_termo
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

TABELA = "conduta_assinaturas"
BUCKET = "conduta-arquivos"

TERMO_DE_POSSE = "termo_de_posse"
MODELO_DO_TERMO = "conduta_termo_de_posse.html"
# A versão do Regimento que o modelo do Termo traz no anexo.
VERSAO_DO_REGIMENTO = 1

# O termo de quem foi convidado para um caso (migration 192 já tem o tipo).
TERMO_DO_CONVIDADO = "termo_do_apurador"
MODELO_DO_TERMO_DO_CONVIDADO = "conduta_termo_do_convidado.html"
# As atribuições que nascem do convite (migration 175).
MOTIVOS_DO_CONVITE = ("apurador", "cipa")

# O relatório de apuração do rito Completo (issue #1832).
RELATORIO_DE_APURACAO = "relatorio_de_apuracao"
MODELO_DO_RELATORIO = "conduta_relatorio_de_apuracao.html"

# O envelope fecha quando todos assinaram. `sign` não conta: num documento de
# três signatários ele chega a cada assinatura.
EVENTOS_DE_FECHAMENTO = frozenset({"auto_close", "close", "AutoClose", "Close"})
# O PDF assinado fica garantido para download só aqui (pesquisa na #1786).
EVENTO_DOCUMENTO_PRONTO = "document_closed"

FALHA_DO_ENVIO = "A assinatura eletrônica não respondeu. Use Reenviar o Termo em instantes."


class TermoNaoGeradoError(Exception):
    """O Termo não pôde ser gerado. A mensagem vai para a tela como está."""


class AssinaturaIndisponivelError(Exception):
    """A ClickSign não respondeu à reconsulta."""


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _dia(valor: Any) -> str:
    dia = valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])
    return dia.strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# O envio, para qualquer documento do Canal
# ---------------------------------------------------------------------------


def enviar_a_clicksign(pdf: bytes, nome: str, arquivo: str, signatarios: list[dict]) -> tuple[str, str] | str:
    """Um envelope com o documento e cada signatário (nome e e-mail). Devolve
    (envelope, chave do documento) ou, em falha, a mensagem para a tela."""
    envelope_id = clicksign_service.create_envelope(nome)
    if not envelope_id:
        return FALHA_DO_ENVIO
    documento_id = clicksign_service.add_document(envelope_id, pdf, arquivo)
    if not documento_id:
        return FALHA_DO_ENVIO
    for pessoa in signatarios:
        signatario_id = clicksign_service.add_signer(envelope_id, nome=pessoa["nome_completo"], email=pessoa["email"])
        if not signatario_id:
            return FALHA_DO_ENVIO
        if not clicksign_service.create_qualification_requirement(envelope_id, documento_id, signatario_id):
            return FALHA_DO_ENVIO
        if not clicksign_service.create_auth_requirement(envelope_id, documento_id, signatario_id):
            return FALHA_DO_ENVIO
    if not clicksign_service.activate_envelope(envelope_id):
        return FALHA_DO_ENVIO
    # A ClickSign também avisa; falhar aqui não derruba um envelope já ativo.
    clicksign_service.notify_signers(envelope_id)
    return envelope_id, documento_id


def _registrar_envio(supabase, assinatura: dict, resultado: tuple[str, str] | str) -> dict:
    if isinstance(resultado, str):
        logger.warning("Assinatura %s do Canal gerada e não enviada: %s", assinatura["id"], resultado)
        campos: dict[str, Any] = {"erro": resultado}
    else:
        envelope_id, documento_key = resultado
        campos = {
            "erro": None,
            "situacao": "enviado",
            "envelope_id": envelope_id,
            "documento_key": documento_key,
            "enviado_em": _agora(),
        }
    supabase.table(TABELA).update(campos).eq("id", assinatura["id"]).execute()
    return {**assinatura, **campos}


# ---------------------------------------------------------------------------
# O Termo de Confidencialidade e Posse
# ---------------------------------------------------------------------------


def _pessoa(supabase, participante_id: str) -> dict:
    linhas = (
        supabase.table("participantes")
        .select("id, nome_completo, email, cargo, setor")
        .eq("id", participante_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not linhas:
        raise TermoNaoGeradoError("A pessoa não está no cadastro.")
    return linhas[0]


def dados_do_termo(pessoa: dict, participacao: dict, identificador: str) -> dict:
    """O que preenche o modelo. Passa pelo sanitizador: o nome vem de quem
    digitou, e o PDF não sai com travessão."""
    dados = sanitizar_estrutura(
        {
            "membro": {
                "nome": pessoa.get("nome_completo") or "Não informado",
                "cargo": pessoa.get("cargo") or "Não informado",
                "setor": pessoa.get("setor") or "Não informado",
                "cadeira": CADEIRAS.get(participacao.get("papel"), participacao.get("papel") or ""),
                "vigencia_inicio": _dia(participacao["vigencia_inicio"]),
                "vigencia_fim": _dia(participacao["vigencia_fim"]),
            },
            "regimento": {"versao": VERSAO_DO_REGIMENTO},
            "documento": {"identificador": identificador},
        }
    )
    return {**dados, "modelo": MODELO_DO_TERMO}


def enviar_termo_de_posse(supabase, participacao: dict) -> dict:
    """Gera o Termo do membro e o envia ao e-mail profissional dele. Devolve a
    linha gravada. Sem e-mail, nada é gerado e sobe `TermoNaoGeradoError`;
    falha da ClickSign deixa a linha em "gerado", com o erro, para o reenvio."""
    pessoa = _pessoa(supabase, participacao["participante_id"])
    if not pessoa.get("email"):
        raise TermoNaoGeradoError(
            "A pessoa não tem e-mail profissional no cadastro, e o Termo vai por e-mail para assinatura."
        )
    assinatura = (
        supabase.table(TABELA)
        .insert(
            {
                "tipo": TERMO_DE_POSSE,
                "participacao_id": participacao["id"],
                "signatarios": [pessoa["id"]],
                "situacao": "gerado",
            }
        )
        .execute()
        .data
    )[0]
    pdf = gerar_pdf_do_termo(dados_do_termo(pessoa, participacao, assinatura["id"]))
    resultado = enviar_a_clicksign(
        pdf,
        f"Termo de Confidencialidade e Posse CC - {assinatura['id']}",
        f"Termo_de_Confidencialidade_e_Posse_{assinatura['id']}.pdf",
        [pessoa],
    )
    return _registrar_envio(supabase, assinatura, resultado)


def abertas_do_membro(supabase, participacao_id: str) -> list[dict]:
    return (
        supabase.table(TABELA)
        .select("*")
        .eq("tipo", TERMO_DE_POSSE)
        .eq("participacao_id", participacao_id)
        .in_("situacao", ["gerado", "enviado"])
        .execute()
        .data
    ) or []


def ultima_do_membro(supabase, participacao_id: str) -> dict | None:
    linhas = (
        supabase.table(TABELA)
        .select("*")
        .eq("tipo", TERMO_DE_POSSE)
        .eq("participacao_id", participacao_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    return linhas[0] if linhas else None


def reenviar_termo_de_posse(supabase, participacao: dict) -> dict:
    """Cancela o envio aberto (o link antigo morre) e manda outro Termo, com
    outro identificador. O retorno do envelope cancelado não muda nada."""
    for aberta in abertas_do_membro(supabase, participacao["id"]):
        if aberta.get("envelope_id"):
            clicksign_service.cancel_envelope(aberta["envelope_id"])
        supabase.table(TABELA).update({"situacao": "cancelado", "cancelado_em": _agora()}).eq(
            "id", aberta["id"]
        ).execute()
    return enviar_termo_de_posse(supabase, participacao)


def situacao_dos_termos(supabase, participacoes: list[dict]) -> dict[str, str]:
    """Por Participação: `assinado`, `aguardando_assinatura` ou `nao_enviado`."""
    ids = [p["id"] for p in participacoes if not p.get("termo_assinado_em")]
    enviados: set[str] = set()
    if ids:
        linhas = (
            supabase.table(TABELA)
            .select("participacao_id")
            .eq("tipo", TERMO_DE_POSSE)
            .eq("situacao", "enviado")
            .in_("participacao_id", ids)
            .execute()
            .data
        ) or []
        enviados = {linha["participacao_id"] for linha in linhas}
    return {
        p["id"]: "assinado"
        if p.get("termo_assinado_em")
        else ("aguardando_assinatura" if p["id"] in enviados else "nao_enviado")
        for p in participacoes
    }


# ---------------------------------------------------------------------------
# O termo de confidencialidade do convidado (issue #1825)
# ---------------------------------------------------------------------------


def _abertas_do_convidado(supabase, caso_id: str, participante_id: str) -> list[dict]:
    linhas = (
        supabase.table(TABELA)
        .select("*")
        .eq("tipo", TERMO_DO_CONVIDADO)
        .eq("caso_id", caso_id)
        .in_("situacao", ["gerado", "enviado"])
        .execute()
        .data
    ) or []
    return [linha for linha in linhas if participante_id in (linha.get("signatarios") or [])]


def enviar_termo_do_convidado(supabase, caso_id: str, pessoa: dict, papel: str) -> dict:
    """Gera o termo do convidado e o envia ao e-mail dele, cancelando o envio
    que ainda estava aberto (o link antigo morre). O documento não leva o
    protocolo nem nada do caso: o identificador é o da própria assinatura.
    Falha da ClickSign deixa a linha em "gerado", com o erro."""
    for aberta in _abertas_do_convidado(supabase, caso_id, pessoa["id"]):
        if aberta.get("envelope_id"):
            clicksign_service.cancel_envelope(aberta["envelope_id"])
        supabase.table(TABELA).update({"situacao": "cancelado", "cancelado_em": _agora()}).eq(
            "id", aberta["id"]
        ).execute()
    assinatura = (
        supabase.table(TABELA)
        .insert({"tipo": TERMO_DO_CONVIDADO, "caso_id": caso_id, "signatarios": [pessoa["id"]], "situacao": "gerado"})
        .execute()
        .data
    )[0]
    dados = sanitizar_estrutura(
        {
            "convidado": {"nome": pessoa.get("nome_completo") or "Não informado", "papel": papel},
            "documento": {"identificador": assinatura["id"]},
        }
    )
    pdf = gerar_pdf_do_termo({**dados, "modelo": MODELO_DO_TERMO_DO_CONVIDADO})
    resultado = enviar_a_clicksign(
        pdf,
        f"Termo de Confidencialidade CC - {assinatura['id']}",
        f"Termo_de_Confidencialidade_{assinatura['id']}.pdf",
        [pessoa],
    )
    return _registrar_envio(supabase, assinatura, resultado)


def termos_enviados_do_caso(supabase, caso_id: str) -> set[str]:
    """Quem do caso tem o termo de convidado enviado, esperando a assinatura."""
    linhas = (
        supabase.table(TABELA)
        .select("signatarios")
        .eq("tipo", TERMO_DO_CONVIDADO)
        .eq("caso_id", caso_id)
        .eq("situacao", "enviado")
        .execute()
        .data
    ) or []
    return {pid for linha in linhas for pid in linha.get("signatarios") or []}


# ---------------------------------------------------------------------------
# O relatório de apuração do rito Completo (issue #1832)
# ---------------------------------------------------------------------------


def enviar_relatorio_de_apuracao(supabase, caso_id: str, relatorio: dict, texto: str, pessoas: list[dict]) -> dict:
    """Gera o PDF da versão `relatorio` e o envia aos apuradores, cancelando o
    envio do relatório que ainda estava aberto no caso (o link antigo morre).
    O documento não leva o protocolo: o identificador é o da assinatura.
    Falha da ClickSign deixa a linha em "gerado", com o erro."""
    abertas = (
        supabase.table(TABELA)
        .select("*")
        .eq("tipo", RELATORIO_DE_APURACAO)
        .eq("caso_id", caso_id)
        .in_("situacao", ["gerado", "enviado"])
        .execute()
        .data
    ) or []
    for aberta in abertas:
        if aberta.get("envelope_id"):
            clicksign_service.cancel_envelope(aberta["envelope_id"])
        supabase.table(TABELA).update({"situacao": "cancelado", "cancelado_em": _agora()}).eq(
            "id", aberta["id"]
        ).execute()
    assinatura = (
        supabase.table(TABELA)
        .insert(
            {
                "tipo": RELATORIO_DE_APURACAO,
                "caso_id": caso_id,
                "relatorio_id": relatorio["id"],
                "signatarios": [p["id"] for p in pessoas],
                "situacao": "gerado",
            }
        )
        .execute()
        .data
    )[0]
    dados = sanitizar_estrutura(
        {
            "relatorio": {"texto": texto, "versao": relatorio["versao"]},
            "apuradores": [p.get("nome_completo") or "Não informado" for p in pessoas],
            "documento": {"identificador": assinatura["id"]},
        }
    )
    pdf = gerar_pdf_do_termo({**dados, "modelo": MODELO_DO_RELATORIO})
    resultado = enviar_a_clicksign(
        pdf,
        f"Relatório de Apuração CC - {assinatura['id']}",
        f"Relatorio_de_Apuracao_{assinatura['id']}.pdf",
        pessoas,
    )
    return _registrar_envio(supabase, assinatura, resultado)


def _registrar_relatorio_assinado(supabase, assinatura: dict) -> None:
    """A assinatura dos apuradores entra na trilha do caso, uma vez só: o
    retorno repetido (fechamento e documento pronto) acha a linha já lá."""
    linhas = (
        supabase.table("conduta_relatorios").select("versao").eq("id", assinatura["relatorio_id"]).limit(1).execute()
    ).data or []
    versao = linhas[0]["versao"] if linhas else "?"
    detalhe = f"relatório de apuração, versão {versao}, assinado pelos apuradores"
    ja = (
        supabase.table("conduta_trilha")
        .select("id")
        .eq("caso_id", assinatura["caso_id"])
        .eq("acao", "relatorio_assinado")
        .eq("detalhe", detalhe)
        .limit(1)
        .execute()
    ).data
    if not ja:
        trilha.registrar(supabase, assinatura["caso_id"], None, "relatorio_assinado", detalhe)


# ---------------------------------------------------------------------------
# O retorno da assinatura: webhook e reconsulta
# ---------------------------------------------------------------------------


def _efeito_da_assinatura(supabase, assinatura: dict, assinado_em: str) -> None:
    """O que a assinatura muda fora da tabela. O Termo carimba a Participação,
    e o do convidado, a atribuição dele no caso, só se ainda falta: o retorno
    repetido não acha mais nada."""
    if assinatura["tipo"] == TERMO_DE_POSSE:
        supabase.table("participacoes").update({"termo_assinado_em": assinado_em}).eq(
            "id", assinatura["participacao_id"]
        ).is_("termo_assinado_em", "null").execute()
    elif assinatura["tipo"] == TERMO_DO_CONVIDADO:
        _carimbar_o_convite(supabase, assinatura, assinado_em)
    elif assinatura["tipo"] == RELATORIO_DE_APURACAO:
        _registrar_relatorio_assinado(supabase, assinatura)


def _carimbar_o_convite(supabase, assinatura: dict, assinado_em: str) -> None:
    """A atribuição aberta do convidado naquele caso passa a valer. A linha da
    trilha vem antes, como em toda ação do caso."""
    [participante_id] = assinatura["signatarios"]
    pendentes = (
        supabase.table("conduta_atribuicoes")
        .select("id")
        .eq("caso_id", assinatura["caso_id"])
        .eq("participante_id", participante_id)
        .in_("motivo", list(MOTIVOS_DO_CONVITE))
        .is_("revogada_em", "null")
        .is_("termo_assinado_em", "null")
        .execute()
        .data
    ) or []
    if not pendentes:
        return
    trilha.registrar(supabase, assinatura["caso_id"], participante_id, "termo_assinado", "termo de confidencialidade")
    supabase.table("conduta_atribuicoes").update({"termo_assinado_em": assinado_em}).in_(
        "id", [linha["id"] for linha in pendentes]
    ).execute()


def _guardar_copia(supabase, assinatura: dict) -> None:
    """O PDF assinado, cifrado, no bucket do Canal, uma vez por envio.
    Best-effort: sem o arquivo pronto, o próximo evento ou a reconsulta tenta
    de novo."""
    if assinatura.get("arquivo_assinado_path"):
        return
    pdf = clicksign_service.get_signed_document(assinatura.get("envelope_id"))
    if not pdf:
        logger.warning("PDF assinado da assinatura %s do Canal ainda indisponível", assinatura["id"])
        return
    try:
        cifrado = cifra.cifrar_arquivo(pdf)
    except cifra.CifraIndisponivelError:
        logger.error("Cópia da assinatura %s do Canal não guardada: cifra indisponível", assinatura["id"])
        return
    caminho = f"assinaturas/{assinatura['id']}.pdf.cifrado"
    if not storage.upload_private(supabase, BUCKET, caminho, cifrado, "application/octet-stream"):
        return
    supabase.table(TABELA).update({"arquivo_assinado_path": caminho}).eq("id", assinatura["id"]).execute()


def processar_evento(supabase, assinatura: dict, evento: str) -> None:
    """O mesmo tratamento para o webhook e para a reconsulta."""
    if assinatura.get("situacao") == "enviado" and evento in EVENTOS_DE_FECHAMENTO:
        agora = _agora()
        trocadas = (
            supabase.table(TABELA)
            .update({"situacao": "assinado", "assinado_em": agora})
            .eq("id", assinatura["id"])
            .eq("situacao", "enviado")
            .execute()
            .data
        ) or []
        if not trocadas:
            return
        assinatura = {**assinatura, "situacao": "assinado", "assinado_em": agora}
    elif not (
        assinatura.get("situacao") == "assinado"
        and (evento in EVENTOS_DE_FECHAMENTO or evento == EVENTO_DOCUMENTO_PRONTO)
    ):
        logger.info("Evento %r da assinatura %s do Canal sem efeito", evento, assinatura.get("id"))
        return
    _efeito_da_assinatura(supabase, assinatura, assinatura.get("assinado_em") or _agora())
    _guardar_copia(supabase, assinatura)


def por_chave(supabase, documento_key: str) -> dict | None:
    """A assinatura do Canal da chave que o webhook recebeu, se for do Canal."""
    linhas = supabase.table(TABELA).select("*").eq("documento_key", documento_key).limit(1).execute().data or []
    return linhas[0] if linhas else None


def reconsultar(supabase, assinatura: dict) -> None:
    """Pergunta à ClickSign como está o envelope e aplica o mesmo tratamento do
    webhook: não depende de o webhook ter chegado."""
    status = clicksign_service.get_envelope_status(assinatura["envelope_id"])
    if status is None:
        raise AssinaturaIndisponivelError()
    if status == "closed":
        processar_evento(supabase, assinatura, "auto_close")
