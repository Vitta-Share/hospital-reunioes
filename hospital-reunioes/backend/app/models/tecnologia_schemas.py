"""Schemas Pydantic da aba Tecnologia (PRD #634, ADR 0050).

Desde a ADR 0077 a aba e o chat do agente e mais nada: aqui ficam a lista das
conversas, os turnos do chat e a leitura do print (issue #1386).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class BloqueadoraDaParte(BaseModel):
    """Uma issue aberta que trava a parte (issue #1902, ADR 0100, decisao 2): o
    "Espera a #N" da tela, com o "de outro pedido" quando ela nao e parte da
    mesma Demanda."""

    # Nulo no Ajuste do plano (issue #1915): a tela diz "Espera o ajuste do
    # plano", sem o numero, que e so do Desenvolvedor.
    numero: int | None = None
    de_outro_pedido: bool = False
    ajuste_do_plano: bool = False


class ParteDaEntrega(BaseModel):
    """Uma parte da entrega como o diretor a le (issue #676, ADR 0054, decisao 7).

    O que aquela parte muda para ele, em que pe ela esta e quando fechou. O
    titulo da fatia NAO entra, porque e tecnico. O numero entra desde a issue
    #1902 (ADR 0100, decisao 1), sem link, com a Onda e as bloqueadoras abertas.

    `situacao` e opcional porque uma linha gravada antes desta fatia nao a tem: a
    tela desenha o texto sem selo em vez de derrubar a conversa inteira.
    """

    numero: int | None = None
    o_que_muda: str | None = None
    situacao: str | None = None
    # Quando a parte fechou, lida na sincronizacao (issue #1552). Nula na
    # parte aberta e na linha gravada antes desta fatia.
    fechada_em: str | None = None
    # A Onda (ADR 0100, decisao 3). Nula na linha gravada antes da issue #1902.
    onda: int | None = None
    bloqueadoras: list[BloqueadoraDaParte] = []


class PedidoDaImplantacao(BaseModel):
    """Um Pedido de implantacao na secao Implantacao do Documento do card
    (issue #2209, ADR 0111, decisao 5): o titulo, quem recebeu e a situacao.
    A `espera` diz o que ele espera; vem nula ate as issues #2208 e #2210."""

    titulo: str
    destinatario: str | None = None
    situacao: Literal["feito", "esperando", "aberto"]
    espera: str | None = None


class ImplantacaoDaDemanda(BaseModel):
    """O que o hospital faz depois que a entrega sobe: os feitos sobre o total
    (o "Implantacao 1 de 3" do Quadro) e cada Pedido de implantacao."""

    feitos: int
    total: int
    pedidos: list[PedidoDaImplantacao] = []


class DemandaResponse(BaseModel):
    """Uma conversa da lista lateral do chat (issue #1384, ADR 0077).

    So o que o diretor le: o titulo, a Etapa (com as partes e a versao) e O que
    muda. Numero e endereco da issue nao saem daqui (ADR 0054, decisao 9);
    `tem_vinculo` diz so que o card ja nasceu.
    """

    id: str
    # O Numero da Demanda (issue #1585): o "Demanda 42" da tela, gerado pelo
    # banco no insert, para todo mundo que ve a Demanda. Nao e o numero da
    # issue, que continua so do Desenvolvedor (`issue_numero`).
    numero: int | None = None
    titulo: str
    criado_em: str | None = None
    # `registrada` (o default do banco) e a conversa sem card.
    etapa: str = "registrada"
    partes_entregues: int | None = None
    partes_total: int | None = None
    tem_vinculo: bool = False
    # O bloco "Para o diretor" da issue-raiz e o de cada parte, lidos do GitHub
    # e NUNCA digitados no app (ADR 0054, decisao 7). Nulo e "a Vitta ainda nao
    # escreveu", e a tela o traduz numa frase.
    o_que_muda: str | None = None
    partes: list[ParteDaEntrega] = []
    # A versao em que a Demanda subiu, RESOLVIDA pelo backend: vem preenchida so
    # quando a Etapa e Em producao (`versao_da_entrega`), e o selo a mostra
    # ("Em producao desde v0.165.0", issue #1065). A tela nao repete a regra.
    versao: str | None = None
    # As Datas do Documento do card (issue #1552, ADR 0084, decisao 7), alem
    # do `criado_em`: a entrega (o fechamento da issue-raiz) e a entrada Em
    # producao. Resolvidas pelo backend, nulas fora da Etapa que as segura.
    fechada_em: str | None = None
    em_producao_em: str | None = None
    # O selo ao lado da Etapa (issue #1438): o Tipo da Demanda traduzido de
    # volta para a pergunta do chat. Nulo no Tipo de antes do chat.
    classificacao: Literal["bug", "melhoria"] | None = None
    # Se quem esta logado e o autor (ADR 0083): a Demanda de outro autor abre
    # so para leitura.
    minha: bool = True
    # O numero da issue-raiz, sem link, para todos que veem a Demanda (issue
    # #1902, ADR 0100, decisao 1). As Entregas nao o mandam (PRD #1689).
    raiz_numero: int | None = None
    # So para o Desenvolvedor (ADR 0083, decisao 3): quem pediu, e o numero e o
    # endereco da issue. Para o diretor saem nulos (ADR 0054, decisao 9).
    autor: str | None = None
    issue_numero: int | None = None
    issue_url: str | None = None
    # Quem cuida do card (ADR 0083, decisao 5), para o diretor e para o
    # Desenvolvedor. Nulo enquanto o card nao nasceu.
    responsavel: str | None = None
    # O selo "Envio falhou" (issue #1535, ADR 0083, decisao 7), para os dois.
    # O motivo tecnico sai so para o Desenvolvedor; para o diretor, nulo.
    envio_falhou: bool = False
    # A issue nasceu sem o Responsavel (issue #1536): so para o Desenvolvedor,
    # que tem o "Designar de novo". O motivo sai no mesmo `envio_motivo`.
    designacao_falhou: bool = False
    envio_motivo: str | None = None
    # Quem abriu o card (issue #1554, ADR 0084, decisao 4): o diretor, pelo
    # chat, ou a Vitta, pela issue aberta no terminal. O selo da lista. Desde
    # a issue #2275, tambem o bug do Assistente do app ("Relato no app").
    origem: Literal["diretor", "vitta", "relato"] = "diretor"
    # O Projeto da Demanda (issue #1715, ADR 0093, decisao 8): o Aplicativo do
    # Hospital, a Ana ou, desde a issue #1967, um Projeto novo da Vitta. O selo
    # do card no Quadro e na lista do celular leva o `projeto_nome`.
    projeto: str = "hospital"
    projeto_nome: str | None = None
    # O link do PRD do Projeto novo (issue #1967), que a ponte gravou, para
    # todos que veem a Demanda: o app nao le aquele repositorio. Nulo no
    # Hospital e na Ana, cujo link segue so do Desenvolvedor (`issue_url`).
    raiz_url: str | None = None
    # O video de demonstracao da entrega (issue #1559): o link `https` lido do
    # marcador da issue-raiz e quando ele chegou. Nulo, sem selo nem secao.
    demonstracao_url: str | None = None
    demonstracao_em: str | None = None
    # O atalho Ver o plano (issue #2010, ADR 0108, decisao 2): o link da
    # Apresentacao do PRD, lido do marcador da issue-raiz, e se o diretor ja
    # validou o plano (a label `validado:diretor`). Nulo, sem botao nem cartao.
    apresentacao_url: str | None = None
    plano_validado: bool = False
    # O selo "Plano validado em" e a faixa do Ajuste do plano (issue #1915),
    # derivados da foto, para todos que veem a Demanda. O numero e o link do
    # Ajuste, so para o Desenvolvedor; para o diretor saem nulos.
    validado_em: str | None = None
    ajuste_aberto: bool = False
    ajuste_numero: int | None = None
    ajuste_url: str | None = None
    # Os Pedidos de implantacao da Demanda (issue #2209, ADR 0111, decisao 5),
    # para todos que veem a Demanda. Nulo sem nenhum: nem secao nem selo. A
    # Etapa nao depende deles.
    implantacao: ImplantacaoDaDemanda | None = None


class DesenvolvedorResponse(BaseModel):
    """Uma opcao do "Quem cuida disto?" (ADR 0083, decisao 5): um
    Desenvolvedor, pelo id e pelo nome. O login fica no servidor. `padrao` e
    quem recebe o card sem escolha."""

    id: str
    nome: str
    padrao: bool = False


# ─── As Entregas (issue #1556, ADR 0084, decisao 8) ────────────────────────


class PedidosDoTopoResponse(BaseModel):
    """Os pedidos das ultimas 4 semanas, contando a corrente (`total`), os das
    4 anteriores e a composicao do `total` (issue #1701, ADR 0092)."""

    total: int
    anteriores: int
    bugs: int
    melhorias: int


class EntregasDoTopoResponse(BaseModel):
    """As entregas das ultimas 4 semanas (`total`), as das 4 anteriores e o
    `total` pelo Tamanho da entrega (issue #1701, ADR 0092, decisao 3)."""

    total: int
    anteriores: int
    g: int
    m: int
    p: int


class TopoDasEntregasResponse(BaseModel):
    """Os dois numeros do alto da aba Entregas."""

    pedidos: PedidosDoTopoResponse
    entregas: EntregasDoTopoResponse


class EntregaDaSemanaResponse(BaseModel):
    """O que saiu numa semana, como a previa do grafico mostra: o titulo, o
    Tamanho da entrega e o Projeto, o selo (issue #1716). Sem numero de issue."""

    titulo: str
    tamanho: Literal["P", "M", "G"]
    projeto: str = "hospital"


class SemanaDasEntregasResponse(BaseModel):
    """Uma das 12 semanas do grafico: a segunda-feira (AAAA-MM-DD, fuso do
    hospital), os pedidos que nasceram nela e as entregas por tamanho, com o
    que saiu, o mais novo primeiro."""

    inicio: str
    pedidos: int
    g: int
    m: int
    p: int
    entregas: list[EntregaDaSemanaResponse]


class ResponsavelDasEntregasResponse(BaseModel):
    """Uma opcao do filtro Responsavel: o id do usuario, ou o login do dono no
    GitHub quando ele nao e usuario do app (issue #1534), e o nome da tela."""

    valor: str
    nome: str


class EntregaDaListaResponse(DemandaResponse):
    """Uma linha de "O que foi entregue" (issue #1703, ADR 0092, decisao 5): a
    Demanda no formato da lista do chat, para Abrir o card mostrar o Documento
    do card sem outro pedido, mais o Tamanho da entrega."""

    tamanho: Literal["P", "M", "G"]


class GrupoDasEntregasResponse(BaseModel):
    """Uma semana da lista: a segunda-feira (AAAA-MM-DD, fuso do hospital) e o
    que saiu nela, o mais novo primeiro."""

    inicio: str
    entregas: list[EntregaDaListaResponse]


class EntregasResponse(BaseModel):
    """A aba Entregas: o ritmo (o topo e as 12 semanas, issue #1701) e a lista
    "O que foi entregue" por semana, a mais nova em cima (issue #1703). O
    `proximo_corte` e a semana de corte do bloco seguinte da lista, nulo quando
    nao ha entrega mais antiga (issue #1704)."""

    topo: TopoDasEntregasResponse
    semanas: list[SemanaDasEntregasResponse]
    grupos: list[GrupoDasEntregasResponse]
    proximo_corte: str | None = None
    responsaveis: list[ResponsavelDasEntregasResponse]


class QuemSouNaAbaResponse(BaseModel):
    """Se quem esta logado e Desenvolvedor (ADR 0083, decisao 2): e o que faz a
    tela mostrar o filtro "Todas". A regra fica no backend."""

    desenvolvedor: bool


# ─── A Conversa da Demanda (issue #1537, ADR 0083, decisao 8) ──────────────


# O teto de uma fala do chat. E do pydantic, e nao do router, porque aqui nao
# ha frase de gente a preservar: um texto de 50 mil caracteres nao veio da tela,
# veio de um cliente que resolveu mandar o que quisesse para uma rota que gasta
# token de LLM a cada chamada.
LIMITE_DA_MENSAGEM = 5000


# ─── A leitura do print (PRD #726, ADR 0056) ─────────────────────────────────


# ─── O resumo da melhoria (issue #1383, ADR 0077) ───────────────────────────


# ─── O chat da aba (issue #1381, PRD #1380, ADR 0077) ────────────────────────


class ResumoDoBug(BaseModel):
    """O resumo do Roteiro do bug, como o diretor o confere."""

    titulo: str
    onde: str
    o_que_aconteceu: str
    o_que_esperava: str
    como_repetir: str
    criterios: list[str]


# ─── O Passo a passo da Vitta (issue #2176, ADR 0110) ───────────────────────


# ─── O Me explique (issue #2122, ADR 0109, decisao 8) ───────────────────────
