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

Desde a issue #2207 (ADR 0111, emenda a 0110) ha o terceiro tipo, o Pedido de
implantacao: o que o hospital faz depois que o codigo sobe. Tem os passos e
os checks do Passo a passo, mas so nasce para o card com a label
`implantacao`, e nascer fecha o card como concluido, com o comentario fixo. O
Concluir so comenta na issue fechada, nunca chama o fechamento, e o webhook
nao mexe nele (decisao 7).

Desde a issue #2208 (ADR 0111, decisao 8) um Pedido de implantacao pode
esperar outro da mesma Demanda (`espera_pedido_id`): o cartao mostra a espera
e o Concluir recusa enquanto o esperado nao esta concluido.
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
from app.services.tecnologia import (
    ETAPA_EM_PRODUCAO,
    ETAPA_ENTREGUE,
    TABELA_CONVERSA_DA_DEMANDA,
    TABELA_DEMANDAS,
    e_desenvolvedor,
    nome_do_projeto,
)

logger = logging.getLogger(__name__)

TABELA_PERGUNTAS = "tecnologia_perguntas"
# O historico dos checks do Passo a passo (migration 232): so cresce.
TABELA_CHECKS = "tecnologia_checks_do_pedido"

# Os dois tipos do Pedido da Vitta (ADR 0110, decisao 1).
TIPO_PERGUNTA = "pergunta"
TIPO_PASSO_A_PASSO = "passo_a_passo"
# O Pedido de implantacao (ADR 0111, decisao 1): passos com check, como o
# Passo a passo, para o que vem depois do codigo.
TIPO_IMPLANTACAO = "implantacao"
TIPOS = (TIPO_PERGUNTA, TIPO_PASSO_A_PASSO, TIPO_IMPLANTACAO)
TIPOS_COM_PASSOS = (TIPO_PASSO_A_PASSO, TIPO_IMPLANTACAO)

