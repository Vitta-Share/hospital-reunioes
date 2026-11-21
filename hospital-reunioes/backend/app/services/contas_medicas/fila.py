"""A Fila de contas de Contas médicas (issue #1307, ADR 0073).

A Fila é comum: toda conta com Guia pronto (`A_FAZER`) é livre, qualquer que
seja o `faturista_id`, e ganha dono quando uma faturista abre o Guia dela
(puxar a conta). Quem envia não vira dono: quem enviou fica em
`cm_envio.usuario_id`, e é quem acompanha a conta até ela ficar pronta.
"""

from __future__ import annotations

from app.dependencies import selecionar_participantes

# A conta com Guia pronto que ninguém puxou.
LIVRE = "A_FAZER"
# A que a faturista puxou e está trabalhando: a única que volta para a Fila.
EM_CORRECAO = "EM_CORRECAO"
SO_EM_CORRECAO_VOLTA = "Só a conta Em correção volta para a Fila"
# As que a faturista puxou e ainda não concluiu.
COM_A_FATURISTA = (EM_CORRECAO, "RETORNO")
# As que ainda não ficaram prontas: ficam com quem enviou, que tem o PDF.
NAO_PRONTAS = ("AGUARDANDO_ARQUIVO", "NA_FILA", "PROCESSANDO", "ERRO")
CONCLUIDAS = ("CONCLUIDA", "CONCLUIDA_COM_PENDENCIA")
# A aba Concluídas mostra as mais recentes; o resto fica no banco para o Painel.
TETO_DE_CONCLUIDAS = 100


def _contas(supabase, situacoes, *, de: str | None = None, recentes_primeiro: bool = False) -> list[dict]:
    """As contas nas situações, em ordem de envio. Com `de`, só as em que a
    pessoa é `faturista_id`; com `recentes_primeiro`, as mais recentes até o teto."""
    consulta = supabase.table("cm_conta").select("*").in_("situacao", list(situacoes))
    if de is not None:
        consulta = consulta.eq("faturista_id", de)
    consulta = consulta.order("ordem_fila", desc=recentes_primeiro)
    if recentes_primeiro:
        consulta = consulta.limit(TETO_DE_CONCLUIDAS)
    return consulta.execute().data or []


def _concluidas(supabase, me: dict) -> list[dict]:
    """As Concluídas mais recentes de todas e, junto, as mais recentes da
    pessoa, para o filtro "Minhas" não ficar vazio quando as colegas
    concluíram muitas depois dela (issue #1955)."""
    de_todas = _contas(supabase, CONCLUIDAS, recentes_primeiro=True)
    vistas = {c["id"] for c in de_todas}
    dela = [c for c in _contas(supabase, CONCLUIDAS, de=me.get("id"), recentes_primeiro=True) if c["id"] not in vistas]
    return sorted(de_todas + dela, key=lambda c: c.get("ordem_fila") or 0, reverse=True)


def _quantas_concluidas(supabase, de: str | None = None) -> int:
    """Todas as Concluídas, ou só as da pessoa com `de`, sem o teto da lista:
    é o número da Esteira (issue #1951). Conta no banco: a leitura volta
    cortada no `max_rows` do PostgREST, sem aviso."""
    consulta = supabase.table("cm_conta").select("id", count="exact").in_("situacao", list(CONCLUIDAS))
    if de is not None:
        consulta = consulta.eq("faturista_id", de)
    return consulta.limit(1).execute().count or 0


def ve_todas(me: dict) -> bool:
    """Quem tem "painel completo" vê os envios de todas e abre a conta de
    qualquer faturista."""
    return "painel_completo" in me["permissoes_cm"]


def fila_da_pessoa(supabase, me: dict) -> dict:
    """As listas de quem analisa, em ordem de envio (nunca por valor): a Fila
    (as livres, a mesma para todas), "minhas" (as Em análise de todas as
    faturistas, nome antigo da lista) e as Concluídas de todas, as mais
    recentes primeiro (issue #1955, ADR 0105 decisão 1).

    Cada conta Em análise ou Concluída vem com `com_quem`, o nome da faturista
    que está com ela, e diz se é da própria pessoa (`minha`): o filtro "Minhas"
    da tela é sobre essa marca. `todas` diz se a pessoa abre as das outras
    (decisão 2). A `contagem` dá o número de cada etapa da Esteira (issue
    #1951), e a `contagem_minhas`, o de Em análise e Concluídas em "Minhas"."""
    livres = _contas(supabase, (LIVRE,))
    em_analise = _contas(supabase, COM_A_FATURISTA)
    concluidas = _concluidas(supabase, me)

    for conta in livres:
        conta["com_quem"] = None
        conta["minha"] = False
    for conta in em_analise + concluidas:
        conta["com_quem"] = conta.get("faturista_id")
        conta["minha"] = conta.get("faturista_id") == me.get("id")
    _trocar_id_por_nome(supabase, em_analise + concluidas)
    contagem = {"fila": len(livres), "em_analise": len(em_analise), "concluidas": _quantas_concluidas(supabase)}
    contagem_minhas = {
        "em_analise": sum(1 for conta in em_analise if conta["minha"]),
        "concluidas": _quantas_concluidas(supabase, me.get("id")),
    }
    return {
        "todas": ve_todas(me),
        "fila": livres,
        "minhas": em_analise,
        "concluidas": concluidas,
        "contagem": contagem,
        "contagem_minhas": contagem_minhas,
    }


