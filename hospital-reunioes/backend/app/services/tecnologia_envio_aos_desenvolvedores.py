"""O Envio aos desenvolvedores, a porta unica (issue #2011, PRD #2007, ADR 0108, decisoes 3 a 5).

O diretor escreve na Conversa da Demanda e, no fim, aperta "Enviar para os
desenvolvedores". Duas operacoes, e so estas duas tocam o envio:

- `interpretar`: as mensagens do diretor (quem nao e Desenvolvedor) desde o
  ultimo envio, com o card e a ultima mensagem de um Desenvolvedor como
  contexto, vao ao modelo pela mesma porta do planejamento
  (`planejamento_demanda.chamar_o_modelo`), com o custo gravado. Volta o
  "Entendi assim:" em topicos e o que muda em cada card, guardado como envio
  `interpretado`. Sem mensagem nova do diretor, recusa;
- `enviar`: a interpretacao aprovada vira o Ajuste do plano, sub-issue
  `ready-for-human` do dono na issue-raiz. O corpo leva so a interpretacao,
  pela peneira do repositorio publico (`texto_do_diretor`): a fala do diretor
  fica no app (ADR 0083, decisao 8). A conversa ganha a linha do sistema
  "Enviado aos desenvolvedores em <data>, as <hora>" com os topicos.

A observacao do Validar da Apresentacao do PRD (issue #2013) passa pela mesma
interpretacao (`interpretar_a_validacao`): o texto original fica nesta tabela,
com a origem `validacao`, e so os topicos voltam para a funcao da Vercel.

A trava contra o duplo clique segue a porta de envio do card
(`tecnologia_envio`): estado, motivo e instante, com o UPDATE condicionado ao
instante lido. Depois de nascer, o Ajuste trava as fatias iniciais da raiz pelas dependencias,
com a regra do Validar (issue #2012, ADR 0108, decisao 4).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_validator

from app.config import settings
from app.dependencies import selecionar_participantes
from app.services import ai_processor, github_client, planejamento_demanda
from app.services.tecnologia import (
    TABELA_CONVERSA_DA_DEMANDA,
    e_desenvolvedor,
    instante_do_banco,
    projeto_da_demanda,
    recuar_continuacao,
)
from app.services.tecnologia_vinculo import (
    LABEL_EM_ANDAMENTO,
    LABEL_PRONTA_PARA_AGENTE,
    link_da_demanda,
    login_para_publicar,
    texto_do_diretor,
)
from app.utils.text_sanitizer import sanitizar_travessao

logger = logging.getLogger(__name__)

TABELA_ENVIOS = "tecnologia_envios_aos_desenvolvedores"

# A origem da linha do envio na Conversa (CHECK da migration 165).
ORIGEM_SISTEMA = "sistema"

# De onde veio o envio (CHECK da migration 166): a Conversa da Demanda ou a
# observacao do Validar da Apresentacao do PRD (issue #2013).
ORIGEM_CONVERSA = "conversa"
ORIGEM_VALIDACAO = "validacao"

PASSO_DO_CUSTO = "envio"
PROMPT_DO_ENVIO = "envio_aos_desenvolvedores_system"

ESTADO_INTERPRETADO = "interpretado"
ESTADO_ENVIANDO = "enviando"
ESTADO_ENVIADO = "enviado"
ESTADO_FALHOU = "falhou"

LABEL_DO_AJUSTE = "ready-for-human"

# A mesma janela da porta do card: maior que o timeout do GitHub, curta o
# bastante para um processo morto no meio nao trancar o envio.
JANELA_DO_ENVIO = timedelta(seconds=60)

LIMITE_DE_TOPICOS = 5

MOTIVO_SO_O_HOSPITAL = "Só quem é do hospital envia aos desenvolvedores."
MOTIVO_SEM_CARD = "Este pedido ainda não virou card no desenvolvimento. O envio existe depois do Criar o card."
MOTIVO_SEM_MENSAGEM_NOVA = (
    "Não há mensagem sua nova desde o último envio. Escreva na conversa o que quer mandar e aperte de novo."
)
MOTIVO_INTERPRETACAO_FALHOU = (
    "A IA não conseguiu ler a conversa agora, e nada foi enviado. A sua conversa ficou como estava: tente de novo."
)
MOTIVO_ENVIO_SUMIU = "Este resumo não vale mais. Aperte de novo em Enviar para os desenvolvedores."
MOTIVO_EM_ANDAMENTO = "Este envio já está saindo agora. Espere alguns segundos e recarregue a página."
MOTIVO_JA_ENVIADO = "Estas mensagens já foram enviadas aos desenvolvedores."
MOTIVO_GITHUB_FALHOU = (
    "O desenvolvimento não respondeu, e nada foi enviado. A sua conversa ficou como estava: tente de novo."
)

FUSO_DO_HOSPITAL = ZoneInfo("America/Sao_Paulo")

INTERPRETACAO_MOCK = {
    "topicos": ["[MOCK] Enviar aos desenvolvedores exige a IA configurada."],
    "cards": [],
}


class EnvioRecusadoErrorError(RuntimeError):
    """O envio nao sai: duplo clique, envio ja feito ou interpretacao que sumiu.
    `motivo` e a frase da tela."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


