"""O Pedido da Vitta que ficou aberto: o webhook e o lembrete (issue #2281, ADR 0113, decisão 7).

Desde a issue #2281 o Pedido não nasce mais pela ponte, mas os que já estão
no banco seguem vivos: o Passo a passo acompanha o card no GitHub (fechado
como feito conclui "pelo GitHub", fechado como não planejado cancela; ADR
0110, decisão 7), o Pedido de implantação não muda com o card (ADR 0111,
decisão 7), e os dois recebem o lembrete único depois de 3 dias abertos.
Antes, estes testes criavam o Pedido pela rota da ponte que saiu; aqui ele já
está gravado, como o deixou a ponte.

Pela ROTA de verdade do webhook, com o Supabase em memória de
`test_tecnologia_vinculo` e o e-mail gravado na porta do transporte.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_vinculo import _demanda, _pessoa, _SupabaseMock  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import webhooks as webhooks_router  # noqa: E402
from app.services import tecnologia_email, tecnologia_perguntas  # noqa: E402

AGORA = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
CARD = 1961
REPO = "Vitta-Share/hospital-reunioes"
SEGREDO = "segredo-falso-de-teste-2281"

PEDRO = _pessoa("P001", "Pedro Rezende", github_login="pedrorezendefig")
DIRETORA = _pessoa("P004", "Diretora Clínica")

TABELA = "tecnologia_perguntas"
CONVERSA = "tecnologia_conversa_da_demanda"

PASSOS = [
    "Abra a aba Segurança do Paciente e clique em Documentos.",
    "Clique em Publicar no Regimento do NSP.",
    "Como saber que acabou: o Regimento aparece como Publicado na lista.",
]


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


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


def _pedido(tipo: str, *, ha: timedelta = timedelta(hours=1), **campos) -> dict:
    """O Pedido aberto, como a ponte o gravava: o card, os passos e o Destinatário."""
    assunto = "publicar o Regimento do NSP" if tipo == "passo_a_passo" else "testar o anonimato do Canal de Conduta"
    return {
        "id": f"pedido-{tipo}",
        "demanda_id": DEMANDA,
        "mensagem_id": f"msg-{tipo}",
        "autor_id": PEDRO["id"],
        "destinatario_id": DIRETORA["id"],
        "assunto": assunto,
        "texto": "Faça os passos no app.",
        "estado": "aberta",
        "tipo": tipo,
        "passos": list(PASSOS),
        "card_projeto": "hospital",
        "card_numero": CARD,
        "lembrete_enviado_em": None,
        "criado_em": (AGORA - ha).isoformat(),
        **campos,
    }


def _banco(*pedidos: dict) -> _SupabaseMock:
    return _SupabaseMock(
        {
            "participantes": [dict(PEDRO), dict(DIRETORA)],
            "tecnologia_demandas": [
                _demanda(DEMANDA, titulo="A Ata assinada no app", autor_id=PEDRO["id"], origem="vitta")
            ],
            TABELA: [dict(p) for p in pedidos],
            CONVERSA: [],
        }
    )


@pytest.fixture
def webhook(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", SEGREDO)
    monkeypatch.setattr(settings, "github_integracao_repo", REPO)

    def _entregar(sb, acao: str, *, motivo: str | None = None):
        app = FastAPI()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.include_router(webhooks_router.router, prefix="/api")
        app.dependency_overrides[get_supabase_client] = lambda: sb
        corpo = json.dumps(
            {"action": acao, "issue": {"number": CARD, "state_reason": motivo}, "repository": {"full_name": REPO}}
        ).encode()
        assinatura = "sha256=" + hmac.new(SEGREDO.encode(), corpo, hashlib.sha256).hexdigest()
        return TestClient(app).post(
            "/api/webhooks/github",
            content=corpo,
            headers={"X-GitHub-Event": "issues", "X-Hub-Signature-256": assinatura, "Content-Type": "application/json"},
        )

    return _entregar


class TestOWebhook:
    def test_o_card_fechado_como_feito_conclui_o_passo_a_passo_pelo_github(self, webhook):
        sb = _banco(_pedido("passo_a_passo"))

        resposta = webhook(sb, "closed", motivo="completed")

        assert resposta.status_code == 200, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["estado"], pedido["concluida_como"], pedido["fechamento_github"]) == (
            "concluida",
            "github",
            "fechado",
        )
        assert pedido.get("concluida_por") is None

    def test_o_card_fechado_como_nao_planejado_cancela_o_passo_a_passo(self, webhook):
        sb = _banco(_pedido("passo_a_passo"))

        webhook(sb, "closed", motivo="not_planned")

        [pedido] = sb.tabelas[TABELA]
        assert pedido["estado"] == "cancelada"
        assert pedido["cancelada_em"]

    def test_o_card_fechado_nao_muda_o_pedido_de_implantacao(self, webhook):
        """O Pedido de implantação fechou o card ao nascer: o mesmo evento
        volta pelo webhook, e o Pedido segue aberto, esperando o hospital."""
        sb = _banco(_pedido("implantacao"))
        antes = dict(sb.tabelas[TABELA][0])

        resposta = webhook(sb, "closed", motivo="completed")

        assert resposta.status_code == 200, resposta.text
        assert sb.tabelas[TABELA][0] == antes
        assert sb.tabelas[CONVERSA] == []


class TestOLembrete:
    def test_o_passo_a_passo_aberto_ha_3_dias_e_lembrado_uma_vez(self, emails):
        sb = _banco(_pedido("passo_a_passo", ha=timedelta(days=3)))

        assert tecnologia_perguntas.lembrar(sb, AGORA) == 1
        assert tecnologia_perguntas.lembrar(sb, AGORA) == 0

        [sino] = sb.tabelas["notificacoes"]
        assert (sino["titulo"], sino["mensagem"]) == (
            "Seu passo a passo espera há 3 dias",
            "publicar o Regimento do NSP",
        )
        [email] = emails
        assert email["assunto"] == "Seu passo a passo espera há 3 dias: publicar o Regimento do NSP"

    def test_o_pedido_de_implantacao_aberto_ha_3_dias_e_lembrado_uma_vez(self, emails):
        sb = _banco(_pedido("implantacao", ha=timedelta(days=3)))

        assert tecnologia_perguntas.lembrar(sb, AGORA - timedelta(hours=1)) == 0
        assert tecnologia_perguntas.lembrar(sb, AGORA) == 1
        assert tecnologia_perguntas.lembrar(sb, AGORA + timedelta(days=1)) == 0

        [sino] = sb.tabelas["notificacoes"]
        assert (sino["destinatario_id"], sino["mensagem"]) == (DIRETORA["id"], "testar o anonimato do Canal de Conduta")
        assert len(emails) == 1
