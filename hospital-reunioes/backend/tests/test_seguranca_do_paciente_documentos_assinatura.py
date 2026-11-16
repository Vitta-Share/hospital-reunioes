"""A assinatura eletrônica dos documentos do Núcleo (issue #1771, PRD #1764, ADR 0095).

Na tela Documentos, a Presidência e o Acesso pleno mandam para assinatura uma
versão nova do ato de designação (assina a Diretoria Executiva) ou do Regimento
e do Plano de Segurança do Paciente (assinam a Diretoria Executiva e a
Presidência). A versão só vira vigente quando todas as assinaturas chegam; até
lá a anterior continua valendo. O retorno da assinatura guarda o arquivo
assinado na versão, e quem lê Documentos baixa esse arquivo.

A assinatura eletrônica é sempre um dublê (a `_Assinatura` abaixo): nenhum
teste daqui fala com ela de verdade. O banco e o Storage são dublês em memória.
Nenhum nome nem e-mail de pessoa real: as pessoas daqui são de teste. O PDF é
gerado de verdade (WeasyPrint) e lido de volta com o pdfplumber.
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
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_documentos as documentos_router  # noqa: E402
from app.routers import seguranca_do_paciente_documentos_assinatura as assinatura_router  # noqa: E402
from app.routers import webhooks as webhooks_router  # noqa: E402
from app.services import clicksign_service  # noqa: E402
from app.services.seguranca_do_paciente import assinatura_dos_documentos, permissao  # noqa: E402

ENVIAR = "/api/nsp/documentos/assinatura"
SITUACAO = "/api/nsp/assinaturas-dos-documentos"
RECUSA_DO_CONTEUDO = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}
SEGREDO_DO_WEBHOOK = "segredo-de-teste"

HOJE = permissao.hoje_em_sao_paulo()
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}
ASSINADO = "2026-01-10T12:00:00+00:00"

TRAVESSAO, MEIA_RISCA = chr(0x2014), chr(0x2013)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _dia_fixo(monkeypatch):
    monkeypatch.setattr(permissao, "hoje_em_sao_paulo", lambda: HOJE)
    monkeypatch.setattr(assinatura_dos_documentos, "hoje_em_sao_paulo", lambda: HOJE)


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
    como a de verdade responderia. `falhar_em` derruba um passo; `assinaram`
    diz quem já assinou, para a reconsulta."""

    def __init__(self):
        self.chamadas: list[tuple] = []
        self.documentos: list[bytes] = []
        self.assinaram: set[str] = set()
        self.signatarios_fora = False
        self.falhar_em: str | None = None
        self.pdf_assinado: bytes | None = b"%PDF-1.4 assinado"
        self._n = 0
        self._por_envelope: dict[str, list[tuple[str, str, str]]] = {}

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
        if not self._passo("add_signer", envelope_id, nome, email):
            return None
        sid = f"sig-{envelope_id}-{len(self._por_envelope.setdefault(envelope_id, [])) + 1}"
        self._por_envelope[envelope_id].append((sid, nome, email))
        return sid

    def create_qualification_requirement(self, envelope_id, documento_id, signatario_id):
        return "req-q" if self._passo("create_qualification_requirement", envelope_id, signatario_id) else None

    def create_auth_requirement(self, envelope_id, documento_id, signatario_id):
        return "req-a" if self._passo("create_auth_requirement", envelope_id, signatario_id) else None

    def activate_envelope(self, envelope_id):
        return self._passo("activate_envelope", envelope_id)

    def notify_signers(self, envelope_id):
        return self._passo("notify_signers", envelope_id)

    def cancel_envelope(self, envelope_id):
        return self._passo("cancel_envelope", envelope_id)

    def list_signers(self, envelope_id):
        self._passo("list_signers", envelope_id)
        if self.signatarios_fora:
            return None
        return [
            {
                "signer_id": sid,
                "nome": nome,
                "email": email,
                "status": "signed" if sid in self.assinaram else "pending",
                "signed_at": ASSINADO if sid in self.assinaram else None,
            }
            for sid, nome, email in self._por_envelope.get(envelope_id, [])
        ]

    def get_signed_document(self, envelope_id):
        self._passo("get_signed_document", envelope_id)
        return self.pdf_assinado

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
        "list_signers",
        "get_signed_document",
    ):
        monkeypatch.setattr(clicksign_service, nome, getattr(dubla, nome))
    for nome in ("get_envelope_status", "list_envelope_events", "remind_signer", "find_envelope_id"):
        monkeypatch.setattr(clicksign_service, nome, _proibida(nome))
    return dubla