# A label do card que pode virar Pedido de implantacao (ADR 0111, decisao 3).
LABEL_DA_IMPLANTACAO = "implantacao"

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
MOTIVO_TIPO = "O tipo do Pedido é pergunta, passo_a_passo ou implantacao."
MOTIVO_SEM_LABEL_DE_IMPLANTACAO = (
    "Só o card com a label implantacao vira Pedido de implantação. Mande como Passo a passo, ou ponha a label."
)
MOTIVO_CARD_NAO_EXISTE = "O card não existe no repositório do Projeto {projeto}."
MOTIVO_SEM_CONFERIR_O_CARD = "O app não conseguiu ler o card no GitHub para conferir a label ({erro})."
MOTIVO_PASSOS = 'O Passo a passo precisa de 2 a 15 passos, todos com texto; o último é o "Como saber que acabou".'
MOTIVO_SEM_CARD = "Falta o card do Passo a passo (o número da issue)."
# Issue #2190: o app so fecha card no repositorio que conhece.
MOTIVO_SEM_REPOSITORIO = (
    "O app não alcança o repositório do Projeto {projeto}, então não fecharia o card. Mande como Pergunta."
)
MOTIVO_OPCOES_SO_NA_PERGUNTA = "Opções prontas só existem na Pergunta."
MOTIVO_SO_NO_PASSO_A_PASSO = "Só o Passo a passo tem passos para marcar e concluir."
MOTIVO_PASSO_A_PASSO_NAO_SE_RESPONDE = "O Passo a passo se conclui no cartão, não se responde."
MOTIVO_PASSO_DESCONHECIDO = "Este passo não existe no Passo a passo."
MOTIVO_FALTA_CHECK = "Marque todos os passos antes de concluir."
MOTIVO_SO_QUEM_FAZ = "Só quem recebeu o Passo a passo, ou um Desenvolvedor no lugar dele, pode marcar e concluir."
MOTIVO_JA_CONCLUIDO = "Este Passo a passo já não está aberto."
MOTIVO_NADA_A_REENVIAR = "Este Pedido não tem fechamento que falhou para reenviar."
MOTIVO_GITHUB_SEM_ACESSO = "O app não tem acesso ao repositório deste card."
# A espera de um Pedido de implantacao por outro (issue #2208, ADR 0111, decisao 8).
MOTIVO_ESPERA_SO_NA_IMPLANTACAO = "Só o Pedido de implantação espera outro Pedido."
MOTIVO_ESPERA_NAO_EXISTE = "O Pedido esperado não existe."
MOTIVO_ESPERA_DE_OUTRA_DEMANDA = "O Pedido de implantação só espera outro da mesma Demanda."
MOTIVO_ESPERA_DE_OUTRO_TIPO = "O Pedido de implantação só espera outro Pedido de implantação."
MOTIVO_ESPERA_CANCELADA = "O Pedido esperado foi cancelado: este nunca poderia ser concluído."
MOTIVO_ESPERA_ABERTA = 'Este Pedido espera "{assunto}" ser concluído.'
# O "Achei um problema" (issue #2210, ADR 0111, decisao 9).
MOTIVO_PROBLEMA_SO_NA_IMPLANTACAO = "Só o Pedido de implantação tem o Achei um problema."
MOTIVO_PROBLEMA_SO_NO_ABERTO = "Este Pedido de implantação já não está aberto."
TEXTO_DO_PROBLEMA = 'Achei um problema no Pedido de implantação "{assunto}", da entrega "{entrega}".'
MOTIVO_ESPERA_O_BUG = "Este Pedido espera a Demanda {numero} ser entregue."
# A Demanda de bug entregue solta o Pedido que espera por ela.
ETAPAS_DO_BUG_ENTREGUE = (ETAPA_ENTREGUE, ETAPA_EM_PRODUCAO)
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
    espera_pedido_id: str | None = None,
) -> dict[str, Any]:
    """Grava o Pedido aberto, a entrada dele na Conversa da Demanda e a linha
    de sistema "Pergunta aberta" ou "Passo a passo aberto", e avisa so o
    Destinatario ("Pede sua resposta" ou "Pede sua ação", ADR 0110). Devolve a
    linha do Pedido. Tudo e conferido antes da primeira escrita: a recusa
    (`PerguntaRecusadaError`) nao deixa nada gravado nem avisado.

    O Passo a passo (`tipo=passo_a_passo`) exige de 2 a 15 passos com texto e
    o numero do card; o Projeto do card e o da Demanda quando nao vem, e
    precisa ter repositorio configurado no app (issue #2190). Opcoes prontas
    so existem na Pergunta.

    O Pedido de implantacao (`tipo=implantacao`, issue #2207) pede o mesmo
    que o Passo a passo e mais a label `implantacao` no card, lida no GitHub
    antes de gravar. Depois de gravado, o app fecha o card como concluido com
    o comentario fixo; a recusa do GitHub nao desfaz o Pedido, deixa o
    fechamento `falhou` com o motivo (ADR 0111, decisao 4).

    O Pedido de implantacao pode esperar outro (`espera_pedido_id`, issue
    #2208): so outro Pedido de implantacao da mesma Demanda."""
    tipo = tipo or TIPO_PERGUNTA
    if tipo not in TIPOS:
        raise PerguntaRecusadaError(MOTIVO_TIPO)
    e_passo_a_passo = tipo in TIPOS_COM_PASSOS
    implantacao = tipo == TIPO_IMPLANTACAO
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
    projeto_do_card = ""
    if e_passo_a_passo:
        lista_de_passos = [_limpo(passo) for passo in passos]
        if not MINIMO_DE_PASSOS <= len(lista_de_passos) <= MAXIMO_DE_PASSOS or not all(lista_de_passos):
            raise PerguntaRecusadaError(MOTIVO_PASSOS)
        if not card_numero:
            raise PerguntaRecusadaError(MOTIVO_SEM_CARD)
        projeto_do_card = _limpo(card_projeto) or str(demanda.get("projeto") or github_client.PROJETO_HOSPITAL)
        if not github_client.repositorio_do_projeto(projeto_do_card):
            raise PerguntaRecusadaError(MOTIVO_SEM_REPOSITORIO.format(projeto=projeto_do_card))
        if any(_limpo(o) for o in opcoes) or recomendada:
            raise PerguntaRecusadaError(MOTIVO_OPCOES_SO_NA_PERGUNTA)
    lista = _opcoes(opcoes, recomendada)
    if not destinatario_id or not tecnologia_conversa.e_participante_ativo(supabase, destinatario_id):
        raise PerguntaRecusadaError(MOTIVO_DESTINATARIO)
    espera_pedido_id = _limpo(espera_pedido_id) or None
    if espera_pedido_id:
        _exigir_a_espera_valida(supabase, demanda, tipo, espera_pedido_id)
    if implantacao:
        _exigir_a_label_da_implantacao(int(card_numero), projeto_do_card)

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
            "card_projeto": projeto_do_card,
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
                **({"espera_pedido_id": espera_pedido_id} if espera_pedido_id else {}),
            }
        )
        .execute()
        .data
    )
    supabase.table(TABELA_CONVERSA_DA_DEMANDA).insert(
        {
            "demanda_id": demanda["id"],
            "autor_id": autor["id"],
            "texto": f"{NOME_DO_TIPO[tipo]} {'aberto' if e_passo_a_passo else 'aberta'}: {assunto}",
            "mencoes": [],
            "origem": ORIGEM_SISTEMA,
        }
    ).execute()
    if implantacao:
        pergunta = _fechar_o_card(supabase, pergunta)
    return pergunta


