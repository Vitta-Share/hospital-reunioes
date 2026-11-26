"""A mensagem pela ponte com Destinatário, Assunto e "pede resposta" (issue
#1965, PRD #1964, ADR 0106).

A escrita na Conversa da Demanda pela ponte de automação (ADR 0096) ganha três
campos opcionais. Com Destinatário, o aviso (sino e e-mail) vai só para ele,
em qualquer Origem, e não pela regra das entregas. Com "pede resposta", o sino
diz "Pede sua resposta" com o Assunto, e o e-mail tem o assunto "<Nome> pede
sua resposta: <Assunto>". Sem os campos, tudo segue como hoje.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo`.
"""

from __future__ import annotations

import os
import sys

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
from app.routers import tecnologia_automacao  # noqa: E402
from app.services import tecnologia_email  # noqa: E402

CHAVE = "chave-de-automacao-do-teste-1965"
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
ESCREVER = f"/api/automacao/tecnologia/demandas/{DEMANDA}/conversa"

# O id do participante é VARCHAR(10) no formato "P001" (migration 001,
# `generate_participant_id`): o Destinatário chega nesse formato, como na
# lista de Destinatários da #1966.
PEDRO = _pessoa("P001", "Pedro Rezende", github_login="pedrorezendefig")
LUCAS = _pessoa("P002", "Lucas Sampaio", github_login="lucas-vitta")
DIRETOR = _pessoa("P003", "Diretor Geral")
DIRETORA = _pessoa("P004", "Diretora Clínica")
# Fora da diretoria e fora da regra das entregas: só o Destinatário o alcança.
GESTORA = _pessoa("P012", "Gestora da Recepção", access_profile="gestor")
DESLIGADO = {**_pessoa("P006", "Diretor Antigo"), "ativo": False}
NINGUEM = "P999"

CADASTRO = [PEDRO, LUCAS, DIRETOR, DIRETORA, GESTORA, DESLIGADO]


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def chave_configurada(monkeypatch):
    monkeypatch.setattr(settings, "tecnologia_automacao_api_key", CHAVE)


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


def _demanda_do_diretor(**campos) -> dict:
    base = {
        "autor_id": DIRETOR["id"],
        "responsavel_id": LUCAS["id"],
        "github_issue_numero": 1700,
        "origem": "diretor",
        "apagada_em": None,
    }
    base.update(campos)
    return _demanda(DEMANDA, titulo="O relatório some", **base)


def _demanda_da_vitta() -> dict:
    return _demanda_do_diretor(autor_id=PEDRO["id"], responsavel_id=PEDRO["id"], origem="vitta")


