"""A trilha com gavetas e o Dossiê do caso do Canal de Conduta (issue #1837;
especificação, seções 9.1 e 9.2; ADR 0097, decisões 2 e 9).

Cada classe é um critério de aceite da issue. O banco e o Storage são os
dublês de `conduta_apoio`, e a cifra é de verdade.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import secrets
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient
from test_conduta_voto import BASE, COORDENACAO, LEITOR, MEMBRO, NOMES, Comite, _pessoa

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.routers import conduta_depoimentos, conduta_trilha  # noqa: E402

AUDIO = b"ID3 audio do depoimento do acusado" + bytes(range(256))
TRANSCRICAO = "Rogério Valente: eu não ameacei ninguém, só levantei a voz.".encode()
TERMO = b"%PDF-1.4 termo de declaracao assinado a caneta"


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")


def _sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


class ComiteDaTrilha(Comite):
    def cliente(self, pid: str) -> TestClient:
        cliente = super().cliente(pid)
        cliente.app.include_router(conduta_depoimentos.router, prefix="/api")
        cliente.app.include_router(conduta_trilha.router, prefix="/api")
        return cliente

    def enviar(self, pid: str, caminho: str, nome: str, conteudo: bytes, campo: str = "arquivo"):
        return self.cliente(pid).post(f"{BASE}{caminho}", files={campo: (nome, conteudo, "application/octet-stream")})

    def caso_com_depoimento(self, *, termo: bool = True) -> tuple[str, str]:
        """Um caso do rito Rápido com o acusado ouvido: transcrição, áudio e,
        se pedido, o termo assinado, enviados pela tela. Volta na etapa Voto."""
        caso = self.caso(acusado_ouvido=False)
        self.linha_do_caso(caso)["etapa"] = "apuracao"
        resposta = self.post(
            COORDENACAO, f"/casos/{caso}/depoimentos", {"nome": "Rogério Valente", "cargo": "Supervisor", "papel": "acusado"}
        )
        assert resposta.status_code == 200, resposta.text
        depoimento = resposta.json()["depoimento"]["id"]
        base = f"/casos/{caso}/depoimentos/{depoimento}"
        assert self.enviar(COORDENACAO, f"{base}/transcricao", "depoimento.txt", TRANSCRICAO).status_code == 200
        assert self.enviar(MEMBRO, f"{base}/audio", "depoimento.mp3", AUDIO).status_code == 200
        if termo:
            assert self.enviar(COORDENACAO, f"{base}/termo-assinado", "termo.pdf", TERMO).status_code == 200
        self.linha_do_caso(caso)["etapa"] = "voto"
        return caso, depoimento

    def trilha_do_caso(self, caso: str, pid: str = COORDENACAO) -> dict:
        return self.abrir(pid, caso)["trilha"]


@pytest.fixture
def comite() -> ComiteDaTrilha:
    return ComiteDaTrilha()


# ═══════════════════════════════════════════════════════════════════════════
# A trilha mostra cada ato e documento com autor, data, origem e código de
# integridade
# ═══════════════════════════════════════════════════════════════════════════


class TestLinhaDoTempo:
    def test_o_documento_enviado_aparece_com_quem_enviou_quando_origem_e_codigo(self, comite):
        caso, _ = comite.caso_com_depoimento()

        documentos = [i for i in comite.trilha_do_caso(caso)["linha_do_tempo"] if i["tipo"] == "documento"]

        audio = next(d for d in documentos if d["titulo"] == "Áudio do depoimento, Acusado 1")
        assert audio["autor"] == NOMES[MEMBRO]
        assert audio["data"]
        assert audio["origem"] == "Upload"
        assert audio["codigo"] == _sha(AUDIO)
        assert audio["versao"] == 1
