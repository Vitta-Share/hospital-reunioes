"""As Capacitações do Núcleo (issue #1778, PRD #1764, ADR 0095).

O que a issue promete, um bloco por critério de aceite:

1. a Presidência cadastra a capacitação com todos os campos e a lista de
   participantes;
2. só o próprio participante confirma a própria presença, e a confirmação
   grava data e hora;
3. a cobertura dos temas mínimos, por membro, conta só as capacitações com
   presença confirmada;
4. a Presidência edita a lista de temas mínimos;
5. o kit de conhecimento diz o comportamento novo.

E o que mais pode vazar: o super admin sem papel no Núcleo é recusado em toda
rota das capacitações (decisão 4), pelo código e pelo corpo.

O banco é um dublê em memória. Nenhum nome, registro ou e-mail de pessoa real:
as pessoas daqui são de teste. As datas são fixas ou saem de
`hoje_em_sao_paulo()`.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_capacitacoes as capacitacoes_router  # noqa: E402
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo  # noqa: E402

ROTA = "/api/nsp/capacitacoes"
RECUSA_DO_CONTEUDO = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}

HOJE = hoje_em_sao_paulo()
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}

# A chave única de cada tabela, como a migration declara.
_UNICAS = {
    "nsp_capacitacao_participantes": ("capacitacao_id", "participante_id"),
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


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
        self._acao = "select"
        self._valores: Any = None

    def select(self, *_a, **_kw):
        return self

    def insert(self, valores):
        self._acao, self._valores = "insert", valores
        return self

    def update(self, valores):
        self._acao, self._valores = "update", valores
        return self

    def delete(self):
        self._acao = "delete"
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        self._filtros.append(lambda linha: linha.get(coluna) in list(valores))
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
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

    def execute(self):
        if self._acao != "select":
            self._banco.escritas.append((self._acao, self._nome))
        if self._acao == "insert":
            return SimpleNamespace(data=self._inserir())
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._acao == "update":
            for linha in casam:
                linha.update(self._valores)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        if self._acao == "delete":
            self._linhas[:] = [linha for linha in self._linhas if linha not in casam]
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        if self._ordem:
            coluna, desc = self._ordem
            casam.sort(key=lambda linha: (linha.get(coluna) is None, str(linha.get(coluna))), reverse=desc)
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)

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
        self.escritas: list[tuple[str, str]] = []

    def table(self, nome: str):
        return _Consulta(self, nome)


# ═══════════════════════════════════════════════════════════════════════════
# Pessoas e cenário
# ═══════════════════════════════════════════════════════════════════════════


def _pessoa(pid: str = "P1", **campos) -> dict[str, Any]:
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


SUPER_ADMIN = {"access_profile": "super_admin", "is_super_admin": True}


def _participacao(participante: str, papel: str, *, termo=True, fim=None) -> dict[str, Any]:
    """Vigente desde antes do primeiro dia fixo daqui até depois de hoje."""
    return {
        "id": f"part-{participante}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": participante,
        "papel": papel,
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": fim or (HOJE + timedelta(days=300)).isoformat(),
        "termo_assinado_em": "2026-01-10T12:00:00+00:00" if termo else None,
    }


def _tema(tid: str, nome: str, *, ativo=True) -> dict[str, Any]:
    return {"id": tid, "nome": nome, "ativo": ativo}


def _capacitacao(cid: str = "cap-fixa", *, tema_ids=(), data="2026-10-20") -> dict[str, Any]:
    return {
        "id": cid,
        "titulo": "Higiene das mãos",
        "data": data,
        "carga_horaria": 2.0,
        "instrutor": "Instrutor de Teste",
        "publico": "membros",
        "tema_ids": list(tema_ids),
        "criado_por": "P1",
        "created_at": "2026-10-01T10:00:00+00:00",
    }


def _presenca(capacitacao_id: str, participante_id: str, confirmada_em: str | None = None) -> dict[str, Any]:
    return {
        "id": f"pres-{capacitacao_id}-{participante_id}",
        "capacitacao_id": capacitacao_id,
        "participante_id": participante_id,
        "presenca_confirmada_em": confirmada_em,
    }


PRESIDENTE = _pessoa("P1")
MEMBRO = _pessoa("P2")
OUTRO_MEMBRO = _pessoa("P3")
PROFISSIONAL = _pessoa("P4")


def _banco(
    pessoas: list[dict] | None = None,
    participacoes: list[dict] | None = None,
    *,
    temas: list[dict] | None = None,
    capacitacoes: list[dict] | None = None,
    presencas: list[dict] | None = None,
) -> _Banco:
    if pessoas is None:
        pessoas = [PRESIDENTE, MEMBRO, OUTRO_MEMBRO, PROFISSIONAL]
    if participacoes is None:
        participacoes = [
            _participacao("P1", "presidencia"),
            _participacao("P2", "membro"),
            _participacao("P3", "membro"),
        ]
    return _Banco(
        {
            "participantes": [dict(p) for p in pessoas],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [dict(p) for p in participacoes],
            "nsp_temas_minimos": [dict(t) for t in (temas or [])],
            "nsp_capacitacoes": [dict(c) for c in (capacitacoes or [])],
            "nsp_capacitacao_participantes": [dict(p) for p in (presencas or [])],
        }
    )


def _cliente(pessoa: dict[str, Any], banco: _Banco) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(capacitacoes_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA_DO_CONTEUDO


CADASTRO = {
    "titulo": "Identificação do paciente",
    "data": "2026-11-05",
    "carga_horaria": 1.5,
    "instrutor": "Instrutor de Teste",
    "publico": "profissionais",
    "tema_ids": ["tema-id"],
    "participantes": ["P2", "P4"],
}


# ═══════════════════════════════════════════════════════════════════════════
# 0. Super admin sem papel no Núcleo: recusado em toda rota (decisão 4)
# ═══════════════════════════════════════════════════════════════════════════

TODAS_AS_ROTAS = [
    ("get", ROTA, None),
    ("post", ROTA, CADASTRO),
    ("post", f"{ROTA}/cap-fixa/presenca", None),
    ("post", f"{ROTA}/temas", {"nome": "Tema novo"}),
    ("patch", f"{ROTA}/temas/tema-id", {"ativo": False}),
]


class TestSuperAdmin:
    @pytest.mark.parametrize(("metodo", "rota", "corpo"), TODAS_AS_ROTAS)
    def test_super_admin_sem_papel_no_nucleo_e_recusado(self, metodo, rota, corpo):
        """Mutante: trocar o recurso das rotas por um que o super admin tem."""
        admin = _pessoa("P9", **SUPER_ADMIN)
        banco = _banco(
            [admin, MEMBRO, PROFISSIONAL],
            [],
            temas=[_tema("tema-id", "Higiene das mãos")],
            capacitacoes=[_capacitacao(tema_ids=["tema-id"])],
            presencas=[_presenca("cap-fixa", "P2")],
        )

        resposta = getattr(_cliente(admin, banco), metodo)(rota, **({"json": corpo} if corpo else {}))

        _assert_recusado(resposta)
        assert banco.escritas == []


# ═══════════════════════════════════════════════════════════════════════════
# 1. A Presidência cadastra a capacitação com todos os campos e participantes
# ═══════════════════════════════════════════════════════════════════════════


class TestCadastro:
    def test_presidencia_cadastra_a_capacitacao_com_os_participantes(self):
        banco = _banco(temas=[_tema("tema-id", "Identificação do paciente")])

        resposta = _cliente(PRESIDENTE, banco).post(ROTA, json=CADASTRO)

        assert resposta.status_code == 201, resposta.text
        [salva] = banco.tabelas["nsp_capacitacoes"]
        assert salva["titulo"] == "Identificação do paciente"
        assert salva["data"] == "2026-11-05"
        assert salva["carga_horaria"] == 1.5
        assert salva["instrutor"] == "Instrutor de Teste"
        assert salva["publico"] == "profissionais"
        assert salva["tema_ids"] == ["tema-id"]
        assert salva["criado_por"] == "P1"
        presencas = banco.tabelas["nsp_capacitacao_participantes"]
        assert sorted(p["participante_id"] for p in presencas) == ["P2", "P4"]
        assert {p["capacitacao_id"] for p in presencas} == {salva["id"]}
        assert all(p.get("presenca_confirmada_em") is None for p in presencas)

    def test_a_lista_mostra_a_capacitacao_com_os_participantes_e_os_temas(self):
        banco = _banco(temas=[_tema("tema-id", "Identificação do paciente")])
        cliente = _cliente(PRESIDENTE, banco)
        cliente.post(ROTA, json=CADASTRO)

        corpo = cliente.get(ROTA).json()

        [capacitacao] = corpo["capacitacoes"]
        assert capacitacao["titulo"] == "Identificação do paciente"
        assert capacitacao["carga_horaria"] == 1.5
        assert capacitacao["publico"] == "profissionais"
        assert capacitacao["tema_ids"] == ["tema-id"]
        assert [
            (p["participante_id"], p["nome"], p["presenca_confirmada_em"]) for p in capacitacao["participantes"]
        ] == [
            ("P2", "Pessoa de Teste P2", None),
            ("P4", "Pessoa de Teste P4", None),
        ]
        assert corpo["pode_editar"] is True

    def test_membro_le_e_nao_cadastra(self):
        """Mutante: abrir o cadastro pelo recurso `capacitacoes`, que o membro tem."""
        banco = _banco(temas=[_tema("tema-id", "Identificação do paciente")])
        cliente = _cliente(MEMBRO, banco)

        _assert_recusado(cliente.post(ROTA, json=CADASTRO))
        assert banco.escritas == []
        leitura = cliente.get(ROTA)
        assert leitura.status_code == 200, leitura.text
        assert leitura.json()["pode_editar"] is False

    def test_membro_sem_termo_nao_abre_as_capacitacoes(self):
        banco = _banco([MEMBRO], [_participacao("P2", "membro", termo=False)])

        _assert_recusado(_cliente(MEMBRO, banco).get(ROTA))

    def test_sem_participantes_nao_cadastra(self):
        banco = _banco(temas=[_tema("tema-id", "Identificação do paciente")])

        resposta = _cliente(PRESIDENTE, banco).post(ROTA, json={**CADASTRO, "participantes": []})

        assert resposta.status_code == 422
        assert banco.escritas == []

    def test_tema_que_nao_esta_na_lista_nao_entra(self):
        banco = _banco(temas=[_tema("tema-id", "Identificação do paciente", ativo=False)])

        resposta = _cliente(PRESIDENTE, banco).post(ROTA, json=CADASTRO)

        assert resposta.status_code == 422, resposta.text
        assert banco.escritas == []

    def test_pessoa_fora_do_cadastro_nao_entra(self):
        banco = _banco(temas=[_tema("tema-id", "Identificação do paciente")])

        resposta = _cliente(PRESIDENTE, banco).post(ROTA, json={**CADASTRO, "participantes": ["P2", "PX"]})

        assert resposta.status_code == 422, resposta.text
        assert banco.escritas == []

    def test_participante_repetido_entra_uma_vez(self):
        banco = _banco(temas=[_tema("tema-id", "Identificação do paciente")])

        resposta = _cliente(PRESIDENTE, banco).post(ROTA, json={**CADASTRO, "participantes": ["P2", "P2"]})

        assert resposta.status_code == 201, resposta.text
        assert [p["participante_id"] for p in banco.tabelas["nsp_capacitacao_participantes"]] == ["P2"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. Só o próprio participante confirma a própria presença
# ═══════════════════════════════════════════════════════════════════════════


def _cenario_da_presenca() -> _Banco:
    return _banco(
        capacitacoes=[_capacitacao()],
        presencas=[_presenca("cap-fixa", "P2"), _presenca("cap-fixa", "P3")],
    )


def _presencas(banco: _Banco) -> dict[str, str | None]:
    return {p["participante_id"]: p["presenca_confirmada_em"] for p in banco.tabelas["nsp_capacitacao_participantes"]}


class TestPresenca:
    def test_participante_confirma_a_propria_presenca_com_data_e_hora(self):
        banco = _cenario_da_presenca()
        antes = datetime.now().astimezone()

        resposta = _cliente(MEMBRO, banco).post(f"{ROTA}/cap-fixa/presenca")

        assert resposta.status_code == 200, resposta.text
        gravada = _presencas(banco)["P2"]
        assert gravada is not None
        quando = datetime.fromisoformat(gravada)
        assert quando.tzinfo is not None
        assert antes - timedelta(seconds=5) <= quando <= datetime.now().astimezone() + timedelta(seconds=5)
        assert resposta.json()["presenca_confirmada_em"] == gravada

    def test_confirmar_nao_toca_a_presenca_dos_outros(self):
        """Mutante: confirmar a capacitação inteira, sem filtrar pela pessoa."""
        banco = _cenario_da_presenca()

        _cliente(MEMBRO, banco).post(f"{ROTA}/cap-fixa/presenca")

        assert _presencas(banco)["P3"] is None

    def test_a_presidencia_fora_da_lista_nao_confirma_por_ninguem(self):
        """Mutante: aceitar quem tem `gerir_nucleo` mesmo fora da lista."""
        banco = _cenario_da_presenca()

        resposta = _cliente(PRESIDENTE, banco).post(f"{ROTA}/cap-fixa/presenca", json={"participante_id": "P2"})

        _assert_recusado(resposta)
        assert banco.escritas == []
        assert _presencas(banco) == {"P2": None, "P3": None}

    def test_profissional_de_fora_do_nucleo_na_lista_confirma(self):
        banco = _banco(
            capacitacoes=[_capacitacao()],
            presencas=[_presenca("cap-fixa", "P4")],
        )

        resposta = _cliente(PROFISSIONAL, banco).post(f"{ROTA}/cap-fixa/presenca")

        assert resposta.status_code == 200, resposta.text
        assert _presencas(banco)["P4"] is not None

    def test_confirmar_de_novo_guarda_a_primeira_hora(self):
        banco = _banco(
            capacitacoes=[_capacitacao()],
            presencas=[_presenca("cap-fixa", "P2", "2026-10-20T15:00:00-03:00")],
        )

        resposta = _cliente(MEMBRO, banco).post(f"{ROTA}/cap-fixa/presenca")

        assert resposta.status_code == 200, resposta.text
        assert _presencas(banco)["P2"] == "2026-10-20T15:00:00-03:00"
        assert banco.escritas == []

    def test_pessoa_desligada_nao_confirma(self):
        desligada = _pessoa("P2", ativo=False)
        banco = _banco(
            [PRESIDENTE, desligada],
            capacitacoes=[_capacitacao()],
            presencas=[_presenca("cap-fixa", "P2")],
        )

        resposta = _cliente(desligada, banco).post(f"{ROTA}/cap-fixa/presenca")

        assert resposta.status_code == 403
        assert banco.escritas == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. A cobertura por membro conta só a presença confirmada
# ═══════════════════════════════════════════════════════════════════════════


def _cobertura(corpo: dict) -> dict[str, list[str]]:
    return {linha["participante_id"]: linha["temas_cobertos"] for linha in corpo["cobertura"]}


class TestCobertura:
    def test_so_conta_a_capacitacao_com_presenca_confirmada(self):
        """Mutante: contar todo participante da lista, confirmado ou não."""
        banco = _banco(
            temas=[_tema("t-maos", "Higiene das mãos"), _tema("t-id", "Identificação do paciente")],
            capacitacoes=[_capacitacao(tema_ids=["t-maos", "t-id"])],
            presencas=[
                _presenca("cap-fixa", "P2", "2026-10-20T15:00:00-03:00"),
                _presenca("cap-fixa", "P3"),
            ],
        )

        corpo = _cliente(PRESIDENTE, banco).get(ROTA).json()

        assert _cobertura(corpo) == {"P1": [], "P2": ["t-maos", "t-id"], "P3": []}

    def test_cada_membro_tem_nome_e_papel(self):
        banco = _banco()

        corpo = _cliente(MEMBRO, banco).get(ROTA).json()

        assert [(c["participante_id"], c["nome"], c["papel"]) for c in corpo["cobertura"]] == [
            ("P1", "Pessoa de Teste P1", "presidencia"),
            ("P2", "Pessoa de Teste P2", "membro"),
            ("P3", "Pessoa de Teste P3", "membro"),
        ]

    def test_tema_desativado_nao_conta(self):
        banco = _banco(
            temas=[_tema("t-maos", "Higiene das mãos"), _tema("t-velho", "Tema antigo", ativo=False)],
            capacitacoes=[_capacitacao(tema_ids=["t-maos", "t-velho"])],
            presencas=[_presenca("cap-fixa", "P2", "2026-10-20T15:00:00-03:00")],
        )

        corpo = _cliente(PRESIDENTE, banco).get(ROTA).json()

        assert _cobertura(corpo)["P2"] == ["t-maos"]

    def test_quem_saiu_do_nucleo_nao_aparece_na_cobertura(self):
        banco = _banco(
            participacoes=[
                _participacao("P1", "presidencia"),
                _participacao("P2", "membro"),
                _participacao("P3", "membro", fim="2025-06-30"),
            ],
        )

        corpo = _cliente(PRESIDENTE, banco).get(ROTA).json()

        assert sorted(_cobertura(corpo)) == ["P1", "P2"]

    def test_profissional_de_fora_do_nucleo_nao_entra_na_cobertura(self):
        banco = _banco(
            temas=[_tema("t-maos", "Higiene das mãos")],
            capacitacoes=[_capacitacao(tema_ids=["t-maos"])],
            presencas=[_presenca("cap-fixa", "P4", "2026-10-20T15:00:00-03:00")],
        )

        corpo = _cliente(PRESIDENTE, banco).get(ROTA).json()

        assert "P4" not in _cobertura(corpo)


# ═══════════════════════════════════════════════════════════════════════════
# 4. A Presidência edita a lista de temas mínimos
# ═══════════════════════════════════════════════════════════════════════════


class TestTemasMinimos:
    def test_a_lista_comeca_vazia(self):
        corpo = _cliente(PRESIDENTE, _banco()).get(ROTA).json()

        assert corpo["temas"] == []

    def test_presidencia_inclui_um_tema(self):
        banco = _banco()

        resposta = _cliente(PRESIDENTE, banco).post(f"{ROTA}/temas", json={"nome": "  Higiene das mãos  "})

        assert resposta.status_code == 201, resposta.text
        [tema] = banco.tabelas["nsp_temas_minimos"]
        assert tema["nome"] == "Higiene das mãos"
        assert tema["ativo"] is True
        assert [t["nome"] for t in _cliente(PRESIDENTE, banco).get(ROTA).json()["temas"]] == ["Higiene das mãos"]

    def test_presidencia_renomeia_e_desativa_um_tema(self):
        banco = _banco(temas=[_tema("tema-id", "Higiene das maos")])
        cliente = _cliente(PRESIDENTE, banco)

        renomeado = cliente.patch(f"{ROTA}/temas/tema-id", json={"nome": "Higiene das mãos"})
        desativado = cliente.patch(f"{ROTA}/temas/tema-id", json={"ativo": False})

        assert renomeado.status_code == 200, renomeado.text
        assert desativado.status_code == 200, desativado.text
        [tema] = banco.tabelas["nsp_temas_minimos"]
        assert (tema["nome"], tema["ativo"]) == ("Higiene das mãos", False)

    def test_tema_com_o_mesmo_nome_nao_entra_duas_vezes(self):
        banco = _banco(temas=[_tema("tema-id", "Higiene das mãos")])

        resposta = _cliente(PRESIDENTE, banco).post(f"{ROTA}/temas", json={"nome": "higiene das MÃOS"})

        assert resposta.status_code == 409, resposta.text
        assert banco.escritas == []

    def test_tema_inexistente_responde_404(self):
        resposta = _cliente(PRESIDENTE, _banco()).patch(f"{ROTA}/temas/nao-existe", json={"ativo": False})

        assert resposta.status_code == 404

    @pytest.mark.parametrize(
        ("metodo", "rota", "corpo"),
        [("post", f"{ROTA}/temas", {"nome": "Tema novo"}), ("patch", f"{ROTA}/temas/tema-id", {"ativo": False})],
    )
    def test_membro_nao_edita_os_temas(self, metodo, rota, corpo):
        """Mutante: abrir a edição dos temas pelo recurso `capacitacoes`."""
        banco = _banco(temas=[_tema("tema-id", "Higiene das mãos")])

        _assert_recusado(getattr(_cliente(MEMBRO, banco), metodo)(rota, json=corpo))
        assert banco.escritas == []


# ═══════════════════════════════════════════════════════════════════════════
# 5. O texto do Produto no Kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def _secao_do_kit(titulo: str) -> str:
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "seguranca-do-paciente.md").read_text(encoding="utf-8")
    partes = texto.split(f"## {titulo}\n", 1)
    assert len(partes) == 2, f"a seção {titulo!r} sumiu do kit"
    return partes[1].split("\n## ", 1)[0]


class TestKitDeConhecimento:
    def test_as_capacitacoes_estao_no_que_ja_esta_no_ar(self):
        """Mutante: deixar o kit dizendo que a tela de Capacitações está vazia."""
        secao = _secao_do_kit("O que já está no ar")
        for termo in ("Capacitações", "Confirmar minha presença", "temas mínimos", "presença confirmada"):
            assert termo in secao, termo

    def test_a_tela_vazia_saiu_do_que_ele_ainda_nao_faz(self):
        assert "Capacitações ainda está vazia" not in _secao_do_kit("O que ele ainda não faz")

    def test_o_que_costuma_virar_demanda_explica_o_tema_nao_coberto(self):
        assert "não confirmou" in _secao_do_kit("O que costuma virar Demanda")
