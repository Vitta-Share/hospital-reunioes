"""O Início de cada pessoa (ADR 0104): a Minha Fila de todos os módulos.

O endpoint chama uma função por módulo, a fonte. Toda fonte devolve itens no
mesmo formato (tipo, título, origem, prazo ou a data em que o item chegou,
área, rótulo da ação, destino interno e, quando couber, a ação de um clique),
já recortados para quem pede. Aqui o grupo e o atraso de cada item saem da
data, a fila é ordenada e a frase é escrita. Fonte que lança erro não derruba
a resposta: ela some com um aviso (decisão 4). Módulo novo entra como fonte
nova em `FONTES`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from pydantic import BaseModel

from app.services.inicio import fonte_pendencias
from app.services.inicio.regras import (
    ATE_48_HORAS,
    FUSO,
    GRUPOS,
    PASSOU_DO_PRAZO,
    PROXIMOS_7_DIAS,
    dias_de_atraso,
    frase_do_inicio,
    grupo_do_prazo,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Fonte:
    nome: str
    rotulo: str
    itens: Callable[..., list[dict]]


FONTES: tuple[Fonte, ...] = (Fonte("pendencias", fonte_pendencias.ROTULO, fonte_pendencias.itens),)


class AcaoDeUmClique(BaseModel):
    rotulo: str
    endpoint: str


class ItemDoInicio(BaseModel):
    tipo: str
    id: str
    titulo: str
    origem: str
    prazo: date | None = None
    chegou_em: date | None = None
    area: str
    acao: str
    destino: str
    # A linha de contexto (issue #1935): aparece no hover, no foco e sempre na
    # tela de toque. Fonte que não tem o que dizer deixa vazia.
    contexto: str | None = None
    acao_de_um_clique: AcaoDeUmClique | None = None
    grupo: str | None = None
    dias_de_atraso: int | None = None


class Frase(BaseModel):
    titulo: str
    apoio: str


class Contadores(BaseModel):
    passou_do_prazo: int = 0
    ate_48_horas: int = 0
    proximos_7_dias: int = 0


class AvisoDeFonte(BaseModel):
    fonte: str
    mensagem: str


class Inicio(BaseModel):
    hoje: date
    frase: Frase
    contadores: Contadores
    itens: list[ItemDoInicio]
    avisos: list[AvisoDeFonte]
    # Previstos no contrato e vazios nesta fatia: as próximas Reuniões e as
    # Rotinas do ciclo (o trilho) e a linha de resumo de cada Fila do papel.
    trilho: list[dict] = []
    filas_do_papel: list[dict] = []


def _primeiro_nome(me: dict | None) -> str | None:
    nome = ((me or {}).get("nome_completo") or "").strip()
    return nome.split()[0] if nome else None


def _ordem(item: ItemDoInicio) -> tuple:
    # O mais atrasado primeiro, o mais distante por último; sem prazo no fim.
    return (item.prazo is None, item.prazo or date.max, item.id)


def montar_inicio(supabase, me: dict | None, agora: datetime, fontes: tuple[Fonte, ...] = FONTES) -> Inicio:
    itens: list[ItemDoInicio] = []
    avisos: list[AvisoDeFonte] = []
    if me:
        for fonte in fontes:
            try:
                brutos = fonte.itens(supabase, me)
            except Exception:
                logger.exception("[Início] A fonte %s falhou para %s", fonte.nome, me.get("id"))
                avisos.append(
                    AvisoDeFonte(
                        fonte=fonte.nome,
                        mensagem=f"Não foi possível carregar {fonte.rotulo} agora. Tente de novo em instantes.",
                    )
                )
                continue
            for bruto in brutos:
                item = ItemDoInicio(**bruto)
                item.grupo = grupo_do_prazo(item.prazo, agora)
                item.dias_de_atraso = dias_de_atraso(item.prazo, agora) if item.grupo == PASSOU_DO_PRAZO else None
                itens.append(item)
    itens.sort(key=_ordem)

    por_grupo = {grupo: [item for item in itens if item.grupo == grupo] for grupo in GRUPOS}
    vencidos = por_grupo[PASSOU_DO_PRAZO]
    hoje = agora.astimezone(FUSO).date()
    futuros = [item.prazo for item in itens if item.prazo is not None and item.prazo >= hoje]
    titulo, apoio = frase_do_inicio(
        nome=_primeiro_nome(me),
        vencidos=len(vencidos),
        maior_atraso=max((item.dias_de_atraso or 0 for item in vencidos), default=0),
        em_48_horas=len(por_grupo[ATE_48_HORAS]),
        proximo_prazo=min(futuros, default=None),
    )
    return Inicio(
        hoje=hoje,
        frase=Frase(titulo=titulo, apoio=apoio),
        contadores=Contadores(
            passou_do_prazo=len(vencidos),
            ate_48_horas=len(por_grupo[ATE_48_HORAS]),
            proximos_7_dias=len(por_grupo[PROXIMOS_7_DIAS]),
        ),
        itens=itens,
        avisos=avisos,
    )
