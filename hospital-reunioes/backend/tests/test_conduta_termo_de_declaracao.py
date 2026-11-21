"""O termo de declaração redigido pelo agente (issue #1831, PRD #1786; ADR
0097, decisão 7; especificação, 7.1 e Anexos C e E.1).

Cada classe é um critério de aceite da issue. O banco, o Storage e a ClickSign
são dublês, a cifra é de verdade, e a IA é o `ClienteFalso`: o teste lê o que
sairia para o modelo e escolhe o que ele responde.
"""

from __future__ import annotations

import io
import json
import re
from typing import Any

import pdfplumber
import pytest
from anthropic_apoio import ClienteFalso
from test_conduta_depoimentos import (  # noqa: F401  (a fixture da chave vale aqui)
    BASE,
    COORDENACAO,
    MEMBRO,
    Comite,
    _chave,
)

from app.services.conduta import termo_de_declaracao

TRANSCRICAO = (
    "Entrevistador: Fulano de Tal, o senhor confirma que estava no almoxarifado?\n"
    "Fulano de Tal: Confirmo. Eu estava lá com a Maria Souza, das 14h às 15h.\n"
    "Fulano de Tal: Acho que levantei a voz, mas não ameacei ninguém.\n"
).encode()

IDENTIFICACAO = {
    "data": "2026-11-20",
    "hora": "14:30",
    "local": "Sala do Comitê",
    "conduziram": ["Ana Coordenadora", "Bruno Membro"],
    "cpf": "",
}


def _marcador(enviado: str, antes: str) -> str:
    """O marcador que o app pôs logo depois de `antes` no texto enviado."""
    achado = re.search(re.escape(antes) + r"(\[PESSOA_\d+\])", enviado)
    assert achado, f"sem marcador depois de {antes!r}"
    return achado.group(1)


def termo_que_ecoa(enviado: str, **campos) -> str:
    """O agente bem-comportado: usa os marcadores que recebeu, nunca o nome."""
    declarante = _marcador(enviado, "Entrevistador: ")
    maria = _marcador(enviado, "estava lá com a ")
    termo = {
        "declaracoes": [f"{declarante} declarou que estava no almoxarifado com {maria}, das 14h às 15h."],
        "documentos": [],
        "consentimento": "dado",
        "notas": [f"Perguntar a {maria} o que ouviu."],
    }
    return json.dumps({**termo, **campos})


class Agente(ClienteFalso):
    """O `ClienteFalso` que responde conforme o que recebeu: `responder`
    recebe tudo o que saiu para o modelo (instrução e mensagem)."""

    def __init__(self):
        super().__init__()
        self.responder = termo_que_ecoa

    def _create(self, **kwargs):
        self.texto = self.responder(_texto_da_chamada(kwargs))
        return super()._create(**kwargs)


def _texto_da_chamada(chamada: dict) -> str:
    return str(chamada.get("system", "")) + "\n" + json.dumps(chamada["messages"], ensure_ascii=False)


@pytest.fixture
def agente(monkeypatch) -> Agente:
    cliente = Agente()
    monkeypatch.setattr(termo_de_declaracao, "_cliente_do_agente_do_termo", lambda: cliente)
    return cliente


def _enviado(agente: Agente) -> str:
    """Tudo o que saiu para o modelo na última chamada."""
    return _texto_da_chamada(agente.chamadas[-1])


def _cartao(comite: Comite, caso: str, dep: str, pid: str = MEMBRO) -> dict[str, Any]:
    return next(d for d in comite.abrir(pid, caso)["depoimentos"] if d["id"] == dep)


def _redigir(comite: Comite, caso: str, dep: str, pid: str = MEMBRO, **corpo):
    return comite.cliente(pid).post(f"{BASE}/casos/{caso}/depoimentos/{dep}/termo", json={**IDENTIFICACAO, **corpo})


def _com_transcricao(comite: Comite) -> tuple[str, str]:
    caso = comite.caso()
    dep = comite.depoimento(caso)
    resposta = comite.anexar(MEMBRO, caso, dep, "transcricao", "depoimento.txt", TRANSCRICAO)
    assert resposta.status_code == 200, resposta.text
    return caso, dep


# ═══════════════════════════════════════════════════════════════════════════
# 1. O termo nasce de um clique, da transcrição ou dos pontos digitados
# ═══════════════════════════════════════════════════════════════════════════


class TestOTermoNasceDeUmClique:
    def test_o_clique_redige_o_termo_a_partir_da_transcricao(self, agente):
        comite = Comite()
        caso, dep = _com_transcricao(comite)
        assert _cartao(comite, caso, dep)["termo"] is None
        assert agente.chamadas == []

        resposta = _redigir(comite, caso, dep)

        assert resposta.status_code == 200, resposta.text
        assert len(agente.chamadas) == 1
        assert "não ameacei ninguém" in _enviado(agente)
        termo = _cartao(comite, caso, dep)["termo"]
        assert termo["versao"] == 1
        assert termo["declaracoes"] == [
            "Fulano de Tal declarou que estava no almoxarifado com Maria Souza, das 14h às 15h."
        ]

    def test_sem_gravacao_o_termo_sai_dos_pontos_digitados(self, agente):
        comite = Comite()
        caso = comite.caso()
        dep = comite.depoimento(caso)
        pontos = "Entrevistador: Fulano de Tal confirmou. Disse que estava lá com a Maria Souza no almoxarifado."
        comite.cliente(MEMBRO).post(
            f"{BASE}/casos/{caso}/depoimentos/{dep}/sem-gravacao", json={"motivo": "Não quis gravar", "pontos": pontos}
        )

        resposta = _redigir(comite, caso, dep)

        assert resposta.status_code == 200, resposta.text
        assert "no almoxarifado" in _enviado(agente)
        termo = _cartao(comite, caso, dep)["termo"]
        assert termo["gravacao"] == "Não houve gravação. Os pontos da conversa foram registrados por quem conduziu."

    def test_sem_transcricao_nem_pontos_o_clique_e_recusado_sem_chamar_o_agente(self, agente):
        comite = Comite()
        caso = comite.caso()
        dep = comite.depoimento(caso)

        resposta = _redigir(comite, caso, dep)

        assert resposta.status_code == 409
        assert "Anexe a transcrição" in resposta.json()["detail"]
        assert agente.chamadas == []
