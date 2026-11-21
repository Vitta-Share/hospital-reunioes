"""O Termo de Adesão do Núcleo (issue #1768, PRD #1764, ADR 0095).

Um documento só por envio: o gabarito do Termo (anexo E da especificação)
preenchido com o cadastro do membro, seguido do texto integral do Regimento
vigente. Vai para a assinatura eletrônica num envelope próprio, com um
signatário, sobre as mesmas primitivas que os POPs e as Reuniões usam
(`clicksign_service`).

O retorno da assinatura (o webhook) e o "Reconsultar status" da tela passam
pelo mesmo `processar_evento`: a assinatura carimba a Participação (o membro
fica Ativo), grava a trilha e guarda o PDF assinado nos Documentos do Núcleo,
como Termo daquele membro e daquela vigência. Evento repetido não duplica nada;
envio cancelado (pelo reenvio) não muda nada.

Cada envio é uma linha da tabela de envios do Colegiado (a do Núcleo é
`nsp_termos_envios`, migration 151); o id dela é o identificador impresso no
documento.

O serviço recebe o Colegiado (issue #1819, ADR 0097 decisão 3): as tabelas, o
bucket, o modelo e a sigla do envelope vêm do `Colegiado`. Sem ele, vale o
Núcleo, e o comportamento do Núcleo é o de antes.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import UTC, date, datetime
from typing import Any

import httpx
from postgrest.exceptions import APIError

from app.config import settings
from app.services import clicksign_service, colegiados, storage
from app.services.colegiados import Colegiado
from app.services.paginacao import ler_tudo
from app.services.seguranca_do_paciente import permissao
from app.services.seguranca_do_paciente.membros import estado_do_membro
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

LABEL_PAPEL = {"presidencia": "Presidência", "suplente": "Suplente da Presidência", "membro": "Membro"}

# Os eventos do retorno da assinatura que dizem "assinado". Com um signatário
# só, a assinatura dele fecha o envelope: `sign` e `auto_close` chegam os dois.
EVENTOS_DE_ASSINATURA = frozenset({"sign", "auto_close", "close", "AutoClose", "Close"})
# O PDF assinado só fica garantido para download aqui; com o envio já
# assinado, o evento só tenta guardar o arquivo que faltou.
EVENTO_DOCUMENTO_PRONTO = "document_closed"

# O link do documento pendente, na faixa da tela, vale 10 minutos.
VALIDADE_DO_LINK = 600

_SEM_VALOR = "Não informado"


class TermoNaoGeradoError(Exception):
    """O Termo não pôde ser gerado. A mensagem vai para a tela como está."""


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _dia(valor: Any) -> str:
    if not valor:
        return _SEM_VALOR
    dia = valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])
    return dia.strftime("%d/%m/%Y")


def _depois(instante: Any, de: Any) -> bool:
    return bool(instante) and datetime.fromisoformat(str(instante)) > datetime.fromisoformat(str(de))


def novo_termo_pendente(participacao: dict, revisao_material_em: Any = None, hoje: date | None = None) -> bool:
    """O membro tem um Termo à espera da assinatura (issue #1769): nunca
    assinou; ou a renovação ou a mudança de papel pediu Termo novo depois da
    última assinatura (`termo_gerado_em`, carimbado junto com a mudança, antes
    de o documento sair); ou, em Ativo, A vencer e Em carência, assinou antes
    da última revisão material do Regimento (`revisao_material_em`). Assim a
    falha na geração não tira a pendência, e a ficha tem o reenvio."""
    assinado = participacao.get("termo_assinado_em")
    if not assinado:
        return True
    if _depois(participacao.get("termo_gerado_em"), assinado):
        return True
    return (
        _depois(revisao_material_em, assinado)
        and estado_do_membro(participacao, hoje or permissao.hoje_em_sao_paulo()) in ESTADOS_DA_REVISAO_MATERIAL
    )


def marca_do_novo_termo(participacao: dict) -> dict:
    """O carimbo que a renovação e a mudança de papel gravam junto com a
    mudança: deixa o Termo novo pendente antes de qualquer passo que pode
    falhar. Quem nunca assinou já está pendente, e o carimbo mudaria o estado."""
    return {"termo_gerado_em": _agora()} if participacao.get("termo_assinado_em") else {}


def revisao_material_em(supabase, *, colegiado: Colegiado = permissao.NUCLEO) -> str | None:
    """Quando passou a valer a última revisão material do Regimento (issue
    #1800). Só conta a que de fato vigorou: a publicada direto, pelo
    `publicado_em`; a enviada para assinatura, pela conclusão do envio, e
    nada enquanto ela espera. A assinada depois de uma versão mais nova já
    valer nunca vigorou (`nsp_tornar_vigente` não a troca) e também não conta."""
    versoes = (
        supabase.table(colegiado.documentos)
        .select("id, versao, natureza_revisao, publicado_em")
        .eq("tipo", "regimento")
        .execute()
        .data
    ) or []
    if not any(v.get("natureza_revisao") == "material" for v in versoes):
        return None
    envios = (
        supabase.table(colegiado.documentos_envios)
        .select("documento_id, situacao, assinado_em")
        .in_("documento_id", [v["id"] for v in versoes])
        .execute()
        .data
    ) or []
    com_envio = {e["documento_id"] for e in envios}
    vigorou_em = {v["id"]: v.get("publicado_em") for v in versoes if v["id"] not in com_envio}
    for envio in envios:
        if envio.get("situacao") == "assinado" and envio.get("assinado_em"):
            vigorou_em[envio["documento_id"]] = envio["assinado_em"]

    def _vigorou(versao: dict) -> bool:
        quando = vigorou_em.get(versao["id"])
        return bool(quando) and not any(
            outra["versao"] > versao["versao"]
            and vigorou_em.get(outra["id"])
            and not _depois(vigorou_em[outra["id"]], quando)
            for outra in versoes
        )

    datas = [vigorou_em[v["id"]] for v in versoes if v.get("natureza_revisao") == "material" and _vigorou(v)]
    return max(datas, key=lambda d: datetime.fromisoformat(str(d))) if datas else None


def _bucket(colegiado: Colegiado) -> str:
    return getattr(settings, colegiado.bucket_dos_documentos)


def registro_do_membro(pessoa: dict) -> str:
    """O registro como o Termo imprime ("CRF nº 000444/RJ"): conselho, número e UF, como o Termo imprime."""
    conselho = (pessoa.get("conselho_profissional") or "").strip()
    numero = (pessoa.get("registro_profissional") or "").strip()
    uf = (pessoa.get("registro_uf") or "").strip()
    if not conselho and not numero:
        return _SEM_VALOR
    return f"{conselho} nº {numero}{'/' + uf if uf else ''}".strip()


# ---------------------------------------------------------------------------
# O documento
# ---------------------------------------------------------------------------


def _vigente(supabase, tipo: str, *, colegiado: Colegiado = permissao.NUCLEO) -> dict | None:
    linhas = (
        supabase.table(colegiado.documentos)
        .select("id, tipo, versao, titulo, texto, publicado_em")
        .eq("tipo", tipo)
        .eq("vigente", True)
        .limit(1)
        .execute()
        .data
    ) or []
    return linhas[0] if linhas else None


def _pessoa(supabase, participante_id: str) -> dict:
    linhas = (
        supabase.table("participantes")
        .select("id, nome_completo, email, cargo, setor, conselho_profissional, registro_profissional, registro_uf")
        .eq("id", participante_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not linhas:
        raise TermoNaoGeradoError("A pessoa não está no cadastro.")
    return linhas[0]


def dados_do_termo(
    pessoa: dict,
    participacao: dict,
    regimento: dict,
    designacao: dict | None,
    envio_id: str,
    *,
    colegiado: Colegiado = permissao.NUCLEO,
) -> dict:
    """O que preenche o gabarito, e o `modelo` do Colegiado. Tudo passa pelo
    sanitizador: o texto do Regimento e os nomes vêm de quem digitou, e o PDF
    não sai com travessão."""
    dados = sanitizar_estrutura(
        {
            "membro": {
                "nome": pessoa.get("nome_completo") or _SEM_VALOR,
                "cargo": pessoa.get("cargo") or _SEM_VALOR,
                "setor": pessoa.get("setor") or participacao.get("area") or _SEM_VALOR,
                "registro": registro_do_membro(pessoa),
                "papel": LABEL_PAPEL.get(participacao.get("papel"), participacao.get("papel") or _SEM_VALOR),
                "vigencia_inicio": _dia(participacao.get("vigencia_inicio")),
                "vigencia_fim": _dia(participacao.get("vigencia_fim")),
            },
            "designacao": (
                f"{designacao['titulo']}, de {_dia(designacao.get('publicado_em'))}"
                if designacao
                else f"Ainda não publicado nos Documentos do {colegiado.nome}"
            ),
            "regimento": {
                "titulo": regimento.get("titulo") or "Regimento Interno",
                "versao": regimento.get("versao"),
                "data_aprovacao": _dia(regimento.get("publicado_em")),
                "texto": regimento.get("texto") or "",
            },
            "documento": {"identificador": envio_id},
        }
    )
    return {**dados, "modelo": colegiado.modelo_do_termo}


def gerar_pdf_do_termo(dados: dict) -> bytes:
    """O PDF do Termo com o Regimento no fim (WeasyPrint, como a Ata e o POP),
    no modelo que veio em `dados`."""
    from weasyprint import HTML

    from app.services.pdf_generator import env
    from app.services.pdf_url_fetcher import criar_pdf_url_fetcher

    base = os.path.join(os.path.dirname(__file__), "..", "..", "static")
    logo_path = os.path.abspath(os.path.join(base, "images", "logo_hospital.png"))
    font_path = os.path.abspath(os.path.join(base, "fonts", "HPSimplified_Rg.ttf"))
    logo_uri = f"file://{logo_path}" if os.path.exists(logo_path) else None
    font_uri = f"file://{font_path}" if os.path.exists(font_path) else None

    html = env.get_template(dados["modelo"]).render(**dados, logo_path=logo_uri, font_path=font_uri)
    alvo = io.BytesIO()
    permitidos = frozenset(uri for uri in (logo_uri, font_uri) if uri)
    HTML(string=html, url_fetcher=criar_pdf_url_fetcher(permitidos)).write_pdf(target=alvo)
    return alvo.getvalue()


# ---------------------------------------------------------------------------
# Trilha e leituras
# ---------------------------------------------------------------------------


def _trilha(supabase, participacao_id: str, autor_id: str, acao: str, *, valor_novo=None, motivo=None) -> None:
    supabase.table("participacoes_trilha").insert(
        {
            "participacao_id": participacao_id,
            "autor_id": autor_id,
            "acao": acao,
            "campo": "termo",
            "valor_anterior": None,
            "valor_novo": valor_novo,
            "motivo": motivo,
        }
    ).execute()


def envios_abertos(supabase, participacao_id: str, *, colegiado: Colegiado = permissao.NUCLEO) -> list[dict]:
    return (
        supabase.table(colegiado.termos_envios)
        .select("*")
        .eq("participacao_id", participacao_id)
        .in_("situacao", ["gerado", "enviado"])
        .execute()
        .data
    ) or []


def ultimo_envio(supabase, participacao_id: str, *, colegiado: Colegiado = permissao.NUCLEO) -> dict | None:
    linhas = (
        supabase.table(colegiado.termos_envios)
        .select("*")
        .eq("participacao_id", participacao_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    return linhas[0] if linhas else None


def _participacao(supabase, participacao_id: str) -> dict:
    return (
        supabase.table("participacoes")
        .select("id, participante_id, papel, area, vigencia_inicio, vigencia_fim, termo_gerado_em, termo_assinado_em")
        .eq("id", participacao_id)
        .limit(1)
        .execute()
        .data
    )[0]


# ---------------------------------------------------------------------------
# Gerar e enviar
# ---------------------------------------------------------------------------


def _enviar(pdf: bytes, envio_id: str, pessoa: dict, sigla: str) -> tuple[str, str] | str:
    """O envelope com o documento e o signatário. Devolve (envelope, chave do
    documento) ou, em falha, a mensagem para a tela."""
    falha = "A assinatura eletrônica não respondeu. Use Reenviar o Termo em instantes."
    envelope_id = clicksign_service.create_envelope(f"Termo de Adesão {sigla} - {envio_id}")
    if not envelope_id:
        return falha
    documento_id = clicksign_service.add_document(envelope_id, pdf, f"Termo_de_Adesao_{sigla}_{envio_id}.pdf")
    if not documento_id:
        return falha
    signatario_id = clicksign_service.add_signer(envelope_id, nome=pessoa["nome_completo"], email=pessoa["email"])
    if not signatario_id:
        return falha
    if not clicksign_service.create_qualification_requirement(envelope_id, documento_id, signatario_id):
        return falha
    if not clicksign_service.create_auth_requirement(envelope_id, documento_id, signatario_id):
        return falha
    if not clicksign_service.activate_envelope(envelope_id):
        return falha
    # A própria assinatura eletrônica também avisa; falhar aqui não derruba um
    # envelope já ativo (como nos POPs e nas Atas).
    clicksign_service.notify_signers(envelope_id)
    return envelope_id, documento_id


def gerar_e_enviar_termo(
    supabase,
    participacao: dict,
    *,
    autor_id: str,
    acao: str = "termo_enviado",
    colegiado: Colegiado = permissao.NUCLEO,
) -> dict:
    """Gera o documento e o envia para a assinatura. Devolve o envio gravado.

    Sem Regimento vigente ou sem e-mail, nada é gerado e sobe `TermoNaoGeradoError`.
    Falha da assinatura eletrônica deixa o envio em "gerado", com o erro, e a
    Participação em Documento gerado: o reenvio tenta de novo.
    """
    regimento = _vigente(supabase, "regimento", colegiado=colegiado)
    if not regimento:
        raise TermoNaoGeradoError("Publique o Regimento em Documentos para gerar o Termo de Adesão.")
    pessoa = _pessoa(supabase, participacao["participante_id"])
    if not pessoa.get("email"):
        raise TermoNaoGeradoError("A pessoa não tem e-mail no cadastro, e o Termo vai por e-mail para assinatura.")

    envio = (
        supabase.table(colegiado.termos_envios)
        .insert({"participacao_id": participacao["id"], "regimento_id": regimento["id"], "situacao": "gerado"})
        .execute()
        .data
    )[0]
    designacao = _vigente(supabase, "ato_designacao", colegiado=colegiado)
    dados = dados_do_termo(pessoa, participacao, regimento, designacao, envio["id"], colegiado=colegiado)
    pdf = gerar_pdf_do_termo(dados)
    caminho = f"termos/{envio['id']}.pdf"
    arquivo = caminho if storage.upload_private(supabase, _bucket(colegiado), caminho, pdf, "application/pdf") else None
    supabase.table("participacoes").update({"termo_gerado_em": _agora(), "termo_enviado_em": None}).eq(
        "id", participacao["id"]
    ).execute()

    resultado = _enviar(pdf, envio["id"], pessoa, colegiado.sigla)
    if isinstance(resultado, str):
        logger.warning("Termo %s gerado e não enviado: %s", envio["id"], resultado)
        campos = {"arquivo_path": arquivo, "erro": resultado}
    else:
        envelope_id, documento_key = resultado
        agora = _agora()
        campos = {
            "arquivo_path": arquivo,
            "erro": None,
            "situacao": "enviado",
            "envelope_id": envelope_id,
            "documento_key": documento_key,
            "enviado_em": agora,
        }
        supabase.table("participacoes").update({"termo_enviado_em": agora}).eq("id", participacao["id"]).execute()
        _trilha(supabase, participacao["id"], autor_id, acao, valor_novo=envio["id"])
    supabase.table(colegiado.termos_envios).update(campos).eq("id", envio["id"]).execute()
    return {**envio, **campos}


# ---------------------------------------------------------------------------
# O retorno da assinatura
# ---------------------------------------------------------------------------


def _proxima_versao_do_termo(supabase, colegiado: Colegiado) -> int:
    linhas = (
        supabase.table(colegiado.documentos)
        .select("versao")
        .eq("tipo", "termo")
        .order("versao", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    return int(linhas[0]["versao"]) + 1 if linhas else 1


def _guardar_documento_assinado(supabase, envio: dict, colegiado: Colegiado) -> None:
    """O PDF assinado nos Documentos, uma vez por envio. Best-effort: sem o
    arquivo pronto, o próximo evento (ou a reconsulta) tenta de novo."""
    ja = supabase.table(colegiado.documentos).select("id").eq("termo_envio_id", envio["id"]).limit(1).execute().data
    if ja:
        return
    pdf = clicksign_service.get_signed_document(envio.get("envelope_id"))
    if not pdf:
        logger.warning("PDF assinado do Termo %s ainda indisponível", envio["id"])
        return
    caminho = f"termos/{envio['id']}-assinado.pdf"
    if not storage.upload_private(supabase, _bucket(colegiado), caminho, pdf, "application/pdf"):
        return
    participacao = _participacao(supabase, envio["participacao_id"])
    pessoa = _pessoa(supabase, participacao["participante_id"])
    titulo = sanitizar_estrutura(
        f"Termo de Adesão de {pessoa.get('nome_completo')}, vigência de "
        f"{_dia(participacao['vigencia_inicio'])} a {_dia(participacao['vigencia_fim'])}"
    )[:200]
    try:
        supabase.table(colegiado.documentos).insert(
            {
                "tipo": "termo",
                "versao": _proxima_versao_do_termo(supabase, colegiado),
                "titulo": titulo,
                "vigente": False,
                "arquivo_assinado_path": caminho,
                "publicado_por": participacao["participante_id"],
                "termo_envio_id": envio["id"],
            }
        ).execute()
    except (APIError, httpx.HTTPError) as erro:
        # Dois retornos ao mesmo tempo: o UNIQUE do envio segura o segundo.
        logger.warning("Termo assinado %s não entrou nos Documentos agora: %s", envio["id"], erro)


def aplicar_assinatura(supabase, envio: dict, *, colegiado: Colegiado = permissao.NUCLEO) -> bool:
    """Carimba a assinatura. Só o envio ainda "enviado" muda: a troca é
    condicional, e o retorno repetido ou atrasado não acha mais nada."""
    agora = _agora()
    trocados = (
        supabase.table(colegiado.termos_envios)
        .update({"situacao": "assinado", "assinado_em": agora})
        .eq("id", envio["id"])
        .eq("situacao", "enviado")
        .execute()
        .data
    ) or []
    if not trocados:
        return False
    participacao = _participacao(supabase, envio["participacao_id"])
    supabase.table("participacoes").update({"termo_assinado_em": agora}).eq("id", participacao["id"]).execute()
    _trilha(supabase, participacao["id"], participacao["participante_id"], "termo_assinado", valor_novo=envio["id"])
    _guardar_documento_assinado(supabase, {**envio, "situacao": "assinado"}, colegiado)
    return True


def _completar_carimbo(supabase, envio: dict) -> None:
    """O envio já está assinado, mas o carimbo da Participação pode ter
    falhado depois da troca. Carimba só se ainda falta: a troca é condicional,
    e o retorno repetido não grava a trilha duas vezes."""
    participacao = _participacao(supabase, envio["participacao_id"])
    if not novo_termo_pendente(participacao):
        return
    anterior = participacao.get("termo_assinado_em")
    # O Termo antigo, já carimbado, não fecha o novo que ainda não saiu.
    if anterior and envio.get("assinado_em") and not _depois(envio["assinado_em"], anterior):
        return
    consulta = (
        supabase.table("participacoes")
        .update({"termo_assinado_em": envio.get("assinado_em") or _agora()})
        .eq("id", participacao["id"])
    )
    # Troca condicional: só carimba sobre o valor que leu (vazio, ou a
    # assinatura do Termo anterior), e o retorno repetido não acha mais nada.
    consulta = consulta.eq("termo_assinado_em", anterior) if anterior else consulta.is_("termo_assinado_em", "null")
    carimbadas = (consulta.execute().data) or []
    if carimbadas:
        _trilha(supabase, participacao["id"], participacao["participante_id"], "termo_assinado", valor_novo=envio["id"])


def processar_evento(supabase, envio: dict, evento: str, *, colegiado: Colegiado = permissao.NUCLEO) -> None:
    """O mesmo tratamento para o webhook e para a reconsulta."""
    if envio.get("situacao") == "enviado" and evento in EVENTOS_DE_ASSINATURA:
        aplicar_assinatura(supabase, envio, colegiado=colegiado)
    elif envio.get("situacao") == "assinado" and (evento in EVENTOS_DE_ASSINATURA or evento == EVENTO_DOCUMENTO_PRONTO):
        _completar_carimbo(supabase, envio)
        _guardar_documento_assinado(supabase, envio, colegiado)
    else:
        logger.info("Evento %r do Termo %s (%s) sem efeito", evento, envio.get("id"), envio.get("situacao"))


# ---------------------------------------------------------------------------
# Reconsultar, reenviar, liberar
# ---------------------------------------------------------------------------


class AssinaturaIndisponivelError(Exception):
    """A assinatura eletrônica não respondeu à reconsulta."""


def reconsultar(supabase, participacao: dict, *, colegiado: Colegiado = permissao.NUCLEO) -> dict | None:
    """Pergunta à assinatura eletrônica como está o último envio e aplica o
    mesmo tratamento do retorno automático. None quando não há envio."""
    envio = ultimo_envio(supabase, participacao["id"], colegiado=colegiado)
    if not envio or not envio.get("envelope_id"):
        return None
    status = clicksign_service.get_envelope_status(envio["envelope_id"])
    if status is None:
        raise AssinaturaIndisponivelError()
    if status == "closed":
        processar_evento(supabase, envio, "auto_close", colegiado=colegiado)
    return envio


def novo_termo(
    supabase,
    participacao: dict,
    *,
    autor_id: str,
    acao: str = "termo_enviado",
    colegiado: Colegiado = permissao.NUCLEO,
) -> dict:
    """Cancela o envio aberto (o link antigo morre) e gera outro, com outro
    identificador. O retorno do envelope cancelado não muda mais nada.

    A assinatura anterior fica onde está: o membro que já era Ativo segue as
    regras de estado e de carência até assinar o novo (issue #1769)."""
    for envio in envios_abertos(supabase, participacao["id"], colegiado=colegiado):
        if envio.get("envelope_id"):
            clicksign_service.cancel_envelope(envio["envelope_id"])
        supabase.table(colegiado.termos_envios).update({"situacao": "cancelado", "cancelado_em": _agora()}).eq(
            "id", envio["id"]
        ).execute()
    return gerar_e_enviar_termo(supabase, participacao, autor_id=autor_id, acao=acao, colegiado=colegiado)


# Quem assina de novo quando o Regimento muda de conteúdo (anexo E da
# especificação): os membros que contam para quórum.
ESTADOS_DA_REVISAO_MATERIAL = frozenset({"ativo", "a_vencer", "em_carencia"})


def termos_da_revisao_material(supabase, *, autor_id: str, colegiado: Colegiado = permissao.NUCLEO) -> None:
    """Novo Termo, com o Regimento que acabou de ser publicado, para cada
    membro em Ativo, A vencer e Em carência (issue #1769). Roda depois da
    resposta da publicação: falha num membro vai para o log e não impede os
    outros. A pendência vem da data da revisão (`novo_termo_pendente`), não
    do documento: a ficha de quem falhou tem o reenvio, mesmo se tudo falhar
    antes do primeiro membro."""
    try:
        colegiado_id = colegiados.id_do_colegiado(supabase, colegiado)
        if not colegiado_id:
            return
        hoje = permissao.hoje_em_sao_paulo()
        participacoes = ler_tudo(
            lambda: (
                supabase.table("participacoes")
                .select(
                    "id, participante_id, papel, area, vigencia_inicio, vigencia_fim, encerrada_em, "
                    "termo_gerado_em, termo_enviado_em, termo_assinado_em"
                )
                .eq("colegiado_id", colegiado_id)
                .is_("encerrada_em", "null")
                .order("id")
            ),
            rotulo=f"participações do {colegiado.nome}",
        )
    except Exception:  # noqa: BLE001 (depois da resposta: o log e o reenvio da ficha)
        logger.exception("Termos da revisão do Regimento não gerados: a leitura dos membros falhou")
        return
    for participacao in participacoes:
        if estado_do_membro(participacao, hoje) not in ESTADOS_DA_REVISAO_MATERIAL:
            continue
        try:
            novo_termo(supabase, participacao, autor_id=autor_id, colegiado=colegiado)
        except TermoNaoGeradoError as erro:
            logger.warning("Termo da revisão do Regimento não gerado para %s: %s", participacao["id"], erro)
        except Exception:  # noqa: BLE001 (um membro não segura os outros)
            logger.exception("Termo da revisão do Regimento falhou para %s", participacao["id"])


def reenviar_termo(supabase, participacao: dict, *, autor_id: str, colegiado: Colegiado = permissao.NUCLEO) -> dict:
    """O reenvio da ficha: outro documento, com outro identificador."""
    return novo_termo(supabase, participacao, autor_id=autor_id, acao="termo_reenviado", colegiado=colegiado)


def liberar(supabase, participacao: dict, *, autor_id: str, justificativa: str) -> None:
    """Liberação manual: o membro fica Ativo sem a assinatura, e a trilha
    guarda quem liberou, quando e por quê."""
    agora = _agora()
    supabase.table("participacoes").update({"termo_assinado_em": agora}).eq("id", participacao["id"]).execute()
    _trilha(supabase, participacao["id"], autor_id, "liberacao_manual", valor_novo=agora, motivo=justificativa)


def link_do_documento(supabase, envio: dict | None, *, colegiado: Colegiado = permissao.NUCLEO) -> str | None:
    if not envio or not envio.get("arquivo_path"):
        return None
    return storage.signed_url(supabase, _bucket(colegiado), envio["arquivo_path"], VALIDADE_DO_LINK)
