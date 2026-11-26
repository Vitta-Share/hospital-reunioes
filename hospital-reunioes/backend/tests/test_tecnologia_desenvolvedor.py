"""O Desenvolvedor vê as Demandas de todos, com a entrevista inteira (issue #1531, PRD #1529, ADR 0083).

Desenvolvedor é o Super admin com login do GitHub no cadastro (ADR 0083,
decisão 2): não é perfil novo. A regra de quem vê uma Demanda é uma só, usada
pela lista e pela leitura da conversa. Desde a issue #2265 (ADR 0113, decisão
6) todo Super admin vê todas, com o número e o link da issue: o diretor (Super
admin sem login do GitHub) lê o mesmo que o Desenvolvedor.

Tudo pela ROTA, no molde de `test_tecnologia_chat`: o modelo e o GitHub ficam
dublados.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_chat import CHAT, _cenario  # noqa: E402
from test_tecnologia_vinculo import BASE, DIRETOR, PEDRO, _demanda, _pessoa  # noqa: E402

from app.config import settings  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.services import ai_processor  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

# Outra pessoa da diretoria: Super admin, sem login do GitHub.
OUTRO_DIRETOR = _pessoa("P3", "Outro Diretor")

TODAS = f"{CHAT}?filtro=todas"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _llm_em_mock(monkeypatch):
    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "mock")
    yield


@pytest.fixture(autouse=True)
def _integracao_configurada(monkeypatch):
    monkeypatch.setattr(settings, "github_integracao_token", "token-de-teste")
    monkeypatch.setattr(settings, "github_integracao_repo", "pedrorezendefig/hospital-reunioes")


def _demandas_de_dois_autores() -> list[dict]:
    return [
        _demanda(
            "d-diretor", titulo="O relatório some", autor_id=DIRETOR["id"], criado_em="2026-11-01T10:00:00Z", numero=41
        ),
        _demanda(
            "d-pedro", titulo="Pedido da Vitta", autor_id=PEDRO["id"], criado_em="2026-11-02T10:00:00Z", numero=42
        ),
        _demanda(
            "d-outro",
            numero=7,
            titulo="O botão sumiu",
            autor_id=OUTRO_DIRETOR["id"],
            criado_em="2026-10-15T10:00:00Z",
            github_issue_numero=912,
            github_foto={"numero": 912, "url": "https://github.com/pedrorezendefig/hospital-reunioes/issues/912"},
            etapa="em_desenvolvimento",
        ),
    ]


def _participantes() -> list[dict]:
    return [PEDRO, DIRETOR, OUTRO_DIRETOR]


# ═══════════════════════════════════════════════════════════════════════════
# 1. A lista
# ═══════════════════════════════════════════════════════════════════════════


class TestListaDoDesenvolvedor:
    def test_o_desenvolvedor_lista_as_demandas_de_todos_com_o_autor_em_cada_linha(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch, logado=PEDRO, participantes=_participantes(), demandas=_demandas_de_dois_autores()
        )

        resposta = client.get(TODAS)

        assert resposta.status_code == 200, resposta.text
        assert [(d["titulo"], d["autor"]) for d in resposta.json()] == [
            ("Pedido da Vitta", "Pedro Vitta"),
            ("O relatório some", "Diretor do Hospital"),
            ("O botão sumiu", "Outro Diretor"),
        ]

    def test_sem_o_filtro_a_lista_do_desenvolvedor_traz_so_as_dele(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch, logado=PEDRO, participantes=_participantes(), demandas=_demandas_de_dois_autores()
        )

        assert [d["titulo"] for d in client.get(CHAT).json()] == ["Pedido da Vitta"]

    def test_so_a_demanda_do_proprio_desenvolvedor_sai_como_minha_na_lista_de_todas(self, monkeypatch):
        """`minha` é o que faz a tela abrir a Demanda de outro autor no
        Acompanhamento, com os Anexos e sem a caixa de responder."""
        client, _, _ = _cenario(
            monkeypatch, logado=PEDRO, participantes=_participantes(), demandas=_demandas_de_dois_autores()
        )

        por_id = {d["id"]: d["minha"] for d in client.get(TODAS).json()}

        assert por_id == {"d-pedro": True, "d-diretor": False, "d-outro": False}

    def test_super_admin_sem_login_do_github_lista_as_de_todos_no_todas(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch, logado=DIRETOR, participantes=_participantes(), demandas=_demandas_de_dois_autores()
        )

        resposta = client.get(TODAS)

        assert resposta.status_code == 200, resposta.text
        assert [d["titulo"] for d in resposta.json()] == ["Pedido da Vitta", "O relatório some", "O botão sumiu"]

    def test_o_desenvolvedor_ve_o_numero_e_o_link_da_issue_na_demanda_com_card(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch, logado=PEDRO, participantes=_participantes(), demandas=_demandas_de_dois_autores()
        )

        por_id = {d["id"]: d for d in client.get(TODAS).json()}

        assert por_id["d-outro"]["issue_numero"] == 912
        assert por_id["d-outro"]["issue_url"] == "https://github.com/pedrorezendefig/hospital-reunioes/issues/912"
        assert por_id["d-diretor"]["issue_numero"] is None
        assert por_id["d-diretor"]["issue_url"] is None

    def test_a_lista_entregue_ao_diretor_traz_o_numero_e_o_link_da_issue(self, monkeypatch):
        """Issue #2265 (ADR 0113, decisão 6): o login do GitHub não corta mais
        a leitura."""
        client, _, _ = _cenario(
            monkeypatch, logado=OUTRO_DIRETOR, participantes=_participantes(), demandas=_demandas_de_dois_autores()
        )

        item = next(d for d in client.get(TODAS).json() if d["id"] == "d-outro")

        assert item["tem_vinculo"] is True
        assert item["raiz_numero"] == 912
        assert item["issue_numero"] == 912
        assert item["issue_url"] == "https://github.com/pedrorezendefig/hospital-reunioes/issues/912"

    def test_o_diretor_ve_o_numero_da_demanda_e_o_da_issue_lado_a_lado(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch, logado=OUTRO_DIRETOR, participantes=_participantes(), demandas=_demandas_de_dois_autores()
        )

        item = next(d for d in client.get(TODAS).json() if d["id"] == "d-outro")

        assert (item["numero"], item["issue_numero"]) == (7, 912)

    def test_o_desenvolvedor_ve_o_numero_da_demanda_e_o_da_issue_lado_a_lado(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch, logado=PEDRO, participantes=_participantes(), demandas=_demandas_de_dois_autores()
        )

        por_id = {d["id"]: (d["numero"], d["issue_numero"]) for d in client.get(TODAS).json()}

        assert por_id == {"d-pedro": (42, None), "d-diretor": (41, None), "d-outro": (7, 912)}


# ═══════════════════════════════════════════════════════════════════════════
# 2. Quem sou na aba
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemSou:
    """A tela pergunta ao servidor se quem está logado é Desenvolvedor, e só
    então mostra o filtro "Todas": a regra fica num lugar só, no backend."""

    def test_o_super_admin_com_login_do_github_e_desenvolvedor(self, monkeypatch):
        client, _, _ = _cenario(monkeypatch, logado=PEDRO)

        assert client.get(f"{BASE}/eu").json() == {"desenvolvedor": True}

    def test_o_super_admin_sem_login_do_github_nao_e(self, monkeypatch):
        client, _, _ = _cenario(monkeypatch, logado=DIRETOR)

        assert client.get(f"{BASE}/eu").json() == {"desenvolvedor": False}


# ═══════════════════════════════════════════════════════════════════════════
# 3. O Kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


class TestKit:
    def test_o_kit_diz_que_o_desenvolvedor_ve_as_demandas_de_todos(self):
        """O Assistente fala com o diretor pela língua do Kit: sem a regra
        escrita, ele diria que ninguém da Vitta lê a conversa."""
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")

        secao = texto.split("## Quem vê", 1)[1].split("\n## ", 1)[0]
        for trecho in ("Desenvolvedor", "login do GitHub", "todas as Demandas", "Todas"):
            assert trecho in secao, trecho
