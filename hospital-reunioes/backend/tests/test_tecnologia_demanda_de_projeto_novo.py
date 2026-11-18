"""A Demanda de um Projeto novo (issue #1967, PRD #1964).

A ponte de automação cria a Demanda do PRD de um Projeto que o app ainda não
conhece (o PedroOS, por exemplo), pelo par projeto mais número da issue: Origem
Vitta, com o nome do Projeto, o título e o link do PRD. Pedir de novo devolve a
mesma. Essa Demanda tem a Conversa da Demanda e o link, e nenhuma Etapa vinda
do GitHub: o app não lê o repositório desse Projeto, então ela fica fora do
espelho e da conferência de hora em hora.

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

CHAVE = "chave-de-automacao-do-teste-1967"
BASE = "/api/automacao/tecnologia"
PRD_DO_OS = f"{BASE}/projetos/os/issues/915/demanda"
LINK_DO_PRD = "https://github.com/Vitta-Share/os/issues/915"
PEDIDO = {"nome_do_projeto": "PedroOS", "titulo": "Perguntas do PedroOS no app", "link": LINK_DO_PRD}

PEDRO = _pessoa("P1", "Pedro Rezende", github_login="pedrorezendefig")
DIRETOR = _pessoa("P3", "Diretor Geral")
PRODUTO = {"id": "prod-1", "nome": "Aplicativo", "ativo": True, "ordem": 0}


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def chave_configurada(monkeypatch):
    monkeypatch.setattr(settings, "tecnologia_automacao_api_key", CHAVE)
    monkeypatch.setattr(settings, "github_login_dono", "pedrorezendefig")


def _cliente(demandas: list[dict] | None = None) -> tuple[TestClient, _SupabaseMock]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = _SupabaseMock(
        {
            "participantes": [dict(PEDRO), dict(DIRETOR)],
            "tecnologia_produtos": [dict(PRODUTO)],
            "tecnologia_demandas": [dict(d) for d in (demandas or [])],
            "tecnologia_conversa_da_demanda": [],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app), sb


def _pedir_a_demanda(cliente: TestClient, rota: str = PRD_DO_OS, **campos):
    return cliente.post(rota, json={**PEDIDO, **campos}, headers={"X-API-Key": CHAVE})


def _demandas(sb) -> list[dict]:
    return sb.tabelas["tecnologia_demandas"]


class TestADemandaNasceUmaVez:
    def test_pedir_a_demanda_do_prd_de_projeto_novo_cria_uma_e_pedir_de_novo_devolve_a_mesma(self):
        cliente, sb = _cliente()

        primeira = _pedir_a_demanda(cliente)
        segunda = _pedir_a_demanda(cliente)

        assert primeira.status_code == 201, primeira.text
        assert segunda.status_code == 200, segunda.text
        [criada] = _demandas(sb)
        assert primeira.json() == {"id": str(criada["id"]), "criada": True}
        assert segunda.json() == {"id": str(criada["id"]), "criada": False}

    def test_o_mesmo_numero_em_outro_projeto_e_outra_demanda(self):
        """A chave e projeto mais numero: a #915 do Hospital nao e o PRD do PedroOS."""
        cliente, sb = _cliente([_demanda("d-hospital-915", github_issue_numero=915, projeto="hospital")])

        resposta = _pedir_a_demanda(cliente)

        assert resposta.status_code == 201, resposta.text
        assert resposta.json()["id"] != "d-hospital-915"
        assert len(_demandas(sb)) == 2