class EnvioFalhouError(RuntimeError):
    """O GitHub nao abriu o Ajuste. A falha ficou gravada no envio, e o clique
    seguinte tenta de novo. `integracao_desligada` e a falta de configuracao."""

    def __init__(self, motivo: str, *, integracao_desligada: bool = False):
        super().__init__(motivo)
        self.motivo = motivo
        self.integracao_desligada = integracao_desligada


def _agora() -> str:
    return datetime.now(UTC).isoformat()


# ─── O que ainda nao foi enviado ─────────────────────────────────────────────


def _envios(supabase, demanda_id: str) -> list[dict[str, Any]]:
    """Os envios da Conversa. A observacao do Validar mora na mesma tabela
    (issue #2013), mas nao e envio: nao marca de onde comeca o proximo, e o
    Enviar nao a aceita."""
    linhas = supabase.table(TABELA_ENVIOS).select("*").eq("demanda_id", demanda_id).execute().data or []
    return [e for e in linhas if (e.get("origem") or ORIGEM_CONVERSA) == ORIGEM_CONVERSA]


def _ultimo_enviado_ate(envios: list[dict[str, Any]]) -> datetime | None:
    """O instante da ultima mensagem coberta pelo ultimo envio que saiu."""
    instantes = [instante_do_banco(e.get("ate_mensagem_em")) for e in envios if e.get("estado") == ESTADO_ENVIADO]
    instantes = [i for i in instantes if i is not None]
    return max(instantes) if instantes else None


def _conversa(supabase, demanda_id: str) -> list[dict[str, Any]]:
    return list(
        supabase.table(TABELA_CONVERSA_DA_DEMANDA)
        .select("*")
        .eq("demanda_id", demanda_id)
        .order("criado_em")
        .execute()
        .data
        or []
    )


def _desenvolvedores_entre(supabase, autores: set[str]) -> set[str]:
    if not autores:
        return set()
    result = selecionar_participantes(
        supabase,
        "id, access_profile, is_super_admin, github_login",
        lambda q: q.in_("id", sorted(autores)),
    )
    return {str(p["id"]) for p in result.data or [] if e_desenvolvedor(p)}


