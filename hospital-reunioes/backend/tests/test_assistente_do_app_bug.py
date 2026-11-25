"""O Assistente do app: relatar um bug (issue #2275, PRD #2262, ADR 0113,
decisão 8).

O Roteiro do bug no robô do canto da tela: Onde, O que aconteceu, O que
esperava, Como repetir e o print. As quatro respostas viram uma Demanda
Registrada, de Origem "Relato no app"; o print vira Anexo dela; o clique de
envio cria a issue pela mesma porta do "Criar o card" (`tecnologia_envio`).

Tudo pela ROTA. O Supabase é um banco de memória daqui, o bucket e o GitHub são
dublados: nada sai para fora.
"""

from __future__ import annotations

import os
import sys
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import assistente_do_app as assistente_router  # noqa: E402
from app.services import github_client, storage, tecnologia_espelho  # noqa: E402

BUG = "/api/assistente-do-app/bug"

PRINT_PNG = b"\x89PNG\r\n\x1a\n" + b"BYTES-DO-PRINT" * 10

SUPER_ADMIN = {
    "id": "P1",
    "nome_completo": "Pedro Rezende",
    "access_profile": "super_admin",
    "github_login": "pedro",
}
COLABORADORA = {
    "id": "P7",
    "nome_completo": "Ana Souza",
    "access_profile": "regular",
    "github_login": None,
}

