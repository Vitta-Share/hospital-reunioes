"""A Pergunta da Vitta (issue #2116, PRD #2112, ADR 0109, decisoes 1 e 3).

A pergunta que a Vitta manda a alguem do Hospital, pela ponte de automacao,
vira um registro do app ligado a uma Demanda: Destinatario, Assunto, o texto,
as quatro linhas do cartao (por que precisa da pessoa, o que esta parado, o
que anda depois e o ganho), as opcoes com a recomendada e o porque, e o
estado. Nasce aberta.

Todas as regras da Pergunta moram aqui (criar, e nas proximas Fatias
responder, resolver, cancelar, listar e lembrar); as rotas nao repetem regra.

Criar gravava a entrada da Pergunta na Conversa da Demanda, pelo mesmo
servico das mensagens, que avisava so o Destinatario com "Pede sua resposta"
e o Assunto (ADR 0106). Depois vinha a linha de sistema "Pergunta aberta",
pela mesma origem `sistema` da linha do Envio aos desenvolvedores (ADR 0108).

O nome e Pergunta da Vitta, nunca Pendencia (ADR 0109, decisao 2): Pendencia e
a Acao da Ata.

Desde a issue #2279 (ADR 0113, decisao 7) o app nao age mais sobre o Pedido:
sairam a lista Esperando voce, a resposta no cartao, o check, o Concluir e o
Reenviar. Desde a issue #2281 a ponte tambem nao cria, nao le, nao resolve e
nao cancela Pedido. Ficam, para os Pedidos que ja estao no banco, o lembrete
(o agendador) e o acompanhamento do GitHub (o webhook).

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
from datetime import UTC, datetime, timedelta
from typing import Any

from app.dependencies import selecionar_participantes
from app.services import github_client, tecnologia_email
from app.services.notificacao_service import criar_notificacao_tecnologia
from app.services.paginacao import ler_tudo
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
TIPOS_COM_PASSOS = (TIPO_PASSO_A_PASSO, TIPO_IMPLANTACAO)

# Os estados da Pergunta (CHECK da migration 211, ADR 0109, decisao 1).
ESTADO_ABERTA = "aberta"
ESTADO_RESPONDIDA = "respondida"
ESTADO_RESOLVIDA = "resolvida"
ESTADO_CANCELADA = "cancelada"
# So do Passo a passo (migration 232): aberta, concluida e cancelada.
ESTADO_CONCLUIDA = "concluida"

CONCLUIDA_PELO_GITHUB = "github"
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

# A Demanda de bug entregue solta o Pedido que espera por ela.
ETAPAS_DO_BUG_ENTREGUE = (ETAPA_ENTREGUE, ETAPA_EM_PRODUCAO)


def _agora() -> datetime:
    """O relogio do modulo: o teste do webhook pode fixar a hora por aqui."""
    return datetime.now(UTC)


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


# ─── O estado final no cartao (issue #2121, ADR 0109, decisao 6) ────────────


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


# ─── O Reenviar no cartao e a linha de sistema (issue #2176, ADR 0110) ──────


def _cabe_reenviar(pedido: dict[str, Any]) -> bool:
    """O fechamento falhou e ainda vale tentar de novo: o Passo a passo
    concluido, ou o Pedido de implantacao que nao foi cancelado (o dele fecha
    o card ao nascer)."""
    if pedido.get("fechamento_github") != FECHAMENTO_FALHOU:
        return False
    if e_implantacao(pedido):
        return pedido.get("estado") != ESTADO_CANCELADA
    return pedido.get("estado") == ESTADO_CONCLUIDA


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
