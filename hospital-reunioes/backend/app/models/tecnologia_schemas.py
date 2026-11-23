"""Schemas Pydantic da aba Tecnologia (PRD #634, ADR 0050).

Desde a ADR 0077 a aba e o chat do agente e mais nada: aqui ficam a lista das
conversas, os turnos do chat e a leitura do print (issue #1386).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
    # Se quem esta logado pode apagar esta Demanda (issue #1549, ADR 0084,
    # decisao 2): a tela mostra o botao so com o sim. A regra e a da rota.
    pode_apagar: bool = False
    # Quem abriu o card (issue #1554, ADR 0084, decisao 4): o diretor, pelo
    # chat, ou a Vitta, pela issue aberta no terminal. O selo da lista.
    origem: Literal["diretor", "vitta"] = "diretor"
    # O Projeto da Demanda (issue #1715, ADR 0093, decisao 8): o Aplicativo do
    # Hospital, a Ana ou, desde a issue #1967, um Projeto novo da Vitta. O selo
    # do card no Quadro e na lista do celular leva o `projeto_nome`.
    projeto: str = "hospital"
    projeto_nome: str | None = None
    # O link do PRD do Projeto novo (issue #1967), que a ponte gravou, para
    # todos que veem a Demanda: o app nao le aquele repositorio. Nulo no
    # Hospital e na Ana, cujo link segue so do Desenvolvedor (`issue_url`).
    raiz_url: str | None = None
    # A Revisao com o codigo de hoje (issue #1557, ADR 0084, decisao 3):
    # `pode_revisar` mostra o botao, pela regra da rota; `em_revisao` abre a
    # conversa para responder em vez de so ler.
    pode_revisar: bool = False
    em_revisao: bool = False
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


class OpcaoDaPerguntaResponse(BaseModel):
    letra: str
    texto: str


class RespostaDaPerguntaResponse(BaseModel):
    """A resposta da Pergunta da Vitta (issue #2119): a opcao escolhida (a
    letra e o texto), o texto livre, quando, quem registrou e, quando foi um
    Desenvolvedor no lugar do Destinatario, em nome de quem."""

    opcao: str | None = None
    opcao_texto: str | None = None
    texto: str | None = None
    respondida_em: str | None = None
    respondida_por: str | None = None
    em_nome_de: str | None = None


class ResolucaoDaPerguntaResponse(BaseModel):
    """A Pergunta resolvida pela ponte (issue #2121, ADR 0109, decisao 6): o
    que foi decidido e o que destravou, em palavras simples."""

    decidido: str | None = None
    destravou: str | None = None
    resolvida_em: str | None = None


class CancelamentoDaPerguntaResponse(BaseModel):
    """A Pergunta cancelada pela ponte (issue #2121): o motivo."""

    motivo: str | None = None
    cancelada_em: str | None = None


class PassoDoCartaoResponse(BaseModel):
    """Um passo do Passo a passo da Vitta (issue #2176, ADR 0110, decisao 4):
    o texto e o check, com quem marcou e quando (o estado e a ultima linha do
    historico do passo)."""

    texto: str
    marcado: bool = False
    por: str | None = None
    em_nome_de: str | None = None
    em: str | None = None


class ConclusaoDoPassoAPassoResponse(BaseModel):
    """A conclusao do Passo a passo: quando, como (no app ou pelo GitHub),
    quem e em nome de quem, e a anotacao (fica so no app)."""

    concluida_em: str | None = None
    como: Literal["app", "github"] | None = None
    por: str | None = None
    em_nome_de: str | None = None
    anotacao: str | None = None


class FechamentoNoGithubResponse(BaseModel):
    """O fechamento do card pelo app (ADR 0110, decisao 8): `falhou` traz o
    motivo, e o cartao mostra "Não chegou ao GitHub" com o Reenviar."""

    estado: Literal["pendente", "fechado", "falhou"]
    motivo: str | None = None


class EsperaDoPedidoResponse(BaseModel):
    """O Pedido de implantacao que este espera, enquanto ele nao esta
    concluido (issue #2208, ADR 0111, decisao 8)."""

    pedido_id: str
    assunto: str


class EsperaDaDemandaDeBugResponse(BaseModel):
    """A Demanda de bug que o Pedido de implantacao espera, enquanto ela nao
    foi entregue (issue #2210, ADR 0111, decisao 9)."""

    demanda_id: str
    numero: int | None = None


class PerguntaDoCartaoResponse(BaseModel):
    """O cartao da Pergunta da Vitta (issue #2116, ADR 0109, decisao 3): de
    qual Projeto e, a pergunta, as quatro linhas em palavras simples, as
    opcoes, o estado e desde quando espera (`criado_em`; a tela conta os
    dias)."""

    id: str
    # O tipo do Pedido da Vitta (issue #2176, ADR 0110, decisao 1; o Pedido de
    # implantacao, issue #2207, ADR 0111).
    tipo: Literal["pergunta", "passo_a_passo", "implantacao"] = "pergunta"
    projeto: str
    assunto: str
    texto: str
    por_que_precisa: str
    o_que_esta_parado: str
    o_que_anda_depois: str
    ganho: str
    opcoes: list[OpcaoDaPerguntaResponse] = []
    recomendada: str | None = None
    porque: str | None = None
    estado: Literal["aberta", "respondida", "resolvida", "cancelada", "concluida"]
    criado_em: str | None = None
    destinatario: str | None = None
    # A resposta (issue #2119): nula enquanto a Pergunta espera.
    resposta: RespostaDaPerguntaResponse | None = None
    # O estado final (issue #2121): so na resolvida e so na cancelada.
    resolucao: ResolucaoDaPerguntaResponse | None = None
    cancelamento: CancelamentoDaPerguntaResponse | None = None
    # O campo de resposta aparece so a quem responde: o Destinatario, ou o
    # Desenvolvedor no lugar dele, e so na Pergunta aberta (ADR 0109, decisao 5).
    # No Passo a passo, o mesmo diz quem marca os checks e conclui.
    pode_responder: bool = False
    # O Passo a passo (issue #2176): vazios e nulos na Pergunta.
    passos: list[PassoDoCartaoResponse] = []
    conclusao: ConclusaoDoPassoAPassoResponse | None = None
    fechamento: FechamentoNoGithubResponse | None = None
    pode_reenviar: bool = False
    # A espera (issue #2208): nula sem espera ou com o esperado concluido.
    espera: EsperaDoPedidoResponse | None = None
    # O "Achei um problema" (issue #2210): nula sem bug ou com ele entregue.
    espera_demanda: EsperaDaDemandaDeBugResponse | None = None


class PerguntaEsperandoResponse(PerguntaDoCartaoResponse):
    """Um item da lista Esperando você (issue #2118, ADR 0109, decisao 5;
    ADR 0110): o cartao, de qual Demanda e, se espera quem esta logado e se
    esta com a Vitta (o Destinatario e Desenvolvedor)."""

    demanda_id: str
    demanda: str
    minha: bool = False
    com_a_vitta: bool = False


class MensagemDaConversaResponse(BaseModel):
    """Uma mensagem de gente na Conversa da Demanda. `autor` e o nome de quem
    escreveu; `minha` diz se foi quem esta logado."""

    id: str
    autor: str | None = None
    texto: str
    criado_em: str | None = None
    minha: bool = False
    # A linha do Envio aos desenvolvedores (issue #2011, ADR 0108): a tela a
    # mostra como linha do sistema, e nao como bolha de alguem.
    sistema: bool = False
    # A entrada que e Pergunta da Vitta (issue #2116): a tela desenha o cartao
    # no lugar da bolha. Nula na mensagem comum.
    pergunta: PerguntaDoCartaoResponse | None = None


class MencionavelResponse(BaseModel):
    """Quem pode ser mencionado: quem ve a Demanda (o autor e os
    Desenvolvedores)."""

    id: str
    nome: str


class EnvioDaConversaResponse(BaseModel):
    """O botao "Enviar para os desenvolvedores" (issue #2011): so para quem nao
    e Desenvolvedor, em Demanda com issue. `mensagens_novas` e quantas
    mensagens do diretor esperam o proximo envio; zero desliga o botao."""

    mensagens_novas: int


class ConversaDaDemandaResponse(BaseModel):
    mensagens: list[MensagemDaConversaResponse]
    mencionaveis: list[MencionavelResponse]
    # Nulo = o botao nao aparece (Desenvolvedor, ou Demanda sem issue).
    envio: EnvioDaConversaResponse | None = None


class CardDoEnvioResponse(BaseModel):
    numero: int
    muda: str


class InterpretacaoDoEnvioResponse(BaseModel):
    """O "Entendi assim:" do Envio aos desenvolvedores (issue #2011)."""

    id: str
    topicos: list[str]
    cards: list[CardDoEnvioResponse] = []


class EnviarAosDesenvolvedoresPayload(BaseModel):
    """Corpo do POST .../conversa/enviar: a interpretacao aprovada."""

    envio_id: str = Field(min_length=1, max_length=64)


# O teto de uma fala do chat. E do pydantic, e nao do router, porque aqui nao
# ha frase de gente a preservar: um texto de 50 mil caracteres nao veio da tela,
# veio de um cliente que resolveu mandar o que quisesse para uma rota que gasta
# token de LLM a cada chamada.
LIMITE_DA_MENSAGEM = 5000


# ─── A leitura do print (PRD #726, ADR 0056) ─────────────────────────────────


class AssistenteImagemResponse(BaseModel):
    """Resposta do POST /admin/tecnologia/assistente/descrever-imagem.

    So o texto, e nao o nome do arquivo: o prefixo de origem do print e
    `[print] ` seco, sem nome. O nome de um print e "Captura de tela
    2026-09-17 as 14.02.11.png", que nao diz nada a quem le a conversa, e a
    imagem nao e guardada em lugar nenhum para alguem querer achar depois
    (ADR 0056, decisao 4).

    `print_id` e o identificador efemero do print (issue #1062): a imagem fica
    so na memoria do backend e vira Anexo quando a fala do chat que o leva entra
    na conversa.
    """

    texto: str
    print_id: str | None = None


class AssistenteDocumentoResponse(BaseModel):
    """Resposta do POST /admin/tecnologia/assistente/ler-documento (issue #1520).

    O texto extraido NAO sai daqui: a tela mostra so o nome e o tamanho, e o
    texto fica no backend, na memoria e depois na fala. `caracteres` e quanto
    o agente vai ler.
    """

    documento_id: str
    nome: str
    tamanho_bytes: int
    caracteres: int


# ─── O resumo da melhoria (issue #1383, ADR 0077) ───────────────────────────


class DecisaoDoResumo(BaseModel):
    """Uma decisao do resumo: a pergunta da IA, a resposta do diretor e uma
    linha de porque. As duas primeiras vem da conversa, nunca do modelo."""

    pergunta: str
    escolha: str
    porque: str


class ResumoDoPlanejamento(BaseModel):
    decisoes: list[DecisaoDoResumo] = []
    em_aberto: list[str] = []
    # A secao "Para o glossario" do PRD do diretor (issue #1383).
    termos: list[str] = []
    candidatas_a_adr: list[str] = []


# ─── O chat da aba (issue #1381, PRD #1380, ADR 0077) ────────────────────────


class ChatPrimeiroTurnoPayload(BaseModel):
    """Corpo do POST /admin/tecnologia/chat: o primeiro turno, que faz a
    Demanda nascer. Leva o botao da abertura ("bug" ou "melhoria"), o texto
    livre, ou os dois; quem recusa o corpo vazio e a rota, com frase de gente.

    `prints` sao os identificadores efemeros dos prints que a rota
    `descrever-imagem` leu: viram Anexo da Demanda na hora em que o turno entra.
    """

    escolha: Literal["bug", "melhoria"] | None = None
    texto: str | None = Field(default=None, max_length=LIMITE_DA_MENSAGEM)
    prints: list[str] = Field(default_factory=list, max_length=10)
    # Os identificadores dos documentos que a rota `ler-documento` leu (issue
    # #1520): o texto entra na fala, fora do teto da mensagem, e o original
    # vira Anexo quando a fala entra na conversa.
    documentos: list[str] = Field(default_factory=list, max_length=10)
    # O "Achei um problema" do Pedido de implantacao (issue #2210, ADR 0111,
    # decisao 9): o bug nasce com o texto inicial que nomeia o Pedido.
    pedido_id: UUID | None = None


class ChatTurnoPayload(BaseModel):
    """Corpo do POST /admin/tecnologia/chat/{id}: a fala do diretor.

    Sem texto, o turno e o "tente de novo" da IA: vale so quando a ultima fala
    guardada e do diretor (o "nao bateu"). No planejamento da melhoria (issue
    #1383), `opcao` e a letra da opcao clicada, e a resposta e ela OU o texto.
    """

    opcao: Literal["A", "B"] | None = None
    texto: str | None = Field(default=None, max_length=LIMITE_DA_MENSAGEM)
    prints: list[str] = Field(default_factory=list, max_length=10)
    documentos: list[str] = Field(default_factory=list, max_length=10)
    # O "Continuar respondendo" do resumo da melhoria com lacuna (issue #1440):
    # a fala sai do "Ficou em aberto" guardado, sem opcao nem texto.
    continuar: bool = False


class ChatNaoBateuPayload(BaseModel):
    """Corpo do POST .../chat/{id}/nao-bateu: o que nao bateu no resumo."""

    texto: str | None = Field(default=None, max_length=LIMITE_DA_MENSAGEM)


class CriarOCardPayload(BaseModel):
    """Corpo do POST .../chat/{id}/criar-card (ADR 0083, decisao 5): o
    Responsavel escolhido, que e opcional. Sem ele o card vai para o dono."""

    responsavel_id: str | None = None


class DocumentoDaFala(BaseModel):
    """O documento que uma fala do diretor trouxe, como a tela o mostra: o nome
    e o tamanho, e nunca o texto (issue #1520)."""

    nome: str
    tamanho_bytes: int


class ItemQueJaExiste(BaseModel):
    item: str
    versao: str


class RetratoDeHoje(BaseModel):
    """O primeiro turno da Revisao com o codigo de hoje (issue #1557): o que ja
    existe, com a versao em que entrou; o que mudou desde o card; e o que
    continua em aberto."""

    ja_existe: list[ItemQueJaExiste] = []
    mudou: list[str] = []
    em_aberto: list[str] = []


class EstimativaDaRevisao(BaseModel):
    """A faixa em dolar do Retrato de hoje, mostrada antes da confirmacao (ADR
    0082). Nula quando o modelo nao tem preco na tabela."""

    modelo: str
    minimo_usd: float | None = None
    maximo_usd: float | None = None


class ModeloDaDemanda(BaseModel):
    """O modelo da Demanda, no seletor da conversa (issue #1921, ADR 0103).
    So os dois da lista: outro valor e 422."""

    modelo: Literal["claude-sonnet-5-5", "claude-opus-5-5"]


class RevisarPayload(BaseModel):
    """O clique em Confirmar do dialogo: sem ele, a IA nao roda (ADR 0082)."""

    confirmado: bool = False


class RevisaoDaConversa(BaseModel):
    """A marca da revisao e o que o "isso atende?" ja decidiu: `saiu` do
    pedido com o sim, `continua` com o nao."""

    iniciada_em: str | None = None
    versao_base: str | None = None
    saiu: list[str] = []
    continua: list[str] = []


class CartaoDaPergunta(BaseModel):
    """Os textos do cartao da pergunta do planejamento (issue #1592): o titulo
    da pergunta, o que muda na pratica com cada opcao e o porque da
    recomendada. Cada um pode faltar: o modelo nao e obrigado a manda-los."""

    titulo: str | None = None
    na_pratica_a: str | None = None
    na_pratica_b: str | None = None
    porque: str | None = None


class FalaDoChat(BaseModel):
    autor: Literal["ia", "diretor"]
    texto: str
    fonte: str | None = None
    opcoes: list[str] = []
    # A letra da opcao recomendada, so na pergunta do planejamento da melhoria
    # (issue #1383): as `opcoes` vem na ordem A e B.
    recomendada: Literal["A", "B"] | None = None
    nao_bateu: bool = False
    documentos: list[DocumentoDaFala] = []
    # O Retrato de hoje da revisao (issue #1557), so na fala dele.
    retrato: RetratoDeHoje | None = None
    # O cartao da pergunta (issue #1592), so na pergunta que trouxe algum dos
    # textos novos. Nulo, a tela mostra a pergunta como bolha.
    cartao: CartaoDaPergunta | None = None
    # O nome de quem respondeu o turno (issue #1557), so na fala de gente.
    respondido_por: str | None = None


class ResumoDoBug(BaseModel):
    """O resumo do Roteiro do bug, como o diretor o confere."""

    titulo: str
    onde: str
    o_que_aconteceu: str
    o_que_esperava: str
    como_repetir: str
    criterios: list[str]


class AnexoDaDemanda(BaseModel):
    """Um Anexo da Demanda como o Desenvolvedor o abre: o nome, o tipo e a URL
    assinada de vida curta (ADR 0083, decisao 3)."""

    nome: str
    tipo: str
    url: str | None = None


class CustoDaConversa(BaseModel):
    """O modelo da chamada mais recente, no nome de exibicao ("Opus 5.5"), e a
    soma em dolar das chamadas de IA da Demanda. `custo_usd` nulo = nao medido:
    alguma chamada com tokens gravou custo zero (modelo sem preco)."""

    modelo: str
    custo_usd: float | None = None


class DocumentoDoPlanejamento(BaseModel):
    """O rascunho do documento do card, montado a cada turno do planejamento
    (issue #1553, ADR 0084, decisao 7): a frase de "O que muda" e ate cinco
    topicos. E o que o bloco "Para o diretor" do card criado leva."""

    frase: str | None = None
    topicos: list[str] = []


class ChatResponse(BaseModel):
    """A conversa do chat como a tela a mostra.

    `estado` segue o do planejamento: `em_andamento`, `resumido` (o resumo do
    bug esperando "Criar o card" ou "Nao bateu") e `enviado` (o card nasceu).
    `planejamento` verdadeiro e a melhoria confirmada, que segue no proprio
    chat pelo Planejamento da Demanda (issue #1383); o estado `encerrado` e o
    teto ou o fim das perguntas, esperando o "Fechar e resumir".
    Tokens nunca saem por aqui (ADR 0077, decisao 9). O custo sai, so na
    conversa aberta e nunca na lista: `custo` e nulo sem chamada nenhuma
    (ADR 0079, decisao 6, issue #1439).
    """

    demanda_id: str
    # O Numero da Demanda (issue #1585), na leitura da conversa guardada.
    numero: int | None = None
    estado: str | None = None
    mensagens: list[FalaDoChat] = []
    resumo: ResumoDoBug | None = None
    # O resumo do planejamento da melhoria (issue #1383), com `planejamento`
    # verdadeiro: as decisoes e o que ficou em aberto.
    resumo_da_melhoria: ResumoDoPlanejamento | None = None
    # O documento vivo ao lado do chat, so na melhoria (issue #1553). Nulo
    # enquanto o agente nao devolveu rascunho, e sempre no bug.
    documento: DocumentoDoPlanejamento | None = None
    anexos: int = 0
    planejamento: bool = False
    aviso_dos_anexos: str | None = None
    custo: CustoDaConversa | None = None
    # Os Anexos, so para o Desenvolvedor (ADR 0083, decisao 3). O diretor le
    # so a contagem em `anexos`.
    anexos_da_demanda: list[AnexoDaDemanda] = []
    # Quem cuida do card, so leitura: derivado do dono da issue no GitHub
    # (issue #1534, ADR 0083, decisao 6). O nome, ou o login de quem nao e
    # usuario do app. Nulo enquanto o card nao nasceu.
    responsavel: str | None = None
    # A Revisao com o codigo de hoje (issue #1557): nula fora dela.
    revisao: RevisaoDaConversa | None = None
    # O modelo da Demanda (issue #1921, ADR 0103): o que o seletor mostra.
    modelo: str | None = None


class MensagemDaConversaPayload(BaseModel):
    """Corpo do POST /admin/tecnologia/chat/{id}/conversa (issue #1537). A
    mencao vai no proprio texto, como "@Nome Completo"."""

    texto: str = Field(min_length=1, max_length=LIMITE_DA_MENSAGEM)


# A resposta entra na Conversa com "Resposta em nome de <Nome>: X) <opcao>"
# na frente, e a mensagem da Conversa tem o teto de LIMITE_DA_MENSAGEM.
LIMITE_DA_RESPOSTA = 4000


class RespostaDaPerguntaPayload(BaseModel):
    """Corpo do POST /admin/tecnologia/perguntas/{id}/resposta (issue #2119):
    a letra da opcao, o texto livre, ou os dois. A falta dos dois e a opcao
    que a Pergunta nao tem sao recusadas pelo servico, com o motivo."""

    opcao: str | None = Field(default=None, max_length=1)
    texto: str | None = Field(default=None, max_length=LIMITE_DA_RESPOSTA)


class RespostaDaPerguntaRespondidaResponse(BaseModel):
    """O cartao da Pergunta ja respondida e a mensagem da resposta na
    Conversa, para a tela trocar os dois sem reler a Conversa."""

    pergunta: PerguntaDoCartaoResponse
    mensagem: MensagemDaConversaResponse


# ─── O Passo a passo da Vitta (issue #2176, ADR 0110) ───────────────────────


class CheckDoPassoPayload(BaseModel):
    """Corpo do POST /admin/tecnologia/perguntas/{id}/checks: o indice do
    passo (a partir de 0) e se fica marcado."""

    passo: int = Field(ge=0, le=14)
    marcado: bool


class ConclusaoDoPassoAPassoPayload(BaseModel):
    """Corpo do POST /admin/tecnologia/perguntas/{id}/concluir: a anotacao
    opcional, que fica so no app e nunca vai para a issue."""

    anotacao: str | None = Field(default=None, max_length=LIMITE_DA_RESPOSTA)


class PassoAPassoConcluidoResponse(BaseModel):
    """O cartao concluido e, quando houve anotacao, a mensagem dela na Conversa."""

    pergunta: PerguntaDoCartaoResponse
    mensagem: MensagemDaConversaResponse | None = None


# ─── O Me explique (issue #2122, ADR 0109, decisao 8) ───────────────────────


class MeExpliquePayload(BaseModel):
    """Corpo do POST /admin/tecnologia/perguntas/{id}/me-explique: sem
    `texto`, abre a conversa; com ele, a pergunta da pessoa ao Assistente."""

    texto: str | None = Field(default=None, max_length=LIMITE_DA_RESPOSTA)


class FalaDoMeExplique(BaseModel):
    """Uma fala da conversa particular: da pessoa ou do Assistente, que pode
    trazer o rascunho de resposta."""

    papel: Literal["pessoa", "assistente"]
    texto: str
    rascunho: str | None = None


class ConversaDoMeExpliqueResponse(BaseModel):
    """A conversa de quem esta logado sobre a Pergunta, e so a dele."""

    mensagens: list[FalaDoMeExplique] = []
