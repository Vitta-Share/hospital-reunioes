"""Regras puras da aba Tecnologia (PRD #634, ADR 0050).

Sem I/O: quem fala com o Supabase e o router e os servicos ao lado. Desde a ADR
0077 a aba e o chat do agente, e o que sobrou aqui e o que o chat, a
sincronizacao da Etapa e o Anexo ainda leem (issue #1386).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.dependencies import is_super_admin
from app.services.github_client import FATO_ASSIGNEE, PROJETO_ANA, PROJETO_HOSPITAL
from app.services.tecnologia_vinculo import (
    ETAPA_EM_PRODUCAO,
    ETAPA_ENTREGUE,
)

# As tabelas da aba. Moram aqui, e nao no router, porque quem escreve nelas nao
# e so o router: o webhook do GitHub e o job de reconciliacao escrevem pelo
# `tecnologia_sincronizacao`, e um nome de tabela repetido em tres arquivos e
# uma renomeacao que passa em dois deles.
TABELA_DEMANDAS = "tecnologia_demandas"
TABELA_PRODUTOS = "tecnologia_produtos"
# A Conversa da Demanda (issue #1537, ADR 0083, decisao 8): mensagens de gente,
# separadas da conversa com o agente, que mora em `tecnologia_planejamentos`.
TABELA_CONVERSA_DA_DEMANDA = "tecnologia_conversa_da_demanda"

# O estado da Demanda de antes da ADR 0077, congelado na coluna ate o drop. A
# sincronizacao e o apagamento dos prints ainda o leem: a Demanda Concluida ou
# Cancelada a mao, no Quadro de antes, nao volta a ser tocada. Os dois grupos
# sao o COMPLEMENTO um do outro sobre o CHECK da migration 102, e o teste cobra
# isso (`test_admin_tecnologia.py`).
ESTADOS_ABERTOS: tuple[str, ...] = ("nova", "em_andamento", "aguardando")
ESTADOS_FECHADOS: tuple[str, ...] = ("concluida", "cancelada")

# Quem abriu o card (ADR 0084, decisao 4; CHECK da migration 130): o diretor,
# pelo chat da aba, ou a Vitta, pela issue-raiz do app aberta no terminal.
ORIGEM_DIRETOR = "diretor"
ORIGEM_VITTA = "vitta"
# O bug relatado no Assistente do app (issue #2275, ADR 0113, decisao 8;
# CHECK da migration 240): a tela diz "Relato no app".
ORIGEM_RELATO = "relato"
ORIGENS: tuple[str, ...] = (ORIGEM_DIRETOR, ORIGEM_VITTA, ORIGEM_RELATO)

# A classificacao da tela e o Tipo do banco: bug e Defeito, melhoria e Novo.
# O caminho de volta da o selo da lista (issue #1438): o Tipo que nao veio do
# chat (os de antes dele) nao e bug nem melhoria, e fica sem selo. Moravam no
# `chat_tecnologia`, que saiu com o chat da aba (issue #2279).
TIPO_DA_CLASSIFICACAO: dict[str, str] = {"bug": "defeito", "melhoria": "novo"}
CLASSIFICACAO_DO_TIPO: dict[str, str] = {tipo: c for c, tipo in TIPO_DA_CLASSIFICACAO.items()}


RECUO_DA_CONTINUACAO = "    "


def instante_do_banco(valor: str | None) -> datetime | None:
    """O `TIMESTAMPTZ` do PostgREST como `datetime` consciente de fuso.

    Devolve `None` quando nao da para ler, e nunca "agora": um carimbo quebrado
    que virasse o instante atual seria uma janela (a da criacao do card, o
    prazo do print) aberta em cima de dado corrompido.

    Data sem fuso conta como UTC porque comparar um `datetime` ingenuo com um
    consciente estoura `TypeError`, e a janela viraria 500.
    """
    if not valor:
        return None
    try:
        lido = datetime.fromisoformat(str(valor))
    except ValueError:
        return None
    return lido if lido.tzinfo else lido.replace(tzinfo=UTC)


def recuar_continuacao(bloco: str) -> str:
    r"""As linhas depois da primeira entram recuadas.

    E o que impede um texto de varias linhas de derramar no nivel de cima e
    passar por moldura do prompt: a segunda linha de uma fala que diga
    "--- fim do kit ---" sai com quatro espacos na frente, e a marca que fecha
    a cerca continua sendo a unica que comeca na coluna zero.

    **Linha e o que o `splitlines()` diz que e linha** (issue #770). Com
    `split("\n")`, um `\r`, `\x0c` ou `\u2028` no corpo de uma issue nao virava
    linha aqui e escapava do recuo, mas virava linha para quem LE o prompt, e
    a marca de fim voltava para a coluna zero. O criterio e o proprio
    `splitlines()`, e nao uma tabela de caracteres: tabela e enumeracao, e foi
    enumeracao que divergiu do detector no PR #751. A saida so tem `\n`.

    A normalizacao mora AQUI, e nao em quem chama, porque esta funcao e o
    gargalo de todas as cercas do prompt (o `_cercar` do assistente, o kit e a
    conversa do chat). O `splitlines()` descarta a linha vazia final de um
    `"a\n"`, que o `split` mantinha como uma linha so de recuo.

    Docstring cru (prefixo `r`) de proposito: os separadores citados aqui nao
    podem virar quebra de verdade dentro dele.
    """
    primeira, *resto = bloco.splitlines() or [""]
    return "\n".join([primeira, *(f"{RECUO_DA_CONTINUACAO}{linha}" for linha in resto)])


def versao_da_entrega(demanda: dict[str, Any]) -> str | None:
    """A versao do app em que a Demanda subiu, so quando a Etapa e Em producao.

    A coluna pode guardar a versao de uma subida anterior com a Etapa que voltou
    atras (a issue reaberta para um ajuste): mostrar "v0.160.0" ao lado de
    "Entregue" diria que ja esta no ar o que ainda nao esta.
    """
    if demanda.get("etapa") != ETAPA_EM_PRODUCAO:
        return None
    return demanda.get("versao_em_producao") or None


def em_producao_desde(demanda: dict[str, Any]) -> str | None:
    """A data em que a Demanda entrou Em producao, so com a Etapa la (issue
    #1552, ADR 0084, decisao 8). A mesma guarda da versao: a coluna guarda a
    data de uma subida anterior quando a issue reabre."""
    if demanda.get("etapa") != ETAPA_EM_PRODUCAO:
        return None
    return demanda.get("em_producao_em") or None


def entregue_na_data(demanda: dict[str, Any]) -> str | None:
    """A data de entrega do Documento do card: o fechamento da issue-raiz, lido
    na sincronizacao (issue #1552). So com a Etapa Entregue ou Em producao: a
    issue fechada como nao planejada tambem tem data, e nao e entrega."""
    if demanda.get("etapa") not in (ETAPA_ENTREGUE, ETAPA_EM_PRODUCAO):
        return None
    foto = demanda.get("github_foto")
    return (foto.get("fechada_em") or None) if isinstance(foto, dict) else None


def e_desenvolvedor(pessoa: dict[str, Any] | None) -> bool:
    """O Super admin com login do GitHub no cadastro (ADR 0083, decisao 2).

    Nao e perfil nem permissao propria: e o cadastro que diz. Login so de
    espacos conta como sem login.
    """
    return is_super_admin(pessoa) and bool(str((pessoa or {}).get("github_login") or "").strip())


def origem_da_demanda(demanda: dict[str, Any]) -> str:
    """A Origem da Demanda; a linha de antes da coluna (migration 130) e do diretor."""
    origem = demanda.get("origem")
    return origem if origem in (ORIGEM_VITTA, ORIGEM_RELATO) else ORIGEM_DIRETOR


def projeto_da_demanda(demanda: dict[str, Any]) -> str:
    """O Projeto da Demanda (issue #1713, ADR 0093, decisao 2), que diz de qual
    repositorio e a issue dela. A linha de antes da coluna (migration 145) e do
    Hospital, como o default que a migration da as Demandas de hoje. Desde a
    issue #1967 pode ser um Projeto que o app nao le (o PedroOS): quem fala com
    o GitHub confere `github_client.PROJETOS` antes."""
    return str(demanda.get("projeto") or "").strip() or PROJETO_HOSPITAL


# O nome do Projeto como a tela o mostra (ADR 0093, decisao 8). O Projeto novo
# (issue #1967) traz o nome dele na coluna `projeto_nome`, que a ponte grava.
NOME_DO_PROJETO: dict[str, str] = {PROJETO_HOSPITAL: "Aplicativo do Hospital", PROJETO_ANA: "Ana"}


def nome_do_projeto(demanda: dict[str, Any]) -> str:
    """O nome do Projeto da Demanda: o fixo do Hospital e da Ana, o gravado
    pela ponte no Projeto novo, ou o proprio valor na falta dos dois."""
    projeto = projeto_da_demanda(demanda)
    return NOME_DO_PROJETO.get(projeto) or str(demanda.get("projeto_nome") or "").strip() or projeto


def projetos_do_filtro(demandas: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """As opcoes do filtro Projeto (issue #1967): o Hospital e a Ana, sempre,
    e cada Projeto novo que tem Demanda, pelo nome. Quem chama passa as
    Demandas sem a lapide."""
    opcoes = {projeto: nome for projeto, nome in NOME_DO_PROJETO.items()}
    novos = {projeto_da_demanda(d): nome_do_projeto(d) for d in demandas if projeto_da_demanda(d) not in opcoes}
    for projeto in sorted(novos, key=lambda p: novos[p].casefold()):
        opcoes[projeto] = novos[projeto]
    return [{"valor": projeto, "nome": nome} for projeto, nome in opcoes.items()]


def pode_ver(pessoa: dict[str, Any], demanda: dict[str, Any]) -> bool:
    """Quem ve uma Demanda: todo Super admin, qualquer que seja o autor (issue
    #2265, ADR 0113, decisao 6, que emenda a decisao 3 da ADR 0083). O login
    do GitHub no cadastro nao entra aqui: ele so da nome ao Responsavel.

    A regra e uma so, e toda rota de leitura da aba le daqui.
    """
    return is_super_admin(pessoa)


def responsavel_da_demanda(demanda: dict[str, Any]) -> str | None:
    """O id do Responsavel, que so existe depois do "Criar o card" (ADR 0083,
    decisao 5).

    A conversa sem card nao tem Responsavel, mesmo com a coluna preenchida: a
    Demanda de antes desta versao nascia com o dono do Produto ali, e ninguem o
    escolheu.
    """
    if not demanda.get("github_issue_numero"):
        return None
    return demanda.get("responsavel_id") or None


def login_do_responsavel(demanda: dict[str, Any]) -> str | None:
    """O login do dono da issue, como a foto o guardou, ou `None`.

    E o que a tela mostra quando o dono do GitHub nao e usuario do app (issue
    #1534, ADR 0083, decisao 6): sem `responsavel_id`, o Responsavel aparece
    pelo login. A conversa sem card nao tem dono, como em
    `responsavel_da_demanda`.
    """
    if not demanda.get("github_issue_numero"):
        return None
    foto = demanda.get("github_foto")
    login = foto.get(FATO_ASSIGNEE) if isinstance(foto, dict) else None
    return login if isinstance(login, str) and login else None
