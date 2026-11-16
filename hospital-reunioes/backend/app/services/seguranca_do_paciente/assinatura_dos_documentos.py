"""A assinatura eletrônica dos documentos do Núcleo (issue #1771, PRD #1764, ADR 0095).

O ato de designação vai para a Diretoria Executiva (quem tem o Acesso pleno ao
NSP, nominal, do Diretor Executivo); o Regimento e o Plano de Segurança do
Paciente vão para a Diretoria Executiva e para a Presidência vigente do Núcleo.
Um envelope por envio, com um signatário por pessoa, sobre as mesmas
primitivas que os POPs, as Reuniões e o Termo de Adesão usam
(`clicksign_service`).

A versão enviada nasce fora da vigência (`nsp_versao_para_assinatura`, migration
159): a anterior continua valendo. Ela só vira a vigente quando todas as
assinaturas chegam (`nsp_tornar_vigente`), e o PDF assinado fica guardado na
própria versão. O retorno da assinatura (o webhook) e o "Reconsultar status" da
tela passam pelo mesmo tratamento; evento repetido não duplica nada, envio
cancelado (pelo reenvio ou por uma versão mais nova) não muda nada.
"""

from __future__ import annotations

import io
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime

from app.config import settings
from app.services import clicksign_service, storage
from app.services.seguranca_do_paciente.permissao import (
    PERFIL_ACESSO_PLENO,
    hoje_em_sao_paulo,
    id_do_nucleo,
    participacoes_vigentes,
)
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

# Quem assina cada tipo, na ordem em que entram no envelope.
SIGNATARIOS_POR_TIPO: dict[str, tuple[str, ...]] = {
    "ato_designacao": ("diretoria_executiva",),
    "regimento": ("diretoria_executiva", "presidencia"),
    "plano_seguranca_paciente": ("diretoria_executiva", "presidencia"),
}

ROTULO_DO_TIPO = {
    "ato_designacao": "Ato de designação",
    "regimento": "Regimento Interno",
    "plano_seguranca_paciente": "Plano de Segurança do Paciente",
}

ROTULO_DA_QUALIDADE = {"diretoria_executiva": "Diretoria Executiva", "presidencia": "Presidência do Núcleo"}

# `auto_close` só chega com todas as assinaturas; `close` e `deadline` podem
# fechar o envelope com assinatura faltando, e não trocam a vigente.
EVENTOS_DE_TODOS_ASSINARAM = frozenset({"auto_close", "AutoClose"})
EVENTO_DE_UMA_ASSINATURA = "sign"
EVENTO_DOCUMENTO_PRONTO = "document_closed"

ABERTAS = ("gerado", "enviado")

# O link do arquivo assinado vale 10 minutos.
VALIDADE_DO_LINK = 600

_FALHA_DO_ENVIO = "A assinatura eletrônica não respondeu. Use Reenviar para assinatura em instantes."

# Quem chama o retorno da assinatura agenda o Termo novo dos membros quando a
# revisão material do Regimento vigora (issue #1800); recebe o autor do envio.
AoVigorar = Callable[[str | None], None]


class AssinaturaNaoEnviadaError(Exception):
    """Faltou signatário: nada foi criado. A mensagem vai para a tela."""


class AssinaturaIndisponivelError(Exception):
    """A assinatura eletrônica não respondeu à reconsulta."""


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _bucket() -> str:
    return settings.supabase_storage_bucket_nsp_documentos


# ---------------------------------------------------------------------------
# Quem assina
# ---------------------------------------------------------------------------


def _diretoria_executiva(supabase) -> list[dict]:
    return (
        supabase.table("participantes")
        .select("id, nome_completo, email")
        .eq("perfil_nsp", PERFIL_ACESSO_PLENO)
        .eq("ativo", True)
        .order("nome_completo")
        .execute()
        .data
    ) or []


