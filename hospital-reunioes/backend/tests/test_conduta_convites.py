"""O convite do apurador e do membro da CIPA, dentro do caso (issue #1825, PRD
#1786, ADR 0097, decisão 12; especificação, seções 3.2, 6.4 e 10).

Na tela do caso, a coordenação (ou o Grupo Especial, no caso dele) convida
uma pessoa por e-mail. Quem não tem login ganha um cadastro mínimo, sem outro
módulo. O convidado recebe o termo de confidencialidade pela ClickSign e só
abre o caso, e só aquele, depois de assinar. O super admin não participa nem
é avisado.

A ClickSign, o login e o e-mail são dublês: o `.env` local carrega credencial
de produção, e o `httpx` explode se alguém tentar sair para a rede.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_lib
import json
import os
import secrets
import sys
from datetime import timedelta
from typing import Any

import httpx
import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import conduta_comite, conduta_convites, webhooks  # noqa: E402
from app.services import auth_provisioning, clicksign_service  # noqa: E402
from app.services.conduta import assinaturas, casos, convites  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402

ROTA_DOS_CASOS = "/api/comite-de-conduta/casos"
RELATO = "O encarregado da manutenção ameaçou demitir quem reclamasse das horas extras."
RECUSA = {"detail": "Sem acesso a este conteúdo do Canal de Conduta"}
SEGREDO_DO_WEBHOOK = "segredo-de-teste-do-webhook"

HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}


# ═══════════════════════════════════════════════════════════════════════════
# Dublês
# ═══════════════════════════════════════════════════════════════════════════


class _ClickSign:
    """A ClickSign de mentira: anota cada envelope e responde como a de verdade."""

    def __init__(self):
        self.chamadas: list[tuple] = []
        self.documentos: list[bytes] = []
        self._n = 0

    def create_envelope(self, nome):
        self._n += 1
        self.chamadas.append(("create_envelope", nome))
        return f"env-{self._n}"

    def add_document(self, envelope_id, pdf, nome_do_arquivo):
        self.documentos.append(pdf)
        self.chamadas.append(("add_document", envelope_id, nome_do_arquivo))
        return f"doc-{envelope_id}"

    def add_signer(self, envelope_id, nome, email):
        self.chamadas.append(("add_signer", envelope_id, nome, email))
        return f"sig-{envelope_id}"

    def create_qualification_requirement(self, *_a):
        return "req-q"

    def create_auth_requirement(self, *_a):
        return "req-a"

    def activate_envelope(self, envelope_id):
        self.chamadas.append(("activate_envelope", envelope_id))
        return True

    def notify_signers(self, *_a):
        return True

    def cancel_envelope(self, envelope_id):
        self.chamadas.append(("cancel_envelope", envelope_id))
        return True

    def get_envelope_status(self, *_a):
        return "running"

    def get_signed_document(self, *_a):
        return b"%PDF-1.4 assinado pelo convidado"

    def signatarios(self) -> list[tuple]:
        return [c for c in self.chamadas if c[0] == "add_signer"]


@pytest.fixture(autouse=True)
def clicksign(monkeypatch) -> _ClickSign:
    dubla = _ClickSign()
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

    def _rede(*_a, **_kw):
        raise AssertionError("teste tentou sair para a rede")

    monkeypatch.setattr(clicksign_service.httpx, "Client", _rede)
    return dubla


@pytest.fixture(autouse=True)
def logins(monkeypatch) -> list[dict]:
    """O provedor de login de mentira: cada conta criada fica anotada."""
    criadas: list[dict] = []

    def _criar(_supabase, nome, email, role, password=None):
        criadas.append({"nome": nome, "email": email, "role": role})
        return f"auth-novo-{len(criadas)}"

    monkeypatch.setattr(auth_provisioning, "provision_auth_user", _criar)
    return criadas


@pytest.fixture(autouse=True)
def emails(monkeypatch) -> list[dict]:
    """Todo e-mail que o módulo manda, com destinatário, assunto e corpo."""
    enviados: list[dict] = []

    def _enviar(destinatario, assunto, html, texto, *_a, **_kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(convites, "_enviar_email", _enviar)
    return enviados


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    limiter._storage.reset()
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "clicksign_webhook_secret", SEGREDO_DO_WEBHOOK)
    monkeypatch.setattr(assinaturas.storage, "upload_private", lambda *_a, **_kw: True)
    yield
    limiter._storage.reset()


def _pessoa(pid: str, nome: str | None = None, **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": nome or f"Pessoa {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "role": None,
        "ativo": True,
        "is_super_admin": False,
        "access_profile": None,
        "perfil_conduta": None,
    }
    return {**base, **campos}


def _participacao(pid: str, *, papel: str) -> dict:
    return {
        "id": f"part-{pid}",
        "colegiado_id": COMITE["id"],
        "participante_id": pid,
        "papel": papel,
        "e_diretor": False,
        "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=600)).isoformat(),
        "encerrada_em": None,
        "termo_assinado_em": "2026-10-01T12:00:00+00:00",
    }


COORDENACAO = _pessoa("C1", "Cora Coordenação")
MEMBRO = _pessoa("M1", "Mário Membro")
DO_GRUPO = _pessoa("G1", "Gilda do Grupo")
APURADOR = _pessoa("A1", "Ana Apuradora", email="ana.apuradora@hsm.com.br")
SUPER_ADMIN = _pessoa("S1", "Sílvio Super", access_profile="super_admin", is_super_admin=True)


class _Cenario:
    def __init__(self, *pessoas: dict):
        self.banco = Banco(
            {
                "participantes": [dict(p) for p in (COORDENACAO, MEMBRO, DO_GRUPO, SUPER_ADMIN, *pessoas)],
                "colegiados": [dict(COMITE)],
                "participacoes": [
                    _participacao("C1", papel="coordenacao"),
                    _participacao("M1", papel="membro"),
                ],
            }
        )

    def caso(self, rota: str = "comum") -> dict:
        novo = casos.registrar_caso(self.banco, relato=RELATO, categoria="A", rota=rota)
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == novo["id"])

    def no_grupo_especial(self, caso: dict, pid: str = "G1") -> None:
        self.banco.tabelas.setdefault("conduta_atribuicoes", []).append(
            {
                "caso_id": caso["id"],
                "participante_id": pid,
                "motivo": "grupo_especial",
                "termo_assinado_em": "2026-10-01T12:00:00+00:00",
                "impedido_em": None,
                "revogada_em": None,
            }
        )

    def tabela(self, nome: str) -> list[dict]:
        return self.banco.tabelas.get(nome, [])

    def pessoa(self, email: str) -> dict:
        [linha] = [p for p in self.tabela("participantes") if p.get("email") == email]
        return linha

    def como(self, pid: str) -> TestClient:
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(conduta_comite.router, prefix="/api")
        app.include_router(conduta_convites.router, prefix="/api")
        app.include_router(webhooks.router, prefix="/api")
        [quem] = [p for p in self.tabela("participantes") if p["id"] == pid]

        async def _usuario() -> dict[str, Any]:
            return {"id": quem["auth_user_id"], "email": quem["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app)

    def convidar(self, quem: str, caso: dict, **corpo):
        corpo = {"email": APURADOR["email"], "nome": "", "motivo": "apurador", **corpo}
        return self.como(quem).post(f"{ROTA_DOS_CASOS}/{caso['id']}/convites", json=corpo)


def _assinar(cenario: _Cenario, documento_key: str):
    corpo = json.dumps({"event": {"name": "auto_close"}, "document": {"key": documento_key}}).encode()
    assinatura = hmac_lib.new(SEGREDO_DO_WEBHOOK.encode(), corpo, hashlib.sha256).hexdigest()
    return cenario.como("C1").post(
        "/api/webhooks/clicksign",
        content=corpo,
        headers={"content-hmac": f"sha256={assinatura}", "content-type": "application/json"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quem convida
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemConvida:
    def test_a_coordenacao_convida_um_apurador_dentro_do_caso(self, clicksign):
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()

        resposta = cenario.convidar("C1", caso)

        assert resposta.status_code == 201, resposta.text
        [atribuicao] = cenario.tabela("conduta_atribuicoes")
        assert atribuicao["caso_id"] == caso["id"]
        assert atribuicao["participante_id"] == "A1"
        assert atribuicao["motivo"] == "apurador"
        assert atribuicao.get("termo_assinado_em") is None
        assert [c[3] for c in clicksign.signatarios()] == ["ana.apuradora@hsm.com.br"]
        [termo] = cenario.tabela("conduta_assinaturas")
        assert termo["tipo"] == "termo_do_apurador"
        assert termo["caso_id"] == caso["id"]
        assert termo["signatarios"] == ["A1"]
        assert termo["situacao"] == "enviado"
