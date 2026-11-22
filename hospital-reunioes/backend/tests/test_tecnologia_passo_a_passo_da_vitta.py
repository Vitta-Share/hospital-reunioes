"""O Passo a passo da Vitta: o Pedido de fazer alguma coisa, com um check em
cada passo, que fecha o card no GitHub quando é concluído (issue #2176, ADR
0110).

A Pergunta da Vitta (ADR 0109) vira um dos dois tipos do Pedido da Vitta. O
outro, o Passo a passo, nasce pela mesma ponte, com os passos (de 2 a 15, o
último é o "Como saber que acabou") e o card. No cartão, cada passo tem um
check, guardado num histórico que só cresce; o Concluir só vale com todos
marcados. Concluído, o app grava, comenta na issue (o fato, o papel e os
checks, sem a anotação e sem nome: o repositório é público) e fecha o card.
Se o GitHub recusa, o Pedido fica concluído com "Não chegou ao GitHub" e o
motivo, e o Reenviar tenta de novo. O Pedido acompanha o GitHub: card fechado
por fora conclui ou cancela, card reaberto reabre com os checks zerados.

Pela ROTA de verdade (ponte, tela e webhook), com o Supabase em memória de
`test_tecnologia_vinculo` e o transporte do GitHub dublado.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    CONVERSA,
    CONVERSA_DA_TELA,
    DEMANDA,
    DIRETOR,
    DIRETORA,
    PEDRO,
    QUATRO_LINHAS,
    TABELA,
    _ler,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
)
from test_tecnologia_vinculo import _integracao_configurada  # noqa: E402, F401

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import webhooks as webhooks_router  # noqa: E402
from app.services import github_client, tecnologia_email, tecnologia_me_explique, tecnologia_perguntas  # noqa: E402

CRIAR = f"/api/automacao/tecnologia/demandas/{DEMANDA}/perguntas"
CHECKS = "tecnologia_checks_do_pedido"
CARD = 1961
REPO = "pedrorezendefig/hospital-reunioes"
SEGREDO = "segredo-falso-de-teste-2176"

PASSOS = [
    "Abra a aba Segurança do Paciente e clique em Documentos.",
    "Clique em Publicar no Regimento do NSP.",
    "Como saber que acabou: o Regimento aparece como Publicado na lista.",
]
PASSO_A_PASSO = {
    "github_login": "pedrorezendefig",
    "tipo": "passo_a_passo",
    "destinatario_id": DIRETORA["id"],
    "assunto": "publicar o Regimento do NSP",
    "texto": "Publique o Regimento do NSP no app.",
    **QUATRO_LINHAS,
    "passos": PASSOS,
    "card_numero": CARD,
}

# A anotação da Diretora: fica só no app, nunca vai para a issue.
ANOTACAO = "Publiquei, mas a Dra. Fernanda ainda vai revisar o anexo 2."


@pytest.fixture(autouse=True)
def emails(monkeypatch) -> list[dict]:
    """Cada e-mail que sairia, gravado na porta do transporte."""
    enviados: list[dict] = []

    def _gravar(destinatario, assunto, html_content, texto_fallback, *a, **kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html_content, "texto": texto_fallback})
        return True

    monkeypatch.setattr(tecnologia_email, "_enviar_email", _gravar)
    monkeypatch.setattr(settings, "frontend_url", "https://app.hsm.test")
    return enviados


@pytest.fixture(autouse=True)
def github(monkeypatch) -> dict:
    """O transporte do GitHub: grava cada chamada e responde 200, ou o status
    que o teste puser em `status`."""
    estado: dict = {"chamadas": [], "status": 200}

    def _responder(metodo, url, *, headers=None, json=None, timeout=None):
        estado["chamadas"].append((metodo, url, json))
        return httpx.Response(estado["status"], json={"number": CARD}, request=httpx.Request(metodo, url))

    monkeypatch.setattr(github_client.httpx, "request", _responder)
    return estado


def _criar(cliente: TestClient, **campos):
    return cliente.post(CRIAR, json={**PASSO_A_PASSO, **campos}, headers={"X-API-Key": CHAVE})


def _um_passo_a_passo(**campos):
    ponte, sb = _ponte()
    resposta = _criar(ponte, **campos)
    assert resposta.status_code == 201, resposta.text
    return ponte, sb, resposta.json()["id"]


def _marcar(sb, logado, pedido_id, monkeypatch, passo, marcado=True):
    return _tela(sb, logado, monkeypatch).post(
        f"/api/admin/tecnologia/perguntas/{pedido_id}/checks", json={"passo": passo, "marcado": marcado}
    )


def _marcar_todos(sb, logado, pedido_id, monkeypatch):
    for passo in range(len(PASSOS)):
        assert _marcar(sb, logado, pedido_id, monkeypatch, passo).status_code == 200


def _concluir(sb, logado, pedido_id, monkeypatch, anotacao=None):
    corpo = {} if anotacao is None else {"anotacao": anotacao}
    return _tela(sb, logado, monkeypatch).post(f"/api/admin/tecnologia/perguntas/{pedido_id}/concluir", json=corpo)


def _reenviar(sb, logado, pedido_id, monkeypatch):
    return _tela(sb, logado, monkeypatch).post(f"/api/admin/tecnologia/perguntas/{pedido_id}/reenviar")


def _comentarios(github) -> list[str]:
    return [
        corpo["body"] for metodo, url, corpo in github["chamadas"] if metodo == "POST" and url.endswith("/comments")
    ]


def _fechamentos(github) -> list[dict]:
    return [corpo for metodo, url, corpo in github["chamadas"] if metodo == "PATCH"]


# ═══════════════════════════════════════════════════════════════════════════
# Criar pela ponte
# ═══════════════════════════════════════════════════════════════════════════


class TestCriar:
    def test_criar_o_passo_a_passo_grava_o_tipo_os_passos_e_o_card(self):
        ponte, sb = _ponte()

        resposta = _criar(ponte)

        assert resposta.status_code == 201, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert resposta.json()["tipo"] == "passo_a_passo"
        assert (pedido["tipo"], pedido["estado"]) == ("passo_a_passo", "aberta")
        assert pedido["passos"] == PASSOS
        assert (pedido["card_projeto"], pedido["card_numero"]) == ("hospital", CARD)
        assert pedido["opcoes"] == []

    def test_a_pergunta_continua_nascendo_pergunta(self):
        ponte, sb = _ponte()

        resposta = _criar(ponte, tipo=None, passos=[], card_numero=None, opcoes=["Sim", "Não"], recomendada="A")

        assert resposta.status_code == 201, resposta.text
        assert sb.tabelas[TABELA][0]["tipo"] == "pergunta"

    @pytest.mark.parametrize(
        ("campos", "motivo"),
        [
            ({"passos": ["Só um passo."]}, tecnologia_perguntas.MOTIVO_PASSOS),
            ({"passos": [f"Passo {i}." for i in range(16)]}, tecnologia_perguntas.MOTIVO_PASSOS),
            ({"passos": ["Abra a aba.", "   "]}, tecnologia_perguntas.MOTIVO_PASSOS),
            ({"card_numero": None}, tecnologia_perguntas.MOTIVO_SEM_CARD),
            ({"opcoes": ["Sim", "Não"], "recomendada": "A"}, tecnologia_perguntas.MOTIVO_OPCOES_SO_NA_PERGUNTA),
            ({"ganho": " "}, "Falta a linha do cartão: o ganho."),
        ],
        ids=["um-passo", "dezesseis-passos", "passo-vazio", "sem-card", "com-opcoes", "sem-ganho"],
    )
    def test_passo_a_passo_invalido_e_recusado_com_o_motivo_e_nada_e_gravado(self, campos, motivo, emails):
        ponte, sb = _ponte()

        resposta = _criar(ponte, **campos)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": motivo}
        assert sb.tabelas[TABELA] == []
        assert sb.tabelas[CONVERSA] == []
        assert emails == []

    def test_criar_avisa_o_destinatario_com_pede_sua_acao_e_o_assunto(self, emails):
        ponte, sb = _ponte()

        _criar(ponte)

        [aviso] = sb.tabelas["notificacoes"]
        assert (aviso["destinatario_id"], aviso["titulo"], aviso["mensagem"]) == (
            DIRETORA["id"],
            "Pede sua ação",
            "publicar o Regimento do NSP",
        )
        [email] = emails
        assert email["assunto"] == "Pedro Rezende pede sua ação: publicar o Regimento do NSP"

    def test_a_conversa_ganha_a_linha_do_passo_a_passo_aberto(self):
        _, sb, _ = _um_passo_a_passo()

        assert sb.tabelas[CONVERSA][-1]["texto"] == "Passo a passo aberto: publicar o Regimento do NSP"


# ═══════════════════════════════════════════════════════════════════════════
# Os checks
# ═══════════════════════════════════════════════════════════════════════════


class TestChecks:
    def test_marcar_um_passo_guarda_quem_marcou_e_o_cartao_mostra(self, monkeypatch):
        _, sb, pedido_id = _um_passo_a_passo()

        resposta = _marcar(sb, DIRETORA, pedido_id, monkeypatch, 0)

        assert resposta.status_code == 200, resposta.text
        passos = resposta.json()["passos"]
        assert [p["marcado"] for p in passos] == [True, False, False]
        assert passos[0]["por"] == "Diretora Clínica"
        [check] = sb.tabelas[CHECKS]
        assert (check["pedido_id"], check["passo"], check["marcado"], check["por"]) == (
            pedido_id,
            0,
            True,
            DIRETORA["id"],
        )

    def test_desmarcar_acrescenta_uma_linha_e_o_historico_so_cresce(self, monkeypatch):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar(sb, DIRETORA, pedido_id, monkeypatch, 1)

        resposta = _marcar(sb, DIRETORA, pedido_id, monkeypatch, 1, marcado=False)

        assert [p["marcado"] for p in resposta.json()["passos"]] == [False, False, False]
        assert [(c["passo"], c["marcado"]) for c in sb.tabelas[CHECKS]] == [(1, True), (1, False)]

    def test_passo_que_nao_existe_e_recusado(self, monkeypatch):
        _, sb, pedido_id = _um_passo_a_passo()

        resposta = _marcar(sb, DIRETORA, pedido_id, monkeypatch, 3)

        assert resposta.status_code == 422
        assert sb.tabelas.get(CHECKS, []) == []

    def test_outro_super_admin_nao_marca_nem_conclui(self, monkeypatch):
        _, sb, pedido_id = _um_passo_a_passo()

        assert _marcar(sb, DIRETOR, pedido_id, monkeypatch, 0).status_code == 403
        assert _concluir(sb, DIRETOR, pedido_id, monkeypatch).status_code == 403
        assert sb.tabelas.get(CHECKS, []) == []


# ═══════════════════════════════════════════════════════════════════════════
# Concluir
# ═══════════════════════════════════════════════════════════════════════════


class TestConcluir:
    def test_concluir_com_um_check_desmarcado_e_recusado_e_nada_muda(self, monkeypatch, github):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar(sb, DIRETORA, pedido_id, monkeypatch, 0)
        _marcar(sb, DIRETORA, pedido_id, monkeypatch, 1)

        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_FALTA_CHECK}
        assert sb.tabelas[TABELA][0]["estado"] == "aberta"
        assert github["chamadas"] == []

    def test_concluir_grava_a_conclusao_e_fecha_o_card_no_github(self, monkeypatch, github):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)

        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch, anotacao=ANOTACAO)

        assert resposta.status_code == 200, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["estado"], pedido["concluida_como"]) == ("concluida", "app")
        assert (pedido["concluida_por"], pedido["concluida_em_nome_de"]) == (DIRETORA["id"], None)
        assert pedido["resposta_texto"] == ANOTACAO
        assert pedido["fechamento_github"] == "fechado"
        assert _fechamentos(github) == [{"state": "closed", "state_reason": "completed"}]
        assert all(f"/issues/{CARD}" in url for _, url, _ in github["chamadas"])
        cartao = resposta.json()["pergunta"]
        assert cartao["estado"] == "concluida"
        assert cartao["conclusao"]["por"] == "Diretora Clínica"
        assert cartao["conclusao"]["anotacao"] == ANOTACAO
        assert cartao["fechamento"] == {"estado": "fechado", "motivo": None}

    def test_o_comentario_leva_so_o_fato_o_papel_e_os_checks(self, monkeypatch, github):
        """O repositório é público: o comentário é fixo. Sem a anotação e sem
        o nome de ninguém, nem de quem marcou."""
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        monkeypatch.setattr(tecnologia_perguntas, "_agora", lambda: datetime(2026, 11, 22, 17, 30, tzinfo=UTC))

        _concluir(sb, DIRETORA, pedido_id, monkeypatch, anotacao=ANOTACAO)

        assert _comentarios(github) == [
            "<!-- pedido-da-vitta: passo-a-passo-concluido -->\n"
            "Passo a passo concluído no app em 22/11 às 14:30, pelo Destinatário (Diretoria).\n"
            "\n"
            "- [x] Abra a aba Segurança do Paciente e clique em Documentos.\n"
            "- [x] Clique em Publicar no Regimento do NSP.\n"
            "- [x] Como saber que acabou: o Regimento aparece como Publicado na lista."
        ]

    def test_o_desenvolvedor_conclui_no_lugar_e_os_dois_nomes_ficam_gravados(self, monkeypatch, github):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, PEDRO, pedido_id, monkeypatch)

        resposta = _concluir(sb, PEDRO, pedido_id, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["concluida_por"], pedido["concluida_em_nome_de"]) == (PEDRO["id"], DIRETORA["id"])
        assert {(c["por"], c["em_nome_de"]) for c in sb.tabelas[CHECKS]} == {(PEDRO["id"], DIRETORA["id"])}
        conclusao = resposta.json()["pergunta"]["conclusao"]
        assert (conclusao["por"], conclusao["em_nome_de"]) == ("Pedro Rezende", "Diretora Clínica")
        [comentario] = _comentarios(github)
        assert "por um Desenvolvedor, no lugar do Destinatário (Diretoria)." in comentario

    def test_a_anotacao_entra_na_conversa_e_a_linha_de_sistema_diz_que_concluiu(self, monkeypatch):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)

        _concluir(sb, DIRETORA, pedido_id, monkeypatch, anotacao=ANOTACAO)

        textos = [(m["texto"], m["origem"]) for m in sb.tabelas[CONVERSA]]
        assert ("Passo a passo concluído: publicar o Regimento do NSP", "sistema") in textos
        assert (f"Anotação: {ANOTACAO}", "app") in textos

    def test_concluir_duas_vezes_e_409(self, monkeypatch, github):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 409
        assert len(_fechamentos(github)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Não chegou ao GitHub, e o Reenviar
# ═══════════════════════════════════════════════════════════════════════════


class TestNaoChegouAoGithub:
    def test_github_recusando_deixa_concluido_com_falhou_e_o_motivo(self, monkeypatch, github):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        github["status"] = 403

        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["estado"], pedido["fechamento_github"]) == ("concluida", "falhou")
        assert pedido["fechamento_motivo"] == "O GitHub não aceitou (GitHub respondeu 403)."
        assert resposta.json()["pergunta"]["fechamento"] == {
            "estado": "falhou",
            "motivo": "O GitHub não aceitou (GitHub respondeu 403).",
        }

    def test_reenviar_tenta_de_novo_e_fecha(self, monkeypatch, github):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        github["status"] = 500
        _concluir(sb, DIRETORA, pedido_id, monkeypatch)
        github["status"] = 200
        github["chamadas"].clear()

        resposta = _reenviar(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["fechamento_github"], pedido["fechamento_motivo"]) == ("fechado", None)
        assert len(_comentarios(github)) == 1
        assert _fechamentos(github) == [{"state": "closed", "state_reason": "completed"}]

    def test_reenviar_o_que_ja_chegou_e_409_e_nao_vai_ao_github(self, monkeypatch, github):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        _concluir(sb, DIRETORA, pedido_id, monkeypatch)
        github["chamadas"].clear()

        resposta = _reenviar(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 409
        assert github["chamadas"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Ler pela ponte
# ═══════════════════════════════════════════════════════════════════════════


class TestLer:
    def test_ler_devolve_o_tipo_a_conclusao_a_anotacao_e_o_fechamento(self, monkeypatch):
        ponte, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        _concluir(sb, DIRETORA, pedido_id, monkeypatch, anotacao=ANOTACAO)

        corpo = _ler(ponte, pedido_id).json()

        assert (corpo["tipo"], corpo["estado"]) == ("passo_a_passo", "concluida")
        assert corpo["card"] == {"projeto": "hospital", "numero": CARD}
        assert corpo["conclusao"]["como"] == "app"
        assert corpo["conclusao"]["anotacao"] == ANOTACAO
        assert corpo["conclusao"]["concluida_em"]
        assert corpo["fechamento"] == {"estado": "fechado", "motivo": None}


# ═══════════════════════════════════════════════════════════════════════════
# O webhook: o Pedido acompanha o GitHub
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def webhook(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", SEGREDO)
    monkeypatch.setattr(settings, "github_integracao_repo", REPO)

    def _entregar(sb, acao: str, *, motivo: str | None = None, numero: int = CARD):
        app = FastAPI()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.include_router(webhooks_router.router, prefix="/api")
        app.dependency_overrides[get_supabase_client] = lambda: sb
        corpo = json.dumps(
            {
                "action": acao,
                "issue": {"number": numero, "state_reason": motivo},
                "repository": {"full_name": REPO},
            }
        ).encode()
        assinatura = "sha256=" + hmac.new(SEGREDO.encode(), corpo, hashlib.sha256).hexdigest()
        return TestClient(app).post(
            "/api/webhooks/github",
            content=corpo,
            headers={"X-GitHub-Event": "issues", "X-Hub-Signature-256": assinatura, "Content-Type": "application/json"},
        )

    return _entregar


class TestWebhook:
    def test_card_fechado_como_feito_por_fora_conclui_pelo_github(self, webhook):
        _, sb, _ = _um_passo_a_passo()

        resposta = webhook(sb, "closed", motivo="completed")

        assert resposta.status_code == 200, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["estado"], pedido["concluida_como"], pedido["fechamento_github"]) == (
            "concluida",
            "github",
            "fechado",
        )
        assert pedido.get("concluida_por") is None

    def test_card_fechado_como_nao_planejado_cancela(self, webhook):
        _, sb, _ = _um_passo_a_passo()

        webhook(sb, "closed", motivo="not_planned")

        [pedido] = sb.tabelas[TABELA]
        assert pedido["estado"] == "cancelada"
        assert pedido["cancelada_em"]

    def test_card_reaberto_reabre_com_os_checks_zerados(self, monkeypatch, webhook):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        _concluir(sb, DIRETORA, pedido_id, monkeypatch, anotacao=ANOTACAO)
        marcados = len(sb.tabelas[CHECKS])

        webhook(sb, "reopened")

        [pedido] = sb.tabelas[TABELA]
        assert pedido["estado"] == "aberta"
        assert (pedido["concluida_em"], pedido["fechamento_github"], pedido["resposta_texto"]) == (None, None, None)
        assert len(sb.tabelas[CHECKS]) == marcados + len(PASSOS)
        cartao = tecnologia_perguntas.cartao(sb, pedido, ator=DIRETORA)
        assert [p["marcado"] for p in cartao["passos"]] == [False, False, False]

    def test_o_fechamento_que_o_proprio_app_fez_nao_conclui_de_novo(self, monkeypatch, webhook):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        _concluir(sb, DIRETORA, pedido_id, monkeypatch)
        antes = dict(sb.tabelas[TABELA][0])
        conversa = len(sb.tabelas[CONVERSA])

        webhook(sb, "closed", motivo="completed")

        assert sb.tabelas[TABELA][0] == antes
        assert len(sb.tabelas[CONVERSA]) == conversa

    def test_o_card_fechado_depois_de_falhar_no_app_vira_fechado(self, monkeypatch, webhook, github):
        _, sb, pedido_id = _um_passo_a_passo()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        github["status"] = 502
        _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        webhook(sb, "closed", motivo="completed")

        [pedido] = sb.tabelas[TABELA]
        assert (pedido["concluida_como"], pedido["fechamento_github"], pedido["fechamento_motivo"]) == (
            "app",
            "fechado",
            None,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Esperando você, o lembrete e o Me explique
# ═══════════════════════════════════════════════════════════════════════════


class TestEsperandoVoce:
    def test_a_lista_traz_os_dois_tipos_e_diz_o_que_esta_com_a_vitta(self, monkeypatch):
        ponte, sb, _ = _um_passo_a_passo()
        _criar(ponte, destinatario_id=PEDRO["id"], assunto="cadastrar a suplente")
        ponte.post(
            CRIAR,
            json={**PASSO_A_PASSO, "tipo": "pergunta", "passos": [], "card_numero": None, "assunto": "quem assina"},
            headers={"X-API-Key": CHAVE},
        )

        lista = _tela(sb, DIRETORA, monkeypatch).get("/api/admin/tecnologia/perguntas/esperando").json()

        assert [(i["tipo"], i["assunto"], i["com_a_vitta"]) for i in lista] == [
            ("passo_a_passo", "publicar o Regimento do NSP", False),
            ("pergunta", "quem assina", False),
            ("passo_a_passo", "cadastrar a suplente", True),
        ]


class TestLembrete:
    def test_o_passo_a_passo_aberto_ha_3_dias_e_lembrado_uma_vez(self, emails):
        _, sb, _ = _um_passo_a_passo()
        sb.tabelas.pop("notificacoes", None)
        emails.clear()
        agora = datetime.fromisoformat(sb.tabelas[TABELA][0]["criado_em"].replace("Z", "+00:00")) + timedelta(days=3)

        assert tecnologia_perguntas.lembrar(sb, agora) == 1
        assert tecnologia_perguntas.lembrar(sb, agora) == 0

        [sino] = sb.tabelas["notificacoes"]
        assert (sino["titulo"], sino["mensagem"]) == (
            "Seu passo a passo espera há 3 dias",
            "publicar o Regimento do NSP",
        )
        [email] = emails
        assert email["assunto"] == "Seu passo a passo espera há 3 dias: publicar o Regimento do NSP"


class TestMeExplique:
    def test_o_pedido_ao_modelo_leva_os_passos(self):
        _, sb, _ = _um_passo_a_passo()
        [pedido] = sb.tabelas[TABELA]

        texto = tecnologia_me_explique.pedido(sb.tabelas["tecnologia_demandas"][0], pedido, [])

        assert "O PASSO A PASSO DA VITTA" in texto
        assert "Passos:" in texto
        assert "3. Como saber que acabou: o Regimento aparece como Publicado na lista." in texto