RESPOSTAS = {
    "onde": "Na tela de Pendências",
    "o_que_aconteceu": "O botão Salvar não faz nada",
    "o_que_esperava": "Que a Pendência fosse salva",
    "como_repetir": "Abrir uma Pendência e clicar em Salvar",
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


class _Consulta:
    def __init__(self, banco: _Banco, tabela: str):
        self._banco = banco
        self._tabela = tabela
        self._filtros: list = []
        self._operacao = ("select", None)

    def select(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def is_(self, coluna, _valor):
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def insert(self, linha):
        self._operacao = ("insert", linha)
        return self

    def update(self, mudanca):
        self._operacao = ("update", mudanca)
        return self

    def execute(self):
        linhas = self._banco.tabelas.setdefault(self._tabela, [])
        operacao, valor = self._operacao
        if operacao == "insert":
            nova = {"id": str(uuid.uuid4()), **valor}
            linhas.append(nova)
            return type("R", (), {"data": [dict(nova)]})()
        casadas = [linha for linha in linhas if all(f(linha) for f in self._filtros)]
        if operacao == "update":
            for linha in casadas:
                linha.update(valor)
        return type("R", (), {"data": [dict(linha) for linha in casadas]})()


class _Banco:
    def __init__(self):
        self.tabelas: dict[str, list[dict]] = {
            "tecnologia_produtos": [{"id": "prod-1", "nome": "Aplicativo", "ativo": True, "ordem": 1}],
        }

    def table(self, nome):
        return _Consulta(self, nome)

    def demandas(self) -> list[dict]:
        return self.tabelas.get("tecnologia_demandas", [])


class _GitHub:
    def __init__(self):
        self.criadas: list[dict] = []
        self.tentativas = 0
        self.erro: Exception | None = None

    def criar_issue(self, *, projeto, titulo, corpo, labels, assignees):
        self.tentativas += 1
        if self.erro is not None:
            raise self.erro
        criada = {"projeto": projeto, "titulo": titulo, "corpo": corpo, "labels": labels, "assignees": assignees}
        self.criadas.append(criada)
        return {
            "number": 900 + len(self.criadas),
            "title": titulo,
            "body": corpo,
            "state": "open",
            "labels": [{"name": nome} for nome in labels],
            "assignees": [{"login": login} for login in assignees],
            "user": {"login": "hospital-app"},
        }


@pytest.fixture
def gh(monkeypatch) -> _GitHub:
    falso = _GitHub()
    monkeypatch.setattr(github_client, "criar_issue", falso.criar_issue)
    monkeypatch.setattr(github_client, "integracao_configurada", lambda *_a, **_kw: True)
    return falso


@pytest.fixture
def bucket(monkeypatch) -> list[bytes]:
    guardados: list[bytes] = []

    def _upload(_supabase, *, bucket, path, content, content_type):
        guardados.append(content)
        return True

    monkeypatch.setattr(storage, "upload_private", _upload)
    return guardados


def _app(banco: _Banco, pessoa: dict) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(assistente_router.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: banco
    app.dependency_overrides[assistente_router.pessoa_logada] = lambda: dict(pessoa)
    return TestClient(app)


def _relatar(client: TestClient, respostas: dict | None = None, *, com_print: bool = True) -> str:
    """As quatro respostas, o print e o resumo: devolve o id da Demanda."""
    resposta = client.post(BUG, json=RESPOSTAS if respostas is None else respostas)
    assert resposta.status_code == 200, resposta.text
    demanda_id = resposta.json()["demanda_id"]
    if com_print:
        enviado = client.post(f"{BUG}/{demanda_id}/print", files={"imagem": ("tela.png", PRINT_PNG, "image/png")})
        assert enviado.status_code == 200, enviado.text
    return demanda_id


class TestOEnvioCriaAIssue:
    def test_o_bug_com_as_cinco_respostas_cria_a_issue_com_as_secoes_do_roteiro_sem_o_print(self, gh, bucket):
        client = _app(_Banco(), SUPER_ADMIN)
        demanda_id = _relatar(client)

        resposta = client.post(f"{BUG}/{demanda_id}/enviar")

        assert resposta.status_code == 200, resposta.text
        assert len(gh.criadas) == 1
        criada = gh.criadas[0]
        assert "type:fix" in criada["labels"]
        corpo = criada["corpo"]
        assert "- **Onde:** Na tela de Pendências" in corpo
        assert "- **O que aconteceu:** O botão Salvar não faz nada" in corpo
        assert "- **O que esperava:** Que a Pendência fosse salva" in corpo
        assert "- **Como repetir:** Abrir uma Pendência e clicar em Salvar" in corpo
        assert "## Critérios de aceite" in corpo
        assert "Anexos: 1 imagem na Demanda" in corpo
        assert "tela.png" not in corpo
        assert "BYTES-DO-PRINT" not in corpo
        assert bucket == [PRINT_PNG]


class TestAFilaDependeDeQuemRelata:
    def test_o_bug_do_super_admin_nasce_ready_for_agent(self, gh, bucket):
        client = _app(_Banco(), SUPER_ADMIN)
        demanda_id = _relatar(client)

        assert client.post(f"{BUG}/{demanda_id}/enviar").status_code == 200

        assert "ready-for-agent" in gh.criadas[0]["labels"]
        assert "needs-triage" not in gh.criadas[0]["labels"]

    def test_o_bug_de_outro_perfil_nasce_needs_triage(self, gh, bucket):
        client = _app(_Banco(), COLABORADORA)
        demanda_id = _relatar(client)

        assert client.post(f"{BUG}/{demanda_id}/enviar").status_code == 200

        assert "needs-triage" in gh.criadas[0]["labels"]
        assert "ready-for-agent" not in gh.criadas[0]["labels"]


class TestADemandaDoRelato:
    def test_a_demanda_nasce_registrada_com_a_origem_relato_no_app(self, gh, bucket):
        banco = _Banco()
        _relatar(_app(banco, COLABORADORA))

        demanda = banco.demandas()[0]
        assert demanda["origem"] == "relato"
        assert demanda["etapa"] == "registrada"
        assert demanda["autor_id"] == "P7"
        assert demanda.get("github_issue_numero") is None

    def test_o_envio_grava_o_vinculo_e_o_espelho_nao_cria_outra_demanda(self, gh, bucket, monkeypatch):
        banco = _Banco()
        client = _app(banco, SUPER_ADMIN)
        demanda_id = _relatar(client)
        assert client.post(f"{BUG}/{demanda_id}/enviar").status_code == 200
        numero = banco.demandas()[0]["github_issue_numero"]
        criada = gh.criadas[0]
        # A issue como o GitHub a devolve, com uma `area:` de app que a triagem
        # pode pôr depois: é o caso em que o espelho criaria uma Demanda.
        issue = {
            "number": numero,
            "title": criada["titulo"],
            "body": criada["corpo"],
            "state": "open",
            "labels": [{"name": nome} for nome in [*criada["labels"], "area:frontend"]],
        }
        monkeypatch.setattr(github_client, "ler_issue", lambda *_a, **_kw: issue)

        assert numero == 901
        assert tecnologia_espelho.espelhar(banco, "hospital", numero) is None
        assert len(banco.demandas()) == 1


class TestRotuloSemResposta:
    def test_rotulo_sem_resposta_sai_nao_informado_no_resumo_e_na_issue(self, gh, bucket):
        client = _app(_Banco(), SUPER_ADMIN)
        respostas = {**RESPOSTAS, "como_repetir": "   ", "o_que_esperava": ""}

        registrado = client.post(BUG, json=respostas)

        assert registrado.status_code == 200, registrado.text
        resumo = registrado.json()["resumo"]
        assert resumo["como_repetir"] == "não informado"
        assert resumo["o_que_esperava"] == "não informado"
        demanda_id = registrado.json()["demanda_id"]
        assert client.post(f"{BUG}/{demanda_id}/enviar").status_code == 200
        assert "- **Como repetir:** não informado" in gh.criadas[0]["corpo"]
        assert "- **O que esperava:** não informado" in gh.criadas[0]["corpo"]


class TestFalhaNoGitHub:
    def test_a_falha_devolve_o_motivo_e_nada_reenvia_ate_o_proximo_clique(self, gh, bucket):
        banco = _Banco()
        client = _app(banco, SUPER_ADMIN)
        demanda_id = _relatar(client)
        gh.erro = github_client.GithubIndisponivelError("GitHub respondeu 502")

        falhou = client.post(f"{BUG}/{demanda_id}/enviar")

        assert falhou.status_code == 502
        assert "Tentar de novo" in falhou.json()["detail"]
        assert gh.tentativas == 1
        assert banco.demandas()[0]["envio_estado"] == "falhou"

        gh.erro = None
        de_novo = client.post(f"{BUG}/{demanda_id}/enviar")

        assert de_novo.status_code == 200, de_novo.text
        assert gh.tentativas == 2
        assert len(gh.criadas) == 1
        assert banco.demandas()[0]["github_issue_numero"] == 901

    def test_o_bug_ja_enviado_nao_cria_a_segunda_issue(self, gh, bucket):
        client = _app(_Banco(), SUPER_ADMIN)
        demanda_id = _relatar(client)
        assert client.post(f"{BUG}/{demanda_id}/enviar").status_code == 200

        assert client.post(f"{BUG}/{demanda_id}/enviar").status_code == 409
        assert len(gh.criadas) == 1

    def test_outra_pessoa_nao_envia_o_relato_de_quem_relatou(self, gh, bucket):
        banco = _Banco()
        demanda_id = _relatar(_app(banco, COLABORADORA))

        assert _app(banco, SUPER_ADMIN).post(f"{BUG}/{demanda_id}/enviar").status_code == 404
        assert gh.criadas == []


class TestOPrint:
    def test_o_print_so_entra_como_imagem(self, gh, bucket):
        client = _app(_Banco(), SUPER_ADMIN)
        demanda_id = _relatar(client, com_print=False)

        resposta = client.post(f"{BUG}/{demanda_id}/print", files={"imagem": ("dados.csv", b"a,b", "text/csv")})

        assert resposta.status_code == 422
        assert bucket == []
