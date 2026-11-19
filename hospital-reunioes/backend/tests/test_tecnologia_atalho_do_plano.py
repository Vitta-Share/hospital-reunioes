"""O atalho Ver o plano no card (issue #2010, PRD #2007, ADR 0108 decisão 2).

A sincronização lê na issue-raiz o marcador `<!-- apresentacao: <url> -->`,
que o `apresentar.py publicar` grava, como já lê o da Demonstração, e aceita
só a página dos planos (`https://planos-hsm.vercel.app/`). Lê também a label
`validado:diretor`: com ela o plano está validado, e sem ela volta a não
estar. A lista entrega os dois campos à tela.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_chat import CHAT, _cenario  # noqa: E402
from test_tecnologia_vinculo import DIRETOR  # noqa: E402
from test_tecnologia_vinculo import _demanda as _demanda_do_diretor  # noqa: E402
from test_tecnologia_webhook_github import (  # noqa: E402
    _corpo,
    _demandas,
    _entregar,
    _GithubFalso,
    _issue,
    _ja_sincronizada,
    _montar,
    _pr_do_app,  # noqa: F401  (autouse)
    _reset_rate_limiter,  # noqa: F401  (autouse)
    _segredo_configurado,  # noqa: F401  (autouse)
    _sem_github_de_verdade,  # noqa: F401  (autouse)
    _sem_pr_aberto,  # noqa: F401  (autouse)
)

from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

PLANO = "https://planos-hsm.vercel.app/2007/"
OUTRO_PLANO = "https://planos-hsm.vercel.app/2007-v2/"


def _raiz(corpo: str = "", *, labels=()) -> dict:
    return {**_issue(673, labels=labels), "body": f"## Para o diretor\n\nO selo se atualiza sozinho.\n\n{corpo}"}


def _sincronizar(issue: dict, monkeypatch, *, acao: str = "edited", antes: dict | None = None, **campos) -> dict:
    """Entrega o evento `issues` da raiz e devolve a Demanda como ficou.

    `antes` é a issue como a sincronização anterior a viu: a Demanda parte do
    cache que ela deixou.
    """
    gh = _GithubFalso({673: issue})
    anterior = _GithubFalso({673: antes or _issue(673)})
    cliente, sb, _ = _montar(demandas=[_ja_sincronizada(anterior, 673, **campos)], github=gh, monkeypatch=monkeypatch)
    _entregar(cliente, _corpo(acao=acao))
    [demanda] = _demandas(sb)
    return demanda


class TestOMarcador:
    def test_o_marcador_da_pagina_dos_planos_grava_o_link_do_plano(self, monkeypatch):
        demanda = _sincronizar(_raiz(f"<!-- apresentacao: {PLANO} -->"), monkeypatch)

        assert demanda["apresentacao_url"] == PLANO

    @pytest.mark.parametrize(
        "marcador",
        [
            "<!-- apresentacao: https://youtu.be/plano -->",
            "<!-- apresentacao: http://planos-hsm.vercel.app/2007/ -->",
            "<!-- apresentacao: https://planos-hsm.vercel.app.golpe.com/2007/ -->",
            "<!-- apresentacao: https://outro.vercel.app/planos-hsm.vercel.app/ -->",
            '<!-- apresentacao: https://planos-hsm.vercel.app/x"onclick="y -->',
            "<!-- apresentacao: javascript:alert(1) -->",
            "`<!-- apresentacao: <url> -->`",
        ],
    )
    def test_o_endereco_fora_da_pagina_dos_planos_e_recusado(self, monkeypatch, marcador):
        demanda = _sincronizar(_raiz(marcador), monkeypatch)

        assert demanda.get("apresentacao_url") is None

    def test_vale_o_ultimo_marcador_do_corpo(self, monkeypatch):
        corpo = f"O marcador e `<!-- apresentacao: <url> -->`.\n\n<!-- apresentacao: {PLANO} -->\n"

        demanda = _sincronizar(_raiz(corpo), monkeypatch)

        assert demanda["apresentacao_url"] == PLANO

    def test_o_plano_republicado_troca_o_link(self, monkeypatch):
        demanda = _sincronizar(_raiz(f"<!-- apresentacao: {OUTRO_PLANO} -->"), monkeypatch, apresentacao_url=PLANO)

        assert demanda["apresentacao_url"] == OUTRO_PLANO

    def test_tirar_o_marcador_da_issue_nao_apaga_o_link_gravado(self, monkeypatch):
        demanda = _sincronizar(
            {**_issue(673), "body": "## Para o diretor\n\nO selo agora diz outra coisa."},
            monkeypatch,
            apresentacao_url=PLANO,
        )

        assert demanda["o_que_muda"] == "O selo agora diz outra coisa."
        assert demanda["apresentacao_url"] == PLANO


class TestALabel:
    def test_a_label_validado_diretor_marca_o_plano_validado(self, monkeypatch):
        demanda = _sincronizar(_raiz(labels=("validado:diretor",)), monkeypatch, acao="labeled")

        assert demanda["plano_validado"] is True

    def test_sem_a_label_o_plano_volta_a_nao_estar_validado(self, monkeypatch):
        demanda = _sincronizar(
            _raiz(),
            monkeypatch,
            acao="unlabeled",
            antes=_raiz(labels=("validado:diretor",)),
        )

        assert demanda["plano_validado"] is False


class TestALista:
    def test_a_lista_entrega_o_link_do_plano_e_se_ele_esta_validado(self, monkeypatch):
        client, _, _ = _cenario(
            monkeypatch,
            logado=DIRETOR,
            participantes=[DIRETOR],
            demandas=[
                _demanda_do_diretor(
                    "d-1",
                    autor_id=DIRETOR["id"],
                    github_issue_numero=673,
                    apresentacao_url=PLANO,
                    plano_validado=True,
                )
            ],
        )

        [item] = client.get(CHAT).json()

        assert (item["apresentacao_url"], item["plano_validado"]) == (PLANO, True)


class TestOKit:
    def test_o_kit_da_tecnologia_diz_o_atalho_do_plano(self):
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")

        assert "**Ver o plano**" in texto
