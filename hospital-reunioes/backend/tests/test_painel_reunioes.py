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

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha.get(coluna)) >= str(valor))
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha.get(coluna)) <= str(valor))
        return self

    def upsert(self, linhas, *, on_conflict, ignore_duplicates=False):
        # Só o `ignore_duplicates` que a fotografia usa: a linha que já existe
        # pela chave fica como estava (issue #1873).
        assert ignore_duplicates
        self._upsert = (linhas, on_conflict.split(","))
        return self

    def limit(self, quantos):
        self._recorte = (0, quantos - 1)
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
        if getattr(self, "_upsert", None) is not None:
            novas, chave = self._upsert
            gravadas = []
            for nova in novas:
                if not any(all(str(v.get(c)) == str(nova.get(c)) for c in chave) for v in self._linhas):
                    self._linhas.append(dict(nova))
                    gravadas.append(dict(nova))
            return _Result(gravadas)
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
    painel_fotografias: list = field(default_factory=list)
    rotinas: list = field(default_factory=list)
    rotina_verificacoes: list = field(default_factory=list)

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


# ─── 4. O gráfico de atrasos por setor e o ranking de 90 dias (issue #1871) ──


def _evento(id_acao, comando, criado_em, *, conta_atraso=False, status_antes="PENDENTE", prazo_antes=None) -> dict:
    return {
        "id_acao": id_acao,
        "comando": comando,
        "criado_em": criado_em,
        "conta_atraso": conta_atraso,
        "status_antes": status_antes,
        "prazo_antes": prazo_antes,
    }


def _ranking(corpo) -> dict:
    return {linha["responsavel_id"]: linha for linha in corpo["ranking"]}


def test_ranking_so_para_super_admin_e_quem_facilita_alguma_reuniao(painel):
    pedir, estado = painel
    estado["banco"] = _banco_de_papeis()

    # Fábio facilita a R1 e a R3; o Super admin vê; Ana só é responsável.
    assert pedir("admin").json()["ranking"] is not None
    assert pedir("fabio").json()["ranking"] is not None
    corpo_da_ana = pedir("ana").json()
    assert corpo_da_ana["ranking"] is None
    assert corpo_da_ana["atrasos_por_setor"] is None


# Ontem, no meio do dia em Brasília (UTC-3), dentro da janela.
ONTEM_AS_15H = "2026-11-17T18:00:00+00:00"


def _banco_do_ranking(pendencias, historico, participantes=None) -> _Banco:
    """A R9 é de outra pessoa e Fábio facilita a R1: o ranking conta o hospital
    inteiro, também para o Facilitador."""
    return _Banco(
        pendencias=pendencias,
        reunioes=[_reuniao("R9", "P_OUTRO", "ASSINADA"), _reuniao("R1", "P_FABIO", "ASSINADA")],
        participantes=participantes
        if participantes is not None
        else [
            {"id": "P_ANA", "setor": "UTI", "nome_completo": "Ana"},
            {"id": "P_BRUNO", "setor": "Farmácia", "nome_completo": "Bruno"},
        ],
        pendencia_historico=historico,
    )


def test_pendencia_cancelada_nao_entra_no_grafico_nem_no_ranking(painel):
    pedir, estado = painel
    estado["banco"] = _banco_do_ranking(
        [_pendencia("C1", "P_ANA", id_reuniao="R9", status="CANCELADO", prazo=ONTEM)],
        # Repactuada depois de vencer e reaberta, e cancelada depois.
        [
            _evento("C1", "repactuar", ONTEM_AS_15H, conta_atraso=True),
            _evento("C1", "reabrir", ONTEM_AS_15H, status_antes="CONCLUIDO"),
        ],
    )

    corpo = pedir("admin").json()

    assert corpo["ranking"] == []
    assert corpo["atrasos_por_setor"] == []


def test_reabertura_e_repactuacao_vencida_entram_no_ranking_e_a_antes_do_vencimento_nao(painel):
    pedir, estado = painel
    estado["banco"] = _banco_do_ranking(
        [
            _pendencia("A1", "P_ANA", id_reuniao="R9"),
            _pendencia("A2", "P_ANA", id_reuniao="R9"),
            _pendencia("B1", "P_BRUNO", id_reuniao="R9"),
        ],
        [
            # Ana: duas Repactuações depois do vencimento e uma Reabertura.
            _evento("A1", "repactuar", ONTEM_AS_15H, conta_atraso=True),
            _evento("A2", "repactuar", ONTEM_AS_15H, conta_atraso=True),
            _evento("A1", "reabrir", ONTEM_AS_15H, status_antes="CONCLUIDO"),
            # Bruno repactuou antes de vencer: não pesa.
            _evento("B1", "repactuar", ONTEM_AS_15H, conta_atraso=False),
        ],
    )

    ranking = _ranking(pedir("fabio").json())

    assert ranking["P_ANA"]["repactuacoes_vencidas"] == 2
    assert ranking["P_ANA"]["atrasos"] == 2
    assert ranking["P_ANA"]["reaberturas"] == 1
    assert ranking["P_ANA"]["nome"] == "Ana"
    assert "P_BRUNO" not in ranking


