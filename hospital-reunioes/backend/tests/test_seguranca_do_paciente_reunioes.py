"""As reuniões do Núcleo e o sigilo em toda leitura de reunião (issue #1772,
PRD #1764, ADR 0095, decisão 4).

A reunião do Núcleo é uma reunião com `colegiado_id`. Quem a vê é quem a
permissão do módulo libera, e nunca o super admin por ser super admin. Cada
caminho de leitura que já existia (lista geral, busca, detalhe, pendências,
calendário, relatórios, notificações e o Conector) tem o seu teste, e cada um
foi provado tirando o filtro daquele caminho.

O banco é um dublê em memória com as tabelas que as rotas leem. A pessoa "de
fora" está na lista de participantes da reunião do Núcleo de propósito: o que
a esconde é o sigilo, não a lista. Nenhum nome, registro ou e-mail de pessoa
real: as pessoas daqui são de teste. Nada aqui chama IA nem assinatura.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import comentarios as comentarios_router  # noqa: E402
from app.routers import notificacoes as notificacoes_router  # noqa: E402
from app.routers import pendencias as pendencias_router  # noqa: E402
from app.routers import reunioes as reunioes_router  # noqa: E402
from app.routers import seguranca_do_paciente_reunioes as nsp_reunioes_router  # noqa: E402
from app.services.central_de_comando import ferramenta_pendencias, ferramenta_reunioes  # noqa: E402
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo  # noqa: E402

RECUSA = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}

HOJE = hoje_em_sao_paulo()
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}

R_COMUM = "RD_COMUM_01"
R_NUCLEO = "RD_NUCLEO_01"
P_COMUM = "PEND_C1"
P_NUCLEO = "PEND_N1"
P_SOLTA = "PEND_S1"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


# ─── O banco de mentira ──────────────────────────────────────────────────────


def _partes(texto: str) -> list[str]:
    """Divide `a.eq.1,b.in.(x,y)` pelas vírgulas de fora dos parênteses."""
    partes, nivel, atual = [], 0, ""
    for c in texto:
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        if c == "," and nivel == 0:
            partes.append(atual)
            atual = ""
        else:
            atual += c
    return partes + [atual]


def _valor(linha: dict, coluna: str) -> Any:
    if "->>" in coluna:
        base, campo = coluna.split("->>")
        return (linha.get(base) or {}).get(campo)
    return linha.get(coluna)


def _condicao(texto: str):
    coluna, resto = texto.split(".", 1)
    negada = resto.startswith("not.")
    if negada:
        resto = resto[4:]
    op, valor = resto.split(".", 1)
    if op == "eq":
        teste = lambda linha: str(_valor(linha, coluna)) == valor  # noqa: E731
    elif op == "is":
        teste = lambda linha: _valor(linha, coluna) is None  # noqa: E731
    elif op == "in":
        itens = set(valor.strip("()").split(",")) - {""}
        teste = lambda linha: _valor(linha, coluna) in itens  # noqa: E731
    elif op == "ilike":
        miolo = valor.strip("*").lower()
        teste = lambda linha: miolo in str(_valor(linha, coluna) or "").lower()  # noqa: E731
    else:
        raise AssertionError(f"filtro do or_ sem suporte no dublê: {texto}")
    if op != "is" and negada:
        # O NOT IN do Postgres não casa NULL: o dublê repete o banco.
        return lambda linha: _valor(linha, coluna) is not None and not teste(linha)
    return (lambda linha: not teste(linha)) if negada else teste


class _Consulta:
    def __init__(self, banco: _Banco, tabela: str):
        self._banco = banco
        self._tabela = tabela
        self._filtros: list = []
        self._negar = False
        self._contar = False
        self._ordem: tuple[str, bool] | None = None
        self._faixa: tuple[int, int] | None = None
        self._teto: int | None = None
        self._inserir: Any = None
        self._atualizar: dict | None = None
        self._apagar = False
        self._colunas: list[str] | None = None

    def _filtro(self, teste) -> _Consulta:
        if self._negar:
            self._negar = False
            original = teste
            teste = lambda linha: not original(linha)  # noqa: E731
        self._filtros.append(teste)
        return self

    @property
    def not_(self) -> _Consulta:
        self._negar = True
        return self

    def select(self, colunas: str = "*", *_a, count=None, **_kw):
        self._contar = count == "exact"
        # Lista simples de colunas é respeitada, para o teste ver o que a rota
        # deixou de fora; com `*` ou com embed, a linha vai inteira.
        if colunas != "*" and "(" not in colunas:
            self._colunas = [c.strip() for c in colunas.split(",")]
        return self

    def eq(self, coluna, valor):
        return self._filtro(lambda linha: _valor(linha, coluna) == valor)

    def neq(self, coluna, valor):
        return self._filtro(lambda linha: _valor(linha, coluna) != valor)

    def in_(self, coluna, valores):
        valores = list(valores)
        return self._filtro(lambda linha: _valor(linha, coluna) in valores)

    def is_(self, coluna, valor):
        assert valor == "null"
        return self._filtro(lambda linha: _valor(linha, coluna) is None)

    def gte(self, coluna, valor):
        return self._filtro(lambda linha: str(_valor(linha, coluna)) >= str(valor))

    def lte(self, coluna, valor):
        return self._filtro(lambda linha: str(_valor(linha, coluna)) <= str(valor))

    def or_(self, texto):
        condicoes = [_condicao(p) for p in _partes(texto)]
        return self._filtro(lambda linha: any(c(linha) for c in condicoes))

    def order(self, coluna, desc=False, **_kw):
        self._ordem = (coluna, desc)
        return self

    def range(self, inicio, fim):
        self._faixa = (inicio, fim)
        return self

    def limit(self, n):
        self._teto = n
        return self

    def insert(self, linhas):
        self._inserir = linhas
        return self

    def update(self, campos):
        self._atualizar = dict(campos)
        return self

    def delete(self):
        self._apagar = True
        return self

    def execute(self):
        linhas = self._banco.tabelas.setdefault(self._tabela, [])
        if self._inserir is not None:
            novas = self._inserir if isinstance(self._inserir, list) else [self._inserir]
            linhas.extend(dict(n) for n in novas)
            return SimpleNamespace(data=[dict(n) for n in novas], count=None)
        if self._atualizar is not None or self._apagar:
            alvo = [linha for linha in linhas if all(f(linha) for f in self._filtros)]
            for linha in alvo:
                if self._apagar:
                    linhas.remove(linha)
                else:
                    linha.update(self._atualizar)
            return SimpleNamespace(data=[dict(linha) for linha in alvo], count=None)
        casam = [dict(linha) for linha in linhas if all(f(linha) for f in self._filtros)]
        total = len(casam)
        if self._ordem:
            coluna, desc = self._ordem
            casam.sort(key=lambda linha: str(linha.get(coluna) or ""), reverse=desc)
        if self._faixa:
            casam = casam[self._faixa[0] : self._faixa[1] + 1]
        if self._teto is not None:
            casam = casam[: self._teto]
        if self._colunas:
            casam = [{c: linha[c] for c in self._colunas if c in linha} for linha in casam]
        return SimpleNamespace(data=casam, count=total if self._contar else None)


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def table(self, nome: str) -> _Consulta:
        return _Consulta(self, nome)


# ─── As pessoas e o cenário ──────────────────────────────────────────────────


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
        "access_profile": "regular",
        "perfil_pop": None,
        "perfil_ouvidoria": None,
        "perfil_contas_medicas": None,
        "perfil_nsp": None,
        "github_login": None,
        "data_cadastro": "2026-01-01",
    }
    return {**base, **campos}


SUPER_ADMIN = _pessoa("SA1", access_profile="super_admin", is_super_admin=True)
SUPER_ADMIN_PLENO = _pessoa("SA2", access_profile="super_admin", is_super_admin=True, perfil_nsp="acesso_pleno")
DE_FORA = _pessoa("FORA1")
MEMBRO = _pessoa("MEMB1")
MEMBRO_SEM_TERMO = _pessoa("MEMB2")
PRESIDENCIA = _pessoa("PRES1")

# Quem não é do Núcleo, nos dois jeitos de ver reunião: o super admin (sem
# filtro de lista) e o regular que está na lista da reunião do Núcleo.
QUEM_E_DE_FORA = [pytest.param(SUPER_ADMIN, id="super_admin"), pytest.param(DE_FORA, id="regular_na_lista")]


def _participacao(pid: str, *, papel: str = "membro", termo: bool = True) -> dict[str, Any]:
    return {
        "id": f"part-{pid}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": pid,
        "papel": papel,
        "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=300)).isoformat(),
        "termo_assinado_em": "2026-01-10T12:00:00+00:00" if termo else None,
    }


def _reuniao(rid: str, *, titulo: str, tipo: str, colegiado: str | None) -> dict[str, Any]:
    return {
        "id_reuniao": rid,
        "data": HOJE.isoformat(),
        "hora_inicio": "09:00:00",
        "hora_fim": None,
        "titulo": titulo,
        "tipo": tipo,
        "objetivo": "Quedas de pacientes",
        "status_ata": "ASSINADA",
        "facilitador_id": "PRES1",
        "criada_por": "PRES1",
        "colegiado_id": colegiado,
        "deleted_at": None,
        "json_ata": {"resumo_executivo": "Discussão sobre quedas"},
        "fonte": "MOCK",
    }


def _pendencia(pid: str, rid: str | None) -> dict[str, Any]:
    return {
        "id_acao": pid,
        "id_reuniao": rid,
        "descricao_acao": f"Ação {pid}",
        "responsavel_id": "FORA1",
        "co_responsavel_id": None,
        "status": "PENDENTE",
        "prazo": HOJE.isoformat(),
        "deleted_at": None,
    }


def _notificacao(nid: str, destinatario: str, tipo: str, referencia: str | None) -> dict[str, Any]:
    return {
        "id": nid,
        "destinatario_id": destinatario,
        "tipo": tipo,
        "titulo": f"Aviso {nid}",
        "mensagem": None,
        "referencia_id": referencia,
        "lida": False,
        "created_at": "2026-11-15T10:00:00+00:00",
    }


def _banco() -> _Banco:
    pessoas = [SUPER_ADMIN, SUPER_ADMIN_PLENO, DE_FORA, MEMBRO, MEMBRO_SEM_TERMO, PRESIDENCIA]
    return _Banco(
        {
            "participantes": [dict(p) for p in pessoas],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [
                _participacao("MEMB1"),
                _participacao("MEMB2", termo=False),
                _participacao("PRES1", papel="presidencia"),
            ],
            "reunioes": [
                _reuniao(R_COMUM, titulo="Gerencial sobre quedas", tipo="Gerencial", colegiado=None),
                _reuniao(R_NUCLEO, titulo="Núcleo sobre quedas", tipo="Ordinária mensal", colegiado=NUCLEO["id"]),
            ],
            "reuniao_participantes": [
                {"id_reuniao": R_COMUM, "participante_id": "FORA1"},
                {"id_reuniao": R_NUCLEO, "participante_id": "FORA1"},
                {"id_reuniao": R_NUCLEO, "participante_id": "MEMB2"},
            ],
            "pendencias": [_pendencia(P_COMUM, R_COMUM), _pendencia(P_NUCLEO, R_NUCLEO), _pendencia(P_SOLTA, None)],
            "notificacoes": [
                _notificacao("n-ata", "FORA1", "ACEITE_INTERNO", R_NUCLEO),
                _notificacao("n-pend-nucleo", "FORA1", "RESPONSAVEL_ATRIBUIDO", P_NUCLEO),
                _notificacao("n-pend-comum", "FORA1", "RESPONSAVEL_ATRIBUIDO", P_COMUM),
                _notificacao("n-solta", "FORA1", "MENCAO", None),
            ],
            "comentarios_pendencias": [
                {
                    "id": "com-nucleo",
                    "id_acao": P_NUCLEO,
                    "autor_id": "MEMB1",
                    "autor_nome": "Pessoa de Teste MEMB1",
                    "conteudo": "Comentário da análise do evento",
                    "mencoes": [],
                    "created_at": "2026-11-15T10:00:00+00:00",
                }
            ],
        }
    )


def _cliente(pessoa: dict[str, Any], banco: _Banco | None = None) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    for modulo in (reunioes_router, pendencias_router, comentarios_router, notificacoes_router, nsp_reunioes_router):
        app.include_router(modulo.router, prefix="/api")
    banco = banco or _banco()

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _ids(linhas: list[dict], chave: str = "id_reuniao") -> set[str]:
    return {linha[chave] for linha in linhas}


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quem é de fora não vê reunião do Núcleo em caminho nenhum
# ═══════════════════════════════════════════════════════════════════════════


class TestListaGeral:
    @pytest.mark.parametrize("pessoa", QUEM_E_DE_FORA)
    def test_de_fora_nao_ve_reuniao_do_nucleo_na_lista_geral(self, pessoa):
        resposta = _cliente(pessoa).get("/api/reunioes")

        assert resposta.status_code == 200, resposta.text
        assert _ids(resposta.json()) == {R_COMUM}
        assert resposta.headers["X-Total-Count"] == "1"

    def test_membro_ve_a_reuniao_do_nucleo_na_lista_geral_mesmo_fora_da_lista(self):
        resposta = _cliente(MEMBRO).get("/api/reunioes")

        assert resposta.status_code == 200, resposta.text
        assert _ids(resposta.json()) == {R_NUCLEO}


class TestDetalhe:
    @pytest.mark.parametrize("pessoa", QUEM_E_DE_FORA)
    def test_de_fora_recebe_recusa_ao_abrir_reuniao_do_nucleo(self, pessoa):
        resposta = _cliente(pessoa).get(f"/api/reunioes/{R_NUCLEO}")

        _assert_recusado(resposta)
        assert "quedas" not in resposta.text

    def test_super_admin_sem_acesso_pleno_recebe_recusa_ao_abrir_reuniao_do_nucleo(self):
        _assert_recusado(_cliente(SUPER_ADMIN).get(f"/api/reunioes/{R_NUCLEO}"))

    def test_a_recusa_vale_para_toda_rota_da_reuniao_e_nao_so_a_leitura(self):
        """O gate é do router: a rota de assinatura também recusa."""
        _assert_recusado(_cliente(SUPER_ADMIN).get(f"/api/reunioes/{R_NUCLEO}/signatarios/status"))

    def test_super_admin_com_acesso_pleno_abre_a_reuniao_do_nucleo(self):
        resposta = _cliente(SUPER_ADMIN_PLENO).get(f"/api/reunioes/{R_NUCLEO}")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["titulo"] == "Núcleo sobre quedas"

    def test_membro_com_termo_abre_a_reuniao_do_nucleo_fora_da_lista(self):
        resposta = _cliente(MEMBRO).get(f"/api/reunioes/{R_NUCLEO}")

        assert resposta.status_code == 200, resposta.text

    def test_membro_sem_termo_recebe_recusa_ao_abrir_a_ata(self):
        """Ele está na lista de participantes e mesmo assim não abre."""
        _assert_recusado(_cliente(MEMBRO_SEM_TERMO).get(f"/api/reunioes/{R_NUCLEO}"))


class TestCalendario:
    @pytest.mark.parametrize("pessoa", QUEM_E_DE_FORA)
    def test_de_fora_nao_ve_reuniao_do_nucleo_no_calendario(self, pessoa):
        resposta = _cliente(pessoa).get("/api/reunioes/calendario")

        assert resposta.status_code == 200, resposta.text
        assert _ids(resposta.json()) == {R_COMUM}

    def test_membro_sem_termo_ve_a_reuniao_do_nucleo_no_calendario(self):
        resposta = _cliente(MEMBRO_SEM_TERMO).get("/api/reunioes/calendario")

        assert resposta.status_code == 200, resposta.text
        assert _ids(resposta.json()) == {R_NUCLEO}


class TestPendencias:
    @pytest.mark.parametrize("pessoa", QUEM_E_DE_FORA)
    def test_de_fora_nao_ve_pendencia_de_reuniao_do_nucleo(self, pessoa):
        resposta = _cliente(pessoa).get("/api/pendencias")

        assert resposta.status_code == 200, resposta.text
        assert P_NUCLEO not in _ids(resposta.json(), "id_acao")
        assert P_COMUM in _ids(resposta.json(), "id_acao")

    def test_a_pendencia_sem_reuniao_tambem_fica_fora_da_lista_do_super_admin(self):
        """A pendência sem reunião é o lembrete da Agenda regulatória do Núcleo
        (issue #1779): nenhuma lista de Pendências a mostra, nem ao super
        admin. Sobra só a da reunião comum."""
        resposta = _cliente(SUPER_ADMIN).get("/api/pendencias")

        assert _ids(resposta.json(), "id_acao") == {P_COMUM}
        assert resposta.headers["X-Total-Count"] == "1"

    def test_super_admin_recebe_recusa_ao_abrir_pendencia_de_reuniao_do_nucleo(self):
        _assert_recusado(_cliente(SUPER_ADMIN).get(f"/api/pendencias/{P_NUCLEO}"))

    def test_membro_ve_a_pendencia_da_reuniao_do_nucleo(self):
        resposta = _cliente(MEMBRO).get("/api/pendencias")

        assert _ids(resposta.json(), "id_acao") == {P_NUCLEO}


# As rotas irmãs do `GET /pendencias/{id_acao}`: o super admin tem `permitidas`
# None, então só as `ocultas` o barram. Cada uma é uma porta à parte, e o
# `id_acao` sequencial deixa qualquer uma ser achada no chute.
ROTAS_DA_PENDENCIA_DO_NUCLEO = [
    pytest.param("GET", f"/api/pendencias/{P_NUCLEO}/comentarios", None, id="ler_comentarios"),
    pytest.param("POST", f"/api/pendencias/{P_NUCLEO}/comentarios", {"conteudo": "Oi"}, id="comentar"),
    pytest.param("DELETE", f"/api/pendencias/{P_NUCLEO}/comentarios/com-nucleo", None, id="apagar_comentario"),
    pytest.param("GET", f"/api/pendencias/{P_NUCLEO}/mencionaveis", None, id="mencionaveis"),
    pytest.param("PATCH", f"/api/pendencias/{P_NUCLEO}", {"status": "CONCLUIDO"}, id="mudar_status"),
    pytest.param("PATCH", f"/api/pendencias/{P_NUCLEO}/force", {"status": "CONCLUIDO", "reason": "x"}, id="force"),
    pytest.param("DELETE", f"/api/pendencias/{P_NUCLEO}/force", {"reason": "x"}, id="force_del"),
]


class TestRotasIrmasDaPendencia:
    @pytest.mark.parametrize(("metodo", "caminho", "corpo"), ROTAS_DA_PENDENCIA_DO_NUCLEO)
    def test_super_admin_sem_acesso_pleno_recebe_recusa_e_nada_muda(self, metodo, caminho, corpo):
        banco = _banco()

        _assert_recusado(_cliente(SUPER_ADMIN, banco).request(metodo, caminho, json=corpo))

        pendencia = next(p for p in banco.tabelas["pendencias"] if p["id_acao"] == P_NUCLEO)
        assert pendencia["status"] == "PENDENTE"
        assert [c["id"] for c in banco.tabelas["comentarios_pendencias"]] == ["com-nucleo"]

    def test_regular_na_lista_recebe_recusa_nos_comentarios(self):
        _assert_recusado(_cliente(DE_FORA).get(f"/api/pendencias/{P_NUCLEO}/comentarios"))

    def test_super_admin_com_acesso_pleno_le_os_comentarios(self):
        resposta = _cliente(SUPER_ADMIN_PLENO).get(f"/api/pendencias/{P_NUCLEO}/comentarios")

        assert resposta.status_code == 200, resposta.text
        assert [c["id"] for c in resposta.json()] == ["com-nucleo"]

    def test_super_admin_com_acesso_pleno_muda_o_status(self):
        banco = _banco()

        resposta = _cliente(SUPER_ADMIN_PLENO, banco).patch(f"/api/pendencias/{P_NUCLEO}", json={"status": "CANCELADO"})

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["status"] == "CANCELADO"


class TestSerieRecorrente:
    def test_apagar_a_serie_nao_leva_a_reuniao_do_nucleo_de_quem_e_de_fora(self):
        """`DELETE /reunioes/grupo/{id}` não tem `id_reuniao` no caminho, então o
        gate do router não a cobre: o filtro é da própria rota."""
        banco = _banco()
        for reuniao in banco.tabelas["reunioes"]:
            reuniao.update(id_grupo_recorrencia="SERIE1", status_ata="PROGRAMADA")

        resposta = _cliente(SUPER_ADMIN, banco).delete("/api/reunioes/grupo/SERIE1")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["removidas"] == 1
        assert _ids(banco.tabelas["reunioes"]) == {R_NUCLEO}


class TestRelatorios:
    def test_os_numeros_do_painel_nao_contam_pendencia_de_reuniao_do_nucleo(self):
        """O painel do super admin conta as pendências das reuniões do
        hospital: com a do Núcleo seriam 2. A sem reunião é o lembrete da
        agenda (issue #1779) e também fica fora."""
        resposta = _cliente(SUPER_ADMIN).get("/api/pendencias/stats")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["total"] == 1
        assert resposta.json()["pendente"] == 1

    def test_os_numeros_do_painel_de_quem_esta_na_lista_tambem_nao_contam(self):
        resposta = _cliente(DE_FORA).get("/api/pendencias/stats")

        assert resposta.json()["total"] == 1


class TestBuscaEConector:
    @pytest.mark.parametrize("pessoa", QUEM_E_DE_FORA)
    def test_a_busca_por_termo_nao_acha_reuniao_do_nucleo(self, pessoa):
        """As duas reuniões falam de quedas; só a comum volta."""
        resposta = ferramenta_reunioes.executar({"termo": "quedas"}, pessoa, _banco())

        assert {r["id"] for r in resposta["reunioes"]} == {R_COMUM}
        assert resposta["total"] == 1

    def test_o_conector_nao_entrega_pendencia_de_reuniao_do_nucleo(self):
        resposta = ferramenta_pendencias.executar({}, SUPER_ADMIN, _banco())

        assert resposta["total"] == 1
        assert "Ação PEND_N1" not in str(resposta)

    def test_o_conector_entrega_a_reuniao_do_nucleo_a_quem_tem_acesso_pleno(self):
        resposta = ferramenta_reunioes.executar({"termo": "quedas"}, SUPER_ADMIN_PLENO, _banco())

        assert {r["id"] for r in resposta["reunioes"]} == {R_COMUM, R_NUCLEO}


class TestNotificacoes:
    def test_de_fora_nao_recebe_aviso_de_reuniao_do_nucleo_nem_de_pendencia_dela(self):
        resposta = _cliente(DE_FORA).get("/api/notificacoes")

        assert resposta.status_code == 200, resposta.text
        assert {n["id"] for n in resposta.json()} == {"n-pend-comum", "n-solta"}

    def test_o_contador_do_sino_bate_com_a_lista(self):
        assert _cliente(DE_FORA).get("/api/notificacoes/count").json() == {"nao_lidas": 2}


# ═══════════════════════════════════════════════════════════════════════════
# 2. As reuniões que não são do Núcleo continuam como antes
# ═══════════════════════════════════════════════════════════════════════════


class TestReunioesComuns:
    @pytest.mark.parametrize("pessoa", [SUPER_ADMIN, DE_FORA], ids=["super_admin", "regular"])
    def test_reuniao_comum_abre_como_antes(self, pessoa):
        resposta = _cliente(pessoa).get(f"/api/reunioes/{R_COMUM}")

        assert resposta.status_code == 200, resposta.text

    def test_regular_fora_da_lista_continua_sem_ver_a_reuniao_comum(self):
        resposta = _cliente(MEMBRO).get(f"/api/reunioes/{R_COMUM}")

        assert resposta.status_code == 404

    def test_sem_reuniao_do_nucleo_a_permissao_do_modulo_nem_e_lida(self):
        """Sem reunião do Núcleo, nada muda para ninguém: nem a Participação é
        lida."""
        banco = _banco()
        banco.tabelas["reunioes"] = [r for r in banco.tabelas["reunioes"] if r["colegiado_id"] is None]
        lidas: list[str] = []
        original = banco.table

        def _table(nome):
            lidas.append(nome)
            return original(nome)

        banco.table = _table

        resposta = _cliente(SUPER_ADMIN, banco).get("/api/reunioes")

        assert _ids(resposta.json()) == {R_COMUM}
        assert "participacoes" not in lidas

    def test_banco_sem_a_coluna_do_colegiado_nao_derruba_a_lista(self):
        """Entre o deploy e a migration 148 colada no Studio."""
        from postgrest.exceptions import APIError

        banco = _banco()
        banco.tabelas["reunioes"] = [r for r in banco.tabelas["reunioes"] if r["colegiado_id"] is None]
        original = banco.table

        def _table(nome):
            consulta = original(nome)
            if nome == "reunioes":
                eq_original = consulta.eq

                def _eq(coluna, valor):
                    if coluna == "colegiado_id":
                        raise APIError({"code": "42703", "message": "column reunioes.colegiado_id does not exist"})
                    return eq_original(coluna, valor)

                consulta.eq = _eq
            return consulta

        banco.table = _table
        resposta = _cliente(DE_FORA, banco).get("/api/reunioes")

        assert resposta.status_code == 200, resposta.text
        assert _ids(resposta.json()) == {R_COMUM}


# ═══════════════════════════════════════════════════════════════════════════
# 3. O item Reuniões do módulo: a Presidência cria, o Núcleo vê
# ═══════════════════════════════════════════════════════════════════════════

TIPOS_DO_NUCLEO = ["Ordinária mensal", "Análise de evento", "Apresentação à Diretoria", "Reunião rápida de segurança"]
# A reunião rápida não tem ata e entra pelo registro de três linhas (seção 5).
TIPOS_COM_ATA = TIPOS_DO_NUCLEO[:3]


def _nova(tipo: str) -> dict[str, Any]:
    return {"titulo": f"Reunião {tipo}", "data": (HOJE + timedelta(days=7)).isoformat(), "tipo": tipo}


class TestItemReunioesDoModulo:
    @pytest.mark.parametrize("tipo", TIPOS_COM_ATA)
    def test_presidencia_cria_reuniao_do_nucleo_e_ela_aparece_no_modulo(self, tipo):
        banco = _banco()
        cliente = _cliente(PRESIDENCIA, banco)

        criada = cliente.post("/api/nsp/reunioes", json=_nova(tipo))

        assert criada.status_code == 201, criada.text
        id_novo = criada.json()["id_reuniao"]
        linha = next(r for r in banco.tabelas["reunioes"] if r["id_reuniao"] == id_novo)
        assert linha["colegiado_id"] == NUCLEO["id"]
        assert linha["tipo"] == tipo
        assert linha["status_ata"] == "PROGRAMADA"
        lista = cliente.get("/api/nsp/reunioes").json()
        assert {(r["id_reuniao"], r["tipo"]) for r in lista["reunioes"]} >= {(id_novo, tipo)}

    def test_a_reuniao_criada_fica_escondida_de_quem_e_de_fora(self):
        banco = _banco()
        id_novo = (
            _cliente(PRESIDENCIA, banco).post("/api/nsp/reunioes", json=_nova("Análise de evento")).json()["id_reuniao"]
        )

        _assert_recusado(_cliente(SUPER_ADMIN, banco).get(f"/api/reunioes/{id_novo}"))
        assert id_novo not in _ids(_cliente(SUPER_ADMIN, banco).get("/api/reunioes").json())

    def test_tipo_de_fora_do_nucleo_e_recusado(self):
        resposta = _cliente(PRESIDENCIA).post("/api/nsp/reunioes", json=_nova("Gerencial"))

        assert resposta.status_code == 422

    def test_tipo_do_nucleo_nao_entra_pelo_agendamento_geral(self):
        resposta = _cliente(SUPER_ADMIN).post(
            "/api/reunioes/agendar", json={**_nova("Ordinária mensal"), "facilitador_id": "SA1"}
        )

        assert resposta.status_code == 422

    @pytest.mark.parametrize("pessoa", [MEMBRO, MEMBRO_SEM_TERMO, SUPER_ADMIN], ids=["membro", "sem_termo", "super"])
    def test_so_a_presidencia_cria(self, pessoa):
        _assert_recusado(_cliente(pessoa).post("/api/nsp/reunioes", json=_nova("Ordinária mensal")))

    def test_membro_sem_termo_ve_o_calendario_do_modulo_sem_poder_abrir(self):
        resposta = _cliente(MEMBRO_SEM_TERMO).get("/api/nsp/reunioes")

        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert [r["id_reuniao"] for r in corpo["reunioes"]] == [R_NUCLEO]
        assert corpo["pode_abrir"] is False
        assert corpo["pode_criar"] is False
        assert "json_ata" not in corpo["reunioes"][0]

    def test_o_modulo_nao_lista_reuniao_comum(self):
        corpo = _cliente(PRESIDENCIA).get("/api/nsp/reunioes").json()

        assert R_COMUM not in [r["id_reuniao"] for r in corpo["reunioes"]]
        assert corpo["tipos"] == TIPOS_DO_NUCLEO
        assert corpo["pode_abrir"] is True
        assert corpo["pode_criar"] is True

    def test_super_admin_recebe_recusa_no_item_reunioes_do_modulo(self):
        _assert_recusado(_cliente(SUPER_ADMIN).get("/api/nsp/reunioes"))


# ═══════════════════════════════════════════════════════════════════════════
# 4. O Kit de conhecimento do Assistente de Tecnologia diz o que mudou
# ═══════════════════════════════════════════════════════════════════════════

KIT = os.path.join(os.path.dirname(__file__), "..", "app", "conhecimento")


def _kit(arquivo: str) -> str:
    with open(os.path.join(KIT, arquivo), encoding="utf-8") as f:
        return " ".join(f.read().split())


class TestKitDeConhecimento:
    def test_o_produto_seguranca_do_paciente_diz_o_comportamento_novo(self):
        texto = _kit("seguranca-do-paciente.md")

        assert "a Presidência cria a reunião ali mesmo" in texto
        tipos = ("ordinária mensal", "análise de evento", "apresentação à Diretoria", "reunião rápida de segurança")
        for tipo in tipos:
            assert tipo in texto, tipo
        assert "quem ainda não assinou vê a data, o tipo e o título, e não abre" in texto
        assert "Isso vale também para o super admin." in texto
        assert "Reuniões estão vazias" not in texto

    def test_o_produto_reunioes_diz_que_as_do_nucleo_ficam_no_modulo(self):
        texto = _kit("reunioes.md")

        assert (
            "As reuniões do Núcleo de Segurança do Paciente ficam no módulo Segurança do Paciente, no item Reuniões"
            in texto
        )


# ═══════════════════════════════════════════════════════════════════════════
# 5. A reunião rápida de segurança: um registro de três linhas, sem ata
#    (issue #1777)
# ═══════════════════════════════════════════════════════════════════════════

RAPIDA = "Reunião rápida de segurança"
ROTA_RAPIDA = "/api/nsp/reunioes/rapidas"


def _rapida(**campos) -> dict[str, Any]:
    base = {
        "data": HOJE.isoformat(),
        "setor": "Setor de Teste",
        "participantes": ["MEMB1", "FORA1"],
        "texto": "Piso molhado no corredor.\nSinalização reposta.\nConferir de novo amanhã.",
    }
    return {**base, **campos}


def _tamanhos(banco: _Banco) -> dict[str, int]:
    return {nome: len(linhas) for nome, linhas in banco.tabelas.items()}


class TestReuniaoRapida:
    def test_registrar_a_reuniao_rapida_nao_pede_transcricao_nem_gera_ata_ou_envelope(self):
        """Mutante: gravar a rápida como reunião, na tabela do pipeline da ata."""
        banco = _banco()
        antes = _tamanhos(banco)

        resposta = _cliente(PRESIDENCIA, banco).post(ROTA_RAPIDA, json=_rapida())

        assert resposta.status_code == 201, resposta.text
        assert "status_ata" not in resposta.json()
        # Só o registro rápido cresceu: nenhuma reunião, participante de
        # reunião, transcrição, ata ou envelope de assinatura nasceu.
        depois = _tamanhos(banco)
        assert {nome: n for nome, n in depois.items() if n != antes.get(nome, 0)} == {"nsp_reunioes_rapidas": 1}
        registro = banco.tabelas["nsp_reunioes_rapidas"][0]
        assert registro["colegiado_id"] == NUCLEO["id"]
        assert registro["data"] == HOJE.isoformat()
        assert registro["setor"] == "Setor de Teste"
        assert registro["participantes"] == ["MEMB1", "FORA1"]
        assert registro["criada_por"] == "PRES1"

    def test_a_reuniao_rapida_nao_entra_pela_criacao_de_reuniao_com_ata(self):
        banco = _banco()
        antes = _tamanhos(banco)

        resposta = _cliente(PRESIDENCIA, banco).post("/api/nsp/reunioes", json=_nova(RAPIDA))

        assert resposta.status_code == 422, resposta.text
        assert _tamanhos(banco) == antes

    @pytest.mark.parametrize(
        "texto",
        [
            pytest.param("Uma.\nDuas.\nTrês.\nQuatro.", id="quatro_linhas"),
            pytest.param("Uma.\r\nDuas.\r\nTrês.\r\nQuatro.", id="quatro_linhas_do_windows"),
            pytest.param("Uma.\n\n\nQuatro.", id="linhas_em_branco_contam"),
        ],
    )
    def test_o_texto_nao_aceita_mais_de_tres_linhas(self, texto):
        """Mutante: trocar o teto de três linhas por quatro."""
        banco = _banco()

        resposta = _cliente(PRESIDENCIA, banco).post(ROTA_RAPIDA, json=_rapida(texto=texto))

        assert resposta.status_code == 422, resposta.text
        assert "três linhas" in resposta.text
        assert banco.tabelas.get("nsp_reunioes_rapidas", []) == []

    def test_tres_linhas_entram_e_a_quebra_do_fim_nao_conta(self):
        banco = _banco()

        resposta = _cliente(PRESIDENCIA, banco).post(ROTA_RAPIDA, json=_rapida(texto="Uma.\r\nDuas.\r\nTrês.\r\n"))

        assert resposta.status_code == 201, resposta.text
        assert banco.tabelas["nsp_reunioes_rapidas"][0]["texto"] == "Uma.\nDuas.\nTrês."

    def test_participante_que_nao_existe_e_recusado(self):
        banco = _banco()

        resposta = _cliente(PRESIDENCIA, banco).post(ROTA_RAPIDA, json=_rapida(participantes=["MEMB1", "NINGUEM"]))

        assert resposta.status_code == 422, resposta.text
        assert banco.tabelas.get("nsp_reunioes_rapidas", []) == []


def _com_rapida() -> _Banco:
    banco = _banco()
    resposta = _cliente(PRESIDENCIA, banco).post(ROTA_RAPIDA, json=_rapida())
    assert resposta.status_code == 201, resposta.text
    return banco


def _rapidas_da_lista(corpo: dict) -> list[dict]:
    return [r for r in corpo["reunioes"] if r["tipo"] == RAPIDA]


class TestReuniaoRapidaNaLista:
    def test_a_reuniao_rapida_aparece_na_lista_do_modulo_com_o_tipo_marcado(self):
        corpo = _cliente(MEMBRO, _com_rapida()).get("/api/nsp/reunioes").json()

        [rapida] = _rapidas_da_lista(corpo)
        assert rapida["rapida"] is True
        assert rapida["data"] == HOJE.isoformat()
        assert rapida["titulo"] == "Setor de Teste"
        assert rapida["texto"] == "Piso molhado no corredor.\nSinalização reposta.\nConferir de novo amanhã."
        assert rapida["participantes"] == ["Pessoa de Teste MEMB1", "Pessoa de Teste FORA1"]
        # A ordinária do cenário continua na lista, ao lado da rápida.
        assert R_NUCLEO in [r["id_reuniao"] for r in corpo["reunioes"]]

    def test_membro_sem_termo_ve_a_data_o_tipo_e_o_setor_sem_o_texto(self):
        """Mutante: mandar o texto da rápida a quem não abre a ata."""
        corpo = _cliente(MEMBRO_SEM_TERMO, _com_rapida()).get("/api/nsp/reunioes").json()

        [rapida] = _rapidas_da_lista(corpo)
        assert rapida["data"] == HOJE.isoformat()
        assert rapida["titulo"] == "Setor de Teste"
        assert "texto" not in rapida
        assert "participantes" not in rapida

    @pytest.mark.parametrize("pessoa", [SUPER_ADMIN, DE_FORA], ids=["super_admin", "regular_na_lista"])
    def test_quem_e_de_fora_recebe_recusa_na_lista_que_tem_a_rapida(self, pessoa):
        """O de fora está entre os participantes da rápida de propósito: o que
        o barra é o sigilo do Núcleo, não a lista."""
        _assert_recusado(_cliente(pessoa, _com_rapida()).get("/api/nsp/reunioes"))

    @pytest.mark.parametrize("pessoa", [MEMBRO, MEMBRO_SEM_TERMO, SUPER_ADMIN], ids=["membro", "sem_termo", "super"])
    def test_so_a_presidencia_registra_a_reuniao_rapida(self, pessoa):
        banco = _banco()
        antes = _tamanhos(banco)

        _assert_recusado(_cliente(pessoa, banco).post(ROTA_RAPIDA, json=_rapida()))
        assert _tamanhos(banco) == antes

    def test_banco_sem_a_tabela_da_rapida_nao_derruba_a_lista(self):
        """Entre o deploy e a migration 154 colada no Studio."""
        from postgrest.exceptions import APIError

        banco = _banco()
        original = banco.table

        def _table(nome):
            if nome == "nsp_reunioes_rapidas":
                raise APIError({"code": "42P01", "message": 'relation "nsp_reunioes_rapidas" does not exist'})
            return original(nome)

        banco.table = _table
        resposta = _cliente(PRESIDENCIA, banco).get("/api/nsp/reunioes")

        assert resposta.status_code == 200, resposta.text
        assert [r["id_reuniao"] for r in resposta.json()["reunioes"]] == [R_NUCLEO]