def _presidencia(supabase) -> list[dict]:
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return []
    ids = [
        linha["participante_id"]
        for linha in (
            participacoes_vigentes(supabase, nucleo_id, hoje_em_sao_paulo()).eq("papel", "presidencia").execute().data
            or []
        )
    ]
    if not ids:
        return []
    return (
        supabase.table("participantes")
        .select("id, nome_completo, email")
        .in_("id", sorted(set(ids)))
        .eq("ativo", True)
        .order("nome_completo")
        .execute()
        .data
    ) or []


_FALTA = {
    "diretoria_executiva": "Não há Diretoria Executiva (Acesso pleno ao NSP) cadastrada para assinar.",
    "presidencia": "Não há Presidência vigente no Núcleo para assinar.",
}


def signatarios_do_tipo(supabase, tipo: str) -> list[dict]:
    """Quem assina o tipo agora, um por pessoa: [{participante_id, qualidade,
    nome, email}]. Sem alguém de uma das qualidades, ou sem e-mail, sobe
    `AssinaturaNaoEnviadaError` antes de qualquer gravação."""
    buscar = {"diretoria_executiva": _diretoria_executiva, "presidencia": _presidencia}
    signatarios: list[dict] = []
    vistos: set[str] = set()
    for qualidade in SIGNATARIOS_POR_TIPO[tipo]:
        pessoas = buscar[qualidade](supabase)
        if not pessoas:
            raise AssinaturaNaoEnviadaError(_FALTA[qualidade])
        for pessoa in pessoas:
            if pessoa["id"] in vistos:
                continue
            if not (pessoa.get("email") or "").strip():
                raise AssinaturaNaoEnviadaError(
                    f"{pessoa.get('nome_completo')} não tem e-mail no cadastro, "
                    "e o documento vai por e-mail para assinatura."
                )
            vistos.add(pessoa["id"])
            signatarios.append(
                {
                    "participante_id": pessoa["id"],
                    "qualidade": qualidade,
                    "nome": pessoa.get("nome_completo") or "",
                    "email": pessoa["email"].strip(),
                }
            )
    return signatarios


# ---------------------------------------------------------------------------
# O documento
# ---------------------------------------------------------------------------


def _pdf(documento: dict, signatarios: list[dict], envio_id: str) -> bytes:
    """O PDF da versão (WeasyPrint, como a Ata, o POP e o Termo). O texto vem
    de quem digitou e passa pelo sanitizador: o PDF não sai com travessão."""
    from weasyprint import HTML

    from app.services.pdf_generator import env
    from app.services.pdf_url_fetcher import criar_pdf_url_fetcher

    dados = sanitizar_estrutura(
        {
            "documento": {
                "tipo": ROTULO_DO_TIPO.get(documento["tipo"], documento["tipo"]),
                "titulo": documento.get("titulo") or "",
                "versao": documento.get("versao"),
                "texto": documento.get("texto") or "",
                "identificador": envio_id,
            },
            "signatarios": [{"qualidade": ROTULO_DA_QUALIDADE[s["qualidade"]], "nome": s["nome"]} for s in signatarios],
        }
    )
    base = os.path.join(os.path.dirname(__file__), "..", "..", "static")
    logo_path = os.path.abspath(os.path.join(base, "images", "logo_hospital.png"))
    font_path = os.path.abspath(os.path.join(base, "fonts", "HPSimplified_Rg.ttf"))
    logo_uri = f"file://{logo_path}" if os.path.exists(logo_path) else None
    font_uri = f"file://{font_path}" if os.path.exists(font_path) else None

    html = env.get_template("nsp_documento_para_assinatura.html").render(
        **dados, logo_path=logo_uri, font_path=font_uri
    )
    alvo = io.BytesIO()
    permitidos = frozenset(uri for uri in (logo_uri, font_uri) if uri)
    HTML(string=html, url_fetcher=criar_pdf_url_fetcher(permitidos)).write_pdf(target=alvo)
    return alvo.getvalue()


