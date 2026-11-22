"""A faixa "o que exige ação hoje" e o alerta de 72 horas (issue #2000, PRD #1979).

O que a issue promete, um bloco por critério de aceite:

1. a faixa mostra os quatro grupos (casos A e B abertos, triagens pendentes por
   idade, prazos legais a vencer e Termos pendentes) com contagem e link para
   a tela certa, sem nome de paciente nem de profissional;
2. o caso A com o prazo de 72 horas a menos de 24 horas do fim gera o e-mail
   urgente e o destaque, uma vez só;
3. quem não abre os casos não vê a faixa;
4. (a linha de orientação fica no teste da tela);
5. o texto do Produto Segurança do Paciente no kit de conhecimento diz o
   comportamento novo.

O banco é o dublê em memória dos testes da notificação, e o provedor de e-mail
é sempre dublado. As pessoas são de teste.
"""

from __future__ import annotations

import inspect
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import (  # noqa: E402
    DIRETOR,
    DIRETOR_EXECUTIVO,
    MEMBRO,
    NUCLEO,
    PRESIDENTE,
    SETOR,
    SO_REUNIOES,
    SUPER_ADMIN,
    _Banco,
    _Consulta,
    _participacao,
    _pessoa,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente as nsp_router  # noqa: E402
from app.services.seguranca_do_paciente import acao_de_hoje, emails  # noqa: E402

SP = ZoneInfo("America/Sao_Paulo")
# Quinta, 22h em São Paulo: fora do expediente.
AGORA = datetime(2026, 11, 19, 22, 0, tzinfo=SP)

SUPLENTE = _pessoa("P7")
DIRETORIA_EXECUTIVA = _pessoa("P8", perfil_ouvidoria="diretoria_executiva")
NOME_DO_PACIENTE = "Maria Paciente da Silva"
NOME_DO_PROFISSIONAL = "Enfermeiro Fulano"


class _ConsultaComIs(_Consulta):
    def is_(self, coluna, valor):
        esperado = None if valor == "null" else valor
        self._filtros.append(lambda linha: linha.get(coluna) == esperado)
        return self


class _BancoDoPainel(_Banco):
    def table(self, nome: str):
        return _ConsultaComIs(self, nome)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _quinta_22h(monkeypatch):
    monkeypatch.setattr(acao_de_hoje, "_agora", lambda: AGORA)


@pytest.fixture
def enviados(monkeypatch) -> list[dict[str, str]]:
    caixa: list[dict[str, str]] = []

    def _enviar(destino, assunto, html, texto):
        caixa.append({"para": destino, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(emails, "_enviar_email", _enviar)
    return caixa


def _utc(momento: datetime) -> str:
    return momento.astimezone(UTC).isoformat()


def _notificacao(numero: int, estado: str, criado_em: datetime, **campos) -> dict[str, Any]:
    return {
        "id": f"caso-{numero}",
        "protocolo": f"NSP-2026-{numero:04d}",
        "numero": numero,
        "estado": estado,
        "criado_em": _utc(criado_em),
        "setor_id": SETOR["id"],
        "data_ocorrencia": "2026-11-18",
        "grave_ou_morte": None,
        "classificar_manualmente": False,
        "relato": f"{NOME_DO_PROFISSIONAL} trocou a medicação de {NOME_DO_PACIENTE}.",
        "notificante_nome": NOME_DO_PROFISSIONAL,
        "anonimo": False,
        **campos,
    }


def _decisao(caso: str, faixa: str) -> dict[str, Any]:
    return {
        "id": f"tri-{caso}",
        "notificacao_id": caso,
        "autor_tipo": "pessoa",
        "versao": 1,
        "faixa": faixa,
        "assunto": "Troca de medicação",
        "criado_em": _utc(AGORA - timedelta(days=1)),
    }


def _prazo_externo(caso: str, unidade: str, vence_em: datetime) -> dict[str, Any]:
    return {
        "id": f"prazo-{caso}",
        "notificacao_id": caso,
        "marco": "notificacao_externa",
        "tipo": "legal",
        "valor": 72 if unidade == "horas_corridas" else 15,
        "unidade": unidade,
        "contado_de": _utc(vence_em - timedelta(hours=72)),
        "vence_em": _utc(vence_em),
    }


def _externa(caso: str, vence_em: datetime, estado: str = "pendente", sistema: str = "notivisa") -> dict[str, Any]:
    return {
        "id": f"ext-{caso}",
        "notificacao_id": caso,
        "sistema": sistema,
        "prazo_legal": _utc(vence_em),
        "estado": estado,
    }


VENCE_EM_10_HORAS = AGORA + timedelta(hours=10)
VENCE_EM_40_HORAS = AGORA + timedelta(hours=40)
VENCE_NO_DIA_15 = datetime(2026, 12, 21, 23, 59, tzinfo=SP)


def _banco() -> _BancoDoPainel:
    """O cenário do dia:

    - caso 1: faixa A, classificado, 72 horas vencendo em 10 horas;
    - caso 2: faixa B, classificado, até o 15º dia útil;
    - caso 3: faixa C, classificado (não é A nem B);
    - caso 4: faixa A, encaminhado (não está aberto);
    - casos 5, 6 e 7: esperando a triagem, com 2 horas, 2 dias e 5 dias;
    - caso 8: faixa A, classificado, 72 horas vencendo em 40 horas;
    - caso 9: faixa A, classificado, 72 horas já notificadas à vigilância.

    E três Termos pendentes: um cadastrado sem Termo, um gerado e um enviado.
    """
    pessoas = (PRESIDENTE, MEMBRO, SO_REUNIOES, SUPER_ADMIN, DIRETOR_EXECUTIVO, DIRETOR, SUPLENTE, DIRETORIA_EXECUTIVA)
    pendentes = [_pessoa(f"P{n}") for n in (10, 11, 12)]
    participacoes = [
        _participacao("P1", "presidencia"),
        _participacao("P2", "membro"),
        _participacao("P7", "suplente"),
        _participacao("P10", "membro", termo=False),
        {**_participacao("P11", "membro", termo=False), "termo_gerado_em": _utc(AGORA - timedelta(days=3))},
        {
            **_participacao("P12", "membro", termo=False),
            "termo_gerado_em": _utc(AGORA - timedelta(days=3)),
            "termo_enviado_em": _utc(AGORA - timedelta(days=2)),
        },
        # Encerrada sem assinatura: não é Termo pendente.
        {**_participacao("P3", "membro", termo=False), "encerrada_em": _utc(AGORA - timedelta(days=30))},
    ]
    ontem = AGORA - timedelta(days=1)
    notificacoes = [
        _notificacao(1, "classificada", ontem),
        _notificacao(2, "classificada", ontem),
        _notificacao(3, "classificada", ontem),
        _notificacao(4, "encaminhada", ontem),
        _notificacao(5, "recebida", AGORA - timedelta(hours=2)),
        _notificacao(6, "em_triagem", AGORA - timedelta(days=2)),
        _notificacao(7, "recebida", AGORA - timedelta(days=5)),
        _notificacao(8, "classificada", ontem),
        _notificacao(9, "classificada", ontem),
    ]
    return _BancoDoPainel(
        {
            "participantes": [dict(p) for p in (*pessoas, *pendentes)],
            "colegiados": [dict(NUCLEO)],
            "participacoes": participacoes,
            "setores": [dict(SETOR)],
            "nsp_notificacoes": notificacoes,
            "nsp_triagens": [
                _decisao("caso-1", "A"),
                _decisao("caso-2", "B"),
                _decisao("caso-3", "C"),
                _decisao("caso-4", "A"),
                _decisao("caso-8", "A"),
                _decisao("caso-9", "A"),
            ],
            "nsp_prazos_do_caso": [
                _prazo_externo("caso-1", "horas_corridas", VENCE_EM_10_HORAS),
                _prazo_externo("caso-2", "dia_util_do_mes_seguinte", VENCE_NO_DIA_15),
                _prazo_externo("caso-8", "horas_corridas", VENCE_EM_40_HORAS),
                _prazo_externo("caso-9", "horas_corridas", VENCE_EM_10_HORAS),
            ],
            "nsp_notificacoes_externas": [
                _externa("caso-1", VENCE_EM_10_HORAS),
                _externa("caso-2", VENCE_NO_DIA_15, sistema="vigimed"),
                _externa("caso-8", VENCE_EM_40_HORAS),
                _externa("caso-9", VENCE_EM_10_HORAS, estado="enviada"),
            ],
        }
    )


def _faixa(banco: _Banco, pessoa: dict[str, Any]):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(nsp_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app).get("/api/nsp/acao-de-hoje")


def _grupos(resposta) -> dict[str, dict[str, Any]]:
    assert resposta.status_code == 200, resposta.text
    return {grupo["chave"]: grupo for grupo in resposta.json()["grupos"]}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os quatro grupos, com contagem e link, sem nome
# ═══════════════════════════════════════════════════════════════════════════


def test_a_presidencia_ve_os_quatro_grupos_com_contagem_e_link_para_a_tela_certa():
    resposta = _faixa(_banco(), PRESIDENTE)

    grupos = _grupos(resposta)
    assert list(grupos) == ["casos_abertos", "triagens_pendentes", "prazos_legais", "termos_pendentes"]

    casos = grupos["casos_abertos"]
    assert casos["titulo"] == "Casos A e B abertos"
    assert casos["total"] == 4
    assert {item["link"] for item in casos["itens"]} == {
        "/seguranca-do-paciente/notificacoes/caso-1",
        "/seguranca-do-paciente/notificacoes/caso-2",
        "/seguranca-do-paciente/notificacoes/caso-8",
        "/seguranca-do-paciente/notificacoes/caso-9",
    }
    assert any(item["rotulo"] == "NSP-2026-0002, faixa B" for item in casos["itens"])

    triagens = grupos["triagens_pendentes"]
    assert triagens["total"] == 3
    assert triagens["link"] == "/seguranca-do-paciente/notificacoes/triagem"
    assert [item["rotulo"] for item in triagens["itens"]] == [
        "1 há mais de 3 dias",
        "1 de 1 a 3 dias",
        "1 há menos de 1 dia",
    ]
    assert {item["link"] for item in triagens["itens"]} == {"/seguranca-do-paciente/notificacoes/triagem"}

    prazos = grupos["prazos_legais"]
    assert prazos["total"] == 3
    assert [item["link"] for item in prazos["itens"]] == [
        "/seguranca-do-paciente/notificacoes/caso-1",
        "/seguranca-do-paciente/notificacoes/caso-8",
        "/seguranca-do-paciente/notificacoes/caso-2",
    ]
    assert prazos["itens"][0]["rotulo"] == "NSP-2026-0001, NOTIVISA em 72 horas: vence em 20/11/2026 às 08:00"
    assert prazos["itens"][2]["rotulo"] == ("NSP-2026-0002, VigiMed até o 15º dia útil: vence em 21/12/2026 às 23:59")

    termos = grupos["termos_pendentes"]
    assert termos["total"] == 3
    assert termos["link"] == "/seguranca-do-paciente/membros"
    assert {item["link"] for item in termos["itens"]} == {"/seguranca-do-paciente/membros"}

    for nome in (NOME_DO_PACIENTE, NOME_DO_PROFISSIONAL, "Pessoa de Teste"):
        assert nome not in resposta.text


def test_sem_nada_a_fazer_cada_grupo_vem_com_zero():
    banco = _BancoDoPainel(
        {
            "participantes": [dict(PRESIDENTE)],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [_participacao("P1", "presidencia")],
            "setores": [dict(SETOR)],
            "nsp_notificacoes": [],
        }
    )

    grupos = _grupos(_faixa(banco, PRESIDENTE))

    assert {chave: grupo["total"] for chave, grupo in grupos.items()} == {
        "casos_abertos": 0,
        "triagens_pendentes": 0,
        "prazos_legais": 0,
        "termos_pendentes": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. O alerta de 72 horas: o e-mail urgente e o destaque, uma vez só
# ═══════════════════════════════════════════════════════════════════════════


def _alertas(banco: _Banco) -> list[dict[str, Any]]:
    return [a for a in banco.tabelas.get("nsp_avisos", []) if a["marco"] == acao_de_hoje.MARCO_DAS_72_HORAS]


def test_o_caso_a_a_menos_de_24_horas_do_fim_gera_o_email_urgente_uma_vez_so(enviados):
    banco = _banco()

    acao_de_hoje.alertar_os_prazos_de_72_horas(banco, AGORA)
    acao_de_hoje.alertar_os_prazos_de_72_horas(banco, AGORA + timedelta(hours=1))

    alertas = _alertas(banco)
    # Só o caso 1: o 8 ainda tem 40 horas, o 9 já foi notificado e o 2 é do
    # 15º dia útil. Para a Presidência, o suplente e o Acesso pleno.
    assert {a["caso_id"] for a in alertas} == {"caso-1"}
    assert sorted(a["destinatario_id"] for a in alertas) == ["P1", "P5", "P7"]
    for alerta in alertas:
        assert alerta["urgente"] is True
        assert alerta["situacao"] == emails.ENVIADO
    assert sorted(e["para"] for e in enviados) == ["p1@hsm.test", "p5@hsm.test", "p7@hsm.test"]
    envio = enviados[0]
    assert envio["assunto"] == ("[72 HORAS] Notificação NSP-2026-0001: notificar a vigilância até 20/11/2026 às 08:00")
    for parte in ("texto", "html"):
        assert "/seguranca-do-paciente/notificacoes/caso-1" in envio[parte]
        assert NOME_DO_PACIENTE not in envio[parte]
        assert NOME_DO_PROFISSIONAL not in envio[parte]
        assert "—" not in envio[parte]
        assert "–" not in envio[parte]


def test_o_job_de_hora_em_hora_dispara_o_alerta_de_72_horas(monkeypatch, enviados):
    from app.cron import scheduler

    banco = _banco()
    monkeypatch.setattr(scheduler, "_supabase", lambda: banco)
    monkeypatch.setattr(scheduler, "datetime", type("_Relogio", (), {"now": staticmethod(lambda tz=None: AGORA)}))

    scheduler.alertar_prazos_de_72_horas_nsp()

    assert {a["caso_id"] for a in _alertas(banco)} == {"caso-1"}
    assert len(enviados) == 3
    assert 'alertar_prazos_de_72_horas_nsp,\n        "cron",\n        minute=5,' in inspect.getsource(
        scheduler.start_scheduler
    )


def test_a_faixa_destaca_o_prazo_de_72_horas_a_menos_de_24_horas_do_fim():
    prazos = _grupos(_faixa(_banco(), PRESIDENTE))["prazos_legais"]

    destaque = {item["link"]: item["urgente"] for item in prazos["itens"]}
    assert destaque == {
        "/seguranca-do-paciente/notificacoes/caso-1": True,
        "/seguranca-do-paciente/notificacoes/caso-8": False,
        "/seguranca-do-paciente/notificacoes/caso-2": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. Quem não abre os casos não vê a faixa
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "pessoa",
    [DIRETOR, SO_REUNIOES, SUPER_ADMIN],
    ids=["diretoria sem casos", "sem o Núcleo", "super admin sem Acesso pleno"],
)
def test_quem_nao_abre_os_casos_nao_ve_a_faixa(pessoa):
    resposta = _faixa(_banco(), pessoa)

    assert resposta.status_code == 403
    assert "NSP-" not in resposta.text


def test_o_membro_com_termo_abre_os_casos_e_ve_a_faixa():
    assert _faixa(_banco(), MEMBRO).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 5. O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_de_conhecimento_conta_a_faixa_e_o_alerta_de_72_horas():
    kit = (Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "seguranca-do-paciente.md").read_text(
        encoding="utf-8"
    )

    assert "o que exige ação hoje" in kit
    assert "faltam 24 horas para o fim do prazo de 72 horas" in kit