# O nome de cada tipo nas linhas de sistema da Conversa.
NOME_DO_TIPO = {
    TIPO_PERGUNTA: "Pergunta",
    TIPO_PASSO_A_PASSO: "Passo a passo",
    TIPO_IMPLANTACAO: "Pedido de implantação",
}


def _exigir_a_espera_valida(supabase, demanda: dict[str, Any], tipo: str, espera_pedido_id: str) -> None:
    """A espera vale so no Pedido de implantacao e so por outro Pedido de
    implantacao da mesma Demanda, que nao foi cancelado (ADR 0111, decisao 8)."""
    if tipo != TIPO_IMPLANTACAO:
        raise PerguntaRecusadaError(MOTIVO_ESPERA_SO_NA_IMPLANTACAO)
    esperado = buscar(supabase, espera_pedido_id)
    if esperado is None:
        raise PerguntaRecusadaError(MOTIVO_ESPERA_NAO_EXISTE)
    if str(esperado.get("demanda_id")) != str(demanda["id"]):
        raise PerguntaRecusadaError(MOTIVO_ESPERA_DE_OUTRA_DEMANDA)
    if not e_implantacao(esperado):
        raise PerguntaRecusadaError(MOTIVO_ESPERA_DE_OUTRO_TIPO)
    # O cancelado segura o Concluir para sempre (`_espera`): esperar por ele
    # faria nascer um Pedido que nunca conclui, com o lembrete batendo.
    if esperado.get("estado") == ESTADO_CANCELADA:
        raise PerguntaRecusadaError(MOTIVO_ESPERA_CANCELADA)


def texto_do_problema(pedido: dict[str, Any], demanda: dict[str, Any]) -> str:
    """O texto inicial do bug que o "Achei um problema" abre (issue #2210,
    ADR 0111, decisao 9): nomeia o Pedido e a entrega. So vale no Pedido de
    implantacao aberto."""
    if not e_implantacao(pedido):
        raise PerguntaRecusadaError(MOTIVO_PROBLEMA_SO_NA_IMPLANTACAO)
    if pedido.get("estado") != ESTADO_ABERTA:
        raise PerguntaRecusadaError(MOTIVO_PROBLEMA_SO_NO_ABERTO)
    return TEXTO_DO_PROBLEMA.format(
        assunto=" ".join(str(pedido.get("assunto") or "").split()),
        entrega=" ".join(str(demanda.get("titulo") or "").split()),
    )


def pedido_do_bug(supabase, bug: dict[str, Any]) -> dict[str, Any] | None:
    """O Pedido de implantacao de que o bug veio pelo "Achei um problema"
    (issue #2210), ou `None`."""
    pedido_id = bug.get("pedido_origem_id")
    return buscar(supabase, str(pedido_id)) if pedido_id else None