def _mandar_envelope(pdf: bytes, documento: dict, envio_id: str, signatarios: list[dict]) -> tuple | None:
    """O envelope com o documento e os signatários. Devolve (envelope, chave do
    documento, {participante: id do signatário}) ou None em falha."""
    rotulo = ROTULO_DO_TIPO.get(documento["tipo"], documento["tipo"])
    envelope_id = clicksign_service.create_envelope(f"{rotulo} v{documento['versao']} NSP - {envio_id}")
    if not envelope_id:
        return None
    documento_key = clicksign_service.add_document(
        envelope_id, pdf, f"{documento['tipo']}_v{documento['versao']}_NSP_{envio_id}.pdf"
    )
    if not documento_key:
        return None
    ids: dict[str, str] = {}
    for signatario in signatarios:
        signatario_id = clicksign_service.add_signer(envelope_id, nome=signatario["nome"], email=signatario["email"])
        if not signatario_id:
            return None
        if not clicksign_service.create_qualification_requirement(envelope_id, documento_key, signatario_id):
            return None
        if not clicksign_service.create_auth_requirement(envelope_id, documento_key, signatario_id):
            return None
        ids[signatario["participante_id"]] = signatario_id
    if not clicksign_service.activate_envelope(envelope_id):
        return None
    # A própria assinatura eletrônica também avisa; falhar aqui não derruba um
    # envelope já ativo (como nos POPs, nas Atas e no Termo).
    clicksign_service.notify_signers(envelope_id)
    return envelope_id, documento_key, ids


def _cancelar(supabase, envios: list[dict]) -> None:
    for envio in envios:
        if envio.get("envelope_id"):
            clicksign_service.cancel_envelope(envio["envelope_id"])
        supabase.table("nsp_documentos_envios").update({"situacao": "cancelado", "cancelado_em": _agora()}).eq(
            "id", envio["id"]
        ).execute()


def _abertos(supabase, documento_ids: list[str]) -> list[dict]:
    if not documento_ids:
        return []
    return (
        supabase.table("nsp_documentos_envios")
        .select("*")
        .in_("documento_id", documento_ids)
        .in_("situacao", list(ABERTAS))
        .execute()
        .data
    ) or []


def _novo_envio(supabase, documento: dict, signatarios: list[dict], autor_id: str) -> dict:
    """Grava o envio e os signatários e manda o envelope. Falha da assinatura
    eletrônica deixa o envio em "gerado", com o erro: o reenvio tenta de novo."""
    envio = (
        supabase.table("nsp_documentos_envios")
        .insert({"documento_id": documento["id"], "situacao": "gerado", "autor_id": autor_id})
        .execute()
        .data
    )[0]
    supabase.table("nsp_documentos_signatarios").insert(
        [
            {"envio_id": envio["id"], "participante_id": s["participante_id"], "qualidade": s["qualidade"]}
            for s in signatarios
        ]
    ).execute()

    try:
        resultado = _mandar_envelope(_pdf(documento, signatarios, envio["id"]), documento, envio["id"], signatarios)
    except Exception as erro:  # noqa: BLE001 - o envio fica de pé, com o reenvio na tela
        logger.warning("Envio %s do documento %s falhou: %s", envio["id"], documento["id"], erro)
        resultado = None

    if resultado is None:
        campos = {"erro": _FALHA_DO_ENVIO}
    else:
        envelope_id, documento_key, ids = resultado
        campos = {
            "erro": None,
            "situacao": "enviado",
            "envelope_id": envelope_id,
            "documento_key": documento_key,
            "enviado_em": _agora(),
        }
        for participante_id, signatario_id in ids.items():
            supabase.table("nsp_documentos_signatarios").update({"signatario_id": signatario_id}).eq(
                "envio_id", envio["id"]
            ).eq("participante_id", participante_id).execute()
    supabase.table("nsp_documentos_envios").update(campos).eq("id", envio["id"]).execute()
    return {**envio, **campos}