def _proibida(nome: str):
    def _explode(*_a, **_kw):
        raise AssertionError(f"{nome} não deveria ser chamada pela assinatura dos documentos")

    return _explode


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_COLUNAS_UUID = {("nsp_documentos", "id"), ("nsp_documentos_envios", "documento_id")}


class _Consulta:
    def __init__(self, banco: _Banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._filtros: list = []
        self._teto: int | None = None
        self._ordens: list[tuple] = []
        self._operacao = ("select", None)

    @property
    def _linhas(self) -> list[dict]:
        return self._banco.tabelas.setdefault(self._nome, [])

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        # O PostgREST recusa com 22P02 o filtro de texto que não é UUID numa
        # coluna UUID (link velho, URL digitada).
        if (self._nome, coluna) in _COLUNAS_UUID and not _UUID.match(str(valor)):
            raise APIError({"code": "22P02", "message": "invalid input syntax for type uuid"})
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
        self._ordens.append((coluna, desc))
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
                self._banco.relogio += 1
                nova = {
                    "id": str(uuid.uuid4()),
                    "created_at": f"{HOJE.isoformat()}T12:00:{self._banco.relogio:02d}+00:00",
                    **linha,
                }
                self._linhas.append(nova)
                gravadas.append(dict(nova))
            return SimpleNamespace(data=gravadas)
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if operacao == "update":
            for linha in casam:
                linha.update(carga)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        for coluna, desc in reversed(self._ordens):
            casam.sort(key=lambda linha: str(linha.get(coluna) or "").zfill(12), reverse=desc)
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)


class _Rpc:
    def __init__(self, dados):
        self._dados = dados

    def execute(self):
        return SimpleNamespace(data=self._dados)


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
    """O `rpc` faz o que as funções da migration 159 (e da 147) fazem."""

    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas
        self.storage = _Storage()
        self.relogio = 0
        self.chamadas_rpc: list[str] = []

    def table(self, nome: str):
        return _Consulta(self, nome)

    def _documentos(self) -> list[dict]:
        return self.tabelas.setdefault("nsp_documentos", [])

    def rpc(self, nome: str, params: dict):
        self.chamadas_rpc.append(nome)
        if nome in ("nsp_versao_para_assinatura", "nsp_publicar_documento"):
            tipo = params["p_tipo"]
            versao = max((d["versao"] for d in self._documentos() if d["tipo"] == tipo), default=0) + 1
            vigente = nome == "nsp_publicar_documento"
            if vigente:
                for d in self._documentos():
                    if d["tipo"] == tipo:
                        d["vigente"] = False
            novo = {
                "id": str(uuid.uuid4()),
                "tipo": tipo,
                "versao": versao,
                "titulo": params["p_titulo"],
                "texto": params["p_texto"],
                "natureza_revisao": params["p_natureza_revisao"],
                "vigente": vigente,
                "arquivo_assinado_path": None,
                "publicado_por": params["p_publicado_por"],
                "publicado_em": f"{HOJE.isoformat()}T13:00:00+00:00",
            }
            self._documentos().append(novo)
            return _Rpc(dict(novo))
        if nome == "nsp_tornar_vigente":
            doc = next((d for d in self._documentos() if d["id"] == params["p_documento_id"]), None)
            if doc is None:
                return _Rpc(None)
            if not doc["vigente"]:
                do_tipo = [d for d in self._documentos() if d["tipo"] == doc["tipo"]]
                if any(d["vigente"] and d["versao"] > doc["versao"] for d in do_tipo):
                    return _Rpc(None)
                for d in self._documentos():
                    if d["tipo"] == doc["tipo"]:
                        d["vigente"] = False
                doc["vigente"] = True
            return _Rpc(dict(doc))
        raise AssertionError(f"rpc inesperado: {nome}")


# ═══════════════════════════════════════════════════════════════════════════
# Cenário
# ═══════════════════════════════════════════════════════════════════════════


