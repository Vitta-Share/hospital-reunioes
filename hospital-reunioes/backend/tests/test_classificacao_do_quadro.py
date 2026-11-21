"""Ação, Rotina e Processo no quadro da Ata (issue #1872; ADR 0098, decisão 9).

Cada linha do quadro ganha `tipo` (ACAO, ROTINA ou PROCESSO) e, na Rotina,
`frequencia` (SEMANAL, QUINZENAL ou MENSAL). A IA sugere nos três prompts de
geração, o Facilitador ajusta na validação, e linha sem tipo vale como Ação.
O envio recusa Rotina sem responsável ou sem frequência, e só Ação vira
Pendência.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_pendencia_nasce_no_envio import _sb, make_client  # noqa: E402, F401

from app.services import ai_processor  # noqa: E402
from app.services.prompt_loader import load_prompt  # noqa: E402

# ─── 1. Os três prompts e o parser ───────────────────────────────────────────


@pytest.mark.parametrize("prompt", ["extracao_ata", "correcao_ata", "chat_ata_guiada_system"])
def test_os_tres_prompts_pedem_tipo_e_frequencia(prompt):
    texto = load_prompt(prompt)
    assert '"tipo"' in texto
    assert '"frequencia"' in texto
    for valor in ("ACAO", "ROTINA", "PROCESSO", "SEMANAL", "QUINZENAL", "MENSAL"):
        assert valor in texto, f"{prompt} não cita {valor}"


QUADRO_DA_IA = [
    {"acao": "Comprar insumos", "responsavel": "Ana", "prazo": "2026-12-10"},
    {"acao": "Encontro da equipe", "responsavel": "Ana", "tipo": "rotina", "frequencia": "semanal"},
    {"acao": "Toda alta passa pelo checklist", "tipo": "PROCESSO", "frequencia": "MENSAL"},
    {"acao": "Coisa estranha", "tipo": "META", "frequencia": "anual"},
]

CLASSIFICACAO_ESPERADA = [
    ("ACAO", None),
    ("ROTINA", "SEMANAL"),
    ("PROCESSO", None),
    ("ACAO", None),
]


@pytest.fixture
def ia_de_mentira(monkeypatch):
    def _responder(resposta: dict):
        monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "anthropic")
        monkeypatch.setattr(ai_processor, "_get_llm", lambda: (None, "modelo"))
        monkeypatch.setattr(ai_processor, "_pedir_json", lambda *_a, **_kw: json.dumps(resposta))

    return _responder


def _classificacao(quadro: list[dict]) -> list[tuple]:
    return [(item["tipo"], item["frequencia"]) for item in quadro]


def test_a_ata_por_transcricao_classifica_cada_linha_e_sem_tipo_vale_acao(ia_de_mentira):
    ia_de_mentira({"quadro_atribuicoes": [dict(a) for a in QUADRO_DA_IA]})

    ata = ai_processor.process_transcricao("transcrição", "R1")

    assert _classificacao(ata["quadro_atribuicoes"]) == CLASSIFICACAO_ESPERADA


def test_a_correcao_classifica_cada_linha_e_sem_tipo_vale_acao(ia_de_mentira):
    ia_de_mentira({"quadro_atribuicoes": [dict(a) for a in QUADRO_DA_IA]})

    ata = ai_processor.process_correcao("transcrição", {"quadro_atribuicoes": []}, "corrige", "R1")

    assert _classificacao(ata["quadro_atribuicoes"]) == CLASSIFICACAO_ESPERADA


def test_a_ata_guiada_classifica_cada_linha_e_sem_tipo_vale_acao(ia_de_mentira):
    ia_de_mentira(
        {"reply": "ok", "rascunho": {"resumo_executivo": "r", "quadro_atribuicoes": [dict(a) for a in QUADRO_DA_IA]}}
    )

    saida = ai_processor.chat_ata_guiada({}, [{"role": "user", "content": "oi"}])

    assert _classificacao(saida["rascunho"]["quadro_atribuicoes"]) == CLASSIFICACAO_ESPERADA