def enviar_versao_para_assinatura(
    supabase, *, tipo: str, titulo: str, texto: str, natureza_revisao: str | None, autor_id: str
) -> tuple[dict, dict]:
    """Grava a versão seguinte do tipo, fora da vigência, e a manda para os
    signatários do tipo. A versão que esperava assinatura no mesmo tipo tem o
    envio cancelado: vale a mais nova."""
    signatarios = signatarios_do_tipo(supabase, tipo)
    do_tipo = supabase.table("nsp_documentos").select("id").eq("tipo", tipo).execute().data or []
    _cancelar(supabase, _abertos(supabase, [linha["id"] for linha in do_tipo]))
    novo = (
        supabase.rpc(
            "nsp_versao_para_assinatura",
            {
                "p_tipo": tipo,
                "p_titulo": titulo,
                "p_texto": texto,
                "p_natureza_revisao": natureza_revisao,
                "p_publicado_por": autor_id,
            },
        )
        .execute()
        .data
    )
    documento = novo[0] if isinstance(novo, list) else novo
    return documento, _novo_envio(supabase, documento, signatarios, autor_id)


def refazer_envio(supabase, documento: dict, *, autor_id: str) -> dict:
    """Cancela o envio aberto da versão (o link antigo morre) e manda outro,
    com os signatários de agora."""
    signatarios = signatarios_do_tipo(supabase, documento["tipo"])
    _cancelar(supabase, _abertos(supabase, [documento["id"]]))
    return _novo_envio(supabase, documento, signatarios, autor_id)


# ---------------------------------------------------------------------------
# O retorno da assinatura
# ---------------------------------------------------------------------------


def _signatarios_do_envio(supabase, envio_id: str) -> list[dict]:
    return supabase.table("nsp_documentos_signatarios").select("*").eq("envio_id", envio_id).execute().data or []


def _marcar(supabase, linha: dict, quando: str | None) -> None:
    supabase.table("nsp_documentos_signatarios").update({"assinado_em": quando or _agora()}).eq("id", linha["id"]).is_(
        "assinado_em", "null"
    ).execute()


def _achar_signatario(supabase, linhas: list[dict], *, chave: str | None, email: str | None) -> dict | None:
    if chave:
        achado = next((linha for linha in linhas if linha.get("signatario_id") == chave), None)
        if achado:
            return achado
    email = (email or "").strip().lower()
    if not email:
        return None
    pessoas = (
        supabase.table("participantes")
        .select("id, email")
        .in_("id", [linha["participante_id"] for linha in linhas])
        .execute()
        .data
    ) or []
    ids = {p["id"] for p in pessoas if (p.get("email") or "").strip().lower() == email}
    return next((linha for linha in linhas if linha["participante_id"] in ids), None)


def _ler_envio(supabase, envio_id: str) -> dict:
    return supabase.table("nsp_documentos_envios").select("*").eq("id", envio_id).limit(1).execute().data[0]


def _documento(supabase, documento_id: str) -> dict:
    return (
        supabase.table("nsp_documentos")
        .select("id, tipo, versao, vigente, arquivo_assinado_path")
        .eq("id", documento_id)
        .limit(1)
        .execute()
        .data
    )[0]


def _guardar_arquivo(supabase, envio: dict) -> None:
    """O PDF assinado na própria versão, uma vez. Best-effort: sem o arquivo
    pronto, o `document_closed` (ou a reconsulta) tenta de novo."""
    if _documento(supabase, envio["documento_id"]).get("arquivo_assinado_path"):
        return
    pdf = clicksign_service.get_signed_document(envio.get("envelope_id"))
    if not pdf:
        logger.warning("PDF assinado do envio %s ainda indisponível", envio["id"])
        return
    caminho = f"documentos/{envio['documento_id']}-assinado.pdf"
    if not storage.upload_private(supabase, _bucket(), caminho, pdf, "application/pdf"):
        return
    supabase.table("nsp_documentos").update({"arquivo_assinado_path": caminho}).eq("id", envio["documento_id"]).is_(
        "arquivo_assinado_path", "null"
    ).execute()


