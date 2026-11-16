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
    RELATO,
    VALIDACAO,
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


def _como(monkeypatch, quem: dict) -> None:
    """Quem está logado também na fila da Ouvidoria."""

    async def _logado(_user, _sb, fields=None):
        return quem

    monkeypatch.setattr(ouvidoria_router, "get_participante_for_user", _logado)


def _linha_da_fila(client) -> dict | None:
    r = client.get("/api/ouvidoria/protocolos")
    assert r.status_code == 200, r.text
    return next((p for p in r.json()["protocolos"] if p["id"] == "uuid-7"), None)


class TestRespondidoPeloLink:
    def test_responder_pelo_link_tira_o_caso_de_a_responder_e_o_botao_some(
        self, monkeypatch, _nunca_envia_email_de_verdade
    ):
        client, _ = _no_app(monkeypatch)
        token = _token_do_email(_nunca_envia_email_de_verdade)
        _como(monkeypatch, CARLOS)
        assert _linha_da_fila(client)["pode_responder"] is True

        pelo_link = client.post(f"/api/ouvidoria-setor/{token}/responder", data={"resposta": RESPOSTA})
        assert pelo_link.status_code == 200, pelo_link.text

        linha = _linha_da_fila(client)
        assert linha["status"] == "respondido"
        assert linha["pode_responder"] is False
        assert _responder(client).status_code == 410


# O cadastro de quem responde pela Recepção além do titular, e de quem responde
# por outro setor ou já saiu.
SUBSTITUTA = {"id": "P21", "nome_completo": "Sara Substituta", "email": "sara@hsm.br", "access_profile": "regular"}
GESTOR = {"id": "P22", "nome_completo": "Gil Gestor", "email": "gil@hsm.br", "access_profile": "regular"}
HELENA_DA_UTI = {"id": "P23", "nome_completo": "Helena", "email": "helena@hsm.br", "access_profile": "regular"}
QUEM_SAIU = {"id": "P24", "nome_completo": "Otto Antigo", "email": "otto@hsm.br", "access_profile": "regular"}
SECRETARIA_TITULAR = {
    "id": "P25",
    "nome_completo": "Sofia Secretaria",
    "email": "sofia@hsm.br",
    "access_profile": "secretaria",
}
OUTROS_RESPONSAVEIS = [
    _responsavel("substituto", id="resp-sub", nome="Sara Substituta", email="sara@hsm.br"),
    _responsavel("gestor", id="resp-gestor", nome="Gil Gestor", email="gil@hsm.br"),
    _responsavel(id="resp-uti", setor="UTI", nome="Helena", email="helena@hsm.br"),
    _responsavel("substituto", id="resp-antigo", nome="Otto Antigo", email="otto@hsm.br", vigencia_fim="2026-08-01"),
    _responsavel("substituto", id="resp-sofia", nome="Sofia Secretaria", email="sofia@hsm.br"),
]


class TestQuemPodeResponder:
    @pytest.mark.parametrize("quem", [HELENA_DA_UTI, QUEM_SAIU], ids=["outro-setor", "vigencia-encerrada"])
    def test_responsavel_de_outro_setor_ou_com_a_vigencia_encerrada_recebe_403(self, monkeypatch, quem):
        client, sb = _no_app(monkeypatch, quem, OUTROS_RESPONSAVEIS)

        rotas = [
            client.get("/api/ouvidoria/responder/uuid-7"),
            _responder(client),
            client.post("/api/ouvidoria/responder/uuid-7/devolver", json={"motivo": MOTIVO}),
            client.post(
                "/api/ouvidoria/responder/uuid-7/prorrogacao", json={"justificativa": JUSTIFICATIVA, "dias_uteis": 3}
            ),
        ]

        assert [r.status_code for r in rotas] == [403, 403, 403, 403]
        assert sb.tabelas["ouvidoria_protocolos"][0]["status"] == "aguardando_area"

    @pytest.mark.parametrize("quem", [SUBSTITUTA, GESTOR], ids=["substituto", "gestor"])
    def test_substituto_e_gestor_vigentes_respondem_e_a_trilha_guarda_o_nome_e_a_porta(self, monkeypatch, quem):
        client, sb = _no_app(monkeypatch, quem, OUTROS_RESPONSAVEIS)

        r = _responder(client)

        assert r.status_code == 200, r.text
        [movimento] = [m for m in sb.tabelas["ouvidoria_movimentos"] if m["estado_novo"] == "respondido"]
        assert movimento["autor_nome"] == quem["nome_completo"]
        assert movimento["observacao"].endswith("\nPorta: app")
        assert sb.tabelas["ouvidoria_protocolos"][0]["respondida_por_nome"] == quem["nome_completo"]

    def test_secretaria_que_responde_pelo_setor_ganha_o_botao_no_indice_geral(self, monkeypatch):
        client, _ = _no_app(monkeypatch, SECRETARIA_TITULAR, OUTROS_RESPONSAVEIS)
        _como(monkeypatch, SECRETARIA_TITULAR)

        assert _linha_da_fila(client)["pode_responder"] is True
        assert _responder(client).status_code == 200


MOTIVO = "Este caso é do Centro Médico: a recepção não agenda consulta de especialidade."
JUSTIFICATIVA = "Precisamos ouvir a equipe do plantão noturno, que só volta na segunda."


