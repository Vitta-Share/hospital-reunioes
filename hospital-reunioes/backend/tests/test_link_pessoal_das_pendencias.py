"""O link pessoal das Pendências (issue #1878; ADR 0098, decisão 8; Refino 20
e decisões 26 e 48 do PRD #1757).

Quem nunca entrou no app recebe, no e-mail de segunda, um link com token para
atualizar as próprias Pendências sem senha. O token só alcança as Pendências
da pessoa dona dele, vence, pode ser revogado, e toda ação por ele pede
anotação e grava um evento no histórico, pelo mesmo módulo de ações da tela.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_supabase_client
from app.limiter import limiter
from app.main import app
from app.routers import pendencias_link_pessoal as rota
from app.services import link_pessoal

HOJE = date(2026, 11, 23)
AGORA = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.UTC)
AMANHA = (HOJE + timedelta(days=1)).isoformat()
SEMANA_QUE_VEM = (HOJE + timedelta(days=7)).isoformat()


# ─── O banco de mentira ──────────────────────────────────────────────────────


@dataclass
class _Result:
    data: list


class _Negacao:
    def __init__(self, consulta):
        self._consulta = consulta

    def is_(self, coluna, valor):
        assert valor == "null"
        self._consulta._filtros.append(lambda linha: linha.get(coluna) is not None)
        return self._consulta


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []
        self._inserir: dict | None = None
        self._atualizar: dict | None = None

    @property
    def not_(self):
        return _Negacao(self)

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) == str(valor))
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

    def range(self, *_a, **_kw):
        return self

    def insert(self, linha: dict):
        self._inserir = linha
        return self

    def update(self, valores: dict):
        self._atualizar = valores
        return self

    def execute(self):
        if self._inserir is not None:
            linha = {"id": f"L{len(self._linhas) + 1}", "revogado_em": None, **self._inserir}
            self._linhas.append(linha)
            return _Result([dict(linha)])
        achadas = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._atualizar is not None:
            for linha in achadas:
                linha.update(self._atualizar)
        return _Result([dict(linha) for linha in achadas])


@dataclass
class _Banco:
    participantes: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    pendencias: list = field(default_factory=list)
    pendencia_historico: list = field(default_factory=list)
    pendencias_links_pessoais: list = field(default_factory=list)
    colegiados: list = field(default_factory=list)
    chamadas: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))

    def rpc(self, nome, params):
        """A `registrar_acao_da_pendencia` de mentira: aplica o que recebe e
        grava o evento (a de verdade está em `test_pendencia_historico_banco`)."""
        self.chamadas.append((nome, params))
        banco = self

        class _Exec:
            def execute(self_inner):  # noqa: N805
                assert nome == "registrar_acao_da_pendencia"
                p = next(x for x in banco.pendencias if x["id_acao"] == params["p_id_acao"])
                p["status"] = params["p_status_novo"]
                if params["p_prazo_novo"]:
                    p["prazo"] = params["p_prazo_novo"]
                banco.pendencia_historico.append(
                    {
                        "id_acao": params["p_id_acao"],
                        "comando": params["p_comando"],
                        "anotacao": params["p_anotacao"],
                        "autor_id": params["p_autor_id"],
                        "autor_nome": params["p_autor_nome"],
                    }
                )
                return _Result([len(banco.pendencia_historico)])

        return _Exec()


def _pessoa(pid: str, nome: str, *, ativo=True) -> dict:
    return {"id": pid, "nome_completo": nome, "email": f"{pid.lower()}@hsm.test", "ativo": ativo}


def _pendencia(id_acao, descricao, responsavel_id, *, co=None, status="PENDENTE", prazo=AMANHA, id_reuniao="R1"):
    return {
        "id_acao": id_acao,
        "id_reuniao": id_reuniao,
        "descricao_acao": descricao,
        "responsavel_id": responsavel_id,
        "co_responsavel_id": co,
        "responsavel_nome": f"Nome {responsavel_id}",
        "status": status,
        "prazo": prazo,
        "deleted_at": None,
    }


def _banco() -> _Banco:
    """Bruno nunca entrou no app; Carla é outra responsável da mesma Reunião."""
    return _Banco(
        participantes=[_pessoa("P_BRUNO", "Bruno Reis"), _pessoa("P_CARLA", "Carla Dias")],
        reunioes=[{"id_reuniao": "R1", "titulo": "Reunião da UTI", "facilitador_id": "P_FABIO", "deleted_at": None}],
        pendencias=[
            _pendencia("A1", "Trocar o monitor do leito 4", "P_BRUNO"),
            _pendencia("A2", "Revisar a escala", "P_CARLA", co="P_BRUNO"),
            _pendencia("A3", "Comprar luvas", "P_CARLA"),
        ],
    )


@pytest.fixture
def portal(monkeypatch):
    banco = _banco()
    estado = {"agora": AGORA}
    monkeypatch.setattr(rota, "agora_utc", lambda: estado["agora"])
    monkeypatch.setattr(rota, "hoje_em_brasilia", lambda: HOJE)
    app.dependency_overrides[get_supabase_client] = lambda: banco
    limiter._storage.reset()
    try:
        yield TestClient(app), banco, estado
    finally:
        app.dependency_overrides.pop(get_supabase_client, None)
        limiter._storage.reset()


def _token(banco, pid="P_BRUNO") -> str:
    return link_pessoal.emitir(banco, pid, AGORA)


# ─── 1. O token só alcança as Pendências da pessoa dona dele ─────────────────


def test_o_link_mostra_so_as_pendencias_abertas_da_pessoa_dona_dele(portal):
    cliente, banco, _ = portal
    banco.pendencias.append(_pendencia("A4", "Pendência já concluída", "P_BRUNO", status="CONCLUIDO"))
    token = _token(banco)

    resposta = cliente.get(f"/api/minhas-pendencias/{token}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["pessoa"] == "Bruno Reis"
    # A1 como responsável e A2 como co-responsável; a A3 é só da Carla.
    assert sorted(p["id_acao"] for p in corpo["pendencias"]) == ["A1", "A2"]
    a1 = next(p for p in corpo["pendencias"] if p["id_acao"] == "A1")
    assert a1["reuniao"] == "Reunião da UTI"
    assert a1["acoes"] == ["iniciar", "anotar", "concluir", "repactuar"]


def test_o_link_nao_age_na_pendencia_de_outra_pessoa(portal):
    cliente, banco, _ = portal
    token = _token(banco)

    resposta = cliente.post(
        f"/api/minhas-pendencias/{token}/pendencias/A3/acoes",
        json={"comando": "concluir", "anotacao": "Feito."},
    )

    assert resposta.status_code == 404
    assert banco.chamadas == []
    assert next(p for p in banco.pendencias if p["id_acao"] == "A3")["status"] == "PENDENTE"