def _concluir(
    supabase, envio: dict, *, todos_assinaram: bool = False, ao_vigorar_revisao_material: AoVigorar | None = None
) -> None:
    """Todas as assinaturas chegaram: o envio vira "assinado" (troca
    condicional, o retorno repetido não acha mais nada), a versão vira a
    vigente e o arquivo assinado fica guardado nela. Com o envio já assinado,
    só completa o que faltou (a vigência ou o arquivo).

    A revisão material do Regimento que esta chamada tornou vigente avisa
    `ao_vigorar_revisao_material` com o autor do envio (issue #1800): o
    Termo novo dos membros sai uma vez por versão, como no Publicar. O
    retorno repetido acha a versão já vigente e não avisa de novo."""
    if envio.get("situacao") == "enviado":
        agora = _agora()
        if todos_assinaram:
            for linha in _signatarios_do_envio(supabase, envio["id"]):
                if not linha.get("assinado_em"):
                    _marcar(supabase, linha, agora)
        supabase.table("nsp_documentos_envios").update({"situacao": "assinado", "assinado_em": agora}).eq(
            "id", envio["id"]
        ).eq("situacao", "enviado").execute()
        envio = _ler_envio(supabase, envio["id"])
    if envio.get("situacao") != "assinado":
        return
    ja_vigente = _documento(supabase, envio["documento_id"]).get("vigente")
    vigente = supabase.rpc("nsp_tornar_vigente", {"p_documento_id": envio["documento_id"]}).execute().data
    vigente = (vigente[0] if vigente else None) if isinstance(vigente, list) else vigente
    # Sem versão de volta (uma mais nova já vale), o PostgREST devolve a
    # linha com tudo nulo: o id não bate e nada vigorou.
    if (
        ao_vigorar_revisao_material
        and not ja_vigente
        and vigente
        and vigente.get("id") == envio["documento_id"]
        and vigente.get("vigente")
        and vigente.get("tipo") == "regimento"
        and vigente.get("natureza_revisao") == "material"
    ):
        ao_vigorar_revisao_material(envio.get("autor_id"))
    _guardar_arquivo(supabase, envio)


def _todos_assinaram(supabase, envio_id: str) -> bool:
    linhas = _signatarios_do_envio(supabase, envio_id)
    return bool(linhas) and all(linha.get("assinado_em") for linha in linhas)


def tratar_retorno_da_versao(
    supabase,
    envio: dict,
    evento: str,
    signatario: dict | None = None,
    *,
    ao_vigorar_revisao_material: AoVigorar | None = None,
) -> None:
    """O retorno automático da assinatura para o envelope de uma versão."""
    situacao = envio.get("situacao")
    if situacao not in ("enviado", "assinado"):
        logger.info("Evento %r do envio %s (%s) sem efeito", evento, envio.get("id"), situacao)
        return
    if evento == EVENTO_DE_UMA_ASSINATURA:
        if situacao == "enviado":
            signatario = signatario or {}
            linha = _achar_signatario(
                supabase,
                _signatarios_do_envio(supabase, envio["id"]),
                chave=signatario.get("key"),
                email=signatario.get("email"),
            )
            if linha is None:
                logger.warning("Evento 'sign' do envio %s sem signatário conhecido", envio["id"])
                return
            _marcar(supabase, linha, signatario.get("occurred_at"))
            if not _todos_assinaram(supabase, envio["id"]):
                return
        _concluir(supabase, envio, ao_vigorar_revisao_material=ao_vigorar_revisao_material)
    elif evento in EVENTOS_DE_TODOS_ASSINARAM:
        _concluir(
            supabase, envio, todos_assinaram=True, ao_vigorar_revisao_material=ao_vigorar_revisao_material
        )
    elif evento == EVENTO_DOCUMENTO_PRONTO and situacao == "assinado":
        _concluir(supabase, envio, ao_vigorar_revisao_material=ao_vigorar_revisao_material)
    else:
        logger.info("Evento %r do envio %s sem efeito", evento, envio["id"])


# ---------------------------------------------------------------------------
# Reconsultar e a tela
# ---------------------------------------------------------------------------


