"""As Definições de processo do setor (ADR 0098, decisão 9; issue #1875).

No envio da Ata, a linha do tipo Processo entra na lista do setor da Reunião,
com o trecho da Ata copiado. Cuidam da lista os Facilitadores das Reuniões do
setor, até o organograma; o Super admin vê todas e a Secretária não vê. Tiram
um item o Facilitador da Reunião de onde ele saiu e o Super admin, sempre com
anotação: o item sai da lista e fica registrado.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# O `make_client` importado registra a fábrica de TestClient do envio aqui.
from test_pendencia_nasce_no_envio import _sb, make_client  # noqa: E402, F401


@pytest.fixture
def cliente(request):
    return request.getfixturevalue("make_client")


def _sem_clicksign(monkeypatch):
    from app.services import clicksign_service

    monkeypatch.setattr(clicksign_service, "start_signature_flow", lambda *_a, **_kw: None)


QUADRO = [
    {"acao": "Comprar insumos", "responsavel": "Pedro Rezende", "prazo": "2026-12-10", "tipo": "ACAO"},
    {
        "acao": "Toda alta passa pelo checklist de medicação",
        "responsavel": None,
        "objetivo_meta": "Evitar erro de dose na alta",
        "tipo": "PROCESSO",
    },
    {"acao": "Ligar para o fornecedor", "responsavel": "Ana Lima"},
]


def _sb_com_quadro():
    sb = _sb(setor_id="S-ENF")
    sb.reunioes[0]["json_ata"] = {"quadro_atribuicoes": [dict(a) for a in QUADRO]}
    return sb


# ─── 1. O item nasce no envio da Ata ─────────────────────────────────────────


@pytest.mark.parametrize("rota", ["aprovar", "aprovar-sem-assinatura"])
def test_enviar_ata_com_linha_de_processo_cria_o_item_com_o_trecho_copiado(cliente, monkeypatch, rota):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro()

    r = cliente(sb).post(f"/api/reunioes/R1/{rota}")

    assert r.status_code == 200, r.text
    [item] = sb.definicoes_processo
    assert (item["id_reuniao"], item["quadro_pos"], item["trecho"], item["objetivo"], item["status"]) == (
        "R1",
        1,
        "Toda alta passa pelo checklist de medicação",
        "Evitar erro de dose na alta",
        "ATIVA",
    )
    # O Processo não vira Pendência (#1872).
    assert sorted(p["quadro_pos"] for p in sb.pendencias) == [0, 2]


def test_reenviar_nao_repete_o_item(cliente, monkeypatch):
    from app.services import pendencia_service

    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro()
    assert cliente(sb).post("/api/reunioes/R1/aprovar").status_code == 200

    pendencia_service.liberar_pendencias(sb, "R1", origem="RECONCILIACAO")

    assert len(sb.definicoes_processo) == 1
