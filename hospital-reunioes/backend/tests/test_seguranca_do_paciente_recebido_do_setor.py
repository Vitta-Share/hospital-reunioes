"""Encaminhar à Segurança do Trabalho e à queixa técnica com "Recebido"
(issue #1996, PRD #1979, ADR 0107 decisão 8).

Um bloco por critério de aceite:

1. o e-mail vai ao titular vigente do setor; sem titular, vai ao gestor e a
   Presidência é avisada;
2. o link abre a tela com o resumo e o botão "Recebido"; depois do clique,
   recusa nova abertura; vencido, recusa;
3. o banco guarda só o hash do token;
4. sem o clique no prazo, o e-mail é reenviado uma única vez;
5. o caso mostra o recebido com data e hora;
6. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória da triagem. Nenhum dado de pessoa real.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_triagem import (  # noqa: E402
    PRESIDENTE,
    _banco,
    _BancoDaTriagem,
    _cliente,
    _ConsultaDaTriagem,
    _notificacao,
    _secao_do_kit,
    _sugestao,
)

from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_recebimento as recebimento_router  # noqa: E402
from app.services.seguranca_do_paciente import emails, encaminhamento, recebimento  # noqa: E402

SEGURANCA_DO_TRABALHO = {"id": "55555555-5555-5555-5555-555555555555", "nome": "Segurança do Trabalho", "ativo": True}
FARMACIA = {"id": "66666666-6666-6666-6666-666666666666", "nome": "Farmácia Hospitalar", "ativo": True}
MOTIVO = "A técnica se feriu com a agulha ao descartar o material."
RELATO = "Relato com o nome da paciente Maria de Teste, que não pode sair no link."
# Uma terça-feira às 10h de Brasília: dentro do expediente.
AGORA = datetime(2026, 11, 10, 13, 0, tzinfo=UTC)


def _responsavel(rid: str, setor: str, papel: str, **campos) -> dict[str, Any]:
    base = {
        "id": rid,
        "setor": setor,
        "papel": papel,
        "nome": f"Responsável {rid}",
        "email": f"{rid.lower()}@hsm.test",
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": None,
    }
    return {**base, **campos}


class _ConsultaComIs(_ConsultaDaTriagem):
    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self


class _Banco(_BancoDaTriagem):
    def table(self, nome: str):
        return _ConsultaComIs(self, nome)


def _cenario(responsaveis: list[dict] | None = None) -> tuple[_Banco, dict]:
    caso = _notificacao(1, relato=RELATO)
    base = _banco([caso], [_sugestao(caso)])
    banco = _Banco(base.tabelas)
    banco.tabelas["setores"] += [dict(SEGURANCA_DO_TRABALHO), dict(FARMACIA)]
    banco.tabelas["ouvidoria_setor_responsaveis"] = (
        responsaveis
        if responsaveis is not None
        else [
            _responsavel("R1", SEGURANCA_DO_TRABALHO["nome"], "titular"),
            _responsavel("R2", SEGURANCA_DO_TRABALHO["nome"], "gestor"),
            _responsavel("R3", FARMACIA["nome"], "titular"),
        ]
    )
    return banco, caso


def _encaminhar(banco, caso, **corpo):
    corpo.setdefault("motivo", MOTIVO)
    return _cliente(banco, PRESIDENTE).post(f"/api/nsp/triagem/{caso['id']}/encaminhamento", json=corpo)


def _a_seguranca_do_trabalho(banco, caso):
    return _encaminhar(
        banco, caso, destinos=["seguranca_do_trabalho"], setores={"seguranca_do_trabalho": SEGURANCA_DO_TRABALHO["id"]}
    )


@pytest.fixture
def enviados(monkeypatch) -> list[dict]:
    """O que o provedor de e-mail recebeu, sem sair nada de verdade."""
    caixa: list[dict] = []

    def _enviar(para, assunto, html, texto):
        caixa.append({"para": para, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(emails, "_enviar_email", _enviar)
    return caixa


def _do_setor(banco) -> list[dict]:
    return [a for a in banco.tabelas.get("nsp_avisos", []) if a["marco"] == recebimento.MARCO_DO_SETOR]


def _token(email: dict) -> str:
    [token] = re.findall(r"/notificar/recebido/([A-Za-z0-9_-]+)", email["texto"])
    return token


def _publico(banco) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(recebimento_router.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


@pytest.fixture(autouse=True)
def _relogio(monkeypatch):
    """O encaminhamento acontece em AGORA, dentro do expediente."""
    monkeypatch.setattr(encaminhamento, "_agora", lambda: AGORA)
    monkeypatch.setattr(recebimento_router, "agora_utc", lambda: AGORA)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


# ═══════════════════════════════════════════════════════════════════════════
# 1. O e-mail vai ao titular vigente; sem titular, ao gestor, e a Presidência
#    é avisada
# ═══════════════════════════════════════════════════════════════════════════


def test_encaminhar_a_seguranca_do_trabalho_manda_o_email_ao_titular_vigente(enviados):
    banco, caso = _cenario()

    resposta = _a_seguranca_do_trabalho(banco, caso)

    assert resposta.status_code == 201, resposta.text
    [registro] = _do_setor(banco)
    assert registro["caso_id"] == caso["id"]
    emails.despachar_pendentes(banco, AGORA)
    [email] = enviados
    assert email["para"] == "r1@hsm.test"
    assert "NSP-2026-0001" in email["assunto"]
    assert MOTIVO in email["texto"]
    assert banco.notificacoes[0]["estado"] == "encaminhada"


def test_a_queixa_tecnica_vai_ao_titular_do_setor_escolhido(enviados):
    banco, caso = _cenario()

    resposta = _encaminhar(banco, caso, destinos=["queixa_tecnica"], setores={"queixa_tecnica": FARMACIA["id"]})

    assert resposta.status_code == 201, resposta.text
    emails.despachar_pendentes(banco, AGORA)
    assert [e["para"] for e in enviados] == ["r3@hsm.test"]


def test_sem_titular_vigente_vai_ao_gestor_e_a_presidencia_e_avisada(enviados):
    banco, caso = _cenario(
        [
            _responsavel("R1", SEGURANCA_DO_TRABALHO["nome"], "titular", vigencia_fim="2026-10-31"),
            _responsavel("R2", SEGURANCA_DO_TRABALHO["nome"], "gestor"),
        ]
    )

    resposta = _a_seguranca_do_trabalho(banco, caso)

    assert resposta.status_code == 201, resposta.text
    emails.despachar_pendentes(banco, AGORA)
    assert sorted(e["para"] for e in enviados) == ["p1@hsm.test", "r2@hsm.test"]
    [aviso] = [e for e in enviados if e["para"] == PRESIDENTE["email"]]
    assert "Segurança do Trabalho" in aviso["texto"]
    assert "titular" in aviso["texto"]
    assert "/notificar/recebido/" not in aviso["texto"]


def test_com_titular_a_presidencia_nao_e_avisada(enviados):
    banco, caso = _cenario()

    _a_seguranca_do_trabalho(banco, caso)

    emails.despachar_pendentes(banco, AGORA)
    assert [e["para"] for e in enviados] == ["r1@hsm.test"]


SO_SUBSTITUTO = [_responsavel("R5", SEGURANCA_DO_TRABALHO["nome"], "substituto")]


@pytest.mark.parametrize(
    "responsaveis, setores",
    [
        ([], {"seguranca_do_trabalho": SEGURANCA_DO_TRABALHO["id"]}),
        (SO_SUBSTITUTO, {"seguranca_do_trabalho": SEGURANCA_DO_TRABALHO["id"]}),
        (None, {}),
        (None, {"seguranca_do_trabalho": "77777777-7777-7777-7777-777777777777"}),
    ],
    ids=["setor sem ninguém", "só substituto", "sem setor escolhido", "setor fora da taxonomia"],
)
def test_sem_titular_nem_gestor_o_encaminhamento_e_recusado_sem_gravar(responsaveis, setores, enviados):
    banco, caso = _cenario(responsaveis)

    resposta = _encaminhar(banco, caso, destinos=["seguranca_do_trabalho"], setores=setores)

    assert resposta.status_code == 422, resposta.text
    assert banco.tabelas.get("nsp_encaminhamentos", []) == []
    assert banco.tabelas.get("nsp_recebimentos", []) == []
    assert banco.tabelas.get("nsp_avisos", []) == []
    assert banco.notificacoes[0]["estado"] == "recebida"


def test_o_nucleo_e_a_seguranca_do_trabalho_juntos_mantem_o_caso_na_triagem(enviados):
    banco, caso = _cenario()

    resposta = _encaminhar(
        banco,
        caso,
        destinos=["nucleo", "seguranca_do_trabalho"],
        setores={"seguranca_do_trabalho": SEGURANCA_DO_TRABALHO["id"]},
    )

    assert resposta.status_code == 201, resposta.text
    assert banco.notificacoes[0]["estado"] == "recebida"
    emails.despachar_pendentes(banco, AGORA)
    assert [e["para"] for e in enviados] == ["r1@hsm.test"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. O link abre o resumo e o botão Recebido; depois do clique, e vencido,
#    recusa
# ═══════════════════════════════════════════════════════════════════════════


def _link_enviado(banco, caso, enviados) -> str:
    _a_seguranca_do_trabalho(banco, caso)
    emails.despachar_pendentes(banco, AGORA)
    [email] = enviados
    return _token(email)


def test_o_link_abre_o_resumo_sem_o_relato(enviados):
    banco, caso = _cenario()
    token = _link_enviado(banco, caso, enviados)

    resposta = _publico(banco).get(f"/api/nsp/recebimento/{token}")

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["protocolo"] == "NSP-2026-0001"
    assert corpo["motivo"] == MOTIVO
    assert corpo["setor_que_recebe"] == "Segurança do Trabalho"
    assert corpo["setor_do_incidente"] == "UTI Adulto"
    assert "Maria de Teste" not in resposta.text
    assert "Profissional Notificante" not in resposta.text


def test_depois_do_recebido_o_link_recusa_nova_abertura(enviados):
    banco, caso = _cenario()
    token = _link_enviado(banco, caso, enviados)
    publico = _publico(banco)

    clique = publico.post(f"/api/nsp/recebimento/{token}/recebido")

    assert clique.status_code == 200, clique.text
    assert publico.get(f"/api/nsp/recebimento/{token}").status_code == 410
    assert publico.post(f"/api/nsp/recebimento/{token}/recebido").status_code == 410


def test_abrir_o_link_nao_confirma_o_recebido(enviados):
    banco, caso = _cenario()
    token = _link_enviado(banco, caso, enviados)

    _publico(banco).get(f"/api/nsp/recebimento/{token}")

    [linha] = banco.tabelas["nsp_recebimentos"]
    assert linha.get("recebido_em") is None


def test_o_link_vencido_recusa(enviados):
    banco, caso = _cenario()
    token = _link_enviado(banco, caso, enviados)
    [linha] = banco.tabelas["nsp_recebimentos"]
    linha["expira_em"] = (AGORA - timedelta(minutes=1)).isoformat()

    assert _publico(banco).get(f"/api/nsp/recebimento/{token}").status_code == 410
    assert _publico(banco).post(f"/api/nsp/recebimento/{token}/recebido").status_code == 410
    assert linha.get("recebido_em") is None


def test_o_link_adulterado_e_404(enviados):
    banco, caso = _cenario()
    token = _link_enviado(banco, caso, enviados)

    assert _publico(banco).get(f"/api/nsp/recebimento/{token}x").status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 3. O banco guarda só o hash do token
# ═══════════════════════════════════════════════════════════════════════════


def test_o_banco_guarda_so_o_hash_do_token(enviados):
    banco, caso = _cenario()
    token = _link_enviado(banco, caso, enviados)

    [linha] = banco.tabelas["nsp_recebimentos"]
    assert linha["token_hash"] == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token not in str(banco.tabelas)
    assert token not in str(banco.escritas)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Sem o clique no prazo, o e-mail sai de novo uma única vez
# ═══════════════════════════════════════════════════════════════════════════

# Dois dias úteis depois de terça, 10/11: a segunda, 16/11, já passou do prazo;
# a quarta, 11/11, ainda não.
NA_QUARTA = datetime(2026, 11, 11, 13, 0, tzinfo=UTC)
NA_SEGUNDA = datetime(2026, 11, 16, 13, 0, tzinfo=UTC)


def test_sem_o_clique_no_prazo_o_email_e_reenviado_uma_unica_vez(enviados):
    banco, caso = _cenario()
    primeiro = _link_enviado(banco, caso, enviados)

    assert recebimento.reenviar_os_esquecidos(banco, NA_QUARTA, frozenset()) == 0
    assert recebimento.reenviar_os_esquecidos(banco, NA_SEGUNDA, frozenset()) == 1
    assert recebimento.reenviar_os_esquecidos(banco, NA_SEGUNDA + timedelta(days=7), frozenset()) == 0
    emails.despachar_pendentes(banco, NA_SEGUNDA)
    emails.despachar_pendentes(banco, NA_SEGUNDA + timedelta(days=7))

    assert [e["para"] for e in enviados] == ["r1@hsm.test", "r1@hsm.test"]
    segundo = _token(enviados[1])
    assert segundo != primeiro
    assert MOTIVO in enviados[1]["texto"]
    assert _publico(banco).get(f"/api/nsp/recebimento/{segundo}").status_code == 200


def test_com_o_clique_nao_ha_reenvio(enviados):
    banco, caso = _cenario()
    token = _link_enviado(banco, caso, enviados)
    _publico(banco).post(f"/api/nsp/recebimento/{token}/recebido")

    assert recebimento.reenviar_os_esquecidos(banco, NA_SEGUNDA, frozenset()) == 0
    emails.despachar_pendentes(banco, NA_SEGUNDA)
    assert len(enviados) == 1


def test_o_reenvio_que_esperava_na_fila_nao_sai_depois_do_clique(enviados):
    banco, caso = _cenario()
    token = _link_enviado(banco, caso, enviados)
    recebimento.reenviar_os_esquecidos(banco, NA_SEGUNDA, frozenset())

    _publico(banco).post(f"/api/nsp/recebimento/{token}/recebido")
    emails.despachar_pendentes(banco, NA_SEGUNDA)

    assert len(enviados) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. O caso mostra o recebido com data e hora
# ═══════════════════════════════════════════════════════════════════════════


def test_o_caso_mostra_o_recebido_com_data_e_hora(enviados):
    banco, caso = _cenario()
    _encaminhar(
        banco,
        caso,
        destinos=["nucleo", "seguranca_do_trabalho"],
        setores={"seguranca_do_trabalho": SEGURANCA_DO_TRABALHO["id"]},
    )
    emails.despachar_pendentes(banco, AGORA)
    tela = f"/api/nsp/triagem/{caso['id']}"

    [antes] = _cliente(banco).get(tela).json()["encaminhamentos"]
    _publico(banco).post(f"/api/nsp/recebimento/{_token(enviados[0])}/recebido")
    [depois] = _cliente(banco).get(tela).json()["encaminhamentos"]

    [envio] = antes["recebimentos"]
    assert envio["setor"] == "Segurança do Trabalho"
    assert envio["destinatario_nome"] == "Responsável R1"
    assert envio["recebido_em"] is None
    [recebido] = depois["recebimentos"]
    assert recebido["recebido_em"] == AGORA.isoformat()
    assert "token_hash" not in recebido


# ═══════════════════════════════════════════════════════════════════════════
# 6. O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_diz_como_funciona_o_recebido_do_setor():
    no_ar = _secao_do_kit("O que já está no ar")
    for termo in (
        "Segurança do Trabalho e a queixa técnica (Farmácia ou Engenharia Clínica)",
        "titular vigente do setor",
        'botão "Recebido"',
        "vale uma vez só",
        "o e-mail vai ao gestor e a Presidência é avisada",
        "reenviado uma única vez",
        "com data e hora",
    ):
        assert termo in no_ar, termo
    assert "Segurança do Trabalho" not in _secao_do_kit("O que ele ainda não faz")


# ═══════════════════════════════════════════════════════════════════════════
# O job de 10 em 10 minutos faz o reenvio antes da fila
# ═══════════════════════════════════════════════════════════════════════════


def test_o_job_do_nucleo_faz_o_reenvio_antes_de_despachar(monkeypatch):
    from app.cron import scheduler

    ordem: list[str] = []
    monkeypatch.setattr(scheduler, "_supabase", lambda: "banco")
    monkeypatch.setattr(recebimento, "reenviar_os_esquecidos", lambda banco, agora: ordem.append("reenvio") or 0)
    monkeypatch.setattr(emails, "despachar_pendentes", lambda banco, agora: ordem.append("fila") or {})

    scheduler.despachar_emails_nsp()

    assert ordem == ["reenvio", "fila"]


# ═══════════════════════════════════════════════════════════════════════════
# A migration 220, lida como texto (a prova no Postgres está no PR)
# ═══════════════════════════════════════════════════════════════════════════

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "220_nsp_recebido_do_setor.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def test_a_migration_aceita_os_destinos_e_os_marcos_do_app():
    sql = _sql()
    [lista] = re.findall(r"destinos <@ ARRAY\[([^\]]+)\]", sql)
    assert sorted(re.findall(r"'(\w+)'", lista)) == sorted(encaminhamento.DESTINOS)
    for marco in (recebimento.MARCO_DO_SETOR, recebimento.MARCO_SEM_TITULAR):
        assert f"'{marco}'" in sql, marco
    [destinos_do_recebimento] = re.findall(r"destino\s+TEXT NOT NULL CHECK \(destino IN \(([^)]+)\)\)", sql)
    assert sorted(re.findall(r"'(\w+)'", destinos_do_recebimento)) == sorted(recebimento.DESTINOS)


def test_a_tabela_nova_guarda_o_hash_nasce_com_rls_sem_politica_e_o_recibo_e_o_220():
    sql = _sql()
    for tabela in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql):
        assert f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;" in sql, tabela
    assert "token_hash" in sql
    assert not re.search(r"\btoken\s+TEXT", sql)
    assert "VALUES (220) ON CONFLICT" in sql
    assert "CREATE POLICY" not in sql.upper()
