"""A voz do Super admin pela rota de transcricao (PRD #726, ADR 0056).

O Assistente de entrada saiu do codigo com a ADR 0077 (issue #1386), e o chat
da aba Tecnologia, com a leitura do print e a cerca do que veio de fora, saiu
na issue #2279 (ADR 0113, decisao 7). Fica aqui a voz: o Super admin passa
pela rota de transcricao que ja existe, com o gate de pe.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """O slowapi conta por PROCESSO e o TestClient sempre chega do mesmo
    endereco: sem o reset, o 11o request do ARQUIVO leva 429 e quem quebra e o
    teste seguinte, nao o que estourou o teto."""
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _llm_em_mock(monkeypatch):
    """O pytest carrega o `.env` real (chave de PROD). Sem isto, qualquer teste
    que chegasse ao servico bateria no provedor de verdade."""
    from app.services import ai_processor

    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "mock")
    yield


# ─── Dublês ──────────────────────────────────────────────────────────────────


@dataclass
class _Result:
    data: list


class _TableQuery:
    def __init__(
        self,
        nome: str,
        rows: list[dict],
        escritas: list[tuple[str, str, Any]],
        leituras: list[tuple[str, str]],
        falha_no_execute: dict[str, Exception],
    ):
        self._nome = nome
        self._rows = rows
        self._escritas = escritas
        self._leituras = leituras
        self._falha = falha_no_execute
        self._eq: dict[str, Any] = {}
        self._in: dict[str, list] = {}
        self._order: list[str] = []
        self._range: tuple[int, int] | None = None
        self._colunas: list[str] | None = None

    def select(self, colunas="*", *_a, **_kw):
        # O que se PEDE ao banco fica registrado: o corte de colunas do
        # Assistente (issue #732) e uma decisao sobre a consulta, e so da para
        # medi-la aqui, na borda.
        self._leituras.append((self._nome, colunas))
        # E o que se pede e o que se RECEBE. Um dublê que registrasse o `select`
        # e devolvesse a linha inteira mediria uma coisa e deixaria o codigo
        # fazer outra: apagar uma coluna da lista tirava o campo do prompt em
        # producao e a suite continuava verde, porque o dado chegava assim
        # mesmo. A projecao e o que faz cada teste de conteudo virar detector da
        # lista de colunas, sem teste novo nenhum.
        self._colunas = None if colunas == "*" else [c.strip() for c in colunas.split(",") if c.strip()]
        return self

    def order(self, coluna=None, **_kw):
        if coluna is not None:
            self._order.append(coluna)
        return self

    def range(self, inicio, fim):
        """A leitura das Demandas abertas e PAGINADA (`ler_tudo`, issue #732).

        Sem este recorte o dublê devolveria a lista inteira em toda pagina e o
        `ler_paginado` giraria ate o teto de mil linhas: a fatia passaria a ser
        provada contra um laco infinito, e nao contra a leitura.
        """
        self._range = (inicio, fim)
        return self

    def eq(self, coluna, valor):
        self._eq[coluna] = valor
        return self

    def in_(self, coluna, valores):
        self._in[coluna] = list(valores)
        return self

    # As quatro portas de ESCRITA do PostgREST. Elas existem no dublê para que
    # uma gravacao acidental apareca como uma linha em `escritas`, e nao como um
    # `AttributeError` que viraria 500: "nada foi gravado" precisa ser uma
    # assercao sobre o que a rota fez, e nao sobre o que o dublê nao sabe fazer.
    def insert(self, valores, *_a, **_kw):
        self._escritas.append((self._nome, "insert", valores))
        return self

    def update(self, valores, *_a, **_kw):
        self._escritas.append((self._nome, "update", valores))
        return self

    def upsert(self, valores, *_a, **_kw):
        self._escritas.append((self._nome, "upsert", valores))
        return self

    def delete(self, *_a, **_kw):
        self._escritas.append((self._nome, "delete", None))
        return self

    def _casa(self, linha: dict) -> bool:
        if not all(linha.get(c) == v for c, v in self._eq.items()):
            return False
        return all(linha.get(c) in v for c, v in self._in.items())

    def execute(self):
        # A falha e levantada DENTRO do `execute`, que e onde o PostgREST falha
        # de verdade: o `httpx` do timeout sobe cru de dentro da chamada, e um
        # dublê que levantasse antes provaria um caminho que nao existe.
        if self._nome in self._falha:
            raise self._falha[self._nome]
        casadas = [dict(linha) for linha in self._rows if self._casa(linha)]
        for coluna in reversed(self._order):
            casadas.sort(key=lambda linha, c=coluna: (linha.get(c) is None, linha.get(c)))
        if self._range is not None:
            inicio, fim = self._range
            casadas = casadas[inicio : fim + 1]
        # A ordenacao acontece ANTES da projecao, como no PostgREST: da para
        # ordenar por coluna que nao foi selecionada.
        if self._colunas is not None:
            casadas = [{c: linha[c] for c in self._colunas if c in linha} for linha in casadas]
        return _Result(data=casadas)


class _SupabaseMock:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas
        self.escritas: list[tuple[str, str, Any]] = []
        #: `(tabela, colunas)` de cada `select`, na ordem em que a rota os fez.
        self.leituras: list[tuple[str, str]] = []
        #: Tabela -> exceção que o `execute` dela levanta.
        self.falha_no_execute: dict[str, Exception] = {}

    def table(self, nome: str):
        return _TableQuery(
            nome,
            self.tabelas.setdefault(nome, []),
            self.escritas,
            self.leituras,
            self.falha_no_execute,
        )


def _pessoa(pid: str, *, super_admin: bool = True) -> dict:
    return {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": pid,
        "email": f"{pid}@hsm.com",
        "cargo": None,
        "area": None,
        "setor": None,
        "role": None,
        "ativo": True,
        "is_externo": False,
        "is_super_admin": super_admin,
        "access_profile": "super_admin" if super_admin else "regular",
        "perfil_pop": None,
        "perfil_ouvidoria": None,
        "github_login": None,
        "data_cadastro": "2026-01-01",
    }


def _montar_transcricao(*, logado: dict, monkeypatch) -> TestClient:
    """O router da transcricao de voz, com o gate de Reunioes DE PE.

    Nem `require_acesso_reunioes` nem `get_participante_for_user` sao dublados:
    quem resolve a pessoa e o mesmo dublê de Supabase do resto do arquivo, e o
    gate decide sobre o registro de verdade. So o servico de transcricao e
    trocado, porque ele e chamada de rede a um provedor pago.
    """
    from app.routers import transcricao as transcricao_router

    monkeypatch.setattr(transcricao_router, "transcrever", lambda audio, formato: "a Ana travou ontem")

    app = FastAPI()
    app.include_router(transcricao_router.router, prefix="/api")
    sb = _SupabaseMock(tabelas={"participantes": [logado]})

    async def _usuario() -> dict[str, Any]:
        return {"id": logado["auth_user_id"], "email": logado["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Falar e anexar (issue #729)
# ═══════════════════════════════════════════════════════════════════════════
#
# Duas costuras:
#
# * a rota de VOZ que ja existe, so para provar que o Super admin passa por ela;
# * a CERCA da mensagem que veio de fora (audio, documento, print). Ela e o
#   ponto: o que a pessoa DIGITA e dela, mas o que um audio encaminhado ou um
#   PDF de terceiro trazem nao foi escrito por quem esta conversando, e sem
#   cerca entraria no prompt na coluna zero, no meio de um documento cujas
#   secoes sao linhas em maiusculas seguidas de dois-pontos.


class TestVoz:
    """O Super admin passa pela rota de transcricao que ja existe (sem rota nova).

    O gate NAO e dublado aqui: `require_acesso_reunioes` fica de pe e resolve o
    participante pelo mesmo dublê de Supabase do resto do arquivo. Dublar a
    guarda deixaria o teste verde sobre nada, que e justamente o que ele existe
    para descartar.
    """

    def test_super_admin_passa(self, monkeypatch):
        cliente = _montar_transcricao(logado=_pessoa("p1"), monkeypatch=monkeypatch)
        resposta = cliente.post("/api/transcricao/voz", files={"audio": ("voz.webm", b"bytes", "audio/webm")})
        assert resposta.status_code == 200
        assert resposta.json() == {"texto": "a Ana travou ontem"}

    def test_quem_nao_tem_papel_nenhum_nas_reunioes_leva_403(self, monkeypatch):
        """O detector do teste de cima: sem ele, um gate que deixasse passar
        qualquer pessoa logada provaria a mesma coisa."""
        sem_papel = {**_pessoa("p3", super_admin=False), "access_profile": None, "is_super_admin": False}
        cliente = _montar_transcricao(logado=sem_papel, monkeypatch=monkeypatch)
        resposta = cliente.post("/api/transcricao/voz", files={"audio": ("voz.webm", b"bytes", "audio/webm")})
        assert resposta.status_code == 403

    def test_super_admin_so_pela_flag_legada_nao_passa_e_isso_esta_escrito(self, monkeypatch):
        """Perfil de acesso nulo com a flag legada ligada NAO e Super admin.

        Este estado (perfil zerado, `is_super_admin = true` esquecido) e o de
        quem teve o acesso tirado pela metade. O risco dele nunca foi o 403 no
        microfone, que e o que este teste mostra; foi a CONCESSAO: enquanto
        `is_super_admin` caia na flag legada quando o perfil era NULO e
        `tem_acesso_reunioes` lia NULO como "sem papel", a pessoa levava 403
        aqui e seguia passando em TODO `require_super_admin` do app. Retencao de
        Super admin depois de uma revogacao que parecia completa.

        A issue #752 fechou as duas pontas: os dois gates leem NULO explicito
        como "sem papel" (a tabela que os amarra mora em `test_super_admin.py`,
        `TestAsDuasLeiturasDoPerfilNulo`), e o `PATCH {"access_profile": null}`
        de `/admin/usuarios` zera a flag junto, em vez de sair antes do espelho
        (`test_admin_usuarios.py`, `TestPerfilZeradoTiraOSuperAdmin`).
        """
        so_a_flag = {**_pessoa("p4"), "access_profile": None, "is_super_admin": True}
        cliente = _montar_transcricao(logado=so_a_flag, monkeypatch=monkeypatch)
        resposta = cliente.post("/api/transcricao/voz", files={"audio": ("voz.webm", b"bytes", "audio/webm")})
        assert resposta.status_code == 403