def test_atrasada_agora_e_conclusao_depois_do_prazo_contam_como_atraso(painel):
    pedir, estado = painel
    estado["banco"] = _banco_do_ranking(
        [
            _pendencia("B1", "P_BRUNO", id_reuniao="R9", prazo=ONTEM),
            _pendencia("B2", "P_BRUNO", id_reuniao="R9", status="CONCLUIDO", prazo="2026-11-17"),
            _pendencia("B3", "P_BRUNO", id_reuniao="R9", status="CONCLUIDO", prazo="2026-11-10"),
            # Concluída antes do ciclo de vida novo: sem evento, não é medida.
            _pendencia("B4", "P_BRUNO", id_reuniao="R9", status="CONCLUIDO", prazo="2026-11-10"),
        ],
        [
            # Concluída no último dia do prazo: não pesa.
            _evento("B2", "concluir", ONTEM_AS_15H, prazo_antes="2026-11-17"),
            _evento("B3", "concluir", ONTEM_AS_15H, prazo_antes="2026-11-10"),
        ],
    )

    bruno = _ranking(pedir("admin").json())["P_BRUNO"]

    assert bruno["atrasadas"] == 1
    assert bruno["concluidas_com_atraso"] == 1
    assert bruno["atrasos"] == 2


def test_conclusao_atrasada_e_reaberta_nao_perde_o_atraso(painel):
    pedir, estado = painel
    # Ana: prazo 01/11, concluiu em 05/11, a entrega foi reaberta em 06/11 com
    # prazo 20/11 e concluída de novo em 10/11, dentro do prazo novo. A
    # Reabertura apaga o `concluida_em` de 05/11, o histórico não.
    reaberta = _pendencia("A1", "P_ANA", id_reuniao="R9", status="CONCLUIDO", prazo="2026-11-20")
    reaberta["concluida_em"] = "2026-11-10T15:00:00+00:00"
    # Bruno: prazo 01/11, concluiu em 05/11 e ficou assim.
    so_atrasada = _pendencia("B1", "P_BRUNO", id_reuniao="R9", status="CONCLUIDO", prazo="2026-11-01")
    so_atrasada["concluida_em"] = "2026-11-05T15:00:00+00:00"
    estado["banco"] = _banco_do_ranking(
        [reaberta, so_atrasada],
        [
            _evento("A1", "concluir", "2026-11-05T15:00:00+00:00", prazo_antes="2026-11-01"),
            _evento("A1", "reabrir", "2026-11-06T15:00:00+00:00", status_antes="CONCLUIDO", conta_atraso=True),
            _evento("A1", "concluir", "2026-11-10T15:00:00+00:00", prazo_antes="2026-11-20"),
            _evento("B1", "concluir", "2026-11-05T15:00:00+00:00", prazo_antes="2026-11-01"),
        ],
    )

    corpo = pedir("admin").json()
    ranking = _ranking(corpo)

    assert ranking["P_ANA"]["concluidas_com_atraso"] == 1
    assert ranking["P_ANA"]["atrasos"] == 1
    assert ranking["P_ANA"]["reaberturas"] == 1
    assert ranking["P_BRUNO"]["atrasos"] == 1
    # Mesmo atraso, e a Reabertura pesa: Ana fica acima de Bruno.
    assert [linha["responsavel_id"] for linha in corpo["ranking"]] == ["P_ANA", "P_BRUNO"]


def test_janela_de_90_dias_nas_bordas(painel):
    pedir, estado = painel
    # Hoje é 18/11/2026: a janela vai de 21/08 a 18/11, no fuso de Brasília.
    estado["banco"] = _banco_do_ranking(
        [_pendencia("A1", "P_ANA", id_reuniao="R9"), _pendencia("B1", "P_BRUNO", id_reuniao="R9")],
        [
            # 21/08 à meia-noite em Brasília: primeiro instante da janela.
            _evento("A1", "repactuar", "2026-08-21T03:00:00+00:00", conta_atraso=True),
            # 18/11 às 23h59 em Brasília: último instante da janela.
            _evento("A1", "reabrir", "2026-11-19T02:59:00+00:00", status_antes="CONCLUIDO"),
            # 20/08 às 23h59 em Brasília: um minuto antes da janela.
            _evento("B1", "repactuar", "2026-08-21T02:59:00+00:00", conta_atraso=True),
            _evento("B1", "reabrir", "2026-08-21T02:59:00+00:00", status_antes="CONCLUIDO"),
        ],
    )

    ranking = _ranking(pedir("admin").json())

    assert ranking["P_ANA"]["repactuacoes_vencidas"] == 1
    assert ranking["P_ANA"]["reaberturas"] == 1
    assert "P_BRUNO" not in ranking


