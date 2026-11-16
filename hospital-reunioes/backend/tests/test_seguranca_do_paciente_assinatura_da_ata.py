"""A assinatura da ata do Núcleo pelos presentes, o encerramento em 5 dias
úteis e a limpeza da transcrição (issue #1776, PRD #1764, ADR 0095).

O que a issue promete, um bloco por critério:

1. a ata vai para assinatura só dos presentes, e só depois da validação da
   Presidência;
2. o encerramento conta 5 dias úteis com os feriados cadastrados e registra
   quem não assinou;
3. a transcrição de reunião do Núcleo é apagada 30 dias corridos depois da ata
   assinada; a de outras reuniões não é tocada;
4. a ata encerrada aparece nos Documentos com número sequencial;
5. rodar os jobs duas vezes não muda o resultado;
6. o kit de conhecimento diz o comportamento novo.

E a decisão da triagem: a ata assinada sai só pela rota do Núcleo, com a
permissão do módulo, e nunca pelo super admin sem Acesso pleno.

O banco é o dublê em memória das reuniões do Núcleo. A IA, a assinatura
eletrônica e o Storage são sempre dublados: a função da assinatura que não
estiver no dublê explode. Nenhum nome, registro ou e-mail de pessoa real.
"""

from __future__ import annotations

import copy
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_seguranca_do_paciente_ata import (  # noqa: E402, F401
    R_ATA,
    _ata_gravada,
    _BancoDaAta,
    _com_ata,
    _ia,
    _reset_rate_limiter,
    _status,
    _validar,
)
from test_seguranca_do_paciente_reunioes import (  # noqa: E402
    HOJE,
    MEMBRO,
    MEMBRO_SEM_TERMO,
    PRESIDENCIA,
    R_COMUM,
    SUPER_ADMIN,
    SUPER_ADMIN_PLENO,
    _assert_recusado,
    _cliente,
    _reuniao,
)

from app.config import settings  # noqa: E402
from app.services import clicksign_service, storage  # noqa: E402
from app.services.seguranca_do_paciente import assinatura_da_ata  # noqa: E402

FERIADO = date(2026, 11, 20)


# ─── A assinatura eletrônica e o Storage dublados ───────────────────────────


class _Assinatura:
    """O envelope de mentira. `assinaram` diz quem já assinou (por e-mail)."""

    def __init__(self):
        self.chamadas: list[tuple] = []
        self.signatarios: dict[str, list[dict]] = {}
        self.assinaram: set[str] = set()
        self.status = "running"
        self.falhar_em: str | None = None
        self._n = 0

    def _passo(self, nome: str, *args) -> bool:
        self.chamadas.append((nome, *args))
        return self.falhar_em != nome

    def create_envelope(self, nome):
        self._n += 1
        return f"env-{self._n}" if self._passo("create_envelope", nome) else None

    def add_document(self, envelope_id, pdf, nome_do_arquivo):
        return f"doc-{envelope_id}" if self._passo("add_document", envelope_id, nome_do_arquivo) else None

    def add_signer(self, envelope_id, nome, email):
        if not self._passo("add_signer", envelope_id, nome, email):
            return None
        lista = self.signatarios.setdefault(envelope_id, [])
        lista.append({"signer_id": f"sig-{len(lista) + 1}", "nome": nome, "email": email})
        return lista[-1]["signer_id"]

    def create_qualification_requirement(self, envelope_id, documento_id, signatario_id):
        return "req-q" if self._passo("create_qualification_requirement", envelope_id) else None

    def create_auth_requirement(self, envelope_id, documento_id, signatario_id):
        return "req-a" if self._passo("create_auth_requirement", envelope_id) else None

    def activate_envelope(self, envelope_id):
        return self._passo("activate_envelope", envelope_id)

    def notify_signers(self, envelope_id):
        return self._passo("notify_signers", envelope_id)

    def get_envelope_status(self, envelope_id):
        self._passo("get_envelope_status", envelope_id)
        return self.status

    def close_envelope(self, envelope_id):
        if not self._passo("close_envelope", envelope_id):
            return False
        self.status = "closed"
        return True

    def list_signers(self, envelope_id):
        self._passo("list_signers", envelope_id)
        return [
            {
                **s,
                "status": "signed" if s["email"] in self.assinaram else "pending",
                "signed_at": "2026-11-17T10:00:00+00:00" if s["email"] in self.assinaram else None,
            }
            for s in self.signatarios.get(envelope_id, [])
        ]

    def get_signed_document(self, envelope_id):
        self._passo("get_signed_document", envelope_id)
        return b"%PDF-1.4 ata assinada" if self.status == "closed" else None

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