def ultimo_envio(supabase, documento_id: str) -> dict | None:
    linhas = (
        supabase.table("nsp_documentos_envios")
        .select("*")
        .eq("documento_id", documento_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    return linhas[0] if linhas else None


def reconsultar_assinaturas(supabase, documento: dict) -> dict | None:
    """Pergunta à assinatura eletrônica quem já assinou o último envio e aplica
    o mesmo tratamento do retorno automático. None quando não há envelope."""
    envio = ultimo_envio(supabase, documento["id"])
    if not envio or not envio.get("envelope_id"):
        return None
    if envio.get("situacao") in ("enviado", "assinado"):
        assinaturas = clicksign_service.list_signers(envio["envelope_id"])
        if assinaturas is None:
            raise AssinaturaIndisponivelError()
        linhas = _signatarios_do_envio(supabase, envio["id"])
        for assinou in assinaturas:
            if assinou.get("status") != "signed":
                continue
            linha = _achar_signatario(supabase, linhas, chave=assinou.get("signer_id"), email=assinou.get("email"))
            if linha and not linha.get("assinado_em"):
                _marcar(supabase, linha, assinou.get("signed_at"))
        if _todos_assinaram(supabase, envio["id"]):
            _concluir(supabase, envio)
    return _ler_envio(supabase, envio["id"])


def pode_reenviar(documento: dict, envio: dict | None, mais_nova: bool) -> bool:
    """A versão que espera assinatura aceita um envio novo; a vigente, a já
    assinada e a que tem versão mais nova no tipo, não."""
    if documento.get("vigente") or mais_nova or documento.get("tipo") not in SIGNATARIOS_POR_TIPO:
        return False
    return not envio or envio.get("situacao") != "assinado"


def tem_versao_mais_nova(supabase, documento: dict) -> bool:
    return bool(
        supabase.table("nsp_documentos")
        .select("id")
        .eq("tipo", documento["tipo"])
        .gte("versao", documento["versao"] + 1)
        .limit(1)
        .execute()
        .data
    )


def situacao_do_envio(supabase, documento: dict, envio: dict, *, mais_nova: bool, nomes: dict | None = None) -> dict:
    """O que a tela mostra do envio de uma versão. Sem e-mail."""
    linhas = _signatarios_do_envio(supabase, envio["id"])
    if nomes is None:
        nomes = _nomes(supabase, {linha["participante_id"] for linha in linhas})
    return {
        "documento_id": documento["id"],
        "situacao": envio.get("situacao"),
        "erro": envio.get("erro"),
        "enviado_em": envio.get("enviado_em"),
        "assinado_em": envio.get("assinado_em"),
        "pode_reenviar": pode_reenviar(documento, envio, mais_nova),
        "signatarios": [
            {
                "nome": nomes.get(linha["participante_id"]),
                "qualidade": linha["qualidade"],
                "assinado_em": linha.get("assinado_em"),
            }
            for linha in sorted(linhas, key=lambda linha: list(ROTULO_DA_QUALIDADE).index(linha["qualidade"]))
        ],
    }


def _nomes(supabase, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    linhas = supabase.table("participantes").select("id, nome_completo").in_("id", sorted(ids)).execute().data or []
    return {linha["id"]: linha.get("nome_completo") for linha in linhas}


def situacao_das_assinaturas(supabase) -> list[dict]:
    """O último envio de cada versão dos tipos assinados, para a tela."""
    documentos = (
        supabase.table("nsp_documentos")
        .select("id, tipo, versao, vigente")
        .in_("tipo", list(SIGNATARIOS_POR_TIPO))
        .execute()
        .data
    ) or []
    maior = {}
    for documento in documentos:
        maior[documento["tipo"]] = max(maior.get(documento["tipo"], 0), documento["versao"])
    resposta = []
    for documento in documentos:
        envio = ultimo_envio(supabase, documento["id"])
        if envio:
            mais_nova = documento["versao"] < maior[documento["tipo"]]
            resposta.append(situacao_do_envio(supabase, documento, envio, mais_nova=mais_nova))
    return resposta


def link_do_arquivo_assinado(supabase, documento: dict) -> str | None:
    if not documento.get("arquivo_assinado_path"):
        return None
    return storage.signed_url(supabase, _bucket(), documento["arquivo_assinado_path"], VALIDADE_DO_LINK)
