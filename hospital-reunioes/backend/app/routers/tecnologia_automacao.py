"""A ponte com o desenvolvimento (issue #1063, ADR 0069, decisão 2).

Quem desenvolve a Demanda busca os prints pelo app, por uma boca só: o script
`.claude/skills/pegar-issue/scripts/anexos.py` lê o id da Demanda no marcador da
issue e chama esta rota. Os anexos nunca vão para o GitHub (o repositório é
público); daqui sai só a URL assinada de vida curta de cada um.

Autenticação por chave de serviço própria (`X-API-Key` contra
`TECNOLOGIA_AUTOMACAO_API_KEY`), fora do fluxo JWT, no molde da API da Ana.

Desde a ADR 0096 a ponte tambem escreve na Conversa da Demanda: a Mensagem
pelo terminal, no perfil do Desenvolvedor cujo login do GitHub vem no pedido,
e le a resposta do diretor na mesma conversa (decisao 6).

Desde a issue #2013 (ADR 0108, decisao 5) a ponte tem uma segunda porta, com
chave propria (`PLANOS_HSM_API_KEY`): a funcao Validar da Apresentacao do PRD
manda a observacao do diretor, o app guarda o original e devolve so a
interpretacao, que e o que vai para o GitHub.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.dependencies import (
    get_supabase_client,
    require_planos_hsm_api_key,
    require_tecnologia_automacao_api_key,
)
from app.limiter import limiter
from app.models.tecnologia_schemas import LIMITE_DA_MENSAGEM
from app.services import (
    ai_processor,
    tecnologia_anexos,
    tecnologia_conversa,
    tecnologia_envio_aos_desenvolvedores,
    tecnologia_espelho,
    tecnologia_perguntas,
)
from app.services.conhecimento import carregar_kit
from app.services.github_client import FORMATO_DO_PROJETO, PROJETO_HOSPITAL
from app.services.paginacao import ler_tudo
from app.services.tecnologia import TABELA_DEMANDAS

# O detail nunca ecoa o login: a resposta nao confirma quem esta no cadastro.
MOTIVO_LOGIN_RECUSADO = "Este login do GitHub não é de um Desenvolvedor ativo no aplicativo."
MOTIVO_DEMANDA_NAO_ENCONTRADA = "Demanda não encontrada."
MOTIVO_DESTINATARIO_RECUSADO = "O Destinatário não é um participante ativo do aplicativo."
MOTIVO_SEM_ASSUNTO = "A mensagem que pede resposta precisa do Assunto."
# O Assunto vai na linha do sino e no assunto do e-mail: texto curto.
LIMITE_DO_ASSUNTO = 120


@limiter.limit("60/minute")
def _teto_por_endereco(request: Request) -> None:
    """60 pedidos por minuto por endereço, no molde da API da Ana.

    Vem como dependência antes da chave, e não no endpoint: o decorador no
    endpoint só conta depois que as dependências passam, e aí a tentativa de
    chave errada (401) não gastaria o teto.
    """


router = APIRouter(
    prefix="/automacao/tecnologia",
    tags=["automacao"],
    dependencies=[Depends(_teto_por_endereco), Depends(require_tecnologia_automacao_api_key)],
)


@router.get("/demandas/{demanda_id}/anexos")
def anexos_da_demanda(demanda_id: UUID, supabase=Depends(get_supabase_client)) -> dict:
    """Nome, tipo e URL assinada de cada anexo não apagado da Demanda.

    O id é UUID na assinatura: lixo no caminho vira 422 aqui, e não 500 no
    PostgREST. Demanda sem anexo, ou que não existe, devolve a lista vazia.
    """
    return {"anexos": tecnologia_anexos.para_quem_desenvolve(supabase, str(demanda_id))}


@router.get("/destinatarios")
def destinatarios(supabase=Depends(get_supabase_client)) -> dict:
    """Quem pode ser Destinatario de uma mensagem na Conversa da Demanda
    (issue #1966, PRD #1964): os participantes ativos, so id e nome, em ordem
    de nome. O PedroOS usa a lista para escolher o Canal (app ou WhatsApp).

    O select pede so as colunas que saem: e-mail, telefone e o resto do
    cadastro nunca chegam aqui. `ativo` nulo conta como ativo (o default da
    coluna e TRUE), como em toda leitura de participante; por isso o filtro e
    feito aqui, e nao com `.eq`, que descartaria o nulo. O cadastro e lido
    inteiro, em paginas, para o teto do PostgREST nao cortar ninguem."""
    linhas = ler_tudo(
        lambda: supabase.table("participantes").select("id, nome_completo, ativo").order("id"),
        rotulo="participantes que podem ser Destinatario",
    )
    ativos = [p for p in linhas if p.get("ativo") is not False]
    ativos.sort(key=lambda p: (p.get("nome_completo") or "").casefold())
    return {"destinatarios": [{"id": str(p["id"]), "nome": p.get("nome_completo") or ""} for p in ativos]}


def _demanda_ou_404(supabase, **filtros) -> dict:
    """A Demanda que casa os filtros, ou 404. A lapide do Apagar (ADR 0084,
    decisao 2) responde como inexistente, como em toda leitura da aba."""
    consulta = supabase.table(TABELA_DEMANDAS).select("*")
    for coluna, valor in filtros.items():
        consulta = consulta.eq(coluna, valor)
    linhas = consulta.is_("apagada_em", "null").execute().data or []
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MOTIVO_DEMANDA_NAO_ENCONTRADA)
    return linhas[0]


@router.get("/projetos/{projeto}/issues/{numero}/demanda")
def demanda_da_issue(
    projeto: str,
    numero: int = Path(ge=1),
    supabase=Depends(get_supabase_client),
) -> dict:
    """O id da Demanda vinculada a esta issue-raiz (ADR 0093: projeto mais
    numero), para a sessao do terminal escrever na conversa dela. Issue sem
    Demanda, ou de um Projeto que nao existe, e 404: a pergunta segue pelo
    WhatsApp (ADR 0096, decisao 5)."""
    demanda = _demanda_ou_404(supabase, projeto=projeto, github_issue_numero=numero)
    return {"id": str(demanda["id"])}


class DemandaDeProjetoNovoPayload(BaseModel):
    """O que o app nao tem como ler do repositorio de um Projeto novo: o nome
    dele, o titulo e o link do PRD."""

    nome_do_projeto: str = Field(min_length=1, max_length=80)
    titulo: str = Field(min_length=1, max_length=300)
    link: str = Field(max_length=500, pattern=r"^https://\S+$")


@router.post("/projetos/{projeto}/issues/{numero}/demanda")
def demanda_de_projeto_novo(
    payload: DemandaDeProjetoNovoPayload,
    response: Response,
    projeto: str = Path(pattern=FORMATO_DO_PROJETO),
    numero: int = Path(ge=1),
    supabase=Depends(get_supabase_client),
) -> dict:
    """A Demanda do PRD de um Projeto novo (issue #1967, PRD #1964): 201 quando
    nasce, 200 com a mesma quando ja existe. Projeto lido pelo app (Hospital e
    Ana) e Demanda apagada sao 409, com o motivo."""
    nome, titulo = payload.nome_do_projeto.strip(), payload.titulo.strip()
    if not nome or not titulo:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nome e título são obrigatórios.")
    try:
        demanda, criada = tecnologia_espelho.demanda_de_projeto_novo(
            supabase, projeto, numero, nome_do_projeto=nome, titulo=titulo, link=payload.link
        )
    except tecnologia_espelho.DemandaDeProjetoNovoRecusadaError as recusa:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(recusa)) from recusa
    response.status_code = status.HTTP_201_CREATED if criada else status.HTTP_200_OK
    return {"id": str(demanda["id"]), "criada": criada}


class MensagemPeloTerminalPayload(BaseModel):
    """O texto aprovado na sessao e o login do GitHub de quem a roda. Os tres
    campos da ADR 0106 sao opcionais: sem eles, tudo segue como na ADR 0096."""

    texto: str = Field(min_length=1, max_length=LIMITE_DA_MENSAGEM)
    github_login: str = Field(min_length=1, max_length=100)
    # ADR 0106: com Destinatario, o aviso vai so para ele, em qualquer Origem.
    # O id de participante e VARCHAR(10) no formato "P001" (migration 001).
    destinatario_id: str | None = Field(default=None, min_length=1, max_length=10)
    # ADR 0106: com "pede resposta", o sino e o e-mail dizem isso e o Assunto.
    assunto: str | None = Field(default=None, max_length=LIMITE_DO_ASSUNTO)
    pede_resposta: bool = False


@router.post("/demandas/{demanda_id}/conversa", status_code=status.HTTP_201_CREATED)
def escrever_pelo_terminal(
    demanda_id: UUID, payload: MensagemPeloTerminalPayload, supabase=Depends(get_supabase_client)
) -> dict:
    """A Mensagem pelo terminal (ADR 0096): grava no perfil do Desenvolvedor
    dono do login, com a origem `terminal`, e avisa pela regra dos avisos de
    entrega, ou so o Destinatario quando ele vem (ADR 0106). Destinatario que
    nao e participante ativo, ou "pede resposta" sem Assunto, recusa antes de
    gravar. O id e UUID na assinatura: lixo no caminho vira 422, nao 500."""
    autor = tecnologia_conversa.desenvolvedor_do_login(supabase, payload.github_login)
    if autor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MOTIVO_LOGIN_RECUSADO)
    texto = payload.texto.strip()
    if not texto:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A mensagem está vazia.")
    assunto = (payload.assunto or "").strip()
    if payload.pede_resposta and not assunto:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=MOTIVO_SEM_ASSUNTO)
    demanda = _demanda_ou_404(supabase, id=str(demanda_id))
    destinatario_id = payload.destinatario_id or None
    if destinatario_id and not tecnologia_conversa.e_participante_ativo(supabase, destinatario_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=MOTIVO_DESTINATARIO_RECUSADO)
    linha = tecnologia_conversa.escrever(
        supabase,
        demanda,
        autor=autor,
        texto=texto,
        origem=tecnologia_conversa.ORIGEM_TERMINAL,
        destinatario_id=destinatario_id,
        pede_resposta_sobre=assunto if payload.pede_resposta else None,
    )
    return {"id": str(linha["id"]), "criado_em": linha.get("criado_em")}


# ─── A Pergunta da Vitta (issue #2116, PRD #2112, ADR 0109) ──────────────────

# Cada linha do cartao e uma frase em palavras simples (ADR 0109, decisao 3).
LIMITE_DA_LINHA_DO_CARTAO = 500
LIMITE_DA_OPCAO = 300


class PerguntaDaVittaPayload(BaseModel):
    """A Pergunta da Vitta: quem a manda (o login do GitHub, como na Mensagem
    pelo terminal), o Destinatario, o Assunto, o texto, as quatro linhas do
    cartao e, se houver, as opcoes com a letra da recomendada e o porque. O
    que falta e recusado pelo servico, com o motivo em palavras; aqui so os
    tetos de tamanho."""

    github_login: str = Field(min_length=1, max_length=100)
    destinatario_id: str | None = Field(default=None, max_length=10)
    assunto: str | None = Field(default=None, max_length=LIMITE_DO_ASSUNTO)
    texto: str | None = Field(default=None, max_length=LIMITE_DA_MENSAGEM)
    por_que_precisa: str | None = Field(default=None, max_length=LIMITE_DA_LINHA_DO_CARTAO)
    o_que_esta_parado: str | None = Field(default=None, max_length=LIMITE_DA_LINHA_DO_CARTAO)
    o_que_anda_depois: str | None = Field(default=None, max_length=LIMITE_DA_LINHA_DO_CARTAO)
    ganho: str | None = Field(default=None, max_length=LIMITE_DA_LINHA_DO_CARTAO)
    opcoes: list[Annotated[str, Field(max_length=LIMITE_DA_OPCAO)]] = Field(
        default_factory=list, max_length=len(tecnologia_perguntas.LETRAS)
    )
    recomendada: str | None = Field(default=None, max_length=1)
    porque: str | None = Field(default=None, max_length=LIMITE_DA_LINHA_DO_CARTAO)


@router.post("/demandas/{demanda_id}/perguntas", status_code=status.HTTP_201_CREATED)
def criar_a_pergunta(demanda_id: UUID, payload: PerguntaDaVittaPayload, supabase=Depends(get_supabase_client)) -> dict:
    """Cria a Pergunta da Vitta aberta na Demanda, com a entrada na Conversa,
    a linha de sistema e o aviso so ao Destinatario. Falta de Destinatario
    ativo, de Assunto, de texto ou de uma das quatro linhas e 422 com o
    motivo, e nada fica gravado."""
    autor = tecnologia_conversa.desenvolvedor_do_login(supabase, payload.github_login)
    if autor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MOTIVO_LOGIN_RECUSADO)
    demanda = _demanda_ou_404(supabase, id=str(demanda_id))
    try:
        pergunta = tecnologia_perguntas.criar(
            supabase,
            demanda,
            autor=autor,
            destinatario_id=payload.destinatario_id,
            assunto=payload.assunto,
            texto=payload.texto,
            linhas={chave: getattr(payload, chave) for chave, _ in tecnologia_perguntas.LINHAS_DO_CARTAO},
            opcoes=payload.opcoes,
            recomendada=payload.recomendada,
            porque=payload.porque,
        )
    except tecnologia_perguntas.PerguntaRecusadaError as recusa:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(recusa)) from recusa
    return {"id": str(pergunta["id"]), "estado": pergunta["estado"], "criado_em": pergunta.get("criado_em")}


@router.get("/demandas/{demanda_id}/conversa")
def ler_pelo_terminal(
    demanda_id: UUID,
    depois: datetime | None = Query(default=None),
    supabase=Depends(get_supabase_client),
) -> dict:
    """A resposta do diretor (ADR 0096, decisao 6): as mensagens da Conversa
    da Demanda depois do instante `depois` (a data da pergunta da sessao), ou
    a conversa inteira sem ele. So le. O id e UUID e o instante e data na
    assinatura: lixo vira 422, nao 500."""
    demanda = _demanda_ou_404(supabase, id=str(demanda_id))
    return {"mensagens": tecnologia_conversa.ler(supabase, str(demanda["id"]), depois=depois)}


# ─── A observacao do Validar (issue #2013, ADR 0108, decisao 5) ──────────────

# Chave propria, separada da ponte do terminal: quem chega aqui e a funcao
# Validar da Vercel (projeto planos-hsm), nao a sessao de um Desenvolvedor.
router_dos_planos = APIRouter(
    prefix="/automacao/tecnologia",
    tags=["automacao"],
    dependencies=[Depends(_teto_por_endereco), Depends(require_planos_hsm_api_key)],
)

# O teto do campo da pagina (`validar.js` corta em 2000).
LIMITE_DA_OBSERVACAO = 2000


class ObservacaoDaValidacaoPayload(BaseModel):
    """O PRD do Hospital validado e a observacao que o diretor escreveu."""

    prd: int = Field(ge=1)
    observacao: str = Field(min_length=1, max_length=LIMITE_DA_OBSERVACAO)


@router_dos_planos.post("/validacoes", status_code=status.HTTP_201_CREATED)
async def observacao_da_validacao(payload: ObservacaoDaValidacaoPayload, supabase=Depends(get_supabase_client)) -> dict:
    """Guarda a observacao original junto da Demanda do PRD e devolve so os
    topicos interpretados, que a funcao da Vercel poe no comentario e no
    Ajuste. O modelo que falha devolve a lista vazia: o original ja ficou
    guardado. PRD sem Demanda e 404, e nada fica guardado."""
    observacao = payload.observacao.strip()
    if not observacao:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A observação está vazia.")
    demanda = _demanda_ou_404(supabase, projeto=PROJETO_HOSPITAL, github_issue_numero=payload.prd)
    topicos = await ai_processor.chamar_ia_fora_do_loop(
        tecnologia_envio_aos_desenvolvedores.interpretar_a_validacao, supabase, demanda, observacao, kit=carregar_kit()
    )
    return {"guardada": True, "topicos": topicos}