def pendentes(supabase, demanda_id: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """As mensagens do diretor desde o ultimo envio e a ultima mensagem de um
    Desenvolvedor (o contexto). Diretor e quem nao e Desenvolvedor; a linha do
    sistema nao conta, nem a de quem saiu do cadastro."""
    linhas = [linha for linha in _conversa(supabase, demanda_id) if linha.get("origem") != ORIGEM_SISTEMA]
    autores = {str(linha["autor_id"]) for linha in linhas if linha.get("autor_id")}
    desenvolvedores = _desenvolvedores_entre(supabase, autores)
    ate = _ultimo_enviado_ate(_envios(supabase, demanda_id))
    do_diretor = [
        linha
        for linha in linhas
        if linha.get("autor_id")
        and str(linha["autor_id"]) not in desenvolvedores
        and (ate is None or (instante_do_banco(linha.get("criado_em")) or ate) > ate)
    ]
    do_desenvolvedor = [linha for linha in linhas if str(linha.get("autor_id")) in desenvolvedores]
    return do_diretor, (do_desenvolvedor[-1] if do_desenvolvedor else None)


def mensagens_novas(supabase, demanda_id: str) -> int:
    """Quantas mensagens do diretor esperam o proximo envio: e o que liga o botao."""
    return len(pendentes(supabase, demanda_id)[0])


# ─── O interpretar ───────────────────────────────────────────────────────────


class _CardDoModelo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    numero: int
    muda: str


class _SaidaDoEnvio(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topicos: list[str]
    cards: list[_CardDoModelo] = []

    @field_validator("topicos")
    @classmethod
    def _com_topico(cls, valor: list[str]) -> list[str]:
        if not any(t.strip() for t in valor):
            raise ValueError("interpretacao sem topico")
        return valor


def _limpo(texto: str) -> str:
    return sanitizar_travessao(" ".join((texto or "").split()))


def _numeros_do_card(demanda: dict[str, Any]) -> list[int]:
    partes = demanda.get("partes") if isinstance(demanda.get("partes"), list) else []
    numeros = [demanda.get("github_issue_numero"), *[p.get("numero") for p in partes if isinstance(p, dict)]]
    return [n for n in numeros if isinstance(n, int)]


def interpretacao_limpa(saida: _SaidaDoEnvio, demanda: dict[str, Any]) -> dict[str, list]:
    """Os topicos numa linha so, sem travessao e no teto; os cards so com
    numero do proprio card (o modelo nao inventa issue)."""
    validos = set(_numeros_do_card(demanda))
    return {
        "topicos": [t for t in (_limpo(t) for t in saida.topicos) if t][:LIMITE_DE_TOPICOS],
        "cards": [
            {"numero": c.numero, "muda": _limpo(c.muda)} for c in saida.cards if c.numero in validos and _limpo(c.muda)
        ],
    }


def pedido_do_envio(
    demanda: dict[str, Any],
    do_diretor: list[dict[str, Any]],
    do_desenvolvedor: dict[str, Any] | None,
    *,
    de_onde: str = "AS MENSAGENS DO DIRETOR DESDE O ÚLTIMO ENVIO",
) -> str:
    """O pedido ao modelo. Texto de gente entra recuado: nenhuma linha dele
    chega a coluna zero."""
    partes = demanda.get("partes") if isinstance(demanda.get("partes"), list) else []
    linhas_das_partes = [
        recuar_continuacao(f"- #{p.get('numero')}: {p.get('o_que_muda') or '(sem texto)'} ({p.get('situacao') or '?'})")
        for p in partes
        if isinstance(p, dict) and isinstance(p.get("numero"), int)
    ] or ["(sem partes)"]
    contexto = recuar_continuacao(f"    {do_desenvolvedor.get('texto') or ''}") if do_desenvolvedor else "(nenhuma)"
    return "\n".join(
        [
            "PEDIDO: ENVIO AOS DESENVOLVEDORES",
            "",
            "O CARD",
            recuar_continuacao(f"Título: {demanda.get('titulo') or ''}"),
            f"Número da raiz: #{demanda.get('github_issue_numero')}",
            recuar_continuacao(f"O que muda: {demanda.get('o_que_muda') or '(sem texto)'}"),
            "Partes:",
            *linhas_das_partes,
            "",
            "A ÚLTIMA MENSAGEM DE UM DESENVOLVEDOR (só contexto, não é pedido do diretor)",
            contexto,
            "",
            de_onde,
            *[recuar_continuacao(f"- {linha.get('texto') or ''}") for linha in do_diretor],
        ]
    )


def _interpretacao(supabase, demanda: dict[str, Any], conteudo: str, *, kit: str) -> dict[str, list] | None:
    """A chamada ao modelo do Envio, com o custo gravado: os topicos e o que
    muda em cada card, ou `None` quando o modelo falhou."""
    if ai_processor._llm_provider() == "mock":
        logger.warning("Modo MOCK ativo para o Envio aos desenvolvedores (sem chave LLM)")
        return {"topicos": list(INTERPRETACAO_MOCK["topicos"]), "cards": []}
    saida, chamada = planejamento_demanda.chamar_o_modelo(
        demanda=demanda,
        passo=PASSO_DO_CUSTO,
        conteudo=conteudo,
        kit=kit,
        validar=_SaidaDoEnvio.model_validate,
        prompt=PROMPT_DO_ENVIO,
        modelo=planejamento_demanda.modelo_da_linha(planejamento_demanda.ler(supabase, str(demanda["id"]))),
    )
    planejamento_demanda.gravar_chamada(supabase, chamada)
    if saida is None:
        return None
    return interpretacao_limpa(saida, demanda)


def interpretar(supabase, demanda: dict[str, Any], *, kit: str) -> dict[str, Any] | None:
    """O "Entendi assim:" das mensagens novas do diretor, gravado como envio
    `interpretado`, ou `None` quando o modelo falhou (a chamada fica gravada
    do mesmo jeito). Levanta `EnvioRecusadoErrorError` sem mensagem nova."""
    demanda_id = str(demanda["id"])
    do_diretor, do_desenvolvedor = pendentes(supabase, demanda_id)
    if not do_diretor:
        raise EnvioRecusadoErrorError(MOTIVO_SEM_MENSAGEM_NOVA)

    interpretacao = _interpretacao(supabase, demanda, pedido_do_envio(demanda, do_diretor, do_desenvolvedor), kit=kit)
    if interpretacao is None:
        return None

    [linha] = (
        supabase.table(TABELA_ENVIOS)
        .insert(
            {
                "demanda_id": demanda_id,
                "topicos": interpretacao["topicos"],
                "cards": interpretacao["cards"],
                "ate_mensagem_em": do_diretor[-1].get("criado_em"),
                "estado": ESTADO_INTERPRETADO,
                "estado_em": _agora(),
            }
        )
        .execute()
        .data
    )
    return linha


def interpretar_a_validacao(supabase, demanda: dict[str, Any], observacao: str, *, kit: str) -> list[str]:
    """A observacao do Validar da Apresentacao do PRD (issue #2013, ADR 0108,
    decisao 5). Guarda o texto original junto da Demanda, com a origem
    `validacao`, ANTES de chamar o modelo: a observacao fica no app mesmo
    quando a interpretacao falha. Devolve os topicos pela peneira do
    repositorio publico, prontos para o comentario e o Ajuste do GitHub, ou a
    lista vazia quando o modelo falhou."""
    demanda_id = str(demanda["id"])
    [linha] = (
        supabase.table(TABELA_ENVIOS)
        .insert(
            {
                "demanda_id": demanda_id,
                "origem": ORIGEM_VALIDACAO,
                "texto_original": observacao,
                "topicos": [],
                "cards": [],
                "ate_mensagem_em": _agora(),
                "estado": ESTADO_INTERPRETADO,
                "estado_em": _agora(),
            }
        )
        .execute()
        .data
    )
    conteudo = pedido_do_envio(
        demanda,
        [{"texto": observacao}],
        None,
        de_onde="A OBSERVAÇÃO DO DIRETOR AO VALIDAR O PLANO NA APRESENTAÇÃO",
    )
    interpretacao = _interpretacao(supabase, demanda, conteudo, kit=kit)
    if interpretacao is None:
        return []
    supabase.table(TABELA_ENVIOS).update({"topicos": interpretacao["topicos"], "cards": interpretacao["cards"]}).eq(
        "id", linha["id"]
    ).execute()
    return [t for t in (texto_do_diretor(t) for t in interpretacao["topicos"]) if t]


# ─── O enviar ────────────────────────────────────────────────────────────────


def _em_andamento(envio: dict[str, Any]) -> bool:
    if envio.get("estado") != ESTADO_ENVIANDO:
        return False
    carimbo = instante_do_banco(envio.get("estado_em"))
    return carimbo is not None and datetime.now(UTC) - carimbo < JANELA_DO_ENVIO


def _mesmas_mensagens(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return instante_do_banco(a.get("ate_mensagem_em")) == instante_do_banco(b.get("ate_mensagem_em"))


def _tomar_a_vez(supabase, envio: dict[str, Any]) -> bool:
    """O UPDATE condicionado ao `estado_em` que ESTE pedido leu (compare-and-swap,
    como o `tecnologia_envio._tomar_a_vez`): o segundo clique concorrente nao
    casa linha nenhuma."""
    result = (
        supabase.table(TABELA_ENVIOS)
        .update({"estado": ESTADO_ENVIANDO, "motivo": None, "estado_em": _agora()})
        .eq("id", envio["id"])
        .eq("estado_em", envio.get("estado_em"))
        .execute()
    )
    return bool(result.data)


def _data_e_hora(instante: datetime) -> tuple[str, str]:
    local = instante.astimezone(FUSO_DO_HOSPITAL)
    return local.strftime("%d/%m/%Y"), local.strftime("%H:%M")


def titulo_do_ajuste(raiz: int) -> str:
    return f"Ajuste do plano: pedido do diretor no card #{raiz}"


# ─── A trava das fatias iniciais (issue #2012) ───────────────────────────────

# A falta de resposta do GitHub em qualquer forma: a trava falhar nao desfaz o
# Ajuste, so pede a trava a mao.
_FALHAS_DO_GITHUB = (
    github_client.GithubIndisponivelError,
    github_client.IssueNaoEncontradaError,
    github_client.GithubNaoConfiguradoError,
)

SEM_FATIA_LIVRE = "Nenhuma: o PRD não tinha fatia livre."


def _labels(issue: dict[str, Any]) -> set[str]:
    return {
        str(label.get("name") if isinstance(label, dict) else label) for label in (issue.get("labels") or []) if label
    }


def fatias_iniciais(raiz: int, *, projeto: str) -> tuple[list[int], list[int]]:
    """As partes da raiz que o Ajuste trava e as que ja comecaram, com a regra
    do Validar (ADR 0108, decisao 4): trava a aberta, `ready-for-agent`, sem
    `in-progress` e sem bloqueio aberto; a aberta com `in-progress` nao para,
    so entra na lista para o Pedro conferir. Levanta como o `github_client`."""
    abertas = [
        parte
        for parte in github_client.ler_sub_issues(raiz, projeto=projeto)
        if isinstance(parte, dict) and parte.get("state") == "open" and isinstance(parte.get("number"), int)
    ]
    em_andamento = [parte["number"] for parte in abertas if LABEL_EM_ANDAMENTO in _labels(parte)]
    prontas = [
        parte["number"]
        for parte in abertas
        if LABEL_PRONTA_PARA_AGENTE in _labels(parte) and LABEL_EM_ANDAMENTO not in _labels(parte)
    ]
    iniciais = [
        numero
        for numero in prontas
        if not any(b.get("estado") == "open" for b in github_client.ler_bloqueadoras(numero, projeto=projeto))
    ]
    return iniciais, em_andamento


def travar(iniciais: list[int], ajuste_id: object, *, projeto: str) -> list[int]:
    """Pede ao GitHub que cada fatia inicial fique bloqueada pelo Ajuste.
    Devolve as que nao travaram."""
    if not isinstance(ajuste_id, int):
        return list(iniciais)
    nao_travadas = []
    for numero in iniciais:
        try:
            github_client.bloquear(numero, ajuste_id, projeto=projeto)
        except _FALHAS_DO_GITHUB as exc:
            logger.warning("[tecnologia] a fatia #%s nao foi travada pelo Ajuste: %s", numero, exc)
            nao_travadas.append(numero)
    return nao_travadas


def aviso_para_travar_a_mao(raiz: int, nao_travadas: list[int] | None) -> str:
    """A linha que manda travar a mao, como a do Validar. `None` e a leitura
    das fatias que falhou: ninguem sabe quais eram."""
    if nao_travadas is None:
        return (
            f"Não deu para ler as fatias do card #{raiz} no GitHub, e nenhuma foi travada. Trave à mão: "
            "em cada fatia aberta, `ready-for-agent`, sem `in-progress` e sem bloqueio aberto, ponha este card "
            'em "Blocked by".'
        )
    lista = ", ".join(f"#{n}" for n in nao_travadas)
    return (
        f'Não deu para travar pelo GitHub as fatias {lista}. Trave à mão: em cada uma, ponha este card em "Blocked by".'
    )


def corpo_do_ajuste(
    *,
    raiz: int,
    demanda_id: str,
    topicos: list[str],
    cards: list[dict[str, Any]],
    data: str,
    hora: str,
    iniciais: list[int] | None = None,
    em_andamento: list[int] | None = None,
    aviso: str | None = None,
) -> str:
    """O corpo do Ajuste do plano: so a interpretacao aprovada, pela peneira do
    repositorio publico, e o passo a passo do Validar. A fala do diretor nao
    entra (ADR 0108, decisao 5). `iniciais` `None` e a leitura das fatias que
    falhou: a secao fica so com o `aviso`."""
    linhas_dos_topicos = [f"- {texto_do_diretor(t)}" for t in topicos]
    linhas_dos_cards = [f"- #{c['numero']}: {texto_do_diretor(c['muda'])}" for c in cards] or [
        "- Nenhum card em particular: o pedido vale para o plano."
    ]
    if iniciais is None:
        linhas_das_travadas = []
    else:
        linhas_das_travadas = [f"- #{n}" for n in iniciais] or [SEM_FATIA_LIVRE]
    if aviso:
        linhas_das_travadas = [*linhas_das_travadas, *([""] if linhas_das_travadas else []), aviso]
    secao_em_andamento = (
        [
            "## Já em andamento (não param)",
            "",
            "Confira se o pedido muda alguma destas:",
            "",
            *[f"- #{n}" for n in em_andamento],
            "",
        ]
        if em_andamento
        else []
    )
    return "\n".join(
        [
            f"<!-- ajuste-do-plano: {raiz} -->",
            "<!-- envio-aos-desenvolvedores -->",
            "## O que é este card",
            "",
            f"O diretor mandou um pedido pela Conversa da Demanda do card #{raiz} em {data}, às {hora}, "
            "e aprovou o resumo abaixo. Antes de o trabalho seguir, o agente revê o plano pelo resumo e segue "
            "as próprias recomendações. O Pedro só aprova o lançamento das ondas. Enquanto este card estiver "
            "aberto, as fatias iniciais ficam "
            f"bloqueadas. O que o diretor escreveu fica no aplicativo: {link_da_demanda(demanda_id)}",
            "",
            "## O que o diretor quer mudar",
            "",
            *linhas_dos_topicos,
            "",
            "## O que muda em cada card",
            "",
            *linhas_dos_cards,
            "",
            "## Fatias bloqueadas por este card",
            "",
            *linhas_das_travadas,
            "",
            *secao_em_andamento,
            "## Passo a passo",
            "",
            'O agente resolve este card sozinho. A única parada do Pedro é o "Posso lançar?" do passo 5.',
            "",
            "1. Abra o Claude Code na pasta do Hospital e rode `/grill-with-docs --lote` com o número deste card. "
            'O agente segue todas as recomendações dele, sem esperar o "ok".',
            "2. O agente leva o ajuste ao corpo do PRD e dos cards que ele toca, e abre card novo quando o ajuste "
            "pede trabalho que nenhum card cobre.",
            "3. Se o ajuste muda alguma Parte da Apresentação além do que o diretor pediu, o agente roda "
            f"`/apresentar-prd {raiz}` e o link vai de novo para ele validar. Se a mudança é só a que ele pediu, "
            "a Apresentação fica como está.",
            "4. O agente fecha este card com um comentário de uma linha: o que mudou, ou por que não precisou mudar.",
            f'5. O agente roda `/montar-ondas-enxutas` para o #{raiz} e termina em "Posso lançar?". '
            'As ondas só começam com o "pode" do Pedro.',
            "",
            "## Como saber que acabou",
            "",
            "- Este card está fechado com o comentário do passo 4.",
            "- As fatias bloqueadas voltam para a fila "
            '(`gh issue list --label ready-for-agent --search "-is:blocked"`).',
            f'- O "Posso lançar?" das ondas do #{raiz} está respondido.',
            "- Se a Apresentação foi publicada de novo, o PRD perdeu o selo `validado:diretor` e espera a nova "
            "validação.",
        ]
    )


def texto_da_linha(*, data: str, hora: str, topicos: list[str]) -> str:
    return "\n".join([f"Enviado aos desenvolvedores em {data}, às {hora}:", *[f"- {t}" for t in topicos]])


def _gravar_a_falha(supabase, envio_id: str, motivo: str) -> None:
    supabase.table(TABELA_ENVIOS).update({"estado": ESTADO_FALHOU, "motivo": motivo, "estado_em": _agora()}).eq(
        "id", envio_id
    ).execute()


def enviar(supabase, demanda: dict[str, Any], *, ator: dict[str, Any], envio_id: str) -> dict[str, Any]:
    """Abre o Ajuste do plano da interpretacao `envio_id` e escreve a linha do
    envio na conversa. Devolve a linha. Levanta `EnvioRecusadoErrorError` (duplo
    clique, ja enviado, interpretacao que nao existe) e `EnvioFalhouError`
    (o GitHub nao abriu; a falha fica gravada e o clique seguinte tenta)."""
    demanda_id = str(demanda["id"])
    envios = _envios(supabase, demanda_id)
    envio = next((e for e in envios if str(e.get("id")) == str(envio_id)), None)
    if envio is None:
        raise EnvioRecusadoErrorError(MOTIVO_ENVIO_SUMIU)
    if envio.get("estado") == ESTADO_ENVIADO:
        raise EnvioRecusadoErrorError(MOTIVO_JA_ENVIADO)
    if _em_andamento(envio):
        raise EnvioRecusadoErrorError(MOTIVO_EM_ANDAMENTO)
    # Um envio que ja saiu cobriu ate estas mensagens (a interpretacao e de
    # antes dele: outra aba, ou outro diretor no card de Origem Vitta).
    ja_saiu_ate = _ultimo_enviado_ate(envios)
    deste = instante_do_banco(envio.get("ate_mensagem_em"))
    if ja_saiu_ate is not None and (deste is None or deste <= ja_saiu_ate):
        raise EnvioRecusadoErrorError(MOTIVO_JA_ENVIADO)
    # Outra interpretacao das mesmas mensagens (outra aba) ja saiu ou esta saindo.
    for outro in envios:
        if outro is envio or not _mesmas_mensagens(outro, envio):
            continue
        if outro.get("estado") == ESTADO_ENVIADO:
            raise EnvioRecusadoErrorError(MOTIVO_JA_ENVIADO)
        if _em_andamento(outro):
            raise EnvioRecusadoErrorError(MOTIVO_EM_ANDAMENTO)
    if not _tomar_a_vez(supabase, envio):
        raise EnvioRecusadoErrorError(MOTIVO_EM_ANDAMENTO)

    raiz = int(demanda["github_issue_numero"])
    projeto = projeto_da_demanda(demanda)
    agora = datetime.now(UTC)
    data, hora = _data_e_hora(agora)
    topicos = list(envio.get("topicos") or [])
    dono = login_para_publicar(settings.github_login_dono)
    # As fatias sao lidas ANTES de o Ajuste nascer, para o corpo ja dizer quais
    # ele trava. A leitura que falhar nao segura o Ajuste: o corpo pede a mao.
    iniciais: list[int] | None
    try:
        iniciais, em_andamento = fatias_iniciais(raiz, projeto=projeto)
        aviso = None
    except _FALHAS_DO_GITHUB as exc:
        logger.warning("[tecnologia] as fatias da raiz #%s nao foram lidas para o Ajuste: %s", raiz, exc)
        iniciais, em_andamento, aviso = None, [], aviso_para_travar_a_mao(raiz, None)
    corpo = partial(
        corpo_do_ajuste,
        raiz=raiz,
        demanda_id=demanda_id,
        topicos=topicos,
        cards=list(envio.get("cards") or []),
        data=data,
        hora=hora,
        iniciais=iniciais,
        em_andamento=em_andamento,
    )
    try:
        dados = github_client.criar_issue(
            projeto=projeto,
            titulo=titulo_do_ajuste(raiz),
            corpo=corpo(aviso=aviso),
            labels=[LABEL_DO_AJUSTE],
            assignees=[dono] if dono else [],
        )
        numero = dados.get("number")
        if not isinstance(numero, int):
            raise github_client.GithubIndisponivelError("A criacao do Ajuste voltou sem numero")
    except github_client.GithubNaoConfiguradoError as exc:
        _gravar_a_falha(supabase, str(envio_id), str(exc))
        raise EnvioFalhouError(str(exc), integracao_desligada=True) from None
    except github_client.GithubIndisponivelError as exc:
        logger.warning("[tecnologia] o Ajuste do envio da Demanda %s nao nasceu: %s", demanda_id, exc)
        _gravar_a_falha(supabase, str(envio_id), str(exc))
        raise EnvioFalhouError(MOTIVO_GITHUB_FALHOU) from None

    # O Ajuste nasceu: daqui em diante nada desfaz o envio, senao o clique
    # seguinte abriria o segundo. A ligacao que falhar so fica no log.
    if isinstance(dados.get("id"), int):
        try:
            github_client.adicionar_sub_issue(raiz, dados["id"], projeto=projeto)
        except github_client.GithubIndisponivelError as exc:
            logger.warning("[tecnologia] o Ajuste #%s nao foi ligado a raiz #%s: %s", numero, raiz, exc)
    nao_travadas = travar(iniciais or [], dados.get("id"), projeto=projeto)
    if nao_travadas:
        try:
            github_client.regravar_corpo(
                numero, projeto=projeto, corpo=corpo(aviso=aviso_para_travar_a_mao(raiz, nao_travadas))
            )
        except _FALHAS_DO_GITHUB as exc:
            logger.warning("[tecnologia] o Ajuste #%s ficou sem o aviso de travar a mao: %s", numero, exc)

    supabase.table(TABELA_ENVIOS).update(
        {
            "estado": ESTADO_ENVIADO,
            "motivo": None,
            "estado_em": _agora(),
            "enviado_em": agora.isoformat(),
            "enviado_por": ator["id"],
            "ajuste_numero": numero,
        }
    ).eq("id", envio["id"]).execute()
    return gravar_linha_do_sistema(
        supabase, demanda_id, texto_da_linha(data=data, hora=hora, topicos=topicos), autor_id=ator["id"]
    )


def gravar_linha_do_sistema(supabase, demanda_id: str, texto: str, *, autor_id: str | None) -> dict[str, Any]:
    """A linha do sistema na Conversa da Demanda, que nao e bolha de ninguem:
    a do Envio aos desenvolvedores e a de Em producao (issue #2117). Devolve a
    linha gravada."""
    [linha] = (
        supabase.table(TABELA_CONVERSA_DA_DEMANDA)
        .insert(
            {
                "demanda_id": demanda_id,
                "autor_id": autor_id,
                "texto": texto,
                "mencoes": [],
                "origem": ORIGEM_SISTEMA,
            }
        )
        .execute()
        .data
    )
    return linha


def texto_da_linha_em_producao(*, versao: str, data: str) -> str:
    """A linha de Em producao (issue #2117): a versao e o dia da subida, no fuso do hospital."""
    try:
        dia, _ = _data_e_hora(datetime.fromisoformat(data))
    except (TypeError, ValueError):
        return f"Entrou no ar na versão {versao}."
    return f"Entrou no ar na versão {versao}, em {dia}."
