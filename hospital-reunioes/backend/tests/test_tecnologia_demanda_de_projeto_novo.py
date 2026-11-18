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
import re
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_vinculo import _demanda, _pessoa, _SupabaseMock  # noqa: E402
from test_tecnologia_webhook_github import _demanda as _demanda_do_webhook  # noqa: E402
from test_tecnologia_webhook_github import _GithubFalso as _GithubDoWebhook  # noqa: E402
from test_tecnologia_webhook_github import _issue  # noqa: E402
from test_tecnologia_webhook_github import _SupabaseMock as _SupabaseDoWebhook  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import tecnologia_automacao  # noqa: E402
from app.services import github_client, tecnologia, tecnologia_email, tecnologia_sincronizacao  # noqa: E402

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


# ═══════════════════════════════════════════════════════════════════════════
# Fora do espelho e da conferência de hora em hora
# ═══════════════════════════════════════════════════════════════════════════


def _a_demanda_criada_pela_ponte() -> dict:
    """A linha que a ponte grava, lida de volta do duble."""
    cliente, sb = _cliente()
    _pedir_a_demanda(cliente)
    [criada] = _demandas(sb)
    return {**_demanda_do_webhook("x"), **criada, "estado": "nova"}


class TestForaDoEspelho:
    def test_a_conferencia_de_hora_em_hora_nao_le_o_github_pela_demanda_do_projeto_novo(self, monkeypatch):
        """A #915 do Hospital e lida; a #915 do PedroOS nao e lida nem contada:
        o app nao le aquele repositorio, e ler a do Hospital no lugar dela daria
        a Etapa de outra issue."""
        gh = _GithubDoWebhook({915: _issue(915, labels=("in-progress",))})
        monkeypatch.setattr(github_client, "ler_issue", gh.ler_issue)
        monkeypatch.setattr(github_client, "ler_sub_issues", gh.ler_sub_issues)
        do_os = _a_demanda_criada_pela_ponte()
        sb = _SupabaseDoWebhook(
            {
                "tecnologia_demandas": [_demanda_do_webhook("DH", github_issue_numero=915), do_os],
                "tecnologia_conversas": [],
            }
        )

        contagem = tecnologia_sincronizacao.reconciliar_vinculos(sb)

        assert gh.leituras == [915]
        assert contagem["lidas"] == 1
        assert sb.tabelas["tecnologia_demandas"][1] == do_os

    def test_atualizar_a_demanda_do_projeto_novo_nao_le_o_github(self, monkeypatch):
        gh = _GithubDoWebhook({915: _issue(915, labels=("in-progress",))})
        monkeypatch.setattr(github_client, "ler_issue", gh.ler_issue)
        monkeypatch.setattr(github_client, "ler_sub_issues", gh.ler_sub_issues)
        do_os = _a_demanda_criada_pela_ponte()
        sb = _SupabaseDoWebhook({"tecnologia_demandas": [do_os], "tecnologia_conversas": []})

        mudou = tecnologia_sincronizacao.sincronizar_demanda(sb, do_os)

        assert mudou is False
        assert gh.leituras == []
        assert sb.tabelas["tecnologia_demandas"] == [do_os]

    def test_o_apagar_recusa_a_demanda_do_projeto_novo(self):
        """O Apagar fecha a issue no repositorio do Hospital: no card do PedroOS
        ele fecharia a #915 do Hospital."""
        recusa = tecnologia.recusa_de_apagar(PEDRO, _a_demanda_criada_pela_ponte())

        assert recusa is not None
        assert recusa[0] == 409


# ═══════════════════════════════════════════════════════════════════════════
# A migration 163
# ═══════════════════════════════════════════════════════════════════════════

MIGRATION_163 = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "163_tecnologia_projeto_novo.sql"


@pytest.fixture
def sql() -> str:
    """O SQL que o Studio roda, sem os comentarios. A prova de que ele roda (as
    Demandas de hoje intactas, o PedroOS aceito, o nome fora do formato
    recusado, rodar duas vezes) foi feita num Postgres descartavel e esta no
    corpo do PR."""
    return re.sub(r"--[^\n]*", "", MIGRATION_163.read_text(encoding="utf-8"))


class TestAMigracao163:
    def test_o_check_aceita_projeto_novo_no_mesmo_formato_da_ponte(self, sql):
        """A restricao deixa de ser a lista Hospital e Ana e passa a ser o
        formato que a rota da ponte aceita: as duas pontas sao a mesma regra."""
        velho = sql.index("DROP CONSTRAINT IF EXISTS tecnologia_demandas_projeto_check")
        achado = re.search(r"ADD CONSTRAINT tecnologia_demandas_projeto_check\s+CHECK \(projeto ~ '([^']*)'\)", sql)
        assert achado and velho < achado.start()
        assert achado.group(1) == github_client.FORMATO_DO_PROJETO
        for projeto in ("hospital", "ana", "os"):
            assert re.fullmatch(achado.group(1), projeto)

    def test_as_demandas_que_ja_existem_nao_mudam(self, sql):
        antes_do_recibo = sql.split("INSERT INTO migracoes_aplicadas", 1)[0]
        assert "tecnologia_demandas" in antes_do_recibo, "o caso perdeu o sentido: a migration nao mexe na Demanda"
        assert not re.search(r"\bUPDATE\b|\bDELETE\b|SET DEFAULT|DROP COLUMN", antes_do_recibo, re.IGNORECASE)

    def test_o_nome_do_projeto_e_o_link_do_prd_sao_colunas_opcionais(self, sql):
        assert "ADD COLUMN IF NOT EXISTS projeto_nome TEXT;" in sql
        assert "ADD COLUMN IF NOT EXISTS raiz_url TEXT;" in sql
        assert re.search(r"CHECK \(raiz_url IS NULL OR raiz_url LIKE 'https://%'\)", sql)

    def test_a_migration_grava_o_recibo_163_por_ultimo(self, sql):
        instrucoes = [i.strip() for i in sql.split(";") if i.strip()]
        assert instrucoes[-1] == "INSERT INTO migracoes_aplicadas (numero) VALUES (163) ON CONFLICT (numero) DO NOTHING"
