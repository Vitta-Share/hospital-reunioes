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

from app.services.pendencia_service import criar_pendencia_sem_reuniao
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


def registrar_resultado(
    supabase, item_id: str, *, resultado: str, realizada_em: date, autor_id: str | None, agora: datetime
) -> dict[str, Any]:
    """Guarda o resultado da ocorrência da próxima data, conclui o lembrete
    dela e avança a próxima data. Devolve o evento atualizado."""
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
            supabase.table("pendencias").update({"status": "CONCLUIDO"}).eq("id_acao", pendencia_id).in_(
                "status", list(_STATUS_ABERTOS)
            ).execute()
        except (APIError, httpx.HTTPError) as erro:
            # O resultado já está guardado; o lembrete aberto a Presidência
            # conclui à mão.
            logger.warning("[Agenda regulatória] Lembrete %s não concluído: %s", pendencia_id, erro)

    proxima = proxima_depois(date.fromisoformat(prevista), item["periodicidade"])
    atualizado = supabase.table(TABELA).update(
        {"proxima_data": proxima.isoformat() if proxima else None, "updated_at": agora.isoformat()}
    ).eq("id", item_id).execute().data or [{**item, "proxima_data": proxima.isoformat() if proxima else None}]
    return atualizado[0]


def listar(supabase) -> list[dict[str, Any]]:
    """Os eventos, ativos primeiro e pela próxima data, cada um com o
    histórico dos resultados registrados (o mais novo primeiro)."""
    itens = supabase.table(TABELA).select("*").execute().data or []
    historico: dict[str, list[dict]] = {}
    if itens:
        ocorrencias = (
            supabase.table(TABELA_OCORRENCIAS)
            .select("item_id, data_prevista, resultado, realizada_em, registrado_por, registrado_em")
            .in_("item_id", [item["id"] for item in itens])
            .order("data_prevista", desc=True)
            .execute()
            .data
            or []
        )
        for linha in ocorrencias:
            if linha.get("resultado"):
                historico.setdefault(linha["item_id"], []).append(linha)
    itens.sort(
        key=lambda item: (
            not item.get("ativo"),
            item.get("proxima_data") is None,
            str(item.get("proxima_data")),
            item.get("evento") or "",
        )
    )
    return [{**item, "historico": historico.get(item["id"], [])} for item in itens]
