"""Calendário anual, pauta montada pelo sistema e convocação das reuniões do
Núcleo (issue #1773, PRD #1764, ADR 0095).

O que a issue promete, um bloco por critério:

1. gerar o calendário cria as doze ordinárias do ano, uma por mês, e pedir de
   novo no mesmo ano não duplica;
2. a pauta aparece 5 dias úteis antes da ordinária, contando os feriados
   cadastrados, com as pendências da reunião anterior e a situação de hoje;
3. a Presidência edita a pauta antes de convocar;
4. a convocação vai só para quem conta para quórum (Ativo, A vencer, Em
   carência) e grava quem foi convocado;
5. a convocação fora da antecedência mínima do tipo é recusada com mensagem;
6. a montagem da pauta não chama IA;
7. o Kit de conhecimento diz o comportamento novo.

E o que mais pode vazar: o super admin sem papel no Núcleo é recusado em toda
rota nova (decisão 4), pelo código e pelo corpo.

O banco é um dublê em memória; o e-mail é dublado. Nenhum nome, registro ou
e-mail de pessoa real: as pessoas daqui são de teste. As datas relativas saem de
`hoje_em_sao_paulo()`; as regras de dia útil são provadas com datas fixas.
"""

from __future__ import annotations

import inspect
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_reunioes as nsp_reunioes_router  # noqa: E402
from app.services.seguranca_do_paciente import convocacao, pauta  # noqa: E402
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo  # noqa: E402

ROTA = "/api/nsp/reunioes"
RECUSA = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}
FUSO = ZoneInfo("America/Sao_Paulo")

HOJE = hoje_em_sao_paulo()
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}
ORDINARIA = "Ordinária mensal"

_UNICAS = {
    "nsp_pautas": ("id_reuniao",),
    "nsp_convocados": ("id_reuniao", "participante_id"),
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _emails(monkeypatch):
    """O e-mail é sempre dublado: guarda o que sairia."""
    enviados: list[dict] = []

    def _falso(destinatario, assunto, html_content, texto_fallback, **_kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html_content, "texto": texto_fallback})
        return True

    monkeypatch.setattr(convocacao, "_enviar_email", _falso)
    return enviados


# ═══════════════════════════════════════════════════════════════════════════
# O dublê do banco
# ═══════════════════════════════════════════════════════════════════════════


class _Consulta:
    def __init__(self, banco: _Banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._linhas = banco.tabelas.setdefault(nome, [])
        self._filtros: list = []
        self._ordem: tuple[str, bool] | None = None
        self._teto: int | None = None
        self._inicio = 0
        self._acao = "select"
        self._valores: Any = None

    def select(self, *_a, **_kw):
        return self

    def insert(self, valores):
        self._acao, self._valores = "insert", valores
        return self

    def upsert(self, valores, **_kw):
        self._acao, self._valores = "upsert", valores
        return self

    def update(self, valores):
        self._acao, self._valores = "update", valores
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def neq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) != valor)
        return self

    def in_(self, coluna, valores):
        self._filtros.append(lambda linha: linha.get(coluna) in list(valores))
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def lt(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) < str(valor))
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) <= str(valor))
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) >= str(valor))
        return self

    def order(self, coluna, desc=False, **_kw):
        self._ordem = (coluna, desc)
        return self

    def limit(self, n):
        self._teto = n
        return self

    def range(self, inicio, fim):
        self._inicio, self._teto = inicio, fim - inicio + 1
        return self

    def execute(self):
        if self._acao == "insert":
            return SimpleNamespace(data=self._inserir())
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._acao == "upsert":
            novas = self._valores if isinstance(self._valores, list) else [self._valores]
            chave = _UNICAS[self._nome]
            for valores in novas:
                existente = next((x for x in self._linhas if all(x.get(c) == valores.get(c) for c in chave)), None)
                if existente:
                    existente.update(valores)
                else:
                    self._linhas.append(dict(valores))
            return SimpleNamespace(data=[dict(v) for v in novas])
        if self._acao == "update":
            for linha in casam:
                linha.update(self._valores)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        if self._ordem:
            coluna, desc = self._ordem
            casam.sort(key=lambda linha: (linha.get(coluna) is None, str(linha.get(coluna))), reverse=desc)
        casam = casam[self._inicio :]
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam, count=len(casam))

    def _inserir(self) -> list[dict]:
        novas = self._valores if isinstance(self._valores, list) else [self._valores]
        chave = _UNICAS.get(self._nome)
        prontas = []
        for valores in novas:
            linha = {"id": str(uuid.uuid4()), **valores}
            if chave and any(all(linha.get(c) == outra.get(c) for c in chave) for outra in self._linhas + prontas):
                raise APIError({"code": "23505", "message": "duplicate key value violates unique constraint"})
            prontas.append(linha)
        self._linhas.extend(prontas)
        return [dict(linha) for linha in prontas]


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def table(self, nome: str):
        return _Consulta(self, nome)


