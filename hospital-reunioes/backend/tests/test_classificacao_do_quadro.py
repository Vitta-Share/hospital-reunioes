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

# O `make_client` importado registra a fábrica de TestClient do envio aqui.
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


@pytest.fixture
def cliente(request):
    return request.getfixturevalue("make_client")


# ─── 2. O envio: Rotina incompleta trava, e só Ação vira Pendência ───────────


def _sb_com_quadro(quadro: list[dict]):
    sb = _sb()
    sb.reunioes[0]["json_ata"] = {"quadro_atribuicoes": quadro}
    return sb


def _sem_clicksign(monkeypatch):
    from app.services import clicksign_service

    monkeypatch.setattr(clicksign_service, "start_signature_flow", lambda *_a, **_kw: None)


QUADRO_CLASSIFICADO = [
    {"acao": "Comprar insumos", "responsavel": "Pedro Rezende", "prazo": "2026-12-10", "tipo": "ACAO"},
    {"acao": "Reunir a equipe", "responsavel": "Ana Lima", "tipo": "ROTINA", "frequencia": "SEMANAL"},
    {"acao": "Toda alta passa pelo checklist", "responsavel": None, "tipo": "PROCESSO", "frequencia": None},
    {"acao": "Ligar para o fornecedor", "responsavel": "Ana Lima"},
]


@pytest.mark.parametrize("rota", ["aprovar", "aprovar-sem-assinatura"])
def test_no_envio_rotina_e_processo_nao_viram_pendencia(cliente, monkeypatch, rota):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([dict(a) for a in QUADRO_CLASSIFICADO])

    r = cliente(sb).post(f"/api/reunioes/R1/{rota}")

    assert r.status_code == 200, r.text
    assert r.json()["total_pendencias"] == 2
    assert sorted((p["quadro_pos"], p["descricao_acao"]) for p in sb.pendencias) == [
        (0, "Comprar insumos"),
        (3, "Ligar para o fornecedor"),
    ]


def test_pendencias_criadas_de_y_conta_so_as_acoes(cliente, monkeypatch):
    from app.services import aceite_service

    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([dict(a) for a in QUADRO_CLASSIFICADO])
    assert cliente(sb).post("/api/reunioes/R1/aprovar").status_code == 200
    for p in sb.pendencias:
        p.setdefault("deleted_at", None)

    assert aceite_service.progresso_pendencias(sb, "R1") == {"pendencias_criadas": 2, "total_acoes": 2}


@pytest.mark.parametrize("rota", ["aprovar", "aprovar-sem-assinatura"])
@pytest.mark.parametrize(
    ("rotina", "falta"),
    [
        ({"acao": "Reunir a equipe", "responsavel": "", "tipo": "ROTINA", "frequencia": "SEMANAL"}, "sem responsável"),
        (
            {"acao": "Reunir a equipe", "responsavel": "Ana Lima", "tipo": "ROTINA", "frequencia": None},
            "sem frequência",
        ),
    ],
)
def test_enviar_ata_com_rotina_incompleta_e_recusado(cliente, monkeypatch, rota, rotina, falta):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro([{"acao": "Comprar insumos", "responsavel": "Pedro Rezende"}, rotina])

    r = cliente(sb).post(f"/api/reunioes/R1/{rota}")

    assert r.status_code == 422, r.text
    detalhe = r.json()["detail"]
    assert "Rotina" in detalhe
    assert f'linha 2 ("Reunir a equipe") {falta}' in detalhe
    assert sb.reunioes[0]["status_ata"] == "AGUARDANDO_VALIDACAO"
    assert sb.pendencias == []


# ─── 3. A validação troca tipo e frequência de cada linha ────────────────────


def test_facilitador_troca_tipo_e_frequencia_na_validacao_sem_mexer_no_responsavel(cliente):
    sb = _sb_com_quadro(
        [{"acao": "Reunir a equipe", "responsavel": "Ana Lima", "responsavel_id": "P2", "cargo": "Coordenadora"}]
    )
    client = cliente(sb)

    r = client.patch("/api/reunioes/R1/quadro-atribuicoes/0", json={"tipo": "ROTINA", "frequencia": "QUINZENAL"})

    assert r.status_code == 200, r.text
    item = sb.reunioes[0]["json_ata"]["quadro_atribuicoes"][0]
    assert (item["tipo"], item["frequencia"]) == ("ROTINA", "QUINZENAL")
    assert (item["responsavel"], item["responsavel_id"], item["cargo"]) == ("Ana Lima", "P2", "Coordenadora")

    r = client.patch("/api/reunioes/R1/quadro-atribuicoes/0", json={"tipo": "PROCESSO"})

    assert r.status_code == 200, r.text
    item = sb.reunioes[0]["json_ata"]["quadro_atribuicoes"][0]
    assert (item["tipo"], item["frequencia"]) == ("PROCESSO", None)


def test_tipo_ou_frequencia_fora_da_lista_e_recusado(cliente):
    sb = _sb_com_quadro([{"acao": "Reunir a equipe", "responsavel": "Ana Lima"}])
    client = cliente(sb)

    assert client.patch("/api/reunioes/R1/quadro-atribuicoes/0", json={"tipo": "META"}).status_code == 422
    assert client.patch("/api/reunioes/R1/quadro-atribuicoes/0", json={"frequencia": "ANUAL"}).status_code == 422
    assert "tipo" not in sb.reunioes[0]["json_ata"]["quadro_atribuicoes"][0]
