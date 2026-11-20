"""Os feriados cadastrados, lidos num lugar só (issue #1984, ADR 0107 decisão 2).

A tabela `ouvidoria_feriados` é administrável e vale para o app inteiro: o
calendário útil da Ouvidoria, a pauta e o encerramento da ata do Núcleo de
Segurança do Paciente, e os prazos legais do Núcleo. O carregador nasceu no
router da Ouvidoria e saiu dele para cá, para o Núcleo não ler a mesma tabela
por uma cópia que diverge.

Duas portas:

* `carregar_feriados_ou_degradado` / `carregar_feriados`: a tabela inteira, em
  páginas, fail-open (calendário que falha conta sem feriado). É a da Ouvidoria.
* `feriados_entre`: só o intervalo pedido, e a falha SOBE. Quem chama decide se
  aceita contar sem feriado (a pauta do Núcleo aceita, o encerramento da ata
  não).
"""

from __future__ import annotations

import datetime as dt
import logging

from httpx import HTTPError
from postgrest.exceptions import APIError

from app.services.paginacao import ler_paginado

logger = logging.getLogger(__name__)

TABELA_DE_FERIADOS = "ouvidoria_feriados"

# O nome da leitura que falhou, do jeito que a resposta diz isso. É o mesmo
# vocabulário do `degradado` das métricas (`ouvidoria_metricas.py`): a tela já
# traduz "feriados" para o aviso de calendário, e um nome novo aqui obrigaria a
# traduzir duas vezes a mesma falha.
LEITURA_DOS_FERIADOS = "feriados"

# As falhas que o fail-open do calendário cobre, uma a uma:
#
# - `HTTPError` do httpx é o transporte: timeout, conexão recusada, pool
#   estourado, proxy fora. É a falha transitória mais provável de todas, e é a
#   que `APIError` NÃO pega: `APIError` só nasce depois que a resposta HTTP
#   chega, e nenhuma das exceções do httpx é subclasse de `OSError`. Sem esta
#   linha o fail-open viraria fail-closed no primeiro blip de rede, que é o
#   oposto do que a issue pediu. O mesmo raciocínio já está escrito na
#   prorrogação, mais abaixo neste arquivo.
# - `APIError` é o PostgREST respondendo e recusando (tabela fora, RLS, sintaxe).
# - `OSError` é o socket embaixo de qualquer um dos dois.
# - `ValueError` é a data malformada na coluna: dado ruim, não bug de código, e
#   a promessa do fail-open é a tela abrir.
#
# `AttributeError` e `TypeError` ficam DE FORA de propósito: foi um
# `except Exception` largo aqui que deixou quatro arquivos de teste passarem
# verdes rodando com o calendário vazio, porque engoliu o `AttributeError` dos
# próprios fakes. Erro de programação não é indisponibilidade de infraestrutura
# (issue #449).
FALHAS_DE_LEITURA_DO_CALENDARIO = (HTTPError, APIError, OSError, ValueError)


def carregar_feriados_ou_degradado(supabase) -> tuple[frozenset[dt.date], list[str]]:
    """Os feriados que o motor precisa (RN-22) e a lista do que não pôde ser
    lido. Falha aqui não derruba o painel: sem a lista o motor conta feriado
    como dia útil, o que erra para menos (cobra antes), e é melhor que a tela
    não abrir.

    O preço do fail-open é que o número sai errado, e ele não denuncia a si
    mesmo: calendário que falhou dá exatamente a mesma conta de hospital sem
    feriado cadastrado. Por isso a falha volta NOMEADA, no mesmo formato que as
    métricas usam, para a resposta poder dizer "sem confirmação do calendário"
    em vez de afirmar um prazo em dias úteis que ninguém confirmou.

    Calendário INCOMPLETO entra na mesma marca que calendário não lido (issue
    #448). Esta é a única leitura do módulo que tem onde carimbar e ainda usava
    a porta que levanta: o teto derrubava com 500 a listagem, o Dossiê e a
    página do setor, que antes abriam degradadas. Sai mais barato e é mais
    honesto degradar, porque o `degradado` chega na TELA, o que é mais do que um
    log chega."""
    try:
        # Em páginas, como a gêmea `_feriados` das métricas (issue #430): esta
        # roda DENTRO da listagem que o mesmo PR paginou, e um calendário
        # cortado no teto do PostgREST faria o rótulo de prazo de cada linha do
        # índice sair errado com HTTP 200, que é o furo que a issue veio fechar.
        #
        # Por `ler_paginado`, e não `ler_tudo`, porque aqui existe o segundo
        # valor de retorno para carregar a incompletude até a resposta.
        linhas, completa = ler_paginado(
            lambda: supabase.table(TABELA_DE_FERIADOS).select("data").order("data"),
            rotulo=LEITURA_DOS_FERIADOS,
        )
        # A conversão entra no try junto da leitura: uma data malformada não
        # pode derrubar o painel inteiro, que é o que a promessa acima diz.
        feriados = frozenset(dt.date.fromisoformat(str(row["data"])) for row in linhas if row.get("data"))
        # Os feriados que couberam vão junto da marca, em vez de virarem
        # conjunto vazio: calendário parcial erra menos que calendário nenhum, e
        # quem lê a resposta já foi avisado de que não dá para confiar nele.
        return feriados, [] if completa else [LEITURA_DOS_FERIADOS]
    except FALHAS_DE_LEITURA_DO_CALENDARIO:
        # `exc_info` porque o warning sem ele dizia que faltou calendário e não
        # dizia por quê: quem lê o log não tinha como separar banco fora de bug.
        logger.warning("Falha ao carregar feriados: o calendário útil vai contar sem eles", exc_info=True)
        return frozenset(), [LEITURA_DOS_FERIADOS]


def carregar_feriados(supabase) -> frozenset[dt.date]:
    """O calendário para quem não tem onde carimbar a falha.

    A maior parte das chamadas está no caminho de escrita (abrir, pausar,
    devolver, prorrogar) e nos jobs de cron, onde a resposta é o efeito do ato e
    não um prazo afirmado na tela. Quem MOSTRA prazo em dias úteis usa
    `carregar_feriados_ou_degradado` e leva a marca na resposta.

    O fail-open destas chamadas segue igual para falha de infraestrutura, que é
    o que elas precisam: o estreitamento do `except` mudou uma coisa só, erro de
    programação passar a subir em vez de virar calendário vazio.

    Calendário incompleto também segue fail-open aqui, e isso importa mais do
    que parece: em `reenviar_notificacao` a leitura acontece DEPOIS de a cópia
    já estar gravada, então abortar a requisição por causa do calendário
    deixaria o efeito no banco e o ato sem resposta. Quem não tem onde carimbar
    prefere o número aproximado ao meio-ato."""
    feriados, _degradado = carregar_feriados_ou_degradado(supabase)
    return feriados


def feriados_entre(supabase, inicio: dt.date, fim: dt.date) -> frozenset[dt.date]:
    """Os feriados cadastrados de `inicio` a `fim`, inclusive. A falha de
    leitura sobe: aqui não há onde carimbar, e quem chama sabe se contar sem
    feriado erra para o lado seguro ou não."""
    linhas = (
        supabase.table(TABELA_DE_FERIADOS)
        .select("data")
        .gte("data", inicio.isoformat())
        .lte("data", fim.isoformat())
        .execute()
        .data
    ) or []
    return frozenset(dt.date.fromisoformat(str(linha["data"])[:10]) for linha in linhas if linha.get("data"))
