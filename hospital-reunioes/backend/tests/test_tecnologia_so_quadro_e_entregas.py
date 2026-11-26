"""A aba Tecnologia fica com o Quadro e as Entregas (issue #2279, PRD #2262, ADR 0113, decisões 6 e 7).

Saem do backend as rotas da aba que escrevem ou chamam IA: o chat do
Assistente de Tecnologia, o seletor de modelo, a Conversa da Demanda, o Envio
aos desenvolvedores, a lista Esperando você e os cartões de Pergunta e Passo a
passo, o Me explique, o Revisar com o código de hoje, o Apagar, o Reenviar, o
Designar de novo e a leitura do print do chat. Ficam as leituras do Quadro e
das Entregas.

Tudo por chamada HTTP de verdade no app inteiro (`app.main.app`), e não pela
lista `app.routes`: a rota que sumiu responde o 404 do roteador ("Not Found",
e não a frase de uma rota de pé que não achou a Demanda) a um Super admin. A
contraprova são as leituras que ficam, que respondem 200 ao MESMO cliente: sem
ela, um 404 geral (o router desmontado, o login quebrado) passaria por remoção.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_vinculo import BASE, PEDRO, _SupabaseMock  # noqa: E402

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402

DEMANDA = "d-1"
PERGUNTA = "p-1"

# Cada rota que saiu, com o método. Escritas à mão: é a lista da issue.
ROTAS_REMOVIDAS = [
    # O chat do Assistente de Tecnologia, com o Planejamento e o Criar o card.
    ("GET", f"{BASE}/chat/{DEMANDA}"),
    ("POST", f"{BASE}/chat/{DEMANDA}"),
    ("POST", f"{BASE}/chat/{DEMANDA}/nao-bateu"),
    ("POST", f"{BASE}/chat/{DEMANDA}/resumo"),
    ("POST", f"{BASE}/chat/{DEMANDA}/criar-card"),
    ("POST", f"{BASE}/chat/{DEMANDA}/atualizar-card"),
    # O seletor de modelo.
    ("PUT", f"{BASE}/chat/{DEMANDA}/modelo"),
    # A Conversa da Demanda e o Envio aos desenvolvedores.
    ("GET", f"{BASE}/chat/{DEMANDA}/conversa"),
    ("POST", f"{BASE}/chat/{DEMANDA}/conversa"),
    ("POST", f"{BASE}/chat/{DEMANDA}/conversa/interpretar"),
    ("POST", f"{BASE}/chat/{DEMANDA}/conversa/enviar"),
    # Reenviar, Designar de novo, Apagar e Revisar com o código de hoje.
    ("POST", f"{BASE}/chat/{DEMANDA}/reenviar"),
    ("POST", f"{BASE}/chat/{DEMANDA}/designar-de-novo"),
    ("DELETE", f"{BASE}/chat/{DEMANDA}"),
    ("GET", f"{BASE}/chat/{DEMANDA}/revisao"),
    ("POST", f"{BASE}/chat/{DEMANDA}/revisao"),
    # A lista Esperando você e os cartões de Pergunta e Passo a passo.
    ("GET", f"{BASE}/perguntas/esperando"),
    ("POST", f"{BASE}/perguntas/{PERGUNTA}/resposta"),
    ("POST", f"{BASE}/perguntas/{PERGUNTA}/checks"),
    ("POST", f"{BASE}/perguntas/{PERGUNTA}/concluir"),
    ("POST", f"{BASE}/perguntas/{PERGUNTA}/reenviar"),
    # O Me explique.
    ("GET", f"{BASE}/perguntas/{PERGUNTA}/me-explique"),
    ("POST", f"{BASE}/perguntas/{PERGUNTA}/me-explique"),
    # A leitura do print e do documento do chat.
    ("POST", f"{BASE}/assistente/descrever-imagem"),
    ("POST", f"{BASE}/assistente/ler-documento"),
]

# As leituras do Quadro e das Entregas, que ficam.
ROTAS_QUE_FICAM = [
    f"{BASE}/chat",
    f"{BASE}/entregas",
    f"{BASE}/projetos",
    f"{BASE}/eu",
    f"{BASE}/desenvolvedores",
]


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def cliente():
    """O app inteiro, com o Pedro (Super admin) logado e o banco em memória."""
    from app.main import app

    banco = _SupabaseMock(
        {
            "participantes": [dict(PEDRO)],
            "tecnologia_produtos": [],
            "tecnologia_demandas": [
                {"id": DEMANDA, "titulo": "O relatório some", "autor_id": PEDRO["id"], "criado_em": "2026-11-01"}
            ],
        }
    )

    async def _usuario() -> dict[str, Any]:
        return {"id": PEDRO["auth_user_id"], "email": PEDRO["email"], "metadata": {}}

    antes = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(antes)


@pytest.mark.parametrize(("metodo", "rota"), ROTAS_REMOVIDAS, ids=[f"{m} {r}" for m, r in ROTAS_REMOVIDAS])
def test_a_rota_removida_responde_404(cliente: TestClient, metodo: str, rota: str):
    resposta = cliente.request(metodo, rota, json={})

    assert resposta.status_code == 404, resposta.text
    # O "Not Found" do roteador, e não o 404 de uma rota de pé que não achou a
    # Demanda ou a Pergunta: esse vem com a frase dela.
    assert resposta.json() == {"detail": "Not Found"}


def test_o_comeco_do_chat_saiu_e_a_lista_ficou(cliente: TestClient):
    """O `POST /chat` dividia o endereço com a lista do Quadro, que fica: o
    endereço existe, e o método que criava a Demanda não. É o 405 do HTTP, e
    não o 404, pela mesma razão."""
    resposta = cliente.post(f"{BASE}/chat", json={"mensagem": "Quero uma melhoria", "classificacao": "melhoria"})

    assert resposta.status_code == 405, resposta.text
    assert cliente.get(f"{BASE}/chat").status_code == 200


@pytest.mark.parametrize("rota", ROTAS_QUE_FICAM)
def test_a_leitura_do_quadro_e_das_entregas_fica(cliente: TestClient, rota: str):
    resposta = cliente.get(rota)

    assert resposta.status_code == 200, resposta.text
