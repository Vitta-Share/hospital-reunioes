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
0104). Gráfico por setor de atrasos, ranking e evolução semanal são de outras
fatias; o `por_setor` daqui só mantém o gráfico que o painel já tinha.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel

from app.services.paginacao import ler_tudo
from app.services.pendencia_ciclo import situacao
from app.services.pendencias_consulta import as_data, ids_repactuados, no_recorte
from app.services.pendencias_recorte import RecorteDasPendencias

ABERTAS = ("PENDENTE", "EM_PROGRESSO")
# A Ata parada espera validação (ou a IA) há mais de 3 dias.
ESTADOS_PARADOS = ("PROCESSANDO", "AGUARDANDO_VALIDACAO")
AGUARDANDO_ASSINATURA = "AGUARDANDO_ASSINATURA"
SEM_SETOR = "Sem Setor"
DIAS_DO_VENCE_LOGO = 3
DIAS_DA_ATA_PARADA = 3


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


class PainelDeReunioes(BaseModel):
    cards: CardsDoPainel
    situacoes: SituacoesDoPainel
    por_setor: list[SetorDoPainel]
    atas_paradas: list[AtaDoPainel]
    aguardam_assinatura: list[AtaDoPainel]


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


def montar_painel(
    supabase,
    recorte: RecorteDasPendencias,
    *,
    hoje: date,
    agora: datetime,
    filtros: FiltrosDoPainel | None = None,
) -> PainelDeReunioes:
    """Lê a base inteira em páginas e faz a conta."""

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
        lambda: supabase.table("participantes").select("id, setor").order("id"),
        rotulo="setores do painel",
    )
    setor_de = {p["id"]: p.get("setor") for p in participantes}

    repactuados = ids_repactuados(supabase, [p["id_acao"] for p in pendencias if p.get("id_acao")])
    return calcular_painel(
        pendencias=pendencias,
        reunioes=reunioes,
        recorte=recorte,
        repactuados=repactuados,
        setor_de=setor_de,
        hoje=hoje,
        agora=agora,
        filtros=filtros,
    )
