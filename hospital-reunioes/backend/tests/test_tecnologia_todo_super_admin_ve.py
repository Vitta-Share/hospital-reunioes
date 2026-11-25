"""Todo Super admin vê a mesma aba Tecnologia (issue #2265, PRD #2262, ADR 0113, decisão 6).

A leitura das Demandas deixa de conferir autor contra Desenvolvedor (emenda à
ADR 0083, decisão 3): todo Super admin lista todas as Demandas e vê o número
da raiz e de cada parte. A regra de quem vê é uma só (`pode_ver`), e o login
do GitHub no cadastro serve só para dar nome ao Responsável.

Tudo pela ROTA, no molde de `test_tecnologia_desenvolvedor`.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_chat import (  # noqa: E402
    CHAT,
    _ate_o_resumo,
    _cenario,
    _demandas,
    _integracao_configurada,  # noqa: F401
    _llm_em_mock,  # noqa: F401
)
from test_tecnologia_vinculo import BASE, DIRETOR, PEDRO, _demanda, _pessoa  # noqa: E402
from test_tecnologia_vinculo import _montar as _montar_da_aba  # noqa: E402
from test_tecnologia_webhook_github import (  # noqa: E402
    SEGREDO,
    _corpo,
    _entregar,
    _GithubFalso,
    _issue,
    _montar,
    _sem_github_de_verdade,  # noqa: F401
)
from test_tecnologia_webhook_github import _demandas as _demandas_do_webhook  # noqa: E402

from app.config import settings  # noqa: E402
from app.limiter import limiter  # noqa: E402

# Outra pessoa da diretoria: Super admin, sem login do GitHub.
OUTRO_DIRETOR = _pessoa("P3", "Outro Diretor")
# O diretor que virou colaborador do repositorio (ADR 0113, decisao 2): o login
# no cadastro so serve para o card atribuido a ele mostrar o nome dele.
DIRETOR_COLABORADOR = _pessoa("P7", "Diretor Colaborador", github_login="diretor-hsm")
# Tem acesso ao app, mas nao e Super admin.
GESTOR = _pessoa("P9", "Gestora do Setor", access_profile="facilitador")

TODAS = f"{CHAT}?filtro=todas"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _webhook_configurado(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", SEGREDO)
    monkeypatch.setattr(settings, "github_integracao_repo", "pedrorezendefig/hospital-reunioes")
    monkeypatch.setattr(settings, "github_login_dono", "pedrorezendefig")


def _card_de_outro_autor() -> dict:
    """O card que o diretor pediu, já fatiado em duas partes no GitHub."""
    return _demanda(
        "d-diretor",
        titulo="O relatório some",
        autor_id=DIRETOR["id"],
        criado_em="2026-11-01T10:00:00Z",
        github_issue_numero=912,
        github_foto={"numero": 912, "url": "https://github.com/pedrorezendefig/hospital-reunioes/issues/912"},
        etapa="em_desenvolvimento",
        partes=[
            {"numero": 913, "o_que_muda": "A lista mostra o relatório", "situacao": "em_desenvolvimento"},
            {"numero": 914, "o_que_muda": "O PDF sai com a data", "situacao": "planejada"},
        ],
    )


def _demandas_de_dois_autores() -> list[dict]:
    return [
        _card_de_outro_autor(),
        _demanda("d-pedro", titulo="Pedido da Vitta", autor_id=PEDRO["id"], criado_em="2026-11-02T10:00:00Z"),
    ]


class TestTodoSuperAdminListaTodas:
    def test_super_admin_sem_login_do_github_lista_demandas_de_outro_autor(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch,
            logado=OUTRO_DIRETOR,
            participantes=[PEDRO, DIRETOR, OUTRO_DIRETOR],
            demandas=_demandas_de_dois_autores(),
        )

        resposta = client.get(TODAS)

        assert resposta.status_code == 200, resposta.text
        assert [(d["titulo"], d["autor"]) for d in resposta.json()] == [
            ("Pedido da Vitta", "Pedro Vitta"),
            ("O relatório some", "Diretor do Hospital"),
        ]

    def test_super_admin_sem_login_do_github_ve_o_numero_da_raiz_e_das_partes_no_documento_do_card(self, monkeypatch):
        """O Documento do card abre do item da lista: o numero e o link da
        raiz e o numero de cada parte saem tambem para quem nao tem login."""
        client, _, _ = _cenario(
            monkeypatch,
            logado=OUTRO_DIRETOR,
            participantes=[PEDRO, DIRETOR, OUTRO_DIRETOR],
            demandas=_demandas_de_dois_autores(),
        )

        item = next(d for d in client.get(TODAS).json() if d["id"] == "d-diretor")

        assert item["raiz_numero"] == 912
        assert item["issue_numero"] == 912
        assert item["issue_url"] == "https://github.com/pedrorezendefig/hospital-reunioes/issues/912"
        assert [p["numero"] for p in item["partes"]] == [913, 914]


class TestQuemNaoESuperAdmin:
    @pytest.mark.parametrize("rota", [CHAT, TODAS, f"{BASE}/entregas", f"{CHAT}/d-diretor"])
    def test_quem_nao_e_super_admin_continua_sem_acesso_a_aba(self, monkeypatch, rota):
        client, _, _ = _cenario(
            monkeypatch,
            logado=GESTOR,
            participantes=[PEDRO, DIRETOR, GESTOR],
            demandas=_demandas_de_dois_autores(),
        )

        resposta = client.get(rota)

        assert resposta.status_code == 403, resposta.text
        assert "O relatório some" not in resposta.text


class TestResponsavelDiretor:
    def test_card_atribuido_ao_diretor_mostra_o_nome_dele_como_responsavel(self, monkeypatch):
        """O diretor cria o card, a Vitta o atribui a ele no GitHub, e outro
        Super admin, sem login, ve o nome dele como Responsavel."""
        participantes = [PEDRO, DIRETOR, OUTRO_DIRETOR, DIRETOR_COLABORADOR]
        _, sb, _ = _cenario(monkeypatch, logado=DIRETOR, participantes=participantes)
        demanda_id = _ate_o_resumo(_montar_como(DIRETOR, sb, monkeypatch), monkeypatch)
        assert (
            _montar_como(DIRETOR, sb, monkeypatch).post(f"{CHAT}/{demanda_id}/criar-card", json={}).status_code == 200
        )
        linha = _demandas(sb)[0]
        numero = linha["github_issue_numero"]
        dados = _issue(numero, labels=("needs-triage",))
        dados["assignees"] = [{"login": "Diretor-HSM"}]
        dados["assignee"] = dados["assignees"][0]
        cliente, sb_webhook, _ = _montar(
            demandas=[linha],
            participantes=participantes,
            github=_GithubFalso({numero: dados}),
            monkeypatch=monkeypatch,
        )
        assert _entregar(cliente, _corpo(numero, acao="assigned")).status_code == 200
        sb.tabelas["tecnologia_demandas"] = [dict(d) for d in _demandas_do_webhook(sb_webhook)]

        lista = _montar_como(OUTRO_DIRETOR, sb, monkeypatch).get(TODAS).json()

        assert [(d["id"], d["responsavel"]) for d in lista] == [(demanda_id, "Diretor Colaborador")]


def _montar_como(logado: dict, sb, monkeypatch):
    client, _, _ = _montar_da_aba(logado=logado, supabase=sb, monkeypatch=monkeypatch)
    return client


class TestAListaDoDiretor:
    def test_a_lista_sem_recorte_do_super_admin_sem_login_traz_todas(self, monkeypatch):
        """A tela de quem nao e Desenvolvedor pede a lista sem recorte (o
        Minhas): ela traz todas, e nenhum Super admin fica limitado as
        proprias Demandas. O recorte continua do Desenvolvedor."""
        client, _, _ = _cenario(
            monkeypatch,
            logado=OUTRO_DIRETOR,
            participantes=[PEDRO, DIRETOR, OUTRO_DIRETOR],
            demandas=_demandas_de_dois_autores(),
        )

        assert [d["id"] for d in client.get(CHAT).json()] == ["d-pedro", "d-diretor"]
