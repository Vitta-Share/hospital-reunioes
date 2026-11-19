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

A trava contra o duplo clique segue a porta de envio do card
(`tecnologia_envio`): estado, motivo e instante, com o UPDATE condicionado ao
instante lido. A trava das fatias (as dependencias) e da fatia seguinte.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
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
from app.services.tecnologia_vinculo import link_da_demanda, login_para_publicar, texto_do_diretor
from app.utils.text_sanitizer import sanitizar_travessao

logger = logging.getLogger(__name__)

TABELA_ENVIOS = "tecnologia_envios_aos_desenvolvedores"

# A origem da linha do envio na Conversa (CHECK da migration 165).
ORIGEM_SISTEMA = "sistema"

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


class EnvioRecusadoError(RuntimeError):
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
    return list(supabase.table(TABELA_ENVIOS).select("*").eq("demanda_id", demanda_id).execute().data or [])


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
    demanda: dict[str, Any], do_diretor: list[dict[str, Any]], do_desenvolvedor: dict[str, Any] | None
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
            "AS MENSAGENS DO DIRETOR DESDE O ÚLTIMO ENVIO",
            *[recuar_continuacao(f"- {linha.get('texto') or ''}") for linha in do_diretor],
        ]
    )


def interpretar(supabase, demanda: dict[str, Any], *, kit: str) -> dict[str, Any] | None:
    """O "Entendi assim:" das mensagens novas do diretor, gravado como envio
    `interpretado`, ou `None` quando o modelo falhou (a chamada fica gravada
    do mesmo jeito). Levanta `EnvioRecusadoError` sem mensagem nova."""
    demanda_id = str(demanda["id"])
    do_diretor, do_desenvolvedor = pendentes(supabase, demanda_id)
    if not do_diretor:
        raise EnvioRecusadoError(MOTIVO_SEM_MENSAGEM_NOVA)

    if ai_processor._llm_provider() == "mock":
        logger.warning("Modo MOCK ativo para o Envio aos desenvolvedores (sem chave LLM)")
        interpretacao = {"topicos": list(INTERPRETACAO_MOCK["topicos"]), "cards": []}
    else:
        saida, chamada = planejamento_demanda.chamar_o_modelo(
            demanda=demanda,
            passo=PASSO_DO_CUSTO,
            conteudo=pedido_do_envio(demanda, do_diretor, do_desenvolvedor),
            kit=kit,
            validar=_SaidaDoEnvio.model_validate,
            prompt=PROMPT_DO_ENVIO,
            modelo=planejamento_demanda.modelo_da_linha(planejamento_demanda.ler(supabase, demanda_id)),
        )
        planejamento_demanda.gravar_chamada(supabase, chamada)
        if saida is None:
            return None
        interpretacao = interpretacao_limpa(saida, demanda)

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


def corpo_do_ajuste(
    *, raiz: int, demanda_id: str, topicos: list[str], cards: list[dict[str, Any]], data: str, hora: str
) -> str:
    """O corpo do Ajuste do plano: so a interpretacao aprovada, pela peneira do
    repositorio publico, e o passo a passo do Validar. A fala do diretor nao
    entra (ADR 0108, decisao 5)."""
    linhas_dos_topicos = [f"- {texto_do_diretor(t)}" for t in topicos]
    linhas_dos_cards = [f"- #{c['numero']}: {texto_do_diretor(c['muda'])}" for c in cards] or [
        "- Nenhum card em particular: o pedido vale para o plano."
    ]
    return "\n".join(
        [
            f"<!-- ajuste-do-plano: {raiz} -->",
            "<!-- envio-aos-desenvolvedores -->",
            "## O que é este card",
            "",
            f"O diretor mandou um pedido pela Conversa da Demanda do card #{raiz} em {data}, às {hora}, "
            "e aprovou o resumo abaixo. Antes de o trabalho seguir, o Pedro lê o resumo e decide se o plano "
            "ou o conteúdo de algum card muda. O que o diretor escreveu fica no aplicativo: "
            f"{link_da_demanda(demanda_id)}",
            "",
            "## O que o diretor quer mudar",
            "",
            *linhas_dos_topicos,
            "",
            "## O que muda em cada card",
            "",
            *linhas_dos_cards,
            "",
            "## Passo a passo",
            "",
            "1. Abra o Claude Code na pasta do Hospital e rode `/grill-with-docs` com o número deste card.",
            "2. Decida com o agente se o pedido muda o plano ou o conteúdo de algum card.",
            "3. Se algum card muda, o agente reescreve o corpo dele.",
            "4. Se a mudança altera alguma Parte que o diretor vê na Apresentação, rode "
            f"`/apresentar-prd {raiz}` e mande o link de novo para ele validar.",
            "5. Feche este card com um comentário de uma linha: o que mudou, ou por que não precisou mudar.",
            "",
            "## Como saber que acabou",
            "",
            "- Este card está fechado com o comentário do passo 5.",
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
    envio na conversa. Devolve a linha. Levanta `EnvioRecusadoError` (duplo
    clique, ja enviado, interpretacao que nao existe) e `EnvioFalhouError`
    (o GitHub nao abriu; a falha fica gravada e o clique seguinte tenta)."""
    demanda_id = str(demanda["id"])
    envios = _envios(supabase, demanda_id)
    envio = next((e for e in envios if str(e.get("id")) == str(envio_id)), None)
    if envio is None:
        raise EnvioRecusadoError(MOTIVO_ENVIO_SUMIU)
    if envio.get("estado") == ESTADO_ENVIADO:
        raise EnvioRecusadoError(MOTIVO_JA_ENVIADO)
    if _em_andamento(envio):
        raise EnvioRecusadoError(MOTIVO_EM_ANDAMENTO)
    # Outra interpretacao das mesmas mensagens (outra aba) ja saiu ou esta saindo.
    for outro in envios:
        if outro is envio or not _mesmas_mensagens(outro, envio):
            continue
        if outro.get("estado") == ESTADO_ENVIADO:
            raise EnvioRecusadoError(MOTIVO_JA_ENVIADO)
        if _em_andamento(outro):
            raise EnvioRecusadoError(MOTIVO_EM_ANDAMENTO)
    if not _tomar_a_vez(supabase, envio):
        raise EnvioRecusadoError(MOTIVO_EM_ANDAMENTO)

    raiz = int(demanda["github_issue_numero"])
    projeto = projeto_da_demanda(demanda)
    agora = datetime.now(UTC)
    data, hora = _data_e_hora(agora)
    topicos = list(envio.get("topicos") or [])
    dono = login_para_publicar(settings.github_login_dono)
    try:
        dados = github_client.criar_issue(
            projeto=projeto,
            titulo=titulo_do_ajuste(raiz),
            corpo=corpo_do_ajuste(
                raiz=raiz,
                demanda_id=demanda_id,
                topicos=topicos,
                cards=list(envio.get("cards") or []),
                data=data,
                hora=hora,
            ),
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
    [linha] = (
        supabase.table(TABELA_CONVERSA_DA_DEMANDA)
        .insert(
            {
                "demanda_id": demanda_id,
                "autor_id": ator["id"],
                "texto": texto_da_linha(data=data, hora=hora, topicos=topicos),
                "mencoes": [],
                "origem": ORIGEM_SISTEMA,
            }
        )
        .execute()
        .data
    )
    return linha
