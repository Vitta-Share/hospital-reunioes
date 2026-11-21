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
import io
import json
import os
import re
import secrets
import sys
from datetime import timedelta
from typing import Any

import pdfplumber
import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import (  # noqa: E402
    get_current_user,
    get_supabase_client,
    is_super_admin,
    permissoes_contas_medicas,
    tem_acesso_reunioes,
)
from app.limiter import limiter  # noqa: E402
from app.routers import conduta_comite, conduta_convites, webhooks  # noqa: E402
from app.services import auth_provisioning, clicksign_service  # noqa: E402
from app.services.conduta import assinaturas, casos, convites, trilha  # noqa: E402
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


def _texto_do_pdf(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as documento:
        texto = "\n".join(pagina.extract_text() or "" for pagina in documento.pages)
    return re.sub(r"\s+", " ", texto)


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
        assert resposta.json()["convites"] == [
            {
                "participante_id": "A1",
                "nome": "Ana Apuradora",
                "motivo": "apurador",
                "papel": "Apurador designado",
                "termo": "aguardando_assinatura",
            }
        ]
        assert resposta.json()["aviso_termo"] is None

    def test_o_grupo_especial_convida_o_membro_da_cipa_dentro_do_caso_dele(self, clicksign):
        """Mutante: tirar o Grupo Especial de quem convida."""
        cenario = _Cenario(APURADOR)
        caso = cenario.caso(rota="especial")
        cenario.no_grupo_especial(caso)

        resposta = cenario.convidar("G1", caso, motivo="cipa")

        assert resposta.status_code == 201, resposta.text
        convidado = [a for a in cenario.tabela("conduta_atribuicoes") if a["motivo"] == "cipa"]
        assert [(a["caso_id"], a["participante_id"]) for a in convidado] == [(caso["id"], "A1")]
        assert [c[3] for c in clicksign.signatarios()] == ["ana.apuradora@hsm.com.br"]

    def test_membro_que_nao_e_da_coordenacao_nao_convida(self, clicksign):
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()

        resposta = cenario.convidar("M1", caso)

        assert resposta.status_code == 403, resposta.text
        assert resposta.json()["detail"] == convites.SO_QUEM_CONVIDA
        assert cenario.tabela("conduta_atribuicoes") == []
        assert clicksign.chamadas == []

    def test_a_coordenacao_nao_alcanca_o_caso_especial(self, clicksign):
        cenario = _Cenario(APURADOR)
        caso = cenario.caso(rota="especial")

        resposta = cenario.convidar("C1", caso)

        assert resposta.status_code == 403
        assert resposta.json() == RECUSA
        assert cenario.tabela("conduta_atribuicoes") == []

    def test_a_tela_do_caso_diz_quem_pode_convidar(self):
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()
        rota = f"{ROTA_DOS_CASOS}/{caso['id']}/convites"

        assert cenario.como("C1").get(rota).json() == {"pode_convidar": True, "convites": []}
        assert cenario.como("M1").get(rota).json() == {"pode_convidar": False, "convites": []}


# ═══════════════════════════════════════════════════════════════════════════
# 2. Quem não tem login ganha um cadastro mínimo
# ═══════════════════════════════════════════════════════════════════════════

PERFIS_DE_MODULO = ("perfil_pop", "perfil_ouvidoria", "perfil_contas_medicas", "perfil_nsp", "perfil_conduta")


class TestCadastroMinimo:
    def test_pessoa_sem_cadastro_ganha_cadastro_minimo_com_login_e_sem_outro_modulo(self, logins):
        """Mutante: o login do convidado nascer com o perfil padrão das Reuniões."""
        cenario = _Cenario()
        caso = cenario.caso()

        resposta = cenario.convidar("C1", caso, email="Nova.Pessoa@Fora.com.br", nome="Nova Pessoa")

        assert resposta.status_code == 201, resposta.text
        nova = cenario.pessoa("nova.pessoa@fora.com.br")
        assert nova["nome_completo"] == "Nova Pessoa"
        assert nova["auth_user_id"] == "auth-novo-1"
        assert logins == [{"nome": "Nova Pessoa", "email": "nova.pessoa@fora.com.br", "role": "convidado_do_canal"}]
        assert nova.get("access_profile", "regular") is None
        assert nova.get("role") is None
        assert nova.get("cargo") is None
        assert nova.get("is_super_admin") is False
        assert all(nova.get(perfil) is None for perfil in PERFIS_DE_MODULO)
        [atribuicao] = cenario.tabela("conduta_atribuicoes")
        assert atribuicao["participante_id"] == nova["id"]

    def test_o_login_novo_nao_abre_outro_modulo(self):
        """Os eixos de acesso dos outros módulos recusam o convidado."""
        cenario = _Cenario()
        caso = cenario.caso()
        cenario.convidar("C1", caso, email="nova.pessoa@fora.com.br", nome="Nova Pessoa")
        nova = cenario.pessoa("nova.pessoa@fora.com.br")

        assert not tem_acesso_reunioes(nova)
        assert not is_super_admin(nova)
        assert permissoes_contas_medicas(cenario.banco, nova) == []

    def test_pessoa_do_cadastro_sem_login_ganha_login_sem_papel_nas_reunioes(self, logins):
        sem_login = _pessoa("X1", "Xavier", email="xavier@hsm.com.br", auth_user_id=None, access_profile="regular")
        cenario = _Cenario(sem_login)
        caso = cenario.caso()

        resposta = cenario.convidar("C1", caso, email="xavier@hsm.com.br")

        assert resposta.status_code == 201, resposta.text
        xavier = cenario.pessoa("xavier@hsm.com.br")
        assert xavier["id"] == "X1"
        assert xavier["auth_user_id"] == "auth-novo-1"
        assert not tem_acesso_reunioes(xavier)

    def test_quem_ja_tem_login_nao_ganha_outro_nem_perde_o_que_tem(self, logins):
        cenario = _Cenario(_pessoa("R1", email="regina@hsm.com.br", access_profile="regular"))
        caso = cenario.caso()

        resposta = cenario.convidar("C1", caso, email="regina@hsm.com.br")

        assert resposta.status_code == 201, resposta.text
        assert logins == []
        assert cenario.pessoa("regina@hsm.com.br")["access_profile"] == "regular"

    def test_sem_cadastro_e_sem_nome_o_convite_pede_o_nome(self, logins):
        cenario = _Cenario()
        caso = cenario.caso()

        resposta = cenario.convidar("C1", caso, email="ninguem@fora.com.br")

        assert resposta.status_code == 422
        assert resposta.json()["detail"] == convites.SEM_NOME
        assert logins == []
        assert cenario.tabela("conduta_atribuicoes") == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. O termo assinado abre o caso, e só ele
# ═══════════════════════════════════════════════════════════════════════════


def _convidado(cenario: _Cenario, caso: dict) -> dict:
    """Convida a Ana para o caso e devolve a linha do termo dela."""
    assert cenario.convidar("C1", caso).status_code == 201
    [termo] = [a for a in cenario.tabela("conduta_assinaturas") if a["situacao"] == "enviado"]
    return termo


class TestTermoDoConvidado:
    def test_antes_do_termo_assinado_o_convidado_recebe_403_ao_abrir_o_caso(self):
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()
        _convidado(cenario, caso)
        cliente = cenario.como("A1")

        assert cliente.get(f"{ROTA_DOS_CASOS}/{caso['id']}").json() == RECUSA
        assert cliente.get(f"{ROTA_DOS_CASOS}/{caso['id']}").status_code == 403
        assert cliente.get(ROTA_DOS_CASOS).status_code == 403

    def test_com_o_termo_assinado_o_convidado_abre_so_aquele_caso(self):
        """Mutante: o retorno da ClickSign não carimbar a atribuição do convidado."""
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()
        outro = cenario.caso()
        termo = _convidado(cenario, caso)

        assert _assinar(cenario, termo["documento_key"]).status_code == 200
        cliente = cenario.como("A1")

        aberto = cliente.get(f"{ROTA_DOS_CASOS}/{caso['id']}")
        assert aberto.status_code == 200, aberto.text
        assert aberto.json()["relato"] == RELATO
        assert cliente.get(f"{ROTA_DOS_CASOS}/{outro['id']}").json() == RECUSA
        assert [c["id"] for c in cliente.get(ROTA_DOS_CASOS).json()["casos"]] == [caso["id"]]
        [convite] = cenario.como("C1").get(f"{ROTA_DOS_CASOS}/{caso['id']}/convites").json()["convites"]
        assert convite["termo"] == "assinado"

    def test_o_termo_nao_cita_o_protocolo_nem_o_caso(self, clicksign):
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()
        _convidado(cenario, caso)

        texto = _texto_do_pdf(clicksign.documentos[0])
        assert "Ana Apuradora" in texto
        assert "Apurador designado" in texto
        assert caso["protocolo"] not in texto
        assert "manutenção" not in texto
        assert not any(caso["protocolo"] in str(c) for c in clicksign.chamadas)

    def test_convidar_de_novo_quem_nao_assinou_cancela_o_termo_aberto_e_manda_outro(self, clicksign):
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()
        _convidado(cenario, caso)

        resposta = cenario.convidar("C1", caso)

        assert resposta.status_code == 201, resposta.text
        assert ("cancel_envelope", "env-1") in clicksign.chamadas
        assert [a["situacao"] for a in cenario.tabela("conduta_assinaturas")] == ["cancelado", "enviado"]
        assert len(cenario.tabela("conduta_atribuicoes")) == 1

    def test_quem_ja_assinou_nao_e_convidado_de_novo(self):
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()
        _assinar(cenario, _convidado(cenario, caso)["documento_key"])

        resposta = cenario.convidar("C1", caso)

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == convites.JA_TEM_ACESSO

    def test_quem_e_citado_no_caso_nao_recebe_o_convite(self, clicksign, emails):
        """O convite contaria ao citado que existe um caso."""
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()
        cenario.banco.tabelas["conduta_citados"] = [{"caso_id": caso["id"], "participante_id": "A1"}]

        resposta = cenario.convidar("C1", caso)

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == convites.CITADA
        assert cenario.tabela("conduta_atribuicoes") == []
        assert clicksign.chamadas == []
        assert emails == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. O super admin não é avisado, e o e-mail não cita o caso
# ═══════════════════════════════════════════════════════════════════════════


class TestAvisoDoConvite:
    @pytest.mark.parametrize(
        "email,nome",
        [(APURADOR["email"], ""), ("nova.pessoa@fora.com.br", "Nova Pessoa")],
        ids=["com_cadastro", "sem_cadastro"],
    )
    def test_nenhum_aviso_chega_ao_super_admin_e_o_email_nao_cita_o_caso(self, emails, email, nome):
        """Mutante: o convite avisar o super admin no sino."""
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()

        resposta = cenario.convidar("C1", caso, email=email, nome=nome)

        assert resposta.status_code == 201, resposta.text
        assert cenario.tabela("notificacoes") == []
        assert cenario.tabela("audit_log") == []
        assert [e["para"] for e in emails] == [email]
        [email_do_convite] = emails
        corpo = email_do_convite["assunto"] + email_do_convite["html"] + email_do_convite["texto"]
        for proibido in (caso["protocolo"], "manutenção", "horas extras", "Ana", "Apuradora", "Nova Pessoa", "Cora"):
            assert proibido not in corpo
        assert "/comite-de-conduta" in email_do_convite["texto"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. Cada acesso do convidado entra na trilha do caso
# ═══════════════════════════════════════════════════════════════════════════


class TestTrilhaDoConvidado:
    def test_cada_acesso_do_convidado_entra_na_trilha_do_caso(self):
        """Mutante: a leitura de quem entra por atribuição não ir para a trilha."""
        cenario = _Cenario(APURADOR)
        caso = cenario.caso()
        _assinar(cenario, _convidado(cenario, caso)["documento_key"])
        cliente = cenario.como("A1")

        assert cliente.get(f"{ROTA_DOS_CASOS}/{caso['id']}").status_code == 200
        assert cliente.get(f"{ROTA_DOS_CASOS}/{caso['id']}").status_code == 200

        linhas = sorted(cenario.tabela("conduta_trilha"), key=lambda x: x["seq"])
        assert [(x["acao"], x["autor_id"]) for x in linhas] == [
            ("recebimento", None),
            ("convite", "C1"),
            ("termo_assinado", "A1"),
            ("leitura", "A1"),
            ("leitura", "A1"),
        ]
        assert "A1" in linhas[1]["detalhe"]
        assert trilha.linhas_adulteradas(linhas) == []