@pytest.fixture(autouse=True)
def assinatura(monkeypatch, _ia) -> _Assinatura:
    dubla = _Assinatura()
    for nome in (
        "create_envelope",
        "add_document",
        "add_signer",
        "create_qualification_requirement",
        "create_auth_requirement",
        "activate_envelope",
        "notify_signers",
        "get_envelope_status",
        "close_envelope",
        "list_signers",
        "get_signed_document",
    ):
        monkeypatch.setattr(clicksign_service, nome, getattr(dubla, nome))
    # O PDF de verdade tem o próprio teste; aqui ele é só bytes.
    monkeypatch.setattr(assinatura_da_ata, "gerar_pdf_da_ata", lambda reuniao, ata: b"%PDF-1.4 ata")
    return dubla


class _Storage:
    def __init__(self):
        self.arquivos: dict[tuple[str, str], bytes] = {}

    def upload_private(self, supabase, bucket, path, content, content_type="application/octet-stream"):
        self.arquivos[(bucket, path)] = content
        return True

    def signed_url(self, supabase, bucket, path, expires_in):
        return f"https://storage.test/{bucket}/{path}?expira={expires_in}" if (bucket, path) in self.arquivos else None

    def remover(self, bucket, caminhos):
        return [{"name": c} for c in caminhos if self.arquivos.pop((bucket, c), None) is not None]


@pytest.fixture(autouse=True)
def arquivos(monkeypatch) -> _Storage:
    dublado = _Storage()
    monkeypatch.setattr(storage, "upload_private", dublado.upload_private)
    monkeypatch.setattr(storage, "signed_url", dublado.signed_url)
    monkeypatch.setattr(assinatura_da_ata, "_remover_do_storage", lambda supabase, bucket, c: dublado.remover(bucket, c))
    return dublado


def _emails_convidados(dubla: _Assinatura) -> list[str]:
    return sorted(c[3] for c in dubla.chamadas if c[0] == "add_signer")


def _reuniao_gravada(banco, rid: str = R_ATA) -> dict[str, Any]:
    return next(r for r in banco.tabelas["reunioes"] if r["id_reuniao"] == rid)


def _validada() -> Any:
    banco = _com_ata()
    resposta = _validar(_cliente(PRESIDENCIA, banco))
    assert resposta.status_code == 200, resposta.text
    return banco


# ═══════════════════════════════════════════════════════════════════════════
# 1. Só os presentes assinam, e só depois da validação
# ═══════════════════════════════════════════════════════════════════════════


class TestSoOsPresentesAssinam:
    def test_a_ata_validada_vai_para_assinatura_so_dos_presentes(self, assinatura):
        banco = _com_ata()
        assert assinatura.chamadas == []

        resposta = _validar(_cliente(PRESIDENCIA, banco))

        assert resposta.status_code == 200, resposta.text
        # PRES1, MEMB1 e MEMB3 presentes; SUPL1 ausente com justificativa.
        assert _emails_convidados(assinatura) == ["memb1@hsm.test", "memb3@hsm.test", "pres1@hsm.test"]
        assert "activate_envelope" in assinatura.nomes()
        assert _status(banco) == "AGUARDANDO_ASSINATURA"
        assert resposta.json()["status"] == "AGUARDANDO_ASSINATURA"
