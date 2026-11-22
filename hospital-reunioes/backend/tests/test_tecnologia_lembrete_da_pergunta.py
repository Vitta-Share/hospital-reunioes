"""O lembrete único da Pergunta da Vitta, depois de 3 dias sem resposta
(issue #2120, PRD #2112, ADR 0109, decisão 7).

O agendador de hora em hora lembra o Destinatário da Pergunta aberta há 3
dias corridos, por sino e e-mail, com o Assunto e há quantos dias ela espera.
A data do lembrete fica gravada na Pergunta, e nunca sai um segundo.

Com o Supabase em memória de `test_tecnologia_vinculo`; o e-mail é gravado na
porta do transporte.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_vinculo import _demanda, _pessoa, _SupabaseMock  # noqa: E402

from app.config import settings  # noqa: E402
from app.cron import scheduler  # noqa: E402
from app.services import tecnologia_email, tecnologia_perguntas  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

AGORA = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
LINK = f"https://app.hsm.test/admin/tecnologia?demanda={DEMANDA}"

PEDRO = _pessoa("P001", "Pedro Rezende", github_login="pedrorezendefig")
DIRETORA = _pessoa("P004", "Diretora Clínica")
DIRETOR = _pessoa("P003", "Diretor Geral")

TABELA = "tecnologia_perguntas"


@pytest.fixture(autouse=True)
def emails(monkeypatch) -> list[dict]:
    """Cada e-mail que sairia, gravado na porta do transporte."""
    enviados: list[dict] = []

    def _gravar(destinatario, assunto, html_content, texto_fallback, *a, **kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html_content, "texto": texto_fallback})
        return True

    monkeypatch.setattr(tecnologia_email, "_enviar_email", _gravar)
    monkeypatch.setattr(settings, "frontend_url", "https://app.hsm.test")
    return enviados


def _pergunta(pid: str, *, ha: timedelta, destinatario=DIRETORA, estado="aberta", **campos) -> dict:
    return {
        "id": pid,
        "demanda_id": DEMANDA,
        "mensagem_id": f"msg-{pid}",
        "autor_id": PEDRO["id"],
        "destinatario_id": destinatario["id"],
        "assunto": f"quem assina a Ata ({pid})",
        "texto": "Quem assina a Ata em nome da diretoria?",
        "estado": estado,
        "lembrete_enviado_em": None,
        "criado_em": (AGORA - ha).isoformat(),
        **campos,
    }


def _banco(*perguntas: dict) -> _SupabaseMock:
    return _SupabaseMock(
        {
            "participantes": [dict(p) for p in (PEDRO, DIRETORA, DIRETOR)],
            "tecnologia_demandas": [
                _demanda(DEMANDA, titulo="A Ata assinada no app", autor_id=PEDRO["id"], origem="vitta")
            ],
            TABELA: [dict(p) for p in perguntas],
        }
    )


def _sinos(sb: _SupabaseMock) -> list[dict]:
    return sb.tabelas.get("notificacoes", [])


# ═══════════════════════════════════════════════════════════════════════════
# O lembrete sai uma vez, depois de 3 dias
# ═══════════════════════════════════════════════════════════════════════════


def test_pergunta_aberta_ha_3_dias_lembra_o_destinatario_no_sino_e_no_email(emails):
    sb = _banco(_pergunta("q1", ha=timedelta(days=3)))

    assert tecnologia_perguntas.lembrar(sb, AGORA) == 1

    [sino] = _sinos(sb)
    assert sino["destinatario_id"] == DIRETORA["id"]
    assert sino["tipo"] == "TECNOLOGIA"
    assert sino["referencia_id"] == DEMANDA
    assert "quem assina a Ata (q1)" in sino["mensagem"]
    assert "há 3 dias" in sino["titulo"] + " " + sino["mensagem"]

    [email] = emails
    assert email["para"] == DIRETORA["email"]
    assert "quem assina a Ata (q1)" in email["assunto"]
    assert "há 3 dias" in email["texto"]
    assert LINK in email["texto"]
    assert f'href="{LINK}"' in email["html"]

    [pergunta] = sb.tabelas[TABELA]
    assert pergunta["lembrete_enviado_em"] == AGORA.isoformat()


def test_o_lembrete_diz_ha_quantos_dias_a_pergunta_espera(emails):
    sb = _banco(_pergunta("q1", ha=timedelta(days=5, hours=2)))

    tecnologia_perguntas.lembrar(sb, AGORA)

    [sino] = _sinos(sb)
    assert "há 5 dias" in sino["titulo"] + " " + sino["mensagem"]
    assert "há 5 dias" in emails[0]["texto"]


def test_pergunta_aberta_ha_menos_de_3_dias_ainda_nao_lembra(emails):
    sb = _banco(_pergunta("q1", ha=timedelta(days=2, hours=23, minutes=59)))

    assert tecnologia_perguntas.lembrar(sb, AGORA) == 0

    assert _sinos(sb) == []
    assert emails == []
    assert sb.tabelas[TABELA][0]["lembrete_enviado_em"] is None


def test_a_mesma_pergunta_nunca_recebe_um_segundo_lembrete(emails):
    sb = _banco(_pergunta("q1", ha=timedelta(days=3)))

    tecnologia_perguntas.lembrar(sb, AGORA)
    assert tecnologia_perguntas.lembrar(sb, AGORA + timedelta(hours=1)) == 0
    assert tecnologia_perguntas.lembrar(sb, AGORA + timedelta(days=4)) == 0

    assert len(_sinos(sb)) == 1
    assert len(emails) == 1
    assert sb.tabelas[TABELA][0]["lembrete_enviado_em"] == AGORA.isoformat()


def test_pergunta_que_ja_foi_lembrada_antes_nao_lembra_de_novo(emails):
    sb = _banco(_pergunta("q1", ha=timedelta(days=9), lembrete_enviado_em="2026-11-15T12:00:00+00:00"))

    assert tecnologia_perguntas.lembrar(sb, AGORA) == 0

    assert _sinos(sb) == []
    assert emails == []


@pytest.mark.parametrize("estado", ["respondida", "resolvida", "cancelada"])
def test_pergunta_respondida_resolvida_ou_cancelada_nao_recebe_lembrete(emails, estado):
    sb = _banco(_pergunta("q1", ha=timedelta(days=6), estado=estado))

    assert tecnologia_perguntas.lembrar(sb, AGORA) == 0

    assert _sinos(sb) == []
    assert emails == []
    assert sb.tabelas[TABELA][0]["lembrete_enviado_em"] is None


def test_pergunta_aberta_numa_demanda_apagada_nao_recebe_lembrete(emails):
    """O Apagar (ADR 0084) deixa a Demanda como lápide e não mexe nas
    Perguntas, que seguem abertas. A lápide sai de toda leitura: o lembrete
    apontaria para um cartão que não existe mais."""
    sb = _banco(_pergunta("q1", ha=timedelta(days=4)))
    sb.tabelas["tecnologia_demandas"][0]["apagada_em"] = "2026-11-18T10:00:00+00:00"

    assert tecnologia_perguntas.lembrar(sb, AGORA) == 0

    assert _sinos(sb) == []
    assert emails == []


def test_a_falha_no_lembrete_de_uma_pergunta_nao_impede_as_outras(emails, monkeypatch):
    sb = _banco(
        _pergunta("q1", ha=timedelta(days=4), destinatario=DIRETORA),
        _pergunta("q2", ha=timedelta(days=4), destinatario=DIRETOR),
    )
    original = tecnologia_email.enviar_lembrete_da_pergunta

    def _quebra_para_a_diretora(supabase, **kw):
        if kw["destinatario_id"] == DIRETORA["id"]:
            raise RuntimeError("o provedor caiu")
        return original(supabase, **kw)

    monkeypatch.setattr(tecnologia_email, "enviar_lembrete_da_pergunta", _quebra_para_a_diretora)

    assert tecnologia_perguntas.lembrar(sb, AGORA) == 1

    assert [e["para"] for e in emails] == [DIRETOR["email"]]
    assert DIRETOR["id"] in [s["destinatario_id"] for s in _sinos(sb)]


# ═══════════════════════════════════════════════════════════════════════════
# O agendador de hora em hora
# ═══════════════════════════════════════════════════════════════════════════


def test_o_agendador_de_hora_em_hora_lembra_as_perguntas_mesmo_com_o_github_fora(monkeypatch):
    """A passada de hora em hora da Tecnologia lembra as Perguntas, e a falha
    das releituras do GitHub antes dela não pula o lembrete."""
    from app.services import tecnologia_anexos, tecnologia_espelho, tecnologia_sincronizacao

    def _quebra(*_a, **_kw):
        raise RuntimeError("GitHub fora do ar")

    for modulo, nome in (
        (tecnologia_espelho, "conferir_raizes_da_ana"),
        (tecnologia_sincronizacao, "reconciliar_vinculos"),
        (tecnologia_sincronizacao, "reconciliar_em_producao"),
        (tecnologia_anexos, "apagar_vencidos"),
    ):
        monkeypatch.setattr(modulo, nome, _quebra)

    sb = object()
    chamadas: list[tuple] = []
    monkeypatch.setattr(scheduler, "_supabase", lambda: sb)
    monkeypatch.setattr(tecnologia_perguntas, "lembrar", lambda supabase, agora: chamadas.append((supabase, agora)))

    scheduler.reconciliar_vinculos_tecnologia()

    [(supabase, agora)] = chamadas
    assert supabase is sb
    assert agora.tzinfo is not None
    assert abs(datetime.now(tz=UTC) - agora) < timedelta(minutes=1)


def test_o_agendador_segue_quando_o_lembrete_falha(monkeypatch):
    from app.services import tecnologia_anexos, tecnologia_espelho, tecnologia_sincronizacao

    for modulo, nome in (
        (tecnologia_espelho, "conferir_raizes_da_ana"),
        (tecnologia_sincronizacao, "reconciliar_vinculos"),
        (tecnologia_sincronizacao, "reconciliar_em_producao"),
        (tecnologia_anexos, "apagar_vencidos"),
    ):
        monkeypatch.setattr(modulo, nome, lambda *_a, **_kw: None)
    monkeypatch.setattr(scheduler, "_supabase", lambda: object())

    def _quebra(*_a, **_kw):
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(tecnologia_perguntas, "lembrar", _quebra)

    scheduler.reconciliar_vinculos_tecnologia()


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_da_tecnologia_explica_o_lembrete_unico_de_3_dias():
    texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")
    paragrafo = next((p for p in texto.split("\n\n") if "lembrete" in p.lower() and "3 dias" in p), "")
    assert paragrafo, "o kit não diz que a Pergunta da Vitta ganha um lembrete depois de 3 dias"
    assert "uma vez só" in paragrafo
    assert "sino" in paragrafo and "e-mail" in paragrafo
    assert "Pendência" not in paragrafo
