"""O painel de Reuniões calculado no servidor (issue #1868; ADR 0098, decisão
10, emendada pela ADR 0104).

O painel lia 200 Pendências e 200 Reuniões no navegador, e as estatísticas
cortavam em 1000 linhas no PostgREST. Aqui a leitura é da base inteira, em
páginas (`ler_tudo`), e a conta é Python pura (`calcular_painel`), já no
recorte de quem pede (`pendencias_recorte`, issue #1863):

- o responsável conta as Pendências de que é responsável ou co-responsável;
- o Facilitador conta também as Reuniões que facilita e as Pendências delas
  (decisão 59 do diretor no PRD #1757);
- o Super admin conta o hospital inteiro (decisão 67), menos o Núcleo que o
  Núcleo esconde (ADR 0095).

O alerta de 48 horas e a Minha Fila não moram aqui: estão no Início (ADR
0104). A evolução semanal e a seta dos cards vêm da fotografia de segunda
(`fotografia_do_painel`, issue #1873); o `por_setor` daqui mantém o gráfico
que o painel já tinha, no recorte de quem pede.

O gráfico de atrasos por setor e o ranking de 90 dias (issue #1871) contam o
hospital inteiro (decisão 55 do diretor), menos o Núcleo que o Núcleo esconde,
e só vão para o Super admin e para quem facilita ao menos uma Reunião: o
responsável não vê ranking (decisão 35). A conta é `calcular_ranking`.

As Rotinas entram no ranking ao lado dos atrasos e das reaberturas (decisão 71;
issue #1879): o ciclo não cumprido conta para o responsável da Rotina.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel

from app.services import rotina_service
from app.services.paginacao import ler_tudo
from app.services.pendencia_ciclo import esta_atrasada, situacao
from app.services.pendencias_consulta import (
    FUSO,
    as_data,
    ids_repactuados,
    no_recorte,
    sem_reunioes_ocultas,
)
from app.services.pendencias_recorte import RecorteDasPendencias

ABERTAS = ("PENDENTE", "EM_PROGRESSO")
# A Ata parada espera validação (ou a IA) há mais de 3 dias.
ESTADOS_PARADOS = ("PROCESSANDO", "AGUARDANDO_VALIDACAO")
AGUARDANDO_ASSINATURA = "AGUARDANDO_ASSINATURA"
SEM_SETOR = "Sem Setor"
DIAS_DO_VENCE_LOGO = 3
DIAS_DA_ATA_PARADA = 3
# O ranking conta o dia de hoje e os 89 anteriores (decisão 62 do diretor).
DIAS_DO_RANKING = 90


def agora_utc() -> datetime:
    return datetime.now(UTC)


class CardsDoPainel(BaseModel):
    atas_paradas: int = 0
    aguardam_assinatura: int = 0
    atrasadas: int = 0
    vencem_em_3_dias: int = 0
    # Abertas que não venceram, sobre as abertas (0 a 100).
    conformidade: int = 100
    ativas: int = 0


class SituacoesDoPainel(BaseModel):
    pendente: int = 0
    em_progresso: int = 0
    concluido: int = 0
    atrasado: int = 0
    repactuada: int = 0
    cancelado: int = 0


class SetorDoPainel(BaseModel):
    setor: str
    pendente: int = 0
    em_progresso: int = 0
    concluido: int = 0
    atrasado: int = 0
    repactuada: int = 0


class AtaDoPainel(BaseModel):
    id_reuniao: str
    data: str
    tipo: str | None = None
    objetivo: str | None = None
    status_ata: str
    updated_at: str | None = None
    # O Facilitador (e o Super admin) vê quem falta assinar e cobra (decisão 36).
    pode_cobrar: bool = False


class AtrasosDoPainel(BaseModel):
    """Os atrasos de quem é responsável, ou de um setor. `atrasadas`: abertas
    com o prazo vencido agora. Nos últimos 90 dias: `repactuacoes_vencidas`
    (Repactuação feita depois do vencimento), `concluidas_com_atraso`
    (conclusão depois do prazo, só as do ciclo de vida novo, que guarda a
    data) e `reaberturas` (entrega concluída e reaberta), que ficam ao lado
    dos atrasos (decisão 44) e não somam neles. Também ao lado, os
    `rotinas_nao_cumpridas`: os ciclos de Rotina não realizados, marcados
    fora do ciclo ou fechados sem marcação, nos últimos 90 dias (decisão 71;
    issue #1879)."""

    atrasadas: int = 0
    repactuacoes_vencidas: int = 0
    concluidas_com_atraso: int = 0
    atrasos: int = 0
    reaberturas: int = 0
    rotinas_nao_cumpridas: int = 0


class SetorDosAtrasos(AtrasosDoPainel):
    setor: str


class LinhaDoRanking(AtrasosDoPainel):
    responsavel_id: str
    nome: str | None = None
    setor: str


class SemanaDaEvolucao(BaseModel):
    """Uma semana fotografada (issue #1873): a segunda-feira e as atrasadas."""

    semana: str
    atrasadas: int


class PainelDeReunioes(BaseModel):
    cards: CardsDoPainel
    situacoes: SituacoesDoPainel
    por_setor: list[SetorDoPainel]
    atas_paradas: list[AtaDoPainel]
    aguardam_assinatura: list[AtaDoPainel]
    # None para quem não é Super admin nem Facilitador (issue #1871).
    atrasos_por_setor: list[SetorDosAtrasos] | None = None
    ranking: list[LinhaDoRanking] | None = None
    # A fotografia semanal (issue #1873): as atrasadas das últimas 8 semanas
    # fotografadas e os cards da semana anterior, que dão a seta. Sem a
    # fotografia da semana anterior, ou com filtro, None: o card fica sem seta.
    evolucao: list[SemanaDaEvolucao] = []
    semana_anterior: CardsDoPainel | None = None


@dataclass(frozen=True)
class RankingDoPainel:
    ranking: list[LinhaDoRanking]
    atrasos_por_setor: list[SetorDosAtrasos]


@dataclass(frozen=True)
class FiltrosDoPainel:
    responsaveis: frozenset[str] = field(default_factory=frozenset)
    setores: frozenset[str] = field(default_factory=frozenset)
    prazo_de: date | None = None
    prazo_ate: date | None = None


def _ve_reuniao(recorte: RecorteDasPendencias, reuniao: dict) -> bool:
    if reuniao.get("id_reuniao") in recorte.ocultas:
        return False
    return recorte.reunioes is None or reuniao.get("id_reuniao") in recorte.reunioes


def _pode_cobrar(recorte: RecorteDasPendencias, reuniao: dict) -> bool:
    if recorte.reunioes is None:
        return True
    pid = recorte.participante_id
    return pid is not None and reuniao.get("facilitador_id") == pid


def _passa_nos_filtros(pendencia: dict, filtros: FiltrosDoPainel, setor_de: dict[str, str | None]) -> bool:
    if filtros.responsaveis and pendencia.get("responsavel_id") not in filtros.responsaveis:
        return False
    if filtros.setores:
        setor = setor_de.get(pendencia.get("responsavel_id") or "") or SEM_SETOR
        if setor not in filtros.setores:
            return False
    prazo = as_data(pendencia.get("prazo"))
    if filtros.prazo_de and (prazo is None or prazo < filtros.prazo_de):
        return False
    if filtros.prazo_ate and (prazo is None or prazo > filtros.prazo_ate):
        return False
    return True


def _parada(reuniao: dict, limite: datetime) -> bool:
    if reuniao.get("status_ata") not in ESTADOS_PARADOS:
        return False
    atualizada = reuniao.get("updated_at")
    if not atualizada:
        return True  # sem data, conta como parada (conservador, como o front fazia)
    return datetime.fromisoformat(str(atualizada).replace("Z", "+00:00")) < limite


def calcular_painel(
    *,
    pendencias: Iterable[dict],
    reunioes: Iterable[dict],
    recorte: RecorteDasPendencias,
    repactuados: set[str],
    setor_de: dict[str, str | None],
    hoje: date,
    agora: datetime,
    filtros: FiltrosDoPainel | None = None,
) -> PainelDeReunioes:
    """A conta do painel, sem banco: cada Pendência conta uma vez, na situação
    que a lista mostra (ADR 0098, decisão 4). As `pendencias` chegam já no
    recorte (a consulta aplica `no_recorte`); as `reunioes`, não, e o recorte
    delas é feito aqui."""
    filtros = filtros or FiltrosDoPainel()
    situacoes = SituacoesDoPainel()
    setores: dict[str, SetorDoPainel] = {}
    vencem_logo = 0
    limite_do_vence_logo = hoje + timedelta(days=DIAS_DO_VENCE_LOGO)

    for p in pendencias:
        if not _passa_nos_filtros(p, filtros, setor_de):
            continue
        status = p.get("status") or ""
        prazo = as_data(p.get("prazo"))
        s = situacao(status, prazo, hoje, repactuada=p.get("id_acao") in repactuados)
        chave = s.lower()
        if not hasattr(situacoes, chave):
            continue
        setattr(situacoes, chave, getattr(situacoes, chave) + 1)
        if status in ABERTAS and prazo is not None and hoje <= prazo <= limite_do_vence_logo:
            vencem_logo += 1
        if chave != "cancelado":
            nome = setor_de.get(p.get("responsavel_id") or "") or SEM_SETOR
            linha = setores.setdefault(nome, SetorDoPainel(setor=nome))
            setattr(linha, chave, getattr(linha, chave) + 1)

    ativas = situacoes.pendente + situacoes.em_progresso + situacoes.repactuada + situacoes.atrasado
    conformidade = round((ativas - situacoes.atrasado) / ativas * 100) if ativas else 100

    # Ata parada: sem atualização há mais de 3 dias, contados da meia-noite UTC
    # de hoje (o updated_at vem em UTC), a mesma regra que o front usava.
    limite_parada = agora.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=DIAS_DA_ATA_PARADA
    )
    paradas: list[AtaDoPainel] = []
    em_assinatura: list[AtaDoPainel] = []
    for r in sorted(reunioes, key=lambda r: (r.get("data") or "", r.get("id_reuniao") or "")):
        if not _ve_reuniao(recorte, r):
            continue
        if filtros.setores and r.get("setor") not in filtros.setores:
            continue
        ata = AtaDoPainel(
            id_reuniao=r["id_reuniao"],
            data=str(r.get("data") or ""),
            tipo=r.get("tipo"),
            objetivo=r.get("objetivo"),
            status_ata=r.get("status_ata") or "",
            updated_at=r.get("updated_at"),
            pode_cobrar=_pode_cobrar(recorte, r),
        )
        if r.get("status_ata") == AGUARDANDO_ASSINATURA:
            em_assinatura.append(ata)
        elif _parada(r, limite_parada):
            paradas.append(ata)

    por_setor = sorted(
        setores.values(),
        key=lambda s: (-(s.pendente + s.em_progresso + s.atrasado + s.repactuada), s.setor),
    )
    return PainelDeReunioes(
        cards=CardsDoPainel(
            atas_paradas=len(paradas),
            aguardam_assinatura=len(em_assinatura),
            atrasadas=situacoes.atrasado,
            vencem_em_3_dias=vencem_logo,
            conformidade=conformidade,
            ativas=ativas,
        ),
        situacoes=situacoes,
        por_setor=por_setor,
        atas_paradas=paradas,
        aguardam_assinatura=em_assinatura,
    )


