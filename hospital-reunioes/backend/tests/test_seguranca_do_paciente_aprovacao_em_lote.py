"""A aprovação em lote das faixas D e E (issue #2002, PRD #1979, ADR 0107
decisão 10; Anexo F, seção 5, item 13).

Um bloco por critério de aceite do backend:

1. com o lote desligado, a fila não oferece a confirmação em lote e a rota
   recusa;
2. ligar exige a decisão "ligar a aprovação em lote" na pendência de
   recalibração e concordância de 90% ou mais nas últimas 4 semanas; abaixo
   disso, a rota recusa;
3. o lote só aceita casos D e E: um caso A, B ou C no pedido faz a rota recusar
   o pedido inteiro, sem gravar nada;
4. cada caso confirmado em lote ganha a própria linha de triagem e os próprios
   prazos;
5. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória da recalibração. Nenhum dado de pessoa real.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import (  # noqa: E402
    DIRETOR_EXECUTIVO,
    PRESIDENTE,
)
from test_seguranca_do_paciente_recalibracao import (  # noqa: E402
    _banco,
    _BancoDaRecalibracao,
    _com_o_marco_de_30,
    _decisao,
)
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    GRAVE,
    MODERADO,
    OBITO,
    QUASE_ERRO,
    _notificacao,
    _sugestao,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_recalibracao as recalibracao_router  # noqa: E402
from app.routers import seguranca_do_paciente_triagem as triagem_router  # noqa: E402

FILA = "/api/nsp/triagem"
LOTE = "/api/nsp/triagem/lote"
AGORA = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)
LIGADO = {"marco": 30, "devida_em": "2026-10-31", "pendencias": [], "decisao": "ligar_lote"}
DANO_LEVE = {"natureza": "evento_adverso", "grau_de_dano": "leve", "faixa": "D"}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _cliente(banco: _BancoDaRecalibracao, pessoa: dict[str, Any] = PRESIDENTE) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(triagem_router.router, prefix="/api")
    app.include_router(recalibracao_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _leves() -> tuple[list[dict], list[dict]]:
    """Um caso D sem dano, um D com dano leve e um E, todos com sugestão."""
    d_sem_dano, d_leve, e = _notificacao(11), _notificacao(12), _notificacao(13)
    return [d_sem_dano, d_leve, e], [_sugestao(d_sem_dano), _sugestao(d_leve, **DANO_LEVE), _sugestao(e, **QUASE_ERRO)]


def _decisoes(banco) -> list[dict]:
    return [t for t in banco.tabelas["nsp_triagens"] if t["autor_tipo"] == "pessoa"]


def _prazos(banco, caso: dict) -> list[dict]:
    return [p for p in banco.tabelas.get("nsp_prazos_do_caso", []) if p["notificacao_id"] == caso["id"]]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Desligado, a fila não oferece o lote e a rota recusa
# ═══════════════════════════════════════════════════════════════════════════


def test_a_aprovacao_em_lote_nasce_desligada_e_a_rota_recusa():
    casos, sugestoes = _leves()
    banco = _banco(casos, sugestoes)

    fila = _cliente(banco).get(FILA).json()
    resposta = _cliente(banco).post(LOTE, json={"ids": [c["id"] for c in casos]})

    assert fila["lote_ligado"] is False
    assert resposta.status_code == 422
    assert "desligada" in resposta.json()["detail"]
    assert _decisoes(banco) == []
    assert {n["estado"] for n in banco.notificacoes} == {"recebida"}


@pytest.mark.parametrize("decisao", ["manter", "ajustar"])
def test_outra_decisao_da_recalibracao_nao_liga_o_lote(decisao):
    banco = _banco(*_leves(), nsp_recalibracoes=[{**LIGADO, "decisao": decisao}])

    assert _cliente(banco).get(FILA).json()["lote_ligado"] is False


def test_a_fila_marca_so_os_casos_d_e_e_sem_conferencia_campo_a_campo():
    casos, sugestoes = _leves()
    c, morte, manual = _notificacao(14), _notificacao(15, relato="O paciente foi a óbito na troca."), _notificacao(16)
    banco = _banco(
        [*casos, c, morte, manual],
        [*sugestoes, _sugestao(c, **MODERADO), _sugestao(morte)],
        nsp_recalibracoes=[dict(LIGADO)],
    )

    corpo = _cliente(banco).get(FILA).json()

    assert corpo["lote_ligado"] is True
    assert {i["protocolo"]: i["cabe_no_lote"] for i in corpo["fila"]} == {
        "NSP-2026-0011": True,
        "NSP-2026-0012": True,
        "NSP-2026-0013": True,
        "NSP-2026-0014": False,
        "NSP-2026-0015": False,
        "NSP-2026-0016": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. Ligar exige a decisão e concordância de 90% ou mais em 4 semanas
# ═══════════════════════════════════════════════════════════════════════════


def _com_leves_confirmados(sem_ajuste: int, com_ajuste: int) -> _BancoDaRecalibracao:
    """O marco de 30 dias aberto e casos leves confirmados nas 4 semanas
    antes de AGORA, com e sem ajuste da Presidência."""
    banco = _com_o_marco_de_30()
    for n in range(sem_ajuste + com_ajuste):
        caso = _notificacao(20 + n, estado="classificada", criado_em=f"2026-10-{10 + n // 2:02d}T1{n % 2}:00:00+00:00")
        divergencias = [] if n < sem_ajuste else ["assunto"]
        banco.tabelas["nsp_notificacoes"].append(caso)
        banco.tabelas["nsp_triagens"] += [_sugestao(caso), _decisao(caso, divergencias)]
    return banco


def _ligar(banco, monkeypatch, pessoa=DIRETOR_EXECUTIVO):
    monkeypatch.setattr(recalibracao_router, "agora_utc", lambda: AGORA)
    return _cliente(banco, pessoa).post("/api/nsp/recalibracao/30", json={"decisao": "ligar_lote"})


def test_com_90_por_cento_de_concordancia_a_diretoria_liga_o_lote(monkeypatch):
    banco = _com_leves_confirmados(sem_ajuste=9, com_ajuste=1)

    resposta = _ligar(banco, monkeypatch)

    assert resposta.status_code == 200, resposta.text
    assert banco.recalibracoes[0]["decisao"] == "ligar_lote"
    assert _cliente(banco).get(FILA).json()["lote_ligado"] is True


@pytest.mark.parametrize(
    ("sem_ajuste", "com_ajuste"),
    [(8, 2), (26, 3), (0, 0)],
    ids=["80% de concordância", "89,7% que arredonda para 90", "nenhum caso leve nas 4 semanas"],
)
def test_abaixo_de_90_por_cento_a_rota_recusa_ligar(sem_ajuste, com_ajuste, monkeypatch):
    banco = _com_leves_confirmados(sem_ajuste, com_ajuste)

    resposta = _ligar(banco, monkeypatch)

    assert resposta.status_code == 422
    assert "90%" in resposta.json()["detail"]
    assert banco.recalibracoes[0]["decisao"] is None
    assert _cliente(banco).get(FILA).json()["lote_ligado"] is False


def test_caso_leve_de_mais_de_4_semanas_nao_conta_para_ligar(monkeypatch):
    banco = _com_leves_confirmados(sem_ajuste=0, com_ajuste=0)
    velho = _notificacao(40, estado="classificada", criado_em="2026-10-04T10:00:00+00:00")
    banco.tabelas["nsp_notificacoes"].append(velho)
    banco.tabelas["nsp_triagens"] += [_sugestao(velho), _decisao(velho, [])]

    assert _ligar(banco, monkeypatch).status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 3. Um caso A, B ou C no pedido recusa o pedido inteiro
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("grave", [OBITO, GRAVE, MODERADO], ids=["faixa A", "faixa B", "faixa C"])
def test_um_caso_a_b_ou_c_no_pedido_recusa_o_lote_inteiro(grave):
    casos, sugestoes = _leves()
    intruso = _notificacao(14)
    banco = _banco([*casos, intruso], [*sugestoes, _sugestao(intruso, **grave)], nsp_recalibracoes=[dict(LIGADO)])

    resposta = _cliente(banco).post(LOTE, json={"ids": [c["id"] for c in [*casos, intruso]]})

    assert resposta.status_code == 422
    assert "NSP-2026-0014" in resposta.json()["detail"]
    assert _decisoes(banco) == []
    assert banco.tabelas.get("nsp_prazos_do_caso", []) == []
    assert {n["estado"] for n in banco.notificacoes} == {"recebida"}


@pytest.mark.parametrize(
    ("caso", "sugestao"),
    [
        (_notificacao(14, relato="O paciente foi a óbito depois da troca do soro."), {}),
        (_notificacao(14), None),
    ],
    ids=["leve com menção a morte", "sem sugestão"],
)
def test_o_caso_que_pede_conferencia_ou_sem_sugestao_tambem_recusa_o_lote(caso, sugestao):
    casos, sugestoes = _leves()
    triagens = [*sugestoes] + ([] if sugestao is None else [_sugestao(caso, **sugestao)])
    banco = _banco([*casos, caso], triagens, nsp_recalibracoes=[dict(LIGADO)])

    resposta = _cliente(banco).post(LOTE, json={"ids": [c["id"] for c in [*casos, caso]]})

    assert resposta.status_code == 422
    assert _decisoes(banco) == []


def test_o_caso_ja_confirmado_recusa_o_lote_sem_gravar_os_outros():
    casos, sugestoes = _leves()
    banco = _banco(casos, sugestoes, nsp_recalibracoes=[dict(LIGADO)])
    # O confirmado vem por último: sem a checagem antes de gravar, os dois
    # primeiros seriam confirmados antes do 409.
    confirmado = next(n for n in banco.notificacoes if n["id"] == casos[-1]["id"])
    confirmado["estado"] = "classificada"

    resposta = _cliente(banco).post(LOTE, json={"ids": [c["id"] for c in casos]})

    assert resposta.status_code == 409
    assert "NSP-2026-0013" in resposta.json()["detail"]
    assert _decisoes(banco) == []
    assert banco.tabelas.get("nsp_prazos_do_caso", []) == []
    assert [n["estado"] for n in banco.notificacoes if n["id"] != confirmado["id"]] == ["recebida", "recebida"]


def test_o_lote_vazio_e_recusado():
    banco = _banco(*_leves(), nsp_recalibracoes=[dict(LIGADO)])

    assert _cliente(banco).post(LOTE, json={"ids": []}).status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 4. Cada caso ganha a própria linha de triagem e os próprios prazos
# ═══════════════════════════════════════════════════════════════════════════


def test_cada_caso_do_lote_ganha_a_propria_linha_de_triagem_e_os_proprios_prazos():
    casos, sugestoes = _leves()
    banco = _banco(casos, sugestoes, nsp_recalibracoes=[dict(LIGADO)])

    resposta = _cliente(banco).post(LOTE, json={"ids": [c["id"] for c in casos]})

    assert resposta.status_code == 201, resposta.text
    assert [(c["id"], c["estado"]) for c in resposta.json()["confirmados"]] == [
        (casos[0]["id"], "em_analise_agregada"),
        (casos[1]["id"], "classificada"),
        (casos[2]["id"], "em_analise_agregada"),
    ]
    decisoes = {d["notificacao_id"]: d for d in _decisoes(banco)}
    assert set(decisoes) == {c["id"] for c in casos}
    for caso, sugestao in zip(casos, sugestoes, strict=True):
        decisao = decisoes[caso["id"]]
        assert (decisao["autor_id"], decisao["divergencias"]) == ("P1", [])
        assert (decisao["faixa"], decisao["grau_de_dano"]) == (sugestao["faixa"], sugestao["grau_de_dano"])
        assert _prazos(banco, caso), caso["protocolo"]
    assert [n["estado"] for n in banco.notificacoes] == ["em_analise_agregada", "classificada", "em_analise_agregada"]
    assert len([t for t in banco.tabelas["nsp_triagens"] if t["autor_tipo"] == "agente"]) == 3


def test_so_a_presidencia_e_o_acesso_pleno_confirmam_em_lote():
    from test_seguranca_do_paciente_notificacoes import MEMBRO

    casos, sugestoes = _leves()
    banco = _banco(casos, sugestoes, nsp_recalibracoes=[dict(LIGADO)])

    assert _cliente(banco, MEMBRO).post(LOTE, json={"ids": [casos[0]["id"]]}).status_code == 403
    assert _decisoes(banco) == []


# ═══════════════════════════════════════════════════════════════════════════
# 5. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_diz_como_a_aprovacao_em_lote_liga_e_o_que_ela_aceita():
    from test_kit_conhecimento import _secao, _texto

    no_ar = _secao(_texto("seguranca-do-paciente.md"), "O que já está no ar")
    for termo in (
        "**Confirmar em lote**",
        "concordância de 90% ou mais nas últimas 4 semanas",
        "só casos das faixas D e E",
        "cada caso ganha a própria triagem e os próprios prazos",
    ):
        assert termo in no_ar, termo
    assert "a aprovação em lote em si continua desligada" not in no_ar