def _cliente(demanda: dict | None = None) -> tuple[TestClient, _SupabaseMock]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = _SupabaseMock(
        {
            "participantes": [dict(p) for p in CADASTRO],
            "tecnologia_demandas": [dict(demanda or _demanda_do_diretor())],
            "tecnologia_conversa_da_demanda": [],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app), sb


def _escrever(cliente: TestClient, **campos):
    corpo = {"texto": "E aí, a reunião de quinta fica às 10h?", "github_login": "pedrorezendefig", **campos}
    return cliente.post(ESCREVER, json=corpo, headers={"X-API-Key": CHAVE})


def _avisados(sb) -> list[str]:
    return sorted(n["destinatario_id"] for n in sb.tabelas.get("notificacoes", []))


# ═══════════════════════════════════════════════════════════════════════════
# Quem o Destinatário avisa
# ═══════════════════════════════════════════════════════════════════════════


class TestODestinatario:
    @pytest.mark.parametrize("demanda", [_demanda_do_diretor(), _demanda_da_vitta()], ids=["do-diretor", "da-vitta"])
    def test_com_destinatario_o_aviso_vai_so_para_ele_por_sino_e_email(self, demanda, emails):
        """Nem quem abriu a Demanda (card do diretor) nem a diretoria (card da
        Vitta): só a gestora, que a regra das entregas nunca avisaria."""
        cliente, sb = _cliente(demanda)

        resposta = _escrever(cliente, destinatario_id=GESTORA["id"])

        assert resposta.status_code == 201, resposta.text
        assert _avisados(sb) == [GESTORA["id"]]
        assert [e["para"] for e in emails] == [GESTORA["email"]]

    def test_sem_destinatario_o_aviso_segue_a_regra_de_hoje(self, emails):
        """ADR 0096, decisão 4: no card da Vitta, a diretoria ativa."""
        cliente, sb = _cliente(_demanda_da_vitta())

        resposta = _escrever(cliente)

        assert resposta.status_code == 201, resposta.text
        assert _avisados(sb) == sorted([DIRETOR["id"], DIRETORA["id"]])
        assert {n["titulo"] for n in sb.tabelas["notificacoes"]} == {"Pedro Rezende escreveu na Demanda"}
        assert {e["assunto"] for e in emails} == {"Pedro Rezende escreveu na Demanda: O relatório some"}

    @pytest.mark.parametrize("destinatario", [DESLIGADO["id"], NINGUEM], ids=["inativo", "inexistente"])
    def test_destinatario_inativo_ou_inexistente_recusa_com_motivo_sem_gravar(self, destinatario, emails):
        cliente, sb = _cliente()

        resposta = _escrever(cliente, destinatario_id=destinatario)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": "O Destinatário não é um participante ativo do aplicativo."}
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []
        assert _avisados(sb) == []
        assert emails == []

    def test_destinatario_que_nao_cabe_na_coluna_responde_422_sem_gravar(self, emails):
        """`notificacoes.destinatario_id` é VARCHAR(10): um id maior que isso
        nunca é de participante e para no payload, antes de gravar."""
        cliente, sb = _cliente()

        resposta = _escrever(cliente, destinatario_id="7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d")

        assert resposta.status_code == 422
        [erro] = resposta.json()["detail"]
        assert (erro["loc"][-1], erro["type"]) == ("destinatario_id", "string_too_long")
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []
        assert emails == []


# ═══════════════════════════════════════════════════════════════════════════
# O texto do aviso com "pede resposta"
# ═══════════════════════════════════════════════════════════════════════════

ASSUNTO = "confirmar horário da reunião de quinta"


class TestPedeResposta:
    def test_com_pede_resposta_o_sino_e_o_email_dizem_pede_sua_resposta_com_o_assunto(self, emails):
        cliente, sb = _cliente()

        resposta = _escrever(cliente, destinatario_id=DIRETORA["id"], assunto=ASSUNTO, pede_resposta=True)

        assert resposta.status_code == 201, resposta.text
        [aviso] = sb.tabelas["notificacoes"]
        assert (aviso["destinatario_id"], aviso["titulo"], aviso["mensagem"]) == (
            DIRETORA["id"],
            "Pede sua resposta",
            ASSUNTO,
        )
        assert aviso["referencia_id"] == DEMANDA
        [email] = emails
        assert email["assunto"] == "Pedro Rezende pede sua resposta: confirmar horário da reunião de quinta"
        link = f"https://app.hsm.test/admin/tecnologia?demanda={DEMANDA}"
        for corpo in (email["html"], email["texto"]):
            assert "O relatório some" in corpo
            assert ASSUNTO in corpo
            assert link in corpo

    def test_sem_pede_resposta_o_assunto_nao_muda_o_texto_de_hoje(self, emails):
        cliente, sb = _cliente()

        resposta = _escrever(cliente, destinatario_id=DIRETORA["id"], assunto=ASSUNTO)

        assert resposta.status_code == 201, resposta.text
        [aviso] = sb.tabelas["notificacoes"]
        assert (aviso["titulo"], aviso["mensagem"]) == ("Pedro Rezende escreveu na Demanda", "O relatório some")
        assert [e["assunto"] for e in emails] == ["Pedro Rezende escreveu na Demanda: O relatório some"]

    def test_pede_resposta_sem_assunto_recusa_com_motivo_sem_gravar(self, emails):
        cliente, sb = _cliente()

        resposta = _escrever(cliente, pede_resposta=True, assunto="   ")

        assert resposta.status_code == 422
        assert "Assunto" in resposta.text
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []
        assert emails == []


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════
