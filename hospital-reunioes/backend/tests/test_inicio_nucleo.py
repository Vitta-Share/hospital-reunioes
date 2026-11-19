"""O que o Núcleo espera da pessoa, no Início (issue #1939, PRD #1932, ADR 0104).

A fonte do Núcleo traz o que a Fase 1 tem: o Termo de Adesão pendente, o
documento do Núcleo esperando a assinatura da pessoa e a capacitação em que
falta confirmar a presença, esta com a ação de um clique. O acesso segue a
ADR 0095: a regra de verdade (`recursos_nsp`, lida da Participação vigente)
roda aqui sobre o banco de mentira, e o super admin sem acesso ao Núcleo não
recebe nada do Núcleo.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers import inicio as inicio_router  # noqa: E402
from app.services.inicio import fonte_nucleo  # noqa: E402
from app.services.seguranca_do_paciente import permissao  # noqa: E402

BRT = ZoneInfo("America/Sao_Paulo")
# Quarta-feira, 18/11/2026, 10h em Brasília.
AGORA = datetime(2026, 11, 18, 10, 0, tzinfo=BRT)
HOJE = AGORA.date()


# ─── O banco de mentira ───────────────────────────────────────────────────


@dataclass
class _Result:
    data: list


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []
        self._limite: int | None = None

    def select(self, *_a, **_kw):
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

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) <= valor)
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) >= valor)
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, n):
        self._limite = n
        return self

    def execute(self):
        linhas = [dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)]
        return _Result(linhas[: self._limite] if self._limite is not None else linhas)


NUCLEO_ID = "C_NSP"


@dataclass
class _Banco:
    colegiados: list = field(default_factory=lambda: [{"id": NUCLEO_ID, "slug": "nsp"}])
    participacoes: list = field(default_factory=list)
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    nsp_termos_envios: list = field(default_factory=list)
    nsp_documentos: list = field(default_factory=list)
    nsp_documentos_envios: list = field(default_factory=list)
    nsp_documentos_signatarios: list = field(default_factory=list)
    nsp_capacitacoes: list = field(default_factory=list)
    nsp_capacitacao_participantes: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


def _pessoa(pid: str, nome: str, **campos) -> dict:
    return {"id": pid, "nome_completo": nome, "access_profile": "regular", "role": "colaborador", **campos}


PRESIDENTE = _pessoa("P_PRES", "Paula Prado")
MEMBRO_COM_TERMO = _pessoa("P_COM", "Marcos Melo")
MEMBRO_SEM_TERMO = _pessoa("P_SEM", "Sara Souza")
ACESSO_PLENO = _pessoa("P_PLENO", "Davi Dias", perfil_nsp="acesso_pleno")
DE_FORA = _pessoa("P_FORA", "Fábio Faria")
SUPER_ADMIN = _pessoa("P_ADMIN", "Alice Alves", access_profile="super_admin")


def _participacao(pid: str, pessoa: dict, papel: str = "membro", termo: str | None = "2026-10-01T12:00:00+00:00"):
    return {
        "id": pid,
        "colegiado_id": NUCLEO_ID,
        "participante_id": pessoa["id"],
        "papel": papel,
        "vigencia_inicio": "2026-01-01",
        "vigencia_fim": "2027-12-31",
        "termo_assinado_em": termo,
    }


def _banco_do_nucleo(**tabelas) -> _Banco:
    """O Núcleo com a Presidência e o membro com Termo assinados e o membro
    sem Termo ainda pendente."""
    participacoes = [
        _participacao("PA_PRES", PRESIDENTE, papel="presidencia"),
        _participacao("PA_COM", MEMBRO_COM_TERMO),
        _participacao("PA_SEM", MEMBRO_SEM_TERMO, termo=None),
    ]
    return _Banco(participacoes=participacoes, **tabelas)


@pytest.fixture(autouse=True)
def _hoje(monkeypatch):
    monkeypatch.setattr(permissao, "hoje_em_sao_paulo", lambda: HOJE)
    monkeypatch.setattr(fonte_nucleo, "hoje_em_sao_paulo", lambda: HOJE)


def _rota(monkeypatch, me: dict, banco: _Banco):
    async def _participante(_user, _sb, fields=None):
        return me

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: AGORA)
    return asyncio.run(inicio_router.get_inicio(current_user={"id": "u1"}, supabase=banco))


def _do_nucleo(resposta) -> list:
    return [item for item in resposta.itens if item.area == "Segurança do Paciente"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. O Termo de Adesão pendente
# ═══════════════════════════════════════════════════════════════════════════


class TestTermoDeAdesao:
    def test_membro_sem_termo_ve_o_item_com_o_botao_que_abre_o_termo(self, monkeypatch):
        banco = _banco_do_nucleo(
            nsp_termos_envios=[
                {
                    "id": "T1",
                    "participacao_id": "PA_SEM",
                    "situacao": "enviado",
                    "enviado_em": "2026-11-10T13:00:00+00:00",
                    "created_at": "2026-11-10T13:00:00+00:00",
                }
            ]
        )

        resposta = _rota(monkeypatch, MEMBRO_SEM_TERMO, banco)

        itens = _do_nucleo(resposta)
        assert [item.tipo for item in itens] == ["termo_de_adesao"]
        termo = itens[0]
        assert termo.titulo == "Assinar o Termo de Adesão ao Núcleo"
        assert termo.acao == "Abrir o Termo de Adesão"
        assert termo.destino == "/seguranca-do-paciente/documentos"
        # Sem prazo no módulo: fica no grupo Sem prazo, com há quantos dias espera.
        assert termo.grupo == "sem_prazo"
        assert termo.dias_esperando == 8
        assert resposta.contadores.passou_do_prazo == 0