def _pessoa(pid: str, **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": f"Pessoa de Teste {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "cargo": "Cargo de teste",
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


# P1 é o Acesso pleno (a Diretoria Executiva); P2, a Presidência; P3, um membro
# com Termo; P4, um membro sem Termo; P5, o super admin; P6, a Diretoria.
ACESSO_PLENO = _pessoa("P1", perfil_nsp="acesso_pleno")
PRESIDENCIA = _pessoa("P2")
MEMBRO = _pessoa("P3")
SEM_TERMO = _pessoa("P4")
SUPER_ADMIN = _pessoa("P5", access_profile="super_admin", is_super_admin=True)
DIRETORIA = _pessoa("P6", role="diretor")

REGIMENTO_VIGENTE = {
    "id": "8d1f6a7e-0000-4000-8000-000000000001",
    "tipo": "regimento",
    "versao": 1,
    "titulo": "Regimento Interno do Núcleo",
    "texto": "Art. 1º Texto da versão 1.",
    "natureza_revisao": "material",
    "vigente": True,
    "arquivo_assinado_path": None,
    "publicado_por": "P2",
    "publicado_em": "2026-09-01T12:00:00+00:00",
}

TEXTO_NOVO = (
    f"Art. 1º O Núcleo de Segurança do Paciente {TRAVESSAO} instância consultiva {TRAVESSAO} reúne-se mensalmente.\n"
    f"Art. 2º O prazo de análise é de 10{MEIA_RISCA}15 dias corridos."
)


def _versao(tipo="regimento", **campos) -> dict[str, Any]:
    corpo = {
        "tipo": tipo,
        "titulo": "Revisão de teste",
        "texto": TEXTO_NOVO,
        "natureza_revisao": "material" if tipo == "regimento" else None,
    }
    return {**corpo, **campos}


class _Cenario:
    def __init__(self, quem: dict, *, participacoes: list[dict] | None = None, pessoas: list[dict] | None = None):
        if participacoes is None:
            participacoes = [
                _participacao("P2", papel="presidencia"),
                _participacao("P3"),
                _participacao("P4", termo=False),
            ]
        if pessoas is None:
            pessoas = [ACESSO_PLENO, PRESIDENCIA, MEMBRO, SEM_TERMO, SUPER_ADMIN, DIRETORIA]
        self.banco = _Banco(
            {
                "participantes": [dict(p) for p in pessoas],
                "colegiados": [dict(NUCLEO)],
                "participacoes": [dict(p) for p in participacoes],
                "nsp_documentos": [dict(REGIMENTO_VIGENTE)],
                "nsp_documentos_envios": [],
                "nsp_documentos_signatarios": [],
                "nsp_termos_envios": [],
                "reunioes": [],
                "pops_versoes": [],
            }
        )
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(documentos_router.router, prefix="/api")
        app.include_router(assinatura_router.router, prefix="/api")
        app.include_router(webhooks_router.router, prefix="/api")

        async def _usuario() -> dict[str, Any]:
            return {"id": quem["auth_user_id"], "email": quem["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        self.api = TestClient(app)

    def tabela(self, nome: str) -> list[dict]:
        return self.banco.tabelas.setdefault(nome, [])

    def documento(self, documento_id: str) -> dict:
        return next(d for d in self.tabela("nsp_documentos") if d["id"] == documento_id)

    def vigente(self, tipo: str) -> dict | None:
        return next((d for d in self.tabela("nsp_documentos") if d["tipo"] == tipo and d["vigente"]), None)

    def envios(self, documento_id: str) -> list[dict]:
        return [e for e in self.tabela("nsp_documentos_envios") if e["documento_id"] == documento_id]

    def signatarios(self, envio_id: str) -> list[dict]:
        return [s for s in self.tabela("nsp_documentos_signatarios") if s["envio_id"] == envio_id]

    def enviar(self, **campos) -> dict:
        resposta = self.api.post(ENVIAR, json=_versao(**campos))
        assert resposta.status_code == 201, resposta.text
        return resposta.json()

    def retorno_da_assinatura(self, documento_key: str, evento: str = "sign", signatario: str | None = None):
        corpo: dict[str, Any] = {"event": {"name": evento}, "document": {"key": documento_key}}
        if signatario:
            corpo["event"]["data"] = {"signer": {"key": signatario}}
        bruto = json.dumps(corpo).encode()
        assinatura = hmac_lib.new(SEGREDO_DO_WEBHOOK.encode(), bruto, hashlib.sha256).hexdigest()
        return self.api.post(
            "/api/webhooks/clicksign",
            content=bruto,
            headers={"content-hmac": f"sha256={assinatura}", "content-type": "application/json"},
        )


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA_DO_CONTEUDO


def _texto_do_pdf(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as documento:
        texto = "\n".join(pagina.extract_text() or "" for pagina in documento.pages)
    return re.sub(r"\s+", " ", texto)


def _signatarios_chamados(assinatura: _Assinatura) -> list[tuple[str, str]]:
    return [(c[2], c[3]) for c in assinatura.chamadas if c[0] == "add_signer"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Cada tipo vai para assinatura com os signatários certos
# ═══════════════════════════════════════════════════════════════════════════


class TestSignatariosDoTipo:
    def test_regimento_vai_para_a_diretoria_executiva_e_a_presidencia(self, assinatura):
        """Mutante: tirar a Presidência dos signatários do Regimento."""
        cenario = _Cenario(PRESIDENCIA)

        corpo = cenario.enviar(tipo="regimento")

        assert _signatarios_chamados(assinatura) == [
            ("Pessoa de Teste P1", "p1@hsm.test"),
            ("Pessoa de Teste P2", "p2@hsm.test"),
        ]
        assert assinatura.nomes().count("create_envelope") == 1
        assert assinatura.nomes().count("create_qualification_requirement") == 2
        assert "activate_envelope" in assinatura.nomes()
        [envio] = cenario.envios(corpo["documento"]["id"])
        assert envio["situacao"] == "enviado"
        assert envio["documento_key"] == "doc-env-1"
        assert sorted(
            (s["participante_id"], s["qualidade"], s["signatario_id"]) for s in cenario.signatarios(envio["id"])
        ) == [("P1", "diretoria_executiva", "sig-env-1-1"), ("P2", "presidencia", "sig-env-1-2")]

    def test_plano_vai_para_a_diretoria_executiva_e_a_presidencia(self, assinatura):
        cenario = _Cenario(ACESSO_PLENO)

        cenario.enviar(tipo="plano_seguranca_paciente")

        assert [nome for nome, _ in _signatarios_chamados(assinatura)] == ["Pessoa de Teste P1", "Pessoa de Teste P2"]

    def test_ato_de_designacao_vai_so_para_a_diretoria_executiva(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)

        corpo = cenario.enviar(tipo="ato_designacao")

        assert _signatarios_chamados(assinatura) == [("Pessoa de Teste P1", "p1@hsm.test")]
        [envio] = cenario.envios(corpo["documento"]["id"])
        assert [s["qualidade"] for s in cenario.signatarios(envio["id"])] == ["diretoria_executiva"]

    def test_quem_e_diretoria_executiva_e_presidencia_assina_uma_vez(self, assinatura):
        pessoas = [_pessoa("P1", perfil_nsp="acesso_pleno"), SUPER_ADMIN]
        cenario = _Cenario(pessoas[0], participacoes=[_participacao("P1", papel="presidencia")], pessoas=pessoas)

        cenario.enviar(tipo="regimento")

        assert _signatarios_chamados(assinatura) == [("Pessoa de Teste P1", "p1@hsm.test")]

    def test_o_pdf_tem_o_titulo_o_texto_sem_travessao_e_os_signatarios(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)

        cenario.enviar(tipo="regimento", titulo="Regimento Interno, revisão de teste")

        texto = _texto_do_pdf(assinatura.documentos[0])
        assert "Regimento Interno, revisão de teste" in texto
        assert "reúne-se mensalmente" in texto
        assert "10-15 dias corridos" in texto
        assert TRAVESSAO not in texto and MEIA_RISCA not in texto
        assert "Pessoa de Teste P1" in texto and "Pessoa de Teste P2" in texto

    def test_sem_presidencia_vigente_nada_e_criado(self, assinatura):
        cenario = _Cenario(ACESSO_PLENO, participacoes=[_participacao("P3")])

        resposta = cenario.api.post(ENVIAR, json=_versao(tipo="regimento"))

        assert resposta.status_code == 422, resposta.text
        assert "Presidência" in resposta.json()["detail"]
        assert assinatura.chamadas == []
        assert len(cenario.tabela("nsp_documentos")) == 1

    def test_sem_diretoria_executiva_nada_e_criado(self, assinatura):
        pessoas = [PRESIDENCIA, MEMBRO]
        cenario = _Cenario(PRESIDENCIA, pessoas=pessoas)

        resposta = cenario.api.post(ENVIAR, json=_versao(tipo="ato_designacao"))

        assert resposta.status_code == 422, resposta.text
        assert "Diretoria Executiva" in resposta.json()["detail"]
        assert assinatura.chamadas == []
        assert len(cenario.tabela("nsp_documentos")) == 1

    def test_signatario_sem_email_nada_e_criado(self, assinatura):
        pessoas = [_pessoa("P1", perfil_nsp="acesso_pleno", email=None), PRESIDENCIA]
        cenario = _Cenario(PRESIDENCIA, pessoas=pessoas)

        resposta = cenario.api.post(ENVIAR, json=_versao(tipo="ato_designacao"))

        assert resposta.status_code == 422, resposta.text
        assert "e-mail" in resposta.json()["detail"]
        assert assinatura.chamadas == []

    @pytest.mark.parametrize("tipo", ["termo", "ata", "outro"])
    def test_outros_tipos_nao_vao_para_assinatura_por_aqui(self, tipo, assinatura):
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.post(ENVIAR, json=_versao(tipo=tipo))

        assert resposta.status_code == 422
        assert assinatura.chamadas == []

    def test_sem_texto_nao_vai_para_assinatura(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.post(ENVIAR, json=_versao(tipo="ato_designacao", texto="   "))

        assert resposta.status_code == 422
        assert assinatura.chamadas == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. A versão só vira vigente quando todas as assinaturas chegam
# ═══════════════════════════════════════════════════════════════════════════


class TestVigenciaSoComTodasAsAssinaturas:
    def test_enquanto_ninguem_assina_a_anterior_continua_vigente(self):
        cenario = _Cenario(PRESIDENCIA)

        corpo = cenario.enviar(tipo="regimento")

        assert corpo["documento"]["vigente"] is False
        assert corpo["documento"]["versao"] == 2
        assert cenario.vigente("regimento")["id"] == REGIMENTO_VIGENTE["id"]

    def test_uma_assinatura_de_duas_nao_troca_a_vigente(self):
        """Mutante: concluir no primeiro `sign`, sem conferir os outros signatários."""
        cenario = _Cenario(PRESIDENCIA)
        corpo = cenario.enviar(tipo="regimento")

        resposta = cenario.retorno_da_assinatura("doc-env-1", "sign", signatario="sig-env-1-1")

        assert resposta.status_code == 200, resposta.text
        assert cenario.vigente("regimento")["id"] == REGIMENTO_VIGENTE["id"]
        [envio] = cenario.envios(corpo["documento"]["id"])
        assert envio["situacao"] == "enviado"
        assinou = {s["participante_id"]: s.get("assinado_em") for s in cenario.signatarios(envio["id"])}
        assert assinou["P1"] and assinou["P2"] is None

    def test_a_ultima_assinatura_troca_a_vigente_e_guarda_o_arquivo(self):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]

        cenario.retorno_da_assinatura("doc-env-1", "sign", signatario="sig-env-1-1")
        cenario.retorno_da_assinatura("doc-env-1", "sign", signatario="sig-env-1-2")

        assert cenario.vigente("regimento")["id"] == novo["id"]
        assert cenario.documento(REGIMENTO_VIGENTE["id"])["vigente"] is False
        [envio] = cenario.envios(novo["id"])
        assert envio["situacao"] == "assinado"
        caminho = cenario.documento(novo["id"])["arquivo_assinado_path"]
        assert caminho
        assert cenario.banco.storage.arquivos[(settings.supabase_storage_bucket_nsp_documentos, caminho)] == (
            b"%PDF-1.4 assinado"
        )

    def test_auto_close_conclui_com_todos_assinados(self):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="plano_seguranca_paciente")["documento"]

        cenario.retorno_da_assinatura("doc-env-1", "auto_close")

        assert cenario.vigente("plano_seguranca_paciente")["id"] == novo["id"]
        [envio] = cenario.envios(novo["id"])
        assert all(s.get("assinado_em") for s in cenario.signatarios(envio["id"]))

    @pytest.mark.parametrize("evento", ["close", "deadline", "refusal", "cancel", "signature_started"])
    def test_evento_que_nao_garante_todas_as_assinaturas_nao_troca_a_vigente(self, evento):
        cenario = _Cenario(PRESIDENCIA)
        cenario.enviar(tipo="regimento")

        assert cenario.retorno_da_assinatura("doc-env-1", evento).status_code == 200

        assert cenario.vigente("regimento")["id"] == REGIMENTO_VIGENTE["id"]

    def test_evento_repetido_nao_duplica_nada(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="ato_designacao")["documento"]

        for evento in ("sign", "sign", "auto_close", "document_closed"):
            assert cenario.retorno_da_assinatura("doc-env-1", evento, signatario="sig-env-1-1").status_code == 200

        assert cenario.vigente("ato_designacao")["id"] == novo["id"]
        assert assinatura.nomes().count("get_signed_document") == 1

    def test_pdf_ainda_nao_pronto_entra_no_document_closed(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="ato_designacao")["documento"]
        assinatura.pdf_assinado = None

        cenario.retorno_da_assinatura("doc-env-1", "sign", signatario="sig-env-1-1")

        assert cenario.vigente("ato_designacao")["id"] == novo["id"]
        assert cenario.documento(novo["id"])["arquivo_assinado_path"] is None
        assinatura.pdf_assinado = b"%PDF-1.4 assinado"

        cenario.retorno_da_assinatura("doc-env-1", "document_closed")

        assert cenario.documento(novo["id"])["arquivo_assinado_path"]

    def test_assinatura_atrasada_de_versao_antiga_nao_derruba_a_mais_nova(self):
        """A Presidência publicou uma versão mais nova (vigente na hora) antes
        de a versão enviada terminar de assinar."""
        cenario = _Cenario(PRESIDENCIA)
        enviada = cenario.enviar(tipo="regimento")["documento"]
        publicada = cenario.api.post(
            "/api/nsp/documentos", json={**_versao(tipo="regimento"), "natureza_revisao": "redacao"}
        ).json()

        cenario.retorno_da_assinatura("doc-env-1", "auto_close")

        assert cenario.vigente("regimento")["id"] == publicada["id"]
        assert cenario.documento(enviada["id"])["vigente"] is False

    def test_versao_nova_para_assinatura_cancela_a_que_esperava(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)
        primeira = cenario.enviar(tipo="regimento")["documento"]

        cenario.enviar(tipo="regimento")

        [envio_antigo] = cenario.envios(primeira["id"])
        assert envio_antigo["situacao"] == "cancelado"
        assert ("cancel_envelope", "env-1") in assinatura.chamadas
        cenario.retorno_da_assinatura("doc-env-1", "auto_close")
        assert cenario.vigente("regimento")["id"] == REGIMENTO_VIGENTE["id"]

    def test_o_termo_continua_usando_o_regimento_vigente_ate_a_assinatura(self):
        """O Termo de Adesão lê o Regimento vigente: a versão em assinatura
        não entra no Termo de quem for cadastrado agora."""
        from app.services.seguranca_do_paciente import termo

        cenario = _Cenario(PRESIDENCIA)
        cenario.enviar(tipo="regimento")

        assert termo._vigente(cenario.banco, "regimento")["id"] == REGIMENTO_VIGENTE["id"]


# ═══════════════════════════════════════════════════════════════════════════
# 3. O arquivo assinado fica na versão e baixa quem tem acesso
# ═══════════════════════════════════════════════════════════════════════════


def _assinado(cenario: _Cenario) -> dict:
    novo = cenario.enviar(tipo="ato_designacao")["documento"]
    cenario.retorno_da_assinatura("doc-env-1", "auto_close")
    return novo


class TestArquivoAssinado:
    @pytest.mark.parametrize("quem", [ACESSO_PLENO, PRESIDENCIA, MEMBRO], ids=["acesso_pleno", "presidencia", "membro"])
    def test_quem_le_documentos_baixa_o_arquivo_assinado(self, quem):
        cenario = _Cenario(PRESIDENCIA)
        novo = _assinado(cenario)
        cenario_de_quem = cenario
        cenario_de_quem.api.app.dependency_overrides[get_current_user] = _usuario_de(quem)

        resposta = cenario_de_quem.api.get(f"/api/nsp/documentos/{novo['id']}/arquivo-assinado")

        assert resposta.status_code == 200, resposta.text
        caminho = cenario.documento(novo["id"])["arquivo_assinado_path"]
        assert resposta.json()["url"] == (
            f"https://storage.test/{settings.supabase_storage_bucket_nsp_documentos}/{caminho}?token=t"
        )

    def test_a_lista_marca_a_versao_com_arquivo_assinado(self):
        cenario = _Cenario(PRESIDENCIA)
        novo = _assinado(cenario)

        lista = cenario.api.get("/api/nsp/documentos").json()["documentos"]

        assert next(d for d in lista if d["id"] == novo["id"])["tem_arquivo_assinado"] is True

    @pytest.mark.parametrize("quem", [SUPER_ADMIN, DIRETORIA, SEM_TERMO], ids=["super_admin", "diretoria", "sem_termo"])
    def test_quem_nao_le_documentos_nao_baixa(self, quem):
        cenario = _Cenario(PRESIDENCIA)
        novo = _assinado(cenario)
        cenario.api.app.dependency_overrides[get_current_user] = _usuario_de(quem)

        _assert_recusado(cenario.api.get(f"/api/nsp/documentos/{novo['id']}/arquivo-assinado"))

    @pytest.mark.parametrize("quem", [MEMBRO, PRESIDENCIA, ACESSO_PLENO], ids=["membro", "presidencia", "acesso_pleno"])
    def test_termo_assinado_de_outro_membro_nao_baixa_por_aqui(self, quem):
        """O Termo de Adesão assinado tem arquivo no mesmo bucket, mas só sai pela
        ficha do membro (`gerir_nucleo`). Mutante: tirar a conferência do tipo
        da rota (viraria 200 com o link do Termo de outra pessoa)."""
        cenario = _Cenario(quem)
        cenario.tabela("nsp_documentos").append(
            {
                **REGIMENTO_VIGENTE,
                "id": "8d1f6a7e-0000-4000-8000-0000000000a1",
                "tipo": "termo",
                "titulo": "Termo de Adesão de Pessoa de Teste P4",
                "natureza_revisao": None,
                "arquivo_assinado_path": "termos/env-termo-assinado.pdf",
            }
        )
        balde = settings.supabase_storage_bucket_nsp_documentos
        cenario.banco.storage.arquivos[(balde, "termos/env-termo-assinado.pdf")] = b"%PDF termo"

        resposta = cenario.api.get("/api/nsp/documentos/8d1f6a7e-0000-4000-8000-0000000000a1/arquivo-assinado")

        assert resposta.status_code == 404, resposta.text
        assert "url" not in resposta.json()

    def test_versao_sem_arquivo_assinado_da_404(self):
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.get(f"/api/nsp/documentos/{REGIMENTO_VIGENTE['id']}/arquivo-assinado")

        assert resposta.status_code == 404

    @pytest.mark.parametrize("documento_id", ["nao-e-uuid", "8d1f6a7e-0000-4000-8000-0000000000ff"])
    def test_id_que_nao_existe_da_404(self, documento_id):
        """Mutante: tirar o tratamento do 22P02 da rota (viraria 500 ou 503)."""
        cenario = _Cenario(PRESIDENCIA)

        resposta = cenario.api.get(f"/api/nsp/documentos/{documento_id}/arquivo-assinado")

        assert resposta.status_code == 404, resposta.text


def _usuario_de(quem: dict):
    async def _usuario() -> dict[str, Any]:
        return {"id": quem["auth_user_id"], "email": quem["email"], "metadata": {}}

    return _usuario


# ═══════════════════════════════════════════════════════════════════════════
# 4. Reconsultar status e reenviar
# ═══════════════════════════════════════════════════════════════════════════


def _reconsultar(cenario: _Cenario, documento_id: str):
    return cenario.api.post(f"/api/nsp/documentos/{documento_id}/assinatura/reconsultar")


def _reenviar(cenario: _Cenario, documento_id: str):
    return cenario.api.post(f"/api/nsp/documentos/{documento_id}/assinatura/reenviar")


class TestReconsultar:
    def test_reconsulta_marca_quem_assinou_sem_trocar_a_vigente(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]
        assinatura.assinaram = {"sig-env-1-2"}

        resposta = _reconsultar(cenario, novo["id"])

        assert resposta.status_code == 200, resposta.text
        assinaturas = {s["nome"]: s["assinado_em"] for s in resposta.json()["signatarios"]}
        assert assinaturas == {"Pessoa de Teste P1": None, "Pessoa de Teste P2": ASSINADO}
        assert cenario.vigente("regimento")["id"] == REGIMENTO_VIGENTE["id"]

    def test_reconsulta_com_todos_assinados_troca_a_vigente(self, assinatura):
        """Mutante: a reconsulta não concluir o envio quando todos assinaram."""
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]
        assinatura.assinaram = {"sig-env-1-1", "sig-env-1-2"}

        resposta = _reconsultar(cenario, novo["id"])

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["situacao"] == "assinado"
        assert cenario.vigente("regimento")["id"] == novo["id"]
        assert cenario.documento(novo["id"])["arquivo_assinado_path"]

    def test_reconsulta_completa_a_vigencia_que_falhou_depois_da_troca(self, assinatura):
        """O envio ficou "assinado" e a troca da vigente não chegou ao banco."""
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]
        [envio] = cenario.envios(novo["id"])
        envio["situacao"] = "assinado"
        assinatura.assinaram = {"sig-env-1-1", "sig-env-1-2"}

        assert _reconsultar(cenario, novo["id"]).status_code == 200

        assert cenario.vigente("regimento")["id"] == novo["id"]

    def test_assinatura_fora_do_ar_na_reconsulta_da_503(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]
        assinatura.signatarios_fora = True

        resposta = _reconsultar(cenario, novo["id"])

        assert resposta.status_code == 503
        assert cenario.vigente("regimento")["id"] == REGIMENTO_VIGENTE["id"]

    def test_versao_sem_envio_na_reconsulta_da_409(self):
        cenario = _Cenario(PRESIDENCIA)

        resposta = _reconsultar(cenario, REGIMENTO_VIGENTE["id"])

        assert resposta.status_code == 409

    @pytest.mark.parametrize("documento_id", ["nao-e-uuid", "8d1f6a7e-0000-4000-8000-0000000000ff"])
    def test_id_que_nao_existe_na_reconsulta_da_404(self, documento_id):
        cenario = _Cenario(PRESIDENCIA)

        assert _reconsultar(cenario, documento_id).status_code == 404
        assert _reenviar(cenario, documento_id).status_code == 404


class TestFalhaAntesDoCarimbo:
    def test_assinatura_fora_do_ar_deixa_a_versao_esperando_e_avisa(self, assinatura):
        assinatura.falhar_em = "activate_envelope"
        cenario = _Cenario(PRESIDENCIA)

        corpo = cenario.enviar(tipo="regimento")

        assert "Reenviar" in corpo["aviso"]
        assert corpo["assinatura"]["situacao"] == "gerado"
        assert corpo["assinatura"]["pode_reenviar"] is True
        assert cenario.vigente("regimento")["id"] == REGIMENTO_VIGENTE["id"]

    def test_o_reenvio_aparece_na_tela_e_a_rota_aceita(self, assinatura):
        assinatura.falhar_em = "activate_envelope"
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]
        assinatura.falhar_em = None

        situacao = cenario.api.get(SITUACAO).json()["assinaturas"]
        [desta] = [a for a in situacao if a["documento_id"] == novo["id"]]
        assert desta["pode_reenviar"] is True

        resposta = _reenviar(cenario, novo["id"])

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["situacao"] == "enviado"
        envios = cenario.envios(novo["id"])
        assert sorted(e["situacao"] for e in envios) == ["cancelado", "enviado"]

    def test_reenvio_cancela_o_envelope_aberto(self, assinatura):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]

        assert _reenviar(cenario, novo["id"]).status_code == 200

        assert ("cancel_envelope", "env-1") in assinatura.chamadas
        cenario.retorno_da_assinatura("doc-env-1", "auto_close")
        assert cenario.vigente("regimento")["id"] == REGIMENTO_VIGENTE["id"]
        cenario.retorno_da_assinatura("doc-env-2", "auto_close")
        assert cenario.vigente("regimento")["id"] == novo["id"]

    def test_versao_vigente_ou_assinada_nao_se_reenvia(self):
        cenario = _Cenario(PRESIDENCIA)
        novo = _assinado(cenario)

        assert _reenviar(cenario, novo["id"]).status_code == 409
        assert _reenviar(cenario, REGIMENTO_VIGENTE["id"]).status_code == 409

    def test_versao_com_outra_mais_nova_nao_se_reenvia(self):
        cenario = _Cenario(PRESIDENCIA)
        primeira = cenario.enviar(tipo="regimento")["documento"]
        cenario.enviar(tipo="regimento")

        assert _reenviar(cenario, primeira["id"]).status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# 5. A tela mostra quem já assinou
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemJaAssinou:
    def test_a_tela_mostra_quem_assinou_e_quem_falta(self):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]
        cenario.retorno_da_assinatura("doc-env-1", "sign", signatario="sig-env-1-2")

        resposta = cenario.api.get(SITUACAO)

        assert resposta.status_code == 200, resposta.text
        [desta] = [a for a in resposta.json()["assinaturas"] if a["documento_id"] == novo["id"]]
        assert desta["situacao"] == "enviado"
        assert desta["pode_reenviar"] is True
        por_nome = {s["nome"]: s for s in desta["signatarios"]}
        assert por_nome["Pessoa de Teste P1"]["qualidade"] == "diretoria_executiva"
        assert por_nome["Pessoa de Teste P1"]["assinado_em"] is None
        assert por_nome["Pessoa de Teste P2"]["qualidade"] == "presidencia"
        assert por_nome["Pessoa de Teste P2"]["assinado_em"]
        assert "email" not in por_nome["Pessoa de Teste P1"]

    def test_o_membro_com_termo_le_a_situacao(self):
        cenario = _Cenario(PRESIDENCIA)
        cenario.enviar(tipo="regimento")
        cenario.api.app.dependency_overrides[get_current_user] = _usuario_de(MEMBRO)

        assert cenario.api.get(SITUACAO).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 6. Quem manda para assinatura: a Presidência e o Acesso pleno, e mais ninguém
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemAlcanca:
    @pytest.mark.parametrize(
        "quem", [SUPER_ADMIN, DIRETORIA, MEMBRO, SEM_TERMO], ids=["super_admin", "diretoria", "membro", "sem_termo"]
    )
    def test_quem_nao_gere_o_nucleo_nao_envia_nem_reconsulta_nem_reenvia(self, quem, assinatura):
        cenario = _Cenario(PRESIDENCIA)
        novo = cenario.enviar(tipo="regimento")["documento"]
        chamadas = list(assinatura.chamadas)
        cenario.api.app.dependency_overrides[get_current_user] = _usuario_de(quem)

        _assert_recusado(cenario.api.post(ENVIAR, json=_versao(tipo="regimento")))
        _assert_recusado(_reconsultar(cenario, novo["id"]))
        _assert_recusado(_reenviar(cenario, novo["id"]))
        assert assinatura.chamadas == chamadas

    @pytest.mark.parametrize("quem", [SUPER_ADMIN, DIRETORIA, SEM_TERMO], ids=["super_admin", "diretoria", "sem_termo"])
    def test_quem_nao_le_documentos_nao_ve_a_situacao(self, quem):
        cenario = _Cenario(PRESIDENCIA)
        cenario.api.app.dependency_overrides[get_current_user] = _usuario_de(quem)

        _assert_recusado(cenario.api.get(SITUACAO))
