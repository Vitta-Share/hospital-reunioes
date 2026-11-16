"""Os membros do Núcleo pela API (issue #1766, PRD #1764, ADR 0095).

A Presidência e o Acesso pleno cadastram, editam, renovam e encerram; quem tem
o recurso `membros` só lê; o super admin sem Acesso pleno não lê nem escreve
(decisão 4). Toda recusa é afirmada pelo código E pelo corpo. Toda mudança
grava trilha com autor, campo, valor anterior e novo, e nada se apaga.

O banco é um dublê em memória. Nenhum nome, registro ou e-mail de pessoa real:
as pessoas daqui são de teste.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_membros as membros_router  # noqa: E402

ROTA = "/api/nsp/membros"
RECUSA_DO_CONTEUDO = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}

HOJE = date.today()
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}
ASSINADO = "2026-01-10T12:00:00+00:00"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _iso(delta: int) -> str:
    return (HOJE + timedelta(days=delta)).isoformat()


class _Consulta:
    def __init__(self, banco: _Banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._filtros: list = []
        self._teto: int | None = None
        self._operacao = ("select", None)

    @property
    def _linhas(self) -> list[dict]:
        return self._banco.tabelas.setdefault(self._nome, [])

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        valores = list(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) <= str(valor))
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) >= str(valor))
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, n):
        self._teto = n
        return self

    def insert(self, linha: dict):
        self._operacao = ("insert", linha)
        return self

    def update(self, campos: dict):
        self._operacao = ("update", campos)
        return self

    def delete(self):
        raise AssertionError("Nada se apaga no módulo do Núcleo")

    def execute(self):
        operacao, carga = self._operacao
        if operacao == "insert":
            linhas = carga if isinstance(carga, list) else [carga]
            gravadas = []
            for linha in linhas:
                nova = {"id": str(uuid.uuid4()), "created_at": f"{HOJE.isoformat()}T12:00:00+00:00", **linha}
                self._linhas.append(nova)
                gravadas.append(dict(nova))
            return SimpleNamespace(data=gravadas)
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if operacao == "update":
            for linha in casam:
                linha.update(carga)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def table(self, nome: str):
        return _Consulta(self, nome)


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
        "conselho_profissional": None,
        "registro_profissional": None,
        "registro_uf": None,
        "data_cadastro": "2026-01-01",
    }
    return {**base, **campos}


def _participacao(
    pid: str, *, papel="membro", inicio=-30, fim=300, termo=True, encerrada=None, area="UTI adulto"
) -> dict[str, Any]:
    return {
        "id": f"part-{pid}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": pid,
        "papel": papel,
        "area": area,
        "vigencia_inicio": _iso(inicio),
        "vigencia_fim": _iso(fim),
        "encerrada_em": encerrada,
        "termo_assinado_em": ASSINADO if termo else None,
    }


# As pessoas de teste. P1 é o Acesso pleno; P2, a Presidência; P3, um membro
# com Termo; P4, alguém de fora; P5, o super admin; P6, a Diretoria.
ACESSO_PLENO = _pessoa("P1", perfil_nsp="acesso_pleno")
PRESIDENCIA = _pessoa("P2")
MEMBRO = _pessoa("P3", conselho_profissional="COREN", registro_profissional="000003", registro_uf="RJ")
DE_FORA = _pessoa("P4")
SUPER_ADMIN = _pessoa("P5", access_profile="super_admin", is_super_admin=True)
DIRETORIA = _pessoa("P6", role="diretor")


class _Cenario:
    def __init__(self, quem: dict, participacoes: list[dict] | None = None):
        if participacoes is None:
            participacoes = [_participacao("P2", papel="presidencia"), _participacao("P3")]
        self.banco = _Banco(
            {
                "participantes": [
                    dict(p) for p in (ACESSO_PLENO, PRESIDENCIA, MEMBRO, DE_FORA, SUPER_ADMIN, DIRETORIA)
                ],
                "colegiados": [dict(NUCLEO)],
                "participacoes": [dict(p) for p in participacoes],
                "participacoes_trilha": [],
            }
        )
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(membros_router.router, prefix="/api")

        async def _usuario() -> dict[str, Any]:
            return {"id": quem["auth_user_id"], "email": quem["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        self.api = TestClient(app)

    @property
    def participacoes(self) -> list[dict]:
        return self.banco.tabelas["participacoes"]

    @property
    def trilha(self) -> list[dict]:
        return self.banco.tabelas["participacoes_trilha"]

    def participacao(self, pid: str) -> dict:
        return next(p for p in self.participacoes if p["participante_id"] == pid and not p.get("encerrada_em"))


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA_DO_CONTEUDO


NOVO = {
    "participante_id": "P4",
    "papel": "suplente",
    "area": "Farmácia",
    "vigencia_inicio": _iso(0),
    "vigencia_fim": _iso(365),
    "conselho_profissional": "CRF",
    "registro_profissional": "000004",
    "registro_uf": "rj",
}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quem cadastra, edita, renova e encerra; quem só lê
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemFazOQue:
    @pytest.mark.parametrize("quem", [ACESSO_PLENO, PRESIDENCIA], ids=["acesso_pleno", "presidencia"])
    def test_presidencia_e_acesso_pleno_cadastram(self, quem):
        cenario = _Cenario(quem)

        resposta = cenario.api.post(ROTA, json=NOVO)

        assert resposta.status_code == 201, resposta.text
        assert resposta.json()["estado"] == "cadastrado"
        assert cenario.participacao("P4")["papel"] == "suplente"

    def test_membro_com_termo_le_a_lista_mas_nao_cadastra(self):
        """Mutante: trocar o recurso do cadastro de `gerir_nucleo` para `membros`."""
        cenario = _Cenario(MEMBRO)

        assert cenario.api.get(ROTA).status_code == 200
        _assert_recusado(cenario.api.post(ROTA, json=NOVO))
        assert [p for p in cenario.participacoes if p["participante_id"] == "P4"] == []

    def test_diretoria_le_a_composicao_mas_nao_edita(self):
        cenario = _Cenario(DIRETORIA)

        assert cenario.api.get(ROTA).status_code == 200
        _assert_recusado(cenario.api.patch(f"{ROTA}/part-P3", json={"area": "Outra"}))
        _assert_recusado(cenario.api.post(f"{ROTA}/part-P3/renovar", json={"vigencia_fim": _iso(700)}))
        _assert_recusado(cenario.api.post(f"{ROTA}/part-P3/encerrar", json={}))
        assert cenario.participacao("P3")["area"] == "UTI adulto"
        assert cenario.trilha == []

    def test_super_admin_sem_acesso_pleno_nao_le_nem_escreve(self):
        """ADR 0095, decisão 4. Mutante: deixar o super admin passar no gate."""
        cenario = _Cenario(SUPER_ADMIN)

        _assert_recusado(cenario.api.get(ROTA))
        _assert_recusado(cenario.api.post(ROTA, json=NOVO))

    def test_membro_sem_termo_nao_le_a_lista(self):
        cenario = _Cenario(MEMBRO, [_participacao("P2", papel="presidencia"), _participacao("P3", termo=False)])

        _assert_recusado(cenario.api.get(ROTA))

    def test_pessoa_de_fora_nao_le(self):
        _assert_recusado(_Cenario(DE_FORA).api.get(ROTA))


# ═══════════════════════════════════════════════════════════════════════════
# 2. A lista: o estado de cada um, sem dado de contato
# ═══════════════════════════════════════════════════════════════════════════


class TestLista:
    def test_cada_linha_traz_papel_area_registro_vigencia_estado_e_termo(self):
        corpo = _Cenario(PRESIDENCIA).api.get(ROTA).json()

        linha = next(m for m in corpo["membros"] if m["participante_id"] == "P3")
        assert linha["nome"] == "Pessoa de Teste P3"
        assert linha["papel"] == "membro"
        assert linha["area"] == "UTI adulto"
        assert (linha["conselho_profissional"], linha["registro_profissional"], linha["registro_uf"]) == (
            "COREN",
            "000003",
            "RJ",
        )
        assert linha["vigencia_fim"] == _iso(300)
        assert linha["estado"] == "ativo"
        assert linha["termo_assinado_em"] == ASSINADO
        assert "email" not in linha

    def test_o_estado_sai_da_funcao_pura(self):
        cenario = _Cenario(
            PRESIDENCIA,
            [_participacao("P2", papel="presidencia"), _participacao("P3", fim=10), _participacao("P4", termo=False)],
        )

        estados = {m["participante_id"]: m["estado"] for m in cenario.api.get(ROTA).json()["membros"]}

        assert estados == {"P2": "ativo", "P3": "a_vencer", "P4": "cadastrado"}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Encerrar não apaga; a composição em qualquer data
# ═══════════════════════════════════════════════════════════════════════════


class TestEncerrarEComposicao:
    def test_encerrar_nao_apaga_e_a_participacao_fica_no_historico(self):
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.post(f"{ROTA}/part-P3/encerrar", json={})

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["estado"] == "encerrado"
        encerrada = next(p for p in cenario.participacoes if p["id"] == "part-P3")
        assert encerrada["encerrada_em"] == HOJE.isoformat()
        assert encerrada["vigencia_fim"] == HOJE.isoformat()
        lista = cenario.api.get(ROTA).json()["membros"]
        assert {m["participante_id"]: m["estado"] for m in lista}["P3"] == "encerrado"

    def test_a_encerrada_continua_na_composicao_das_datas_em_que_valia(self):
        """Mutante: a composição filtrar `encerrada_em IS NULL`."""
        cenario = _Cenario(
            PRESIDENCIA,
            [
                _participacao("P2", papel="presidencia", inicio=-400),
                _participacao("P3", inicio=-300, fim=-100, encerrada=_iso(-100)),
            ],
        )

        composicao = cenario.api.get(ROTA, params={"data": _iso(-200)}).json()

        assert composicao["data"] == _iso(-200)
        assert sorted(m["participante_id"] for m in composicao["membros"]) == ["P2", "P3"]

    def test_a_composicao_em_data_passada_traz_so_quem_valia_naquele_dia(self):
        """Mutante: ignorar o fim da vigência na composição."""
        cenario = _Cenario(
            PRESIDENCIA,
            [
                _participacao("P2", papel="presidencia", inicio=-400),
                _participacao("P3", inicio=-300, fim=-250, encerrada=_iso(-250)),  # saiu antes
                _participacao("P4", inicio=-100, fim=300),  # entrou depois
                _participacao("P6", inicio=-200, fim=-200, encerrada=_iso(-200)),  # o próprio dia vale
            ],
        )

        composicao = cenario.api.get(ROTA, params={"data": _iso(-200)}).json()

        assert sorted(m["participante_id"] for m in composicao["membros"]) == ["P2", "P6"]

    def test_encerrar_com_data_anterior_ao_inicio_e_recusado(self):
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.post(f"{ROTA}/part-P3/encerrar", json={"data": _iso(-31)})

        assert resposta.status_code == 422
        assert cenario.participacao("P3")["encerrada_em"] is None

    def test_encerrada_nao_se_edita(self):
        cenario = _Cenario(
            PRESIDENCIA, [_participacao("P2", papel="presidencia"), _participacao("P3", encerrada=_iso(-1))]
        )

        resposta = cenario.api.patch(f"{ROTA}/part-P3", json={"area": "Outra"})

        assert resposta.status_code == 409
        assert cenario.trilha == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. A trilha; nenhuma rota de exclusão
# ═══════════════════════════════════════════════════════════════════════════


class TestTrilha:
    def test_editar_grava_autor_campo_valor_anterior_e_novo(self):
        """Mutante: não gravar a trilha da edição."""
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.patch(f"{ROTA}/part-P3", json={"area": "Centro cirúrgico", "papel": "suplente"})

        assert resposta.status_code == 200, resposta.text
        linhas = sorted(cenario.trilha, key=lambda t: t["campo"])
        assert [(t["acao"], t["campo"], t["valor_anterior"], t["valor_novo"], t["autor_id"]) for t in linhas] == [
            ("edicao", "area", "UTI adulto", "Centro cirúrgico", "P2"),
            ("mudanca_de_papel", "papel", "membro", "suplente", "P2"),
        ]
        assert all(t["participacao_id"] == "part-P3" and t["created_at"] for t in linhas)

    def test_editar_o_registro_profissional_grava_trilha_e_o_cadastro_da_pessoa(self):
        cenario = _Cenario(PRESIDENCIA)

        cenario.api.patch(f"{ROTA}/part-P3", json={"registro_profissional": "000033"})

        pessoa = next(p for p in cenario.banco.tabelas["participantes"] if p["id"] == "P3")
        assert pessoa["registro_profissional"] == "000033"
        assert [(t["campo"], t["valor_anterior"], t["valor_novo"]) for t in cenario.trilha] == [
            ("registro_profissional", "000003", "000033")
        ]

    def test_editar_sem_mudar_nada_nao_grava_trilha(self):
        cenario = _Cenario(PRESIDENCIA)

        cenario.api.patch(f"{ROTA}/part-P3", json={"area": "UTI adulto"})

        assert cenario.trilha == []

    def test_renovar_grava_o_fim_anterior_e_o_novo(self):
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.post(f"{ROTA}/part-P3/renovar", json={"vigencia_fim": _iso(700)})

        assert resposta.status_code == 200, resposta.text
        assert cenario.participacao("P3")["vigencia_fim"] == _iso(700)
        assert [(t["acao"], t["campo"], t["valor_anterior"], t["valor_novo"]) for t in cenario.trilha] == [
            ("renovacao", "vigencia_fim", _iso(300), _iso(700))
        ]

    def test_renovar_para_antes_do_fim_atual_e_recusado(self):
        cenario = _Cenario(PRESIDENCIA)

        assert cenario.api.post(f"{ROTA}/part-P3/renovar", json={"vigencia_fim": _iso(100)}).status_code == 422
        assert cenario.trilha == []

    def test_encerrar_grava_trilha(self):
        cenario = _Cenario(PRESIDENCIA)

        cenario.api.post(f"{ROTA}/part-P3/encerrar", json={"data": _iso(5)})

        assert sorted((t["acao"], t["campo"], t["valor_anterior"], t["valor_novo"]) for t in cenario.trilha) == [
            ("encerramento", "encerrada_em", None, _iso(5)),
            ("encerramento", "vigencia_fim", _iso(300), _iso(5)),
        ]

    def test_cadastrar_grava_trilha_com_o_autor(self):
        cenario = _Cenario(ACESSO_PLENO)

        cenario.api.post(ROTA, json=NOVO)

        cadastro = [t for t in cenario.trilha if t["acao"] == "cadastro"]
        assert sorted((t["campo"], t["valor_anterior"], t["valor_novo"]) for t in cadastro) == [
            ("area", None, "Farmácia"),
            ("papel", None, "suplente"),
            ("vigencia_fim", None, _iso(365)),
            ("vigencia_inicio", None, _iso(0)),
        ]
        assert {(t["autor_id"], t["participacao_id"]) for t in cadastro} == {("P1", cenario.participacao("P4")["id"])}

    def test_a_trilha_e_lida_com_o_nome_do_autor(self):
        cenario = _Cenario(PRESIDENCIA)
        cenario.api.patch(f"{ROTA}/part-P3", json={"area": "Centro cirúrgico"})

        trilha = cenario.api.get(f"{ROTA}/part-P3/trilha").json()["trilha"]

        assert [(t["autor"], t["campo"], t["valor_anterior"], t["valor_novo"]) for t in trilha] == [
            ("Pessoa de Teste P2", "area", "UTI adulto", "Centro cirúrgico")
        ]

    def test_nao_existe_rota_de_exclusao(self):
        """Mutante: acrescentar um DELETE ao router."""
        metodos = {metodo for rota in membros_router.router.routes for metodo in getattr(rota, "methods", ())}
        assert "DELETE" not in metodos
        assert metodos >= {"GET", "POST", "PATCH"}  # o detector enxerga as rotas

    def test_delete_na_participacao_nao_existe(self):
        resposta = _Cenario(ACESSO_PLENO).api.delete(f"{ROTA}/part-P3")

        assert resposta.status_code == 405


# ═══════════════════════════════════════════════════════════════════════════
# 5. O cadastro
# ═══════════════════════════════════════════════════════════════════════════


class TestCadastro:
    def test_o_cadastro_grava_o_registro_profissional_na_pessoa(self):
        cenario = _Cenario(PRESIDENCIA)

        cenario.api.post(ROTA, json=NOVO)

        pessoa = next(p for p in cenario.banco.tabelas["participantes"] if p["id"] == "P4")
        assert (pessoa["conselho_profissional"], pessoa["registro_profissional"], pessoa["registro_uf"]) == (
            "CRF",
            "000004",
            "RJ",
        )

    def test_quem_ja_tem_participacao_aberta_nao_e_cadastrado_de_novo(self):
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.post(ROTA, json={**NOVO, "participante_id": "P3"})

        assert resposta.status_code == 409
        assert len([p for p in cenario.participacoes if p["participante_id"] == "P3"]) == 1

    def test_quem_teve_a_participacao_encerrada_volta_com_participacao_nova(self):
        cenario = _Cenario(
            PRESIDENCIA,
            [_participacao("P2", papel="presidencia"), _participacao("P3", inicio=-300, fim=-10, encerrada=_iso(-10))],
        )

        resposta = cenario.api.post(ROTA, json={**NOVO, "participante_id": "P3"})

        assert resposta.status_code == 201, resposta.text
        assert len([p for p in cenario.participacoes if p["participante_id"] == "P3"]) == 2

    def test_fim_antes_do_inicio_e_recusado(self):
        resposta = _Cenario(PRESIDENCIA).api.post(ROTA, json={**NOVO, "vigencia_fim": _iso(-1)})

        assert resposta.status_code == 422

    def test_pessoa_que_nao_existe_e_recusada(self):
        resposta = _Cenario(PRESIDENCIA).api.post(ROTA, json={**NOVO, "participante_id": "P99"})

        assert resposta.status_code == 404

    def test_as_pessoas_para_o_cadastro_vem_sem_contato(self):
        resposta = _Cenario(PRESIDENCIA).api.get(f"{ROTA}/pessoas")

        assert resposta.status_code == 200
        pessoas = resposta.json()["pessoas"]
        assert {"id": "P4", "nome": "Pessoa de Teste P4"} in pessoas
        assert all(set(p) == {"id", "nome"} for p in pessoas)

    def test_as_pessoas_so_para_quem_gere(self):
        _assert_recusado(_Cenario(MEMBRO).api.get(f"{ROTA}/pessoas"))
