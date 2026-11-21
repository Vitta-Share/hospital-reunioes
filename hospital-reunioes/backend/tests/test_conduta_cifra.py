"""A cifra do Canal de Conduta (issue #1820, ADR 0097, decisões 1 e 2).

O conteúdo dos casos sai cifrado da aplicação, com a chave numa variável do
Coolify. Sem a chave, o módulo recusa gravar e ler (fail-closed) e o resto do
app sobe normal; o `/api/health` diz se a chave está configurada, sem o valor.

As chaves daqui são de teste, geradas na hora.
"""

from __future__ import annotations

import base64
import os
import secrets
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.routers import health  # noqa: E402
from app.services.conduta import cifra  # noqa: E402

RELATO = "O supervisor gritou com a equipe do plantão noturno na frente dos pacientes."


def _chave() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


@pytest.fixture
def com_chave(monkeypatch):
    chave = _chave()
    monkeypatch.setattr(settings, "conduta_chave_cifra", chave)
    return chave


@pytest.fixture
def sem_chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", "")


class TestCifraDoTexto:
    def test_o_texto_cifrado_nao_traz_o_relato_em_claro(self, com_chave):
        cifrado = cifra.cifrar_texto(RELATO)

        assert "supervisor" not in cifrado
        assert "plantão" not in cifrado
        assert cifra.decifrar_texto(cifrado) == RELATO

    def test_o_mesmo_relato_cifrado_duas_vezes_sai_diferente(self, com_chave):
        """Nonce novo a cada cifra: dois casos iguais não se denunciam no banco."""
        assert cifra.cifrar_texto(RELATO) != cifra.cifrar_texto(RELATO)

    def test_texto_cifrado_com_outra_chave_nao_abre(self, com_chave, monkeypatch):
        cifrado = cifra.cifrar_texto(RELATO)
        monkeypatch.setattr(settings, "conduta_chave_cifra", _chave())

        with pytest.raises(cifra.CifraIndisponivel):
            cifra.decifrar_texto(cifrado)

    def test_o_arquivo_cifrado_volta_igual(self, com_chave):
        audio = secrets.token_bytes(4096)
        cifrado = cifra.cifrar_arquivo(audio)

        assert audio not in cifrado
        assert cifra.decifrar_arquivo(cifrado) == audio


class TestSemAChave:
    def test_sem_a_chave_o_modulo_recusa_gravar(self, sem_chave):
        with pytest.raises(cifra.CifraIndisponivel):
            cifra.cifrar_texto(RELATO)

    def test_sem_a_chave_o_modulo_recusa_ler(self, com_chave, monkeypatch):
        cifrado = cifra.cifrar_texto(RELATO)
        monkeypatch.setattr(settings, "conduta_chave_cifra", "")

        with pytest.raises(cifra.CifraIndisponivel):
            cifra.decifrar_texto(cifrado)

    @pytest.mark.parametrize("valor", ["", "curta", base64.b64encode(b"x" * 16).decode(), "não é base64!"])
    def test_chave_ausente_ou_malformada_vale_como_nao_configurada(self, monkeypatch, valor):
        monkeypatch.setattr(settings, "conduta_chave_cifra", valor)

        assert cifra.chave_configurada() is False
        with pytest.raises(cifra.CifraIndisponivel):
            cifra.cifrar_arquivo(b"audio")

    def test_o_app_inteiro_sobe_sem_a_chave(self, sem_chave):
        """O resto do app não depende da cifra: o `main` importa e monta as
        rotas sem ela."""
        from app.main import app

        assert len(app.openapi()["paths"]) > 150


class _Consulta:
    def __init__(self, linhas):
        self._linhas = linhas

    def select(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        from types import SimpleNamespace

        return SimpleNamespace(data=list(self._linhas))


class _Banco:
    def table(self, nome):
        return _Consulta([{"numero": 175}] if nome == "migracoes_aplicadas" else [{"id": "P1"}])


def _health(monkeypatch):
    monkeypatch.setattr(health, "get_supabase_client", lambda: _Banco())
    app = FastAPI()
    app.include_router(health.router, prefix=settings.api_prefix)
    return TestClient(app).get("/api/health")


class TestHealth:
    def test_o_health_diz_que_a_chave_esta_configurada_sem_mostrar_o_valor(self, com_chave, monkeypatch):
        resposta = _health(monkeypatch)

        assert resposta.status_code == 200
        assert resposta.json()["cifra_do_canal_de_conduta"] == "configurada"
        assert com_chave not in resposta.text

    def test_o_health_diz_que_a_chave_falta(self, sem_chave, monkeypatch):
        resposta = _health(monkeypatch)

        assert resposta.status_code == 200
        assert resposta.json()["status"] == "healthy"
        assert resposta.json()["cifra_do_canal_de_conduta"] == "ausente"