def test_responsavel_sem_setor_aparece_como_sem_setor(painel):
    pedir, estado = painel
    estado["banco"] = _banco_do_ranking(
        [_pendencia("D1", "P_DORA", id_reuniao="R9", prazo=ONTEM), _pendencia("A1", "P_ANA", id_reuniao="R9")],
        [_evento("A1", "repactuar", ONTEM_AS_15H, conta_atraso=True)],
        participantes=[
            {"id": "P_DORA", "setor": None, "nome_completo": "Dora"},
            {"id": "P_ANA", "setor": "UTI", "nome_completo": "Ana"},
        ],
    )

    corpo = pedir("admin").json()

    assert _ranking(corpo)["P_DORA"]["setor"] == "Sem Setor"
    assert {s["setor"]: s["atrasos"] for s in corpo["atrasos_por_setor"]} == {"Sem Setor": 1, "UTI": 1}


# ─── 4b. A Rotina no ranking (issue #1879; decisões 71 e 89 da #1757) ───────


def _rotina(rid, responsavel_id, frequencia, comeca_em, *, encerrada_em=None) -> dict:
    return {
        "id": rid,
        "id_reuniao": "R9",
        "responsavel_id": responsavel_id,
        "frequencia": frequencia,
        "comeca_em": comeca_em,
        "status": "ENCERRADA" if encerrada_em else "ATIVA",
        "encerrada_em": encerrada_em,
    }


def _verificacao(rotina_id, ciclo_inicio, ciclo_fim, resultado="REALIZADA", *, atrasada=False) -> dict:
    return {
        "rotina_id": rotina_id,
        "ciclo_inicio": ciclo_inicio,
        "ciclo_fim": ciclo_fim,
        "resultado": resultado,
        "atrasada": atrasada,
    }


def test_verificacao_nao_realizada_ou_atrasada_entra_no_ranking_do_responsavel_da_rotina(painel):
    pedir, estado = painel
    banco = _banco_do_ranking([], [])
    # Hoje é quarta, 18/11. Ana tem uma Rotina semanal desde 26/10:
    # 26/10 a 01/11 realizada no prazo (não pesa), 02/11 a 08/11 não
    # realizada (pesa), 09/11 a 15/11 terminou sem marcação (pesa) e
    # 16/11 a 22/11 ainda corre (não pesa).
    banco.rotinas = [
        _rotina("RA", "P_ANA", "SEMANAL", "2026-10-26"),
        # Bruno: semanal realizada fora do ciclo (pesa) e mensal desde julho:
        # julho terminou antes da janela de 90 dias (não pesa), agosto
        # terminou sem marcação dentro dela (pesa), setembro e outubro
        # realizadas, novembro ainda corre.
        _rotina("RB", "P_BRUNO", "SEMANAL", "2026-11-09"),
        _rotina("RM", "P_BRUNO", "MENSAL", "2026-07-01"),
        # Sem frequência (o fluxo contínuo antigo): não tem ciclo, não pesa.
        _rotina("RS", "P_ANA", None, None),
    ]
    banco.rotina_verificacoes = [
        _verificacao("RA", "2026-10-26", "2026-11-01"),
        _verificacao("RA", "2026-11-02", "2026-11-08", "NAO_REALIZADA"),
        _verificacao("RB", "2026-11-09", "2026-11-15", atrasada=True),
        _verificacao("RM", "2026-09-01", "2026-09-30"),
        _verificacao("RM", "2026-10-01", "2026-10-31"),
    ]
    estado["banco"] = banco

    corpo = pedir("admin").json()
    ranking = _ranking(corpo)

    assert ranking["P_ANA"]["rotinas_nao_cumpridas"] == 2
    assert ranking["P_BRUNO"]["rotinas_nao_cumpridas"] == 2
    # Ao lado dos atrasos e das reaberturas, sem somar neles.
    assert ranking["P_ANA"]["atrasos"] == 0
    assert ranking["P_ANA"]["reaberturas"] == 0
    assert {s["setor"]: s["rotinas_nao_cumpridas"] for s in corpo["atrasos_por_setor"]} == {"UTI": 2, "Farmácia": 2}


