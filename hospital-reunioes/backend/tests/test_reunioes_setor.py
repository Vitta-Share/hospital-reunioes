"""Setor obrigatório na Reunião e a tela de acertos do Super admin (issue #1861).

A Reunião ganha setor de verdade: `reunioes.setor_id` aponta para `setores`
(migration 168), e agendar sem setor é recusado. As Reuniões antigas sem setor
continuam válidas, e o Super admin acerta o setor delas e o dos responsáveis
(Colaboradores) sem setor numa tela própria (decisões 11 e 62 do PRD #1757).

O fake do banco aplica os filtros de verdade (`eq`, `is_`, `in_`, `not_.is_`),
para que a lista de acertos dependa da consulta que a rota faz, e não de uma
resposta pronta.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import _participante_ctx, get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import reunioes as reunioes_router  # noqa: E402
from app.services import audit, email_service, reuniao_email_service  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "168_reunioes_setor_obrigatorio.sql"

BASE: dict[str, Any] = {
    "id": "P_BASE",
    "auth_user_id": "auth-base",
    "email": "base@hsm.com",
    "nome_completo": "Pessoa Base",
    "role": "diretor",
    "ativo": True,
    "is_externo": False,
    "is_super_admin": False,
    "access_profile": "regular",
    "perfil_pop": None,
    "perfil_ouvidoria": None,
    "setor": "Faturamento",
    "setor_id": "S_FAT",
}

FACILITADORA = {**BASE, "id": "P_FACIL", "auth_user_id": "auth-facil", "email": "facil@hsm.com"}

SUPER_ADMIN = {
    **BASE,
    "id": "P_SUPER",
    "auth_user_id": "auth-super",
    "email": "diretoria@hsm.com",
    "is_super_admin": True,
    "access_profile": "super_admin",
}

SECRETARIA = {
    **BASE,
    "id": "P_SECRE",
    "auth_user_id": "auth-secre",
    "email": "secretaria@hsm.com",
    "role": "secretaria",
    "access_profile": "secretaria",
}

# Responsável de pendência que ficou sem setor: é quem a tela de acertos lista.
SEM_SETOR = {
    **BASE,
    "id": "P_SEM",
    "auth_user_id": "auth-sem",
    "email": "sem@hsm.com",
    "nome_completo": "Carla Sem Setor",
    "setor": None,
    "setor_id": None,
}
# Sem setor também, mas não responde por pendência nenhuma.
SEM_SETOR_SEM_PENDENCIA = {**SEM_SETOR, "id": "P_SEM2", "auth_user_id": "auth-sem2", "email": "sem2@hsm.com"}
# Externo sem setor que é responsável: é só nome, não tem setor a acertar.
EXTERNO = {
    **SEM_SETOR,
    "id": "P_EXT",
    "auth_user_id": None,
    "email": None,
    "is_externo": True,
    "ativo": False,
    "access_profile": None,
}

SETORES = [
    {"id": "S_FAT", "nome": "Faturamento", "ativo": True},
    {"id": "S_UTI", "nome": "UTI Adulto", "ativo": True},
    {"id": "S_VELHO", "nome": "Setor Arquivado", "ativo": False},
]


@pytest.fixture(autouse=True)
def _reset_estado_global(monkeypatch):
    limiter._storage.reset()
    _participante_ctx.set(None)
    monkeypatch.setattr(reuniao_email_service, "enviar_convites", MagicMock(return_value=None))
    monkeypatch.setattr(email_service, "send_meeting_scheduled_notification", MagicMock(return_value=None))
    monkeypatch.setattr(audit, "log_action", MagicMock(return_value=None))
    yield
    limiter._storage.reset()
    _participante_ctx.set(None)


class _Not:
    def __init__(self, query: _Query):
        self._query = query

    def is_(self, col, valor):
        self._query._filtros.append(lambda r: r.get(col) is not None if valor == "null" else True)
        return self._query


class _Query:
    def __init__(self, tabela: list):
        self._tabela = tabela
        self._op = "select"
        self._payload: Any = None
        self._filtros: list = []
        self._colunas: list[str] | None = None

    @property
    def not_(self):
        return _Not(self)

    def select(self, colunas: str = "*", *_a, **_kw):
        self._op = "select"
        if colunas.strip() != "*":
            self._colunas = [c.strip() for c in colunas.split(",")]
        return self

    def insert(self, payload, **_kw):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, col, valor):
        self._filtros.append(lambda r: r.get(col) == valor)
        return self

    def is_(self, col, valor):
        self._filtros.append(lambda r: r.get(col) is None if valor == "null" else True)
        return self

    def in_(self, col, valores):
        valores = list(valores)
        self._filtros.append(lambda r: r.get(col) in valores)
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def execute(self):
        if self._op == "insert":
            novas = self._payload if isinstance(self._payload, list) else [self._payload]
            self._tabela.extend(dict(n) for n in novas)
            return type("_R", (), {"data": [dict(n) for n in novas]})()
        casadas = [r for r in self._tabela if all(f(r) for f in self._filtros)]
        if self._op == "update":
            for row in casadas:
                row.update(self._payload or {})
        if self._colunas is not None:
            casadas = [{c: r[c] for c in self._colunas if c in r} for r in casadas]
        return type("_R", (), {"data": [dict(r) for r in casadas]})()


class _Supabase:
    def __init__(self, participantes: list[dict], reunioes: list[dict] | None = None, pendencias=None):
        self.tabelas: dict[str, list] = {
            "participantes": [dict(p) for p in participantes],
            "setores": [dict(s) for s in SETORES],
            "reunioes": [dict(r) for r in (reunioes or [])],
            "reuniao_participantes": [],
            "pendencias": [dict(p) for p in (pendencias or [])],
        }

    def table(self, nome: str):
        return _Query(self.tabelas.setdefault(nome, []))

    def reuniao(self, id_reuniao: str) -> dict:
        return next(r for r in self.tabelas["reunioes"] if r["id_reuniao"] == id_reuniao)

    def participante(self, pid: str) -> dict:
        return next(p for p in self.tabelas["participantes"] if p["id"] == pid)


def _cliente(sb: _Supabase, logado_como: dict) -> TestClient:
    from app.routers.admin import acertos_de_setor

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(reunioes_router.router, prefix="/api")
    app.include_router(acertos_de_setor.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: sb

    async def _fake_user() -> dict:
        return {"id": logado_como["auth_user_id"], "email": logado_como["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


def _agendar(sb: _Supabase, ator: dict, **extra):
    corpo = {"titulo": "Reuniao nova", "data": "2026-11-20", "facilitador_id": FACILITADORA["id"]}
    corpo.update(extra)
    return _cliente(sb, ator).post("/api/reunioes/agendar", json=corpo)


# ─── Critério 1 e 5: agendar sem setor é recusado; a Secretária escolhe o setor ─


class TestAgendarExigeSetor:
    @pytest.mark.parametrize("ator", [SECRETARIA, FACILITADORA], ids=["secretaria", "facilitador"])
    def test_agendar_sem_setor_e_recusado_sem_criar_a_reuniao(self, ator):
        sb = _Supabase([ator, FACILITADORA])

        resp = _agendar(sb, ator)

        assert resp.status_code == 422, resp.text
        assert "setor" in resp.json()["detail"].lower()
        assert sb.tabelas["reunioes"] == [], "a recusa veio tarde: a reunião já tinha nascido"

    @pytest.mark.parametrize("setor", ["Setor Que Nao Existe", "Setor Arquivado", "   "])
    def test_setor_fora_da_lista_ativa_e_recusado(self, setor):
        sb = _Supabase([SECRETARIA, FACILITADORA])

        resp = _agendar(sb, SECRETARIA, setor=setor)

        assert resp.status_code == 422, resp.text
        assert sb.tabelas["reunioes"] == []

    def test_a_secretaria_agenda_com_o_setor_escolhido(self):
        sb = _Supabase([SECRETARIA, FACILITADORA])

        resp = _agendar(sb, SECRETARIA, setor="uti adulto ")

        assert resp.status_code == 200, resp.text
        [nova] = sb.tabelas["reunioes"]
        assert nova["setor_id"] == "S_UTI"
        assert nova["setor"] == "UTI Adulto", "a TEXT fica em sincronia com o nome canônico"


# ─── Critério 2: a migration liga o setor sem quebrar as antigas ──────────────


class TestMigration:
    def _sql(self) -> str:
        return MIGRATION.read_text(encoding="utf-8")

    def test_a_coluna_aponta_para_a_tabela_de_setores(self):
        assert re.search(
            r"ALTER TABLE reunioes\s+ADD COLUMN IF NOT EXISTS setor_id UUID REFERENCES setores\(id\)",
            self._sql(),
        )

    def test_as_reunioes_antigas_sem_setor_continuam_validas(self):
        """Nulo no banco: a obrigação é do agendamento, não da coluna."""
        sql = self._sql()
        [coluna] = re.findall(r"ADD COLUMN IF NOT EXISTS setor_id[^;,]*", sql)
        assert "NOT NULL" not in coluna.upper()
        assert "ON DELETE SET NULL" in coluna
        assert not re.search(r"ALTER COLUMN\s+setor_id\s+SET\s+NOT\s+NULL", sql, re.IGNORECASE)


# ─── Critério 3: só o Super admin abre a tela de acertos ──────────────────────

REUNIAO_SEM_SETOR = {
    "id_reuniao": "RD_SEM",
    "titulo": "Reunião antiga",
    "data": "2026-03-10",
    "tipo": "Gerencial",
    "setor": None,
    "setor_id": None,
    "deleted_at": None,
    "colegiado_id": None,
}
REUNIAO_COM_SETOR = {**REUNIAO_SEM_SETOR, "id_reuniao": "RD_COM", "setor": "Faturamento", "setor_id": "S_FAT"}
REUNIAO_EXCLUIDA = {**REUNIAO_SEM_SETOR, "id_reuniao": "RD_DEL", "deleted_at": "2026-04-01T00:00:00Z"}
# A reunião do Núcleo é sigilosa até para o Super admin (issue #1772).
REUNIAO_DO_NUCLEO = {**REUNIAO_SEM_SETOR, "id_reuniao": "RD_NSP", "colegiado_id": "C_NUCLEO"}

PENDENCIAS = [
    {"id_acao": "A1", "responsavel_id": SEM_SETOR["id"]},
    {"id_acao": "A2", "responsavel_id": SEM_SETOR["id"]},
    {"id_acao": "A3", "responsavel_id": FACILITADORA["id"]},
    {"id_acao": "A4", "responsavel_id": EXTERNO["id"]},
    {"id_acao": "A5", "responsavel_id": None},
]


def _banco_de_acertos() -> _Supabase:
    return _Supabase(
        [SUPER_ADMIN, SECRETARIA, FACILITADORA, SEM_SETOR, SEM_SETOR_SEM_PENDENCIA, EXTERNO],
        reunioes=[REUNIAO_SEM_SETOR, REUNIAO_COM_SETOR, REUNIAO_EXCLUIDA, REUNIAO_DO_NUCLEO],
        pendencias=PENDENCIAS,
    )


def _acertos(sb: _Supabase, ator: dict):
    return _cliente(sb, ator).get("/api/admin/acertos-de-setor")


class TestSoOSuperAdmin:
    @pytest.mark.parametrize("ator", [SECRETARIA, FACILITADORA], ids=["secretaria", "regular"])
    def test_outros_perfis_recebem_403_na_lista(self, ator):
        assert _acertos(_banco_de_acertos(), ator).status_code == 403

    @pytest.mark.parametrize("ator", [SECRETARIA, FACILITADORA], ids=["secretaria", "regular"])
    def test_outros_perfis_recebem_403_ao_preencher_sem_mudar_nada(self, ator):
        sb = _banco_de_acertos()
        cliente = _cliente(sb, ator)

        r1 = cliente.patch("/api/admin/acertos-de-setor/reunioes/RD_SEM", json={"setor": "UTI Adulto"})
        r2 = cliente.patch(f"/api/admin/acertos-de-setor/responsaveis/{SEM_SETOR['id']}", json={"setor": "UTI Adulto"})

        assert (r1.status_code, r2.status_code) == (403, 403)
        assert sb.reuniao("RD_SEM")["setor_id"] is None
        assert sb.participante(SEM_SETOR["id"])["setor_id"] is None

    def test_o_super_admin_abre_a_lista(self):
        resp = _acertos(_banco_de_acertos(), SUPER_ADMIN)

        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert [r["id_reuniao"] for r in corpo["reunioes"]] == ["RD_SEM"]
        assert [p["id"] for p in corpo["responsaveis"]] == [SEM_SETOR["id"]]


# ─── Critério 4: preencher o setor tira da lista ──────────────────────────────


class TestPreencherTiraDaLista:
    def test_preencher_o_setor_da_reuniao_tira_ela_da_lista(self):
        sb = _banco_de_acertos()
        cliente = _cliente(sb, SUPER_ADMIN)

        resp = cliente.patch("/api/admin/acertos-de-setor/reunioes/RD_SEM", json={"setor": "UTI Adulto"})

        assert resp.status_code == 200, resp.text
        assert sb.reuniao("RD_SEM")["setor_id"] == "S_UTI"
        assert sb.reuniao("RD_SEM")["setor"] == "UTI Adulto"
        _participante_ctx.set(None)
        assert cliente.get("/api/admin/acertos-de-setor").json()["reunioes"] == []

    def test_preencher_o_setor_do_responsavel_tira_ele_da_lista(self):
        sb = _banco_de_acertos()
        cliente = _cliente(sb, SUPER_ADMIN)

        resp = cliente.patch(
            f"/api/admin/acertos-de-setor/responsaveis/{SEM_SETOR['id']}", json={"setor": "Faturamento"}
        )

        assert resp.status_code == 200, resp.text
        assert sb.participante(SEM_SETOR["id"])["setor_id"] == "S_FAT"
        assert sb.participante(SEM_SETOR["id"])["setor"] == "Faturamento"
        _participante_ctx.set(None)
        assert cliente.get("/api/admin/acertos-de-setor").json()["responsaveis"] == []

    def test_setor_fora_da_lista_ativa_nao_grava(self):
        sb = _banco_de_acertos()

        resp = _cliente(sb, SUPER_ADMIN).patch(
            "/api/admin/acertos-de-setor/reunioes/RD_SEM", json={"setor": "Setor Arquivado"}
        )

        assert resp.status_code == 422, resp.text
        assert sb.reuniao("RD_SEM")["setor_id"] is None

    def test_a_reuniao_do_nucleo_nao_se_acerta_por_aqui(self):
        sb = _banco_de_acertos()

        resp = _cliente(sb, SUPER_ADMIN).patch(
            "/api/admin/acertos-de-setor/reunioes/RD_NSP", json={"setor": "UTI Adulto"}
        )

        assert resp.status_code == 404, resp.text
        assert sb.reuniao("RD_NSP")["setor_id"] is None


# ─── Issue #1877: as Pendências sem prazo que não viraram Rotina ──────────────

ABERTA_SEM_PRAZO = {
    "id_acao": "A10",
    "id_reuniao": "RD_COM",
    "descricao_acao": "Comprar luvas",
    "responsavel_nome": "Carla Sem Setor",
    "responsavel_id": SEM_SETOR["id"],
    "status": "PENDENTE",
    "prazo": None,
    "deleted_at": None,
}
PENDENCIAS_SEM_PRAZO = [
    ABERTA_SEM_PRAZO,
    {**ABERTA_SEM_PRAZO, "id_acao": "A11", "status": "EM_PROGRESSO", "descricao_acao": "Treinar equipe"},
    # Com prazo, concluída, cancelada (a que virou Rotina) ou apagada: nada a acertar.
    {**ABERTA_SEM_PRAZO, "id_acao": "A12", "prazo": "2026-12-01"},
    {**ABERTA_SEM_PRAZO, "id_acao": "A13", "status": "CONCLUIDO"},
    {**ABERTA_SEM_PRAZO, "id_acao": "A14", "status": "CANCELADO"},
    {**ABERTA_SEM_PRAZO, "id_acao": "A15", "deleted_at": "2026-10-01T00:00:00Z"},
    # A da Reunião do Núcleo é sigilosa até para o Super admin; a da Reunião
    # excluída não aparece em lugar nenhum; o lembrete do Núcleo não tem Reunião.
    {**ABERTA_SEM_PRAZO, "id_acao": "A16", "id_reuniao": "RD_NSP"},
    {**ABERTA_SEM_PRAZO, "id_acao": "A17", "id_reuniao": "RD_DEL"},
    {**ABERTA_SEM_PRAZO, "id_acao": "A18", "id_reuniao": None},
]


class TestPendenciasSemPrazo:
    def test_as_pendencias_abertas_sem_prazo_entram_na_tela_de_acertos(self):
        sb = _Supabase(
            [SUPER_ADMIN, SEM_SETOR],
            reunioes=[REUNIAO_SEM_SETOR, REUNIAO_COM_SETOR, REUNIAO_EXCLUIDA, REUNIAO_DO_NUCLEO],
            pendencias=PENDENCIAS_SEM_PRAZO,
        )

        resp = _acertos(sb, SUPER_ADMIN)

        assert resp.status_code == 200, resp.text
        lista = resp.json()["pendencias_sem_prazo"]
        assert [(p["id_acao"], p["descricao_acao"], p["responsavel_nome"], p["reuniao_titulo"]) for p in lista] == [
            ("A10", "Comprar luvas", "Carla Sem Setor", "Reunião antiga"),
            ("A11", "Treinar equipe", "Carla Sem Setor", "Reunião antiga"),
        ]

    def test_sem_pendencia_sem_prazo_a_lista_vem_vazia(self):
        resp = _acertos(_banco_de_acertos(), SUPER_ADMIN)

        assert resp.json()["pendencias_sem_prazo"] == []