# ═══════════════════════════════════════════════════════════════════════════
# Pessoas e cenário
# ═══════════════════════════════════════════════════════════════════════════


def _pessoa(pid: str, **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": f"Pessoa de Teste {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "cargo": None,
        "area": None,
        "setor": None,
        "role": None,
        "ativo": True,
        "is_externo": False,
        "is_super_admin": False,
        "access_profile": None,
        "perfil_pop": None,
        "perfil_ouvidoria": None,
        "perfil_contas_medicas": None,
        "perfil_nsp": None,
        "github_login": None,
        "data_cadastro": "2026-01-01",
    }
    return {**base, **campos}


PRESIDENTE = _pessoa("P1")
MEMBRO = _pessoa("P2")
SUPER_ADMIN = _pessoa("SA1", access_profile="super_admin", is_super_admin=True)


def _participacao(pid: str, papel: str = "membro", *, inicio: date | None = None, fim: date | None = None, **campos):
    return {
        "id": f"part-{pid}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": pid,
        "papel": papel,
        "vigencia_inicio": (inicio or HOJE - timedelta(days=200)).isoformat(),
        "vigencia_fim": (fim or HOJE + timedelta(days=300)).isoformat(),
        "encerrada_em": None,
        "termo_assinado_em": "2026-01-10T12:00:00+00:00",
        **campos,
    }


def _reuniao(rid: str, dia: date, *, tipo: str = ORDINARIA, hora: str | None = "09:00:00", **campos):
    return {
        "id_reuniao": rid,
        "data": dia.isoformat(),
        "hora_inicio": hora,
        "hora_fim": None,
        "titulo": f"Reunião {rid}",
        "tipo": tipo,
        "status_ata": "PROGRAMADA",
        "colegiado_id": NUCLEO["id"],
        "deleted_at": None,
        **campos,
    }


def _pendencia(pid: str, rid: str, status: str = "PENDENTE", **campos):
    return {
        "id_acao": pid,
        "id_reuniao": rid,
        "descricao_acao": f"Ação {pid}",
        "responsavel_nome": "Pessoa de Teste P2",
        "prazo": HOJE.isoformat(),
        "status": status,
        "deleted_at": None,
        **campos,
    }


def _banco(**tabelas) -> _Banco:
    base = {
        "participantes": [dict(PRESIDENTE), dict(MEMBRO), dict(SUPER_ADMIN)],
        "colegiados": [dict(NUCLEO)],
        "participacoes": [_participacao("P1", "presidencia"), _participacao("P2")],
        "reunioes": [],
        "reuniao_participantes": [],
        "pendencias": [],
        "nsp_agenda_regulatoria": [],
        "nsp_pautas": [],
        "nsp_convocados": [],
        "ouvidoria_feriados": [],
    }
    base.update(tabelas)
    return _Banco(base)


def _cliente(pessoa: dict[str, Any], banco: _Banco) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(nsp_reunioes_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA


def _ordinarias(banco: _Banco, ano: int) -> list[dict]:
    return [
        r
        for r in banco.tabelas["reunioes"]
        if r["tipo"] == ORDINARIA and r["data"].startswith(str(ano)) and r.get("colegiado_id") == NUCLEO["id"]
    ]


# ═══════════════════════════════════════════════════════════════════════════
# 1. O calendário anual
# ═══════════════════════════════════════════════════════════════════════════

ANO = HOJE.year + 1


class TestCalendarioAnual:
    def test_gerar_o_calendario_cria_doze_ordinarias_uma_por_mes(self):
        banco = _banco()

        resposta = _cliente(PRESIDENTE, banco).post(
            f"{ROTA}/calendario", json={"ano": ANO, "dia": 10, "hora_inicio": "14:00"}
        )

        assert resposta.status_code == 201, resposta.text
        criadas = _ordinarias(banco, ANO)
        assert sorted(int(r["data"][5:7]) for r in criadas) == list(range(1, 13))
        assert {r["status_ata"] for r in criadas} == {"PROGRAMADA"}
        assert {r["hora_inicio"] for r in criadas} == {"14:00:00"}
        assert len(resposta.json()["criadas"]) == 12

    def test_pedir_de_novo_no_mesmo_ano_nao_duplica(self):
        banco = _banco()
        cliente = _cliente(PRESIDENTE, banco)
        cliente.post(f"{ROTA}/calendario", json={"ano": ANO, "dia": 10, "hora_inicio": "14:00"})

        de_novo = cliente.post(f"{ROTA}/calendario", json={"ano": ANO, "dia": 20, "hora_inicio": "14:00"})

        assert de_novo.status_code == 201, de_novo.text
        assert len(_ordinarias(banco, ANO)) == 12
        assert de_novo.json()["criadas"] == []
        assert de_novo.json()["ja_existiam"] == list(range(1, 13))

    def test_mes_que_ja_tem_ordinaria_fica_como_esta(self):
        banco = _banco(reunioes=[_reuniao("RD_MARCO", date(ANO, 3, 25))])

        _cliente(PRESIDENTE, banco).post(f"{ROTA}/calendario", json={"ano": ANO, "dia": 10, "hora_inicio": "14:00"})

        marco = [r for r in _ordinarias(banco, ANO) if r["data"][5:7] == "03"]
        assert [r["id_reuniao"] for r in marco] == ["RD_MARCO"]
        assert len(_ordinarias(banco, ANO)) == 12

    def test_ordinaria_cancelada_nao_segura_o_mes(self):
        banco = _banco(reunioes=[_reuniao("RD_CANC", date(ANO, 3, 25), status_ata="CANCELADA")])

        _cliente(PRESIDENTE, banco).post(f"{ROTA}/calendario", json={"ano": ANO, "dia": 10, "hora_inicio": "14:00"})

        assert len([r for r in _ordinarias(banco, ANO) if r["status_ata"] == "PROGRAMADA"]) == 12

    def test_so_a_presidencia_gera(self):
        banco = _banco()

        _assert_recusado(
            _cliente(MEMBRO, banco).post(f"{ROTA}/calendario", json={"ano": ANO, "dia": 10, "hora_inicio": "14:00"})
        )
        assert _ordinarias(banco, ANO) == []


class TestDiaDoCalendario:
    def test_dia_que_cai_no_fim_de_semana_vai_para_o_proximo_dia_util(self):
        """10 de janeiro de 2027 é domingo."""
        assert pauta.datas_do_calendario(2027, 10, frozenset())[0] == date(2027, 1, 11)

    def test_dia_que_cai_em_feriado_cadastrado_vai_para_o_proximo_dia_util(self):
        assert pauta.datas_do_calendario(2027, 8, frozenset({date(2027, 3, 8)}))[2] == date(2027, 3, 9)

    def test_fim_de_semana_no_fim_do_mes_volta_para_o_ultimo_dia_util_do_mes(self):
        """28 de fevereiro de 2027 é domingo; 1º de março já é outro mês."""
        assert pauta.datas_do_calendario(2027, 28, frozenset())[1] == date(2027, 2, 26)


# ═══════════════════════════════════════════════════════════════════════════
# 2. A pauta aparece 5 dias úteis antes, com as pendências da anterior
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def relogio(monkeypatch):
    """Fixa o agora das rotas do módulo num instante de São Paulo."""

    def _fixar(dia: date, hora: time = time(10, 0)) -> None:
        monkeypatch.setattr(nsp_reunioes_router, "_agora", lambda: datetime.combine(dia, hora, tzinfo=FUSO))

    return _fixar


def _pauta(banco: _Banco, rid: str, pessoa: dict | None = None) -> dict:
    resposta = _cliente(pessoa or PRESIDENTE, banco).get(f"{ROTA}/{rid}/pauta")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _bloco(corpo: dict, chave: str) -> dict:
    return next(b for b in corpo["blocos"] if b["chave"] == chave)


def _evento(eid: str, evento: str, proxima: date, ativo: bool = True) -> dict:
    return {"id": eid, "evento": evento, "proxima_data": proxima.isoformat(), "ativo": ativo}


class TestDiaDaPauta:
    def test_a_pauta_da_ordinaria_aparece_cinco_dias_uteis_antes(self):
        """Segunda, 15 de março de 2027: cinco dias úteis antes é segunda, 8."""
        assert pauta.data_da_pauta(ORDINARIA, date(2027, 3, 15), frozenset()) == date(2027, 3, 8)

    def test_feriado_cadastrado_nao_conta_como_dia_util(self):
        """Com quarta, 10, feriado, a pauta sobe para sexta, 5."""
        assert pauta.data_da_pauta(ORDINARIA, date(2027, 3, 15), frozenset({date(2027, 3, 10)})) == date(2027, 3, 5)

    def test_antes_do_dia_a_pauta_ainda_nao_aparece(self, relogio):
        relogio(date(2027, 3, 5))
        banco = _banco(reunioes=[_reuniao("RD_MAR", date(2027, 3, 15))])

        corpo = _pauta(banco, "RD_MAR")

        assert corpo["disponivel"] is False
        assert corpo["disponivel_em"] == "2027-03-08"
        assert corpo["blocos"] == []
        assert banco.tabelas["nsp_pautas"] == []

    def test_o_feriado_cadastrado_entra_na_conta_da_rota(self, relogio):
        relogio(date(2027, 3, 5))
        banco = _banco(
            reunioes=[_reuniao("RD_MAR", date(2027, 3, 15))],
            ouvidoria_feriados=[{"data": "2027-03-10", "nome": "Feriado de teste"}],
        )

        corpo = _pauta(banco, "RD_MAR")

        assert corpo["disponivel"] is True
        assert corpo["disponivel_em"] == "2027-03-05"

    def test_a_pauta_traz_as_pendencias_da_reuniao_anterior_com_a_situacao(self):
        banco = _banco(
            reunioes=[
                _reuniao("RD_RETRASADA", HOJE - timedelta(days=60), status_ata="ASSINADA"),
                _reuniao("RD_ANTERIOR", HOJE - timedelta(days=30), status_ata="ASSINADA"),
                _reuniao("RD_PROXIMA", HOJE + timedelta(days=1)),
            ],
            pendencias=[
                _pendencia("PA1", "RD_ANTERIOR", "PENDENTE"),
                _pendencia("PA2", "RD_ANTERIOR", "CONCLUIDO"),
                _pendencia("PA3", "RD_ANTERIOR", deleted_at="2026-11-01T10:00:00+00:00"),
                _pendencia("PR1", "RD_RETRASADA"),
            ],
        )

        corpo = _pauta(banco, "RD_PROXIMA")

        assert corpo["disponivel"] is True
        itens = _bloco(corpo, "pendencias")["itens"]
        assert {(i["id_acao"], i["situacao"]) for i in itens} == {("PA1", "Pendente"), ("PA2", "Concluída")}
        assert all("Ação PA" in i["texto"] for i in itens)

    def test_a_situacao_e_a_de_hoje_e_nao_a_da_montagem(self):
        banco = _banco(
            reunioes=[
                _reuniao("RD_ANTERIOR", HOJE - timedelta(days=30), status_ata="ASSINADA"),
                _reuniao("RD_PROXIMA", HOJE + timedelta(days=1)),
            ],
            pendencias=[_pendencia("PA1", "RD_ANTERIOR", "PENDENTE")],
        )
        _pauta(banco, "RD_PROXIMA")
        banco.tabelas["pendencias"][0]["status"] = "CONCLUIDO"

        itens = _bloco(_pauta(banco, "RD_PROXIMA"), "pendencias")["itens"]

        assert [(i["id_acao"], i["situacao"]) for i in itens] == [("PA1", "Concluída")]

    def test_a_pauta_traz_a_agenda_regulatoria_e_os_blocos_das_proximas_fases(self):
        banco = _banco(
            reunioes=[_reuniao("RD_PROXIMA", HOJE + timedelta(days=1))],
            nsp_agenda_regulatoria=[
                _evento("ag1", "Notificação externa do mês", HOJE + timedelta(days=10)),
                _evento("ag2", "Revisão do PSP", HOJE + timedelta(days=200)),
                _evento("ag3", "Evento desativado", HOJE, ativo=False),
            ],
        )

        corpo = _pauta(banco, "RD_PROXIMA")

        agenda = _bloco(corpo, "agenda")["itens"]
        assert [i["texto"].split(",")[0] for i in agenda] == ["Notificação externa do mês"]
        for chave in ("indicadores", "casos", "planos_vencidos", "alertas_sanitarios"):
            assert _bloco(corpo, chave)["sem_dados"] is True
            assert _bloco(corpo, chave)["itens"] == []

    def test_a_pauta_montada_fica_gravada_uma_vez(self):
        banco = _banco(reunioes=[_reuniao("RD_PROXIMA", HOJE + timedelta(days=1))])

        _pauta(banco, "RD_PROXIMA")
        _pauta(banco, "RD_PROXIMA")

        assert [p["id_reuniao"] for p in banco.tabelas["nsp_pautas"]] == ["RD_PROXIMA"]

    def test_reuniao_de_fora_do_nucleo_nao_tem_pauta_aqui(self):
        banco = _banco(reunioes=[_reuniao("RD_COMUM", HOJE + timedelta(days=1), tipo="Gerencial", colegiado_id=None)])

        resposta = _cliente(PRESIDENTE, banco).get(f"{ROTA}/RD_COMUM/pauta")

        assert resposta.status_code == 404
