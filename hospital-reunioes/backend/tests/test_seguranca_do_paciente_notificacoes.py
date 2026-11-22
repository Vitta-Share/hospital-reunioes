"""Notificar um incidente (issue #1987, PRD #1979, ADR 0107).

O que a issue promete, um bloco por critério de aceite do backend:

1. enviar grava a notificação com o protocolo NSP-AAAA-NNNN e a origem pelo
   ponto de entrada: QR (`/notificar/qr`), endereço (`/notificar`) ou o botão
   do módulo, que vale para todo usuário logado e preenche a identificação;
2. a anônima recebe o código uma vez, guarda só o hash e não guarda IP nem
   identificador do aparelho;
3. a página de acompanhamento mostra só o estado em palavras simples e recusa
   protocolo com código ou contato errado;
4. a lista de casos aparece para quem tem o recurso de casos; a identidade de
   quem notificou só para a Presidência e o Acesso pleno; o super admin sem
   Acesso pleno recebe recusa;
5. envio repetido do mesmo aparelho acima do limite recebe recusa.

O banco é um dublê em memória. O protocolo do dublê imita o trigger da
migration 174 (contador por ano); o formato e a sequência no banco de verdade
são conferidos no teste da migration. Nenhum dado de pessoa real.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_notificacoes as notificacoes_router  # noqa: E402
from app.services.ouvidoria_acompanhamento import codigo_confere  # noqa: E402
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo  # noqa: E402

HOJE = hoje_em_sao_paulo()
ANO = HOJE.year
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}
SETOR = {"id": "11111111-1111-1111-1111-111111111111", "nome": "UTI Adulto", "ativo": True}
SETOR_DESATIVADO = {"id": "22222222-2222-2222-2222-222222222222", "nome": "Setor antigo", "ativo": False}
RECUSA_DO_CONTEUDO = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}


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
        self._faixa: tuple[int, int] | None = None
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

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        valores = list(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
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
        self._faixa = (inicio, fim)
        return self

    def execute(self):
        if self._acao == "insert":
            self._banco.escritas.append((self._nome, self._valores))
            return SimpleNamespace(data=self._inserir())
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._acao == "update":
            self._banco.escritas.append((self._nome, self._valores))
            for linha in casam:
                linha.update(self._valores)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        if self._ordem:
            coluna, desc = self._ordem
            casam.sort(key=lambda linha: str(linha.get(coluna)), reverse=desc)
        if self._faixa is not None:
            # Como o PostgREST: as duas pontas entram.
            casam = casam[self._faixa[0] : self._faixa[1] + 1]
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)

    def _inserir(self) -> list[dict]:
        novas = self._valores if isinstance(self._valores, list) else [self._valores]
        prontas = []
        for valores in novas:
            linha = {"id": str(uuid.uuid4()), **valores}
            if self._nome == "nsp_notificacoes":
                # O que o trigger da migration 174 faz no insert.
                self._banco.ultimo_do_ano[ANO] = self._banco.ultimo_do_ano.get(ANO, 0) + 1
                linha.setdefault("estado", "recebida")
                linha["ano"] = ANO
                linha["numero"] = self._banco.ultimo_do_ano[ANO]
                linha["protocolo"] = f"NSP-{ANO}-{linha['numero']:04d}"
                linha["criado_em"] = f"{HOJE.isoformat()}T10:00:00+00:00"
            prontas.append(linha)
        self._linhas.extend(prontas)
        return [dict(linha) for linha in prontas]


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas
        self.escritas: list[tuple[str, Any]] = []
        self.ultimo_do_ano: dict[int, int] = {}

    def table(self, nome: str):
        return _Consulta(self, nome)

    @property
    def notificacoes(self) -> list[dict]:
        return self.tabelas.get("nsp_notificacoes", [])


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


def _participacao(participante: str, papel: str, *, termo=True) -> dict[str, Any]:
    return {
        "id": f"part-{participante}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": participante,
        "papel": papel,
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": (HOJE + timedelta(days=300)).isoformat(),
        "termo_assinado_em": "2026-01-10T12:00:00+00:00" if termo else None,
    }


PRESIDENTE = _pessoa("P1")
MEMBRO = _pessoa("P2")
SO_REUNIOES = _pessoa("P3", access_profile="regular")
SUPER_ADMIN = _pessoa("P4", access_profile="super_admin", is_super_admin=True)
DIRETOR_EXECUTIVO = _pessoa("P5", perfil_nsp="acesso_pleno")
DIRETOR = _pessoa("P6", role="diretor", access_profile="regular")


def _banco(notificacoes: list[dict] | None = None) -> _Banco:
    return _Banco(
        {
            "participantes": [
                dict(p) for p in (PRESIDENTE, MEMBRO, SO_REUNIOES, SUPER_ADMIN, DIRETOR_EXECUTIVO, DIRETOR)
            ],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [_participacao("P1", "presidencia"), _participacao("P2", "membro")],
            "setores": [dict(SETOR), dict(SETOR_DESATIVADO)],
            "nsp_notificacoes": [dict(n) for n in (notificacoes or [])],
        }
    )


def _cliente(banco: _Banco, pessoa: dict[str, Any] | None = None) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(notificacoes_router.router, prefix="/api")
    if pessoa is not None:

        async def _usuario() -> dict[str, Any]:
            return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


RELATO = {
    "relato": "A bomba de infusão do leito 4 alarmou e ninguém ouviu por meia hora.",
    "leito_ou_atendimento": "Leito 4",
    "setor_id": SETOR["id"],
    "data_ocorrencia": HOJE.isoformat(),
    "turno": "noite",
    "hora_aproximada": "03:30",
    "chegou_ao_paciente": "sem_dano",
    "grave_ou_morte": None,
    "percebido_ou_reclamacao": "nao",
}

IDENTIFICADO = {**RELATO, "anonimo": False, "nome": "Profissional de Teste", "contato": "profissional@hsm.test"}
ANONIMO = {**RELATO, "anonimo": True}

PUBLICO = "/api/nsp/publico/notificacoes"
PELO_MODULO = "/api/nsp/notificacoes"
ACOMPANHAMENTO = "/api/nsp/publico/acompanhamento"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Protocolo e origem pelo ponto de entrada
# ═══════════════════════════════════════════════════════════════════════════


def test_o_endereco_grava_sem_login_com_protocolo_e_origem_endereco():
    banco = _banco()

    resposta = _cliente(banco).post(PUBLICO, json={**IDENTIFICADO, "origem": "endereco"})

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["protocolo"] == f"NSP-{ANO}-0001"
    [gravada] = banco.notificacoes
    assert gravada["origem"] == "endereco"
    assert gravada["relato"] == RELATO["relato"]
    assert gravada["setor_id"] == SETOR["id"]
    assert gravada["notificante_nome"] == "Profissional de Teste"
    assert gravada["notificante_contato"] == "profissional@hsm.test"
    assert gravada["anonimo"] is False


def test_o_qr_grava_a_origem_qr_e_o_protocolo_segue_a_sequencia_do_ano():
    banco = _banco()
    cliente = _cliente(banco)

    primeira = cliente.post(PUBLICO, json={**IDENTIFICADO, "origem": "endereco"})
    segunda = cliente.post(PUBLICO, json={**ANONIMO, "origem": "qr"})

    assert primeira.json()["protocolo"] == f"NSP-{ANO}-0001"
    assert segunda.json()["protocolo"] == f"NSP-{ANO}-0002"
    assert [n["origem"] for n in banco.notificacoes] == ["endereco", "qr"]


@pytest.mark.parametrize("origem", ["modulo", "ouvidoria", "ronda", None])
def test_a_porta_publica_nao_aceita_outra_origem(origem):
    banco = _banco()

    resposta = _cliente(banco).post(PUBLICO, json={**IDENTIFICADO, "origem": origem})

    assert resposta.status_code == 422
    assert banco.notificacoes == []


@pytest.mark.parametrize(
    "mudanca",
    [
        {"setor_id": SETOR_DESATIVADO["id"]},
        {"setor_id": "33333333-3333-3333-3333-333333333333"},
        {"relato": "   "},
        {"data_ocorrencia": (HOJE + timedelta(days=1)).isoformat()},
        {"chegou_ao_paciente": "com_dano", "grave_ou_morte": None},
        {"contato": ""},
    ],
    ids=[
        "setor desativado",
        "setor que não existe",
        "relato vazio",
        "data futura",
        "dano sem gravidade",
        "sem contato",
    ],
)
def test_o_envio_incompleto_e_recusado_sem_gravar(mudanca):
    banco = _banco()

    resposta = _cliente(banco).post(PUBLICO, json={**IDENTIFICADO, "origem": "endereco", **mudanca})

    assert resposta.status_code == 422, resposta.text
    assert banco.notificacoes == []


@pytest.mark.parametrize(
    "pessoa",
    [SO_REUNIOES, SUPER_ADMIN, MEMBRO, DIRETOR],
    ids=["só nas Reuniões", "super admin sem Acesso pleno", "membro do Núcleo", "diretoria"],
)
def test_o_botao_do_modulo_vale_para_todo_logado_e_preenche_a_identificacao(pessoa):
    banco = _banco()

    resposta = _cliente(banco, pessoa).post(
        PELO_MODULO, json={**RELATO, "anonimo": False, "nome": "Outro nome", "contato": "outro@hsm.test"}
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["protocolo"] == f"NSP-{ANO}-0001"
    [gravada] = banco.notificacoes
    assert gravada["origem"] == "modulo"
    assert gravada["notificante_id"] == pessoa["id"]
    assert gravada["notificante_nome"] == pessoa["nome_completo"]
    assert gravada["notificante_contato"] == pessoa["email"]


def test_pelo_modulo_quem_escolhe_o_anonimato_nao_fica_ligado_a_notificacao():
    banco = _banco()

    resposta = _cliente(banco, SO_REUNIOES).post(PELO_MODULO, json=ANONIMO)

    assert resposta.status_code == 201, resposta.text
    assert "codigo_acompanhamento" in resposta.json()
    [gravada] = banco.notificacoes
    assert gravada["origem"] == "modulo"
    assert SO_REUNIOES["id"] not in str(banco.escritas)
    assert SO_REUNIOES["email"] not in str(banco.escritas)


def test_o_desligado_nao_notifica_pelo_modulo():
    banco = _banco()
    banco.tabelas["participantes"].append(_pessoa("P9", ativo=False))

    resposta = _cliente(banco, _pessoa("P9", ativo=False)).post(PELO_MODULO, json=ANONIMO)

    assert resposta.status_code == 403
    assert banco.notificacoes == []


def test_setor_fora_do_formato_e_recusado_sem_perguntar_ao_banco():
    banco = _banco()

    resposta = _cliente(banco).post(PUBLICO, json={**IDENTIFICADO, "origem": "endereco", "setor_id": "uti"})

    assert resposta.status_code == 422
    assert banco.notificacoes == []


@pytest.mark.parametrize(
    "falha",
    [
        APIError({"code": "57014", "message": "canceling statement due to statement timeout"}),
        httpx.ReadTimeout("o PostgREST não respondeu"),
    ],
    ids=["erro do banco", "timeout do PostgREST"],
)
def test_falha_ao_gravar_pede_para_tentar_de_novo_sem_detalhe_do_banco(falha, monkeypatch):
    banco = _banco()

    def _falhar(self):
        raise falha

    monkeypatch.setattr(_Consulta, "_inserir", _falhar)

    resposta = _cliente(banco).post(PUBLICO, json={**IDENTIFICADO, "origem": "endereco"})

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": "Não foi possível registrar a notificação agora. Tente de novo em instantes."}


def test_sem_dano_a_gravidade_nao_e_gravada():
    banco = _banco()

    _cliente(banco).post(
        PUBLICO, json={**IDENTIFICADO, "origem": "endereco", "chegou_ao_paciente": "nao", "grave_ou_morte": True}
    )

    assert banco.notificacoes[0]["grave_ou_morte"] is None


def test_com_dano_e_grave_a_gravidade_e_gravada():
    banco = _banco()

    _cliente(banco).post(
        PUBLICO, json={**IDENTIFICADO, "origem": "qr", "chegou_ao_paciente": "com_dano", "grave_ou_morte": True}
    )

    assert banco.notificacoes[0]["chegou_ao_paciente"] == "com_dano"
    assert banco.notificacoes[0]["grave_ou_morte"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 2. Anônima: o código uma vez, só o hash, nada do aparelho
# ═══════════════════════════════════════════════════════════════════════════


def test_a_anonima_recebe_o_codigo_uma_vez_e_o_banco_guarda_so_o_hash():
    banco = _banco()

    resposta = _cliente(banco).post(
        PUBLICO, json={**ANONIMO, "origem": "qr", "nome": "Não deveria ficar", "contato": "nao@hsm.test"}
    )

    assert resposta.status_code == 201, resposta.text
    codigo = resposta.json()["codigo_acompanhamento"]
    [gravada] = banco.notificacoes
    assert gravada["anonimo"] is True
    assert codigo_confere(codigo, gravada["codigo_acompanhamento_hash"])
    assert codigo not in str(banco.escritas)
    assert codigo.replace("-", "") not in str(banco.escritas)
    for campo in ("notificante_id", "notificante_nome", "notificante_contato"):
        assert gravada.get(campo) is None, campo
    assert "Não deveria ficar" not in str(banco.escritas)


def test_a_identificada_nao_recebe_codigo():
    resposta = _cliente(_banco()).post(PUBLICO, json={**IDENTIFICADO, "origem": "endereco"})

    assert "codigo_acompanhamento" not in resposta.json()


def test_nada_do_aparelho_e_gravado():
    banco = _banco()
    aparelho = {
        "User-Agent": "AparelhoDeTeste/9.9 (Android 14; Modelo XYZ-123)",
        "X-Forwarded-For": "203.0.113.77",
        "X-Real-IP": "203.0.113.77",
    }

    _cliente(banco).post(PUBLICO, json={**ANONIMO, "origem": "qr"}, headers=aparelho)
    _cliente(banco, SO_REUNIOES).post(PELO_MODULO, json=ANONIMO, headers=aparelho)

    assert len(banco.notificacoes) == 2
    escrito = str(banco.escritas)
    for vestigio in ("203.0.113.77", "AparelhoDeTeste", "XYZ-123", "testclient"):
        assert vestigio not in escrito, vestigio


def test_o_formulario_lista_so_os_setores_ativos_sem_login():
    resposta = _cliente(_banco()).get("/api/nsp/publico/setores")

    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"setores": [{"id": SETOR["id"], "nome": "UTI Adulto"}]}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Acompanhamento: só o estado, e a mesma recusa para todo dado errado
# ═══════════════════════════════════════════════════════════════════════════

NAO_ENCONTRADA = (
    "Não encontramos uma notificação com esses dados. Confira o protocolo e o código, "
    "ou o e-mail ou telefone que você deixou."
)


def _notificar(banco: _Banco, envio: dict) -> dict:
    return _cliente(banco).post(PUBLICO, json={**envio, "origem": "endereco"}).json()


def test_a_anonima_acompanha_pelo_protocolo_e_codigo_e_ve_so_o_estado():
    banco = _banco()
    recibo = _notificar(banco, ANONIMO)

    resposta = _cliente(banco).post(
        ACOMPANHAMENTO, json={"protocolo": recibo["protocolo"], "codigo": recibo["codigo_acompanhamento"].lower()}
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"protocolo": recibo["protocolo"], "estado": "Recebida"}


def test_a_identificada_acompanha_pelo_protocolo_e_contato():
    banco = _banco()
    recibo = _notificar(banco, IDENTIFICADO)

    resposta = _cliente(banco).post(
        ACOMPANHAMENTO, json={"protocolo": recibo["protocolo"], "contato": "PROFISSIONAL@hsm.test"}
    )

    assert resposta.json() == {"protocolo": recibo["protocolo"], "estado": "Recebida"}


@pytest.mark.parametrize(
    "estado,publico",
    [
        ("em_triagem", "Em análise"),
        ("classificada", "Em análise"),
        ("em_analise_agregada", "Em análise"),
        ("encaminhada", "Concluída"),
        ("fora_de_escopo", "Concluída"),
    ],
)
def test_o_estado_sai_em_palavras_simples(estado, publico):
    banco = _banco()
    recibo = _notificar(banco, IDENTIFICADO)
    banco.notificacoes[0]["estado"] = estado

    resposta = _cliente(banco).post(
        ACOMPANHAMENTO, json={"protocolo": recibo["protocolo"], "contato": "profissional@hsm.test"}
    )

    assert resposta.json()["estado"] == publico


def test_banco_fora_do_ar_no_acompanhamento_pede_para_tentar_de_novo(monkeypatch):
    def _falhar(self):
        raise httpx.ReadTimeout("o PostgREST não respondeu")

    monkeypatch.setattr(_Consulta, "execute", _falhar)

    resposta = _cliente(_banco()).post(ACOMPANHAMENTO, json={"protocolo": f"NSP-{ANO}-0001", "codigo": "AAAAA-BBBBB"})

    assert resposta.status_code == 503


def test_protocolo_com_codigo_ou_contato_errado_recebe_a_mesma_recusa():
    banco = _banco()
    anonima = _notificar(banco, ANONIMO)
    identificada = _notificar(banco, IDENTIFICADO)
    cliente = _cliente(banco)

    tentativas = [
        {"protocolo": anonima["protocolo"], "codigo": "AAAAA-BBBBB"},
        {"protocolo": anonima["protocolo"], "contato": "profissional@hsm.test"},
        {"protocolo": identificada["protocolo"], "contato": "outra@hsm.test"},
        {"protocolo": identificada["protocolo"], "codigo": anonima["codigo_acompanhamento"]},
        {"protocolo": f"NSP-{ANO}-9999", "codigo": anonima["codigo_acompanhamento"]},
    ]
    for consulta in tentativas:
        resposta = cliente.post(ACOMPANHAMENTO, json=consulta)
        assert resposta.status_code == 404, consulta
        assert resposta.json() == {"detail": NAO_ENCONTRADA}, consulta


# ═══════════════════════════════════════════════════════════════════════════
# 4. A lista de casos e a identidade de quem notificou
# ═══════════════════════════════════════════════════════════════════════════

LISTA = "/api/nsp/notificacoes"


def _com_duas_notificacoes() -> _Banco:
    banco = _banco()
    _notificar(banco, IDENTIFICADO)
    _notificar(banco, ANONIMO)
    return banco


@pytest.mark.parametrize("pessoa", [PRESIDENTE, DIRETOR_EXECUTIVO], ids=["Presidência", "Acesso pleno"])
def test_a_presidencia_e_o_acesso_pleno_veem_quem_notificou(pessoa):
    resposta = _cliente(_com_duas_notificacoes(), pessoa).get(LISTA)

    assert resposta.status_code == 200, resposta.text
    casos = resposta.json()["notificacoes"]
    assert [c["protocolo"] for c in casos] == [f"NSP-{ANO}-0002", f"NSP-{ANO}-0001"]
    identificada = casos[1]
    assert identificada["notificante"] == {"nome": "Profissional de Teste", "contato": "profissional@hsm.test"}
    assert identificada["setor"] == "UTI Adulto"
    assert identificada["estado"] == "recebida"
    assert identificada["origem"] == "endereco"
    assert casos[0]["notificante"] is None
    assert casos[0]["anonimo"] is True


def test_o_membro_com_termo_ve_os_casos_sem_quem_notificou():
    resposta = _cliente(_com_duas_notificacoes(), MEMBRO).get(LISTA)

    assert resposta.status_code == 200, resposta.text
    casos = resposta.json()["notificacoes"]
    assert len(casos) == 2
    assert "Profissional de Teste" not in resposta.text
    assert "profissional@hsm.test" not in resposta.text
    for caso in casos:
        assert "notificante" not in caso
        assert "anonimo" not in caso


def test_a_lista_traz_todos_os_casos_alem_de_uma_pagina(monkeypatch):
    """A tela diz "toda notificação que chegou ao Núcleo": a lista não pode
    parar no tamanho de uma página do banco e esconder as mais antigas."""
    from app.services.seguranca_do_paciente import notificacoes as servico

    monkeypatch.setattr(servico, "TAMANHO_DA_PAGINA", 2)
    banco = _banco()
    for _ in range(5):
        _notificar(banco, ANONIMO)

    resposta = _cliente(banco, PRESIDENTE).get(LISTA)

    assert resposta.status_code == 200, resposta.text
    protocolos = sorted(c["protocolo"] for c in resposta.json()["notificacoes"])
    assert protocolos == [f"NSP-{ANO}-{n:04d}" for n in range(1, 6)]


@pytest.mark.parametrize(
    "pessoa",
    [SUPER_ADMIN, SO_REUNIOES],
    ids=["super admin sem Acesso pleno", "só nas Reuniões"],
)
def test_quem_nao_tem_o_recurso_de_casos_recebe_recusa(pessoa):
    """A Diretoria lê os casos das faixas A e B (issue #1999): o teste dela
    mora em test_seguranca_do_paciente_suplente_em_exercicio."""
    resposta = _cliente(_com_duas_notificacoes(), pessoa).get(LISTA)

    assert resposta.status_code == 403
    assert resposta.json() == RECUSA_DO_CONTEUDO


# ═══════════════════════════════════════════════════════════════════════════
# 5. Limite de envios por aparelho
# ═══════════════════════════════════════════════════════════════════════════


# Sem o IP (ADR 0107, decisão 6), a conta é por rede: os computadores e o
# Wi-Fi do hospital saem pelo mesmo endereço, e o TestClient também manda
# tudo de um endereço só. O teto da rede precisa caber no hospital inteiro.
TETO_DA_REDE_POR_MINUTO = 30


def test_envio_repetido_da_mesma_rede_acima_do_teto_e_recusado():
    banco = _banco()
    cliente = _cliente(banco)

    respostas = [cliente.post(PUBLICO, json={**ANONIMO, "origem": "qr"}) for _ in range(TETO_DA_REDE_POR_MINUTO + 1)]

    assert [r.status_code for r in respostas[:-1]] == [201] * TETO_DA_REDE_POR_MINUTO
    assert respostas[-1].status_code == 429
    assert len(banco.notificacoes) == TETO_DA_REDE_POR_MINUTO


def test_vinte_envios_da_rede_do_hospital_nao_fecham_o_canal():
    """Antes o teto era 20 por hora para o endereço, e o hospital inteiro sai
    por um endereço só: vinte envios de qualquer pessoa fechavam o canal."""
    banco = _banco()
    cliente = _cliente(banco)

    respostas = [cliente.post(PUBLICO, json={**ANONIMO, "origem": "endereco"}) for _ in range(21)]

    assert [r.status_code for r in respostas] == [201] * 21


def test_o_botao_do_modulo_tambem_tem_limite():
    banco = _banco()
    cliente = _cliente(banco, SO_REUNIOES)

    respostas = [cliente.post(PELO_MODULO, json=ANONIMO) for _ in range(6)]

    assert respostas[5].status_code == 429
    assert len(banco.notificacoes) == 5


def test_o_botao_do_modulo_conta_por_pessoa_e_nao_pela_rede():
    """Duas pessoas no mesmo computador do hospital: o limite de uma não
    recusa a outra."""
    banco = _banco()
    for _ in range(5):
        assert _cliente(banco, SO_REUNIOES).post(PELO_MODULO, json=ANONIMO).status_code == 201
    assert _cliente(banco, SO_REUNIOES).post(PELO_MODULO, json=ANONIMO).status_code == 429

    resposta = _cliente(banco, MEMBRO).post(PELO_MODULO, json=ANONIMO)

    assert resposta.status_code == 201, resposta.text


def test_a_porta_publica_esgotada_nao_fecha_o_botao_do_modulo():
    """Quem esgota o teto das portas sem login não tranca quem está logado."""
    banco = _banco()
    publico = _cliente(banco)
    for _ in range(TETO_DA_REDE_POR_MINUTO):
        publico.post(PUBLICO, json={**ANONIMO, "origem": "qr"})
    assert publico.post(PUBLICO, json={**ANONIMO, "origem": "qr"}).status_code == 429

    resposta = _cliente(banco, SO_REUNIOES).post(PELO_MODULO, json=ANONIMO)

    assert resposta.status_code == 201, resposta.text


def test_tentar_adivinhar_o_codigo_tambem_tem_limite():
    banco = _banco()
    recibo = _notificar(banco, ANONIMO)
    cliente = _cliente(banco)

    respostas = [
        cliente.post(ACOMPANHAMENTO, json={"protocolo": recibo["protocolo"], "codigo": f"AAAAA-BBB{n:02d}"})
        for n in range(TETO_DA_REDE_POR_MINUTO + 1)
    ]

    assert respostas[-2].status_code == 404
    assert respostas[-1].status_code == 429


def test_as_rotas_sem_login_saem_do_log_sem_endereco():
    from app.services import limite_sem_ip

    for rota in notificacoes_router.router.routes:
        assert limite_sem_ip.rota_sem_endereco({"endpoint": rota.endpoint}), rota.path


# ═══════════════════════════════════════════════════════════════════════════
# 6. O texto do Produto no Kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def _secao_do_kit(titulo: str) -> str:
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "seguranca-do-paciente.md").read_text(encoding="utf-8")
    partes = texto.split(f"## {titulo}\n", 1)
    assert len(partes) == 2, f"a seção {titulo!r} sumiu do kit"
    return partes[1].split("\n## ", 1)[0]


class TestKitDeConhecimento:
    def test_a_notificacao_esta_no_que_ja_esta_no_ar(self):
        secao = _secao_do_kit("O que já está no ar")
        for termo in (
            "Notificar incidente",
            "sem login",
            "NSP-2026-0001",
            "código de acompanhamento",
            "Notificar não gera punição",
            "página de acompanhamento",
            "Notificações",
            "Diretor Executivo",
        ):
            assert termo in secao, termo

    def test_quem_ve_diz_que_todo_logado_tem_o_botao(self):
        secao = _secao_do_kit("Quem vê")
        assert "todo usuário logado" in secao
        assert "Notificar incidente" in secao
        assert "Os demais não veem o item." not in secao

    def test_o_que_ainda_nao_faz_deixa_de_dizer_que_a_notificacao_e_da_segunda_fase(self):
        secao = _secao_do_kit("O que ele ainda não faz")
        assert "A notificação de incidente e a triagem são da segunda fase." not in secao
        assert "triagem" in secao
