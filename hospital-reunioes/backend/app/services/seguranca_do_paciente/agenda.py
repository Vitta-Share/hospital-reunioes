"""A Agenda regulatória do Núcleo (issue #1779, PRD #1764, ADR 0095).

As obrigações recorrentes do Núcleo, uma linha por evento, e as ocorrências de
cada um (a data, o lembrete e o resultado). Três regras moram aqui:

- o lembrete: quando a próxima data entra na antecedência do evento, nasce uma
  Pendência para a Presidência vigente, uma vez por ocorrência. Nada de e-mail:
  o lembrete mora no app (seção 11.2 da especificação). O job é só relógio e
  banco, sem IA (ADR 0082);
- o resultado: registrar guarda a ocorrência no histórico, conclui o lembrete e
  avança a próxima data pela periodicidade;
- a próxima data: mensal, anual ou bienal soma meses; avulsa não se repete.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from postgrest.exceptions import APIError

from app.services.pendencia_acao import agir
from app.services.pendencia_ciclo import ABERTOS, Comando, Papel, situacao
from app.services.pendencia_service import criar_pendencia_sem_reuniao
from app.services.pendencias_consulta import as_data, hoje_em_brasilia
from app.services.seguranca_do_paciente.permissao import id_do_nucleo, participacoes_vigentes

logger = logging.getLogger(__name__)

TABELA = "nsp_agenda_regulatoria"
TABELA_OCORRENCIAS = "nsp_agenda_ocorrencias"

PERIODICIDADES = ("mensal", "anual", "bienal", "avulsa")
_MESES = {"mensal": 1, "anual": 12, "bienal": 24}

# A maior antecedência que a migration aceita: o teto da leitura do job.
ANTECEDENCIA_MAXIMA = 90

# O lembrete, enquanto aberto, não volta a nascer; concluído ou cancelado, o
# resultado já foi tratado.
_STATUS_ABERTOS = ("PENDENTE", "EM_PROGRESSO", "ATRASADO", "REPACTUADA")

# No lembrete, a Presidência é a responsável (ele nasce para ela) e quem conduz
# o Núcleo (cancela o da data que mudou). Quem é Presidência quem decide é o
# recurso `gerir_nucleo` da rota; o job age em nome dela.
_PAPEIS_DA_PRESIDENCIA = frozenset({Papel.RESPONSAVEL, Papel.FACILITADOR})


class EventoNaoEncontradoError(LookupError):
    pass


class SemProximaDataError(ValueError):
    pass


def proxima_depois(data: date, periodicidade: str) -> date | None:
    """A data seguinte pela periodicidade. Dia que não existe no mês de
    destino (31 de janeiro mais um mês) cai no último dia dele."""
    meses = _MESES.get(periodicidade)
    if meses is None:
        return None
    indice = data.month - 1 + meses
    ano, mes = data.year + indice // 12, indice % 12 + 1
    return date(ano, mes, min(data.day, calendar.monthrange(ano, mes)[1]))


def presidencia_vigente(supabase, hoje: date) -> dict[str, Any] | None:
    """Quem tem a Participação de Presidência vigente no Núcleo hoje."""
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return None
    linhas = participacoes_vigentes(supabase, nucleo_id, hoje).eq("papel", "presidencia").execute().data or []
    if not linhas:
        return None
    pid = linhas[0]["participante_id"]
    pessoas = supabase.table("participantes").select("id, nome_completo").eq("id", pid).limit(1).execute().data or []
    return pessoas[0] if pessoas else {"id": pid, "nome_completo": None}


def _devidos(itens: list[dict], hoje: date) -> list[dict]:
    devidos = []
    for item in itens:
        if not item.get("ativo") or not item.get("proxima_data"):
            continue
        prevista = date.fromisoformat(str(item["proxima_data"])[:10])
        if prevista - timedelta(days=int(item.get("antecedencia_dias") or 0)) <= hoje:
            devidos.append(item)
    return devidos


def lembrar(supabase, hoje: date) -> int:
    """O job diário: cria a Pendência de lembrete de cada evento cuja data se
    aproxima e que ainda não foi lembrado. Devolve quantos nasceram."""
    itens = (
        supabase.table(TABELA)
        .select("id, evento, proxima_data, antecedencia_dias, ativo")
        .eq("ativo", True)
        .lte("proxima_data", (hoje + timedelta(days=ANTECEDENCIA_MAXIMA)).isoformat())
        .execute()
        .data
        or []
    )
    devidos = _devidos(itens, hoje)
    if not devidos:
        return 0

    presidencia = presidencia_vigente(supabase, hoje)
    if not presidencia:
        logger.warning("[Agenda regulatória] %d evento(s) a lembrar e nenhuma Presidência vigente.", len(devidos))
        return 0

    ja_lembrados = {
        (linha["item_id"], str(linha["data_prevista"])[:10])
        for linha in (
            supabase.table(TABELA_OCORRENCIAS)
            .select("item_id, data_prevista")
            .in_("item_id", [item["id"] for item in devidos])
            .execute()
            .data
            or []
        )
    }

    criados = 0
    for item in devidos:
        prevista = str(item["proxima_data"])[:10]
        if (item["id"], prevista) in ja_lembrados:
            continue
        pendencia = criar_pendencia_sem_reuniao(
            supabase,
            {
                "descricao_acao": f"Agenda regulatória: {item['evento']}",
                "responsavel_id": presidencia["id"],
                "responsavel_nome": presidencia.get("nome_completo"),
                "prazo": prevista,
            },
        )
        try:
            supabase.table(TABELA_OCORRENCIAS).insert(
                {"item_id": item["id"], "data_prevista": prevista, "pendencia_id": pendencia["id_acao"]}
            ).execute()
        except APIError as erro:
            if getattr(erro, "code", None) != "23505":
                raise
            # Outra rodada lembrou a mesma ocorrência no meio: a Pendência
            # desta sai, para o lembrete continuar sendo um só.
            supabase.table("pendencias").update({"deleted_at": datetime.now().astimezone().isoformat()}).eq(
                "id_acao", pendencia["id_acao"]
            ).execute()
            continue
        criados += 1
    return criados


def _agir_no_lembrete(
    supabase, id_acao: str, comando: Comando, *, anotacao: str, autor_id: str | None, autor_nome: str | None
) -> None:
    """Conclui ou cancela o lembrete pelo comando de ação da Pendência, com a
    anotação no histórico (ADR 0098; issue #1866). Lembrete já fechado não
    tem o que mudar."""
    linhas = (
        supabase.table("pendencias")
        .select("id_acao, status, prazo")
        .eq("id_acao", id_acao)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not linhas or linhas[0].get("status") not in ABERTOS:
        return
    agir(
        supabase,
        linhas[0],
        comando,
        _PAPEIS_DA_PRESIDENCIA,
        anotacao=anotacao,
        autor_id=autor_id,
        autor_nome=autor_nome or "Sistema",
        hoje=hoje_em_brasilia(),
    )


def registrar_resultado(
    supabase,
    item_id: str,
    *,
    resultado: str,
    realizada_em: date,
    autor_id: str | None,
    agora: datetime,
    autor_nome: str | None = None,
) -> dict[str, Any]:
    """Guarda o resultado da ocorrência da próxima data, conclui o lembrete
    dela (o resultado é a anotação) e avança a próxima data. Devolve o evento
    atualizado."""
    itens = supabase.table(TABELA).select("*").eq("id", item_id).limit(1).execute().data or []
    if not itens:
        raise EventoNaoEncontradoError(item_id)
    item = itens[0]
    if not item.get("proxima_data"):
        raise SemProximaDataError(item_id)
    prevista = str(item["proxima_data"])[:10]

    registro = {
        "resultado": resultado,
        "realizada_em": realizada_em.isoformat(),
        "registrado_por": autor_id,
        "registrado_em": agora.isoformat(),
    }
    existentes = (
        supabase.table(TABELA_OCORRENCIAS)
        .select("id, pendencia_id")
        .eq("item_id", item_id)
        .eq("data_prevista", prevista)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existentes:
        supabase.table(TABELA_OCORRENCIAS).update(registro).eq("id", existentes[0]["id"]).execute()
        pendencia_id = existentes[0].get("pendencia_id")
    else:
        supabase.table(TABELA_OCORRENCIAS).insert({"item_id": item_id, "data_prevista": prevista, **registro}).execute()
        pendencia_id = None

    if pendencia_id:
        try:
            _agir_no_lembrete(
                supabase, pendencia_id, Comando.CONCLUIR, anotacao=resultado, autor_id=autor_id, autor_nome=autor_nome
            )
        except (APIError, httpx.HTTPError) as erro:
            # O resultado já está guardado; o lembrete aberto a Presidência
            # conclui à mão.
            logger.warning("[Agenda regulatória] Lembrete %s não concluído: %s", pendencia_id, erro)

    proxima = proxima_depois(date.fromisoformat(prevista), item["periodicidade"])
    atualizado = supabase.table(TABELA).update(
        {"proxima_data": proxima.isoformat() if proxima else None, "updated_at": agora.isoformat()}
    ).eq("id", item_id).execute().data or [{**item, "proxima_data": proxima.isoformat() if proxima else None}]
    return atualizado[0]


def _dd_mm_aaaa(valor: str) -> str:
    return date.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")


def encerrar_lembrete(
    supabase,
    item_id: str,
    data_prevista: str,
    *,
    data_nova: str | None = None,
    autor_id: str | None = None,
    autor_nome: str | None = None,
) -> None:
    """A data do evento mudou antes do resultado: o lembrete da data antiga
    não tem mais o que cobrar. A Pendência dele é cancelada pelo comando de
    ação, com a troca de data na anotação, e a ocorrência sem resultado sai,
    para a data antiga voltar a lembrar se for marcada de novo. Ocorrência com
    resultado é histórico e fica."""
    ocorrencias = (
        supabase.table(TABELA_OCORRENCIAS)
        .select("id, pendencia_id, resultado")
        .eq("item_id", item_id)
        .eq("data_prevista", str(data_prevista)[:10])
        .limit(1)
        .execute()
        .data
        or []
    )
    if not ocorrencias or ocorrencias[0].get("resultado"):
        return
    ocorrencia = ocorrencias[0]
    if ocorrencia.get("pendencia_id"):
        antiga = _dd_mm_aaaa(data_prevista)
        anotacao = (
            f"A data do evento mudou de {antiga} para {_dd_mm_aaaa(data_nova)} antes do resultado."
            if data_nova
            else f"A data do evento, {antiga}, foi retirada antes do resultado."
        )
        _agir_no_lembrete(
            supabase,
            ocorrencia["pendencia_id"],
            Comando.CANCELAR,
            anotacao=anotacao,
            autor_id=autor_id,
            autor_nome=autor_nome,
        )
    supabase.table(TABELA_OCORRENCIAS).delete().eq("id", ocorrencia["id"]).execute()


def _lembretes_abertos(supabase, ocorrencias: list[dict]) -> dict[str, dict]:
    """O lembrete aberto de cada evento (a Pendência da ocorrência ainda sem
    resultado), como a Presidência o vê na tela: código, prazo e situação. As
    rotas de Pendências não mostram o lembrete (é conteúdo do Núcleo)."""
    por_pendencia = {
        linha["pendencia_id"]: linha["item_id"]
        for linha in ocorrencias
        if linha.get("pendencia_id") and not linha.get("resultado")
    }
    if not por_pendencia:
        return {}
    pendencias = (
        supabase.table("pendencias")
        .select("id_acao, prazo, status")
        .in_("id_acao", list(por_pendencia))
        .in_("status", list(_STATUS_ABERTOS))
        .is_("deleted_at", "null")
        .execute()
        .data
        or []
    )
    # Atrasado é calculado pela data desde a issue #1862 (ADR 0098, decisão
    # 4): nenhum job grava mais ATRASADO, então a situação sai daqui.
    hoje = hoje_em_brasilia()
    for p in pendencias:
        p["status"] = situacao(p.get("status") or "", as_data(p.get("prazo")), hoje, repactuada=False)
    return {por_pendencia[p["id_acao"]]: p for p in pendencias}


def listar(supabase) -> list[dict[str, Any]]:
    """Os eventos, ativos primeiro e pela próxima data, cada um com o
    histórico dos resultados registrados (o mais novo primeiro) e o lembrete
    aberto, se houver."""
    itens = supabase.table(TABELA).select("*").execute().data or []
    historico: dict[str, list[dict]] = {}
    lembretes: dict[str, dict] = {}
    if itens:
        ocorrencias = (
            supabase.table(TABELA_OCORRENCIAS)
            .select("item_id, data_prevista, pendencia_id, resultado, realizada_em, registrado_por, registrado_em")
            .in_("item_id", [item["id"] for item in itens])
            .order("data_prevista", desc=True)
            .execute()
            .data
            or []
        )
        for linha in ocorrencias:
            if linha.get("resultado"):
                historico.setdefault(linha["item_id"], []).append(
                    {chave: valor for chave, valor in linha.items() if chave != "pendencia_id"}
                )
        lembretes = _lembretes_abertos(supabase, ocorrencias)
    itens.sort(
        key=lambda item: (
            not item.get("ativo"),
            item.get("proxima_data") is None,
            str(item.get("proxima_data")),
            item.get("evento") or "",
        )
    )
    return [
        {**item, "historico": historico.get(item["id"], []), "lembrete": lembretes.get(item["id"])} for item in itens
    ]
