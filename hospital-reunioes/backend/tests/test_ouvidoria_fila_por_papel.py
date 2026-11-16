"""A fila da Ouvidoria recortada pelo papel de quem pede (issue #1884, ADR 0099).

O responsável do setor recebe só os casos acionados para os setores em que
está vigente, com o índice de quem está fora da Ouvidoria (sem relato e sem
identificação de quem manifestou), inclusive o caso com sigilo reforçado do
setor dele. Quem não tem papel nenhum recebe 403.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import RequestContextMiddleware  # noqa: E402
from app.routers import ouvidoria as ouvidoria_router  # noqa: E402

TITULAR_DA_RECEPCAO = {
    "id": "P10",
    "nome_completo": "Dr. Bruno",
    "email": "bruno@hsm.test",
    "access_profile": "regular",
    "perfil_ouvidoria": None,
}
MEDICO_SEM_SETOR = {
    "id": "P11",
    "nome_completo": "Dra. Clara",
    "email": "clara@hsm.test",
    "access_profile": "regular",
    "perfil_ouvidoria": None,
}

CADASTRO = [
    {
        "id": "R1",
        "setor": "Recepção",
        "papel": "titular",
        "email": "Bruno@HSM.test",
        "vigencia_inicio": "2026-01-01",
        "vigencia_fim": None,
    },
    {
        "id": "R2",
        "setor": "UTI",
        "papel": "titular",
        "email": "outro@hsm.test",
        "vigencia_inicio": "2026-01-01",
        "vigencia_fim": None,
    },
]

RELATO = "Fui maltratado pelo porteiro João na entrada."


def _caso(numero: int, setor: str, status: str = "aguardando_area", **extra) -> dict:
    return {
        "id": f"uuid-{numero}",
        "numero": numero,
        "protocolo": f"2026-{numero:04d}",
        "data_abertura": "2026-11-10",
        "prazo_resposta": None,
        "status": status,
        "categoria": "Atendimento",
        "setor": setor,
        "resumo": RELATO,
        "assunto": "Atendimento na portaria",
        "anonimo": False,
        "conversa_id": None,
        "sigilo_reforcado": False,
        "arquivada_em": None,
        **extra,
    }


class _Query:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filtros: list = []
        self._ordem = None
        self._negar = False

    @property
    def not_(self):
        self._negar = True
        return self

    def select(self, *_a, **_kw):
        return self

    def _filtrar(self, teste):
        negar, self._negar = self._negar, False
        self._filtros.append((lambda r: not teste(r)) if negar else teste)
        return self

    def eq(self, col, valor):
        return self._filtrar(lambda r: r.get(col) == valor)

    def is_(self, col, valor):
        alvo = None if valor in ("null", None) else valor
        return self._filtrar(lambda r: r.get(col) == alvo)

    def in_(self, col, valores):
        valores = list(valores)
        return self._filtrar(lambda r: r.get(col) in valores)

    def order(self, col, desc=False):
        self._ordem = (col, desc)
        return self

    def range(self, inicio, fim):
        self._janela = (inicio, fim)
        return self

    def execute(self):
        linhas = [dict(r) for r in self._rows if all(f(r) for f in self._filtros)]
        if self._ordem:
            col, desc = self._ordem
            linhas.sort(key=lambda r: str(r.get(col)), reverse=desc)
        inicio, fim = getattr(self, "_janela", None) or (0, len(linhas))
        return type("R", (), {"data": linhas[inicio : fim + 1]})()


class _Supabase:
    def __init__(self, casos: list[dict], cadastro: list[dict]):
        self.tabelas = {"ouvidoria_protocolos": casos, "ouvidoria_setor_responsaveis": cadastro}

    def table(self, nome: str):
        assert nome in self.tabelas, f"Tabela inesperada: {nome}"
        return _Query(self.tabelas[nome])

    def rpc(self, nome: str, _params: dict):
        raise AssertionError(f"RPC inesperada para o responsável do setor: {nome}")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _cliente(monkeypatch, participante: dict | None, casos: list[dict]) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(ouvidoria_router.router, prefix="/api")
    supabase = _Supabase(casos, CADASTRO)

    async def _participante(_user, _sb, fields=None):
        return participante

    monkeypatch.setattr(ouvidoria_router, "get_participante_for_user", _participante)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "email": "u@hsm.test"}
    app.dependency_overrides[get_supabase_client] = lambda: supabase
    return TestClient(app)


def test_titular_recebe_so_os_casos_do_setor_dele(monkeypatch):
    casos = [_caso(1, "Recepção"), _caso(2, "UTI"), _caso(3, "Recepção", status="respondido")]
    cliente = _cliente(monkeypatch, TITULAR_DA_RECEPCAO, casos)

    r = cliente.get("/api/ouvidoria/protocolos")

    assert r.status_code == 200
    assert sorted(p["protocolo"] for p in r.json()["protocolos"]) == ["2026-0001", "2026-0003"]


@pytest.mark.parametrize("status", ["novo", "em_classificacao"])
def test_caso_ainda_na_classificacao_nao_chega_ao_responsavel(monkeypatch, status):
    cliente = _cliente(monkeypatch, TITULAR_DA_RECEPCAO, [_caso(4, "Recepção", status=status)])

    r = cliente.get("/api/ouvidoria/protocolos")

    assert r.status_code == 200
    assert r.json()["protocolos"] == []


def test_caso_sigiloso_do_setor_chega_sem_relato_e_sem_identificacao(monkeypatch):
    sigiloso = _caso(5, "Recepção", sigilo_reforcado=True, manifestante_nome="Maria da Silva")
    cliente = _cliente(monkeypatch, TITULAR_DA_RECEPCAO, [sigiloso])

    r = cliente.get("/api/ouvidoria/protocolos")

    assert r.status_code == 200
    [linha] = r.json()["protocolos"]
    assert linha["protocolo"] == "2026-0005"
    assert linha["sigilo_reforcado"] is True
    corpo = r.text
    assert RELATO not in corpo
    assert "Maria da Silva" not in corpo
    assert "Atendimento na portaria" not in corpo
    assert {"resumo", "assunto", "anonimo", "manifestante_nome", "relato_integral"}.isdisjoint(linha)


def test_responsavel_sem_caso_recebe_lista_vazia(monkeypatch):
    cliente = _cliente(monkeypatch, TITULAR_DA_RECEPCAO, [_caso(6, "UTI")])

    r = cliente.get("/api/ouvidoria/protocolos")

    assert r.status_code == 200
    assert r.json()["protocolos"] == []


def test_quem_nao_tem_papel_na_ouvidoria_recebe_403(monkeypatch):
    cliente = _cliente(monkeypatch, MEDICO_SEM_SETOR, [_caso(7, "Recepção")])

    r = cliente.get("/api/ouvidoria/protocolos")

    assert r.status_code == 403


def test_responsavel_nao_le_o_arquivo(monkeypatch):
    cliente = _cliente(monkeypatch, TITULAR_DA_RECEPCAO, [_caso(8, "Recepção")])

    r = cliente.get("/api/ouvidoria/protocolos?arquivados=sim")

    assert r.status_code == 403
