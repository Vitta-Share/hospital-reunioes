"""O termo de declaração redigido pelo agente (issue #1831; especificação, 7.1
e Anexos C e E.1; ADR 0097, decisão 7).

Depois de um clique de quem conduziu, o agente do Anexo C redige as
declarações a partir da transcrição (ou dos pontos digitados, quando não houve
gravação). O resto do termo é do sistema: a identificação, a frase da
gravação, o encerramento, os compromissos, o rodapé e as assinaturas.

Nenhum nome vai à IA: os nomes viram marcadores numerados na ida e voltam a
ser nomes aqui (`marcadores`). As "Notas para quem apura" saem junto, marcadas
como Sugestão, e nunca entram no PDF.

Cada correção lançada é uma versão nova do termo; a anterior fica. "IMPRIMIR
TERMO" gera o PDF da última versão, no modelo do Anexo E.1. O agente também
sugere o roteiro de perguntas, por clique. Nenhum job chama estas IAs.

Toda ação grava a sua linha na trilha antes de mudar qualquer coisa.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from app.services import ai_processor, storage
from app.services.conduta import assinaturas, cifra, depoimentos, impedimento, membros, trilha
from app.services.conduta.acesso import hoje_em_sao_paulo
from app.services.conduta.depoimentos import DepoimentoRecusadoError
from app.services.conduta.marcadores import Marcacao
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc
from app.services.prompt_loader import load_prompt
from app.services.transcricao_extractor import extrair_texto
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

TABELA = depoimentos.TERMOS
# Os agentes do Canal usam o mesmo modelo (ADR 0097, decisão 6).
MODELO_DE_IA = "claude-sonnet-5-5"
PROMPT_DO_TERMO = "conduta_termo_de_declaracao"
PROMPT_DO_ROTEIRO = "conduta_roteiro_de_perguntas"
MODELO_DO_PDF = "conduta_termo_de_declaracao.html"

AGENTE_FORA = "O agente não conseguiu responder agora. Tente de novo em instantes."

GRAVADA = "Esta conversa foi gravada com meu consentimento."
SEM_GRAVACAO = "Não houve gravação. Os pontos da conversa foram registrados por quem conduziu."
CONFIRMAR_CONSENTIMENTO = "[confirmar: o consentimento para gravar foi dado no início da conversa]"

_TAMANHO_DA_LINHA = 200
_TAMANHO_DO_PARAGRAFO = 4000
_ITENS = 60
_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class AgenteIndisponivelError(Exception):
    """O agente não respondeu, ou respondeu fora do formato."""


# ── O agente ────────────────────────────────────────────────────────────────


def _cliente_do_agente_do_termo():
    if ai_processor._llm_provider() == "mock":
        raise AgenteIndisponivelError("IA sem chave configurada")
    cliente, _modelo_geral = ai_processor._get_llm()
    return cliente


def _pedir_ao_agente_do_canal_de_conduta(prompt: str, usuario: str) -> dict[str, Any]:
    """Uma chamada ao agente. Qualquer falha vira `AgenteIndisponivelError`."""
    cliente = _cliente_do_agente_do_termo()
    try:
        bruto = ai_processor._pedir_json(cliente, MODELO_DE_IA, system=load_prompt(prompt), usuario=usuario)
        resposta = json.loads(bruto)
    except Exception as erro:  # a tela pede para tentar de novo; nada é gravado
        logger.error("Agente do Canal de Conduta (%s) sem resposta: %s", prompt, type(erro).__name__)
        raise AgenteIndisponivelError(str(erro)) from erro
    if not isinstance(resposta, dict):
        raise AgenteIndisponivelError("a resposta não é um objeto")
    return resposta


def _textos(valor: Any) -> list[str]:
    if not isinstance(valor, list):
        return []
    return [str(item).strip() for item in valor if isinstance(item, str | int | float) and str(item).strip()]


# ── O que vai ao agente ─────────────────────────────────────────────────────


def _texto_do_arquivo(conteudo: bytes, content_type: str) -> str:
    if content_type.startswith("text/"):
        return conteudo.decode("utf-8", errors="replace").strip()
    extensao = ".pdf" if content_type == "application/pdf" else ".docx"
    try:
        texto, _ = extrair_texto(f"transcricao{extensao}", conteudo)
    except ValueError as erro:
        raise DepoimentoRecusadoError(422, f"A transcrição não pôde ser lida: {erro}") from erro
    return texto


def _conversa(supabase, depoimento: dict) -> str:
    """Os pontos digitados, sem gravação; senão, a última transcrição."""
    if depoimento.get("sem_gravacao_em"):
        return cifra.decifrar_texto(depoimento["pontos_cifrados"])
    transcricoes = [a for a in depoimentos._arquivos(supabase, [depoimento["id"]]) if a["tipo"] == "transcricao"]
    if not transcricoes:
        raise DepoimentoRecusadoError(
            409, "Anexe a transcrição do depoimento, ou registre os pontos da conversa, antes de redigir o termo."
        )
    ultima = max(transcricoes, key=lambda a: a["versao"])
    cifrado = storage.download_file(supabase, depoimentos.BUCKET, ultima["storage_path"])
    if cifrado is None:
        raise DepoimentoRecusadoError(503, "A transcrição não pôde ser aberta agora. Tente de novo.")
    return _texto_do_arquivo(cifra.decifrar_arquivo(cifrado), ultima["content_type"])


def _citados(supabase, caso_id: str) -> list[str]:
    return [c["nome"] for c in impedimento.citados_para_a_tela(supabase, caso_id) if c.get("nome")]


def _nomes_do_caso(supabase, caso: dict, *extras: str) -> list[str]:
    """Os nomes que o app conhece no caso: viram marcador antes de tudo."""
    pessoas_ouvidas = [cifra.decifrar_texto(d["nome_cifrado"]) for d in depoimentos._do_caso(supabase, caso["id"])]
    do_comite = list(membros.nomes(supabase, list(impedimento.membros_do_caso(supabase, caso))).values())
    return [n for n in (*extras, *pessoas_ouvidas, *_citados(supabase, caso["id"]), *do_comite) if n]


def relato_anonimo(supabase, caso_id: str) -> bool:
    """O relato é anônimo enquanto nenhuma pessoa ouvida é o denunciante
    identificado."""
    return not any(d["papel"] == "denunciante" for d in depoimentos._do_caso(supabase, caso_id))


def _sobre_o_relato(anonimo: bool, papel: str) -> str:
    if papel == "denunciante":
        return "O depoente é o denunciante identificado: ele mesmo fez o relato."
    if anonimo:
        return (
            "O relato do caso é ANÔNIMO. Ninguém sabe quem relatou. Não escreva nome, marcador, cargo ou pista "
            "de quem relatou, e não registre a suposição do depoente sobre quem foi."
        )
    return "Quem fez o relato é um denunciante identificado, que não é este depoente. Não cite quem relatou."


# ── O termo ─────────────────────────────────────────────────────────────────


def _linha(valor: Any, campo: str) -> str:
    texto = " ".join(str(valor or "").split())
    if not texto:
        raise DepoimentoRecusadoError(422, f"Preencha {campo}.")
    if len(texto) > _TAMANHO_DA_LINHA:
        raise DepoimentoRecusadoError(422, f"{campo[0].upper()}{campo[1:]} cabe em uma linha.")
    return texto


def _cpf(valor: Any) -> str:
    digitos = re.sub(r"\D", "", str(valor or ""))
    if not digitos:
        return ""
    if len(digitos) != 11:
        raise DepoimentoRecusadoError(422, "O CPF tem 11 dígitos. Deixe em branco para preencher à caneta.")
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def identificacao(depoimento: dict, dados: dict[str, Any]) -> dict[str, Any]:
    """O bloco de identificação do Anexo E.1, conferido. O nome e o cargo são
    os do cartão."""
    try:
        dia = date.fromisoformat(str(dados.get("data") or "")).isoformat()
    except ValueError as erro:
        raise DepoimentoRecusadoError(422, "Preencha a data da conversa.") from erro
    hora = str(dados.get("hora") or "").strip()
    if not _HORA.match(hora):
        raise DepoimentoRecusadoError(422, "Preencha a hora da conversa (por exemplo, 14:30).")
    conduziram = [" ".join(str(n).split()) for n in dados.get("conduziram") or [] if str(n).strip()]
    if len(conduziram) < 2:
        raise DepoimentoRecusadoError(422, "Ninguém conduz sozinho: diga as duas pessoas que conduziram.")
    if len(conduziram) > 4 or any(len(n) > _TAMANHO_DA_LINHA for n in conduziram):
        raise DepoimentoRecusadoError(422, "Diga de duas a quatro pessoas que conduziram, uma por linha.")
    return {
        "nome": cifra.decifrar_texto(depoimento["nome_cifrado"]),
        "cargo": cifra.decifrar_texto(depoimento["cargo_cifrado"]),
        "cpf": _cpf(dados.get("cpf")),
        "data": dia,
        "hora": hora,
        "local": _linha(dados.get("local"), "o local da conversa"),
        "conduziram": conduziram,
    }


def _gravacao(depoimento: dict, consentimento: Any) -> str:
    if depoimento.get("sem_gravacao_em"):
        return SEM_GRAVACAO
    return GRAVADA if consentimento == "dado" else CONFIRMAR_CONSENTIMENTO


def _mensagem_do_termo(marcacao: Marcacao, ident: dict, depoimento: dict, anonimo: bool, conversa: str, nomes):
    declarante = marcacao.marcar(ident["nome"], nomes)
    conduziram = [marcacao.marcar(n, nomes) for n in ident["conduziram"]]
    papel = depoimento["papel"]
    sem_gravacao = bool(depoimento.get("sem_gravacao_em"))
    partes = [
        f"Papel do depoente: {depoimentos.PAPEIS[papel]}.",
        f"Quem é quem: {declarante} é o declarante. {' e '.join(conduziram)} conduziram a conversa.",
        _sobre_o_relato(anonimo, papel),
        "Não houve gravação: a entrada são os pontos digitados por quem conduziu."
        if sem_gravacao
        else "A conversa foi gravada: a entrada é a transcrição automática.",
        ("Pontos da conversa:\n" if sem_gravacao else "Transcrição:\n") + marcacao.marcar(conversa, nomes),
    ]
    return "\n\n".join(partes)


def _versoes(supabase, depoimento_id: str) -> list[dict]:
    linhas = supabase.table(TABELA).select("*").eq("depoimento_id", depoimento_id).execute().data or []
    return sorted(linhas, key=lambda v: v["versao"])


def _gravar_versao(
    supabase, aberto: CasoAberto, depoimento: dict, termo: dict, notas: list[str], *, origem: str, detalhe: str
) -> dict:
    """`origem` é `agente` (o clique) ou `correcao` (o que quem conduziu lançou)."""
    versao = max((v["versao"] for v in _versoes(supabase, depoimento["id"])), default=0) + 1
    termo_cifrado = cifra.cifrar_texto(json.dumps(termo, ensure_ascii=False))
    notas_cifradas = cifra.cifrar_texto(json.dumps(notas, ensure_ascii=False)) if notas else None
    acao = "redigiu_termo" if origem == "agente" else "corrigiu_termo"
    trilha.registrar(supabase, aberto.caso["id"], aberto.autor_id, acao, f"{detalhe}, versão {versao}")
    supabase.table(TABELA).insert(
        {
            "depoimento_id": depoimento["id"],
            "versao": versao,
            "origem": origem,
            "termo_cifrado": termo_cifrado,
            "notas_cifradas": notas_cifradas,
            "criado_por": aberto.autor_id,
            "criado_em": agora_utc().isoformat(),
        }
    ).execute()
    return {"versao": versao}


def redigir_termo_de_declaracao_conduta(supabase, aberto: CasoAberto, depoimento_id: str, dados: dict) -> dict:
    """O clique de quem conduziu: o agente redige as declarações, e o termo
    vira uma versão nova. Roda no executor da IA."""
    caso = aberto.caso
    depoimento = depoimentos._depoimento(supabase, caso["id"], depoimento_id)
    depoimentos._exigir_aberto(caso, depoimento)
    ident = identificacao(depoimento, dados)
    conversa = _conversa(supabase, depoimento)
    nomes = _nomes_do_caso(supabase, caso, ident["nome"], *ident["conduziram"])
    marcacao = Marcacao()
    usuario = _mensagem_do_termo(marcacao, ident, depoimento, relato_anonimo(supabase, caso["id"]), conversa, nomes)
    resposta = _pedir_ao_agente_do_canal_de_conduta(PROMPT_DO_TERMO, usuario)
    declaracoes = [marcacao.devolver(p) for p in _textos(resposta.get("declaracoes"))]
    if not declaracoes:
        raise AgenteIndisponivelError("a resposta veio sem declarações")
    termo = sanitizar_estrutura(
        {
            "identificacao": ident,
            "gravacao": _gravacao(depoimento, resposta.get("consentimento")),
            "declaracoes": declaracoes,
            "documentos": [marcacao.devolver(d) for d in _textos(resposta.get("documentos"))],
            "lido_em_voz_alta": False,
        }
    )
    notas = sanitizar_estrutura([marcacao.devolver(n) for n in _textos(resposta.get("notas"))])
    return _gravar_versao(
        supabase, aberto, depoimento, termo, notas, origem="agente", detalhe="termo de declaração redigido pelo agente"
    )


def _ultima_versao(supabase, depoimento_id: str) -> dict:
    versoes = _versoes(supabase, depoimento_id)
    if not versoes:
        raise DepoimentoRecusadoError(409, "O termo ainda não foi redigido. Toque em REDIGIR TERMO.")
    return versoes[-1]


def _paragrafos(valor: Any, campo: str, *, obrigatorio: bool) -> list[str]:
    itens = [" ".join(str(p).split()) for p in valor or [] if str(p).strip()]
    if obrigatorio and not itens:
        raise DepoimentoRecusadoError(422, f"O termo precisa de {campo}.")
    if len(itens) > _ITENS or any(len(p) > _TAMANHO_DO_PARAGRAFO for p in itens):
        raise DepoimentoRecusadoError(422, "O termo passou do tamanho que cabe.")
    return itens


def lancar_correcoes(supabase, aberto: CasoAberto, depoimento_id: str, corrigido: dict) -> dict:
    """As correções do depoente, lançadas por quem conduziu: o termo inteiro,
    como ficou, vira uma versão nova. A anterior fica, e as notas seguem."""
    caso = aberto.caso
    depoimento = depoimentos._depoimento(supabase, caso["id"], depoimento_id)
    depoimentos._exigir_aberto(caso, depoimento)
    ultima = _ultima_versao(supabase, depoimento["id"])
    anterior = json.loads(cifra.decifrar_texto(ultima["termo_cifrado"]))
    termo = sanitizar_estrutura(
        {
            "identificacao": identificacao(depoimento, corrigido.get("identificacao") or {}),
            "gravacao": _paragrafos([corrigido.get("gravacao")], "a frase da gravação", obrigatorio=True)[0],
            "declaracoes": _paragrafos(corrigido.get("declaracoes"), "ao menos uma declaração", obrigatorio=True),
            "documentos": _paragrafos(corrigido.get("documentos"), "documentos", obrigatorio=False),
            "lido_em_voz_alta": bool(corrigido.get("lido_em_voz_alta")),
        }
    )
    if termo == anterior:
        raise DepoimentoRecusadoError(409, "Nada mudou no termo.")
    notas = json.loads(cifra.decifrar_texto(ultima["notas_cifradas"])) if ultima.get("notas_cifradas") else []
    return _gravar_versao(
        supabase,
        aberto,
        depoimento,
        termo,
        notas,
        origem="correcao",
        detalhe="correções lançadas no termo de declaração",
    )


# ── O PDF (Anexo E.1) ───────────────────────────────────────────────────────


def _dia_legivel(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def dados_do_pdf(caso: dict, versao: dict) -> dict[str, Any]:
    """O que preenche o modelo do termo. As Notas para quem apura não entram:
    elas nem chegam ao modelo. Passa pelo sanitizador, para o PDF não sair com
    travessão."""
    termo = json.loads(cifra.decifrar_texto(versao["termo_cifrado"]))
    ident = termo["identificacao"]
    return sanitizar_estrutura(
        {
            "protocolo": caso["protocolo"],
            "versao": versao["versao"],
            "identificacao": {
                **ident,
                "data": _dia_legivel(ident["data"]),
                "conduziram": " e ".join(ident["conduziram"]),
            },
            "assinam_por_quem_conduziu": ident["conduziram"],
            "gravacao": termo["gravacao"],
            "declaracoes": termo["declaracoes"],
            "documentos": termo["documentos"],
            "lido_em_voz_alta": termo["lido_em_voz_alta"],
            "modelo": MODELO_DO_PDF,
        }
    )


def imprimir_termo(supabase, aberto: CasoAberto, depoimento_id: str) -> tuple[bytes, str]:
    """IMPRIMIR TERMO: o PDF da última versão, depois de gravada a impressão
    na trilha."""
    from app.services.seguranca_do_paciente.termo import gerar_pdf_do_termo

    caso = aberto.caso
    depoimento = depoimentos._depoimento(supabase, caso["id"], depoimento_id)
    versao = _ultima_versao(supabase, depoimento["id"])
    dados = dados_do_pdf(caso, versao)
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "imprimiu_termo",
        f"imprimiu o termo de declaração, versão {versao['versao']}",
    )
    return gerar_pdf_do_termo(dados), f"Termo_de_declaracao_versao_{versao['versao']}.pdf"


# ── O roteiro de perguntas ──────────────────────────────────────────────────


def sugerir_roteiro_do_depoimento_conduta(supabase, aberto: CasoAberto, depoimento_id: str) -> dict:
    """O clique que pede ao agente o roteiro de perguntas, a partir do relato
    e do papel da pessoa ouvida. O roteiro é Sugestão. Roda no executor da IA."""
    caso = aberto.caso
    depoimento = depoimentos._depoimento(supabase, caso["id"], depoimento_id)
    depoimentos._exigir_aberto(caso, depoimento)
    nome = cifra.decifrar_texto(depoimento["nome_cifrado"])
    nomes = _nomes_do_caso(supabase, caso, nome)
    marcacao = Marcacao()
    usuario = "\n\n".join(
        [
            f"{marcacao.marcar(nome, nomes)} é a pessoa ouvida. Papel: {depoimentos.PAPEIS[depoimento['papel']]}.",
            _sobre_o_relato(relato_anonimo(supabase, caso["id"]), depoimento["papel"]),
            "Relato do caso:\n" + marcacao.marcar(cifra.decifrar_texto(caso["relato_cifrado"]), nomes),
        ]
    )
    resposta = _pedir_ao_agente_do_canal_de_conduta(PROMPT_DO_ROTEIRO, usuario)
    perguntas = sanitizar_estrutura([marcacao.devolver(p) for p in _textos(resposta.get("perguntas"))])
    if not perguntas:
        raise AgenteIndisponivelError("a resposta veio sem perguntas")
    roteiro_cifrado = cifra.cifrar_texto(json.dumps(perguntas, ensure_ascii=False))
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "sugeriu_roteiro", "roteiro de perguntas sugerido pelo agente"
    )
    depoimentos._mudar(
        supabase, depoimento, {"roteiro_cifrado": roteiro_cifrado, "roteiro_em": agora_utc().isoformat()}
    )
    return {"perguntas": len(perguntas)}


# ── A certidão de recusa ────────────────────────────────────────────────────


def registrar_recusa(supabase, aberto: CasoAberto, depoimento_id: str, membro_id: str) -> dict:
    """A pessoa se recusou a assinar: quem registra e outro membro do caso
    assinam a certidão de recusa na ClickSign. Assinada, ela volta à trilha e
    vale pelo termo assinado na lista de conferência."""
    caso = aberto.caso
    depoimento = depoimentos._depoimento(supabase, caso["id"], depoimento_id)
    depoimentos._exigir_aberto(caso, depoimento)
    versao = _ultima_versao(supabase, depoimento["id"])
    if any(a["tipo"] == "termo_assinado" for a in depoimentos._arquivos(supabase, [depoimento["id"]])):
        raise DepoimentoRecusadoError(409, "O termo assinado já foi anexado.")
    certidoes = assinaturas.certidoes_dos_depoimentos(supabase, [depoimento["id"]])
    if any(c["situacao"] == "assinado" for c in certidoes):
        raise DepoimentoRecusadoError(409, "A certidão de recusa já foi assinada.")
    do_caso = impedimento.membros_do_caso(supabase, caso)
    if aberto.autor_id not in do_caso:
        raise DepoimentoRecusadoError(403, "Só membro do Comitê neste caso registra a certidão de recusa.")
    if membro_id == aberto.autor_id or membro_id not in do_caso:
        raise DepoimentoRecusadoError(422, "Escolha outro membro do Comitê neste caso para assinar com você.")
    pessoas = (
        supabase.table("participantes")
        .select("id, nome_completo, email")
        .in_("id", [aberto.autor_id, membro_id])
        .execute()
        .data
    ) or []
    if len(pessoas) != 2 or not all(p.get("email") for p in pessoas):
        raise DepoimentoRecusadoError(422, "Os dois membros precisam de e-mail no cadastro para assinar a certidão.")
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "enviou_certidao_de_recusa",
        f"certidão de recusa de assinatura do termo, versão {versao['versao']}, enviada a dois membros",
    )
    dados = {
        "declarante": cifra.decifrar_texto(depoimento["nome_cifrado"]),
        "versao": versao["versao"],
        "data": hoje_em_sao_paulo().strftime("%d/%m/%Y"),
    }
    enviada = assinaturas.enviar_certidao_de_recusa(supabase, caso["id"], depoimento["id"], pessoas, dados)
    return {"situacao": enviada["situacao"], "erro": enviada.get("erro")}
