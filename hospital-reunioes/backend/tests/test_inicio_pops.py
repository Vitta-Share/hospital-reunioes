"""O POP na etapa da pessoa, no Início (issue #1938, PRD #1932, ADR 0104).

A Versão em elaboração, revisão ou validação aparece para quem é o designado da
etapa atual: o Elaborador na elaboração, o Revisor na revisão, o Validador na
validação. O módulo não dá prazo à etapa, então o item fica em "Sem prazo", com
há quantos dias a Versão está na etapa (a data da transição que a pôs lá, da
trilha de auditoria; na etapa "a elaborar", a criação da Versão).
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


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []

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

    def execute(self):
        return _Result([dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)])


@dataclass
class _Banco:
    pops: list = field(default_factory=list)
    pops_versoes: list = field(default_factory=list)
    audit_log: list = field(default_factory=list)
    # A fonte de Pendências também roda: sem nada no nome de ninguém.
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


ELABORADORA = {"id": "P_ELA", "nome_completo": "Elisa Prado", "perfil_pop": "coordenador"}
REVISOR = {"id": "P_REV", "nome_completo": "Rui Vaz", "perfil_pop": "gerente"}
VALIDADORA = {"id": "P_VAL", "nome_completo": "Vera Lins", "perfil_pop": "gestor_qualidade"}
DE_OUTRO_SETOR = {"id": "P_OUT", "nome_completo": "Otto Reis", "perfil_pop": "coordenador"}


def _pop(pop_id: str, **campos) -> dict:
    base = {
        "id": pop_id,
        "codigo": f"HSM_ENF-{pop_id[-3:]}",
        "nome": f"Higiene das mãos {pop_id}",
        "setor_id": "S_ENF",
        "elaborador_id": ELABORADORA["id"],
        "revisor_id": REVISOR["id"],
        "validador_id": VALIDADORA["id"],
    }
    return {**base, **campos}


def _versao(versao_id: str, pop_id: str, estado: str, created_at: str = "2026-11-02T13:00:00+00:00") -> dict:
    return {"id": versao_id, "pop_id": pop_id, "estado": estado, "numero_versao": "1.0", "created_at": created_at}


def _transicao(versao_id: str, action: str, para: str, quando: str) -> dict:
    return {
        "action": action,
        "target_type": "pop_versao",
        "target_id": versao_id,
        "timestamp": quando,
        "metadata": {"para": para},
    }


def _rota(monkeypatch, me: dict, banco: _Banco):
    async def _participante(_user, _sb, fields=None):
        return me

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: AGORA)
    return asyncio.run(inicio_router.get_inicio(current_user={"id": "u1"}, supabase=banco))


def _pops(resposta) -> list:
    return [item for item in resposta.itens if item.tipo == "pop"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. O designado da etapa atual vê o POP, e o botão abre a etapa
# ═══════════════════════════════════════════════════════════════════════════


class TestPorPapel:
    def test_elaboradora_ve_o_pop_em_elaboracao_e_o_botao_abre_a_elaboracao(self, monkeypatch):
        banco = _Banco(
            pops=[_pop("POP001")],
            pops_versoes=[_versao("V1", "POP001", "EM_ELABORACAO")],
            audit_log=[_transicao("V1", "POPS_INICIAR_ELABORACAO", "EM_ELABORACAO", "2026-11-10T15:00:00+00:00")],
        )

        resposta = _rota(monkeypatch, ELABORADORA, banco)

        [item] = _pops(resposta)
        assert item.id == "POP001"
        assert item.titulo == "Higiene das mãos POP001"
        assert item.area == "POPs"
        assert item.acao == "Elaborar"
        assert item.destino == "/pops/POP001/elaboracao"

    def test_revisor_ve_o_pop_em_revisao_e_o_botao_abre_a_versao(self, monkeypatch):
        banco = _Banco(
            pops=[_pop("POP002")],
            pops_versoes=[_versao("V2", "POP002", "EM_REVISAO")],
            audit_log=[_transicao("V2", "POPS_APROVAR_VERSAO_FINAL", "EM_REVISAO", "2026-11-12T15:00:00+00:00")],
        )

        [item] = _pops(_rota(monkeypatch, REVISOR, banco))

        assert (item.id, item.acao, item.destino) == ("POP002", "Revisar", "/pops/POP002/versao")

    def test_validadora_ve_o_pop_em_validacao_e_o_botao_abre_a_versao(self, monkeypatch):
        banco = _Banco(
            pops=[_pop("POP003")],
            pops_versoes=[_versao("V3", "POP003", "EM_VALIDACAO")],
            audit_log=[_transicao("V3", "POPS_APROVAR_REVISAO", "EM_VALIDACAO", "2026-11-14T15:00:00+00:00")],
        )

        [item] = _pops(_rota(monkeypatch, VALIDADORA, banco))

        assert (item.id, item.acao, item.destino) == ("POP003", "Validar", "/pops/POP003/versao")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Sem prazo, com há quantos dias a Versão está na etapa
# ═══════════════════════════════════════════════════════════════════════════


class TestSemPrazo:
    def test_o_pop_fica_em_sem_prazo_com_os_dias_desde_que_entrou_na_etapa(self, monkeypatch):
        # Duas idas à revisão: vale a mais recente (16/11, às 23h de Brasília
        # ainda é dia 16, mesmo já sendo 17 em UTC). Hoje é 18/11: 2 dias.
        banco = _Banco(
            pops=[_pop("POP002")],
            pops_versoes=[_versao("V2", "POP002", "EM_REVISAO")],
            audit_log=[
                _transicao("V2", "POPS_APROVAR_VERSAO_FINAL", "EM_REVISAO", "2026-11-05T15:00:00+00:00"),
                _transicao("V2", "POPS_DEVOLVER_REVISAO", "EM_ELABORACAO", "2026-11-09T15:00:00+00:00"),
                _transicao("V2", "POPS_APROVAR_VERSAO_FINAL", "EM_REVISAO", "2026-11-17T02:00:00+00:00"),
            ],
        )

        resposta = _rota(monkeypatch, REVISOR, banco)

        [item] = _pops(resposta)
        assert item.grupo == "sem_prazo"
        assert item.prazo is None
        assert item.chegou_em.isoformat() == "2026-11-16"
        assert item.dias_esperando == 2
        assert resposta.contadores.passou_do_prazo == 0
        assert resposta.frase.titulo == "Rui, você está em dia."

    def test_a_elaborar_conta_desde_a_criacao_da_versao(self, monkeypatch):
        banco = _Banco(
            pops=[_pop("POP004")],
            pops_versoes=[_versao("V4", "POP004", "A_ELABORAR", created_at="2026-11-08T12:00:00+00:00")],
        )

        [item] = _pops(_rota(monkeypatch, ELABORADORA, banco))

        assert (item.grupo, item.dias_esperando, item.acao) == ("sem_prazo", 10, "Elaborar")

    def test_sem_a_data_da_etapa_o_pop_aparece_sem_a_contagem(self, monkeypatch):
        banco = _Banco(pops=[_pop("POP002")], pops_versoes=[_versao("V2", "POP002", "EM_REVISAO")])

        [item] = _pops(_rota(monkeypatch, REVISOR, banco))

        assert (item.grupo, item.chegou_em, item.dias_esperando) == ("sem_prazo", None, None)
