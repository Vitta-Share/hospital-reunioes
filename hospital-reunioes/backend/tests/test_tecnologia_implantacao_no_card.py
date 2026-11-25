"""A Implantação no card lida dos Cards de implantação (issue #2266, PRD
#2262, ADR 0113, decisão 9; antes, issue #2209 e ADR 0111, decisão 5).

O "Implantação X de Y" do Documento do card e o selo do Quadro saem das
sub-issues da raiz com a label `implantacao`: as fechadas sobre o total. A
sincronização (webhook e conferência de hora em hora) guarda essas sub-issues
na foto da Demanda, e a lista do chat deriva a Implantação dela. O registro do
Pedido de implantação deixa de ser fonte. Sem sub-issue `implantacao`, a
leitura vem com a Implantação nula, e o Card de implantação não conta como
Parte.

Pela ROTA de verdade (a lista do chat lê, o webhook sincroniza), com o
Supabase em memória e o GitHub dublado.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_kit_conhecimento import ARQUIVO_DA_ABA  # noqa: E402
from test_kit_conhecimento import _texto as _texto_do_kit  # noqa: E402
from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    DEMANDA,
    DIRETORA,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
)

from app.services import github_client  # noqa: E402

LISTA = "/api/admin/tecnologia/chat"

RAIZ = 1700
TESTE = "Testar o anonimato do Canal de Conduta"
ABERTURA = "Abrir o Canal de Conduta para todos"


def _issue(numero: int, titulo: str, *, estado: str = "open", labels=(), dono: str | None = None) -> dict:
    dados = {
        "number": numero,
        "title": titulo,
        "html_url": f"https://github.com/pedrorezendefig/hospital-reunioes/issues/{numero}",
        "state": estado,
        "state_reason": "completed" if estado == "closed" else None,
        "labels": [{"name": nome} for nome in labels],
        "body": "## Para o diretor\n\n**O que muda:** o relato anônimo.",
        "assignees": [{"login": dono}] if dono else [],
    }
    if estado == "closed":
        dados["closed_at"] = "2026-11-24T12:00:00Z"
    return dados


def _raiz(*, estado: str = "open") -> dict:
    return _issue(RAIZ, "Canal de Conduta", estado=estado)


def _fatia(numero: int = 1801, *, estado: str = "closed") -> dict:
    return _issue(numero, "Fatia do relato anônimo", estado=estado)


def _card(numero: int, titulo: str, *, estado: str = "open", dono: str | None = None) -> dict:
    return _issue(numero, titulo, estado=estado, labels=("implantacao",), dono=dono)


def _na_lista(foto: dict, monkeypatch) -> dict:
    """A Demanda como a lista do chat a devolve, com esta foto guardada pela
    sincronização."""
    _, sb = _ponte()
    [linha] = sb.tabelas["tecnologia_demandas"]
    linha["github_foto"] = foto
    resposta = _tela(sb, DIRETORA, monkeypatch).get(LISTA)
    assert resposta.status_code == 200, resposta.text
    [demanda] = [d for d in resposta.json() if d["id"] == DEMANDA]
    return demanda


class TestALeituraDaDemanda:
    def test_raiz_com_dois_cards_de_implantacao_e_um_fechado_mostra_1_de_2(self, monkeypatch):
        foto = github_client.montar_foto(
            _raiz(),
            [
                _fatia(),
                _card(1854, TESTE, estado="closed", dono="pedrorezendefig"),
                _card(1855, ABERTURA, dono="fulano-de-fora"),
            ],
        )

        demanda = _na_lista(foto, monkeypatch)

        assert demanda["implantacao"] == {
            "feitos": 1,
            "total": 2,
            "pedidos": [
                {"titulo": TESTE, "destinatario": "Pedro Rezende", "situacao": "feito", "espera": None},
                {"titulo": ABERTURA, "destinatario": "fulano-de-fora", "situacao": "aberto", "espera": None},
            ],
        }
