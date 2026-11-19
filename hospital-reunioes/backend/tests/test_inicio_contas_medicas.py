"""A fonte de Contas médicas no Início (issue #1940, PRD #1932, ADR 0104).

As contas em correção ou em retorno que estão com a faturista entram na Minha
Fila dela, no grupo Sem prazo: o módulo não dá prazo à conta. A Fila de contas,
as contas com Guia pronto que ninguém pegou, é de um papel e não de uma pessoa:
entra como uma linha da Fila do papel para quem analisa contas, fora da frase e
dos contadores. Quem não tem perfil de Contas médicas não recebe nada.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers import inicio as inicio_router  # noqa: E402

BRT = ZoneInfo("America/Sao_Paulo")
# Quarta-feira, 18/11/2026, 10h em Brasília.
AGORA = datetime(2026, 11, 18, 10, 0, tzinfo=BRT)


# ─── O banco de mentira ───────────────────────────────────────────────────


@dataclass
class _Result:
    data: list
    count: int | None = None


class _Consulta:
    def __init__(self, nome: str, linhas: list[dict], lidas: list[str]):
        self._nome = nome
        self._linhas = linhas
        self._lidas = lidas
        self._filtros: list = []
        self._contar = False

    def select(self, *_a, count=None, **_kw):
        self._contar = count == "exact"
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        valores = set(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def execute(self):
        self._lidas.append(self._nome)
        linhas = [dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)]
        return _Result(linhas, len(linhas) if self._contar else None)


@dataclass
class _Banco:
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    cm_conta: list = field(default_factory=list)
    cm_atendimento: list = field(default_factory=list)
    cm_perfil_permissao: list = field(default_factory=list)
    lidas: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(nome, getattr(self, nome), self.lidas)


# A matriz de permissões de Contas médicas como o banco a guarda: a faturista e
# a coordenadora analisam contas; o apoio ao faturamento só envia.
MATRIZ = [
    {"perfil": "faturista", "permissao": "enviar_corrigir_contas", "ligada": True},
    {"perfil": "coordenadora", "permissao": "enviar_corrigir_contas", "ligada": True},
    {"perfil": "coordenadora", "permissao": "painel_completo", "ligada": True},
    {"perfil": "apoio_faturamento", "permissao": "enviar_contas", "ligada": True},
]

FATIMA = {
    "id": "P_FATIMA",
    "nome_completo": "Fátima Rocha",
    "access_profile": None,
    "perfil_contas_medicas": "faturista",
}
CORA = {
    "id": "P_CORA",
    "nome_completo": "Cora Dias",
    "access_profile": None,
    "perfil_contas_medicas": "coordenadora",
}
AURORA = {"id": "P_AURORA", "nome_completo": "Aurora Lima", "access_profile": "regular", "perfil_contas_medicas": None}


def _conta(id_: str, situacao: str = "A_FAZER", faturista_id: str | None = None, **campos) -> dict:
    base = {
        "id": id_,
        "situacao": situacao,
        "faturista_id": faturista_id,
        "atendimento_id": f"AT_{id_}",
        "numero_conta": f"9{id_[-3:]}",
        "aberta_em": "2026-11-13T14:00:00+00:00",
        "ordem_fila": 1,
    }
    return {**base, **campos}


def _atendimento(id_conta: str, numero: str) -> dict:
    return {"id": f"AT_{id_conta}", "numero_atendimento": numero}


def _banco(contas: list[dict], atendimentos: list[dict] | None = None) -> _Banco:
    return _Banco(cm_conta=contas, cm_atendimento=atendimentos or [], cm_perfil_permissao=list(MATRIZ))


def _rota(monkeypatch, me: dict | None, banco: _Banco, agora: datetime = AGORA):
    async def _participante(_user, _sb, fields=None):
        return me

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: agora)
    return asyncio.run(inicio_router.get_inicio(current_user={"id": "u1"}, supabase=banco))


def _contas(resposta) -> list[tuple[str, str | None]]:
    return [(item.id, item.grupo) for item in resposta.itens if item.area == "Contas médicas"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. A faturista vê as contas que estão com ela
# ═══════════════════════════════════════════════════════════════════════════


class TestFaturista:
    def test_faturista_ve_a_conta_em_correcao_e_a_em_retorno_em_sem_prazo(self, monkeypatch):
        banco = _banco(
            [
                _conta("C001", "EM_CORRECAO", "P_FATIMA"),
                _conta("C002", "RETORNO", "P_FATIMA"),
            ],
            [_atendimento("C001", "123456"), _atendimento("C002", "654321")],
        )

        resposta = _rota(monkeypatch, FATIMA, banco)

        assert sorted(_contas(resposta)) == [("C001", "sem_prazo"), ("C002", "sem_prazo")]
        em_correcao = next(item for item in resposta.itens if item.id == "C001")
        assert em_correcao.titulo == "Atendimento 123456, conta 9001"
        assert em_correcao.destino == "/contas-medicas/guia/C001"
        assert em_correcao.acao == "Abrir o Guia"
        # A conta foi puxada em 13/11: espera há 5 dias.
        assert em_correcao.dias_esperando == 5
        assert em_correcao.prazo is None
