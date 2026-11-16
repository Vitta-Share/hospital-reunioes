"""O cadastro de responsáveis mostra quem tem login no app (issue #1887, ADR
0099 decisão 1).

O login vira Responsável do setor pelo e-mail: se o e-mail do cadastro não casa
com o de um participante, a pessoa entra no app e não vê os casos do setor. A
linha do cadastro diz isso ao ouvidor, para ele achar o e-mail digitado errado.

O casamento é o mesmo do papel na Ouvidoria (sem diferenciar maiúsculas, sem os
espaços das pontas): um cadastro que dissesse "tem login" para quem o papel não
reconhece mandaria o ouvidor procurar o problema no lugar errado.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_ouvidoria_validacao_acionamento import (  # noqa: E402
    OUVIDOR,
    _client,
    _responsavel,
    _SupabaseFake,
)

from app.limiter import limiter  # noqa: E402
from app.services.ouvidoria_papel import RESPONSAVEL, papel_na_ouvidoria  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _cadastro(monkeypatch, *responsaveis: dict) -> dict[str, bool]:
    """O `tem_login` de cada linha que a rota devolve, por id."""
    supabase = _SupabaseFake(responsaveis=list(responsaveis))
    supabase.tabelas["participantes"].append(
        {"id": "P40", "nome_completo": "Dra. Helena", "email": "helena@hsm.br", "ativo": True}
    )
    client, _ = _client(monkeypatch, OUVIDOR, supabase)
    resposta = client.get("/api/ouvidoria/responsaveis")
    assert resposta.status_code == 200, resposta.text
    return {linha["id"]: linha["tem_login"] for linha in resposta.json()["responsaveis"]}


class TestCadaLinhaDizSeTemLogin:
    def test_email_de_um_participante_aparece_com_login(self, monkeypatch):
        linhas = _cadastro(monkeypatch, _responsavel(id="r-helena", nome="Dra. Helena", email="helena@hsm.br"))

        assert linhas == {"r-helena": True}

    def test_email_sem_participante_aparece_sem_login(self, monkeypatch):
        linhas = _cadastro(
            monkeypatch,
            _responsavel(id="r-helena", nome="Dra. Helena", email="helena@hsm.br"),
            _responsavel(id="r-digitado-errado", nome="Dra. Helena", email="helena@hsm.com.br"),
        )

        assert linhas == {"r-helena": True, "r-digitado-errado": False}

    def test_linha_sem_email_aparece_sem_login(self, monkeypatch):
        linhas = _cadastro(monkeypatch, _responsavel(id="r-sem-email", email=None))

        assert linhas == {"r-sem-email": False}


class TestOMesmoCasamentoDoPapel:
    """Critério 2: maiúscula ou espaço nas pontas não tiram o login."""

    def test_email_com_maiuscula_e_espacos_aparece_com_login(self, monkeypatch):
        linhas = _cadastro(monkeypatch, _responsavel(id="r-helena", email="  Helena@HSM.br "))

        assert linhas == {"r-helena": True}

    def test_quem_o_cadastro_diz_que_tem_login_e_reconhecido_como_responsavel(self, monkeypatch):
        """A tela e o papel não podem discordar: a mesma linha que o cadastro
        mostra com login faz a pessoa logada virar responsável do setor."""
        linha = _responsavel(id="r-helena", email="  Helena@HSM.br ")
        assert _cadastro(monkeypatch, linha) == {"r-helena": True}

        helena = {"id": "P40", "email": "helena@hsm.br", "access_profile": "medico"}
        papel = papel_na_ouvidoria(helena, [linha], dt.date(2026, 11, 16))

        assert papel.papel == RESPONSAVEL
        assert papel.setores == frozenset({"Recepcao"})
