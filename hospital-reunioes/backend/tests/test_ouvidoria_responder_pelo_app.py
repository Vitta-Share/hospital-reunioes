"""Responder pelo app: a porta do login da Tela do responsável (issue #1886, ADR 0099).

O Responsável do setor que entra com a própria senha abre o caso do setor dele
pelo id, e responde, pede prorrogação ou devolve à Ouvidoria pelo mesmo serviço
da porta do token. Cada caso tem uma resposta só: agir pelo login consome os
links vivos do acionamento, e usar o link tira o caso de "A responder".

Mesmo seam das fatias do portal do setor: HTTP no `TestClient`, com o fake do
PostgREST de `test_ouvidoria_portal_setor`. O Resend nunca é chamado de verdade.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.limiter import limiter  # noqa: E402
from app.routers import ouvidoria as ouvidoria_router  # noqa: E402
from app.routers import ouvidoria_responder as responder_router  # noqa: E402
from app.services import ouvidoria_notificacoes  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))

from test_ouvidoria_portal_setor import (  # noqa: E402
    DENTRO_DO_EXPEDIENTE,
    OUVIDOR,
    _acionar,
    _client,
    _responsavel,
    _token_do_email,
)

# O titular do cadastro padrão do fake (`_responsavel()`), agora com login.
CARLOS = {
    "id": "P20",
    "nome_completo": "Carlos Titular",
    "email": "Carlos@HSM.br",
    "access_profile": "regular",
    "perfil_ouvidoria": None,
}

RESPOSTA = "Conversamos com a equipe da recepção e abrimos o segundo guichê às 7h a partir de hoje."

JA_USADO = "Este link já foi usado: a resposta do setor já entrou"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _nunca_envia_email_de_verdade(monkeypatch):
    enviados: list[dict] = []

    def _fake(destinatario, assunto, html_content, texto_fallback):
        enviados.append({"destinatario": destinatario, "assunto": assunto, "texto": texto_fallback})
        return True

    monkeypatch.setattr(ouvidoria_notificacoes, "_enviar_email", _fake)
    return enviados


def _no_app(monkeypatch, quem: dict = CARLOS, responsaveis: list[dict] | None = None):
    """O caso uuid-7 acionado na Recepção pelo ouvidor, e o app com a porta do
    login, onde `quem` está logado."""
    client, sb = _client(monkeypatch, participante=OUVIDOR)
    if responsaveis is not None:
        sb.tabelas["ouvidoria_setor_responsaveis"].extend(responsaveis)
    _acionar(client)
    client.app.include_router(responder_router.router, prefix="/api")

    async def _logado(_user, _sb, fields=None):
        return quem

    monkeypatch.setattr(responder_router, "get_participante_for_user", _logado)
    monkeypatch.setattr(responder_router, "agora_utc", lambda: DENTRO_DO_EXPEDIENTE)
    return client, sb


def _responder(client, resposta: str = RESPOSTA):
    return client.post("/api/ouvidoria/responder/uuid-7/responder", data={"resposta": resposta})


class TestUmaRespostaPorCaso:
    def test_responder_pelo_app_grava_a_resposta_e_o_link_diz_que_ja_foi_usado(
        self, monkeypatch, _nunca_envia_email_de_verdade
    ):
        client, sb = _no_app(monkeypatch)
        token = _token_do_email(_nunca_envia_email_de_verdade)

        r = _responder(client)

        assert r.status_code == 200, r.text
        caso = sb.tabelas["ouvidoria_protocolos"][0]
        assert caso["status"] == "respondido"
        assert caso["resposta_da_area"] == RESPOSTA
        link = client.get(f"/api/ouvidoria-setor/{token}")
        assert link.status_code == 410
        assert link.json()["detail"] == JA_USADO
