"""O Termo de Adesão do Núcleo (issue #1768, PRD #1764, ADR 0095).

Cadastrar o membro gera um documento só (o Termo preenchido e o Regimento
vigente na íntegra) e o manda para a assinatura eletrônica com um signatário.
O retorno da assinatura deixa o membro Ativo sozinho; a Presidência reconsulta,
reenvia ou libera à mão, com justificativa.

A assinatura eletrônica é sempre um dublê (a `_Assinatura` abaixo): nenhum
teste daqui fala com ela de verdade. O banco e o Storage são dublês em memória.
Nenhum nome, registro ou e-mail de pessoa real: as pessoas daqui são de teste.
O PDF é gerado de verdade (WeasyPrint) e lido de volta com o pdfplumber.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_lib
import io
import json
import os
import re
import sys
import uuid
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pdfplumber
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_membros as membros_router  # noqa: E402
from app.routers import seguranca_do_paciente_termo as termo_router  # noqa: E402
from app.routers import webhooks as webhooks_router  # noqa: E402
from app.services import clicksign_service  # noqa: E402
from app.services.seguranca_do_paciente import permissao  # noqa: E402

ROTA = "/api/nsp/membros"
RECUSA_DO_CONTEUDO = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}
SEGREDO_DO_WEBHOOK = "segredo-de-teste"

HOJE = permissao.hoje_em_sao_paulo()
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}
ASSINADO = "2026-01-10T12:00:00+00:00"

# O Regimento de teste traz travessão e meia-risca de propósito: o PDF não pode
# sair com nenhum dos dois.
TEXTO_DO_REGIMENTO = (
    "Art. 1º O Núcleo de Segurança do Paciente — instância consultiva — reúne-se mensalmente.\n"
    "Art. 2º O prazo de análise é de 10–15 dias corridos."
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _dia_fixo(monkeypatch):
    monkeypatch.setattr(membros_router, "hoje_em_sao_paulo", lambda: HOJE)
    monkeypatch.setattr(termo_router, "hoje_em_sao_paulo", lambda: HOJE)
    monkeypatch.setattr(permissao, "hoje_em_sao_paulo", lambda: HOJE)


@pytest.fixture(autouse=True)
def _segredo_do_webhook(monkeypatch):
    monkeypatch.setattr(settings, "clicksign_webhook_secret", SEGREDO_DO_WEBHOOK)


def _iso(delta: int) -> str:
    return (HOJE + timedelta(days=delta)).isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# Dublês
# ═══════════════════════════════════════════════════════════════════════════


class _Assinatura:
    """A assinatura eletrônica de mentira: anota cada chamada e responde
    como a de verdade responderia. `falhar_em` derruba um passo."""

    def __init__(self):
        self.chamadas: list[tuple] = []
        self.documentos: list[bytes] = []
        self.status: str | None = "running"
        self.falhar_em: str | None = None
        self._n = 0

    def _passo(self, nome: str, *args):
        self.chamadas.append((nome, *args))
        return self.falhar_em != nome

    def create_envelope(self, nome):
        self._n += 1
        return f"env-{self._n}" if self._passo("create_envelope", nome) else None

    def add_document(self, envelope_id, pdf, nome_do_arquivo):
        self.documentos.append(pdf)
        return f"doc-{envelope_id}" if self._passo("add_document", envelope_id, nome_do_arquivo) else None

    def add_signer(self, envelope_id, nome, email):
        return f"sig-{envelope_id}" if self._passo("add_signer", envelope_id, nome, email) else None

    def create_qualification_requirement(self, envelope_id, documento_id, signatario_id):
        return "req-q" if self._passo("create_qualification_requirement", envelope_id) else None

    def create_auth_requirement(self, envelope_id, documento_id, signatario_id):
        return "req-a" if self._passo("create_auth_requirement", envelope_id) else None

    def activate_envelope(self, envelope_id):
        return self._passo("activate_envelope", envelope_id)

    def notify_signers(self, envelope_id):
        return self._passo("notify_signers", envelope_id)

    def cancel_envelope(self, envelope_id):
        return self._passo("cancel_envelope", envelope_id)

    def get_envelope_status(self, envelope_id):
        self._passo("get_envelope_status", envelope_id)
        return self.status

    def get_signed_document(self, envelope_id):
        self._passo("get_signed_document", envelope_id)
        return b"%PDF-1.4 assinado"

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


@pytest.fixture(autouse=True)
def assinatura(monkeypatch) -> _Assinatura:
    """Toda função da assinatura eletrônica que o módulo usa vira dublê. A que
    não estiver aqui explode: nenhum teste chega à assinatura de verdade."""
    dubla = _Assinatura()
    for nome in (
        "create_envelope",
        "add_document",
        "add_signer",
        "create_qualification_requirement",
        "create_auth_requirement",
        "activate_envelope",
        "notify_signers",
        "cancel_envelope",
        "get_envelope_status",
        "get_signed_document",
    ):
        monkeypatch.setattr(clicksign_service, nome, getattr(dubla, nome))
    return dubla


class _Consulta:
    def __init__(self, banco: _Banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._filtros: list = []
        self._teto: int | None = None
        self._ordem: tuple | None = None
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

    def order(self, coluna, desc=False):
        self._ordem = (coluna, desc)
        return self

    def limit(self, n):
        self._teto = n
        return self

    def insert(self, linha):
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
            gravadas = []
            for linha in carga if isinstance(carga, list) else [carga]:
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
        if self._ordem:
            coluna, desc = self._ordem
            casam.sort(key=lambda linha: str(linha.get(coluna) or ""), reverse=desc)
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)


class _Balde:
    def __init__(self, arquivos: dict, nome: str):
        self._arquivos = arquivos
        self._nome = nome

    def upload(self, caminho, conteudo, _opcoes=None):
        self._arquivos[(self._nome, caminho)] = conteudo

    def create_signed_url(self, caminho, _segundos):
        assert (self._nome, caminho) in self._arquivos
        return {"signedURL": f"https://storage.test/{self._nome}/{caminho}?token=t"}


class _Storage:
    def __init__(self):
        self.arquivos: dict[tuple[str, str], bytes] = {}

    def from_(self, nome):
        return _Balde(self.arquivos, nome)


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas
        self.storage = _Storage()

    def table(self, nome: str):
        return _Consulta(self, nome)


# ═══════════════════════════════════════════════════════════════════════════
# Cenário
# ═══════════════════════════════════════════════════════════════════════════


def _pessoa(pid: str, **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": f"Pessoa de Teste {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "cargo": "Enfermeira de teste",
        "area": None,
        "setor": "Setor de teste",
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


def _participacao(pid: str, *, papel="membro", termo=True, **campos) -> dict[str, Any]:
    return {
        "id": f"part-{pid}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": pid,
        "papel": papel,
        "area": "UTI adulto",
        "vigencia_inicio": _iso(-30),
        "vigencia_fim": _iso(300),
        "encerrada_em": None,
        "termo_assinado_em": ASSINADO if termo else None,
        **campos,
    }


# P1 é o Acesso pleno; P2, a Presidência; P3, um membro com Termo; P4, a pessoa
# cadastrada nos testes; P5, o super admin; P6, a Diretoria.
ACESSO_PLENO = _pessoa("P1", perfil_nsp="acesso_pleno")
PRESIDENCIA = _pessoa("P2")
MEMBRO = _pessoa("P3")
NOVA = _pessoa("P4")
SUPER_ADMIN = _pessoa("P5", access_profile="super_admin", is_super_admin=True)
DIRETORIA = _pessoa("P6", role="diretor")

REGIMENTO = {
    "id": "doc-regimento-2",
    "tipo": "regimento",
    "versao": 2,
    "titulo": "Regimento Interno do Núcleo",
    "texto": TEXTO_DO_REGIMENTO,
    "natureza_revisao": "material",
    "vigente": True,
    "publicado_por": "P2",
    "publicado_em": "2026-09-01T12:00:00+00:00",
}

NOVO = {
    "participante_id": "P4",
    "papel": "membro",
    "area": "Farmácia",
    "vigencia_inicio": _iso(0),
    "vigencia_fim": _iso(365),
    "conselho_profissional": "CRF",
    "registro_profissional": "000444",
    "registro_uf": "rj",
}


class _Cenario:
    def __init__(self, quem: dict, participacoes: list[dict] | None = None, *, regimento: bool = True):
        if participacoes is None:
            participacoes = [_participacao("P2", papel="presidencia"), _participacao("P3")]
        self.banco = _Banco(
            {
                "participantes": [dict(p) for p in (ACESSO_PLENO, PRESIDENCIA, MEMBRO, NOVA, SUPER_ADMIN, DIRETORIA)],
                "colegiados": [dict(NUCLEO)],
                "participacoes": [dict(p) for p in participacoes],
                "participacoes_trilha": [],
                "nsp_documentos": [dict(REGIMENTO)] if regimento else [],
                "nsp_termos_envios": [],
                "reunioes": [],
                "pops_versoes": [],
            }
        )
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(membros_router.router, prefix="/api")
        app.include_router(termo_router.router, prefix="/api")
        app.include_router(webhooks_router.router, prefix="/api")

        async def _usuario() -> dict[str, Any]:
            return {"id": quem["auth_user_id"], "email": quem["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        self.api = TestClient(app)

    def tabela(self, nome: str) -> list[dict]:
        return self.banco.tabelas.setdefault(nome, [])

    def participacao(self, pid: str) -> dict:
        return next(p for p in self.tabela("participacoes") if p["participante_id"] == pid)

    def envios(self, pid: str) -> list[dict]:
        part = self.participacao(pid)["id"]
        return [e for e in self.tabela("nsp_termos_envios") if e["participacao_id"] == part]

    def trilha(self, acao: str) -> list[dict]:
        return [t for t in self.tabela("participacoes_trilha") if t["acao"] == acao]

    def estado(self, pid: str) -> str:
        part = self.participacao(pid)["id"]
        return next(m for m in self.api.get(ROTA).json()["membros"] if m["id"] == part)["estado"]

    def retorno_da_assinatura(self, documento_key: str, evento: str = "sign"):
        corpo = json.dumps({"event": {"name": evento}, "document": {"key": documento_key}}).encode()
        assinatura = hmac_lib.new(SEGREDO_DO_WEBHOOK.encode(), corpo, hashlib.sha256).hexdigest()
        return self.api.post(
            "/api/webhooks/clicksign",
            content=corpo,
            headers={"content-hmac": f"sha256={assinatura}", "content-type": "application/json"},
        )

    def cadastrar(self) -> dict:
        resposta = self.api.post(ROTA, json=NOVO)
        assert resposta.status_code == 201, resposta.text
        return resposta.json()


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA_DO_CONTEUDO


def _texto_do_pdf(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as documento:
        texto = "\n".join(pagina.extract_text() or "" for pagina in documento.pages)
    return re.sub(r"\s+", " ", texto)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Cadastrar gera um documento só e o envia com um signatário
# ═══════════════════════════════════════════════════════════════════════════


class TestCadastroGeraEEnvia:
    def test_cadastro_gera_um_documento_com_termo_e_regimento_e_envia_com_um_signatario(self, assinatura):
        """Mutante: não chamar o envio do Termo no cadastro."""
        cenario = _Cenario(PRESIDENCIA)

        corpo = cenario.cadastrar()

        assert corpo["estado"] == "aguardando_assinatura"
        assert assinatura.nomes().count("create_envelope") == 1
        assert assinatura.nomes().count("add_document") == 1
        signatarios = [c for c in assinatura.chamadas if c[0] == "add_signer"]
        assert signatarios == [("add_signer", "env-1", "Pessoa de Teste P4", "p4@hsm.test")]
        assert "activate_envelope" in assinatura.nomes()
        texto = _texto_do_pdf(assinatura.documentos[0])
        assert "TERMO DE ADESÃO" in texto.upper()
        assert "Pessoa de Teste P4" in texto
        assert "reúne-se mensalmente" in texto
        assert "O prazo de análise é de 10-15 dias corridos" in texto
        [envio] = cenario.envios("P4")
        assert envio["situacao"] == "enviado"
        assert envio["documento_key"] == "doc-env-1"
        assert envio["regimento_id"] == REGIMENTO["id"]
