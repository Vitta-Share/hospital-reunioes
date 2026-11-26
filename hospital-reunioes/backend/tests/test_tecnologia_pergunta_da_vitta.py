"""A Pergunta da Vitta nasce pela ponte e aparece como cartão na Conversa da
Demanda (issue #2116, PRD #2112, ADR 0109, decisões 1 e 3).

A Pergunta vira registro do app: ligada a uma Demanda, com Destinatário,
Assunto, o texto, as quatro linhas do cartão (por que precisa da pessoa, o que
está parado, o que anda depois e o ganho), as opções com a recomendada e o
porquê, e o estado. Nasce aberta. A ponte ganha duas rotas, com a mesma chave
e o mesmo teto: criar e ler. A mensagem pela rota de antes, com ou sem "pede
resposta", segue igual e não cria Pergunta.

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

from test_tecnologia_vinculo import _demanda, _montar, _pessoa, _SupabaseMock  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import tecnologia_automacao  # noqa: E402
from app.services import tecnologia_email  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

CHAVE = "chave-de-automacao-do-teste-2116"
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
CRIAR = f"/api/automacao/tecnologia/demandas/{DEMANDA}/perguntas"
MENSAGEM_DE_ANTES = f"/api/automacao/tecnologia/demandas/{DEMANDA}/conversa"

PEDRO = _pessoa("P001", "Pedro Rezende", github_login="pedrorezendefig")
DIRETOR = _pessoa("P003", "Diretor Geral")
DIRETORA = _pessoa("P004", "Diretora Clínica")
GESTORA = _pessoa("P012", "Gestora da Recepção", access_profile="gestor")
DESLIGADO = {**_pessoa("P006", "Diretor Antigo"), "ativo": False}
NINGUEM = "P999"

CADASTRO = [PEDRO, DIRETOR, DIRETORA, GESTORA, DESLIGADO]

TABELA = "tecnologia_perguntas"
CONVERSA = "tecnologia_conversa_da_demanda"

QUATRO_LINHAS = {
    "por_que_precisa": "Só a diretoria decide quem assina a ata em nome do hospital.",
    "o_que_esta_parado": "A tela de assinatura da Ata espera essa regra para sair.",
    "o_que_anda_depois": "A Vitta termina a tela e ela entra na próxima subida.",
    "ganho": "A ata sai assinada no mesmo dia da reunião.",
}
PERGUNTA = {
    "github_login": "pedrorezendefig",
    "destinatario_id": DIRETORA["id"],
    "assunto": "quem assina a Ata pela diretoria",
    "texto": "Quem assina a Ata em nome da diretoria quando a senhora não está?",
    **QUATRO_LINHAS,
    "opcoes": ["O diretor geral", "Quem presidiu a reunião"],
    "recomendada": "B",
    "porque": "Quem presidiu esteve na reunião e conhece o que foi decidido.",
}


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


def _a_demanda() -> dict:
    """Um card que a Vitta abriu (Origem Vitta): toda a diretoria o vê."""
    return _demanda(
        DEMANDA,
        titulo="A Ata assinada no app",
        autor_id=PEDRO["id"],
        responsavel_id=PEDRO["id"],
        github_issue_numero=1700,
        origem="vitta",
        apagada_em=None,
    )


def _ponte(sb: _SupabaseMock | None = None) -> tuple[TestClient, _SupabaseMock]:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    sb = sb or _SupabaseMock(
        {
            "participantes": [dict(p) for p in CADASTRO],
            "tecnologia_produtos": [{"id": "prod-1", "nome": "Reuniões", "ativo": True, "ordem": 1, "dono_id": "P001"}],
            "tecnologia_demandas": [_a_demanda()],
            CONVERSA: [],
            TABELA: [],
        }
    )
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app), sb


def _criar(cliente: TestClient, **campos):
    return cliente.post(CRIAR, json={**PERGUNTA, **campos}, headers={"X-API-Key": CHAVE})


def _avisados(sb) -> list[str]:
    return sorted(n["destinatario_id"] for n in sb.tabelas.get("notificacoes", []))


# ═══════════════════════════════════════════════════════════════════════════
# Criar pela ponte
# ═══════════════════════════════════════════════════════════════════════════


class TestCriar:
    def test_criar_grava_a_pergunta_aberta_com_as_quatro_linhas_e_as_opcoes_e_devolve_o_id(self):
        cliente, sb = _ponte()

        resposta = _criar(cliente)

        assert resposta.status_code == 201, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert resposta.json()["id"] == pergunta["id"]
        assert resposta.json()["estado"] == "aberta"
        assert pergunta["estado"] == "aberta"
        assert pergunta["demanda_id"] == DEMANDA
        assert pergunta["destinatario_id"] == DIRETORA["id"]
        assert pergunta["autor_id"] == PEDRO["id"]
        assert pergunta["assunto"] == "quem assina a Ata pela diretoria"
        assert pergunta["texto"] == "Quem assina a Ata em nome da diretoria quando a senhora não está?"
        assert {chave: pergunta[chave] for chave in QUATRO_LINHAS} == QUATRO_LINHAS
        assert pergunta["opcoes"] == [
            {"letra": "A", "texto": "O diretor geral"},
            {"letra": "B", "texto": "Quem presidiu a reunião"},
        ]
        assert pergunta["recomendada"] == "B"
        assert pergunta["porque_da_recomendada"] == "Quem presidiu esteve na reunião e conhece o que foi decidido."

    def test_criar_sem_opcoes_tambem_vale(self):
        cliente, sb = _ponte()

        resposta = _criar(cliente, opcoes=[], recomendada=None, porque=None)

        assert resposta.status_code == 201, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert (pergunta["opcoes"], pergunta["recomendada"]) == ([], None)


# ═══════════════════════════════════════════════════════════════════════════
# A recusa, com motivo e sem gravar nada
# ═══════════════════════════════════════════════════════════════════════════

MOTIVO_DESTINATARIO = "O Destinatário não é um participante ativo do aplicativo."


class TestRecusa:
    @pytest.mark.parametrize(
        ("campos", "motivo"),
        [
            ({"destinatario_id": DESLIGADO["id"]}, MOTIVO_DESTINATARIO),
            ({"destinatario_id": NINGUEM}, MOTIVO_DESTINATARIO),
            ({"destinatario_id": None}, MOTIVO_DESTINATARIO),
            ({"assunto": "   "}, "Falta o Assunto da Pergunta."),
            ({"texto": ""}, "Falta o texto da Pergunta."),
            ({"por_que_precisa": " "}, "Falta a linha do cartão: por que precisa da pessoa."),
            ({"o_que_esta_parado": None}, "Falta a linha do cartão: o que está parado."),
            ({"o_que_anda_depois": ""}, "Falta a linha do cartão: o que anda depois."),
            ({"ganho": None}, "Falta a linha do cartão: o ganho."),
            (
                {"opcoes": ["Só uma"], "recomendada": "A"},
                "A Pergunta com opções precisa de duas a quatro, todas com texto.",
            ),
            ({"recomendada": "C"}, "A recomendada precisa ser a letra de uma das opções."),
        ],
        ids=[
            "destinatario-inativo",
            "destinatario-inexistente",
            "sem-destinatario",
            "sem-assunto",
            "sem-texto",
            "sem-por-que-precisa",
            "sem-o-que-esta-parado",
            "sem-o-que-anda-depois",
            "sem-ganho",
            "uma-opcao-so",
            "recomendada-fora-das-opcoes",
        ],
    )
    def test_criar_incompleta_e_recusado_com_motivo_e_nada_e_gravado(self, campos, motivo, emails):
        cliente, sb = _ponte()

        resposta = _criar(cliente, **campos)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": motivo}
        assert sb.tabelas[TABELA] == []
        assert sb.tabelas[CONVERSA] == []
        assert _avisados(sb) == []
        assert emails == []

    def test_login_que_nao_e_de_desenvolvedor_e_recusado_sem_gravar(self, emails):
        cliente, sb = _ponte()

        resposta = _criar(cliente, github_login="quem-nao-e")

        assert resposta.status_code == 403
        assert sb.tabelas[TABELA] == []
        assert emails == []

    def test_sem_a_chave_da_ponte_nada_entra(self):
        cliente, sb = _ponte()

        resposta = cliente.post(CRIAR, json=PERGUNTA, headers={"X-API-Key": "chave-errada"})

        assert resposta.status_code == 401
        assert sb.tabelas[TABELA] == []


# ═══════════════════════════════════════════════════════════════════════════
# O aviso
# ═══════════════════════════════════════════════════════════════════════════


class TestAviso:
    def test_criar_avisa_so_o_destinatario_por_sino_e_email_com_pede_sua_resposta_e_o_assunto(self, emails):
        """Card da Vitta: a regra das entregas avisaria a diretoria inteira.
        A Pergunta avisa só a Diretora."""
        cliente, sb = _ponte()

        resposta = _criar(cliente)

        assert resposta.status_code == 201, resposta.text
        [aviso] = sb.tabelas["notificacoes"]
        assert (aviso["destinatario_id"], aviso["titulo"], aviso["mensagem"]) == (
            DIRETORA["id"],
            "Pede sua resposta",
            "quem assina a Ata pela diretoria",
        )
        [email] = emails
        assert email["para"] == DIRETORA["email"]
        assert email["assunto"] == "Pedro Rezende pede sua resposta: quem assina a Ata pela diretoria"


# ═══════════════════════════════════════════════════════════════════════════
# Ler pela ponte
# ═══════════════════════════════════════════════════════════════════════════


def _ler(cliente: TestClient, pergunta_id: str):
    return cliente.get(f"/api/automacao/tecnologia/perguntas/{pergunta_id}", headers={"X-API-Key": CHAVE})


class TestLer:
    def test_ler_a_pergunta_aberta_devolve_o_estado_e_nenhuma_resposta(self):
        cliente, _ = _ponte()
        pergunta_id = _criar(cliente).json()["id"]

        resposta = _ler(cliente, pergunta_id)

        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert (corpo["id"], corpo["demanda_id"], corpo["estado"]) == (pergunta_id, DEMANDA, "aberta")
        assert corpo["assunto"] == "quem assina a Ata pela diretoria"
        assert corpo["resposta"] is None

    def test_ler_a_pergunta_respondida_devolve_a_opcao_o_texto_e_quem_respondeu(self):
        """Responder vem na próxima Fatia: a resposta é gravada aqui direto na
        linha, com as colunas da migration, e a leitura a devolve."""
        cliente, sb = _ponte()
        pergunta_id = _criar(cliente).json()["id"]
        [linha] = sb.tabelas[TABELA]
        linha.update(
            {
                "estado": "respondida",
                "resposta_opcao": "B",
                "resposta_texto": "E se ninguém presidiu, o diretor geral.",
                "respondida_por": PEDRO["id"],
                "respondida_em_nome_de": DIRETORA["id"],
                "respondida_em": "2026-11-22T09:30:00Z",
            }
        )

        corpo = _ler(cliente, pergunta_id).json()

        assert corpo["estado"] == "respondida"
        assert corpo["resposta"] == {
            "opcao": "B",
            "opcao_texto": "Quem presidiu a reunião",
            "texto": "E se ninguém presidiu, o diretor geral.",
            "respondida_em": "2026-11-22T09:30:00Z",
            "respondida_por": "Pedro Rezende",
            "em_nome_de": "Diretora Clínica",
        }

    def test_pergunta_que_nao_existe_e_404(self):
        cliente, _ = _ponte()

        resposta = _ler(cliente, "0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e")

        assert resposta.status_code == 404

    def test_ler_sem_a_chave_e_401(self):
        cliente, _ = _ponte()
        pergunta_id = _criar(cliente).json()["id"]

        resposta = cliente.get(f"/api/automacao/tecnologia/perguntas/{pergunta_id}")

        assert resposta.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# A Conversa da Demanda, na tela
# ═══════════════════════════════════════════════════════════════════════════

CONVERSA_DA_TELA = f"/api/admin/tecnologia/chat/{DEMANDA}/conversa"


def _tela(sb: _SupabaseMock, logado: dict, monkeypatch) -> TestClient:
    cliente, _, _ = _montar(logado=logado, supabase=sb, monkeypatch=monkeypatch)
    return cliente


# ═══════════════════════════════════════════════════════════════════════════
# A rota de antes segue igual
# ═══════════════════════════════════════════════════════════════════════════


class TestARotaDeAntes:
    @pytest.mark.parametrize(
        "campos",
        [{}, {"destinatario_id": DIRETORA["id"], "assunto": "quem assina a Ata", "pede_resposta": True}],
        ids=["recado", "pede-resposta"],
    )
    def test_a_mensagem_pela_rota_de_antes_segue_igual_e_nao_cria_pergunta(self, campos):
        cliente, sb = _ponte()

        resposta = cliente.post(
            MENSAGEM_DE_ANTES,
            json={"texto": "Quem assina a Ata?", "github_login": "pedrorezendefig", **campos},
            headers={"X-API-Key": CHAVE},
        )

        assert resposta.status_code == 201, resposta.text
        assert set(resposta.json()) == {"id", "criado_em"}
        assert sb.tabelas[TABELA] == []
        [mensagem] = sb.tabelas[CONVERSA]
        assert (mensagem["texto"], mensagem["origem"]) == ("Quem assina a Ata?", "terminal")


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


class TestOKit:
    def test_o_kit_da_tecnologia_diz_que_a_pergunta_da_vitta_chega_como_cartao(self):
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")

        for trecho in (
            "a pergunta aparece na Conversa como um cartão em destaque",
            "por que a resposta é sua, o que está parado, o que anda quando você responder e o que o hospital ganha",
            "há quantos dias ela espera",
            'a linha "Pergunta aberta"',
        ):
            assert trecho in texto, trecho
        assert "sem marca diferente" not in texto
        assert "Pendência da Vitta" not in texto
