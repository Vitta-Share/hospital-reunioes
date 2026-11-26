"""A Mensagem pelo terminal (issue #1805, PRD #1803, ADR 0096).

A ponte de automação (a mesma chave da leitura dos anexos) ganha duas rotas:
achar a Demanda de uma issue-raiz pelo projeto e número, e escrever na
Conversa da Demanda no perfil de quem roda a sessão, pelo login do GitHub. O
app só aceita login de Desenvolvedor ativo (o Super admin com login do GitHub
no cadastro) e grava a mensagem com a origem `terminal`.

O aviso segue a regra dos avisos de entrega: no card da Vitta, a diretoria
(Super admins ativos sem login do GitHub); no card do diretor, quem abriu a
Demanda. Sino e e-mail, dublados.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

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
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

CHAVE = "chave-de-automacao-do-teste-1805"
DEMANDA = "5c1e7a2b-3d4f-4a6b-9c8d-1e2f3a4b5c6d"
INEXISTENTE = "0b9a8c7d-6e5f-4a3b-8c2d-1e0f9a8b7c6d"
BASE = "/api/automacao/tecnologia"
ESCREVER = f"{BASE}/demandas/{DEMANDA}/conversa"

# Os Desenvolvedores da Vitta (Super admin com login do GitHub).
PEDRO = _pessoa("P1", "Pedro Rezende", github_login="pedrorezendefig")
LUCAS = _pessoa("P2", "Lucas Sampaio", github_login="lucas-vitta")
# A diretoria do hospital (Super admin sem login do GitHub).
DIRETOR = _pessoa("P3", "Diretor Geral")
DIRETORA = _pessoa("P4", "Diretora Clínica")
# Fora de quem pode escrever ou ser avisado.
DESLIGADO = {**_pessoa("P5", "Diretor Antigo"), "ativo": False}
EX_DESENVOLVEDOR = {**_pessoa("P6", "Ex Vitta", github_login="ex-vitta"), "ativo": False}
GESTOR_COM_LOGIN = _pessoa("P7", "Gestor Curioso", github_login="gestor-curioso", access_profile="gestor")

CADASTRO = [PEDRO, LUCAS, DIRETOR, DIRETORA, DESLIGADO, EX_DESENVOLVEDOR, GESTOR_COM_LOGIN]


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
        enviados.append({"para": destinatario, "assunto": assunto})
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


def _demanda_da_vitta(**campos) -> dict:
    return _demanda_do_diretor(autor_id=PEDRO["id"], responsavel_id=PEDRO["id"], origem="vitta", **campos)


def _cliente(
    demandas: list[dict] | None = None, conversa: list[dict] | None = None
) -> tuple[TestClient, _SupabaseMock]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = _SupabaseMock(
        {
            "participantes": [dict(p) for p in CADASTRO],
            "tecnologia_demandas": [dict(d) for d in (demandas if demandas is not None else [_demanda_do_diretor()])],
            "tecnologia_conversa_da_demanda": [dict(m) for m in (conversa or [])],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app), sb


def _escrever(cliente: TestClient, *, login: str = "pedrorezendefig", texto: str = "E aí, qual das duas?", **kw):
    return cliente.post(
        kw.pop("rota", ESCREVER),
        json={"texto": texto, "github_login": login},
        headers=kw.pop("headers", {"X-API-Key": CHAVE}),
    )


def _avisados(sb) -> list[str]:
    return sorted(n["destinatario_id"] for n in sb.tabelas.get("notificacoes", []))


# ═══════════════════════════════════════════════════════════════════════════
# A mensagem gravada
# ═══════════════════════════════════════════════════════════════════════════


class TestAMensagemGravada:
    def test_a_mensagem_pela_ponte_sai_no_perfil_do_dono_do_login_com_origem_terminal(self):
        cliente, sb = _cliente()

        resposta = _escrever(cliente, login="lucas-vitta", texto="E aí, o senhor prefere a opção A ou a B?")

        assert resposta.status_code == 201, resposta.text
        [linha] = sb.tabelas["tecnologia_conversa_da_demanda"]
        assert linha["demanda_id"] == DEMANDA
        assert linha["autor_id"] == LUCAS["id"]
        assert linha["texto"] == "E aí, o senhor prefere a opção A ou a B?"
        assert linha["origem"] == "terminal"
        assert resposta.json()["id"] == linha["id"]


# ═══════════════════════════════════════════════════════════════════════════
# A chave, nas duas rotas novas
# ═══════════════════════════════════════════════════════════════════════════

ACHAR = f"{BASE}/projetos/hospital/issues/1700/demanda"


def _pedir(cliente: TestClient, rota: str, cabecalhos: dict):
    if rota == ACHAR:
        return cliente.get(rota, headers=cabecalhos)
    return _escrever(cliente, headers=cabecalhos)


class TestAChave:
    @pytest.mark.parametrize("rota", [ACHAR, ESCREVER], ids=["achar", "escrever"])
    @pytest.mark.parametrize(
        "cabecalhos", [{}, {"X-API-Key": ""}, {"X-API-Key": CHAVE + "x"}], ids=["ausente", "vazia", "errada"]
    )
    def test_chave_ausente_ou_errada_recusa_com_401_sem_escrever_nada(self, rota, cabecalhos):
        cliente, sb = _cliente()

        resposta = _pedir(cliente, rota, cabecalhos)

        assert resposta.status_code == 401
        assert resposta.json() == {"detail": "API key inválida ou ausente"}
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []

    @pytest.mark.parametrize("rota", [ACHAR, ESCREVER], ids=["achar", "escrever"])
    def test_sem_chave_configurada_responde_503(self, monkeypatch, rota):
        monkeypatch.setattr(settings, "tecnologia_automacao_api_key", "")
        cliente, sb = _cliente()

        resposta = _pedir(cliente, rota, {"X-API-Key": CHAVE})

        assert resposta.status_code == 503
        assert "TECNOLOGIA_AUTOMACAO_API_KEY" in resposta.json()["detail"]
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []


# ═══════════════════════════════════════════════════════════════════════════
# O login de quem roda a sessão
# ═══════════════════════════════════════════════════════════════════════════


class TestOLogin:
    @pytest.mark.parametrize(
        "login",
        ["ninguem-cadastrado", "ex-vitta", "gestor-curioso"],
        ids=["desconhecido", "inativo", "nao-e-super-admin"],
    )
    def test_login_que_nao_e_de_desenvolvedor_ativo_recusa_com_403_sem_ecoar_o_login(self, login, emails):
        cliente, sb = _cliente()

        resposta = _escrever(cliente, login=login)

        assert resposta.status_code == 403
        assert login not in resposta.text
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []
        assert _avisados(sb) == []
        assert emails == []

    def test_super_admin_sem_login_nao_escreve_por_login_vazio(self):
        """Login só de espaços não casa a diretoria, que não tem login."""
        cliente, sb = _cliente()

        resposta = _escrever(cliente, login="   ")

        assert resposta.status_code == 403
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []

    def test_o_login_vale_sem_diferenciar_maiusculas_nem_arroba(self):
        """O cadastro guarda o login em minúsculas; o GitHub não distingue."""
        cliente, sb = _cliente()

        resposta = _escrever(cliente, login="@PedroRezendeFig")

        assert resposta.status_code == 201, resposta.text
        assert [m["autor_id"] for m in sb.tabelas["tecnologia_conversa_da_demanda"]] == [PEDRO["id"]]


# ═══════════════════════════════════════════════════════════════════════════
# Achar a Demanda da issue-raiz
# ═══════════════════════════════════════════════════════════════════════════


class TestAcharADemanda:
    def test_projeto_e_numero_da_issue_raiz_devolvem_o_id_da_demanda(self):
        cliente, _ = _cliente()

        resposta = cliente.get(ACHAR, headers={"X-API-Key": CHAVE})

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {"id": DEMANDA}

    @pytest.mark.parametrize(
        "rota",
        [
            f"{BASE}/projetos/hospital/issues/1701/demanda",
            f"{BASE}/projetos/ana/issues/1700/demanda",
            f"{BASE}/projetos/outro/issues/1700/demanda",
        ],
        ids=["issue-sem-demanda", "mesmo-numero-em-outro-projeto", "projeto-que-nao-existe"],
    )
    def test_issue_sem_demanda_devolve_404(self, rota):
        cliente, _ = _cliente()

        resposta = cliente.get(rota, headers={"X-API-Key": CHAVE})

        assert resposta.status_code == 404

    def test_demanda_apagada_responde_como_inexistente(self):
        cliente, _ = _cliente([_demanda_do_diretor(apagada_em="2026-11-10T10:00:00Z")])

        assert cliente.get(ACHAR, headers={"X-API-Key": CHAVE}).status_code == 404

    def test_numero_que_nao_e_inteiro_responde_422(self):
        cliente, _ = _cliente()

        resposta = cliente.get(f"{BASE}/projetos/hospital/issues/abc/demanda", headers={"X-API-Key": CHAVE})

        assert resposta.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# Escrever numa Demanda que não existe
# ═══════════════════════════════════════════════════════════════════════════


class TestEscreverSemDemanda:
    @pytest.mark.parametrize(
        ("demandas", "rota", "esperado"),
        [
            (None, f"{BASE}/demandas/{INEXISTENTE}/conversa", 404),
            ([_demanda_do_diretor(apagada_em="2026-11-10T10:00:00Z")], ESCREVER, 404),
            (None, f"{BASE}/demandas/nao-e-uuid/conversa", 422),
        ],
        ids=["inexistente", "apagada", "id-que-nao-e-uuid"],
    )
    def test_demanda_inexistente_ou_id_invalido_responde_404_ou_422_sem_gravar(self, demandas, rota, esperado):
        cliente, sb = _cliente(demandas)

        resposta = _escrever(cliente, rota=rota)

        assert resposta.status_code == esperado, resposta.text
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []
        assert _avisados(sb) == []

    def test_texto_so_de_espacos_responde_422_sem_gravar(self):
        cliente, sb = _cliente()

        resposta = _escrever(cliente, texto="   ")

        assert resposta.status_code == 422
        assert sb.tabelas["tecnologia_conversa_da_demanda"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Quem a mensagem pelo terminal avisa
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemEAvisado:
    def test_no_card_da_vitta_avisa_a_diretoria_ativa_e_mais_ninguem(self, emails):
        """A diretoria são os Super admins ativos sem login do GitHub: o
        desligado, os Desenvolvedores e o gestor ficam de fora. Quem já
        escreveu na conversa (o LUCAS) e o nome citado no texto também não
        entram: o terminal não manda nome de ninguém."""
        conversa = [{"id": "m-1", "demanda_id": DEMANDA, "autor_id": LUCAS["id"], "texto": "Comecei.", "origem": "app"}]
        cliente, sb = _cliente([_demanda_da_vitta()], conversa)

        resposta = _escrever(cliente, texto="E aí, @Lucas Sampaio já viu, falta o senhor escolher.")

        assert resposta.status_code == 201, resposta.text
        assert _avisados(sb) == [DIRETOR["id"], DIRETORA["id"]]
        assert sorted(e["para"] for e in emails) == sorted([DIRETOR["email"], DIRETORA["email"]])
        assert {n["titulo"] for n in sb.tabelas["notificacoes"]} == {"Pedro Rezende escreveu na Demanda"}
        assert {n["referencia_id"] for n in sb.tabelas["notificacoes"]} == {DEMANDA}

    def test_no_card_do_diretor_avisa_quem_abriu_a_demanda_e_mais_ninguem(self, emails):
        """Nem o Responsável (LUCAS), que a regra da tela avisaria se o autor
        escrevesse, nem a outra diretora."""
        cliente, sb = _cliente([_demanda_do_diretor()])

        resposta = _escrever(cliente, texto="E aí, o senhor prefere a opção A ou a B?")

        assert resposta.status_code == 201, resposta.text
        assert _avisados(sb) == [DIRETOR["id"]]
        assert [e["para"] for e in emails] == [DIRETOR["email"]]
        assert emails[0]["assunto"] == "Pedro Rezende escreveu na Demanda: O relatório some"

    def test_quem_escreve_pelo_terminal_nao_e_avisado_da_propria_mensagem(self, emails):
        """O Desenvolvedor que abriu a Demanda do diretor não se avisa."""
        cliente, sb = _cliente([_demanda_do_diretor(autor_id=PEDRO["id"])])

        resposta = _escrever(cliente)

        assert resposta.status_code == 201, resposta.text
        assert _avisados(sb) == []
        assert emails == []


def test_as_rotas_novas_estao_montadas_no_app():
    from app.main import app

    caminhos = app.openapi()["paths"]
    assert "/api/automacao/tecnologia/projetos/{projeto}/issues/{numero}/demanda" in caminhos
    assert "/api/automacao/tecnologia/demandas/{demanda_id}/conversa" in caminhos


# ═══════════════════════════════════════════════════════════════════════════
# A migration 161
# ═══════════════════════════════════════════════════════════════════════════

MIGRATION_161 = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "161_tecnologia_origem_da_mensagem.sql"
)


def _sql_sem_comentario() -> str:
    linhas = MIGRATION_161.read_text(encoding="utf-8").splitlines()
    return "\n".join(linha for linha in linhas if not linha.lstrip().startswith("--")).strip()


class TestMigration:
    def test_a_origem_entra_com_app_como_padrao_e_so_os_dois_valores(self):
        sql = _sql_sem_comentario()

        assert (
            "ALTER TABLE tecnologia_conversa_da_demanda ADD COLUMN IF NOT EXISTS origem TEXT NOT NULL DEFAULT 'app';"
            in sql
        )
        assert "CHECK (origem IN ('app', 'terminal'))" in sql

    def test_termina_com_o_recibo_do_proprio_numero(self):
        assert _sql_sem_comentario().endswith(
            "INSERT INTO migracoes_aplicadas (numero) VALUES (161) ON CONFLICT (numero) DO NOTHING;"
        )


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


class TestOKit:
    def test_o_kit_da_tecnologia_diz_que_a_vitta_pergunta_pela_conversa_e_quem_e_avisado(self):
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")

        for trecho in (
            "Quando a Vitta precisa de uma decisão sua num pedido",
            "no card que a Vitta abriu, avisa a diretoria",
            "no seu pedido, avisa você",
        ):
            assert trecho in texto, trecho
        # A frase de antes dizia que toda decisão da Vitta ia pelo WhatsApp.
        assert "Quando a Vitta precisa de uma decisão, de um dado ou de um acesso" not in texto
