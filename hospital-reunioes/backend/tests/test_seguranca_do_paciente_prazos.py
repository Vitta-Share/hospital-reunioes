"""Os prazos do caso e a tabela de prazos do Núcleo (issue #1993, PRD #1979,
ADR 0107 decisões 1 e 2).

Um bloco por critério de aceite do backend:

1. confirmar um caso de cada faixa grava os prazos do art. 26 do Regimento,
   com data e hora absolutas;
2. os prazos legais não aparecem como editáveis, e a rota recusa alterá-los;
3. editar um prazo interno grava o histórico (quem, quando, de e para) e não
   muda caso já classificado;
4. confirmar cria a linha de notificação externa: VigiMed para medicação,
   NOTIVISA para o resto, e nenhuma na circunstância de risco;
5. só a Presidência e o Acesso pleno editam a tabela;
6. o kit de conhecimento diz o comportamento novo.

Os vencimentos esperados são contados à mão, no calendário de novembro de
2026: o caso chega na terça 10/11 às 10h de São Paulo, e o incidente foi na
segunda 09/11 às 22h. Úteis são os dias de segunda a sexta, das 8h às 17h.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_triagem import (  # noqa: E402
    DIRETOR_EXECUTIVO,
    GRAVE,
    MEMBRO,
    MODERADO,
    OBITO,
    PRESIDENTE,
    QUASE_ERRO,
    SUPER_ADMIN,
    TODOS_OS_CAMPOS,
    _banco,
    _notificacao,
    _sugestao,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_notificacoes as notificacoes_router  # noqa: E402
from app.routers import seguranca_do_paciente_prazos as prazos_router  # noqa: E402
from app.routers import seguranca_do_paciente_triagem as triagem_router  # noqa: E402

SP = ZoneInfo("America/Sao_Paulo")

# Chegou na terça 10/11/2026 às 10h de São Paulo; o incidente foi na segunda
# 09/11 às 22h.
CHEGADA = "2026-11-10T13:00:00+00:00"
DO_CASO = {"criado_em": CHEGADA, "data_ocorrencia": "2026-11-09", "hora_aproximada": "22:00:00"}

LEVE = {"natureza": "evento_adverso", "grau_de_dano": "leve", "faixa": "D"}
CIRCUNSTANCIA = {"natureza": "circunstancia_de_risco", "grau_de_dano": "nenhum", "faixa": "E"}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _cliente(banco, pessoa: dict[str, Any] = PRESIDENTE) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(triagem_router.router, prefix="/api")
    app.include_router(notificacoes_router.router, prefix="/api")
    app.include_router(prazos_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _caso_confirmado(sugestao: dict, **campos) -> tuple[Any, dict]:
    caso = _notificacao(1, **{**DO_CASO, **campos})
    banco = _banco([caso], [_sugestao(caso, **sugestao)])
    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})
    assert resposta.status_code == 201, resposta.text
    return banco, caso


def _prazos_na_tela(banco, caso, pessoa=PRESIDENTE) -> dict[str, tuple[str, str]]:
    """O que o caso mostra: marco -> (legal ou interno, data e hora em São Paulo)."""
    resposta = _cliente(banco, pessoa).get(f"/api/nsp/notificacoes/{caso['id']}")
    assert resposta.status_code == 200, resposta.text
    return {
        p["marco"]: (p["tipo"], datetime.fromisoformat(p["vence_em"]).astimezone(SP).strftime("%d/%m/%Y %H:%M"))
        for p in resposta.json()["prazos"]
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Confirmar grava os prazos do art. 26, com data e hora absolutas
# ═══════════════════════════════════════════════════════════════════════════

PRAZOS_ESPERADOS = {
    # Faixa A, óbito: 72 horas corridas do incidente, 60 dias corridos para a
    # complementação, e os internos da coluna "Evento que nunca deveria
    # ocorrer / Óbito".
    "A": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),  # 24h corridas
        "comunicacao_a_direcao": ("interno", "10/11/2026 12:00"),  # 2h corridas
        "triagem": ("interno", "10/11/2026 14:00"),  # 4h úteis
        "inicio_da_investigacao": ("interno", "12/11/2026 16:00"),  # 24h úteis: 7 + 9 + 8
        "conclusao_da_investigacao": ("interno", "25/12/2026 23:59"),  # 45 dias corridos
        "reuniao_de_analise": ("interno", "19/11/2026 17:00"),  # 7 dias úteis
        "notificacao_externa": ("legal", "12/11/2026 22:00"),  # 72h corridas do incidente
        "complementacao_da_notificacao_externa": ("legal", "08/01/2027 23:59"),  # 60 dias corridos
    },
    # Faixa B, dano grave: 15º dia útil de dezembro (21/12).
    "B": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),
        "comunicacao_a_direcao": ("interno", "11/11/2026 10:00"),  # 24h corridas
        "triagem": ("interno", "11/11/2026 17:00"),  # 1 dia útil
        "inicio_da_investigacao": ("interno", "13/11/2026 17:00"),  # 3 dias úteis
        "conclusao_da_investigacao": ("interno", "10/12/2026 23:59"),  # 30 dias corridos
        "reuniao_de_analise": ("interno", "01/12/2026 17:00"),  # 15 dias úteis
        "notificacao_externa": ("legal", "21/12/2026 17:00"),
    },
    # Faixa C, dano moderado: sem comunicação à Direção e reunião na pauta
    # ordinária, sem data.
    "C": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),
        "triagem": ("interno", "12/11/2026 17:00"),  # 2 dias úteis
        "inicio_da_investigacao": ("interno", "17/11/2026 17:00"),  # 5 dias úteis
        "conclusao_da_investigacao": ("interno", "08/12/2026 17:00"),  # 20 dias úteis
        "notificacao_externa": ("legal", "21/12/2026 17:00"),
    },
    # Faixa D, dano leve.
    "D": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),
        "triagem": ("interno", "13/11/2026 17:00"),  # 3 dias úteis
        "conclusao_da_investigacao": ("interno", "24/11/2026 17:00"),  # 10 dias úteis
        "notificacao_externa": ("legal", "21/12/2026 17:00"),
    },
    # Faixa E, quase erro: a análise é agregada no mês, sem data própria.
    "E": {
        "confirmacao_ao_notificante": ("interno", "11/11/2026 10:00"),
        "triagem": ("interno", "17/11/2026 17:00"),  # 5 dias úteis
        "notificacao_externa": ("legal", "21/12/2026 17:00"),
    },
}

SUGESTAO_DA_FAIXA = {"A": OBITO, "B": GRAVE, "C": MODERADO, "D": LEVE, "E": QUASE_ERRO}


@pytest.mark.parametrize("faixa", list(PRAZOS_ESPERADOS))
def test_confirmar_grava_os_prazos_do_art_26_da_faixa(faixa):
    banco, caso = _caso_confirmado(SUGESTAO_DA_FAIXA[faixa])

    assert _prazos_na_tela(banco, caso) == PRAZOS_ESPERADOS[faixa]


# ═══════════════════════════════════════════════════════════════════════════
# 4. A linha de notificação externa: VigiMed para medicação, NOTIVISA para o
#    resto, nenhuma na circunstância de risco
# ═══════════════════════════════════════════════════════════════════════════


def _notificacao_externa(banco, caso) -> dict | None:
    resposta = _cliente(banco).get(f"/api/nsp/notificacoes/{caso['id']}")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["notificacao_externa"]


def _em_sao_paulo(instante: str) -> str:
    return datetime.fromisoformat(instante).astimezone(SP).strftime("%d/%m/%Y %H:%M")


@pytest.mark.parametrize(
    ("sugestao", "sistema", "prazo"),
    [
        ({**OBITO, "categoria": "MED"}, "vigimed", "12/11/2026 22:00"),
        ({**MODERADO, "categoria": "MED"}, "vigimed", "21/12/2026 17:00"),
        (OBITO, "notivisa", "12/11/2026 22:00"),
        (QUASE_ERRO, "notivisa", "21/12/2026 17:00"),
    ],
    ids=["óbito por medicação", "medicação, dano moderado", "óbito por equipamento", "quase erro"],
)
def test_confirmar_cria_a_linha_de_notificacao_externa_com_o_sistema_e_o_prazo_legal(sugestao, sistema, prazo):
    banco, caso = _caso_confirmado(sugestao)

    externa = _notificacao_externa(banco, caso)

    assert externa is not None
    assert externa["sistema"] == sistema
    assert _em_sao_paulo(externa["prazo_legal"]) == prazo
    assert externa["estado"] == "pendente"


def test_circunstancia_de_risco_nao_cria_linha_de_notificacao_externa():
    banco, caso = _caso_confirmado(CIRCUNSTANCIA)

    assert _notificacao_externa(banco, caso) is None
    assert banco.tabelas.get("nsp_notificacoes_externas", []) == []
    assert "notificacao_externa" not in _prazos_na_tela(banco, caso)


def test_o_caso_antes_da_confirmacao_nao_tem_prazo_nem_linha_externa():
    caso = _notificacao(1, **DO_CASO)
    banco = _banco([caso], [_sugestao(caso, **OBITO)])

    assert _prazos_na_tela(banco, caso) == {}
    assert _notificacao_externa(banco, caso) is None