def _com_a_ouvidoria_para_avisar(sb) -> None:
    sb.tabelas["participantes"].append(
        {
            "id": "P10",
            "nome_completo": "Marta Ouvidora",
            "email": "marta@hsm.br",
            "perfil_ouvidoria": "ouvidor",
            "ativo": True,
        }
    )


class TestAsRegrasDoLink:
    def test_pedir_prorrogacao_pelo_app_avisa_a_ouvidoria_e_nao_gasta_o_link(
        self, monkeypatch, _nunca_envia_email_de_verdade
    ):
        client, sb = _no_app(monkeypatch)
        _com_a_ouvidoria_para_avisar(sb)
        token = _token_do_email(_nunca_envia_email_de_verdade)

        r = client.post(
            "/api/ouvidoria/responder/uuid-7/prorrogacao", json={"justificativa": JUSTIFICATIVA, "dias_uteis": 3}
        )

        assert r.status_code == 201, r.text
        [pedido] = sb.tabelas["ouvidoria_prorrogacoes"]
        assert pedido["solicitante_nome"] == "Carlos Titular"
        assert [n["gatilho"] for n in sb.tabelas["ouvidoria_notificacoes"]].count("prorrogacao_solicitada") == 1
        assert sb.tabelas["ouvidoria_movimentos"][-1]["observacao"].endswith("\nPorta: app")
        segundo = client.post(
            "/api/ouvidoria/responder/uuid-7/prorrogacao", json={"justificativa": JUSTIFICATIVA, "dias_uteis": 3}
        )
        assert segundo.status_code == 409, "uma vez só, como no link"
        assert client.get(f"/api/ouvidoria-setor/{token}").status_code == 200

    def test_devolver_pelo_app_avisa_a_ouvidoria_acende_a_novidade_e_consome_o_link(
        self, monkeypatch, _nunca_envia_email_de_verdade
    ):
        client, sb = _no_app(monkeypatch)
        _com_a_ouvidoria_para_avisar(sb)
        token = _token_do_email(_nunca_envia_email_de_verdade)
        # A Ouvidoria já tinha visto o caso: a devolução é o que acende o ponto.
        sb.tabelas["ouvidoria_protocolos"][0]["vista_pela_ouvidoria_em"] = "2026-08-25T16:00:00+00:00"

        r = client.post("/api/ouvidoria/responder/uuid-7/devolver", json={"motivo": MOTIVO})

        assert r.status_code == 200, r.text
        assert sb.tabelas["ouvidoria_protocolos"][0]["status"] == "em_classificacao"
        avisos = [n for n in sb.tabelas["ouvidoria_notificacoes"] if n["gatilho"] == "devolvido_a_ouvidoria"]
        assert [a["destinatario_email"] for a in avisos] == ["marta@hsm.br"]
        assert avisos[0]["detalhe"].endswith("\nPorta: app")
        # A novidade é derivada da trilha (RN-66): o movimento da devolução,
        # gravado pela mesma RPC do link, é o que a acende.
        [devolucao] = [m for m in sb.tabelas["ouvidoria_movimentos"] if m["estado_novo"] == "em_classificacao"]
        assert devolucao["autor_nome"] == "Carlos Titular"
        assert client.get(f"/api/ouvidoria-setor/{token}").json()["detail"] == JA_USADO


class TestGuardasDoConteudo:
    def test_caso_com_sigilo_reforcado_abre_pelo_app_so_com_a_nota_da_ouvidoria(self, monkeypatch):
        client, sb = _no_app(monkeypatch)
        sb.tabelas["ouvidoria_protocolos"][0]["sigilo_reforcado"] = True

        r = client.get("/api/ouvidoria/responder/uuid-7")

        assert r.status_code == 200, r.text
        corpo = r.json()
        assert [b["chave"] for b in corpo["blocos"]] == ["nota_da_ouvidoria"]
        assert corpo["identificacao"] is None
        assert RELATO not in r.text
        assert "Joana da Silva" not in r.text

    def test_caso_anonimo_abre_pelo_app_sem_identificacao(self, monkeypatch):
        client, sb = _no_app(monkeypatch)
        sb.tabelas["ouvidoria_protocolos"][0]["anonimo"] = True

        r = client.get("/api/ouvidoria/responder/uuid-7")

        assert r.status_code == 200, r.text
        assert r.json()["identificacao"] is None
        assert "Joana da Silva" not in r.text


class TestRedirecionado:
    def test_caso_redirecionado_pelo_ouvidor_some_da_lista_do_setor_antigo(self, monkeypatch):
        novo = _responsavel(id="resp-cm", setor="Centro Medico", nome="Dra. Alice", email="alice@hsm.br")
        client, sb = _no_app(monkeypatch, CARLOS, [novo])
        sb.tabelas["setores"].append({"id": "s2", "nome": "Centro Medico", "ativo": True})
        _como(monkeypatch, CARLOS)
        assert _linha_da_fila(client) is not None

        _como(monkeypatch, OUVIDOR)
        r = client.post(
            "/api/ouvidoria/manifestacoes/uuid-7/redirecionamentos",
            json={**VALIDACAO, "setor": "Centro Medico", "motivo": MOTIVO},
        )
        assert r.status_code == 201, r.text

        _como(monkeypatch, CARLOS)
        assert _linha_da_fila(client) is None
        assert client.get("/api/ouvidoria/responder/uuid-7").status_code == 403