def test_rotina_encerrada_deixa_de_contar_a_partir_do_encerramento(painel):
    pedir, estado = painel
    banco = _banco_do_ranking([], [])
    # Ana encerrou a Rotina semanal em 11/11, no meio do ciclo de 09/11 a
    # 15/11: o ciclo de 02/11 a 08/11, que fechou sem marcação, continua
    # pesando; o de 09/11, mesmo marcado como não realizado, e os
    # seguintes, não.
    banco.rotinas = [_rotina("RA", "P_ANA", "SEMANAL", "2026-11-02", encerrada_em="2026-11-11")]
    banco.rotina_verificacoes = [_verificacao("RA", "2026-11-09", "2026-11-15", "NAO_REALIZADA")]
    estado["banco"] = banco

    assert _ranking(pedir("admin").json())["P_ANA"]["rotinas_nao_cumpridas"] == 1


# ─── 5. O kit de conhecimento ────────────────────────────────────────────────


def test_o_texto_de_reunioes_no_kit_diz_o_painel_novo():
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "reunioes.md").read_text(encoding="utf-8")
    assert "## O painel de Reuniões" in texto
    assert "sobre todas as pendências e reuniões do hospital, sem corte de quantidade" in texto
    assert "O facilitador conta também as reuniões que conduz e as pendências delas" in texto
    assert "manda de novo o pedido de assinatura da ClickSign só para quem não assinou" in texto
    assert "O painel não tem alerta de prazo nem lista do que depende de cada um" in texto


def test_o_texto_de_reunioes_no_kit_diz_o_ranking_de_90_dias():
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "reunioes.md").read_text(encoding="utf-8")
    assert "o gráfico de atrasos por setor e o ranking dos responsáveis dos últimos 90 dias" in texto
    assert "só para quem administra o aplicativo e para quem facilitou ao menos uma reunião" in texto
    assert "conta no setor do responsável pela pendência" in texto
    assert "A pendência cancelada não entra em nenhuma dessas contas" in texto
    assert "a repactuação feita antes de o prazo vencer não pesa" in texto


def test_o_texto_de_reunioes_no_kit_diz_a_fotografia_semanal():
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "reunioes.md").read_text(encoding="utf-8")
    assert "Toda segunda-feira, o aplicativo guarda os números do painel de cada pessoa" in texto
    assert "a evolução das atrasadas nas últimas 8 semanas" in texto
    assert "a seta só aparece quando existe a fotografia da semana anterior" in texto
    assert "A semana sem fotografia não aparece, e nada é recalculado do passado" in texto


# ─── 6. A fotografia semanal (issue #1873) ───────────────────────────────────

# HOJE é quarta, 18/11/2026: a semana dele começa na segunda, 16/11.
SEMANA = "2026-11-16"
SEMANA_ANTERIOR = "2026-11-09"


def _com_login(banco: _Banco) -> _Banco:
    """O Super admin e Ana entram no app; a Secretária também, e não tem painel;
    Bruno nunca entrou."""
    banco.participantes = [
        {"id": "P_ADMIN", "access_profile": "super_admin", "auth_user_id": "u-admin", "ativo": True},
        {"id": "P_ANA", "access_profile": "regular", "auth_user_id": "u-ana", "ativo": True, "setor": "UTI"},
        {"id": "P_SELMA", "access_profile": "secretaria", "auth_user_id": "u-selma", "ativo": True},
        {"id": "P_BRUNO", "access_profile": "regular", "auth_user_id": None, "setor": "Farmácia"},
    ]
    return banco


def _recorte_pelo_vinculo(sb, me):
    facilitadas = [r["id_reuniao"] for r in sb.reunioes if r["facilitador_id"] == me["id"]]
    return recorte_das_pendencias(
        me["id"],
        super_admin=me["access_profile"] == "super_admin",
        facilitadas=facilitadas,
        do_nucleo=[],
        ocultas=[],
    )


def _foto(participante_id, semana, *, atrasadas=0, conformidade=100) -> dict:
    return {
        "participante_id": participante_id,
        "semana": semana,
        "atas_paradas": 0,
        "aguardam_assinatura": 0,
        "atrasadas": atrasadas,
        "vencem_em_3_dias": 0,
        "conformidade": conformidade,
        "ativas": 4,
    }


def _atrasadas_da_semana(banco: _Banco, semana: str) -> dict:
    return {f["participante_id"]: f["atrasadas"] for f in banco.painel_fotografias if str(f["semana"]) == semana}