def _dia_em_brasilia(valor) -> date | None:
    if not valor:
        return None
    momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return momento.astimezone(FUSO).date()


def inicio_do_ranking(hoje: date) -> date:
    return hoje - timedelta(days=DIAS_DO_RANKING - 1)


# Ao lado dos atrasos, sem somar neles.
_AO_LADO = ("reaberturas", "rotinas_nao_cumpridas")


def _somar(linha: AtrasosDoPainel, campo: str, quantos: int = 1) -> None:
    setattr(linha, campo, getattr(linha, campo) + quantos)
    if campo not in _AO_LADO:
        linha.atrasos += quantos


def calcular_ranking(
    *,
    pendencias: Iterable[dict],
    historico: Iterable[dict],
    nome_de: dict[str, str | None],
    setor_de: dict[str, str | None],
    hoje: date,
    rotinas: Iterable[dict] = (),
    verificacoes: Iterable[dict] = (),
) -> RankingDoPainel:
    """O ranking de 90 dias e o gráfico de atrasos por setor, sem banco.

    Cada atraso conta para quem é o responsável pela Pendência, no setor
    dele (decisão 61). A Pendência cancelada sai de todas as contas
    (decisão 60): o cancelamento não pesa contra o responsável."""
    inicio = inicio_do_ranking(hoje)

    def na_janela(dia: date | None) -> bool:
        return dia is not None and inicio <= dia <= hoje

    por_id = {p["id_acao"]: p for p in pendencias if p.get("status") != "CANCELADO" and p.get("responsavel_id")}
    linhas: dict[str, LinhaDoRanking] = {}

    def linha_de(p: dict) -> LinhaDoRanking:
        # A Pendência ou a Rotina: as duas têm `responsavel_id`.
        rid = p["responsavel_id"]
        if rid not in linhas:
            linhas[rid] = LinhaDoRanking(
                responsavel_id=rid, nome=nome_de.get(rid), setor=setor_de.get(rid) or SEM_SETOR
            )
        return linhas[rid]

    for p in por_id.values():
        if esta_atrasada(p.get("status") or "", as_data(p.get("prazo")), hoje):
            _somar(linha_de(p), "atrasadas")

    for evento in historico:
        p = por_id.get(evento.get("id_acao"))
        dia = _dia_em_brasilia(evento.get("criado_em"))
        if p is None or not na_janela(dia):
            continue
        # A conclusão vem do evento, com o prazo que valia nela: a Reabertura
        # apaga `pendencias.concluida_em` e o histórico guarda o atraso.
        if evento.get("comando") == "concluir":
            prazo_antes = as_data(evento.get("prazo_antes"))
            if prazo_antes is not None and dia > prazo_antes:
                _somar(linha_de(p), "concluidas_com_atraso")
        elif evento.get("comando") == "repactuar" and evento.get("conta_atraso"):
            _somar(linha_de(p), "repactuacoes_vencidas")
        elif evento.get("comando") == "reabrir" and evento.get("status_antes") == "CONCLUIDO":
            _somar(linha_de(p), "reaberturas")

    marcadas: dict[str, list[dict]] = {}
    for v in verificacoes:
        marcadas.setdefault(v["rotina_id"], []).append(v)
    for rotina in rotinas:
        if not rotina.get("responsavel_id"):
            continue
        # O ciclo que ainda tocou a janela: o que terminou nela ou o em curso.
        falhas = [
            c
            for c in rotina_service.ciclos_nao_cumpridos(rotina, marcadas.get(rotina["id"], []), hoje)
            if c.fim >= inicio
        ]
        if falhas:
            _somar(linha_de(rotina), "rotinas_nao_cumpridas", len(falhas))

    ranking = sorted(
        linhas.values(),
        key=lambda li: (-li.atrasos, -li.rotinas_nao_cumpridas, -li.reaberturas, li.nome or "", li.responsavel_id),
    )
    setores: dict[str, SetorDosAtrasos] = {}
    for linha in ranking:
        do_setor = setores.setdefault(linha.setor, SetorDosAtrasos(setor=linha.setor))
        for campo in AtrasosDoPainel.model_fields:
            setattr(do_setor, campo, getattr(do_setor, campo) + getattr(linha, campo))
    por_setor = sorted(setores.values(), key=lambda s: (-s.atrasos, -s.rotinas_nao_cumpridas, -s.reaberturas, s.setor))
    return RankingDoPainel(ranking=ranking, atrasos_por_setor=por_setor)


