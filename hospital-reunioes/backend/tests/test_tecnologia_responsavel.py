"""O Responsavel da Demanda na lista (issue #1533, PRD #1529, ADR 0083, decisao 5).

O "Quem cuida disto?" do resumo saiu com o chat (issue #2279, ADR 0113,
decisao 7). Ficam a lista dos Desenvolvedores, que da as opcoes do filtro
Responsavel, o Responsavel em cada linha e o filtro "Para mim".
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_chat import (  # noqa: E402
    CHAT,
    _cenario,
    _integracao_configurada,  # noqa: F401
    _llm_em_mock,  # noqa: F401
    _reset_rate_limiter,  # noqa: F401
)
from test_tecnologia_vinculo import BASE, DIRETOR, PEDRO, _demanda, _pessoa  # noqa: E402

from app.config import settings  # noqa: E402

RIB = _pessoa("P4", "Pedro Rib", github_login="pedrorib")
LUCAS = _pessoa("P5", "Lucas Sampaio", github_login="lucas-sampaio")
# Tem login do GitHub, mas não é Super admin: não é Desenvolvedor.
ANALISTA = _pessoa("P6", "Analista de TI", github_login="analista-ti", access_profile="facilitador")

DESENVOLVEDORES = f"{BASE}/desenvolvedores"


def _participantes() -> list[dict]:
    return [PEDRO, DIRETOR, RIB, LUCAS, ANALISTA]


@pytest.fixture(autouse=True)
def _dono_na_configuracao(monkeypatch):
    monkeypatch.setattr(settings, "github_login_dono", "pedrorezendefig")


# ═══════════════════════════════════════════════════════════════════════════
# 1. O seletor "Quem cuida disto?"
# ═══════════════════════════════════════════════════════════════════════════


class TestSeletor:
    def test_o_seletor_lista_exatamente_os_super_admins_com_login_do_github(self, monkeypatch):
        client, _, _ = _cenario(monkeypatch, participantes=_participantes())

        resposta = client.get(DESENVOLVEDORES)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == [
            {"id": "P5", "nome": "Lucas Sampaio", "padrao": False},
            {"id": "P4", "nome": "Pedro Rib", "padrao": False},
            {"id": "P1", "nome": "Pedro Vitta", "padrao": True},
        ]

    def test_o_padrao_e_quem_tem_o_login_do_dono_da_configuracao(self, monkeypatch):
        """A tela diz para quem vai o card sem escolha: o dono, pelo nome."""
        monkeypatch.setattr(settings, "github_login_dono", "Lucas-Sampaio")
        client, _, _ = _cenario(monkeypatch, participantes=_participantes())

        padrao = [d["nome"] for d in client.get(DESENVOLVEDORES).json() if d["padrao"]]

        assert padrao == ["Lucas Sampaio"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. O assignee pedido ao GitHub
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 3. As labels de sempre
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# 4. A lista
# ═══════════════════════════════════════════════════════════════════════════


def _demandas_com_responsavel() -> list[dict]:
    return [
        _demanda(
            "d-rib",
            titulo="O relatório some",
            autor_id=DIRETOR["id"],
            responsavel_id=RIB["id"],
            github_issue_numero=910,
            etapa="em_analise",
            criado_em="2026-11-03T10:00:00Z",
        ),
        _demanda(
            "d-pedro",
            titulo="Agenda de retorno",
            autor_id=DIRETOR["id"],
            responsavel_id=PEDRO["id"],
            github_issue_numero=911,
            etapa="em_analise",
            criado_em="2026-11-02T10:00:00Z",
        ),
        # Conversa sem card, de antes desta versão: o Responsável que o
        # Produto punha no nascimento não conta, porque ninguém escolheu.
        _demanda(
            "d-registrada",
            titulo="Conversa no meio",
            autor_id=DIRETOR["id"],
            responsavel_id=PEDRO["id"],
            criado_em="2026-11-01T10:00:00Z",
        ),
    ]


class TestLista:
    @pytest.mark.parametrize("logado", [DIRETOR, PEDRO], ids=["diretor", "desenvolvedor"])
    def test_o_responsavel_aparece_em_cada_linha(self, monkeypatch, logado):
        client, _, _ = _cenario(
            monkeypatch, logado=logado, participantes=_participantes(), demandas=_demandas_com_responsavel()
        )

        resposta = client.get(f"{CHAT}?filtro=todas")

        assert resposta.status_code == 200, resposta.text
        assert [(d["id"], d["responsavel"]) for d in resposta.json()] == [
            ("d-rib", "Pedro Rib"),
            ("d-pedro", "Pedro Vitta"),
            ("d-registrada", None),
        ]

    def test_para_mim_mostra_so_as_demandas_de_que_o_desenvolvedor_e_responsavel(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch, logado=PEDRO, participantes=_participantes(), demandas=_demandas_com_responsavel()
        )

        resposta = client.get(f"{CHAT}?filtro=para_mim")

        assert resposta.status_code == 200, resposta.text
        assert [d["id"] for d in resposta.json()] == ["d-pedro"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. O Kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════