def prd_de_origem(supabase, pedido: dict[str, Any]) -> str | None:
    """A referencia ao PRD da entrega do Pedido, como o GitHub a le na issue
    do bug (que nasce no Hospital): "#1700", ou "dono/repo#12" de outro
    Projeto. `None` sem card vinculado."""
    demandas = supabase.table(TABELA_DEMANDAS).select("*").eq("id", pedido["demanda_id"]).execute().data or []
    numero = demandas[0].get("github_issue_numero") if demandas else None
    if not numero:
        return None
    projeto = str(demandas[0].get("projeto") or github_client.PROJETO_HOSPITAL)
    repositorio = "" if projeto == github_client.PROJETO_HOSPITAL else github_client.repositorio_do_projeto(projeto)
    return f"{repositorio}#{numero}"


def ligar_o_bug(supabase, bug: dict[str, Any], pedido: dict[str, Any]) -> None:
    """Depois do Criar o card (issue #2210, ADR 0111, decisao 9): a Demanda de
    bug guarda de qual Demanda veio, e o Pedido passa a esperar por ela. O
    Pedido continua aberto; o PRD de origem nao reabre."""
    bug_id = str(bug["id"])
    supabase.table(TABELA_DEMANDAS).update({"demanda_origem_id": str(pedido["demanda_id"])}).eq("id", bug_id).execute()
    supabase.table(TABELA_PERGUNTAS).update({"espera_demanda_id": bug_id}).eq("id", str(pedido["id"])).execute()


def _exigir_a_label_da_implantacao(numero: int, projeto: str) -> None:
    """So o card com a label `implantacao` vira Pedido de implantacao (ADR
    0111, decisao 3): o app le a label no GitHub, e nao no que a ponte diz.
    Sem conseguir ler, recusa: nada e gravado."""
    try:
        dados = github_client.ler_issue(numero, projeto=projeto)
    except github_client.IssueNaoEncontradaError as erro:
        raise PerguntaRecusadaError(MOTIVO_CARD_NAO_EXISTE.format(projeto=projeto)) from erro
    except (github_client.GithubNaoConfiguradoError, github_client.GithubIndisponivelError) as erro:
        raise PerguntaRecusadaError(MOTIVO_SEM_CONFERIR_O_CARD.format(erro=erro)) from erro
    labels = {str(label.get("name")) for label in dados.get("labels") or [] if isinstance(label, dict)}
    if github_client.e_pull_request(dados) or LABEL_DA_IMPLANTACAO not in labels:
        raise PerguntaRecusadaError(MOTIVO_SEM_LABEL_DE_IMPLANTACAO)


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
    """O Pedido com passos e checks: o Passo a passo e o Pedido de implantacao."""
    return pedido.get("tipo") in TIPOS_COM_PASSOS


def e_implantacao(pedido: dict[str, Any]) -> bool:
    return pedido.get("tipo") == TIPO_IMPLANTACAO


