"""O Início com a Minha Fila das Pendências (issue #1934, PRD #1932, ADR 0104).

Um endpoint monta o Início de quem pede chamando uma função por módulo, a
fonte. Esta fatia tem uma fonte só, a de Pendências: as abertas em que a pessoa
é responsável ou co-responsável, inclusive a Pendência sem Reunião (o lembrete
da Agenda regulatória do Núcleo). O grupo de cada item e a frase do topo são
funções puras; o atraso sai da data, nunca do status gravado.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers import inicio as inicio_router  # noqa: E402
from app.services import inicio  # noqa: E402
from app.services.inicio import fonte_pendencias  # noqa: E402
from app.services.inicio.regras import dias_de_atraso, frase_do_inicio, grupo_do_prazo  # noqa: E402

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
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


def _pendencia(id_acao: str, **campos) -> dict:
    base = {
        "id_acao": id_acao,
        "descricao_acao": f"Ação {id_acao}",
        "responsavel_id": "P_OUTRO",
        "co_responsavel_id": None,
        "id_reuniao": "R1",
        "prazo": (HOJE + timedelta(days=3)).isoformat(),
        "status": "PENDENTE",
        "deleted_at": None,
        "created_at": "2026-11-01T12:00:00+00:00",
    }
    return {**base, **campos}


REUNIAO = {"id_reuniao": "R1", "titulo": "Reunião de Atendimento", "data": "2026-10-28"}
REUNIAO_DO_NUCLEO = {"id_reuniao": "RN", "titulo": "Reunião ordinária do Núcleo", "data": "2026-10-21"}

AURORA = {"id": "P_AURORA", "nome_completo": "Aurora Lima", "access_profile": "regular"}
SECRETARIA = {"id": "P_SEC", "nome_completo": "Selma Souza", "access_profile": "secretaria"}


@pytest.fixture
def nucleo(monkeypatch):
    """O que a pessoa alcança do Núcleo: sem nada, por padrão. Cada teste
    liga o que precisa. A regra de verdade mora em `dependencies` e tem teste
    próprio; aqui ela é a entrada."""
    estado = {"ocultas": [], "recursos": frozenset()}
    monkeypatch.setattr(fonte_pendencias, "reunioes_ocultas", lambda _sb, _me: list(estado["ocultas"]))
    monkeypatch.setattr(fonte_pendencias, "recursos_nsp_da_pessoa", lambda _sb, _me: estado["recursos"])
    return estado


def _rota(monkeypatch, me: dict | None, banco: _Banco, agora: datetime = AGORA):
    async def _participante(_user, _sb, fields=None):
        return me

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: agora)

    import asyncio

    return asyncio.run(inicio_router.get_inicio(current_user={"id": "u1"}, supabase=banco))


def _ids(resposta) -> list[str]:
    return [item.id for item in resposta.itens]


# ═══════════════════════════════════════════════════════════════════════════
# 1. As Pendências abertas de quem é responsável ou co-responsável
# ═══════════════════════════════════════════════════════════════════════════


class TestFonteDePendencias:
    def test_responsavel_ve_a_pendencia_aberta_dele(self, monkeypatch, nucleo):
        banco = _Banco(pendencias=[_pendencia("A001", responsavel_id="P_AURORA")], reunioes=[REUNIAO])

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A001"]
        item = resposta.itens[0]
        assert item.titulo == "Ação A001"
        assert item.area == "Reuniões"
        assert item.origem == "Reunião de Atendimento, de 28/10/2026."
        assert item.destino == "/pendencias/kanban?highlight=A001"

    def test_co_responsavel_ve_a_pendencia_e_sabe_que_divide(self, monkeypatch, nucleo):
        banco = _Banco(
            pendencias=[_pendencia("A002", responsavel_id="P_OUTRO", co_responsavel_id="P_AURORA")],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A002"]
        assert resposta.itens[0].origem == "Reunião de Atendimento, de 28/10/2026. Você é co-responsável."

    def test_so_as_abertas_e_so_as_dela(self, monkeypatch, nucleo):
        banco = _Banco(
            pendencias=[
                _pendencia("A010", responsavel_id="P_AURORA", status="PENDENTE"),
                _pendencia("A011", responsavel_id="P_AURORA", status="EM_PROGRESSO"),
                _pendencia("A012", responsavel_id="P_AURORA", status="ATRASADO"),
                _pendencia("A013", responsavel_id="P_AURORA", status="REPACTUADA"),
                _pendencia("A014", responsavel_id="P_AURORA", status="CONCLUIDO"),
                _pendencia("A015", responsavel_id="P_AURORA", status="CANCELADO"),
                _pendencia("A016", responsavel_id="P_AURORA", deleted_at="2026-11-10T00:00:00+00:00"),
                _pendencia("A017", responsavel_id="P_OUTRO"),
            ],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert sorted(_ids(resposta)) == ["A010", "A011", "A012", "A013"]

    def test_presidencia_ve_o_lembrete_sem_reuniao_que_abre_a_agenda(self, monkeypatch, nucleo):
        nucleo["recursos"] = frozenset({"agenda", "ver_modulo"})
        banco = _Banco(
            pendencias=[
                _pendencia(
                    "A020",
                    responsavel_id="P_AURORA",
                    id_reuniao=None,
                    descricao_acao="Agenda regulatória: relatório trimestral à vigilância",
                )
            ]
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A020"]
        item = resposta.itens[0]
        assert item.titulo == "Agenda regulatória: relatório trimestral à vigilância"
        assert item.area == "Segurança do Paciente"
        assert item.origem == "Lembrete da Agenda regulatória do Núcleo."
        assert item.destino == "/seguranca-do-paciente/agenda"

    def test_quem_nao_alcanca_a_agenda_nao_ve_o_lembrete(self, monkeypatch, nucleo):
        """O lembrete leva o evento do Núcleo (ADR 0095, decisão 4): quem saiu
        da Presidência e não alcança mais a Agenda não o lê pelo Início."""
        banco = _Banco(pendencias=[_pendencia("A021", responsavel_id="P_AURORA", id_reuniao=None)])

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == []

    def test_pendencia_de_reuniao_do_nucleo_fora_do_alcance_nao_aparece(self, monkeypatch, nucleo):
        nucleo["ocultas"] = ["RN"]
        banco = _Banco(
            pendencias=[
                _pendencia("A030", responsavel_id="P_AURORA", id_reuniao="RN"),
                _pendencia("A031", responsavel_id="P_AURORA", id_reuniao="R1"),
            ],
            reunioes=[REUNIAO, REUNIAO_DO_NUCLEO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A031"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. A Secretária não recebe dado nenhum
# ═══════════════════════════════════════════════════════════════════════════


class TestSecretaria:
    def test_secretaria_e_recusada_sem_dado_nenhum(self, monkeypatch, nucleo):
        banco = _Banco(pendencias=[_pendencia("A040", responsavel_id="P_SEC")], reunioes=[REUNIAO])

        with pytest.raises(HTTPException) as recusa:
            _rota(monkeypatch, SECRETARIA, banco)

        assert recusa.value.status_code == 403
        assert "A040" not in str(recusa.value.detail)