def test_rodar_o_job_duas_vezes_na_mesma_semana_grava_uma_fotografia_so(painel, monkeypatch):
    from app.cron import scheduler as cron
    from app.services import fotografia_do_painel

    banco = _com_login(_banco_de_papeis())
    dia = {"hoje": HOJE}
    monkeypatch.setattr(cron, "_supabase", lambda: banco)
    monkeypatch.setattr(cron, "_hoje", lambda: dia["hoje"])
    monkeypatch.setattr(fotografia_do_painel, "recorte_das_pendencias_de", _recorte_pelo_vinculo)

    cron.fotografar_painel_de_reunioes()
    # Uma atrasada a mais no meio da semana, e o job roda de novo no domingo.
    banco.pendencias.append(_pendencia("A9", "P_ANA", id_reuniao="R1", prazo=ONTEM))
    dia["hoje"] = date(2026, 11, 22)
    cron.fotografar_painel_de_reunioes()

    fotos = {(f["participante_id"], str(f["semana"])): f for f in banco.painel_fotografias}
    # Quem entra no app e vê o painel; a Secretária e quem nunca entrou, não.
    assert set(fotos) == {("P_ADMIN", SEMANA), ("P_ANA", SEMANA)}
    # Os números da primeira rodada, que a segunda não muda.
    assert fotos[("P_ADMIN", SEMANA)]["atrasadas"] == 2
    assert fotos[("P_ADMIN", SEMANA)]["ativas"] == 4
    assert fotos[("P_ANA", SEMANA)]["atrasadas"] == 1

    # A segunda seguinte é outra semana, e ganha a fotografia dela (a A3,
    # que vencia em 20/11, também já está atrasada).
    dia["hoje"] = date(2026, 11, 23)
    cron.fotografar_painel_de_reunioes()
    assert _atrasadas_da_semana(banco, "2026-11-23") == {"P_ADMIN": 4, "P_ANA": 2}


def test_sem_fotografia_da_semana_anterior_o_card_nao_mostra_seta(painel):
    pedir, estado = painel
    banco = _banco_de_papeis()
    # Só a fotografia desta semana, a da segunda 16/11.
    banco.painel_fotografias = [_foto("P_ADMIN", SEMANA, atrasadas=9)]
    estado["banco"] = banco

    assert pedir("admin").json()["semana_anterior"] is None

    banco.painel_fotografias.append(_foto("P_ADMIN", SEMANA_ANTERIOR, atrasadas=3, conformidade=70))
    banco.painel_fotografias.append(_foto("P_ANA", "2026-11-02", atrasadas=1))
    corpo = pedir("admin").json()

    assert corpo["semana_anterior"]["atrasadas"] == 3
    assert corpo["semana_anterior"]["conformidade"] == 70
    # A fotografia é de cada pessoa: a de Ana é de duas semanas atrás.
    assert pedir("ana").json()["semana_anterior"] is None
    # Com filtro, o número do card não é o da fotografia: sem seta.
    assert pedir("admin", responsavel_id="P_ANA").json()["semana_anterior"] is None


def test_a_evolucao_mostra_no_maximo_8_semanas_so_as_fotografadas(painel):
    pedir, estado = painel
    banco = _banco_de_papeis()
    segundas = [(date(2026, 11, 16) - timedelta(weeks=i)).isoformat() for i in range(10)]
    # Dez segundas, menos a de 26/10, quando o job não rodou.
    banco.painel_fotografias = [
        _foto("P_ADMIN", s, atrasadas=i) for i, s in enumerate(segundas) if s != "2026-10-26"
    ] + [_foto("P_ANA", SEMANA, atrasadas=50)]
    estado["banco"] = banco

    evolucao = pedir("admin").json()["evolucao"]

    # As 8 semanas de 28/09 a 16/11, sem a que não tem fotografia, da mais antiga à mais nova.
    assert evolucao == [
        {"semana": "2026-09-28", "atrasadas": 7},
        {"semana": "2026-10-05", "atrasadas": 6},
        {"semana": "2026-10-12", "atrasadas": 5},
        {"semana": "2026-10-19", "atrasadas": 4},
        {"semana": "2026-11-02", "atrasadas": 2},
        {"semana": "2026-11-09", "atrasadas": 1},
        {"semana": "2026-11-16", "atrasadas": 0},
    ]
    assert pedir("ana").json()["evolucao"] == [{"semana": "2026-11-16", "atrasadas": 50}]

    banco.painel_fotografias.append(_foto("P_ADMIN", "2026-10-26", atrasadas=3))
    assert len(pedir("admin").json()["evolucao"]) == 8
