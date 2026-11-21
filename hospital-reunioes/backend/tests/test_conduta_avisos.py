"""Os avisos por e-mail do Canal de Conduta (issue #1840, PRD #1786).

Uma classe por critério de aceite da issue:

1. tarefa nova gera e-mail ao membro responsável, com o texto fixo e o link
   para MINHA VEZ;
2. o e-mail e o link não contêm protocolo, nome, rito nem trecho de relato;
3. caso do rito Completo ou da Rota Especial avisa na hora;
4. os lembretes saem a cinco dias e a um dia do prazo;
5. nenhum e-mail é enviado a quem relatou;
6. o job não chama IA;
7. o texto do Produto no kit de conhecimento diz o comportamento novo.

O banco é o dublê de `conduta_apoio`, o Comitê é o de `test_conduta_triagem`
e o e-mail é sempre dublado. As pessoas são de teste.
"""

from __future__ import annotations

import base64
import inspect
import os
import secrets
import sys
from datetime import timedelta

import pytest
from test_conduta_triagem import (
    COORDENACAO,
    DE_FORA,
    DENTRO_COMPLETO,
    DENTRO_RAPIDO,
    FORA_DP,
    HOJE,
    MEMBRO,
    RELATO,
    SEGUNDO_LEITOR,
    Comite,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.services.conduta import avisos  # noqa: E402

FRASE = "Há uma tarefa no Canal de Conduta."


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "frontend_url", "https://app.hsm.test")


@pytest.fixture
def emails(monkeypatch) -> list[dict]:
    enviados: list[dict] = []

    def _enviar(destinatario, assunto, html, texto, **kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html, "texto": texto, **kw})
        return True

    monkeypatch.setattr(avisos, "_enviar_email", _enviar)
    return enviados


@pytest.fixture
def comite() -> Comite:
    return Comite()


def _para(emails: list[dict]) -> list[str]:
    return sorted(e["para"] for e in emails)


def _email(pid: str) -> str:
    return f"{pid.lower()}@hsm.test"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Tarefa nova gera e-mail ao membro responsável
# ═══════════════════════════════════════════════════════════════════════════


class TestTarefaNova:
    def test_caso_recebido_avisa_a_coordenacao_que_confirma_a_triagem(self, comite, emails):
        comite.caso()

        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _para(emails) == [_email(COORDENACAO)]
        assert emails[0]["assunto"] == FRASE
        assert FRASE in emails[0]["texto"]
        assert "https://app.hsm.test/comite-de-conduta\n" in emails[0]["texto"]
        assert 'href="https://app.hsm.test/comite-de-conduta"' in emails[0]["html"]

    def test_triagem_confirmada_avisa_o_segundo_leitor_e_so_ele(self, comite, emails):
        caso_id = comite.caso()
        avisos.rodada_do_dia(comite.banco, HOJE)
        emails.clear()

        comite.ok(COORDENACAO, caso_id, "triagem", DENTRO_RAPIDO)
        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _para(emails) == [_email(SEGUNDO_LEITOR)]

    def test_contestacao_avisa_os_votantes_e_quem_ja_votou_nao_e_avisado(self, comite, emails):
        caso_id = comite.caso()
        comite.ok(COORDENACAO, caso_id, "triagem", DENTRO_RAPIDO)
        avisos.rodada_do_dia(comite.banco, HOJE)
        emails.clear()

        comite.ok(SEGUNDO_LEITOR, caso_id, "contestacao", {**DENTRO_COMPLETO, "motivo": "É grave."})
        comite.ok(COORDENACAO, caso_id, "contestacao/decisao", {"escolha": "manter"})
        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _para(emails) == [_email(SEGUNDO_LEITOR), _email(MEMBRO)]

    def test_tarefa_que_ja_foi_feita_antes_da_rodada_nao_vira_email(self, comite, emails):
        caso_id = comite.caso()
        comite.ok(COORDENACAO, caso_id, "triagem", DENTRO_RAPIDO)

        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _para(emails) == [_email(SEGUNDO_LEITOR)]
        situacoes = {(a["participante_id"], a["situacao"]) for a in comite.banco.tabelas["conduta_avisos"]}
        assert (COORDENACAO, "dispensado") in situacoes

    def test_duas_rodadas_no_mesmo_dia_nao_repetem_o_email(self, comite, emails):
        comite.caso()
        avisos.rodada_do_dia(comite.banco, HOJE)

        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _para(emails) == [_email(COORDENACAO)]

    def test_quem_tem_varias_tarefas_recebe_um_email_so(self, comite, emails):
        comite.caso()
        comite.caso()

        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _para(emails) == [_email(COORDENACAO)]
        assert {a["situacao"] for a in comite.banco.tabelas["conduta_avisos"]} == {"enviado"}

    def test_o_aviso_que_falha_fica_pendente_e_sai_na_rodada_seguinte(self, comite, emails, monkeypatch):
        comite.caso()
        monkeypatch.setattr(avisos, "_enviar_email", lambda *_a, **_kw: False)
        avisos.rodada_do_dia(comite.banco, HOJE)
        assert {a["situacao"] for a in comite.banco.tabelas["conduta_avisos"]} == {"pendente"}

        monkeypatch.setattr(avisos, "_enviar_email", lambda para, *_a, **_kw: emails.append({"para": para}) or True)
        avisos.rodada_do_dia(comite.banco, HOJE + timedelta(days=1))

        assert _para(emails) == [_email(COORDENACAO)]

    def test_a_acao_acontece_mesmo_com_o_aviso_fora_do_ar(self, comite, monkeypatch):
        caso_id = comite.caso()

        def _explode(*_a, **_kw):
            raise RuntimeError("banco dos avisos fora do ar")

        monkeypatch.setattr(avisos, "tarefas_do_caso", _explode)

        assert comite.ok(COORDENACAO, caso_id, "triagem", DENTRO_RAPIDO)["etapa"] == "apuracao"
