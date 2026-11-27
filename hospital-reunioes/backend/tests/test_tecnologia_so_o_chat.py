"""A aba Tecnologia só lê: o Quadro e as Entregas (issue #2279, PRD #2262, ADR 0113, decisões 6 e 7).

Desde a issue #1386 (ADR 0077) a aba era o chat do agente. Saíram, nesta
fatia, o chat com o Planejamento e o Criar o card, a Conversa da Demanda, o
Envio aos desenvolvedores, a lista Esperando você com os cartões de Pergunta e
Passo a passo, o Me explique, o Revisar, o Apagar, o Reenviar, o Designar de
novo, o seletor de modelo e a leitura do print. Ficam as leituras da aba, o
webhook do GitHub que deriva a Etapa e a rota de automação dos anexos. A
prova por chamada HTTP de que cada rota que saiu responde 404 mora em
`test_tecnologia_so_quadro_e_entregas.py`; aqui é o schema inteiro.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PREFIXO_DA_ABA = "/api/admin/tecnologia"

# As rotas que a aba chama, e só elas. Escritas à mão, e não lidas do router:
# desde a issue #2279 (ADR 0113, decisões 6 e 7) a aba só lê o Quadro e as
# Entregas, e o chat, a Conversa da Demanda e os Pedidos da Vitta saíram.
ROTAS_DO_CHAT = {
    # Se quem esta logado e Desenvolvedor (issue #1531, ADR 0083).
    "/api/admin/tecnologia/eu",
    # As opcoes do filtro Responsavel (issue #1533, ADR 0083, decisao 5).
    "/api/admin/tecnologia/desenvolvedores",
    # O Quadro e a lista do celular (issue #1384).
    "/api/admin/tecnologia/chat",
    # A aba Entregas, só leitura (issue #1556, ADR 0084, decisão 8).
    "/api/admin/tecnologia/entregas",
    # As opções do filtro Projeto, com os projetos novos da Vitta (issue #1967).
    "/api/admin/tecnologia/projetos",
}

# O que fica de fora da aba e continua de pé (critério 2 da issue).
ROTAS_QUE_FICAM = (
    "/api/webhooks/github",
    "/api/webhooks/deploy",
    "/api/automacao/tecnologia/demandas/{demanda_id}/anexos",
)


def _caminhos_do_app() -> dict:
    """A fonte é o schema OpenAPI, e não `app.routes` (issues #542 e #546)."""
    from app.main import app

    cache = app.openapi_schema
    try:
        return app.openapi()["paths"]
    finally:
        app.openapi_schema = cache


def test_a_aba_tecnologia_so_tem_as_rotas_de_leitura():
    caminhos = _caminhos_do_app()

    assert len(caminhos) > 50, "O schema voltou quase vazio: a varredura estaria olhando para nada"
    da_aba = {caminho for caminho in caminhos if caminho.startswith(PREFIXO_DA_ABA)}
    assert da_aba == ROTAS_DO_CHAT


def test_o_webhook_da_etapa_e_a_automacao_dos_anexos_continuam_no_app():
    caminhos = _caminhos_do_app()

    for rota in ROTAS_QUE_FICAM:
        assert rota in caminhos, rota
