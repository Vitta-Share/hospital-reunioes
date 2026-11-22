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

Desde a issue #2176 (ADR 0110, emenda a 0109) este e o modulo do Pedido da
Vitta, com dois tipos na mesma tabela: a Pergunta, que se responde, e o Passo
a passo, que se conclui. O Passo a passo traz os passos (o ultimo e o "Como
saber que acabou"), um check por passo num historico que so cresce, e o card
do GitHub, que o app comenta e fecha quando ele e concluido. Concluir grava
antes e fecha depois: o GitHub recusando deixa o fechamento `falhou`, com o
motivo, e so o Reenviar tenta de novo. O Pedido acompanha o GitHub pelo
webhook (`aplicar_evento_da_issue`).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.dependencies import selecionar_participantes
from app.services import github_client, tecnologia_conversa, tecnologia_email
from app.services.notificacao_service import criar_notificacao_tecnologia
from app.services.paginacao import ler_tudo
from app.services.pendencias_consulta import FUSO
from app.services.tecnologia import TABELA_CONVERSA_DA_DEMANDA, TABELA_DEMANDAS, e_desenvolvedor, nome_do_projeto

logger = logging.getLogger(__name__)

TABELA_PERGUNTAS = "tecnologia_perguntas"
# O historico dos checks do Passo a passo (migration 232): so cresce.
TABELA_CHECKS = "tecnologia_checks_do_pedido"

# Os dois tipos do Pedido da Vitta (ADR 0110, decisao 1).
TIPO_PERGUNTA = "pergunta"
TIPO_PASSO_A_PASSO = "passo_a_passo"
TIPOS = (TIPO_PERGUNTA, TIPO_PASSO_A_PASSO)

# O Passo a passo tem de 2 a 15 passos; o ultimo e o "Como saber que acabou".
MINIMO_DE_PASSOS = 2
MAXIMO_DE_PASSOS = 15

# Os estados da Pergunta (CHECK da migration 211, ADR 0109, decisao 1).
ESTADO_ABERTA = "aberta"
ESTADO_RESPONDIDA = "respondida"
ESTADO_RESOLVIDA = "resolvida"
ESTADO_CANCELADA = "cancelada"
# So do Passo a passo (migration 232): aberta, concluida e cancelada.
ESTADO_CONCLUIDA = "concluida"

# Como o Passo a passo foi concluido (decisao 7) e o fechamento do card
# (decisao 8).
CONCLUIDA_NO_APP = "app"
CONCLUIDA_PELO_GITHUB = "github"
FECHAMENTO_PENDENTE = "pendente"
FECHAMENTO_FECHADO = "fechado"
FECHAMENTO_FALHOU = "falhou"

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
MOTIVO_SEM_DECIDIDO = "Falta o que foi decidido."
MOTIVO_SEM_DESTRAVOU = "Falta o que destravou."
MOTIVO_SEM_MOTIVO = "Falta o motivo do cancelamento."
MOTIVO_TIPO = "O tipo do Pedido é pergunta ou passo_a_passo."
MOTIVO_PASSOS = 'O Passo a passo precisa de 2 a 15 passos, todos com texto; o último é o "Como saber que acabou".'
MOTIVO_SEM_CARD = "Falta o card do Passo a passo (o número da issue)."
MOTIVO_OPCOES_SO_NA_PERGUNTA = "Opções prontas só existem na Pergunta."
MOTIVO_SO_NO_PASSO_A_PASSO = "Só o Passo a passo tem passos para marcar e concluir."
MOTIVO_PASSO_A_PASSO_NAO_SE_RESPONDE = "O Passo a passo se conclui no cartão, não se responde."
MOTIVO_PASSO_DESCONHECIDO = "Este passo não existe no Passo a passo."
MOTIVO_FALTA_CHECK = "Marque todos os passos antes de concluir."
MOTIVO_SO_QUEM_FAZ = "Só quem recebeu o Passo a passo, ou um Desenvolvedor no lugar dele, pode marcar e concluir."
MOTIVO_JA_CONCLUIDO = "Este Passo a passo já não está aberto."
MOTIVO_NADA_A_REENVIAR = "Este Passo a passo não tem fechamento que falhou para reenviar."
MOTIVO_GITHUB_SEM_ACESSO = "O app não tem acesso ao repositório deste card."
# Por que a passagem nao vale, pelo estado em que a Pergunta esta.
MOTIVO_DA_PASSAGEM_RECUSADA = {
    ESTADO_ABERTA: "A Pergunta ainda não foi respondida: só a respondida se resolve.",
    ESTADO_RESOLVIDA: "Esta Pergunta já foi resolvida e não muda mais.",
    ESTADO_CANCELADA: "Esta Pergunta já foi cancelada e não muda mais.",
    ESTADO_CONCLUIDA: "Este Passo a passo já foi concluído e não muda mais.",
}


class PerguntaRecusadaError(ValueError):
    """A Pergunta nao pode nascer assim. A mensagem e o motivo, para a ponte
    devolver como esta; nada foi gravado."""


class RespostaRecusadaError(ValueError):
    """A resposta veio vazia ou com opcao que a Pergunta nao tem (422)."""


class RespostaProibidaError(PermissionError):
    """Quem tentou responder nao e o Destinatario nem um Desenvolvedor (403)."""


class PerguntaFechadaError(ValueError):
    """A Pergunta ja nao esta aberta (409): respondida, resolvida ou cancelada."""


class FechamentoIncompletoError(ValueError):
    """Resolver sem o que foi decidido ou o que destravou, ou cancelar sem o
    motivo (422). Nada foi gravado."""


class PassagemRecusadaError(ValueError):
    """A Pergunta nao esta num estado de onde a passagem vale (409): resolver
    a aberta, ou resolver ou cancelar a que ja fechou."""


class ConclusaoRecusadaError(ValueError):
    """O check ou o Concluir nao valem assim (422): passo que nao existe,
    Pedido que nao e Passo a passo, ou passo ainda desmarcado. Nada muda."""


def _agora() -> datetime:
    """O relogio do modulo: o teste do comentario fixa a hora por aqui."""
    return datetime.now(UTC)


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
    tipo: str | None = None,
    passos: Sequence[str] = (),
    card_numero: int | None = None,
    card_projeto: str | None = None,
) -> dict[str, Any]:
    """Grava o Pedido aberto, a entrada dele na Conversa da Demanda e a linha
    de sistema "Pergunta aberta" ou "Passo a passo aberto", e avisa so o
    Destinatario ("Pede sua resposta" ou "Pede sua ação", ADR 0110). Devolve a
    linha do Pedido. Tudo e conferido antes da primeira escrita: a recusa
    (`PerguntaRecusadaError`) nao deixa nada gravado nem avisado.

    O Passo a passo (`tipo=passo_a_passo`) exige de 2 a 15 passos com texto e
    o numero do card; o Projeto do card e o da Demanda quando nao vem. Opcoes
    prontas so existem na Pergunta."""
    tipo = tipo or TIPO_PERGUNTA
    if tipo not in TIPOS:
        raise PerguntaRecusadaError(MOTIVO_TIPO)
    e_passo_a_passo = tipo == TIPO_PASSO_A_PASSO
    assunto, texto = _limpo(assunto), _limpo(texto)
    if not assunto:
        raise PerguntaRecusadaError(MOTIVO_SEM_ASSUNTO)
    if not texto:
        raise PerguntaRecusadaError(MOTIVO_SEM_TEXTO)
    cartao = {chave: _limpo(linhas.get(chave)) for chave, _ in LINHAS_DO_CARTAO}
    for chave, nome in LINHAS_DO_CARTAO:
        if not cartao[chave]:
            raise PerguntaRecusadaError(f"Falta a linha do cartão: {nome}.")
    lista_de_passos: list[str] = []
    if e_passo_a_passo:
        lista_de_passos = [_limpo(passo) for passo in passos]
        if not MINIMO_DE_PASSOS <= len(lista_de_passos) <= MAXIMO_DE_PASSOS or not all(lista_de_passos):
            raise PerguntaRecusadaError(MOTIVO_PASSOS)
        if not card_numero:
            raise PerguntaRecusadaError(MOTIVO_SEM_CARD)
        if any(_limpo(o) for o in opcoes) or recomendada:
            raise PerguntaRecusadaError(MOTIVO_OPCOES_SO_NA_PERGUNTA)
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
        pede_acao=e_passo_a_passo,
    )
    do_passo_a_passo = (
        {
            "passos": lista_de_passos,
            "card_projeto": _limpo(card_projeto) or str(demanda.get("projeto") or github_client.PROJETO_HOSPITAL),
            "card_numero": card_numero,
        }
        if e_passo_a_passo
        else {}
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
                "tipo": tipo,
                **do_passo_a_passo,
            }
        )
        .execute()
        .data
    )
    supabase.table(TABELA_CONVERSA_DA_DEMANDA).insert(
        {
            "demanda_id": demanda["id"],
            "autor_id": autor["id"],
            "texto": f"{'Passo a passo aberto' if e_passo_a_passo else 'Pergunta aberta'}: {assunto}",
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
    chaves = ("destinatario_id", "respondida_por", "respondida_em_nome_de", "concluida_por", "concluida_em_nome_de")
    return {str(pergunta.get(chave) or "") for chave in chaves}


def e_passo_a_passo(pedido: dict[str, Any]) -> bool:
    return pedido.get("tipo") == TIPO_PASSO_A_PASSO


def pode_responder(pergunta: dict[str, Any], ator: dict[str, Any]) -> bool:
    """Responde (no Passo a passo, marca e conclui) o Destinatario; o
    Desenvolvedor registra no lugar dele (ADR 0109, decisao 5; ADR 0110,
    decisao 6). Outro Super admin so ve o cartao."""
    return str(ator.get("id")) == str(pergunta.get("destinatario_id")) or e_desenvolvedor(ator)


# ─── Os checks do Passo a passo (issue #2176, ADR 0110, decisao 4) ──────────


def _historico(supabase, pedido_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """O historico dos checks de cada Pedido, do mais antigo ao mais novo."""
    if not pedido_ids:
        return {}
    linhas = ler_tudo(
        lambda: supabase.table(TABELA_CHECKS).select("*").in_("pedido_id", sorted(pedido_ids)).order("criado_em"),
        rotulo="checks do Passo a passo",
    )
    por_pedido: dict[str, list[dict[str, Any]]] = {}
    for linha in linhas:
        por_pedido.setdefault(str(linha["pedido_id"]), []).append(linha)
    return por_pedido


def _estado_dos_checks(pedido: dict[str, Any], historico: list[dict[str, Any]]) -> list[dict[str, Any] | None]:
    """A ultima linha de cada passo (o estado dele), ou `None` se nunca foi tocado."""
    ultimos: list[dict[str, Any] | None] = [None] * len(pedido.get("passos") or [])
    for linha in historico:
        indice = int(linha.get("passo") or 0)
        if 0 <= indice < len(ultimos):
            ultimos[indice] = linha
    return ultimos


def _todos_marcados(pedido: dict[str, Any], historico: list[dict[str, Any]]) -> bool:
    ultimos = _estado_dos_checks(pedido, historico)
    return bool(ultimos) and all(linha is not None and linha.get("marcado") for linha in ultimos)


def _passos(pedido: dict[str, Any], historico: list[dict[str, Any]], nomes: dict[str, str]) -> list[dict[str, Any]]:
    itens = []
    for texto, linha in zip(pedido.get("passos") or [], _estado_dos_checks(pedido, historico), strict=True):
        marcado = bool(linha and linha.get("marcado"))
        por = (linha or {}).get("por") if marcado else None
        em_nome_de = (linha or {}).get("em_nome_de") if marcado else None
        itens.append(
            {
                "texto": str(texto),
                "marcado": marcado,
                "por": nomes.get(str(por)) if por else None,
                "em_nome_de": nomes.get(str(em_nome_de)) if em_nome_de else None,
                "em": (linha or {}).get("criado_em") if marcado else None,
            }
        )
    return itens


def _pessoas_dos_checks(historico: list[dict[str, Any]]) -> set[str]:
    return {str(linha.get(chave) or "") for linha in historico for chave in ("por", "em_nome_de")}


def _conclusao(pedido: dict[str, Any], nomes: dict[str, str]) -> dict[str, Any] | None:
    if pedido.get("estado") != ESTADO_CONCLUIDA:
        return None
    por, em_nome_de = pedido.get("concluida_por"), pedido.get("concluida_em_nome_de")
    return {
        "concluida_em": pedido.get("concluida_em"),
        "como": pedido.get("concluida_como"),
        "por": nomes.get(str(por)) if por else None,
        "em_nome_de": nomes.get(str(em_nome_de)) if em_nome_de else None,
        "anotacao": pedido.get("resposta_texto"),
    }


def _fechamento(pedido: dict[str, Any]) -> dict[str, Any] | None:
    if not pedido.get("fechamento_github"):
        return None
    return {"estado": pedido["fechamento_github"], "motivo": pedido.get("fechamento_motivo")}


def _cartao(
    p: dict[str, Any],
    *,
    projeto: str,
    nomes: dict[str, str],
    ator: dict[str, Any] | None,
    historico: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    estado = p.get("estado") or ESTADO_ABERTA
    passo_a_passo = e_passo_a_passo(p)
    return {
        "id": str(p["id"]),
        "tipo": TIPO_PASSO_A_PASSO if passo_a_passo else TIPO_PERGUNTA,
        # O Passo a passo (issue #2176): os passos com o check, a conclusao e
        # o fechamento no GitHub. Vazios na Pergunta.
        "passos": _passos(p, historico or [], nomes) if passo_a_passo else [],
        "conclusao": _conclusao(p, nomes),
        "fechamento": _fechamento(p),
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
        # O estado final (issue #2121): a decisao ou o motivo.
        "resolucao": _resolucao(p),
        "cancelamento": _cancelamento(p),
        "pode_responder": ator is not None and estado == ESTADO_ABERTA and pode_responder(p, ator),
    }


def cartao(supabase, pedido: dict[str, Any], *, ator: dict[str, Any] | None) -> dict[str, Any]:
    """O cartao de um Pedido, com os checks e os nomes lidos agora."""
    historico = _historico(supabase, [str(pedido["id"])]).get(str(pedido["id"]), [])
    nomes = _nomes(supabase, _pessoas_da_pergunta(pedido) | _pessoas_dos_checks(historico))
    demandas = supabase.table(TABELA_DEMANDAS).select("*").eq("id", pedido["demanda_id"]).execute().data or []
    projeto = nome_do_projeto(demandas[0]) if demandas else ""
    return _cartao(pedido, projeto=projeto, nomes=nomes, ator=ator, historico=historico)


def cartoes_da_demanda(
    supabase, demanda: dict[str, Any], *, ator: dict[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    """O cartao de cada Pedido da Demanda, pela entrada dele na Conversa (id
    da mensagem): de qual Projeto e, a pergunta ou os passos com os checks,
    as quatro linhas, as opcoes, o estado, desde quando espera (a tela conta
    os dias), a resposta ou a conclusao e se quem esta logado (`ator`) pode
    agir."""
    linhas = supabase.table(TABELA_PERGUNTAS).select("*").eq("demanda_id", demanda["id"]).execute().data or []
    historicos = _historico(supabase, [str(p["id"]) for p in linhas if e_passo_a_passo(p)])
    pessoas = {pessoa for p in linhas for pessoa in _pessoas_da_pergunta(p)}
    pessoas |= {pessoa for h in historicos.values() for pessoa in _pessoas_dos_checks(h)}
    nomes = _nomes(supabase, pessoas)
    projeto = nome_do_projeto(demanda)
    return {
        str(p["mensagem_id"]): _cartao(
            p, projeto=projeto, nomes=nomes, ator=ator, historico=historicos.get(str(p["id"]), [])
        )
        for p in linhas
        if p.get("mensagem_id")
    }


def _participantes(supabase, ids: set[str]) -> dict[str, dict[str, Any]]:
    """O cadastro de cada id, com o que diz se a pessoa e Desenvolvedor."""
    ids = {i for i in ids if i}
    if not ids:
        return {}
    result = selecionar_participantes(
        supabase,
        "id, nome_completo, access_profile, is_super_admin, github_login",
        lambda q: q.in_("id", sorted(ids)),
    )
    return {str(p["id"]): p for p in result.data or []}


def esperando(supabase, *, ator: dict[str, Any]) -> list[dict[str, Any]]:
    """A lista Esperando você (issue #2118, ADR 0109, decisao 5; ADR 0110):
    os Pedidos da Vitta abertos, Perguntas e Passos a passo, de todos os
    Projetos, cada um com o cartao e o nome da Demanda. Os de que `ator` e o
    Destinatario vem primeiro; por ultimo, os que estao com a Vitta (o
    Destinatario e Desenvolvedor, `com_a_vitta`, ADR 0110, decisao 2). Em
    cada grupo, o mais antigo primeiro. A Demanda apagada (lapide) nao entra.

    O cartao da lista diz se `ator` pode responder, pelas mesmas regras da
    Conversa (issue #2145): o Destinatario responde, o Desenvolvedor registra
    no lugar dele, outro Super admin so le."""
    ator_id = str(ator.get("id") or "")
    abertas = ler_tudo(
        lambda: supabase.table(TABELA_PERGUNTAS).select("*").eq("estado", ESTADO_ABERTA).order("criado_em").order("id"),
        rotulo="Pedidos da Vitta abertos",
    )
    if not abertas:
        return []
    ids = sorted({str(p["demanda_id"]) for p in abertas})
    demandas = {
        str(d["id"]): d
        for d in supabase.table(TABELA_DEMANDAS).select("*").in_("id", ids).is_("apagada_em", "null").execute().data
        or []
    }
    historicos = _historico(supabase, [str(p["id"]) for p in abertas if e_passo_a_passo(p)])
    pessoas = _participantes(supabase, {str(p.get("destinatario_id") or "") for p in abertas})
    nomes = {pid: pessoa.get("nome_completo") or "" for pid, pessoa in pessoas.items()}
    nomes |= _nomes(supabase, {pessoa for h in historicos.values() for pessoa in _pessoas_dos_checks(h)})
    itens = []
    for p in abertas:
        demanda = demandas.get(str(p["demanda_id"]))
        if not demanda:
            continue
        destinatario = str(p.get("destinatario_id") or "")
        minha = destinatario == ator_id
        itens.append(
            {
                **_cartao(
                    p, projeto=nome_do_projeto(demanda), nomes=nomes, ator=ator, historico=historicos.get(str(p["id"]))
                ),
                "demanda_id": str(demanda["id"]),
                "demanda": str(demanda.get("titulo") or ""),
                "minha": minha,
                "com_a_vitta": not minha and e_desenvolvedor(pessoas.get(destinatario)),
            }
        )
    # `sorted` e estavel: dentro de cada grupo fica a ordem da leitura.
    return sorted(itens, key=lambda item: (not item["minha"], item["com_a_vitta"]))


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
    if e_passo_a_passo(pergunta):
        raise RespostaRecusadaError(MOTIVO_PASSO_A_PASSO_NAO_SE_RESPONDE)
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


# O lembrete unico (ADR 0109, decisao 7): 3 dias corridos sem resposta.
ESPERA_DO_LEMBRETE = timedelta(days=3)


def _instante(valor: str) -> datetime:
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))


def _lembrar_uma(supabase, pergunta: dict[str, Any], agora: datetime) -> bool:
    # Grava antes de avisar, so se a Pergunta segue aberta e sem lembrete:
    # a passada seguinte, ou outra ao mesmo tempo, nao lembra de novo.
    gravadas = (
        supabase.table(TABELA_PERGUNTAS)
        .update({"lembrete_enviado_em": agora.isoformat()})
        .eq("id", pergunta["id"])
        .eq("estado", ESTADO_ABERTA)
        .is_("lembrete_enviado_em", "null")
        .execute()
        .data
    )
    if not gravadas:
        return False
    # A lapide do Apagar (ADR 0084) sai de toda leitura: nao lembra de um
    # cartao que nao existe mais.
    demandas = (
        supabase.table(TABELA_DEMANDAS)
        .select("*")
        .eq("id", pergunta["demanda_id"])
        .is_("apagada_em", "null")
        .execute()
        .data
        or []
    )
    if not demandas:
        return False
    destinatario_id = str(pergunta["destinatario_id"])
    assunto = pergunta.get("assunto") or ""
    dias = (agora - _instante(pergunta["criado_em"])).days
    # O Passo a passo tem o mesmo lembrete unico (ADR 0110, decisao 1).
    acao = e_passo_a_passo(pergunta)
    criar_notificacao_tecnologia(
        supabase,
        destinatario_id=destinatario_id,
        titulo=f"Seu passo a passo espera há {dias} dias" if acao else f"Sua resposta espera há {dias} dias",
        mensagem=assunto,
        demanda_id=str(pergunta["demanda_id"]),
    )
    autor_id = str(pergunta.get("autor_id") or "")
    tecnologia_email.enviar_lembrete_da_pergunta(
        supabase,
        destinatario_id=destinatario_id,
        assunto=assunto,
        dias=dias,
        autor_nome=_nomes(supabase, {autor_id}).get(autor_id) or "A Vitta",
        demanda=demandas[0],
        acao=acao,
    )
    return True


def lembrar(supabase, agora: datetime) -> int:
    """O lembrete unico da Pergunta aberta ha 3 dias corridos (issue #2120,
    ADR 0109, decisao 7): sino e e-mail ao Destinatario, com o Assunto e ha
    quantos dias ela espera. Quem chama e o agendador de hora em hora.
    Devolve quantas foram lembradas. A falha de uma nao impede as outras."""
    abertas = ler_tudo(
        lambda: (
            supabase.table(TABELA_PERGUNTAS)
            .select("id, demanda_id, autor_id, destinatario_id, assunto, criado_em, tipo")
            .eq("estado", ESTADO_ABERTA)
            .is_("lembrete_enviado_em", "null")
            .order("id")
        ),
        rotulo="Perguntas da Vitta abertas sem lembrete",
    )
    limite = agora - ESPERA_DO_LEMBRETE
    lembradas = 0
    for pergunta in abertas:
        try:
            if not pergunta.get("destinatario_id") or _instante(pergunta["criado_em"]) > limite:
                continue
            if _lembrar_uma(supabase, pergunta, agora):
                lembradas += 1
        except Exception as e:  # noqa: BLE001 (uma Pergunta nao segura as outras)
            logger.error(f"[tecnologia_perguntas] Falha no lembrete da Pergunta {pergunta.get('id')}: {e}")
    return lembradas


# ─── Resolver e cancelar (issue #2121, ADR 0109, decisao 6) ─────────────────


def _fechar(
    supabase,
    pergunta: dict[str, Any],
    demanda: dict[str, Any],
    *,
    autor: dict[str, Any],
    de: tuple[str, ...],
    campos: dict[str, Any],
    linha: str,
) -> dict[str, Any]:
    """A passagem para resolvida ou cancelada: so dos estados `de`, por UPDATE
    condicional (de dois pedidos ao mesmo tempo, so o primeiro grava), e a
    linha de sistema na Conversa da Demanda. Depois dela a Pergunta nao muda
    mais: nenhum estado final esta em `de`."""
    estado = pergunta.get("estado") or ESTADO_ABERTA
    if estado not in de:
        raise PassagemRecusadaError(MOTIVO_DA_PASSAGEM_RECUSADA[estado])
    gravadas = (
        supabase.table(TABELA_PERGUNTAS).update(campos).eq("id", pergunta["id"]).in_("estado", list(de)).execute().data
        or []
    )
    if not gravadas:
        atual = buscar(supabase, str(pergunta["id"])) or {}
        raise PassagemRecusadaError(MOTIVO_DA_PASSAGEM_RECUSADA.get(atual.get("estado"), MOTIVO_NAO_ESTA_ABERTA))
    supabase.table(TABELA_CONVERSA_DA_DEMANDA).insert(
        {
            "demanda_id": demanda["id"],
            "autor_id": autor["id"],
            "texto": linha,
            "mencoes": [],
            "origem": ORIGEM_SISTEMA,
        }
    ).execute()
    return gravadas[0]


def _resolucao(pergunta: dict[str, Any]) -> dict[str, Any] | None:
    if pergunta.get("estado") != ESTADO_RESOLVIDA:
        return None
    return {
        "decidido": pergunta.get("resolucao_decidido"),
        "destravou": pergunta.get("resolucao_destravou"),
        "resolvida_em": pergunta.get("resolvida_em"),
    }


def _cancelamento(pergunta: dict[str, Any]) -> dict[str, Any] | None:
    if pergunta.get("estado") != ESTADO_CANCELADA:
        return None
    return {"motivo": pergunta.get("resolucao_decidido"), "cancelada_em": pergunta.get("cancelada_em")}


def resolver(
    supabase,
    pergunta: dict[str, Any],
    demanda: dict[str, Any],
    *,
    autor: dict[str, Any],
    decidido: str | None,
    destravou: str | None,
) -> dict[str, Any]:
    """A Vitta leu a resposta e deu o ok (ADR 0109, decisao 6): a Pergunta
    respondida passa a resolvida, com o que foi decidido e o que destravou, e
    a Conversa ganha a linha de sistema com os dois. So a respondida se
    resolve. Devolve a linha gravada."""
    decidido, destravou = _limpo(decidido), _limpo(destravou)
    if not decidido:
        raise FechamentoIncompletoError(MOTIVO_SEM_DECIDIDO)
    if not destravou:
        raise FechamentoIncompletoError(MOTIVO_SEM_DESTRAVOU)
    return _fechar(
        supabase,
        pergunta,
        demanda,
        autor=autor,
        de=(ESTADO_RESPONDIDA,),
        campos={
            "estado": ESTADO_RESOLVIDA,
            "resolucao_decidido": decidido,
            "resolucao_destravou": destravou,
            "resolvida_em": datetime.now(UTC).isoformat(),
        },
        linha=(
            f"Pergunta resolvida: {pergunta.get('assunto') or ''}\n"
            f"O que foi decidido: {decidido}\n"
            f"O que destravou: {destravou}"
        ),
    )


def cancelar(
    supabase,
    pergunta: dict[str, Any],
    demanda: dict[str, Any],
    *,
    autor: dict[str, Any],
    motivo: str | None,
) -> dict[str, Any]:
    """A Pergunta deixou de ser necessaria (ADR 0109, decisao 6): a aberta ou
    a respondida passa a cancelada, com o motivo, e a Conversa ganha a linha
    de sistema com ele. A aberta sai da lista Esperando sua resposta, que so
    le as abertas. A migration 211 nao tem coluna propria para o motivo: ele
    fica em `resolucao_decidido`, que na cancelada e o que se decidiu (que a
    Pergunta nao precisa mais). Devolve a linha gravada."""
    motivo = _limpo(motivo)
    if not motivo:
        raise FechamentoIncompletoError(MOTIVO_SEM_MOTIVO)
    return _fechar(
        supabase,
        pergunta,
        demanda,
        autor=autor,
        de=(ESTADO_ABERTA, ESTADO_RESPONDIDA),
        campos={
            "estado": ESTADO_CANCELADA,
            "resolucao_decidido": motivo,
            "cancelada_em": datetime.now(UTC).isoformat(),
        },
        linha=(
            f"{'Passo a passo cancelado' if e_passo_a_passo(pergunta) else 'Pergunta cancelada'}: "
            f"{pergunta.get('assunto') or ''}\nMotivo: {motivo}"
        ),
    )


# ─── Marcar, concluir e reenviar o Passo a passo (issue #2176, ADR 0110) ────


def _do_passo_a_passo_aberto(pedido: dict[str, Any], ator: dict[str, Any]) -> None:
    """A guarda comum do check e do Concluir: quem faz (403), o tipo (422) e
    o estado (409)."""
    if not pode_responder(pedido, ator):
        raise RespostaProibidaError(MOTIVO_SO_QUEM_FAZ)
    if not e_passo_a_passo(pedido):
        raise ConclusaoRecusadaError(MOTIVO_SO_NO_PASSO_A_PASSO)
    if (pedido.get("estado") or ESTADO_ABERTA) != ESTADO_ABERTA:
        raise PerguntaFechadaError(MOTIVO_JA_CONCLUIDO)


def _no_lugar_de(pedido: dict[str, Any], ator: dict[str, Any]) -> str | None:
    """O Destinatario, quando quem age e um Desenvolvedor no lugar dele."""
    destinatario_id = pedido.get("destinatario_id")
    return str(destinatario_id) if destinatario_id and str(ator["id"]) != str(destinatario_id) else None


def marcar(supabase, pedido: dict[str, Any], *, ator: dict[str, Any], passo: int, marcado: bool) -> dict[str, Any]:
    """Marca ou desmarca um passo (ADR 0110, decisao 4): uma linha nova no
    historico, com quem e, se for o Desenvolvedor no lugar, em nome de quem.
    Nada se apaga. Devolve o cartao."""
    _do_passo_a_passo_aberto(pedido, ator)
    if isinstance(passo, bool) or not 0 <= passo < len(pedido.get("passos") or []):
        raise ConclusaoRecusadaError(MOTIVO_PASSO_DESCONHECIDO)
    supabase.table(TABELA_CHECKS).insert(
        {
            "pedido_id": str(pedido["id"]),
            "passo": passo,
            "marcado": bool(marcado),
            "por": ator["id"],
            "em_nome_de": _no_lugar_de(pedido, ator),
        }
    ).execute()
    return cartao(supabase, pedido, ator=ator)


def leitura_do_passo_a_passo(supabase, pedido: dict[str, Any]) -> dict[str, Any]:
    """O que a ponte devolve alem da resposta (o Checar respostas do PedroOS):
    o tipo, o card, a conclusao (quando, como, quem e a anotacao) e o
    fechamento no GitHub. Nulos na Pergunta."""
    if not e_passo_a_passo(pedido):
        return {"tipo": TIPO_PERGUNTA, "card": None, "conclusao": None, "fechamento": None}
    return {
        "tipo": TIPO_PASSO_A_PASSO,
        "card": {"projeto": pedido.get("card_projeto"), "numero": pedido.get("card_numero")},
        "conclusao": _conclusao(pedido, _nomes(supabase, _pessoas_da_pergunta(pedido))),
        "fechamento": _fechamento(pedido),
    }


def _hora_local(instante: str) -> str:
    momento = _instante(instante).astimezone(FUSO)
    return f"{momento:%d/%m} às {momento:%H:%M}"


# O marcador da primeira linha do comentario: e por ele que o teste (e quem
# le a issue) reconhece o comentario do app.
MARCADOR_DO_COMENTARIO = "<!-- pedido-da-vitta: passo-a-passo-concluido -->"


def comentario_de_fechamento(pedido: dict[str, Any], *, destinatario_e_desenvolvedor: bool) -> str:
    """O comentario fixo na issue (ADR 0110, decisao 10): quando, por qual
    papel e os checks. Sem a anotacao e sem o nome de ninguem: o repositorio e
    publico (ADR 0083, decisao 8)."""
    papel = "Desenvolvedor" if destinatario_e_desenvolvedor else "Diretoria"
    quem = (
        f"por um Desenvolvedor, no lugar do Destinatário ({papel})"
        if pedido.get("concluida_em_nome_de")
        else f"pelo Destinatário ({papel})"
    )
    checks = "\n".join(f"- [x] {passo}" for passo in pedido.get("passos") or [])
    return (
        f"{MARCADOR_DO_COMENTARIO}\n"
        f"Passo a passo concluído no app em {_hora_local(pedido['concluida_em'])}, {quem}.\n\n"
        f"{checks}"
    )


def _motivo_da_falha(erro: Exception) -> str:
    if isinstance(erro, github_client.GithubNaoConfiguradoError):
        return MOTIVO_GITHUB_SEM_ACESSO
    return f"O GitHub não aceitou ({erro})."[:500]


def _fechar_o_card(supabase, pedido: dict[str, Any]) -> dict[str, Any]:
    """Comenta e fecha o card como feito, e grava o desfecho: `fechado`, ou
    `falhou` com o motivo (decisao 8). Nunca tenta de novo sozinho."""
    destinatario = _participantes(supabase, {str(pedido.get("destinatario_id") or "")})
    comentario = comentario_de_fechamento(
        pedido,
        destinatario_e_desenvolvedor=e_desenvolvedor(destinatario.get(str(pedido.get("destinatario_id") or ""))),
    )
    try:
        github_client.fechar_como_feita(
            int(pedido["card_numero"]), projeto=str(pedido.get("card_projeto") or ""), comentario=comentario
        )
        desfecho = {"fechamento_github": FECHAMENTO_FECHADO, "fechamento_motivo": None}
    except (github_client.GithubNaoConfiguradoError, github_client.GithubIndisponivelError) as erro:
        logger.warning(f"[tecnologia_perguntas] O card do Passo a passo {pedido.get('id')} não fechou: {erro}")
        desfecho = {"fechamento_github": FECHAMENTO_FALHOU, "fechamento_motivo": _motivo_da_falha(erro)}
    gravadas = supabase.table(TABELA_PERGUNTAS).update(desfecho).eq("id", pedido["id"]).execute().data or []
    return gravadas[0] if gravadas else {**pedido, **desfecho}


def concluir(
    supabase,
    pedido: dict[str, Any],
    demanda: dict[str, Any],
    *,
    ator: dict[str, Any],
    anotacao: str | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Conclui o Passo a passo (ADR 0110, decisoes 4 a 6, 8 e 10): so com
    todos os checks marcados. Grava antes e fecha depois: a passagem para
    concluida e condicional (`estado = aberta`), a Conversa ganha a linha de
    sistema e, se houver, a anotacao como mensagem de quem concluiu; depois o
    app comenta e fecha o card. O GitHub recusando deixa o Pedido concluido
    com o fechamento `falhou`. Devolve o cartao e a mensagem da anotacao."""
    _do_passo_a_passo_aberto(pedido, ator)
    historico = _historico(supabase, [str(pedido["id"])]).get(str(pedido["id"]), [])
    if not _todos_marcados(pedido, historico):
        raise ConclusaoRecusadaError(MOTIVO_FALTA_CHECK)
    anotacao = _limpo(anotacao)
    gravadas = (
        supabase.table(TABELA_PERGUNTAS)
        .update(
            {
                "estado": ESTADO_CONCLUIDA,
                "concluida_por": ator["id"],
                "concluida_em_nome_de": _no_lugar_de(pedido, ator),
                "concluida_em": _agora().isoformat(),
                "concluida_como": CONCLUIDA_NO_APP,
                "resposta_texto": anotacao or None,
                "fechamento_github": FECHAMENTO_PENDENTE,
                "fechamento_motivo": None,
            }
        )
        .eq("id", pedido["id"])
        .eq("estado", ESTADO_ABERTA)
        .execute()
        .data
        or []
    )
    if not gravadas:
        raise PerguntaFechadaError(MOTIVO_JA_CONCLUIDO)
    _linha_de_sistema(supabase, demanda, gravadas[0], f"Passo a passo concluído: {pedido.get('assunto') or ''}")
    mensagem = None
    if anotacao:
        mensagem = tecnologia_conversa.escrever(
            supabase, demanda, autor=ator, texto=f"Anotação: {anotacao}", origem=tecnologia_conversa.ORIGEM_APP
        )
    concluido = _fechar_o_card(supabase, gravadas[0])
    return cartao(supabase, concluido, ator=ator), mensagem


def reenviar(supabase, pedido: dict[str, Any], *, ator: dict[str, Any]) -> dict[str, Any]:
    """O Reenviar do "Não chegou ao GitHub" (decisao 8): tenta de novo
    comentar e fechar o card, so quando o fechamento falhou. Devolve o cartao."""
    if not pode_responder(pedido, ator):
        raise RespostaProibidaError(MOTIVO_SO_QUEM_FAZ)
    if pedido.get("estado") != ESTADO_CONCLUIDA or pedido.get("fechamento_github") != FECHAMENTO_FALHOU:
        raise PassagemRecusadaError(MOTIVO_NADA_A_REENVIAR)
    return cartao(supabase, _fechar_o_card(supabase, pedido), ator=ator)


def _linha_de_sistema(supabase, demanda: dict[str, Any] | None, pedido: dict[str, Any], texto: str) -> None:
    supabase.table(TABELA_CONVERSA_DA_DEMANDA).insert(
        {
            "demanda_id": (demanda or {}).get("id") or pedido["demanda_id"],
            "autor_id": pedido.get("autor_id"),
            "texto": texto,
            "mencoes": [],
            "origem": ORIGEM_SISTEMA,
        }
    ).execute()


# ─── O Pedido acompanha o GitHub (issue #2176, ADR 0110, decisao 7) ────────

ACAO_FECHADA = "closed"
ACAO_REABERTA = "reopened"
ACOES_QUE_O_PEDIDO_ACOMPANHA = (ACAO_FECHADA, ACAO_REABERTA)


def _depois_do_evento(pedido: dict[str, Any], acao: str, motivo: str | None) -> tuple[dict[str, Any], str] | None:
    """O que o evento muda no Passo a passo, e a linha da Conversa; `None`
    quando nao muda nada (idempotente pelo estado)."""
    estado = pedido.get("estado")
    assunto = pedido.get("assunto") or ""
    agora = _agora().isoformat()
    if acao == ACAO_REABERTA:
        if estado == ESTADO_ABERTA:
            return None
        campos = {
            "estado": ESTADO_ABERTA,
            "concluida_por": None,
            "concluida_em_nome_de": None,
            "concluida_em": None,
            "concluida_como": None,
            "resposta_texto": None,
            "fechamento_github": None,
            "fechamento_motivo": None,
            "cancelada_em": None,
            "resolucao_decidido": None,
        }
        return campos, f"Passo a passo reaberto pelo GitHub, com os checks zerados: {assunto}"
    if acao != ACAO_FECHADA:
        return None
    if str(motivo or "").lower() == github_client.FECHAMENTO_NAO_PLANEJADA:
        if estado != ESTADO_ABERTA:
            return None
        return (
            {"estado": ESTADO_CANCELADA, "cancelada_em": agora, "resolucao_decidido": "O card foi fechado no GitHub."},
            f"Passo a passo cancelado pelo GitHub: {assunto}",
        )
    if estado == ESTADO_ABERTA:
        return (
            {
                "estado": ESTADO_CONCLUIDA,
                "concluida_em": agora,
                "concluida_como": CONCLUIDA_PELO_GITHUB,
                "fechamento_github": FECHAMENTO_FECHADO,
                "fechamento_motivo": None,
            },
            f"Passo a passo concluído pelo GitHub: {assunto}",
        )
    if estado == ESTADO_CONCLUIDA and pedido.get("fechamento_github") != FECHAMENTO_FECHADO:
        # O app concluiu e o fechamento falhou; o card fechou depois: chegou.
        return {"fechamento_github": FECHAMENTO_FECHADO, "fechamento_motivo": None}, ""
    return None


def aplicar_evento_da_issue(supabase, *, projeto: str, numero: int, acao: str, motivo: str | None) -> int:
    """O evento `issues` do card de um Passo a passo (decisao 7): fechado
    como feito conclui "pelo GitHub", fechado como nao planejado cancela, e
    reaberto reabre com os checks zerados (uma linha desmarcada no historico
    para cada passo marcado). O fechamento que o proprio app fez nao conclui
    de novo. Devolve quantos Pedidos mudaram."""
    if acao not in ACOES_QUE_O_PEDIDO_ACOMPANHA:
        return 0
    pedidos = (
        supabase.table(TABELA_PERGUNTAS)
        .select("*")
        .eq("tipo", TIPO_PASSO_A_PASSO)
        .eq("card_projeto", projeto)
        .eq("card_numero", numero)
        .execute()
        .data
        or []
    )
    mudaram = 0
    for pedido in pedidos:
        depois = _depois_do_evento(pedido, acao, motivo)
        if depois is None:
            continue
        campos, linha = depois
        gravadas = (
            supabase.table(TABELA_PERGUNTAS)
            .update(campos)
            .eq("id", pedido["id"])
            .eq("estado", pedido.get("estado"))
            .execute()
            .data
            or []
        )
        if not gravadas:
            continue
        mudaram += 1
        if acao == ACAO_REABERTA:
            historico = _historico(supabase, [str(pedido["id"])]).get(str(pedido["id"]), [])
            zerar = [
                {"pedido_id": str(pedido["id"]), "passo": indice, "marcado": False, "por": None, "em_nome_de": None}
                for indice, ultimo in enumerate(_estado_dos_checks(pedido, historico))
                if ultimo is not None and ultimo.get("marcado")
            ]
            if zerar:
                supabase.table(TABELA_CHECKS).insert(zerar).execute()
        if linha:
            _linha_de_sistema(supabase, None, pedido, linha)
    return mudaram
