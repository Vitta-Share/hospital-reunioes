"""Encaminhar da tela de triagem (issue #1995, PRD #1979, ADR 0095 decisão 11
e ADR 0107 decisão 8).

Um bloco por critério de aceite:

1. encaminhar exige ao menos um destino e o motivo; o protocolo não muda;
2. o destino Ouvidoria registra o e-mail ao ouvidor com protocolo, motivo e
   relato;
3. o destino Canal de Conduta não envia nem grava conteúdo fora do Núcleo;
4. fora de escopo leva o caso a Fora de escopo, e a orientação aparece no
   acompanhamento;
5. Núcleo e Ouvidoria juntos mantêm o caso na triagem e registram o e-mail;
6. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória da triagem. Nenhum dado de pessoa real.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import _cliente as _cliente_publico  # noqa: E402
from test_seguranca_do_paciente_notificacoes import _pessoa  # noqa: E402
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    MEMBRO,
    PRESIDENTE,
    _banco,
    _cliente,
    _notificacao,
    _secao_do_kit,
    _sugestao,
)

from app.services.seguranca_do_paciente import encaminhamento  # noqa: E402

OUVIDOR = _pessoa("P7", perfil_ouvidoria="ouvidor")
OUVIDOR_DESLIGADO = _pessoa("P8", perfil_ouvidoria="ouvidor", ativo=False)
DIRETORIA_DA_OUVIDORIA = _pessoa("P9", perfil_ouvidoria="diretoria_executiva")
MOTIVO = "Reclamação de atendimento na recepção, sem incidente com o paciente."
RELATO = "A recepção demorou duas horas para chamar a paciente e ninguém explicou o motivo."


def _cenario(**campos) -> tuple[Any, dict]:
    caso = _notificacao(1, relato=RELATO, **campos)
    banco = _banco([caso], [_sugestao(caso)])
    banco.tabelas["participantes"] += [dict(OUVIDOR), dict(OUVIDOR_DESLIGADO), dict(DIRETORIA_DA_OUVIDORIA)]
    return banco, caso


def _encaminhar(banco, caso, pessoa=PRESIDENTE, **corpo):
    return _cliente(banco, pessoa).post(f"/api/nsp/triagem/{caso['id']}/encaminhamento", json=corpo)


def _escritas_fora_do_nucleo(banco) -> list[str]:
    """O que foi gravado em tabela que não é do Núcleo, nem o registro de
    e-mail do Núcleo."""
    return [nome for nome, _ in banco.escritas if not nome.startswith("nsp_")]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Destino e motivo obrigatórios; o protocolo não muda
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "corpo",
    [
        {"destinos": [], "motivo": MOTIVO},
        {"destinos": ["ouvidoria"], "motivo": "   "},
        {"destinos": ["ouvidoria"]},
        {"destinos": ["vigilancia"], "motivo": MOTIVO},
    ],
    ids=["sem destino", "motivo em branco", "sem motivo", "destino fora da lista"],
)
def test_encaminhar_sem_destino_ou_sem_motivo_e_recusado_sem_gravar(corpo):
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, **corpo)

    assert resposta.status_code == 422, resposta.text
    assert banco.tabelas.get("nsp_encaminhamentos", []) == []
    assert banco.tabelas.get("nsp_avisos", []) == []
    assert banco.notificacoes[0]["estado"] == "recebida"


def test_encaminhar_grava_o_destino_e_o_motivo_e_o_protocolo_nao_muda():
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, destinos=["canal_de_conduta"], motivo=MOTIVO)

    assert resposta.status_code == 201, resposta.text
    [encaminhamento] = banco.tabelas["nsp_encaminhamentos"]
    assert encaminhamento["notificacao_id"] == caso["id"]
    assert encaminhamento["destinos"] == ["canal_de_conduta"]
    assert encaminhamento["motivo"] == MOTIVO
    assert encaminhamento["autor_id"] == "P1"
    assert banco.notificacoes[0]["protocolo"] == "NSP-2026-0001"
    assert banco.notificacoes[0]["estado"] == "encaminhada"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Ouvidoria: o e-mail ao ouvidor, no registro de e-mail do Núcleo
# ═══════════════════════════════════════════════════════════════════════════


def test_encaminhar_a_ouvidoria_registra_o_email_ao_ouvidor_com_protocolo_motivo_e_relato():
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, destinos=["ouvidoria"], motivo=MOTIVO)

    assert resposta.status_code == 201, resposta.text
    [email] = banco.tabelas["nsp_avisos"]
    assert email["destinatario_id"] == "P7"
    assert email["caso_id"] == caso["id"]
    assert email["marco"] == "encaminhamento_ouvidoria"
    assert email["situacao"] == "pendente"
    assert "NSP-2026-0001" in email["assunto"]
    for parte in ("NSP-2026-0001", MOTIVO, RELATO):
        assert parte in email["texto"], parte
        assert any(parte in p for p in email["contexto"]["paragrafos"]), parte
    assert banco.notificacoes[0]["estado"] == "encaminhada"


def test_sem_ouvidor_ativo_a_ouvidoria_e_recusada_sem_gravar():
    banco, caso = _cenario()
    banco.tabelas["participantes"] = [p for p in banco.tabelas["participantes"] if p["id"] != "P7"]

    resposta = _encaminhar(banco, caso, destinos=["ouvidoria"], motivo=MOTIVO)

    assert resposta.status_code == 422
    assert "ouvidor" in resposta.json()["detail"]
    assert banco.tabelas.get("nsp_encaminhamentos", []) == []
    assert banco.tabelas.get("nsp_avisos", []) == []
    assert banco.notificacoes[0]["estado"] == "recebida"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Canal de Conduta: só a orientação na tela
# ═══════════════════════════════════════════════════════════════════════════


def test_canal_de_conduta_so_orienta_e_nada_sai_nem_e_gravado_fora_do_nucleo():
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, destinos=["canal_de_conduta"], motivo=MOTIVO)

    assert resposta.status_code == 201, resposta.text
    orientacao = resposta.json()["orientacao_do_canal_de_conduta"]
    assert "Canal de Conduta" in orientacao
    assert not re.search(r"https?://|www\.|/conduta", orientacao)
    assert banco.tabelas.get("nsp_avisos", []) == []
    assert _escritas_fora_do_nucleo(banco) == []
    [gravado] = [valores for nome, valores in banco.escritas if nome == "nsp_encaminhamentos"]
    assert RELATO not in str(gravado)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Fora de escopo: encerra, e a orientação aparece no acompanhamento
# ═══════════════════════════════════════════════════════════════════════════

ORIENTACAO = "Este assunto é trabalhista: procure o Departamento Pessoal do hospital."
ACOMPANHAMENTO = {"protocolo": "NSP-2026-0001", "contato": "notificante@hsm.test"}


def test_fora_de_escopo_encerra_e_a_orientacao_aparece_no_acompanhamento():
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, destinos=["fora_de_escopo"], motivo=MOTIVO, orientacao=ORIENTACAO)

    assert resposta.status_code == 201, resposta.text
    assert banco.notificacoes[0]["estado"] == "fora_de_escopo"
    assert banco.notificacoes[0]["protocolo"] == "NSP-2026-0001"
    acompanhamento = _cliente_publico(banco).post("/api/nsp/publico/acompanhamento", json=ACOMPANHAMENTO)
    assert acompanhamento.status_code == 200, acompanhamento.text
    assert acompanhamento.json()["estado"] == "Concluída"
    assert acompanhamento.json()["orientacao"] == ORIENTACAO
    assert MOTIVO not in acompanhamento.text


def test_o_caso_que_segue_no_nucleo_nao_mostra_orientacao_no_acompanhamento():
    banco, _ = _cenario()

    acompanhamento = _cliente_publico(banco).post("/api/nsp/publico/acompanhamento", json=ACOMPANHAMENTO)

    assert acompanhamento.status_code == 200, acompanhamento.text
    assert acompanhamento.json().get("orientacao") is None


@pytest.mark.parametrize(
    "corpo",
    [
        {"destinos": ["fora_de_escopo"], "motivo": MOTIVO},
        {"destinos": ["fora_de_escopo", "ouvidoria"], "motivo": MOTIVO, "orientacao": ORIENTACAO},
        {"destinos": ["fora_de_escopo", "nucleo"], "motivo": MOTIVO, "orientacao": ORIENTACAO},
    ],
    ids=["sem orientação", "junto da Ouvidoria", "junto do Núcleo"],
)
def test_fora_de_escopo_pede_a_orientacao_e_nao_se_soma_a_outro_destino(corpo):
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, **corpo)

    assert resposta.status_code == 422, resposta.text
    assert banco.tabelas.get("nsp_encaminhamentos", []) == []
    assert banco.notificacoes[0]["estado"] == "recebida"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Núcleo e Ouvidoria juntos: o caso fica na triagem do Núcleo
# ═══════════════════════════════════════════════════════════════════════════


def test_nucleo_e_ouvidoria_juntos_mantem_o_caso_na_triagem_e_registram_o_email():
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, destinos=["nucleo", "ouvidoria"], motivo=MOTIVO)

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["estado"] == "recebida"
    assert banco.notificacoes[0]["estado"] == "recebida"
    assert [c["protocolo"] for c in _cliente(banco).get("/api/nsp/triagem").json()["fila"]] == ["NSP-2026-0001"]
    [email] = banco.tabelas["nsp_avisos"]
    assert email["destinatario_id"] == "P7"
    assert MOTIVO in email["texto"]
    tela = _cliente(banco).get(f"/api/nsp/triagem/{caso['id']}").json()
    assert [e["destinos"] for e in tela["encaminhamentos"]] == [["nucleo", "ouvidoria"]]


def test_o_caso_que_ja_saiu_da_triagem_nao_se_encaminha():
    banco, caso = _cenario(estado="classificada")

    resposta = _encaminhar(banco, caso, destinos=["ouvidoria"], motivo=MOTIVO)

    assert resposta.status_code == 409
    assert banco.tabelas.get("nsp_avisos", []) == []


def test_so_a_presidencia_e_o_acesso_pleno_encaminham():
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, pessoa=MEMBRO, destinos=["ouvidoria"], motivo=MOTIVO)

    assert resposta.status_code == 403
    assert banco.tabelas.get("nsp_encaminhamentos", []) == []


# ═══════════════════════════════════════════════════════════════════════════
# 6. O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_diz_como_a_presidencia_encaminha():
    no_ar = _secao_do_kit("O que já está no ar")
    for termo in (
        "**Encaminhar**",
        "o protocolo continua o mesmo",
        "e-mail ao ouvidor com o protocolo, o motivo e o relato",
        "Canal de Conduta, nada é enviado",
        "Fora de escopo encerra o caso",
        "página de acompanhamento",
        "continua na fila de triagem",
    ):
        assert termo in no_ar, termo
    assert "encaminhamento a outro canal" not in _secao_do_kit("O que ele ainda não faz")


# ═══════════════════════════════════════════════════════════════════════════
# A migration 205, lida como texto (a prova no Postgres está no PR)
# ═══════════════════════════════════════════════════════════════════════════

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "205_nsp_encaminhamento.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def test_a_migration_aceita_os_destinos_do_app_e_o_marco_do_email_ao_ouvidor():
    sql = _sql()
    [lista] = re.findall(r"destinos <@ ARRAY\[([^\]]+)\]", sql)
    assert sorted(re.findall(r"'(\w+)'", lista)) == sorted(encaminhamento.DESTINOS)
    assert f"''{encaminhamento.MARCO_DA_OUVIDORIA}''" in sql


def test_a_tabela_nova_nasce_com_rls_sem_politica_e_o_recibo_e_o_205():
    sql = _sql()
    for tabela in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql):
        assert f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;" in sql, tabela
    assert "VALUES (205) ON CONFLICT" in sql
    assert "CREATE POLICY" not in sql.upper()
