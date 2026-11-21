"""O alerta imediato de caso grave e a confirmação de recebimento (issue #1989, PRD #1979).

O que a issue promete, um bloco por critério de aceite:

1. "grave ou houve morte = Sim" registra o alerta à Presidência, ao suplente
   vigente, a quem tem Acesso pleno e à Diretoria, urgente, ainda dentro do
   envio (antes de qualquer triagem do agente), de madrugada e no fim de semana;
2. o e-mail leva protocolo, setor e link, e nunca o relato;
3. o início do módulo destaca o caso grave;
4. quem se identificou com e-mail recebe a confirmação com o protocolo; o
   anônimo e quem deixou só telefone não geram e-mail;
5. sem travessão no e-mail.

O banco é o dublê em memória dos testes da notificação, e o provedor de e-mail
é sempre dublado. As pessoas são de teste.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import (  # noqa: E402
    ANONIMO,
    DIRETOR,
    DIRETOR_EXECUTIVO,
    IDENTIFICADO,
    MEMBRO,
    NUCLEO,
    PELO_MODULO,
    PRESIDENTE,
    PUBLICO,
    RELATO,
    SETOR,
    SO_REUNIOES,
    SUPER_ADMIN,
    _Banco,
    _cliente,
    _participacao,
    _pessoa,
)

from app.limiter import limiter  # noqa: E402
from app.services.seguranca_do_paciente import caso_grave, emails  # noqa: E402

SP = ZoneInfo("America/Sao_Paulo")
# Sábado, três da manhã: fora de qualquer expediente.
SABADO_3H = datetime(2026, 11, 14, 3, 0, tzinfo=SP)

SUPLENTE = _pessoa("P7")
DIRETORIA_EXECUTIVA = _pessoa("P8", perfil_ouvidoria="diretoria_executiva")
GRAVE = {**RELATO, "chegou_ao_paciente": "com_dano", "grave_ou_morte": True}
RELATO_GRAVE = GRAVE["relato"]


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _madrugada_de_sabado(monkeypatch):
    monkeypatch.setattr(caso_grave, "_agora", lambda: SABADO_3H)


@pytest.fixture
def enviados(monkeypatch) -> list[dict[str, str]]:
    """O provedor de e-mail dublado: anota cada envio."""
    caixa: list[dict[str, str]] = []

    def _enviar(destino, assunto, html, texto):
        caixa.append({"para": destino, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(emails, "_enviar_email", _enviar)
    return caixa


def _banco() -> _Banco:
    pessoas = (PRESIDENTE, MEMBRO, SO_REUNIOES, SUPER_ADMIN, DIRETOR_EXECUTIVO, DIRETOR, SUPLENTE, DIRETORIA_EXECUTIVA)
    return _Banco(
        {
            "participantes": [dict(p) for p in pessoas],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [
                _participacao("P1", "presidencia"),
                _participacao("P2", "membro"),
                _participacao("P7", "suplente"),
            ],
            "setores": [dict(SETOR)],
            "nsp_notificacoes": [],
        }
    )


def _avisos(banco: _Banco, marco: str) -> list[dict[str, Any]]:
    return [a for a in banco.tabelas.get("nsp_avisos", []) if a["marco"] == marco]


# ═══════════════════════════════════════════════════════════════════════════
# 1. O alerta a todos os destinatários, na hora
# ═══════════════════════════════════════════════════════════════════════════


def test_caso_grave_alerta_presidencia_suplente_acesso_pleno_e_diretoria_na_madrugada_de_sabado(enviados):
    banco = _banco()

    resposta = _cliente(banco).post(PUBLICO, json={**ANONIMO, **GRAVE, "anonimo": True, "origem": "qr"})

    assert resposta.status_code == 201, resposta.text
    [caso] = banco.notificacoes
    alertas = _avisos(banco, caso_grave.MARCO_DO_ALERTA)
    assert sorted(a["destinatario_id"] for a in alertas) == ["P1", "P5", "P7", "P8"]
    for alerta in alertas:
        assert alerta["caso_id"] == caso["id"]
        assert alerta["urgente"] is True
        assert datetime.fromisoformat(alerta["enviar_a_partir_de"]) == SABADO_3H
        assert alerta["situacao"] == emails.ENVIADO
    assert sorted(e["para"] for e in enviados) == ["p1@hsm.test", "p5@hsm.test", "p7@hsm.test", "p8@hsm.test"]


def test_o_alerta_fica_registrado_no_envio_mesmo_sem_a_tarefa_de_fundo(monkeypatch, enviados):
    """A tarefa de fundo é onde a triagem do agente roda: o alerta já está na
    fila antes dela, e o job de 10 em 10 minutos o leva se a entrega não vier."""
    monkeypatch.setattr(caso_grave, "entregar_os_avisos_da_chegada", lambda *_a, **_kw: None)
    banco = _banco()

    _cliente(banco).post(PUBLICO, json={**GRAVE, "anonimo": True, "origem": "endereco"})

    alertas = _avisos(banco, caso_grave.MARCO_DO_ALERTA)
    assert len(alertas) == 4
    assert {a["situacao"] for a in alertas} == {emails.PENDENTE}
    assert enviados == []


@pytest.mark.parametrize(
    "mudanca",
    [{"chegou_ao_paciente": "com_dano", "grave_ou_morte": False}, {"chegou_ao_paciente": "sem_dano"}],
    ids=["com dano, não grave", "sem dano"],
)
def test_caso_que_nao_e_grave_nao_alerta_ninguem(mudanca, enviados):
    banco = _banco()

    _cliente(banco).post(PUBLICO, json={**RELATO, **mudanca, "anonimo": True, "origem": "qr"})

    assert len(banco.notificacoes) == 1
    assert _avisos(banco, caso_grave.MARCO_DO_ALERTA) == []
    assert enviados == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. Protocolo, setor e link, nunca o relato; 5. sem travessão
# ═══════════════════════════════════════════════════════════════════════════


def test_o_alerta_leva_protocolo_setor_e_link_e_nunca_o_relato(enviados):
    banco = _banco()

    resposta = _cliente(banco).post(PUBLICO, json={**GRAVE, "anonimo": True, "origem": "qr"})

    protocolo = resposta.json()["protocolo"]
    para_a_presidencia = next(e for e in enviados if e["para"] == "p1@hsm.test")
    assert para_a_presidencia["assunto"] == (
        f"Caso grave ou com morte: abra a notificação {protocolo}, recebida em 14/11/2026 às 03:00"
    )
    for parte in ("texto", "html"):
        corpo = para_a_presidencia[parte]
        assert protocolo in corpo
        assert SETOR["nome"] in corpo
        assert "/seguranca-do-paciente/notificacoes" in corpo
        assert "Pessoa de Teste P1" in corpo
    for envio in enviados:
        for parte in ("assunto", "texto", "html"):
            assert RELATO_GRAVE not in envio[parte]
            assert "bomba de infusão" not in envio[parte]
            assert GRAVE["leito_ou_atendimento"] not in envio[parte]


def test_o_alerta_sai_sem_travessao_mesmo_com_setor_e_nome_que_tem(enviados):
    banco = _banco()
    banco.tabelas["setores"][0]["nome"] = "UTI — Adulto – Leste"
    banco.tabelas["participantes"][0]["nome_completo"] = "Ana — Presidente"

    _cliente(banco).post(PUBLICO, json={**GRAVE, "anonimo": True, "origem": "qr"})

    assert len(enviados) == 4
    for envio in enviados:
        for parte in ("assunto", "texto", "html"):
            assert "—" not in envio[parte]
            assert "–" not in envio[parte]
    assert any("UTI" in e["texto"] and "Leste" in e["texto"] for e in enviados)