def ve_ranking(me: dict | None, *, super_admin: bool, facilita_alguma: bool) -> bool:
    """O ranking e o gráfico de atrasos aparecem para o Super admin e para quem
    facilita ao menos uma Reunião (Refino da #1757, item 1)."""
    return me is not None and (super_admin or facilita_alguma)


def _montar_ranking(supabase, recorte: RecorteDasPendencias, *, hoje: date, participantes: list[dict]):
    ocultas = list(recorte.ocultas)
    pendencias = ler_tudo(
        lambda: sem_reunioes_ocultas(
            supabase.table("pendencias")
            .select("id_acao, status, prazo, responsavel_id, id_reuniao")
            .is_("deleted_at", "null")
            .not_.is_("id_reuniao", "null"),
            ocultas,
        ).order("id_acao"),
        rotulo="pendências do ranking",
    )
    # Um dia de folga na consulta: a borda exata da janela é decidida no fuso
    # de Brasília, em `calcular_ranking`.
    desde = (inicio_do_ranking(hoje) - timedelta(days=1)).isoformat()
    historico = ler_tudo(
        lambda: (
            supabase.table("pendencia_historico")
            .select("id, id_acao, comando, criado_em, conta_atraso, status_antes, prazo_antes")
            .in_("comando", ["concluir", "repactuar", "reabrir"])
            .gte("criado_em", desde)
            .order("id")
        ),
        rotulo="histórico do ranking",
    )
    # As Rotinas com ciclo (a sem frequência não tem), menos as do Núcleo oculto.
    rotinas = [
        r
        for r in ler_tudo(
            lambda: (
                supabase.table("rotinas")
                .select("id, id_reuniao, responsavel_id, frequencia, comeca_em, encerrada_em")
                .not_.is_("frequencia", "null")
                .order("id")
            ),
            rotulo="rotinas do ranking",
        )
        if r.get("id_reuniao") not in recorte.ocultas
    ]
    # Só o ciclo que terminou na janela, ou depois, pode pesar.
    verificacoes = ler_tudo(
        lambda: (
            supabase.table("rotina_verificacoes")
            .select("rotina_id, ciclo_inicio, resultado, atrasada")
            .gte("ciclo_fim", inicio_do_ranking(hoje).isoformat())
            .order("rotina_id")
            .order("ciclo_inicio")
        ),
        rotulo="verificações do ranking",
    )
    return calcular_ranking(
        pendencias=pendencias,
        historico=historico,
        nome_de={p["id"]: p.get("nome_completo") for p in participantes},
        setor_de={p["id"]: p.get("setor") for p in participantes},
        hoje=hoje,
        rotinas=rotinas,
        verificacoes=verificacoes,
    )


