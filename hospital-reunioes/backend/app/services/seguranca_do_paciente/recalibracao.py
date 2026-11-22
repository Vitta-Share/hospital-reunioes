"""O período de sombra e a recalibração do agente do Núcleo (issue #2001,
PRD #1979, ADR 0107 decisão 10; Anexo F, seções 4, 5 e 7).

Três peças, todas sem IA:

- a concordância: quanto a decisão da Presidência concordou com a sugestão do
  agente, por eixo, a partir das divergências que a tela de triagem grava na
  linha da pessoa (migration 197). Os casos em que a Presidência subiu o grau
  de dano sugerido ficam à parte: é o erro que mais importa;
- o lembrete: aos 30 e aos 60 dias da primeira notificação registrada, o job
  diário cria a pendência "Recalibrar o agente do NSP" para quem tem Acesso
  pleno, pela porta de Pendência sem Reunião da Fase 1, sem e-mail. Cada marco
  nasce uma vez só (a chave de `nsp_recalibracoes`, migration 210);
- a tela dos itens do Anexo F (seções 4 e 5): o que já tem dado nesta fase sai
  calculado; o resto aparece como "sem dados nesta fase". Concluir grava a
  decisão (manter, ajustar ou ligar a aprovação em lote), quem e quando.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from postgrest.exceptions import APIError

from app.models.schemas import StatusAta
from app.services.pendencia_ciclo import Comando
from app.services.pendencia_service import criar_pendencia_sem_reuniao
from app.services.seguranca_do_paciente import agenda, triagem
from app.services.seguranca_do_paciente.agente_de_triagem import BASE, PROMPT, versao
from app.services.seguranca_do_paciente.permissao import PERFIL_ACESSO_PLENO, id_do_nucleo
from app.services.seguranca_do_paciente.reunioes import TipoReuniaoNsp

logger = logging.getLogger(__name__)

TABELA = "nsp_recalibracoes"

# O título da pendência (Anexo F, seção 7). O marco vai entre parênteses.
TITULO = "Recalibrar o agente do NSP"

# Os marcos, em dias da primeira notificação registrada.
MARCOS = (30, 60)

# A Diretoria tem uma semana, a partir do marco, para registrar a decisão.
PRAZO_DIAS = 7

_FUSO = ZoneInfo("America/Sao_Paulo")

# Cada eixo e os campos conferidos na triagem que ele junta (Anexo F, seção 4,
# item 2). Marcadores são o evento da lista, IRAS, risco de imagem e protocolo
# básico (Anexo A, seção 6).
EIXOS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("natureza", "Natureza", ("natureza",)),
    ("grau_de_dano", "Grau de dano", ("grau_de_dano",)),
    ("categoria", "Categoria", ("categoria",)),
    ("faixa", "Faixa", ("faixa",)),
    ("canal", "Canal", ("canais",)),
    ("marcadores", "Marcadores", ("evento", "iras", "risco_de_imagem", "protocolo_basico")),
)

# A ordem do grau de dano: o erro para baixo é a decisão acima da sugestão.
# `nao_se_aplica` (migration 188) é o caso que o agente nem tratou como
# incidente: fica no fundo, junto do sem dano.
_ORDEM_DO_DANO = {"nao_se_aplica": 0, "nenhum": 0, "leve": 1, "moderado": 2, "grave": 3, "obito": 4}


def _percentual(parte: int, total: int) -> int | None:
    return round(100 * parte / total) if total else None


def _decisoes(supabase) -> list[dict[str, Any]]:
    """As linhas de pessoa (a triagem confirmada), todas, página a página."""
    return triagem._paginas(
        lambda: supabase.table("nsp_triagens").select("*").eq("autor_tipo", "pessoa").order("criado_em")
    )


def _com_sugestao(supabase, decisoes: list[dict[str, Any]]) -> list[tuple[dict, dict]]:
    """Os pares (decisão, sugestão) dos casos que tiveram sugestão do agente.
    O caso para classificar manualmente (divergências nulas) fica de fora."""
    medidas = [d for d in decisoes if d.get("divergencias") is not None]
    linhas = triagem._triagens_por_notificacao(supabase, [d["notificacao_id"] for d in medidas])
    pares = []
    for decisao in medidas:
        sugestao = triagem._sugestao(linhas.get(decisao["notificacao_id"], []))
        if sugestao is not None:
            pares.append((decisao, sugestao))
    return pares


def _eixos(pares: list[tuple[dict, dict]]) -> list[dict[str, Any]]:
    total = len(pares)
    saida = []
    for eixo, rotulo, campos in EIXOS:
        acatadas = sum(1 for decisao, _ in pares if not set(campos) & set(decisao["divergencias"]))
        saida.append(
            {
                "eixo": eixo,
                "rotulo": rotulo,
                "acatadas": acatadas,
                "total": total,
                "percentual": _percentual(acatadas, total),
            }
        )
    return saida


def _erros_para_baixo(supabase, pares: list[tuple[dict, dict]]) -> list[dict[str, Any]]:
    subidos = [
        (decisao, sugestao)
        for decisao, sugestao in pares
        if _ORDEM_DO_DANO.get(decisao.get("grau_de_dano"), -1) > _ORDEM_DO_DANO.get(sugestao.get("grau_de_dano"), 99)
    ]
    casos = _notificacoes_por_id(supabase, [d["notificacao_id"] for d, _ in subidos])
    return [
        {
            "notificacao_id": decisao["notificacao_id"],
            "protocolo": casos.get(decisao["notificacao_id"], {}).get("protocolo"),
            "sugerido": sugestao["grau_de_dano"],
            "decidido": decisao["grau_de_dano"],
            "grave_ou_obito": decisao["grau_de_dano"] in ("grave", "obito"),
        }
        for decisao, sugestao in subidos
    ]


def _notificacoes_por_id(supabase, ids: list[str]) -> dict[str, dict[str, Any]]:
    """O protocolo e o envio de cada notificação, lidos em lotes de ids."""
    casos: dict[str, dict[str, Any]] = {}
    ids = sorted(set(ids))
    for inicio in range(0, len(ids), triagem.LOTE_DE_IDS):
        lote = ids[inicio : inicio + triagem.LOTE_DE_IDS]
        consulta = supabase.table("nsp_notificacoes").select("id, protocolo, criado_em").in_("id", lote)
        for linha in consulta.execute().data or []:
            casos[linha["id"]] = linha
    return casos


def concordancia(supabase, pares: list[tuple[dict, dict]] | None = None) -> dict[str, Any]:
    """A concordância por eixo desde o primeiro dia, os erros para baixo e as
    versões do prompt e da base em uso."""
    if pares is None:
        pares = _com_sugestao(supabase, _decisoes(supabase))
    return {
        "versoes": {"prompt": versao(PROMPT), "base": versao(BASE)},
        "casos": len(pares),
        "eixos": _eixos(pares),
        "erros_para_baixo": _erros_para_baixo(supabase, pares),
    }


# ═══════════════════════════════════════════════════════════════════════════
# O lembrete aos 30 e aos 60 dias
# ═══════════════════════════════════════════════════════════════════════════


def e_recalibracao(pendencia: dict[str, Any]) -> bool:
    """A Pendência sem Reunião que pede a recalibração do agente, e não o
    lembrete da Agenda regulatória. O título não muda: as rotas de Pendências
    não editam a Pendência sem Reunião."""
    return (pendencia.get("descricao_acao") or "").startswith(TITULO)


def primeira_notificacao_em(supabase) -> date | None:
    """O dia, em Brasília, da primeira notificação registrada no módulo."""
    linhas = supabase.table("nsp_notificacoes").select("criado_em").order("criado_em").limit(1).execute().data or []
    if not linhas:
        return None
    return datetime.fromisoformat(str(linhas[0]["criado_em"])).astimezone(_FUSO).date()


def _acesso_pleno(supabase) -> list[dict[str, Any]]:
    return (
        supabase.table("participantes")
        .select("id, nome_completo")
        .eq("perfil_nsp", PERFIL_ACESSO_PLENO)
        .eq("ativo", True)
        .order("nome_completo")
        .execute()
        .data
    ) or []


def lembrar(supabase, hoje: date) -> int:
    """O job diário: quando um marco chega, cria a pendência para cada pessoa
    com Acesso pleno, uma vez por marco. O marco que chegou sem ninguém com
    Acesso pleno nasce no dia em que alguém tiver. Devolve quantas nasceram."""
    primeira = primeira_notificacao_em(supabase)
    if primeira is None:
        return 0
    devidos = [marco for marco in MARCOS if primeira + timedelta(days=marco) <= hoje]
    if not devidos:
        return 0
    gravados = {linha["marco"]: linha for linha in supabase.table(TABELA).select("*").execute().data or []}
    pendentes = [m for m in devidos if m not in gravados or not (gravados[m].get("pendencias") or [])]
    pendentes = [m for m in pendentes if not (gravados.get(m) or {}).get("decisao")]
    if not pendentes:
        return 0
    pessoas = _acesso_pleno(supabase)
    if not pessoas:
        logger.warning("[Recalibração] Marco de %s dias chegou e ninguém tem Acesso pleno.", pendentes)
        return 0

    criadas = 0
    for marco in pendentes:
        devida_em = primeira + timedelta(days=marco)
        if marco not in gravados:
            try:
                supabase.table(TABELA).insert({"marco": marco, "devida_em": devida_em.isoformat()}).execute()
            except APIError as erro:
                if getattr(erro, "code", None) != "23505":
                    raise
                # Outra rodada gravou o marco no meio: ela cria as pendências.
                continue
        titulo = f"{TITULO} ({marco} dias)"
        # A rodada que caiu depois do insert do marco deixou pendências sem
        # entrar na lista: elas valem, e só quem ficou sem a sua ganha uma.
        ja_nascidas = {
            linha["responsavel_id"]: linha["id_acao"]
            for linha in (
                supabase.table("pendencias")
                .select("id_acao, responsavel_id")
                .eq("descricao_acao", titulo)
                .is_("id_reuniao", "null")
                .execute()
                .data
            )
            or []
        }
        ids = list(ja_nascidas.values())
        for pessoa in pessoas:
            if pessoa["id"] in ja_nascidas:
                continue
            ids.append(
                criar_pendencia_sem_reuniao(
                    supabase,
                    {
                        "descricao_acao": titulo,
                        "responsavel_id": pessoa["id"],
                        "responsavel_nome": pessoa.get("nome_completo"),
                        "prazo": (devida_em + timedelta(days=PRAZO_DIAS)).isoformat(),
                    },
                )["id_acao"]
            )
            criadas += 1
        supabase.table(TABELA).update({"pendencias": ids}).eq("marco", marco).execute()
    return criadas


# ═══════════════════════════════════════════════════════════════════════════
# A decisão da Diretoria
# ═══════════════════════════════════════════════════════════════════════════

# As três decisões da auditoria (Anexo F, seção 7), na ordem da tela.
DECISOES = {
    "manter": "Manter o agente como está",
    "ajustar": "Ajustar o prompt e a base",
    "ligar_lote": "Ligar a aprovação em lote",
}


class RecalibracaoRecusadaError(Exception):
    """A decisão não pode ser gravada; a mensagem vai para a tela."""


class DecisaoInvalidaError(RecalibracaoRecusadaError):
    pass


class MarcoNaoChegouError(RecalibracaoRecusadaError):
    pass


class JaDecididaError(RecalibracaoRecusadaError):
    pass


class LoteSemConcordanciaError(RecalibracaoRecusadaError):
    pass


# O mínimo de concordância nos casos leves para ligar a aprovação em lote
# (Anexo F, seção 5, item 13).
CONCORDANCIA_MINIMA_DO_LOTE = 90


def decidir(supabase, marco: int, decisao: str | None, *, autor: dict[str, Any], agora: datetime) -> None:
    """Grava a decisão do marco, quem decidiu e quando, e conclui as pendências
    dele com a decisão na anotação. A decisão gravada não muda depois."""
    if decisao not in DECISOES:
        raise DecisaoInvalidaError("Escolha uma das três decisões: manter, ajustar ou ligar a aprovação em lote.")
    linhas = supabase.table(TABELA).select("*").eq("marco", marco).limit(1).execute().data or []
    if not linhas:
        raise MarcoNaoChegouError("Esta recalibração ainda não chegou.")
    if linhas[0].get("decisao"):
        raise JaDecididaError("A decisão desta recalibração já foi registrada.")
    if decisao == "ligar_lote":
        acatados, total, percentual = concordancia_do_lote(
            _com_sugestao(supabase, _decisoes(supabase)), agora.astimezone(_FUSO).date()
        )
        # Pelos inteiros: o percentual arredondado faria 89,7% (26 de 29) passar por 90.
        if not total or acatados * 100 < CONCORDANCIA_MINIMA_DO_LOTE * total:
            medida = "sem casos leves confirmados" if percentual is None else f"{percentual}%"
            raise LoteSemConcordanciaError(
                f"A aprovação em lote só liga com concordância de {CONCORDANCIA_MINIMA_DO_LOTE}% ou mais "
                f"nos casos leves das últimas 4 semanas. Agora: {medida}."
            )
    gravadas = (
        supabase.table(TABELA)
        .update({"decisao": decisao, "decidido_por": autor["id"], "decidido_em": agora.isoformat()})
        .eq("marco", marco)
        .is_("decisao", "null")
        .execute()
        .data
    )
    if not gravadas:
        raise JaDecididaError("A decisão desta recalibração já foi registrada.")
    for id_acao in linhas[0].get("pendencias") or []:
        try:
            agenda._agir_no_lembrete(
                supabase,
                id_acao,
                Comando.CONCLUIR,
                anotacao=f"Decisão da recalibração: {DECISOES[decisao]}.",
                autor_id=autor["id"],
                autor_nome=autor.get("nome_completo"),
            )
        except (APIError, httpx.HTTPError) as erro:
            # A decisão já está gravada; a pendência aberta se conclui à mão.
            logger.warning("[Recalibração] Pendência %s não concluída: %s", id_acao, erro)


def _nomes(supabase, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    linhas = supabase.table("participantes").select("id, nome_completo").in_("id", sorted(ids)).execute().data or []
    return {linha["id"]: linha.get("nome_completo") for linha in linhas}


def recalibracoes(supabase) -> list[dict[str, Any]]:
    """Os marcos que já chegaram, com a decisão, quem decidiu e quando."""
    linhas = sorted(supabase.table(TABELA).select("*").execute().data or [], key=lambda linha: linha["marco"])
    nomes = _nomes(supabase, {linha["decidido_por"] for linha in linhas if linha.get("decidido_por")})
    return [
        {
            "marco": linha["marco"],
            "devida_em": str(linha["devida_em"])[:10],
            "decisao": linha.get("decisao"),
            "decidido_por": nomes.get(linha.get("decidido_por")) if linha.get("decidido_por") else None,
            "decidido_em": linha.get("decidido_em"),
        }
        for linha in linhas
    ]


def tela(supabase, hoje: date) -> dict[str, Any]:
    """A tela da recalibração: os marcos, as decisões possíveis e os itens do
    Anexo F."""
    return {
        "recalibracoes": recalibracoes(supabase),
        "decisoes": [{"valor": valor, "rotulo": rotulo} for valor, rotulo in DECISOES.items()],
        "itens": itens_do_anexo_f(supabase, hoje),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Os itens do Anexo F, seções 4 e 5
# ═══════════════════════════════════════════════════════════════════════════

# Número, seção, título e sinal de alerta, como o Anexo F diz.
ITENS_DO_ANEXO_F: tuple[tuple[int, int, str, str], ...] = (
    (1, 4, "Volume de notificações", "Setor assistencial com zero notificação"),
    (2, 4, "Concordância agente e coordenação", "Abaixo de 85% em grau de dano"),
    (3, 4, "Erros para baixo", "Qualquer caso grave ou óbito sugerido como menor"),
    (4, 4, "Lista ANVISA", "Item da lista não reconhecido pelo agente"),
    (5, 4, "Prazos legais", "Qualquer atraso"),
    (6, 4, "Tempo de triagem", "Faixa A acima de 4 horas úteis"),
    (7, 4, "Casos parados", "Mais de 10% vencidas"),
    (8, 4, "Perguntas de esclarecimento", "Menos de 30% respondidas: rever a redação"),
    (9, 4, "Roteamento", "Devoluções recorrentes do mesmo tipo"),
    (10, 4, "Anônimas", "Acima de 60% indica medo de identificação"),
    (11, 4, "Amostra de leitura", "Justificativa genérica ou fato inventado"),
    (12, 5, "Tendência do volume", "Queda sem causa conhecida"),
    (13, 5, "Aprovação em lote", "Abaixo de 90%: manter o lote desligado"),
    (14, 5, "Planos de ação", "Mais de 50% dos planos só com ações fracas"),
    (15, 5, "Sinais de conduta", "Queda de notificações após encaminhamento"),
    (16, 5, "Reuniões", "Reunião mensal não realizada"),
    (17, 5, "Efetividade", "Caso encerrado sem verificação quando exigida"),
    (18, 5, "Dossiê", "Documento incompleto"),
    (19, 5, "Carga da coordenação", "Acima do previsto: rever automações"),
)

_JANELA = 30
_SEMANAS_DO_LOTE = 4
_TAMANHO_DA_AMOSTRA = 15
_HORAS_DA_FAIXA_A = 4
_ROTULO_DO_DANO = {
    "nao_se_aplica": "não se aplica",
    "nenhum": "nenhum",
    "leve": "leve",
    "moderado": "moderado",
    "grave": "grave",
    "obito": "óbito",
}


def _dia(instante: Any) -> date:
    return datetime.fromisoformat(str(instante)).astimezone(_FUSO).date()


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def _notificacoes_recentes(supabase, hoje: date) -> list[dict[str, Any]]:
    """As notificações dos últimos 60 dias (dois meses de 30), pelo dia em
    Brasília."""
    inicio = hoje - timedelta(days=2 * _JANELA - 1)
    linhas = triagem._paginas(
        lambda: (
            supabase.table("nsp_notificacoes")
            .select("id, setor_id, anonimo, criado_em")
            .gte("criado_em", (inicio - timedelta(days=1)).isoformat())
            .order("criado_em")
        )
    )
    return [linha for linha in linhas if inicio <= _dia(linha["criado_em"]) <= hoje]


def _volume(supabase, do_mes: list[dict]) -> tuple[list[str], bool]:
    nomes = triagem._nomes_dos_setores(supabase, {n["setor_id"] for n in do_mes if n.get("setor_id")})
    por_setor: dict[str, int] = {}
    for linha in do_mes:
        nome = nomes.get(linha.get("setor_id"), "Sem setor")
        por_setor[nome] = por_setor.get(nome, 0) + 1
    ordem = sorted(por_setor.items(), key=lambda par: (-par[1], par[0]))
    linhas = [f"{_plural(len(do_mes), 'notificação', 'notificações')} nos últimos 30 dias."]
    linhas += [f"{nome}: {total}" for nome, total in ordem]
    # O setor com zero é o que o item procura. A tabela `setores` não diz a
    # natureza (a da migration 053 era de `pops_setores` e saiu na 055): entra
    # todo setor ativo, a lista que o formulário da notificação oferece.
    ativos = supabase.table("setores").select("id, nome").eq("ativo", True).order("nome").execute().data or []
    notificaram = {n.get("setor_id") for n in do_mes}
    zerados = sorted(s["nome"] for s in ativos if s["id"] not in notificaram)
    if zerados:
        linhas.append(f"Setores sem notificação nos últimos 30 dias: {', '.join(zerados)}.")
    return linhas, bool(zerados)


def _linhas_da_concordancia(medida: dict[str, Any]) -> tuple[list[str], bool]:
    if not medida["casos"]:
        return ["Nenhum caso com sugestão do agente e decisão da Presidência ainda."], False
    linhas = [f"{e['rotulo']}: {e['percentual']}% ({e['acatadas']} de {e['total']})" for e in medida["eixos"]]
    dano = next(e for e in medida["eixos"] if e["eixo"] == "grau_de_dano")
    return linhas, dano["percentual"] < 85


def _linhas_dos_erros(medida: dict[str, Any]) -> tuple[list[str], bool]:
    erros = medida["erros_para_baixo"]
    linhas = [f"{_plural(len(erros), 'caso', 'casos')} com o grau de dano subido pela Presidência."]
    linhas += [
        f"{e['protocolo']}: sugerido {_ROTULO_DO_DANO[e['sugerido']]}, decidido {_ROTULO_DO_DANO[e['decidido']]}"
        for e in erros
    ]
    return linhas, any(e["grave_ou_obito"] for e in erros)


def _lista_anvisa(decisoes: list[dict], pares: list[tuple[dict, dict]]) -> tuple[list[str], bool]:
    sim = sum(1 for _, s in pares if s.get("evento_situacao") == "sim")
    possivel = sum(1 for _, s in pares if s.get("evento_situacao") == "possivel")
    graves_sem_marca = sum(
        1 for d in decisoes if d.get("grau_de_dano") in ("grave", "obito") and d.get("evento_situacao") == "nao"
    )
    nao_reconhecidos = sum(
        1 for d, s in pares if d.get("evento_situacao") in ("sim", "possivel") and s.get("evento_situacao") == "nao"
    )
    return [
        f"Marcados pelo agente como evento que nunca deveria ocorrer: {sim} sim e {possivel} possível.",
        f"Graves ou com óbito sem marcação na decisão: {graves_sem_marca}.",
        f"Marcados pela Presidência e não reconhecidos pelo agente: {nao_reconhecidos}.",
    ], nao_reconhecidos > 0


def _horas(valor: float) -> str:
    texto = f"{valor:.1f}".replace(".", ",")
    return f"{texto} {'hora corrida' if valor < 2 else 'horas corridas'}"


def _tempo_de_triagem(supabase, decisoes: list[dict]) -> tuple[list[str], bool]:
    casos = _notificacoes_por_id(supabase, [d["notificacao_id"] for d in decisoes])
    por_faixa: dict[str, list[float]] = {}
    for decisao in decisoes:
        caso = casos.get(decisao["notificacao_id"])
        if not caso or decisao.get("faixa") not in ("A", "B", "C", "D", "E"):
            continue
        espera = datetime.fromisoformat(str(decisao["criado_em"])) - datetime.fromisoformat(str(caso["criado_em"]))
        por_faixa.setdefault(decisao["faixa"], []).append(espera.total_seconds() / 3600)
    if not por_faixa:
        return ["Nenhuma triagem confirmada ainda."], False
    linhas = [
        f"Faixa {faixa}: {_horas(sum(horas) / len(horas))} em média ({_plural(len(horas), 'caso', 'casos')})"
        for faixa, horas in sorted(por_faixa.items())
    ]
    return linhas, any(h > _HORAS_DA_FAIXA_A for h in por_faixa.get("A", []))


def _anonimas(do_mes: list[dict]) -> tuple[list[str], bool]:
    if not do_mes:
        return ["Nenhuma notificação nos últimos 30 dias."], False
    anonimas = sum(1 for n in do_mes if n.get("anonimo"))
    percentual = _percentual(anonimas, len(do_mes))
    return [
        f"{anonimas} de {_plural(len(do_mes), 'notificação', 'notificações')} sem identificação "
        f"nos últimos 30 dias ({percentual}%)."
    ], percentual > 60


def _amostra(supabase, pares: list[tuple[dict, dict]]) -> tuple[list[str], bool]:
    recentes = sorted(pares, key=lambda par: str(par[0]["criado_em"]), reverse=True)[:_TAMANHO_DA_AMOSTRA]
    casos = _notificacoes_por_id(supabase, [d["notificacao_id"] for d, _ in recentes])
    protocolos = sorted(casos[d["notificacao_id"]]["protocolo"] for d, _ in recentes if d["notificacao_id"] in casos)
    return protocolos or ["Nenhum caso com sugestão do agente ainda."], False


def _tendencia(do_mes: list[dict], do_mes_anterior: list[dict]) -> tuple[list[str], bool]:
    return [f"Últimos 30 dias: {len(do_mes)}. Os 30 dias anteriores: {len(do_mes_anterior)}."], len(do_mes) < len(
        do_mes_anterior
    )


def concordancia_do_lote(pares: list[tuple[dict, dict]], hoje: date) -> tuple[int, int, int | None]:
    """Os casos leves (faixas D e E) confirmados nas últimas 4 semanas: quantos
    sem ajuste, quantos ao todo e o percentual (None sem nenhum)."""
    inicio = hoje - timedelta(weeks=_SEMANAS_DO_LOTE)
    leves = [d for d, _ in pares if d.get("faixa") in ("D", "E") and _dia(d["criado_em"]) > inicio]
    acatados = sum(1 for d in leves if not d["divergencias"])
    return acatados, len(leves), _percentual(acatados, len(leves))


def _lote(pares: list[tuple[dict, dict]], hoje: date) -> tuple[list[str], bool]:
    acatados, total, percentual = concordancia_do_lote(pares, hoje)
    if not total:
        return ["Nenhum caso leve confirmado nas últimas 4 semanas."], False
    return [
        f"Casos leves (faixas D e E) confirmados nas últimas 4 semanas: {acatados} de {total} "
        f"sem ajuste ({percentual}%)."
    ], percentual < CONCORDANCIA_MINIMA_DO_LOTE


_CAMPOS_DA_MUDANCA = ("natureza", "grau_de_dano", "categoria", "faixa")
_RESPONDIDAS_NO_MINIMO = 30


def _esclarecimentos(supabase) -> tuple[list[str], bool]:
    """As perguntas do agente a quem notificou, as respondidas (migration 207)
    e os casos em que a rodada depois da resposta mudou a classificação."""
    do_agente = triagem._paginas(
        lambda: supabase.table("nsp_triagens").select("*").eq("autor_tipo", "agente").order("criado_em")
    )
    feitas: dict[str, set[str]] = {}
    for linha in do_agente:
        feitas.setdefault(linha["notificacao_id"], set()).update(linha.get("perguntas_ao_notificante") or [])
    total = sum(len(perguntas) for perguntas in feitas.values())
    if not total:
        return ["Nenhuma pergunta de esclarecimento feita ainda."], False
    respostas = [
        r
        for r in triagem._paginas(lambda: supabase.table("nsp_esclarecimentos").select("*").order("criado_em"))
        if r.get("pergunta") in feitas.get(r["notificacao_id"], set())
    ]
    por_id = {linha["id"]: linha for linha in do_agente}
    ultima: dict[str, dict] = {}
    for linha in do_agente:
        if linha["versao"] > ultima.get(linha["notificacao_id"], {}).get("versao", 0):
            ultima[linha["notificacao_id"]] = linha
    primeira_resposta: dict[str, dict] = {}
    for resposta in respostas:
        primeira_resposta.setdefault(resposta["notificacao_id"], resposta)
    mudaram = 0
    for notificacao_id, resposta in primeira_resposta.items():
        perguntou, depois = por_id.get(resposta["triagem_id"]), ultima[notificacao_id]
        if perguntou and depois["versao"] > perguntou["versao"]:
            mudaram += any(perguntou.get(c) != depois.get(c) for c in _CAMPOS_DA_MUDANCA)
    respondidas = _percentual(len(respostas), total)
    casos = len(primeira_resposta)
    linhas = [f"{len(respostas)} de {_plural(total, 'pergunta', 'perguntas')} respondidas ({respondidas}%)."]
    if casos:
        linhas.append(
            f"{mudaram} de {_plural(casos, 'caso com resposta', 'casos com resposta')} com a classificação do "
            f"agente mudada depois dela ({_percentual(mudaram, casos)}%)."
        )
    return linhas, respondidas < _RESPONDIDAS_NO_MINIMO


_NAO_REALIZADA = (StatusAta.PROGRAMADA.value, StatusAta.CANCELADA.value, StatusAta.NAO_INSTALADA.value)


def _reunioes(supabase, hoje: date) -> tuple[list[str], bool]:
    nucleo_id = id_do_nucleo(supabase)
    linhas = []
    if nucleo_id:
        linhas = (
            supabase.table("reunioes")
            .select("id_reuniao, tipo, data, status_ata")
            .eq("colegiado_id", nucleo_id)
            .gte("data", (hoje - timedelta(days=2 * _JANELA - 1)).isoformat())
            .lte("data", hoje.isoformat())
            .is_("deleted_at", "null")
            .execute()
            .data
        ) or []
    # A reunião que não aconteceu não conta: o calendário anual cria as
    # ordinárias de antemão como PROGRAMADA.
    linhas = [r for r in linhas if r.get("status_ata") not in _NAO_REALIZADA]
    assinadas = sum(1 for r in linhas if r.get("status_ata") == "ASSINADA")
    inicio_do_mes = hoje - timedelta(days=_JANELA - 1)
    ordinarias = sum(
        1
        for r in linhas
        if r.get("tipo") == TipoReuniaoNsp.ORDINARIA_MENSAL.value
        and date.fromisoformat(str(r["data"])[:10]) >= inicio_do_mes
    )
    return [
        f"{_plural(len(linhas), 'reunião', 'reuniões')} do Núcleo nos últimos 60 dias, {assinadas} com ata assinada.",
        f"Ordinárias mensais nos últimos 30 dias: {ordinarias}.",
    ], ordinarias == 0


def itens_do_anexo_f(supabase, hoje: date) -> list[dict[str, Any]]:
    """Os 19 itens das seções 4 e 5. O que tem dado nesta fase sai calculado,
    com o sinal de alerta aceso quando o Anexo F pede; o resto sai sem linhas e
    com `com_dados` falso, para a tela dizer "sem dados nesta fase"."""
    decisoes = _decisoes(supabase)
    pares = _com_sugestao(supabase, decisoes)
    medida = concordancia(supabase, pares)
    recentes = _notificacoes_recentes(supabase, hoje)
    inicio_do_mes = hoje - timedelta(days=_JANELA - 1)
    do_mes = [n for n in recentes if _dia(n["criado_em"]) >= inicio_do_mes]
    do_mes_anterior = [n for n in recentes if _dia(n["criado_em"]) < inicio_do_mes]
    calculados = {
        1: lambda: _volume(supabase, do_mes),
        2: lambda: _linhas_da_concordancia(medida),
        3: lambda: _linhas_dos_erros(medida),
        4: lambda: _lista_anvisa(decisoes, pares),
        6: lambda: _tempo_de_triagem(supabase, decisoes),
        8: lambda: _esclarecimentos(supabase),
        10: lambda: _anonimas(do_mes),
        11: lambda: _amostra(supabase, pares),
        12: lambda: _tendencia(do_mes, do_mes_anterior),
        13: lambda: _lote(pares, hoje),
        16: lambda: _reunioes(supabase, hoje),
    }
    itens = []
    for numero, secao, titulo, sinal in ITENS_DO_ANEXO_F:
        linhas, alerta = calculados[numero]() if numero in calculados else ([], False)
        itens.append(
            {
                "numero": numero,
                "secao": secao,
                "titulo": titulo,
                "sinal": sinal,
                "com_dados": numero in calculados,
                "linhas": linhas,
                "alerta": alerta,
            }
        )
    return itens
