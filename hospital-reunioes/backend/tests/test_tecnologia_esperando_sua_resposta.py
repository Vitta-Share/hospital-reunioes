"""A lista Esperando sua resposta na aba Tecnologia (issue #2118, PRD #2112,
ADR 0109, decisão 5).

No topo da aba, as Perguntas da Vitta abertas de todos os Projetos, cada uma
com o cartão, o nome da Demanda e o do Projeto. As do usuário logado vêm
primeiro; em cada grupo, a mais antiga primeiro. Todo Super admin vê a lista
inteira; quem não é Super admin não recebe nada. O aviso da Pergunta (sino e
e-mail) passa a levar à aba com o cartão em foco.

As Perguntas nascem pela ponte de verdade, com o Supabase em memória de
`test_tecnologia_vinculo`, e a lista é lida pela ROTA da tela.
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

CHAVE = "chave-de-automacao-do-teste-2118"
LISTA = "/api/admin/tecnologia/perguntas/esperando"

ATA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
AGENDA = "8b2c3d4e-5f6a-4b7c-9d8e-0f1a2b3c4d5e"

PEDRO = _pessoa("P001", "Pedro Rezende", github_login="pedrorezendefig")
DIRETOR = _pessoa("P003", "Diretor Geral")
DIRETORA = _pessoa("P004", "Diretora Clínica")
GESTORA = _pessoa("P012", "Gestora da Recepção", access_profile="gestor")

TABELA = "tecnologia_perguntas"

QUATRO_LINHAS = {
    "por_que_precisa": "Só a diretoria decide quem assina a ata em nome do hospital.",
    "o_que_esta_parado": "A tela de assinatura da Ata espera essa regra para sair.",
    "o_que_anda_depois": "A Vitta termina a tela e ela entra na próxima subida.",
    "ganho": "A ata sai assinada no mesmo dia da reunião.",
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


def _banco() -> _SupabaseMock:
    """Duas Demandas de Projetos diferentes: a do app do Hospital e a do
    PedroOS, um Projeto novo que a ponte gravou com o nome."""
    return _SupabaseMock(
        {
            "participantes": [dict(p) for p in (PEDRO, DIRETOR, DIRETORA, GESTORA)],
            "tecnologia_produtos": [{"id": "prod-1", "nome": "Reuniões", "ativo": True, "ordem": 1, "dono_id": "P001"}],
            "tecnologia_demandas": [
                _demanda(ATA, titulo="A Ata assinada no app", autor_id=PEDRO["id"], origem="vitta", apagada_em=None),
                _demanda(
                    AGENDA,
                    titulo="A agenda do diretor no celular",
                    autor_id=PEDRO["id"],
                    origem="vitta",
                    projeto="pedro-os",
                    projeto_nome="PedroOS",
                    apagada_em=None,
                ),
            ],
            "tecnologia_conversa_da_demanda": [],
            TABELA: [],
        }
    )


def _ponte(sb: _SupabaseMock) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(tecnologia_automacao.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: sb
    return TestClient(app)


def _perguntar(
    sb: _SupabaseMock, demanda: str, *, para: dict, assunto: str, em: str, estado: str = "aberta", **opcoes
) -> str:
    """Cria a Pergunta pela ponte e a põe na data `em` (e no `estado`, que as
    próximas Fatias mudam pelas rotas delas). `opcoes` leva as opções e a
    recomendada, quando a Pergunta tem."""
    resposta = _ponte(sb).post(
        f"/api/automacao/tecnologia/demandas/{demanda}/perguntas",
        json={
            "github_login": "pedrorezendefig",
            "destinatario_id": para["id"],
            "assunto": assunto,
            "texto": f"Pergunta sobre {assunto}?",
            **QUATRO_LINHAS,
            **opcoes,
        },
        headers={"X-API-Key": CHAVE},
    )
    assert resposta.status_code == 201, resposta.text
    pergunta_id = resposta.json()["id"]
    [linha] = [p for p in sb.tabelas[TABELA] if p["id"] == pergunta_id]
    linha.update({"criado_em": em, "estado": estado})
    return pergunta_id


def _lista(sb: _SupabaseMock, logado: dict, monkeypatch):
    cliente, _, _ = _montar(logado=logado, supabase=sb, monkeypatch=monkeypatch)
    return cliente.get(LISTA)


class TestALista:
    def test_a_lista_traz_so_as_abertas_de_todos_os_projetos_com_a_demanda_o_projeto_e_a_data(self, monkeypatch):
        sb = _banco()
        da_ata = _perguntar(sb, ATA, para=DIRETORA, assunto="quem assina a Ata", em="2026-11-18T10:00:00Z")
        da_agenda = _perguntar(sb, AGENDA, para=DIRETORA, assunto="o horário da agenda", em="2026-11-19T10:00:00Z")
        for estado in ("respondida", "resolvida", "cancelada"):
            _perguntar(sb, ATA, para=DIRETORA, assunto=f"a {estado}", em="2026-11-17T10:00:00Z", estado=estado)

        resposta = _lista(sb, DIRETORA, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        itens = resposta.json()
        assert [i["id"] for i in itens] == [da_ata, da_agenda]
        ata, agenda = itens
        assert (ata["demanda_id"], ata["demanda"], ata["projeto"]) == (
            ATA,
            "A Ata assinada no app",
            "Aplicativo do Hospital",
        )
        assert (agenda["demanda_id"], agenda["demanda"], agenda["projeto"]) == (
            AGENDA,
            "A agenda do diretor no celular",
            "PedroOS",
        )
        assert ata["criado_em"] == "2026-11-18T10:00:00Z"
        assert ata["estado"] == "aberta"
        assert ata["assunto"] == "quem assina a Ata"
        assert {chave: ata[chave] for chave in QUATRO_LINHAS} == QUATRO_LINHAS
        assert ata["destinatario"] == "Diretora Clínica"

    def test_as_do_usuario_logado_vem_primeiro_e_em_cada_grupo_a_mais_antiga_primeiro(self, monkeypatch):
        sb = _banco()
        dele_nova = _perguntar(sb, ATA, para=DIRETOR, assunto="dele nova", em="2026-11-20T10:00:00Z")
        minha_nova = _perguntar(sb, AGENDA, para=DIRETORA, assunto="minha nova", em="2026-11-19T10:00:00Z")
        dele_antiga = _perguntar(sb, AGENDA, para=DIRETOR, assunto="dele antiga", em="2026-11-10T10:00:00Z")
        minha_antiga = _perguntar(sb, ATA, para=DIRETORA, assunto="minha antiga", em="2026-11-15T10:00:00Z")

        itens = _lista(sb, DIRETORA, monkeypatch).json()

        assert [i["id"] for i in itens] == [minha_antiga, minha_nova, dele_antiga, dele_nova]
        assert [i["minha"] for i in itens] == [True, True, False, False]

    def test_sem_pergunta_aberta_a_lista_vem_vazia(self, monkeypatch):
        sb = _banco()
        _perguntar(sb, ATA, para=DIRETORA, assunto="já respondida", em="2026-11-18T10:00:00Z", estado="respondida")

        resposta = _lista(sb, DIRETORA, monkeypatch)

        assert resposta.status_code == 200
        assert resposta.json() == []

    def test_quem_nao_e_super_admin_nao_recebe_os_dados_da_lista(self, monkeypatch):
        sb = _banco()
        _perguntar(sb, ATA, para=GESTORA, assunto="quem assina a Ata", em="2026-11-18T10:00:00Z")

        resposta = _lista(sb, GESTORA, monkeypatch)

        assert resposta.status_code == 403
        assert "quem assina a Ata" not in resposta.text


# ═══════════════════════════════════════════════════════════════════════════
# Responder pelo cartão da lista (issue #2145)
# ═══════════════════════════════════════════════════════════════════════════

OPCOES = {"opcoes": ["A diretora de plantão", "O diretor geral"], "recomendada": "B", "porque": "Ele já assina hoje."}


def _responder_pela_lista(sb: _SupabaseMock, logado: dict, monkeypatch, **corpo):
    """Lê a lista como `logado` e responde a primeira Pergunta dela pela rota
    da resposta, como o cartão da lista faz."""
    cliente, _, _ = _montar(logado=logado, supabase=sb, monkeypatch=monkeypatch)
    [item] = cliente.get(LISTA).json()
    return item, cliente.post(f"/api/admin/tecnologia/perguntas/{item['id']}/resposta", json=corpo)


class TestResponderPelaLista:
    @pytest.mark.parametrize(
        ("logado", "pode"),
        [(DIRETORA, True), (PEDRO, True), (DIRETOR, False)],
        ids=["destinatario", "desenvolvedor", "outro-super-admin"],
    )
    def test_o_cartao_da_lista_diz_se_quem_esta_logado_pode_responder(self, logado, pode, monkeypatch):
        sb = _banco()
        _perguntar(sb, ATA, para=DIRETORA, assunto="quem assina a Ata", em="2026-11-18T10:00:00Z")

        [item] = _lista(sb, logado, monkeypatch).json()

        assert item["pode_responder"] is pode

    def test_o_destinatario_responde_por_opcao_pela_lista_e_a_pergunta_sai_dela(self, monkeypatch):
        sb = _banco()
        _perguntar(sb, ATA, para=DIRETORA, assunto="quem assina a Ata", em="2026-11-18T10:00:00Z", **OPCOES)

        item, resposta = _responder_pela_lista(sb, DIRETORA, monkeypatch, opcao="B")

        assert item["pode_responder"] is True
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["pergunta"]["estado"] == "respondida"
        [pergunta] = sb.tabelas[TABELA]
        assert (pergunta["estado"], pergunta["resposta_opcao"]) == ("respondida", "B")
        assert _lista(sb, DIRETORA, monkeypatch).json() == []

    def test_o_destinatario_responde_por_texto_livre_pela_lista(self, monkeypatch):
        sb = _banco()
        _perguntar(sb, ATA, para=DIRETORA, assunto="quem assina a Ata", em="2026-11-18T10:00:00Z")

        _, resposta = _responder_pela_lista(sb, DIRETORA, monkeypatch, texto="Quem estiver de plantão.")

        assert resposta.status_code == 200, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert (pergunta["estado"], pergunta["resposta_texto"]) == ("respondida", "Quem estiver de plantão.")

    def test_o_desenvolvedor_registra_pela_lista_no_lugar_do_destinatario_com_os_dois_nomes(self, monkeypatch):
        sb = _banco()
        _perguntar(sb, ATA, para=DIRETORA, assunto="quem assina a Ata", em="2026-11-18T10:00:00Z", **OPCOES)

        _, resposta = _responder_pela_lista(sb, PEDRO, monkeypatch, opcao="A")

        assert resposta.status_code == 200, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert (pergunta["respondida_por"], pergunta["respondida_em_nome_de"]) == (PEDRO["id"], DIRETORA["id"])
        gravada = resposta.json()["pergunta"]["resposta"]
        assert (gravada["respondida_por"], gravada["em_nome_de"]) == ("Pedro Rezende", "Diretora Clínica")


class TestOAviso:
    def test_o_sino_da_pergunta_leva_ao_cartao_na_aba(self):
        sb = _banco()
        pergunta_id = _perguntar(sb, ATA, para=DIRETORA, assunto="quem assina a Ata", em="2026-11-18T10:00:00Z")

        [aviso] = sb.tabelas["notificacoes"]

        assert (aviso["tipo"], aviso["referencia_id"]) == ("TECNOLOGIA", f"pergunta:{pergunta_id}")

    def test_o_email_da_pergunta_traz_o_link_da_aba_com_o_cartao(self, emails):
        sb = _banco()
        pergunta_id = _perguntar(sb, ATA, para=DIRETORA, assunto="quem assina a Ata", em="2026-11-18T10:00:00Z")

        [email] = emails

        link = f"https://app.hsm.test/admin/tecnologia?pergunta={pergunta_id}"
        assert link in email["texto"]
        assert f'href="{link}"' in email["html"]


class TestOKit:
    def test_o_kit_da_tecnologia_diz_a_lista_esperando_sua_resposta(self):
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")

        for trecho in (
            'a lista "Esperando você"',
            "as perguntas abertas de todos os projetos",
            "As suas vêm primeiro",
            "a mais antiga primeiro",
            "abrem a aba Tecnologia já no cartão da pergunta",
            "responde ali mesmo, no cartão da lista",
            "sai da lista na hora",
        ):
            assert trecho in texto, trecho
        assert "Pendência da Vitta" not in texto