def montar_painel(
    supabase,
    recorte: RecorteDasPendencias,
    *,
    hoje: date,
    agora: datetime,
    filtros: FiltrosDoPainel | None = None,
    com_ranking: bool = False,
) -> PainelDeReunioes:
    """Lê a base inteira em páginas e faz a conta. Com `com_ranking`, junta o
    gráfico de atrasos por setor e o ranking de 90 dias do hospital inteiro."""

    def _consulta_de_pendencias():
        return no_recorte(
            supabase.table("pendencias")
            .select("id_acao, status, prazo, responsavel_id, co_responsavel_id, id_reuniao")
            .is_("deleted_at", "null")
            .not_.is_("id_reuniao", "null"),
            recorte,
        )

    pendencias: list[dict] = []
    if _consulta_de_pendencias() is not None:
        pendencias = ler_tudo(lambda: _consulta_de_pendencias().order("id_acao"), rotulo="pendências do painel")

    reunioes: list[dict] = []
    if recorte.reunioes is None or recorte.reunioes:
        reunioes = ler_tudo(
            lambda: (
                supabase.table("reunioes")
                .select("id_reuniao, data, tipo, objetivo, status_ata, updated_at, facilitador_id, setor")
                .is_("deleted_at", "null")
                .in_("status_ata", [*ESTADOS_PARADOS, AGUARDANDO_ASSINATURA])
                .order("id_reuniao")
            ),
            rotulo="reuniões do painel",
        )

    participantes = ler_tudo(
        lambda: supabase.table("participantes").select("id, setor, nome_completo").order("id"),
        rotulo="setores do painel",
    )
    setor_de = {p["id"]: p.get("setor") for p in participantes}

    repactuados = ids_repactuados(supabase, [p["id_acao"] for p in pendencias if p.get("id_acao")])
    painel = calcular_painel(
        pendencias=pendencias,
        reunioes=reunioes,
        recorte=recorte,
        repactuados=repactuados,
        setor_de=setor_de,
        hoje=hoje,
        agora=agora,
        filtros=filtros,
    )
    if com_ranking:
        ranking = _montar_ranking(supabase, recorte, hoje=hoje, participantes=participantes)
        painel.ranking = ranking.ranking
        painel.atrasos_por_setor = ranking.atrasos_por_setor
    return painel