def implantacao_aberta(supabase, demanda_id: str) -> list[dict[str, Any]]:
    """Os Pedidos de implantacao ainda abertos da Demanda, do mais antigo ao
    mais novo: o que falta o hospital fazer para usar a entrega (ADR 0111,
    decisao 11). O `/mensagem-prd` le pela ponte (issue #2213)."""
    linhas = (
        supabase.table(TABELA_PERGUNTAS)
        .select("id, assunto, criado_em")
        .eq("demanda_id", demanda_id)
        .eq("tipo", TIPO_IMPLANTACAO)
        .eq("estado", ESTADO_ABERTA)
        .order("criado_em")
        .order("id")
        .execute()
        .data
        or []
    )
    return [{"id": str(p["id"]), "assunto": p.get("assunto") or ""} for p in linhas]


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
    esperados: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    estado = p.get("estado") or ESTADO_ABERTA
    passo_a_passo = e_passo_a_passo(p)
    return {
        "id": str(p["id"]),
        "tipo": p["tipo"] if passo_a_passo else TIPO_PERGUNTA,
        # O Passo a passo (issue #2176): os passos com o check, a conclusao e
        # o fechamento no GitHub. Vazios na Pergunta.
        "passos": _passos(p, historico or [], nomes) if passo_a_passo else [],
        "conclusao": _conclusao(p, nomes),
        "fechamento": _fechamento(p),
        # O Reenviar do "Não chegou ao GitHub": quem pode agir no Pedido.
        "pode_reenviar": ator is not None and _cabe_reenviar(p) and pode_responder(p, ator),
        # A espera (issue #2208): o Pedido esperado enquanto nao esta concluido.
        "espera": _espera(p, esperados or {}),
        # A Demanda de bug do "Achei um problema" (issue #2210) ate ser entregue.
        "espera_demanda": _espera_demanda(p, esperados or {}),
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


def _esperados(supabase, pedidos: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Os Pedidos e as Demandas de bug que estes esperam, pelo id, lidos
    agora (o estado de agora e o que libera o Concluir). Os ids sao uuid de
    duas tabelas, e por isso cabem no mesmo dicionario."""
    lidos: dict[str, dict[str, Any]] = {}
    ids = sorted({str(p["espera_pedido_id"]) for p in pedidos if p.get("espera_pedido_id")})
    if ids:
        linhas = supabase.table(TABELA_PERGUNTAS).select("id, assunto, estado").in_("id", ids).execute().data or []
        lidos |= {str(linha["id"]): linha for linha in linhas}
    bugs = sorted({str(p["espera_demanda_id"]) for p in pedidos if p.get("espera_demanda_id")})
    if bugs:
        linhas = (
            supabase.table(TABELA_DEMANDAS).select("id, numero, etapa, apagada_em").in_("id", bugs).execute().data or []
        )
        lidos |= {str(linha["id"]): linha for linha in linhas}
    return lidos


def _espera(pedido: dict[str, Any], esperados: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """O Pedido esperado enquanto ele nao esta concluido, ou `None`. O
    cancelado continua segurando: so a conclusao libera (ADR 0111, decisao 8)."""
    espera_id = pedido.get("espera_pedido_id")
    if not espera_id:
        return None
    esperado = esperados.get(str(espera_id)) or {}
    if esperado.get("estado") == ESTADO_CONCLUIDA:
        return None
    return {"pedido_id": str(espera_id), "assunto": str(esperado.get("assunto") or "")}


def _espera_demanda(pedido: dict[str, Any], esperados: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """A Demanda de bug que o Pedido espera enquanto ela nao foi entregue, ou
    `None` (issue #2210, ADR 0111, decisao 9). Entregue ou Em producao
    libera; a apagada tambem, porque nao ha mais o que esperar."""
    bug_id = pedido.get("espera_demanda_id")
    if not bug_id:
        return None
    bug = esperados.get(str(bug_id)) or {}
    if bug.get("etapa") in ETAPAS_DO_BUG_ENTREGUE or bug.get("apagada_em"):
        return None
    return {"demanda_id": str(bug_id), "numero": bug.get("numero")}


def cartao(supabase, pedido: dict[str, Any], *, ator: dict[str, Any] | None) -> dict[str, Any]:
    """O cartao de um Pedido, com os checks e os nomes lidos agora."""
    historico = _historico(supabase, [str(pedido["id"])]).get(str(pedido["id"]), [])
    nomes = _nomes(supabase, _pessoas_da_pergunta(pedido) | _pessoas_dos_checks(historico))
    demandas = supabase.table(TABELA_DEMANDAS).select("*").eq("id", pedido["demanda_id"]).execute().data or []
    projeto = nome_do_projeto(demandas[0]) if demandas else ""
    return _cartao(
        pedido, projeto=projeto, nomes=nomes, ator=ator, historico=historico, esperados=_esperados(supabase, [pedido])
    )


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
    esperados = _esperados(supabase, linhas)
    return {
        str(p["mensagem_id"]): _cartao(
            p,
            projeto=projeto,
            nomes=nomes,
            ator=ator,
            historico=historicos.get(str(p["id"]), []),
            esperados=esperados,
        )
        for p in linhas
        if p.get("mensagem_id")
    }


# A situacao de cada Pedido de implantacao na secao Implantacao do Documento
# do card (issue #2209, ADR 0111, decisao 5). `esperando` e o Pedido que
# espera outro ou a Demanda de bug (decisoes 8 e 9), que chegam pelas issues
# #2208 e #2210: ate la, a `espera` sai nula.
SITUACAO_FEITO = "feito"
SITUACAO_ABERTO = "aberto"

# O cliente do PostgREST poe o `in_` na querystring (cerca de 38 bytes por
# UUID): algumas centenas de ids estouram o header do proxy, e a lista do chat
# manda todas as Demandas. Mesmo teto de `contas_medicas/painel.py`.
LOTE_DE_IDS = 100


def implantacao_das_demandas(supabase, demanda_ids: list[str]) -> dict[str, dict[str, Any]]:
    """A Implantacao de cada Demanda que tem Pedido de implantacao, numa
    leitura so: os feitos, o total e cada Pedido (o titulo, o Destinatario, a
    situacao e a espera), na ordem em que nasceram. O cancelado nao conta. A
    Demanda sem Pedido de implantacao fica fora do dicionario."""
    if not demanda_ids:
        return {}
    linhas: list[dict[str, Any]] = []
    for inicio in range(0, len(demanda_ids), LOTE_DE_IDS):
        linhas += (
            supabase.table(TABELA_PERGUNTAS)
            .select("id, demanda_id, assunto, destinatario_id, estado, criado_em")
            .eq("tipo", TIPO_IMPLANTACAO)
            .in_("demanda_id", demanda_ids[inicio : inicio + LOTE_DE_IDS])
            .order("criado_em")
            .execute()
            .data
            or []
        )
    vivos = [p for p in linhas if p.get("estado") != ESTADO_CANCELADA]
    nomes = _nomes(supabase, {str(p.get("destinatario_id") or "") for p in vivos})
    por_demanda: dict[str, dict[str, Any]] = {}
    for p in vivos:
        feito = p.get("estado") == ESTADO_CONCLUIDA
        implantacao = por_demanda.setdefault(str(p["demanda_id"]), {"feitos": 0, "total": 0, "pedidos": []})
        implantacao["total"] += 1
        implantacao["feitos"] += int(feito)
        implantacao["pedidos"].append(
            {
                "titulo": p.get("assunto") or "",
                "destinatario": nomes.get(str(p.get("destinatario_id"))),
                "situacao": SITUACAO_FEITO if feito else SITUACAO_ABERTO,
                "espera": None,
            }
        )
    return por_demanda


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
    esperados = _esperados(supabase, abertas)
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
                    p,
                    projeto=nome_do_projeto(demanda),
                    nomes=nomes,
                    ator=ator,
                    historico=historicos.get(str(p["id"])),
                    esperados=esperados,
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
    de sistema com ele. A aberta sai da lista Esperando voce, que so
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
            f"{NOME_DO_TIPO.get(pergunta.get('tipo') or TIPO_PERGUNTA, 'Pergunta')} "
            f"{'cancelado' if e_passo_a_passo(pergunta) else 'cancelada'}: "
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
        "tipo": pedido["tipo"],
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
MARCADOR_DA_IMPLANTACAO_CONCLUIDA = "<!-- pedido-da-vitta: implantacao-concluida -->"


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
    # O Pedido de implantacao (ADR 0111, decisao 7) comenta o mesmo fato, com
    # o marcador e o nome dele.
    marcador, nome = (
        (MARCADOR_DA_IMPLANTACAO_CONCLUIDA, "Pedido de implantação")
        if e_implantacao(pedido)
        else (MARCADOR_DO_COMENTARIO, "Passo a passo")
    )
    return f"{marcador}\n{nome} concluído no app em {_hora_local(pedido['concluida_em'])}, {quem}.\n\n{checks}"


def _motivo_da_falha(erro: Exception) -> str:
    if isinstance(erro, github_client.GithubNaoConfiguradoError):
        return MOTIVO_GITHUB_SEM_ACESSO
    return f"O GitHub não aceitou ({erro})."[:500]


# O comentario fixo com que o Pedido de implantacao fecha o card ao nascer
# (ADR 0111, decisao 4).
COMENTARIO_DO_NASCIMENTO_DA_IMPLANTACAO = (
    "<!-- pedido-da-vitta: virou-implantacao -->\nVirou Pedido de implantação no app."
)


def _cabe_reenviar(pedido: dict[str, Any]) -> bool:
    """O fechamento falhou e ainda vale tentar de novo: o Passo a passo
    concluido, ou o Pedido de implantacao que nao foi cancelado (o dele fecha
    o card ao nascer)."""
    if pedido.get("fechamento_github") != FECHAMENTO_FALHOU:
        return False
    if e_implantacao(pedido):
        return pedido.get("estado") != ESTADO_CANCELADA
    return pedido.get("estado") == ESTADO_CONCLUIDA


def _comentario_do_destinatario(supabase, pedido: dict[str, Any]) -> str:
    destinatario = _participantes(supabase, {str(pedido.get("destinatario_id") or "")})
    return comentario_de_fechamento(
        pedido,
        destinatario_e_desenvolvedor=e_desenvolvedor(destinatario.get(str(pedido.get("destinatario_id") or ""))),
    )


def _fechar_o_card(supabase, pedido: dict[str, Any]) -> dict[str, Any]:
    """Comenta e fecha o card como feito, e grava o desfecho: `fechado`, ou
    `falhou` com o motivo (decisao 8). Nunca tenta de novo sozinho. O Passo a
    passo fecha com o comentario da conclusao; o Pedido de implantacao, com o
    comentario fixo do nascimento."""
    if e_implantacao(pedido):
        comentario = COMENTARIO_DO_NASCIMENTO_DA_IMPLANTACAO
    else:
        comentario = _comentario_do_destinatario(supabase, pedido)
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
    com o fechamento `falhou`. Devolve o cartao e a mensagem da anotacao.

    O Pedido de implantacao (issue #2207, ADR 0111, decisao 7) fechou o card
    ao nascer: concluir so comenta na issue fechada, nunca chama o
    fechamento, e nao mexe no fechamento do nascimento. O comentario que
    falha so vai ao log: a conclusao ja esta gravada no app.

    O Pedido que espera outro (issue #2208) so conclui com o esperado
    concluido; antes, recusa com o motivo numa linha."""
    _do_passo_a_passo_aberto(pedido, ator)
    esperados = _esperados(supabase, [pedido])
    espera = _espera(pedido, esperados)
    if espera:
        raise ConclusaoRecusadaError(MOTIVO_ESPERA_ABERTA.format(assunto=" ".join(espera["assunto"].split())))
    bug = _espera_demanda(pedido, esperados)
    if bug:
        raise ConclusaoRecusadaError(MOTIVO_ESPERA_O_BUG.format(numero=bug["numero"]))
    historico = _historico(supabase, [str(pedido["id"])]).get(str(pedido["id"]), [])
    if not _todos_marcados(pedido, historico):
        raise ConclusaoRecusadaError(MOTIVO_FALTA_CHECK)
    anotacao = _limpo(anotacao)
    implantacao = e_implantacao(pedido)
    fechamento = {} if implantacao else {"fechamento_github": FECHAMENTO_PENDENTE, "fechamento_motivo": None}
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
                **fechamento,
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
    _linha_de_sistema(
        supabase, demanda, gravadas[0], f"{NOME_DO_TIPO[pedido['tipo']]} concluído: {pedido.get('assunto') or ''}"
    )
    mensagem = None
    if anotacao:
        mensagem = tecnologia_conversa.escrever(
            supabase, demanda, autor=ator, texto=f"Anotação: {anotacao}", origem=tecnologia_conversa.ORIGEM_APP
        )
    concluido = _comentar_a_conclusao(supabase, gravadas[0]) if implantacao else _fechar_o_card(supabase, gravadas[0])
    return cartao(supabase, concluido, ator=ator), mensagem


def _comentar_a_conclusao(supabase, pedido: dict[str, Any]) -> dict[str, Any]:
    """So o comentario da conclusao na issue ja fechada do Pedido de
    implantacao, sem fechar nada. A falha fica no log."""
    try:
        github_client.comentar(
            int(pedido["card_numero"]),
            _comentario_do_destinatario(supabase, pedido),
            projeto=str(pedido.get("card_projeto") or ""),
        )
    except (github_client.GithubNaoConfiguradoError, github_client.GithubIndisponivelError) as erro:
        logger.warning(
            f"[tecnologia_perguntas] A conclusão do Pedido de implantação {pedido.get('id')} não chegou: {erro}"
        )
    return pedido


def reenviar(supabase, pedido: dict[str, Any], *, ator: dict[str, Any]) -> dict[str, Any]:
    """O Reenviar do "Não chegou ao GitHub" (decisao 8): tenta de novo
    comentar e fechar o card, so quando o fechamento falhou. Devolve o cartao."""
    if not pode_responder(pedido, ator):
        raise RespostaProibidaError(MOTIVO_SO_QUEM_FAZ)
    if not _cabe_reenviar(pedido):
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
