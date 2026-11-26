"""A ponte de automação fica só com a leitura dos anexos (issue #2281, PRD #2262, ADR 0113, decisões 7 e 10).

Saem da ponte as rotas de escrita (criar Demanda, escrever na Conversa, criar,
resolver e cancelar o Pedido da Vitta), as leituras que ficaram sem chamador
(Destinatários, Demanda, implantação, Pedido e Conversa) e a rota de
validações, que a Apresentação do PRD chamava. Fica a leitura dos anexos, que
serve ao bug: o `pegar-issue/scripts/anexos.py` busca os prints por ela.

Tudo por chamada HTTP de verdade no app inteiro (`app.main.app`), e não pela
lista `app.routes`, com a chave da ponte certa no header: a rota que sumiu
responde o 404 do roteador ("Not Found", e não a frase de uma rota de pé que
não achou a Demanda). A contraprova é a leitura dos anexos, que responde 200
ao MESMO cliente e com a MESMA chave: sem ela, um 404 geral (o router
desmontado) passaria por remoção.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_anexos import _StorageFake  # noqa: E402
from test_tecnologia_vinculo import _SupabaseMock  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402

CHAVE = "chave-da-ponte-do-teste-2281"
BASE = "/api/automacao/tecnologia"
DEMANDA = "3f2a9c1e-7b44-4d0a-9a51-0c6f7e8d1a22"
PEDIDO = "8c1e2d3f-4a5b-4c6d-9e7f-0a1b2c3d4e5f"
BUCKET = "anexos-tecnologia"

# Cada rota que saiu, com o método. Escritas à mão: é a lista da issue.
ROTAS_REMOVIDAS = [
    # As escritas: criar a Demanda de um Projeto novo e escrever na Conversa.
    ("POST", f"{BASE}/projetos/hospital/issues/1700/demanda"),
    ("POST", f"{BASE}/demandas/{DEMANDA}/conversa"),
    # O Pedido da Vitta: criar, resolver e cancelar.
    ("POST", f"{BASE}/demandas/{DEMANDA}/perguntas"),
    ("POST", f"{BASE}/perguntas/{PEDIDO}/resolver"),
    ("POST", f"{BASE}/perguntas/{PEDIDO}/cancelar"),
    # As leituras sem chamador: Destinatários, Demanda, implantação, Pedido e Conversa.
    ("GET", f"{BASE}/destinatarios"),
    ("GET", f"{BASE}/projetos/hospital/issues/1700/demanda"),
    ("GET", f"{BASE}/projetos/hospital/issues/1700/implantacao"),
    ("GET", f"{BASE}/perguntas/{PEDIDO}"),
    ("GET", f"{BASE}/demandas/{DEMANDA}/conversa"),
    # A observação do Validar da Apresentação do PRD (ADR 0113, decisão 10).
    ("POST", f"{BASE}/validacoes"),
]

ANEXOS = f"{BASE}/demandas/{DEMANDA}/anexos"


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    """O teto da ponte guarda a contagem em memória entre testes e arquivos."""
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def cliente(monkeypatch):
    """O app inteiro, com a chave da ponte ligada e um print guardado na Demanda."""
    from app.main import app

    monkeypatch.setattr(settings, "tecnologia_automacao_api_key", CHAVE)
    banco = _SupabaseMock(
        {
            "tecnologia_demandas": [{"id": DEMANDA, "titulo": "O relatório some", "projeto": "hospital"}],
            "tecnologia_anexos": [
                {
                    "id": "a-1",
                    "demanda_id": DEMANDA,
                    "ordem": 1,
                    "storage_path": f"demanda-{DEMANDA}/sorteado1.png",
                    "nome_original": "tela do erro.png",
                    "content_type": "image/png",
                    "tamanho_bytes": 10,
                    "anexado_por": "P1",
                    "criado_em": "2026-11-20T10:00:00Z",
                    "apagado_em": None,
                    "conversa_id": None,
                }
            ],
        }
    )
    banco.storage = _StorageFake()
    banco.storage.arquivos[f"{BUCKET}/demanda-{DEMANDA}/sorteado1.png"] = b"png"

    antes = dict(app.dependency_overrides)
    app.dependency_overrides[get_supabase_client] = lambda: banco
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(antes)


@pytest.mark.parametrize(("metodo", "rota"), ROTAS_REMOVIDAS, ids=[f"{m} {r}" for m, r in ROTAS_REMOVIDAS])
def test_a_rota_que_saiu_da_ponte_responde_404(cliente: TestClient, metodo: str, rota: str):
    resposta = cliente.request(metodo, rota, json={}, headers={"X-API-Key": CHAVE})

    assert resposta.status_code == 404, resposta.text
    # O "Not Found" do roteador, e não o 404 de uma rota de pé que não achou a
    # Demanda ou o Pedido: esse vem com a frase dela.
    assert resposta.json() == {"detail": "Not Found"}


def test_quem_desenvolve_ainda_busca_os_prints_com_a_chave(cliente: TestClient):
    resposta = cliente.get(ANEXOS, headers={"X-API-Key": CHAVE})

    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {
        "anexos": [
            {
                "nome": "tela do erro.png",
                "tipo": "image/png",
                "url": f"https://storage.local/{BUCKET}/demanda-{DEMANDA}/sorteado1.png?token=assinado&exp=600",
            }
        ]
    }


def test_sem_a_chave_os_prints_continuam_fechados(cliente: TestClient):
    resposta = cliente.get(ANEXOS)

    assert resposta.status_code == 401
    assert resposta.json() == {"detail": "API key inválida ou ausente"}
