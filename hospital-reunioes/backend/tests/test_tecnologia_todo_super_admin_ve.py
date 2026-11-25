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

from test_tecnologia_chat import CHAT, _cenario  # noqa: E402
from test_tecnologia_vinculo import DIRETOR, PEDRO, _demanda, _pessoa  # noqa: E402

from app.limiter import limiter  # noqa: E402

# Outra pessoa da diretoria: Super admin, sem login do GitHub.
OUTRO_DIRETOR = _pessoa("P3", "Outro Diretor")

TODAS = f"{CHAT}?filtro=todas"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


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
