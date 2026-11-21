"""Os prazos do caso e a tabela de prazos do Núcleo (issue #1993, PRD #1979,
ADR 0107 decisões 1 e 2).

Confirmar a triagem congela os prazos do art. 26 do Regimento no caso, numa
linha por marco, com o vencimento já calculado em data e hora:

- os **legais** ficam aqui no código, e nenhuma tela os altera: 72 horas
  corridas para a notificação externa no óbito e no evento que nunca deveria
  ocorrer (faixa A), o 15º dia útil do mês seguinte nas outras faixas, e 60
  dias corridos para a complementação na faixa A. Contam do incidente (data e
  hora aproximada; sem hora, do começo do dia, que é o lado seguro). A
  circunstância de risco não é notificada e não tem prazo legal;
- os **internos** vêm da tabela do Núcleo (faixa e marco), carregada com os
  valores do art. 26 e editável pela Presidência e pelo Acesso pleno. Contam
  da chegada da notificação.

Mudar a tabela não alcança o caso já classificado (art. 26, § 2º): o caso lê
os vencimentos congelados, e não a tabela.

Confirmar também cria a linha mínima de notificação externa, com o sistema de
destino (MED vai ao VigiMed; o resto, ao NOTIVISA) e o prazo legal. O texto
para a vigilância e a fila são da Fase 4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from postgrest.exceptions import APIError

from app.services import feriados as feriados_service
from app.services.ouvidoria_prazos import (
    DIA_UTIL_DO_MES_SEGUINTE,
    DIAS_CORRIDOS,
    DIAS_UTEIS,
    FUSO,
    HORAS_CORRIDAS,
    HORAS_UTEIS,
    UTC,
    Prazo,
    calcular_vencimento,
)

logger = logging.getLogger(__name__)

TABELA_DE_PRAZOS = "nsp_tabela_de_prazos"
HISTORICO_DA_TABELA = "nsp_tabela_de_prazos_historico"
PRAZOS_DO_CASO = "nsp_prazos_do_caso"
NOTIFICACOES_EXTERNAS = "nsp_notificacoes_externas"

FAIXAS = ("A", "B", "C", "D", "E")

LEGAL = "legal"
INTERNO = "interno"

# Os marcos internos do art. 26, na ordem da tabela do Regimento.
MARCOS_INTERNOS = (
    "confirmacao_ao_notificante",
    "comunicacao_a_direcao",
    "triagem",
    "inicio_da_investigacao",
    "conclusao_da_investigacao",
    "reuniao_de_analise",
)
MARCOS_LEGAIS = ("notificacao_externa", "complementacao_da_notificacao_externa")

ROTULOS = {
    "confirmacao_ao_notificante": "Confirmação a quem notificou",
    "comunicacao_a_direcao": "Comunicação à Direção",
    "triagem": "Triagem e classificação",
    "inicio_da_investigacao": "Início da investigação",
    "conclusao_da_investigacao": "Conclusão da investigação e do plano de ação",
    "reuniao_de_analise": "Reunião de análise",
    "notificacao_externa": "Notificação externa à vigilância sanitária",
    "complementacao_da_notificacao_externa": "Complementação da notificação externa",
}

# As unidades que um prazo interno pode ter. O 15º dia útil do mês seguinte é
# regra legal, e não entra na tabela.
UNIDADES_INTERNAS = (HORAS_CORRIDAS, HORAS_UTEIS, DIAS_CORRIDOS, DIAS_UTEIS)
TETO_DO_VALOR = 365

# A carga inicial da tabela: o art. 26 do Regimento (Anexo D), coluna por
# faixa. A ausência da célula é "sem prazo próprio" (pauta ordinária, análise
# agregada mensal ou marco que a faixa não tem).
ART_26: dict[tuple[str, str], Prazo] = {
    **{(faixa, "confirmacao_ao_notificante"): Prazo(24, HORAS_CORRIDAS) for faixa in FAIXAS},
    ("A", "comunicacao_a_direcao"): Prazo(2, HORAS_CORRIDAS),
    ("B", "comunicacao_a_direcao"): Prazo(24, HORAS_CORRIDAS),
    ("A", "triagem"): Prazo(4, HORAS_UTEIS),
    ("B", "triagem"): Prazo(1, DIAS_UTEIS),
    ("C", "triagem"): Prazo(2, DIAS_UTEIS),
    ("D", "triagem"): Prazo(3, DIAS_UTEIS),
    ("E", "triagem"): Prazo(5, DIAS_UTEIS),
    ("A", "inicio_da_investigacao"): Prazo(24, HORAS_UTEIS),
    ("B", "inicio_da_investigacao"): Prazo(3, DIAS_UTEIS),
    ("C", "inicio_da_investigacao"): Prazo(5, DIAS_UTEIS),
    ("A", "conclusao_da_investigacao"): Prazo(45, DIAS_CORRIDOS),
    ("B", "conclusao_da_investigacao"): Prazo(30, DIAS_CORRIDOS),
    ("C", "conclusao_da_investigacao"): Prazo(20, DIAS_UTEIS),
    ("D", "conclusao_da_investigacao"): Prazo(10, DIAS_UTEIS),
    ("A", "reuniao_de_analise"): Prazo(7, DIAS_UTEIS),
    ("B", "reuniao_de_analise"): Prazo(15, DIAS_UTEIS),
}

SETENTA_E_DUAS_HORAS = Prazo(72, HORAS_CORRIDAS)
DECIMO_QUINTO_DIA_UTIL = Prazo(15, DIA_UTIL_DO_MES_SEGUINTE)
SESSENTA_DIAS = Prazo(60, DIAS_CORRIDOS)

# A circunstância de risco é categoria interna do hospital: nenhum incidente
# ocorreu, e ela não vai à vigilância (Anexo A, seção 7.3).
NAO_NOTIFICADA = "circunstancia_de_risco"

VIGIMED = "vigimed"
NOTIVISA = "notivisa"
CATEGORIA_DE_MEDICACAO = "MED"

# Os feriados que a conta lê: do incidente até bem depois do mais longo prazo
# em dias úteis (o 15º dia útil do mês seguinte e os 20 dias úteis).
_JANELA_DOS_FERIADOS = timedelta(days=120)


class PrazoRecusadoError(Exception):
    """A alteração não pode ser gravada; a mensagem vai para a tela."""


class PrazoLegalError(PrazoRecusadoError):
    pass


@dataclass(frozen=True)
class Vencimento:
    marco: str
    tipo: str
    prazo: Prazo
    contado_de: datetime
    vence_em: datetime


# ═══════════════════════════════════════════════════════════════════════════
# As regras
# ═══════════════════════════════════════════════════════════════════════════


def prazos_legais(faixa: str | None, natureza: str | None) -> dict[str, Prazo]:
    """Os prazos legais da faixa, fixos no código (RDC 36/2013 e NT 09/2025)."""
    if faixa not in FAIXAS or natureza == NAO_NOTIFICADA:
        return {}
    if faixa == "A":
        return {"notificacao_externa": SETENTA_E_DUAS_HORAS, "complementacao_da_notificacao_externa": SESSENTA_DIAS}
    return {"notificacao_externa": DECIMO_QUINTO_DIA_UTIL}


def sistema_de_destino(categoria: str | None) -> str:
    """Medicação vai ao VigiMed; o resto, ao NOTIVISA."""
    return VIGIMED if categoria == CATEGORIA_DE_MEDICACAO else NOTIVISA


def momento_do_incidente(data_ocorrencia: str, hora_aproximada: str | None) -> datetime:
    """O incidente em São Paulo. Sem a hora, o começo do dia: o prazo de 72
    horas nunca sai mais folgado que o da lei."""
    dia = date.fromisoformat(str(data_ocorrencia)[:10])
    hora = time.fromisoformat(str(hora_aproximada)[:8]) if hora_aproximada else time(0, 0)
    return datetime.combine(dia, hora, tzinfo=FUSO)


def _instante(bruto: str) -> datetime:
    momento = datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def calcular(
    *,
    faixa: str | None,
    natureza: str | None,
    recebida_em: datetime,
    incidente_em: datetime,
    tabela: dict[tuple[str, str], Prazo],
    feriados: frozenset[date],
) -> list[Vencimento]:
    """Os vencimentos do caso, marco a marco: os internos da tabela, contados
    da chegada, e os legais do código, contados do incidente."""
    if faixa not in FAIXAS:
        return []
    vencimentos = []
    for marco in MARCOS_INTERNOS:
        prazo = tabela.get((faixa, marco))
        if prazo is None or prazo.valor is None:
            continue
        vence = calcular_vencimento(recebida_em, prazo, feriados)
        vencimentos.append(Vencimento(marco, INTERNO, prazo, recebida_em, vence))
    for marco, prazo in prazos_legais(faixa, natureza).items():
        vence = calcular_vencimento(incidente_em, prazo, feriados)
        vencimentos.append(Vencimento(marco, LEGAL, prazo, incidente_em, vence))
    return vencimentos


# ═══════════════════════════════════════════════════════════════════════════
# A tabela de prazos internos
# ═══════════════════════════════════════════════════════════════════════════


def tabela_vigente(supabase) -> dict[tuple[str, str], Prazo]:
    """A tabela do banco, ou o art. 26 enquanto a migration 204 não rodou."""
    try:
        linhas = supabase.table(TABELA_DE_PRAZOS).select("faixa, marco, valor, unidade").execute().data
    except APIError:
        linhas = None
    if not linhas:
        return dict(ART_26)
    return {
        (linha["faixa"], linha["marco"]): Prazo(linha["valor"], linha["unidade"])
        for linha in linhas
        if linha.get("valor") is not None
    }


# ═══════════════════════════════════════════════════════════════════════════
# Congelar no caso, ao confirmar
# ═══════════════════════════════════════════════════════════════════════════


def _feriados_da_conta(supabase, inicio: date) -> frozenset[date]:
    """Os feriados do período. Sem o calendário, a conta segue sem feriado: o
    vencimento sai mais cedo, nunca mais tarde que o certo."""
    try:
        return feriados_service.feriados_entre(supabase, inicio, inicio + _JANELA_DOS_FERIADOS)
    except feriados_service.FALHAS_DE_LEITURA_DO_CALENDARIO as erro:
        logger.warning("Feriados ilegíveis; os prazos do caso contam sem feriado: %s", type(erro).__name__)
        return frozenset()


def congelar_no_caso(supabase, notificacao: dict[str, Any], decisao: dict[str, Any]) -> None:
    """Grava os prazos do caso e a linha de notificação externa, uma vez só.
    A nova tentativa de uma confirmação que caiu no meio não grava de novo."""
    caso_id = notificacao["id"]
    ja_gravados = supabase.table(PRAZOS_DO_CASO).select("id").eq("notificacao_id", caso_id).limit(1).execute().data
    incidente_em = momento_do_incidente(notificacao["data_ocorrencia"], notificacao.get("hora_aproximada"))
    if not ja_gravados:
        recebida_em = _instante(notificacao["criado_em"])
        vencimentos = calcular(
            faixa=decisao.get("faixa"),
            natureza=decisao.get("natureza"),
            recebida_em=recebida_em,
            incidente_em=incidente_em,
            tabela=tabela_vigente(supabase),
            feriados=_feriados_da_conta(supabase, min(incidente_em, recebida_em.astimezone(FUSO)).date()),
        )
        if vencimentos:
            supabase.table(PRAZOS_DO_CASO).insert(
                [
                    {
                        "notificacao_id": caso_id,
                        "marco": v.marco,
                        "tipo": v.tipo,
                        "valor": v.prazo.valor,
                        "unidade": v.prazo.unidade,
                        "contado_de": v.contado_de.astimezone(UTC).isoformat(),
                        "vence_em": v.vence_em.astimezone(UTC).isoformat(),
                    }
                    for v in vencimentos
                ]
            ).execute()


# ═══════════════════════════════════════════════════════════════════════════
# O que o caso mostra
# ═══════════════════════════════════════════════════════════════════════════

_ORDEM = {marco: posicao for posicao, marco in enumerate(MARCOS_INTERNOS + MARCOS_LEGAIS)}


def do_caso(supabase, caso_id: str) -> list[dict[str, Any]]:
    """Os prazos congelados do caso, com data e hora absolutas. Vazio enquanto
    a triagem não foi confirmada."""
    linhas = (
        supabase.table(PRAZOS_DO_CASO)
        .select("marco, tipo, valor, unidade, vence_em")
        .eq("notificacao_id", caso_id)
        .execute()
        .data
    ) or []
    linhas.sort(key=lambda linha: _ORDEM.get(linha["marco"], len(_ORDEM)))
    return [
        {
            "marco": linha["marco"],
            "rotulo": ROTULOS.get(linha["marco"], linha["marco"]),
            "tipo": linha["tipo"],
            "valor": linha["valor"],
            "unidade": linha["unidade"],
            "vence_em": linha["vence_em"],
        }
        for linha in linhas
    ]
