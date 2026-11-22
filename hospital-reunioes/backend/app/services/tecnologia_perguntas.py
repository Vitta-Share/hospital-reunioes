"""A Pergunta da Vitta (issue #2116, PRD #2112, ADR 0109, decisoes 1 e 3).

A pergunta que a Vitta manda a alguem do Hospital, pela ponte de automacao,
vira um registro do app ligado a uma Demanda: Destinatario, Assunto, o texto,
as quatro linhas do cartao (por que precisa da pessoa, o que esta parado, o
que anda depois e o ganho), as opcoes com a recomendada e o porque, e o
estado. Nasce aberta.

Todas as regras da Pergunta moram aqui (criar, e nas proximas Fatias
responder, resolver, cancelar, listar e lembrar); as rotas nao repetem regra.

Criar grava a entrada da Pergunta na Conversa da Demanda, pelo mesmo servico
das mensagens (`tecnologia_conversa.escrever`), que avisa so o Destinatario
com "Pede sua resposta" e o Assunto (ADR 0106). Depois vem a linha de sistema
"Pergunta aberta", pela mesma origem `sistema` da linha do Envio aos
desenvolvedores (ADR 0108).

O nome e Pergunta da Vitta, nunca Pendencia (ADR 0109, decisao 2): Pendencia e
a Acao da Ata.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.dependencies import selecionar_participantes
from app.services import tecnologia_conversa
from app.services.paginacao import ler_tudo
from app.services.tecnologia import TABELA_CONVERSA_DA_DEMANDA, TABELA_DEMANDAS, e_desenvolvedor, nome_do_projeto

TABELA_PERGUNTAS = "tecnologia_perguntas"

# Os estados da Pergunta (CHECK da migration 211, ADR 0109, decisao 1).
ESTADO_ABERTA = "aberta"
ESTADO_RESPONDIDA = "respondida"

# A origem da linha de sistema na Conversa (CHECK da migration 165): a mesma
# da linha do Envio aos desenvolvedores, para a tela mostrar do mesmo jeito.
ORIGEM_SISTEMA = "sistema"

# As quatro linhas do cartao, com o nome que o motivo da recusa usa.
LINHAS_DO_CARTAO: tuple[tuple[str, str], ...] = (
    ("por_que_precisa", "por que precisa da pessoa"),
    ("o_que_esta_parado", "o que está parado"),
    ("o_que_anda_depois", "o que anda depois"),
    ("ganho", "o ganho"),
)

# As letras das opcoes, na ordem em que chegam. Quatro no maximo.
LETRAS = ("A", "B", "C", "D")

MOTIVO_DESTINATARIO = "O Destinatário não é um participante ativo do aplicativo."
MOTIVO_SEM_ASSUNTO = "Falta o Assunto da Pergunta."
MOTIVO_SEM_TEXTO = "Falta o texto da Pergunta."
MOTIVO_OPCOES = "A Pergunta com opções precisa de duas a quatro, todas com texto."
MOTIVO_RECOMENDADA = "A recomendada precisa ser a letra de uma das opções."
MOTIVO_SEM_RESPOSTA = "Escolha uma das opções ou escreva a sua resposta."
MOTIVO_OPCAO_DESCONHECIDA = "A opção escolhida não é uma das opções da Pergunta."
MOTIVO_SO_O_DESTINATARIO = "Só quem recebeu a Pergunta, ou um Desenvolvedor no lugar dele, pode responder."
MOTIVO_NAO_ESTA_ABERTA = "Esta Pergunta já não espera resposta."


class PerguntaRecusadaError(ValueError):
    """A Pergunta nao pode nascer assim. A mensagem e o motivo, para a ponte
    devolver como esta; nada foi gravado."""


class RespostaRecusadaError(ValueError):
    """A resposta veio vazia ou com opcao que a Pergunta nao tem (422)."""


class RespostaProibidaError(PermissionError):
    """Quem tentou responder nao e o Destinatario nem um Desenvolvedor (403)."""


class PerguntaFechadaError(ValueError):
    """A Pergunta ja nao esta aberta (409): respondida, resolvida ou cancelada."""


def _limpo(valor: str | None) -> str:
    return (valor or "").strip()


def _opcoes(opcoes: Sequence[str], recomendada: str | None) -> list[dict[str, str]]:
    textos = [_limpo(texto) for texto in opcoes]
    if not textos:
        if recomendada:
            raise PerguntaRecusadaError(MOTIVO_RECOMENDADA)
        return []
    if not 2 <= len(textos) <= len(LETRAS) or not all(textos):
        raise PerguntaRecusadaError(MOTIVO_OPCOES)
    letras = LETRAS[: len(textos)]
    if recomendada not in letras:
        raise PerguntaRecusadaError(MOTIVO_RECOMENDADA)
    return [{"letra": letra, "texto": texto} for letra, texto in zip(letras, textos, strict=True)]


def criar(
    supabase,
    demanda: dict[str, Any],
    *,
    autor: dict[str, Any],
    destinatario_id: str | None,
    assunto: str | None,
    texto: str | None,
    linhas: dict[str, str | None],
    opcoes: Sequence[str] = (),
    recomendada: str | None = None,
    porque: str | None = None,
) -> dict[str, Any]:
    """Grava a Pergunta aberta, a entrada dela na Conversa da Demanda e a
    linha de sistema "Pergunta aberta", e avisa so o Destinatario. Devolve a
    linha da Pergunta. Tudo e conferido antes da primeira escrita: a recusa
    (`PerguntaRecusadaError`) nao deixa nada gravado nem avisado."""
    assunto, texto = _limpo(assunto), _limpo(texto)
    if not assunto:
        raise PerguntaRecusadaError(MOTIVO_SEM_ASSUNTO)
    if not texto:
        raise PerguntaRecusadaError(MOTIVO_SEM_TEXTO)
    cartao = {chave: _limpo(linhas.get(chave)) for chave, _ in LINHAS_DO_CARTAO}
    for chave, nome in LINHAS_DO_CARTAO:
        if not cartao[chave]:
            raise PerguntaRecusadaError(f"Falta a linha do cartão: {nome}.")
    lista = _opcoes(opcoes, recomendada)
    if not destinatario_id or not tecnologia_conversa.e_participante_ativo(supabase, destinatario_id):
        raise PerguntaRecusadaError(MOTIVO_DESTINATARIO)

    # O id nasce aqui, como UUID: e com ele que a ponte le a Pergunta depois
    # (o PedroOS o guarda, Vitta-Share/os#992), e o aviso leva a ele (#2118).
    pergunta_id = str(uuid4())
    entrada = tecnologia_conversa.escrever(
        supabase,
        demanda,
        autor=autor,
        texto=texto,
        origem=tecnologia_conversa.ORIGEM_TERMINAL,
        destinatario_id=destinatario_id,
        pede_resposta_sobre=assunto,
        pergunta_id=pergunta_id,
    )
    [pergunta] = (
        supabase.table(TABELA_PERGUNTAS)
        .insert(
            {
                "id": pergunta_id,
                "demanda_id": demanda["id"],
                "mensagem_id": entrada["id"],
                "autor_id": autor["id"],
                "destinatario_id": destinatario_id,
                "assunto": assunto,
                "texto": texto,
                **cartao,
                "opcoes": lista,
                "recomendada": recomendada if lista else None,
                "porque_da_recomendada": (_limpo(porque) or None) if lista else None,
                "estado": ESTADO_ABERTA,
            }
        )
        .execute()
        .data
    )
    supabase.table(TABELA_CONVERSA_DA_DEMANDA).insert(
        {
            "demanda_id": demanda["id"],
            "autor_id": autor["id"],
            "texto": f"Pergunta aberta: {assunto}",
            "mencoes": [],
            "origem": ORIGEM_SISTEMA,
        }
    ).execute()
    return pergunta


def buscar(supabase, pergunta_id: str) -> dict[str, Any] | None:
    """A linha da Pergunta, ou `None`."""
    linhas = supabase.table(TABELA_PERGUNTAS).select("*").eq("id", pergunta_id).execute().data or []
    return linhas[0] if linhas else None


def _nomes(supabase, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    result = selecionar_participantes(supabase, "id, nome_completo", lambda q: q.in_("id", sorted(ids)))
    return {str(p["id"]): p.get("nome_completo") or "" for p in result.data or []}


def _pessoas_da_pergunta(pergunta: dict[str, Any]) -> set[str]:
    chaves = ("destinatario_id", "respondida_por", "respondida_em_nome_de")
    return {str(pergunta.get(chave) or "") for chave in chaves}


def pode_responder(pergunta: dict[str, Any], ator: dict[str, Any]) -> bool:
    """Responde o Destinatario; o Desenvolvedor registra no lugar dele (ADR
    0109, decisao 5). Outro Super admin so ve o cartao."""
    return str(ator.get("id")) == str(pergunta.get("destinatario_id")) or e_desenvolvedor(ator)


def _cartao(p: dict[str, Any], *, projeto: str, nomes: dict[str, str], ator: dict[str, Any] | None) -> dict[str, Any]:
    estado = p.get("estado") or ESTADO_ABERTA
    return {
        "id": str(p["id"]),
        "projeto": projeto,
        "assunto": p.get("assunto") or "",
        "texto": p.get("texto") or "",
        **{chave: p.get(chave) or "" for chave, _ in LINHAS_DO_CARTAO},
        "opcoes": p.get("opcoes") or [],
        "recomendada": p.get("recomendada"),
        "porque": p.get("porque_da_recomendada"),
        "estado": estado,
        "criado_em": p.get("criado_em"),
        "destinatario": nomes.get(str(p.get("destinatario_id"))),
        # A resposta (issue #2119): o cartao respondido fica na Conversa com ela.
        "resposta": _resposta(p, nomes),
        "pode_responder": ator is not None and estado == ESTADO_ABERTA and pode_responder(p, ator),
    }


def cartoes_da_demanda(
    supabase, demanda: dict[str, Any], *, ator: dict[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    """O cartao de cada Pergunta da Demanda, pela entrada dela na Conversa
    (id da mensagem): de qual Projeto e, a pergunta, as quatro linhas, as
    opcoes, o estado, desde quando espera (a tela conta os dias), a resposta
    e se quem esta logado (`ator`) pode responder."""
    linhas = supabase.table(TABELA_PERGUNTAS).select("*").eq("demanda_id", demanda["id"]).execute().data or []
    nomes = _nomes(supabase, {pessoa for p in linhas for pessoa in _pessoas_da_pergunta(p)})
    projeto = nome_do_projeto(demanda)
    return {
        str(p["mensagem_id"]): _cartao(p, projeto=projeto, nomes=nomes, ator=ator)
        for p in linhas
        if p.get("mensagem_id")
    }


def esperando(supabase, *, ator_id: str) -> list[dict[str, Any]]:
    """A lista Esperando sua resposta (issue #2118, ADR 0109, decisao 5): as
    Perguntas abertas de todos os Projetos, cada uma com o cartao e o nome da
    Demanda. As de que `ator_id` e o Destinatario vem primeiro; em cada grupo,
    a mais antiga primeiro. A Demanda apagada (lapide) nao entra."""
    abertas = ler_tudo(
        lambda: supabase.table(TABELA_PERGUNTAS).select("*").eq("estado", ESTADO_ABERTA).order("criado_em").order("id"),
        rotulo="Perguntas da Vitta abertas",
    )
    if not abertas:
        return []
    ids = sorted({str(p["demanda_id"]) for p in abertas})
    demandas = {
        str(d["id"]): d
        for d in supabase.table(TABELA_DEMANDAS).select("*").in_("id", ids).is_("apagada_em", "null").execute().data
        or []
    }
    nomes = _nomes(supabase, {str(p.get("destinatario_id") or "") for p in abertas})
    itens = [
        {
            **_cartao(p, projeto=nome_do_projeto(demanda), nomes=nomes, ator=None),
            "demanda_id": str(demanda["id"]),
            "demanda": str(demanda.get("titulo") or ""),
            "minha": str(p.get("destinatario_id") or "") == str(ator_id),
        }
        for p in abertas
        if (demanda := demandas.get(str(p["demanda_id"])))
    ]
    # `sorted` e estavel: dentro de cada grupo fica a ordem da leitura.
    return sorted(itens, key=lambda item: not item["minha"])


def _texto_na_conversa(pergunta: dict[str, Any], *, opcao: str | None, texto: str, em_nome_de: str | None) -> str:
    """A mensagem da resposta na Conversa: "Resposta: B) <opcao>", o texto
    livre, ou os dois, e "em nome de" quando o Desenvolvedor registrou."""
    partes = []
    if opcao:
        escolhida = next((o for o in pergunta.get("opcoes") or [] if o.get("letra") == opcao), {})
        partes.append(f"{opcao}) {escolhida.get('texto') or ''}")
    if texto:
        partes.append(texto)
    abertura = f"Resposta em nome de {em_nome_de}" if em_nome_de else "Resposta"
    return f"{abertura}: " + "\n".join(partes)


def responder(
    supabase,
    pergunta: dict[str, Any],
    demanda: dict[str, Any],
    *,
    ator: dict[str, Any],
    opcao: str | None,
    texto: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Grava a resposta (a opcao, o texto livre ou os dois) e leva a Pergunta
    de aberta a respondida (issue #2119, ADR 0109, decisoes 4 e 5). A resposta
    entra na Conversa da Demanda como mensagem de quem respondeu, com o aviso
    de qualquer mensagem da tela.

    O Desenvolvedor que nao e o Destinatario registra no lugar dele, e os dois
    ficam gravados (`respondida_por` e `respondida_em_nome_de`). Nao muda
    Etapa, nao solta trabalho (decisao 6) e nada vai ao GitHub.

    A passagem de estado e condicional (`estado = aberta` no UPDATE): de duas
    respostas ao mesmo tempo, so a primeira grava. Devolve o cartao da
    Pergunta respondida e a mensagem gravada na Conversa."""
    if not pode_responder(pergunta, ator):
        raise RespostaProibidaError(MOTIVO_SO_O_DESTINATARIO)
    if (pergunta.get("estado") or ESTADO_ABERTA) != ESTADO_ABERTA:
        raise PerguntaFechadaError(MOTIVO_NAO_ESTA_ABERTA)
    opcao, texto = (_limpo(opcao) or None), _limpo(texto)
    if not opcao and not texto:
        raise RespostaRecusadaError(MOTIVO_SEM_RESPOSTA)
    if opcao and opcao not in {o.get("letra") for o in pergunta.get("opcoes") or []}:
        raise RespostaRecusadaError(MOTIVO_OPCAO_DESCONHECIDA)

    destinatario_id = pergunta.get("destinatario_id")
    no_lugar = destinatario_id is not None and str(ator["id"]) != str(destinatario_id)
    gravadas = (
        supabase.table(TABELA_PERGUNTAS)
        .update(
            {
                "estado": ESTADO_RESPONDIDA,
                "resposta_opcao": opcao,
                "resposta_texto": texto or None,
                "respondida_por": ator["id"],
                "respondida_em_nome_de": destinatario_id if no_lugar else None,
                "respondida_em": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", pergunta["id"])
        .eq("estado", ESTADO_ABERTA)
        .execute()
        .data
        or []
    )
    if not gravadas:
        raise PerguntaFechadaError(MOTIVO_NAO_ESTA_ABERTA)
    respondida = gravadas[0]
    nomes = _nomes(supabase, _pessoas_da_pergunta(respondida))
    em_nome_de = nomes.get(str(destinatario_id)) if no_lugar else None
    mensagem = tecnologia_conversa.escrever(
        supabase,
        demanda,
        autor=ator,
        texto=_texto_na_conversa(respondida, opcao=opcao, texto=texto, em_nome_de=em_nome_de),
        origem=tecnologia_conversa.ORIGEM_APP,
    )
    return _cartao(respondida, projeto=nome_do_projeto(demanda), nomes=nomes, ator=ator), mensagem


def _resposta(pergunta: dict[str, Any], nomes: dict[str, str]) -> dict[str, Any] | None:
    if not pergunta.get("respondida_em"):
        return None
    letra = pergunta.get("resposta_opcao")
    opcao = next((o for o in pergunta.get("opcoes") or [] if o.get("letra") == letra), None)
    por, em_nome_de = pergunta.get("respondida_por"), pergunta.get("respondida_em_nome_de")
    return {
        "opcao": letra,
        "opcao_texto": opcao.get("texto") if opcao else None,
        "texto": pergunta.get("resposta_texto"),
        "respondida_em": pergunta.get("respondida_em"),
        "respondida_por": nomes.get(str(por)) if por else None,
        "em_nome_de": nomes.get(str(em_nome_de)) if em_nome_de else None,
    }


def resposta(supabase, pergunta: dict[str, Any]) -> dict[str, Any] | None:
    """A resposta da Pergunta, quando houver: a letra e o texto da opcao
    escolhida, o texto livre, quando, quem registrou e em nome de quem."""
    if not pergunta.get("respondida_em"):
        return None
    return _resposta(pergunta, _nomes(supabase, _pessoas_da_pergunta(pergunta)))