def envios_da_pessoa(supabase, me: dict) -> dict:
    """ "Meus envios": as contas que a pessoa enviou e ainda não ficaram prontas,
    em ordem de envio. Quem tem "painel completo" vê as de todos, cada uma com
    o nome de quem enviou em `com_quem`."""
    todas = ve_todas(me)
    nao_prontas = _contas(supabase, NAO_PRONTAS)
    enviou, ambiguas = _quem_enviou(supabase, nao_prontas)
    envios = nao_prontas if todas else [c for c in nao_prontas if enviou.get(c["id"]) == me.get("id")]
    for conta in envios:
        conta["com_quem"] = enviou.get(conta["id"]) if todas else None
        # A mesma regra de posse do descarte: com prontuário de mais de uma
        # pessoa e sem conta, só a gestão descarta (issue #1338).
        conta["so_a_gestao_descarta"] = not todas and conta["id"] in ambiguas
    if todas:
        _trocar_id_por_nome(supabase, envios)
    return {"todas": todas, "meus_envios": envios, "contagem": {"envios": len(envios)}}


def quem_enviou(supabase, conta: dict) -> str | None:
    """O `cm_envio.usuario_id` de quem enviou a conta, pela regra de "Meus
    envios", em qualquer situação (o painel lateral, issue #1418)."""
    enviou, _ = _quem_enviou(supabase, [conta])
    return enviou.get(conta["id"])


def _por_id(supabase, tabela: str, coluna: str, valores, **filtros) -> list[dict]:
    valores = list(dict.fromkeys(v for v in valores if v))
    if not valores:
        return []
    consulta = supabase.table(tabela).select("*").in_(coluna, valores)
    for campo, valor in filtros.items():
        consulta = consulta.eq(campo, valor)
    return consulta.execute().data or []


def _quem_enviou(supabase, contas: list[dict]) -> tuple[dict[str, str], set[str]]:
    """O `cm_envio.usuario_id` de cada conta, pelo arquivo dela. A conta à
    espera da Conta ainda não tem arquivo: quem enviou é quem mandou o
    Prontuário do atendimento. Junto, as contas à espera da Conta cujo
    prontuário veio de mais de uma pessoa (a posse ambígua do descarte)."""
    da_conta = {a["id"]: a for a in _por_id(supabase, "cm_arquivo", "id", (c.get("arquivo_id") for c in contas))}
    prontuarios = _por_id(
        supabase,
        "cm_arquivo",
        "atendimento_id",
        (c.get("atendimento_id") for c in contas if not c.get("arquivo_id")),
        tipo="PRONTUARIO",
    )
    do_atendimento = {a["atendimento_id"]: a for a in prontuarios}
    arquivo_de = {
        c["id"]: da_conta.get(c["arquivo_id"]) if c.get("arquivo_id") else do_atendimento.get(c.get("atendimento_id"))
        for c in contas
    }
    envios = _por_id(supabase, "cm_envio", "id", (a["envio_id"] for a in [*arquivo_de.values(), *prontuarios] if a))
    usuario_do_envio = {e["id"]: e.get("usuario_id") for e in envios}
    remetentes: dict[str, set] = {}
    for p in prontuarios:
        remetentes.setdefault(p["atendimento_id"], set()).add(usuario_do_envio.get(p.get("envio_id")))
    ambiguas = {
        c["id"] for c in contas if not c.get("arquivo_id") and len(remetentes.get(c.get("atendimento_id"), ())) > 1
    }
    return {cid: usuario_do_envio.get(a["envio_id"]) for cid, a in arquivo_de.items() if a}, ambiguas


def _trocar_id_por_nome(supabase, contas: list[dict]) -> None:
    ids = list({c["com_quem"] for c in contas if c.get("com_quem")})
    nomes = {}
    if ids:
        pessoas = selecionar_participantes(supabase, "id, nome_completo", lambda q: q.in_("id", ids)).data or []
        nomes = {p["id"]: p.get("nome_completo") for p in pessoas}
    for conta in contas:
        conta["com_quem"] = nomes.get(conta.get("com_quem"))


def puxar(supabase, conta_id: str, pessoa_id: str, agora: str) -> bool:
    """A conta livre passa a ser de quem abriu. O UPDATE é condicional na
    situação: de duas aberturas ao mesmo tempo, só uma grava, e a outra recebe
    `False`."""
    gravadas = (
        supabase.table("cm_conta")
        .update({"situacao": "EM_CORRECAO", "aberta_em": agora, "faturista_id": pessoa_id})
        .eq("id", conta_id)
        .eq("situacao", LIVRE)
        .execute()
        .data
        or []
    )
    return bool(gravadas)


def devolver(supabase, conta_id: str, dona_lida: str | None) -> bool:
    """A conta Em correção volta livre para a Fila (issue #1309). Só a dona e
    a situação mudam: `ordem_fila`, `aberta_em` e as marcações ficam. O UPDATE
    é condicional na situação e na dona lida: a conta concluída ou passada a
    outra faturista entre a leitura e a escrita não volta (issue #1328).
    A dona lida pode ser nula (pessoa apagada, ON DELETE SET NULL): aí o
    filtro é `is null`, porque `eq` com None vira `eq.None` e não casa nada."""
    consulta = (
        supabase.table("cm_conta")
        .update({"situacao": LIVRE, "faturista_id": None})
        .eq("id", conta_id)
        .eq("situacao", EM_CORRECAO)
    )
    if dona_lida is None:
        consulta = consulta.is_("faturista_id", "null")
    else:
        consulta = consulta.eq("faturista_id", dona_lida)
    gravadas = consulta.execute().data or []
    return bool(gravadas)


def primeira_livre(supabase) -> str | None:
    """A primeira conta livre na ordem de envio, de quem quer que tenha enviado."""
    livres = (
        supabase.table("cm_conta").select("id").eq("situacao", LIVRE).order("ordem_fila").limit(1).execute().data or []
    )
    return livres[0]["id"] if livres else None
