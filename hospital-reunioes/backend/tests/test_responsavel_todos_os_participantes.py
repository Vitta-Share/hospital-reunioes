"""Issue #2327: a linha do quadro com responsável "Todos os participantes".

O quadro mostrava "Todos os participantes", que é o certo, mas a Resolução não
casava esse texto com ninguém: nascia uma Pendência só, sem vínculo, e nenhum
Participante era cobrado. Agora a Ação (e a Rotina) dirigida a todos nasce uma
para cada Participante da Reunião, com o vínculo de cada um.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

# O `make_client` importado registra a fábrica de TestClient do envio aqui.
from test_pendencia_nasce_no_envio import _sb, make_client  # noqa: E402, F401

from app.services import aceite_service, pendencia_service  # noqa: E402


@pytest.fixture
def cliente(request):
    return request.getfixturevalue("make_client")


def _sem_clicksign(monkeypatch):
    from app.services import clicksign_service

    monkeypatch.setattr(clicksign_service, "start_signature_flow", lambda *_a, **_kw: None)


def _sb_com_quadro(quadro: list[dict]):
    sb = _sb()
    sb.reunioes[0]["json_ata"] = {"quadro_atribuicoes": quadro}
    return sb


ZERAR = {
    "acao": "Zerar as pendências na plataforma",
    "responsavel": "Todos os participantes",
    "prazo": "11/12/2026",
    "tipo": "ACAO",
}


@pytest.mark.parametrize("rota", ["aprovar", "aprovar-sem-assinatura"])
def test_acao_para_todos_os_participantes_nasce_uma_pendencia_para_cada_um(cliente, monkeypatch, rota):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([dict(ZERAR)])

    r = cliente(sb).post(f"/api/reunioes/R1/{rota}")

    assert r.status_code == 200, r.text
    assert r.json()["total_pendencias"] == 2
    assert sorted((p["quadro_pos"], p["responsavel_id"], p["responsavel_nome"]) for p in sb.pendencias) == [
        (0, "P1", "Pedro Rezende"),
        (0, "P2", "Ana Lima"),
    ]
    assert {p["descricao_acao"] for p in sb.pendencias} == {"Zerar as pendências na plataforma"}
    assert {p["prazo"] for p in sb.pendencias} == {"2026-12-11"}


PONTO = {
    "acao": "Tratar o ponto da equipe no RHID",
    "responsavel": "Todos os participantes",
    "tipo": "ROTINA",
    "frequencia": "SEMANAL",
}


def test_rotina_para_todos_os_participantes_nasce_uma_rotina_para_cada_um(cliente, monkeypatch):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([dict(ZERAR), dict(PONTO)])

    r = cliente(sb).post("/api/reunioes/R1/aprovar-sem-assinatura")

    assert r.status_code == 200, r.text
    assert sorted((ro["quadro_pos"], ro["responsavel_id"], ro["responsavel_nome"]) for ro in sb.rotinas) == [
        (1, "P1", "Pedro Rezende"),
        (1, "P2", "Ana Lima"),
    ]
    assert {ro["frequencia"] for ro in sb.rotinas} == {"SEMANAL"}


def test_liberar_de_novo_nao_duplica_a_pendencia_de_ninguem(cliente, monkeypatch):
    """A reconciliação das 5h30 e o Reenviar chamam a liberação de novo."""
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([dict(ZERAR), dict(PONTO)])
    assert cliente(sb).post("/api/reunioes/R1/aprovar").status_code == 200

    assert pendencia_service.liberar_pendencias(sb, "R1", origem="RECONCILIACAO") == 0

    assert len(sb.pendencias) == 2
    assert len(sb.rotinas) == 2


def test_linha_comum_ja_nascida_nao_ganha_outra_quando_a_resolucao_muda(cliente, monkeypatch):
    """A linha de uma pessoa só segue uma por posição: se o nome que nasceu sem
    vínculo passa a casar com alguém do cadastro, a reconciliação não cria uma
    segunda Pendência para a mesma linha."""
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([{"acao": "Ligar para o fornecedor", "responsavel": "Carla Souza", "tipo": "ACAO"}])
    assert cliente(sb).post("/api/reunioes/R1/aprovar").status_code == 200
    assert sb.pendencias[0]["responsavel_id"] is None

    sb.participantes.append({"id": "P3", "nome_completo": "Carla Souza", "cargo": "Compras", "ativo": True})
    assert pendencia_service.liberar_pendencias(sb, "R1", origem="RECONCILIACAO") == 0

    assert len(sb.pendencias) == 1


@pytest.mark.parametrize(
    ("responsavel", "e_todos"),
    [
        ("Todos os participantes", True),
        ("TODOS OS PARTICIPANTES.", True),
        ("todos os presentes", True),
        ("Todas as participantes", True),
        ("Todos", True),
        ("Todos os participantes da reunião", True),
        ("Ana Lima", False),
        ("Todos os gestores", False),
        ("Pedro e Ana", False),
        ("", False),
        (None, False),
    ],
)
def test_o_quadro_reconhece_quando_o_responsavel_e_todo_mundo_da_reuniao(responsavel, e_todos):
    from app.services.resolucao_service import e_responsavel_coletivo

    assert e_responsavel_coletivo(responsavel) is e_todos


def test_linha_de_todos_sem_ninguem_no_roster_fica_como_estava(cliente, monkeypatch):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([dict(ZERAR)])
    sb.reuniao_participantes.clear()

    assert cliente(sb).post("/api/reunioes/R1/aprovar-sem-assinatura").status_code == 200

    assert [(p["responsavel_id"], p["responsavel_nome"]) for p in sb.pendencias] == [(None, "Todos os participantes")]


def test_pendencias_criadas_de_y_conta_uma_por_participante_na_linha_de_todos(cliente, monkeypatch):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([dict(ZERAR), dict(PONTO), {"acao": "Comprar insumos", "responsavel": "Ana Lima"}])
    assert cliente(sb).post("/api/reunioes/R1/aprovar").status_code == 200
    for p in sb.pendencias:
        p.setdefault("deleted_at", None)

    assert aceite_service.progresso_pendencias(sb, "R1") == {"pendencias_criadas": 3, "total_acoes": 3}
