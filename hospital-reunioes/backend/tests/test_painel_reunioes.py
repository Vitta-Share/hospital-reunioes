"""O painel de Reuniões calculado no servidor (issue #1868, ADR 0098 decisão 10,
emendada pela ADR 0104).

O endpoint lê a base inteira, sem o corte de 200 linhas que o front fazia nem o
de 1000 linhas do PostgREST, e devolve os cards já recortados para quem pede:
o responsável conta as dele, o Facilitador conta as Reuniões e as Pendências
dele, e o Super admin conta o hospital inteiro. A Secretária não recebe dado de
Pendência. O alerta de 48 horas e a Minha Fila não moram aqui: estão no Início.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import (  # noqa: E402
    get_current_user,
    get_supabase_client,
    require_acesso_reunioes,
)
from app.main import app  # noqa: E402
from app.routers import pendencias as pendencias_router  # noqa: E402
from app.services import painel_reunioes  # noqa: E402
from app.services.pendencias_recorte import recorte_das_pendencias  # noqa: E402

HOJE = date(2026, 11, 18)
AGORA = datetime(2026, 11, 18, 13, 0, tzinfo=UTC)
ONTEM = (HOJE - timedelta(days=1)).isoformat()
EM_DOIS_DIAS = (HOJE + timedelta(days=2)).isoformat()
EM_UM_MES = (HOJE + timedelta(days=30)).isoformat()

# O teto de linhas por resposta do PostgREST (`max_rows` no config.toml).
TETO_DO_POSTGREST = 1000


# ─── O banco de mentira, com o teto do PostgREST ─────────────────────────────


@dataclass
class _Result:
    data: list
    count: int | None = None


def _condicao(expr: str):
    """Uma condição do `or` do PostgREST: `col.eq.v`, `col.in.(a,b)`,
    `col.is.null` e `col.not.in.(a,b)`."""
    coluna, resto = expr.split(".", 1)
    if resto == "is.null":
        return lambda linha: linha.get(coluna) is None
    if resto.startswith("eq."):
        valor = resto[3:]
        return lambda linha: linha.get(coluna) == valor
    if resto.startswith("in.("):
        valores = set(resto[4:-1].split(","))
        return lambda linha: linha.get(coluna) in valores
    if resto.startswith("not.in.("):
        valores = set(resto[8:-1].split(","))
        return lambda linha: linha.get(coluna) not in valores
    raise AssertionError(f"condição não suportada: {expr}")


def _partes_do_or(filtro: str) -> list[str]:
    partes, atual, nivel = [], "", 0
    for ch in filtro:
        if ch == "," and nivel == 0:
            partes.append(atual)
            atual = ""
            continue
        nivel += ch == "("
        nivel -= ch == ")"
        atual += ch
    partes.append(atual)
    return partes


class _Negacao:
    def __init__(self, consulta):
        self._consulta = consulta

    def is_(self, coluna, valor):
        assert valor == "null"
        self._consulta._filtros.append(lambda linha: linha.get(coluna) is not None)
        return self._consulta

    def in_(self, coluna, valores):
        valores = set(valores)
        self._consulta._filtros.append(lambda linha: linha.get(coluna) not in valores)
        return self._consulta


class _Consulta:
    def __init__(self, banco: _Banco, linhas: list[dict]):
        self._banco = banco
        self._linhas = linhas
        self._filtros: list = []
        self._recorte: tuple[int, int] | None = None

    @property
    def not_(self):
        return _Negacao(self)

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

    def or_(self, filtro):
        condicoes = [_condicao(p) for p in _partes_do_or(filtro)]
        self._filtros.append(lambda linha: any(c(linha) for c in condicoes))
        return self

    def order(self, *_a, **_kw):
        return self

    def range(self, inicio, fim):
        self._recorte = (inicio, fim)
        return self

    def execute(self):
        linhas = [dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._recorte is not None:
            inicio, fim = self._recorte
            linhas = linhas[inicio : fim + 1]
        # O PostgREST corta toda resposta no teto, com 200 e sem aviso.
        return _Result(linhas[:TETO_DO_POSTGREST])


@dataclass
class _Banco:
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    participantes: list = field(default_factory=list)
    pendencia_historico: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(self, getattr(self, nome))


def _pendencia(id_acao, responsavel_id, *, id_reuniao="R1", status="PENDENTE", prazo=EM_UM_MES, co=None) -> dict:
    return {
        "id_acao": id_acao,
        "responsavel_id": responsavel_id,
        "co_responsavel_id": co,
        "id_reuniao": id_reuniao,
        "status": status,
        "prazo": prazo,
        "deleted_at": None,
    }


def _reuniao(id_reuniao, facilitador_id, status_ata, *, updated_at=None, setor=None) -> dict:
    return {
        "id_reuniao": id_reuniao,
        "data": "2026-11-10",
        "tipo": "Gerencial",
        "objetivo": f"Objetivo {id_reuniao}",
        "facilitador_id": facilitador_id,
        "status_ata": status_ata,
        "updated_at": updated_at or AGORA.isoformat(),
        "setor": setor,
        "deleted_at": None,
    }


PESSOAS = {
    "ana": {"id": "P_ANA", "access_profile": "regular"},
    "fabio": {"id": "P_FABIO", "access_profile": "regular"},
    "admin": {"id": "P_ADMIN", "access_profile": "super_admin"},
    "selma": {"id": "P_SELMA", "access_profile": "secretaria"},
}


@pytest.fixture
def painel(monkeypatch):
    estado: dict = {"quem": "admin", "banco": _Banco()}

    async def _participante(_user, _sb, fields=None):
        return PESSOAS[estado["quem"]]

    async def _recorte(_user, sb):
        # O recorte pelo vínculo (issue #1863), com a função pura de verdade.
        me = PESSOAS[estado["quem"]]
        facilitadas = [r["id_reuniao"] for r in sb.reunioes if r["facilitador_id"] == me["id"]]
        return recorte_das_pendencias(
            me["id"],
            super_admin=me["access_profile"] == "super_admin",
            facilitadas=facilitadas,
            do_nucleo=[],
            ocultas=[],
        )

    monkeypatch.setattr(pendencias_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(pendencias_router, "get_recorte_das_pendencias", _recorte)
    monkeypatch.setattr(pendencias_router, "hoje_em_brasilia", lambda: HOJE)
    monkeypatch.setattr(painel_reunioes, "agora_utc", lambda: AGORA)

    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "email": "x@x"}
    app.dependency_overrides[get_supabase_client] = lambda: estado["banco"]
    app.dependency_overrides[require_acesso_reunioes] = lambda: None
    client = TestClient(app)

    def pedir(quem: str, **params):
        estado["quem"] = quem
        return client.get("/api/pendencias/painel", params=params)

    try:
        yield pedir, estado
    finally:
        app.dependency_overrides.clear()


# ─── 1. A base inteira ───────────────────────────────────────────────────────


def test_painel_conta_todas_as_pendencias_mesmo_com_mais_de_mil_linhas(painel):
    pedir, estado = painel
    atrasadas = [_pendencia(f"A{i:04d}", "P_ANA", prazo=ONTEM) for i in range(1100)]
    no_prazo = [_pendencia(f"B{i:04d}", "P_ANA") for i in range(400)]
    estado["banco"] = _Banco(pendencias=atrasadas + no_prazo, participantes=[{"id": "P_ANA", "setor": "UTI"}])

    corpo = pedir("admin").json()

    assert corpo["cards"]["atrasadas"] == 1100
    assert corpo["cards"]["ativas"] == 1500
    assert corpo["situacoes"]["pendente"] == 400
    # 400 em dia de 1500 abertas.
    assert corpo["cards"]["conformidade"] == 27


# ─── 2. O recorte de cada papel ──────────────────────────────────────────────


def _banco_de_papeis() -> _Banco:
    """Fábio facilita a R1 (em assinatura) e a R3 (parada); a R2, em
    assinatura, é de outra pessoa. Ana é responsável na R1 e co-responsável
    na R2; Bruno é responsável na R1 e na R2."""
    return _Banco(
        pendencias=[
            _pendencia("A1", "P_ANA", id_reuniao="R1"),
            _pendencia("A2", "P_BRUNO", id_reuniao="R1", prazo=ONTEM),
            _pendencia("A3", "P_BRUNO", id_reuniao="R2", prazo=EM_DOIS_DIAS),
            _pendencia("A4", "P_BRUNO", id_reuniao="R2", co="P_ANA", status="EM_PROGRESSO", prazo=ONTEM),
        ],
        reunioes=[
            _reuniao("R1", "P_FABIO", "AGUARDANDO_ASSINATURA"),
            _reuniao("R2", "P_OUTRO", "AGUARDANDO_ASSINATURA"),
            _reuniao("R3", "P_FABIO", "AGUARDANDO_VALIDACAO", updated_at=(AGORA - timedelta(days=10)).isoformat()),
            # Em validação há 2 dias: ainda não está parada.
            _reuniao("R4", "P_FABIO", "AGUARDANDO_VALIDACAO", updated_at=(AGORA - timedelta(days=2)).isoformat()),
        ],
        participantes=[{"id": "P_ANA", "setor": "UTI"}, {"id": "P_BRUNO", "setor": "Farmácia"}],
    )


def test_responsavel_conta_so_as_pendencias_dele_e_nenhuma_ata(painel):
    pedir, estado = painel
    estado["banco"] = _banco_de_papeis()

    corpo = pedir("ana").json()

    # A1 (responsável, no prazo) e A4 (co-responsável, atrasada).
    assert corpo["cards"]["ativas"] == 2
    assert corpo["cards"]["atrasadas"] == 1
    assert corpo["cards"]["aguardam_assinatura"] == 0
    assert corpo["cards"]["atas_paradas"] == 0
    assert corpo["aguardam_assinatura"] == []


def test_facilitador_conta_as_reunioes_e_as_pendencias_dele(painel):
    pedir, estado = painel
    estado["banco"] = _banco_de_papeis()

    corpo = pedir("fabio").json()

    # A1 e A2, as Pendências da R1; nada da R2, que ele não facilita.
    assert corpo["cards"]["ativas"] == 2
    assert corpo["cards"]["atrasadas"] == 1
    assert corpo["cards"]["vencem_em_3_dias"] == 0
    assert [a["id_reuniao"] for a in corpo["aguardam_assinatura"]] == ["R1"]
    assert corpo["cards"]["aguardam_assinatura"] == 1
    assert [a["id_reuniao"] for a in corpo["atas_paradas"]] == ["R3"]
    assert corpo["aguardam_assinatura"][0]["pode_cobrar"] is True


def test_super_admin_conta_o_hospital_inteiro(painel):
    pedir, estado = painel
    estado["banco"] = _banco_de_papeis()

    corpo = pedir("admin").json()

    assert corpo["cards"]["ativas"] == 4
    assert corpo["cards"]["atrasadas"] == 2
    assert corpo["cards"]["vencem_em_3_dias"] == 1
    assert corpo["cards"]["conformidade"] == 50
    assert [a["id_reuniao"] for a in corpo["aguardam_assinatura"]] == ["R1", "R2"]
    assert all(a["pode_cobrar"] for a in corpo["aguardam_assinatura"])
    assert {s["setor"]: s["atrasado"] for s in corpo["por_setor"]} == {"UTI": 0, "Farmácia": 2}


def test_filtro_de_responsavel_vale_dentro_do_recorte(painel):
    pedir, estado = painel
    estado["banco"] = _banco_de_papeis()

    corpo = pedir("admin", responsavel_id="P_ANA").json()

    assert corpo["cards"]["ativas"] == 1


# ─── 3. A Secretária ─────────────────────────────────────────────────────────


def test_secretaria_nao_recebe_dado_de_pendencia(painel):
    pedir, estado = painel
    estado["banco"] = _banco_de_papeis()

    resposta = pedir("selma")

    assert resposta.status_code == 403
    assert "cards" not in resposta.json()
    assert "situacoes" not in resposta.json()