class TestOQueADemandaNovaMostra:
    def test_a_demanda_nova_e_da_vitta_com_o_nome_do_projeto_o_titulo_e_o_link_do_prd(self):
        cliente, sb = _cliente()

        _pedir_a_demanda(cliente)

        [criada] = _demandas(sb)
        assert criada["origem"] == "vitta"
        assert criada["projeto"] == "os"
        assert criada["projeto_nome"] == "PedroOS"
        assert criada["titulo"] == "Perguntas do PedroOS no app"
        assert criada["raiz_url"] == LINK_DO_PRD
        assert criada["github_issue_numero"] == 915
        assert criada["etapa"] == "registrada"
        assert criada["autor_id"] == PEDRO["id"]

    def test_a_ponte_acha_a_demanda_nova_e_escreve_na_conversa_dela(self, monkeypatch):
        monkeypatch.setattr(tecnologia_email, "_enviar_email", lambda *a, **kw: True)
        cliente, sb = _cliente()
        _pedir_a_demanda(cliente)
        # O banco da o UUID; o duble da um id de texto, que a rota da conversa recusa.
        demanda_id = "7d1e7a2b-3d4f-4a6b-9c8d-1e2f3a4b5c6d"
        _demandas(sb)[0]["id"] = demanda_id

        achada = cliente.get(PRD_DO_OS, headers={"X-API-Key": CHAVE})
        escrita = cliente.post(
            f"{BASE}/demandas/{demanda_id}/conversa",
            json={"texto": "Diretor, qual das duas?", "github_login": "pedrorezendefig"},
            headers={"X-API-Key": CHAVE},
        )

        assert achada.json() == {"id": demanda_id}
        assert escrita.status_code == 201, escrita.text
        [mensagem] = sb.tabelas["tecnologia_conversa_da_demanda"]
        assert (mensagem["demanda_id"], mensagem["texto"]) == (demanda_id, "Diretor, qual das duas?")


class TestAsRecusas:
    @pytest.mark.parametrize("projeto", ["hospital", "ana"])
    def test_projeto_que_o_app_le_nao_ganha_demanda_pela_ponte(self, projeto):
        cliente, sb = _cliente()

        resposta = _pedir_a_demanda(cliente, f"{BASE}/projetos/{projeto}/issues/915/demanda")

        assert resposta.status_code == 409
        assert "espelho" in resposta.json()["detail"]
        assert _demandas(sb) == []

    def test_projeto_que_o_app_le_devolve_a_demanda_que_ja_existe(self):
        cliente, sb = _cliente([_demanda("d-hospital-915", github_issue_numero=915, projeto="hospital")])

        resposta = _pedir_a_demanda(cliente, f"{BASE}/projetos/hospital/issues/915/demanda")

        assert resposta.status_code == 200
        assert resposta.json() == {"id": "d-hospital-915", "criada": False}
        assert len(_demandas(sb)) == 1

    def test_a_demanda_apagada_nao_volta(self):
        lapide = _demanda(
            "d-os-915", github_issue_numero=915, projeto="os", origem="vitta", apagada_em="2026-11-18T10:00:00Z"
        )
        cliente, sb = _cliente([lapide])

        resposta = _pedir_a_demanda(cliente)

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "A Demanda deste PRD foi apagada no aplicativo."
        assert _demandas(sb) == [lapide]

    @pytest.mark.parametrize(
        "campos",
        [{"link": "http://github.com/x"}, {"link": "javascript:alert(1)"}, {"titulo": "  "}, {"nome_do_projeto": ""}],
        ids=["link-sem-https", "link-script", "titulo-vazio", "nome-vazio"],
    )
    def test_pedido_incompleto_e_recusado_sem_gravar(self, campos):
        cliente, sb = _cliente()

        resposta = _pedir_a_demanda(cliente, **campos)

        assert resposta.status_code == 422
        assert _demandas(sb) == []

    @pytest.mark.parametrize("projeto", ["OS", "os_novo", "-os", "a" * 41])
    def test_nome_de_projeto_fora_do_formato_e_recusado(self, projeto):
        cliente, sb = _cliente()

        resposta = _pedir_a_demanda(cliente, f"{BASE}/projetos/{projeto}/issues/915/demanda")

        assert resposta.status_code == 422
        assert _demandas(sb) == []

    @pytest.mark.parametrize("cabecalhos", [{}, {"X-API-Key": CHAVE + "x"}], ids=["ausente", "errada"])
    def test_sem_a_chave_nao_cria(self, cabecalhos):
        cliente, sb = _cliente()

        resposta = cliente.post(PRD_DO_OS, json=PEDIDO, headers=cabecalhos)

        assert resposta.status_code == 401
        assert _demandas(sb) == []
