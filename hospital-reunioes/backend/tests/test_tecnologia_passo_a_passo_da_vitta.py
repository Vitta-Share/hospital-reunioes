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
from datetime import datetime, timedelta

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
from app.services import github_client, tecnologia_email, tecnologia_perguntas  # noqa: E402

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

    def test_passo_a_passo_de_projeto_sem_repositorio_e_recusado_citando_o_projeto(self, emails):
        # Issue #2190: o app só fecha card no repositório que conhece. Num
        # Projeto sem repositório, o Concluir sempre cairia em "Não chegou ao
        # GitHub"; a ponte recusa já na criação, e nada fica gravado.
        ponte, sb = _ponte()

        resposta = _criar(ponte, card_projeto="vitta-os")

        assert resposta.status_code == 422
        assert resposta.json() == {
            "detail": "O app não alcança o repositório do Projeto vitta-os, então não fecharia o card. "
            "Mande como Pergunta."
        }
        assert sb.tabelas[TABELA] == []
        assert sb.tabelas[CONVERSA] == []
        assert emails == []

    def test_sem_card_projeto_vale_o_projeto_da_demanda_e_sem_repositorio_e_recusado(self):
        ponte, sb = _ponte()
        sb.tabelas["tecnologia_demandas"][0]["projeto"] = "vitta-os"

        resposta = _criar(ponte)

        assert resposta.status_code == 422
        assert "Projeto vitta-os" in resposta.json()["detail"]
        assert sb.tabelas[TABELA] == []

    def test_o_da_ana_e_aceito_com_o_repositorio_dela_configurado(self, monkeypatch):
        monkeypatch.setattr(settings, "github_integracao_repo_ana", "pedrorezendefig/ana")
        ponte, sb = _ponte()

        resposta = _criar(ponte, card_projeto="ana")

        assert resposta.status_code == 201, resposta.text
        assert sb.tabelas[TABELA][0]["card_projeto"] == "ana"

    def test_o_da_ana_e_recusado_com_a_variavel_vazia(self, monkeypatch):
        monkeypatch.setattr(settings, "github_integracao_repo_ana", "")
        ponte, sb = _ponte()

        resposta = _criar(ponte, card_projeto="ana")

        assert resposta.status_code == 422
        assert resposta.json() == {
            "detail": "O app não alcança o repositório do Projeto ana, então não fecharia o card. Mande como Pergunta."
        }
        assert sb.tabelas[TABELA] == []

    @pytest.mark.parametrize("card_projeto", [None, "vitta-os"], ids=["sem-card-projeto", "card-projeto-sem-repo"])
    def test_a_pergunta_de_projeto_sem_repositorio_continua_sendo_criada(self, card_projeto):
        ponte, sb = _ponte()
        sb.tabelas["tecnologia_demandas"][0]["projeto"] = "vitta-os"

        resposta = _criar(
            ponte,
            tipo="pergunta",
            passos=[],
            card_numero=None,
            card_projeto=card_projeto,
            opcoes=["Sim", "Não"],
            recomendada="A",
        )

        assert resposta.status_code == 201, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert pedido["tipo"] == "pergunta"
        assert "card_projeto" not in pedido

    def test_o_modulo_do_pedido_recusa_antes_de_gravar(self):
        _, sb = _ponte()
        [demanda] = sb.tabelas["tecnologia_demandas"]

        with pytest.raises(tecnologia_perguntas.PerguntaRecusadaError, match="Projeto vitta-os"):
            tecnologia_perguntas.criar(
                sb,
                {**demanda, "projeto": "vitta-os"},
                autor=PEDRO,
                destinatario_id=DIRETORA["id"],
                assunto="publicar o Regimento do NSP",
                texto="Publique o Regimento do NSP no app.",
                linhas=QUATRO_LINHAS,
                tipo="passo_a_passo",
                passos=PASSOS,
                card_numero=CARD,
            )

        assert sb.tabelas[TABELA] == []
        assert sb.tabelas[CONVERSA] == []

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


# ═══════════════════════════════════════════════════════════════════════════
# Concluir
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# Não chegou ao GitHub, e o Reenviar
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# Ler pela ponte
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# Esperando você, o lembrete e o Me explique
# ═══════════════════════════════════════════════════════════════════════════


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
