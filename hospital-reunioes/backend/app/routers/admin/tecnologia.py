"""Router /admin/tecnologia, a aba Tecnologia (PRD #634, ADR 0050).

Desde a issue #2279 (ADR 0113, decisoes 6 e 7) a aba so informa: o Quadro, com
a Etapa de cada Demanda, e as Entregas. Sairam as rotas que escreviam ou
chamavam a IA: o chat do Assistente de Tecnologia com o Planejamento e o Criar
o card, o seletor de modelo, a Conversa da Demanda, o Envio aos
desenvolvedores, a lista Esperando voce com os cartoes de Pergunta e Passo a
passo, o Me explique, o Revisar com o codigo de hoje, o Apagar, o Reenviar, o
Designar de novo e a leitura do print do chat. As tabelas ficam no banco.

Todos os endpoints exigem `require_super_admin`. Esse e o gate de verdade: a
sidebar apenas esconde o item, e esconder nao e proteger (ADR 0050, decisao 2).

- GET   /admin/tecnologia/eu                    se quem esta logado e
                                                Desenvolvedor (ADR 0083).
- GET   /admin/tecnologia/chat                  o Quadro: as Demandas, da
                                                mais recente para a mais
                                                antiga, com o recorte do
                                                Desenvolvedor (`?filtro=`), a
                                                busca pelo titulo e os
                                                filtros Tipo, Etapa, Origem,
                                                Projeto, Responsavel e Envio
                                                falhou (issue #1551).
- GET   /admin/tecnologia/entregas              a aba Entregas: o ritmo
                                                (pedidos e entregas das 4
                                                ultimas semanas e das 12 do
                                                grafico) e os cards
                                                entregues, com filtros de
                                                tipo, Origem e Responsavel.
                                                So leitura (issues #1556 e
                                                #1701).
- GET   /admin/tecnologia/desenvolvedores       as opcoes do filtro
                                                Responsavel (ADR 0083).
- GET   /admin/tecnologia/projetos              as opcoes do filtro Projeto
                                                (issue #1967).

Fora daqui, e de pe: o webhook do GitHub que deriva a Etapa
(`routers/webhooks.py`), a ponte de automacao (`routers/tecnologia_automacao.py`),
o bug do Assistente do app (`routers/assistente_do_app.py`) e o cron de hora em
hora (`cron/scheduler.py`).
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, date, datetime
from typing import Literal, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.config import settings
from app.dependencies import get_supabase_client, require_super_admin, selecionar_participantes
from app.models.tecnologia_schemas import (
    DemandaResponse,
    DesenvolvedorResponse,
    EntregasResponse,
    QuemSouNaAbaResponse,
)
from app.services import (
    github_client,
    tecnologia_entregas,
    tecnologia_envio,
)
from app.services.github_client import FORMATO_DO_PROJETO
from app.services.tecnologia import (
    CLASSIFICACAO_DO_TIPO,
    TABELA_DEMANDAS,
    TIPO_DA_CLASSIFICACAO,
    e_desenvolvedor,
    em_producao_desde,
    entregue_na_data,
    login_do_responsavel,
    nome_do_projeto,
    origem_da_demanda,
    pode_ver,
    projeto_da_demanda,
    projetos_do_filtro,
    responsavel_da_demanda,
    versao_da_entrega,
)
from app.services.tecnologia_vinculo import (
    ETAPA_REGISTRADA,
    ETAPAS,
    ajuste_aberto_da_foto,
    implantacao_da_foto,
    login_para_publicar,
    normalizar_github_login,
)

router = APIRouter(prefix="/admin/tecnologia", tags=["admin", "tecnologia"])


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _recusar(motivo: str) -> NoReturn:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=motivo)


def _para_a_lista(supabase: Client, demandas: list[dict], *, ator: dict) -> list[dict]:
    """A Demanda como a lista lateral do chat a le (issue #1384).

    E o funil por onde a Demanda sai desta API. Desde a issue #2265 (ADR 0113,
    decisao 6) todo Super admin le a mesma coisa: o autor, o numero e o link
    da issue, o Responsavel, o selo "Envio falhou" com o motivo (issue #1535)
    e a designacao falhada (issue #1536). O login do GitHub no cadastro nao
    corta mais nada aqui. Desde a issue #2279 (ADR 0113, decisao 7) a aba so
    le: sem o `pode_apagar` e o `pode_revisar` dos botoes que sairam. A `origem`
    da o selo "Pedido do diretor" ou "Vitta" (issue #1554), e o `projeto`, o
    selo do Aplicativo do Hospital ou da Ana (issue #1715).
    """
    ids = {responsavel_da_demanda(d) for d in demandas} | {d.get("autor_id") for d in demandas}
    nomes = _nomes(supabase, ids)
    implantacoes = _implantacoes(supabase, demandas)
    return [
        {
            **d,
            "tem_vinculo": bool(d.get("github_issue_numero")),
            "partes": _partes_visiveis(d),
            "versao": versao_da_entrega(d),
            "fechada_em": entregue_na_data(d),
            "em_producao_em": em_producao_desde(d),
            "classificacao": CLASSIFICACAO_DO_TIPO.get(str(d.get("tipo") or "")),
            "minha": d.get("autor_id") == ator["id"],
            "autor": nomes.get(str(d.get("autor_id"))),
            # O numero da raiz para todos (issue #1902, ADR 0100, decisao 1),
            # e o link tambem desde a issue #2265.
            "raiz_numero": d.get("github_issue_numero"),
            "issue_numero": d.get("github_issue_numero"),
            "issue_url": _url_da_issue(d),
            **_plano_validado_e_ajuste(d),
            "responsavel": _nome_do_responsavel(d, nomes),
            "envio_falhou": tecnologia_envio.envio_falhou(d),
            "designacao_falhou": tecnologia_envio.designacao_falhou(d),
            "envio_motivo": d.get("envio_motivo") if _falha_pendente(d) else None,
            "origem": origem_da_demanda(d),
            "projeto": projeto_da_demanda(d),
            "projeto_nome": nome_do_projeto(d),
            # A secao Implantacao e o selo do Quadro, lidos dos Cards de
            # implantacao (issue #2266, ADR 0113, decisao 9); nula sem nenhum.
            "implantacao": implantacoes.get(str(d["id"])),
        }
        for d in demandas
    ]


def _implantacoes(supabase: Client, demandas: list[dict]) -> dict[str, dict]:
    """A Implantacao de cada Demanda, lida da foto que a sincronizacao guardou
    (issue #2266, ADR 0113, decisao 9), com o nome de quem tem cada card no
    lugar do login quando ele e usuario do app. A Demanda sem Card de
    implantacao fica fora do dicionario."""
    por_demanda = {}
    for d in demandas:
        foto = d.get("github_foto") if isinstance(d.get("github_foto"), dict) else None
        implantacao = implantacao_da_foto(foto)
        if implantacao is not None:
            por_demanda[str(d["id"])] = implantacao
    logins = sorted(
        {
            normalizar_github_login(p["destinatario"])
            for i in por_demanda.values()
            for p in i["pedidos"]
            if normalizar_github_login(p["destinatario"])
        }
    )
    if not logins:
        return por_demanda
    result = selecionar_participantes(supabase, "github_login, nome_completo", lambda q: q.in_("github_login", logins))
    nomes = {p.get("github_login"): p.get("nome_completo") for p in (result.data or []) if p.get("nome_completo")}
    for implantacao in por_demanda.values():
        for pedido in implantacao["pedidos"]:
            pedido["destinatario"] = (
                nomes.get(normalizar_github_login(pedido["destinatario"])) or pedido["destinatario"]
            )
    return por_demanda


def _falha_pendente(demanda: dict) -> bool:
    """O envio ou a designacao que falhou e ainda espera alguem (issues #1535 e #1536)."""
    return tecnologia_envio.envio_falhou(demanda) or tecnologia_envio.designacao_falhou(demanda)


def _nome_do_responsavel(demanda: dict, nomes: dict[str, str]) -> str | None:
    """O Responsavel como a tela o mostra: o nome do usuario, ou o login do
    dono no GitHub quando ele nao e usuario do app (issue #1534, ADR 0083,
    decisao 6)."""
    return nomes.get(str(responsavel_da_demanda(demanda))) or login_do_responsavel(demanda)


def _nomes(supabase: Client, ids: set) -> dict[str, str]:
    ids_lidos = sorted({str(i) for i in ids if i})
    if not ids_lidos:
        return {}
    result = selecionar_participantes(supabase, "id, nome_completo", lambda q: q.in_("id", ids_lidos))
    return {str(p["id"]): p.get("nome_completo") or "" for p in (result.data or [])}


def _plano_validado_e_ajuste(demanda: dict) -> dict:
    """O selo "Plano validado em" e a faixa do Ajuste do plano (issue #1915),
    derivados da foto, com o numero e o link do Ajuste, para todo Super admin
    (issue #2265)."""
    foto = demanda.get("github_foto") if isinstance(demanda.get("github_foto"), dict) else {}
    validado = github_client.LABEL_DA_VALIDACAO in (foto.get("labels") or [])
    ajuste = ajuste_aberto_da_foto(foto)
    return {
        "validado_em": foto.get(github_client.FATO_VALIDADO_EM) if validado else None,
        "ajuste_aberto": ajuste is not None,
        "ajuste_numero": ajuste["numero"] if ajuste else None,
        "ajuste_url": ajuste["url"] if ajuste else None,
    }


def _url_da_issue(demanda: dict) -> str | None:
    """O endereco da issue-raiz: o que a foto do GitHub guardou, ou o montado
    pelo numero quando a foto ainda nao veio, no repositorio do Projeto da
    Demanda (issue #1713). O Projeto novo (issue #1967) nao tem repositorio
    configurado: o endereco e o link do PRD que a ponte gravou."""
    numero = demanda.get("github_issue_numero")
    if not numero:
        return None
    if demanda.get("raiz_url"):
        return str(demanda["raiz_url"])
    foto = demanda.get("github_foto")
    if isinstance(foto, dict) and foto.get("url"):
        return str(foto["url"])
    repo = github_client.repositorio_do_projeto(projeto_da_demanda(demanda))
    return f"https://github.com/{repo}/issues/{numero}" if repo else None


def _partes_visiveis(demanda: dict) -> list[dict]:
    """As partes da entrega como o diretor as le (issue #676): o texto, a
    situacao e a data do fechamento (issue #1552).

    Desde a issue #1902 (ADR 0100, decisoes 1 a 3), para todos que veem a
    Demanda: o numero da parte, a Onda e as bloqueadoras ainda abertas, cada
    uma dizendo se e de outro pedido. Titulo, link e labels da fatia nao saem.
    """
    partes = demanda.get("partes")
    if not isinstance(partes, list):
        return []
    return [
        {
            "numero": parte.get("numero"),
            "o_que_muda": parte.get("o_que_muda"),
            "situacao": parte.get("situacao"),
            "fechada_em": parte.get("fechada_em"),
            "onda": parte.get("onda"),
            # O Ajuste do plano sai sem numero, para todos (issue #1915): a
            # tela diz "Espera o ajuste do plano", e o numero dele e so do
            # Desenvolvedor, no `ajuste_numero`.
            "bloqueadoras": [
                {"numero": None, "de_outro_pedido": False, "ajuste_do_plano": True}
                if b.get("ajuste_do_plano")
                else {"numero": b.get("numero"), "de_outro_pedido": not b.get("da_demanda"), "ajuste_do_plano": False}
                for b in (parte.get("bloqueadoras") or [])
                if isinstance(b, dict) and b.get("estado") == "open"
            ],
        }
        for parte in partes
        if isinstance(parte, dict)
    ]


@router.get("/eu", response_model=QuemSouNaAbaResponse)
async def quem_sou_na_aba(ator: dict = Depends(require_super_admin)):
    """Se quem esta logado e Desenvolvedor (ADR 0083, decisao 2)."""
    return {"desenvolvedor": e_desenvolvedor(ator)}


def _desenvolvedores(supabase: Client) -> list[dict]:
    """Os Desenvolvedores do cadastro, pelo nome: o Super admin ativo com login
    do GitHub (ADR 0083, decisao 2). E quem pode ser Responsavel."""
    result = selecionar_participantes(
        supabase, "id, nome_completo, access_profile, is_super_admin, github_login, ativo"
    )
    pessoas = [p for p in (result.data or []) if p.get("ativo") is not False and e_desenvolvedor(p)]
    return sorted(pessoas, key=lambda p: (p.get("nome_completo") or "").casefold())


def _id_do_dono(desenvolvedores: list[dict]) -> str | None:
    """Quem tem, no cadastro, o login do dono que esta na configuracao: o
    Responsavel do card sem escolha."""
    dono = login_para_publicar(settings.github_login_dono)
    pessoa = next((p for p in desenvolvedores if dono and normalizar_github_login(p.get("github_login")) == dono), None)
    return str(pessoa["id"]) if pessoa else None


@router.get("/desenvolvedores", response_model=list[DesenvolvedorResponse])
async def listar_os_desenvolvedores(
    _ator: dict = Depends(require_super_admin),
    supabase: Client = Depends(get_supabase_client),
):
    """O "Quem cuida disto?" do resumo (ADR 0083, decisao 5). `padrao` marca
    para quem vai o card sem escolha, e a tela diz o nome."""
    desenvolvedores = _desenvolvedores(supabase)
    dono = _id_do_dono(desenvolvedores)
    return [
        {"id": str(p["id"]), "nome": p.get("nome_completo") or "", "padrao": str(p["id"]) == dono}
        for p in desenvolvedores
    ]


def _sem_acento(texto: str) -> str:
    """O texto como a busca da lista o compara: sem acento e sem caixa (issue #1551)."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn").casefold()


@router.get("/projetos")
async def listar_os_projetos(
    _ator: dict = Depends(require_super_admin),
    supabase: Client = Depends(get_supabase_client),
) -> list[dict[str, str]]:
    """As opcoes do filtro Projeto do Quadro e das Entregas (issue #1967): o
    Aplicativo do Hospital e a Ana, sempre, e cada Projeto novo que tem
    Demanda, pelo nome. A lapide do Apagar nao conta."""
    result = supabase.table(TABELA_DEMANDAS).select("projeto, projeto_nome").is_("apagada_em", "null").execute()
    return projetos_do_filtro(result.data or [])


@router.get("/chat", response_model=list[DemandaResponse])
async def listar_as_conversas(
    filtro: Literal["minhas", "todas", "para_mim"] = "minhas",
    busca: str | None = None,
    tipo: Literal["bug", "melhoria"] | None = None,
    etapa: str | None = None,
    responsavel: str | None = None,
    envio_falhou: bool = False,
    origem: Literal["diretor", "vitta", "relato"] | None = None,
    projeto: str | None = Query(default=None, pattern=FORMATO_DO_PROJETO),
    ator: dict = Depends(require_super_admin),
    supabase: Client = Depends(get_supabase_client),
):
    """A lista ao lado do chat (issue #1384): as Demandas, com o titulo e a
    Etapa, a mais recente primeiro.

    Quem corta e o `pode_ver`, a regra unica da leitura: desde a issue #2265
    (ADR 0113, decisao 6) todo Super admin ve todas, e o "Minhas" de quem nao
    e Desenvolvedor, a lista sem recorte da tela dele, traz todas. O recorte
    `todas`, `minhas` e `para_mim` continua o do Desenvolvedor (ADR 0083,
    decisoes 3 e 5): `minhas` sao as que ele pediu, `para_mim` as de que ele e
    o Responsavel.

    Por cima do recorte, e combinando entre si (issue #1551): a `busca` pelo
    titulo, sem diferenciar maiuscula e acento; o `tipo` (bug ou melhoria); a
    `etapa`; o `responsavel` (o id de quem cuida); e o `envio_falhou`, as
    Demandas cujo card nao chegou ao GitHub (issue #1535), de todos os autores
    mesmo partindo de `para_mim`, porque elas nao tem Responsavel. `para_mim`,
    `responsavel` e `envio_falhou` continuam do Desenvolvedor, como os chips
    da tela, e a rota os recusa a quem nao e. A `origem` (issue #1554) e o
    `projeto` (issue #1715, ADR 0093, decisao 8) sao para todos.

    Sai pelo `_para_a_lista`, o funil da Demanda desta API.
    """
    if not e_desenvolvedor(ator) and (filtro == "para_mim" or responsavel or envio_falhou):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Filtro so do Desenvolvedor")
    if etapa is not None and etapa not in ETAPAS:
        _recusar("Etapa desconhecida")
    # A lapide do Apagar fica fora de todo filtro (ADR 0084, decisao 2).
    consulta = supabase.table(TABELA_DEMANDAS).select("*").is_("apagada_em", "null")
    if filtro == "minhas" and e_desenvolvedor(ator):
        consulta = consulta.eq("autor_id", ator["id"])
    elif filtro == "para_mim":
        consulta = consulta.eq("responsavel_id", ator["id"])
    result = consulta.order("criado_em", desc=True).execute()
    visiveis = [d for d in (result.data or []) if pode_ver(ator, d)]
    # A Demanda em Envio falhou nao tem card, logo nao tem Responsavel: com
    # `envio_falhou`, o recorte por Responsavel (Para mim e o `responsavel`)
    # nao corta, senao a lista do Desenvolvedor, que abre em Para mim, sairia
    # sempre vazia (issue #1535).
    if filtro == "para_mim" and not envio_falhou:
        visiveis = [d for d in visiveis if responsavel_da_demanda(d) == ator["id"]]
    if busca and busca.strip():
        procurado = _sem_acento(busca.strip())
        visiveis = [d for d in visiveis if procurado in _sem_acento(str(d.get("titulo") or ""))]
    if tipo:
        visiveis = [d for d in visiveis if d.get("tipo") == TIPO_DA_CLASSIFICACAO[tipo]]
    if etapa:
        visiveis = [d for d in visiveis if (d.get("etapa") or ETAPA_REGISTRADA) == etapa]
    if responsavel and not envio_falhou:
        visiveis = [d for d in visiveis if responsavel_da_demanda(d) == responsavel]
    if envio_falhou:
        visiveis = [d for d in visiveis if tecnologia_envio.envio_falhou(d)]
    if origem:
        visiveis = [d for d in visiveis if origem_da_demanda(d) == origem]
    if projeto:
        visiveis = [d for d in visiveis if projeto_da_demanda(d) == projeto]
    return _para_a_lista(supabase, visiveis, ator=ator)


def agora_utc() -> datetime:
    """O relogio das Entregas: as semanas contam a partir dele. O teste o congela."""
    return datetime.now(UTC)


# O que o `_para_a_lista` so manda ao Desenvolvedor, e que as Entregas nao
# mandam a ninguem (PRD #1689).
_SO_DO_DESENVOLVEDOR_NAS_ENTREGAS = {
    "issue_numero": None,
    "issue_url": None,
    "envio_motivo": None,
    "designacao_falhou": False,
    "autor": None,
    # O numero da raiz, que o Documento do card mostra a todos (issue #1902):
    # as Entregas continuam sem numero de issue nenhum, nem o link do PRD do
    # Projeto novo (issue #1967).
    "raiz_numero": None,
    "raiz_url": None,
    # O selo do plano validado e a faixa do Ajuste ficam no Documento aberto
    # pela conversa (issue #1915): as Entregas nao mudam.
    "validado_em": None,
    "ajuste_aberto": False,
    "ajuste_numero": None,
    "ajuste_url": None,
}


def _partes_sem_numero(entrega: dict) -> list[dict]:
    """As partes como as Entregas as mandam (issue #1902): sem o numero da
    parte e sem as bloqueadoras, que sao numeros de issue (PRD #1689)."""
    return [{**parte, "numero": None, "bloqueadoras": []} for parte in entrega.get("partes") or []]


@router.get("/entregas", response_model=EntregasResponse)
async def listar_as_entregas(
    tipo: Literal["bug", "melhoria"] | None = None,
    origem: Literal["diretor", "vitta", "relato"] | None = None,
    responsavel: str | None = None,
    projeto: str | None = Query(default=None, pattern=FORMATO_DO_PROJETO),
    corte: date | None = None,
    ator: dict = Depends(require_super_admin),
    supabase: Client = Depends(get_supabase_client),
):
    """A aba Entregas como ritmo semanal (issue #1701, ADR 0092, decisoes 1 e 7).
    So leitura: ninguem move nada por aqui.

    Entra o que quem pede ve (`pode_ver`, a regra da lista do chat), fora a
    lapide do Apagar. O `topo` traz pedidos e entregas das ultimas 4 semanas e
    das 4 anteriores; as `semanas`, as ultimas 12. Os `grupos` sao a lista
    "O que foi entregue" nas mesmas 12 semanas, so as que tem entrega, a mais
    nova em cima, cada entrega com o Tamanho da entrega (issue #1703; Nao sera
    feita fica de fora). Os filtros `tipo`,
    `origem`, `responsavel` (o id do usuario, ou o login do dono no GitHub
    quando ele nao e usuario do app) e `projeto` (issue #1716, ADR 0093,
    decisao 8) combinam e valem para os tres. As opcoes
    do Responsavel nao seguem o filtro, para o filtro ligado poder trocar.

    Com a semana de `corte` (AAAA-MM-DD, Ver semanas anteriores, issue #1704),
    os `grupos` sao as 12 semanas antes dela, com os mesmos filtros. O
    `proximo_corte` e o corte do bloco seguinte, ou nulo quando nao ha entrega
    mais antiga.

    Diretor e Desenvolvedor recebem a mesma coisa: o numero e o link da issue
    nao saem daqui para ninguem (PRD #1689). A lista sai pelo `_para_a_lista`,
    o funil da lista do chat, para o clique abrir o Documento do card, e aqui
    se apaga o que esse funil so manda ao Desenvolvedor: o motivo da falha
    (o da designacao traz o numero da issue no texto), o selo da designacao
    falhada e o autor.
    """
    result = supabase.table(TABELA_DEMANDAS).select("*").is_("apagada_em", "null").execute()
    visiveis = [d for d in (result.data or []) if pode_ver(ator, d)]
    filtros = tecnologia_entregas.Filtros(tipo=tipo, origem=origem, responsavel=responsavel, projeto=projeto)
    entregues = [d for d in visiveis if tecnologia_entregas.dia_da_entrega(d) is not None]
    nomes = _nomes(supabase, {responsavel_da_demanda(d) for d in entregues})
    opcoes = {
        chave: _nome_do_responsavel(d, nomes) or chave
        for d in entregues
        if (chave := tecnologia_entregas.chave_do_responsavel(d))
    }
    agora = agora_utc()
    grupos = tecnologia_entregas.lista_por_semana(visiveis, agora=agora, filtros=filtros, corte=corte)
    seguinte = tecnologia_entregas.proximo_corte(visiveis, agora=agora, filtros=filtros, corte=corte)
    na_lista = {
        entrega["id"]: {**entrega, **_SO_DO_DESENVOLVEDOR_NAS_ENTREGAS, "partes": _partes_sem_numero(entrega)}
        for entrega in _para_a_lista(supabase, [d for _, demandas in grupos for d in demandas], ator=ator)
    }
    return {
        **tecnologia_entregas.ritmo(visiveis, agora=agora, filtros=filtros),
        "grupos": [
            {
                "inicio": inicio.isoformat(),
                "entregas": [
                    {**na_lista[d["id"]], "tamanho": tecnologia_entregas.tamanho_da_entrega(d.get("partes_total"))}
                    for d in demandas
                ],
            }
            for inicio, demandas in grupos
        ],
        "proximo_corte": seguinte.isoformat() if seguinte else None,
        "responsaveis": [
            {"valor": valor, "nome": nome} for valor, nome in sorted(opcoes.items(), key=lambda par: par[1].casefold())
        ],
    }
