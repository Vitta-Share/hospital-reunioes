"""O registro de e-mail do Núcleo, com retentativa (issue #1985, PRD #1979, ADR 0107 decisão 8).

O que a issue promete, um bloco por critério de aceite:

1. todo e-mail do Núcleo nasce como registro antes de sair;
2. a falha do provedor devolve o registro à fila com espera crescente, e na
   terceira falha ele vira falha e o admin técnico é avisado;
3. o job não manda o mesmo registro duas vezes (reivindica antes de enviar);
4. o registro urgente sai na hora, fora da janela comercial; os demais esperam
   a janela.

O quinto critério (os avisos da Fase 1 continuam saindo) mora nos testes dos
avisos e da convocação, que agora passam pelo registro.

O banco é um dublê em memória e o e-mail é sempre dublado. As pessoas são de
teste.
"""

from __future__ import annotations

import inspect
import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.cron import scheduler  # noqa: E402
from app.services import ouvidoria_notificacoes  # noqa: E402
from app.services.seguranca_do_paciente import emails  # noqa: E402

SP = ZoneInfo("America/Sao_Paulo")
# Segunda-feira, dia útil, em pleno expediente.
SEGUNDA_10H = datetime(2026, 11, 16, 10, 0, tzinfo=SP)
# Sábado à noite: fora da janela comercial.
SABADO_22H = datetime(2026, 11, 14, 22, 0, tzinfo=SP)
SEGUNDA_8H = datetime(2026, 11, 16, 8, 0, tzinfo=SP)

_UNICAS = {"nsp_avisos": ("participacao_id", "marco", "referencia", "destinatario_id")}


# ═══════════════════════════════════════════════════════════════════════════
# O dublê do banco e do e-mail
# ═══════════════════════════════════════════════════════════════════════════


class _Consulta:
    def __init__(self, banco: _Banco, nome: str):
        self._nome = nome
        self._linhas = banco.tabelas.setdefault(nome, [])
        self._filtros: list = []
        self._ordem: str | None = None
        self._inicio = 0
        self._teto: int | None = None
        self._acao = "select"
        self._valores: Any = None

    def select(self, *_a, **_kw):
        return self

    def insert(self, valores):
        self._acao, self._valores = "insert", valores
        return self

    def update(self, valores):
        self._acao, self._valores = "update", valores
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        self._filtros.append(lambda linha: linha.get(coluna) in list(valores))
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) <= str(valor))
        return self

    def order(self, coluna, **_kw):
        self._ordem = coluna
        return self

    def limit(self, n):
        self._teto = n
        return self

    def range(self, inicio, fim):
        self._inicio, self._teto = inicio, fim - inicio + 1
        return self

    def execute(self):
        if self._acao == "insert":
            linha = {"id": str(uuid.uuid4()), **self._valores}
            chave = _UNICAS.get(self._nome)
            if chave and any(all(linha.get(c) == o.get(c) for c in chave) for o in self._linhas):
                raise APIError({"code": "23505", "message": "duplicate key value violates unique constraint"})
            self._linhas.append(linha)
            return SimpleNamespace(data=[dict(linha)])
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._acao == "update":
            for linha in casam:
                linha.update(self._valores)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        if self._ordem:
            casam.sort(key=lambda linha: str(linha.get(self._ordem)))
        casam = casam[self._inicio :]
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def table(self, nome: str):
        return _Consulta(self, nome)


def _pessoa(pid: str, **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "nome_completo": f"Pessoa de Teste {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "ativo": True,
        "access_profile": None,
    }
    return {**base, **campos}


ADMIN = _pessoa("SA1", access_profile="super_admin")


def _banco() -> _Banco:
    return _Banco({"participantes": [_pessoa("P2"), dict(ADMIN)], "nsp_avisos": []})


@pytest.fixture
def caixa(monkeypatch):
    """O provedor dublado. `caixa.falhas` diz quantas chamadas seguidas recusam."""
    estado = SimpleNamespace(saidas=[], falhas=0, explode=False, durante=None)

    def _falso(destinatario, assunto, html_content, texto_fallback, **_kw):
        if estado.durante:
            estado.durante()
        if estado.explode:
            raise RuntimeError("provedor fora do ar")
        if estado.falhas:
            estado.falhas -= 1
            return False
        estado.saidas.append({"para": destinatario, "assunto": assunto, "html": html_content, "texto": texto_fallback})
        return True

    monkeypatch.setattr(emails, "_enviar_email", _falso)
    monkeypatch.setattr(ouvidoria_notificacoes, "_enviar_email", _falso)
    return estado


def _registrar(banco: _Banco, agora: datetime = SEGUNDA_10H, **campos) -> dict | None:
    base = dict(
        marco="vigencia_30",
        referencia="2027-01-31",
        destinatario_id="P2",
        participacao_id="part-P2",
        assunto="Renove a sua participação no Núcleo de Segurança do Paciente: a vigência termina em 31/01/2027",
        texto="Olá, Pessoa de Teste P2.\n\nA sua participação termina em 31/01/2027.\n",
        modelo="email_nsp_aviso.html",
        contexto={"nome": "Pessoa de Teste P2", "paragrafos": ["A sua participação termina em 31/01/2027."], "link": "x"},
        agora=agora,
        feriados=frozenset(),
    )
    return emails.registrar(banco, **{**base, **campos})


def _linha(banco: _Banco) -> dict:
    (linha,) = banco.tabelas["nsp_avisos"]
    return linha


def _para(caixa) -> list[str]:
    return [s["para"] for s in caixa.saidas]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Todo e-mail do Núcleo nasce como registro antes de sair
# ═══════════════════════════════════════════════════════════════════════════


class TestNasceComoRegistro:
    def test_registrar_grava_a_linha_na_fila_sem_mandar_nada(self, caixa):
        banco = _banco()

        registro = _registrar(banco)

        assert caixa.saidas == []
        linha = _linha(banco)
        assert registro["id"] == linha["id"]
        assert linha["situacao"] == "pendente"
        assert linha["tentativas"] == 0
        assert linha["caso_id"] is None

    def test_quando_o_email_sai_o_registro_ja_existe(self, caixa):
        banco = _banco()
        vistos: list[str] = []
        caixa.durante = lambda: vistos.extend(a["situacao"] for a in banco.tabelas["nsp_avisos"])
        registro = _registrar(banco)

        assert emails.despachar_se_puder(banco, registro, SEGUNDA_10H) is True

        assert vistos == ["enviando"]
        assert _para(caixa) == ["p2@hsm.test"]
        assert _linha(banco)["situacao"] == "enviado"
        assert _linha(banco)["enviado_em"]

    def test_o_email_sai_com_o_assunto_o_texto_e_o_modelo_do_registro(self, caixa):
        banco = _banco()
        emails.despachar_se_puder(banco, _registrar(banco), SEGUNDA_10H)

        (saida,) = caixa.saidas
        assert saida["assunto"].startswith("Renove a sua participação")
        assert saida["texto"].startswith("Olá, Pessoa de Teste P2.")
        assert "Pessoa de Teste P2" in saida["html"]
        assert "Abrir Membros do Núcleo" in saida["html"]

    def test_o_registro_aceita_o_caso(self, caixa):
        banco = _banco()

        _registrar(banco, caso_id="caso-1", participacao_id=None)

        assert _linha(banco)["caso_id"] == "caso-1"
        assert _linha(banco)["participacao_id"] is None

    def test_o_mesmo_registro_nao_nasce_duas_vezes(self, caixa):
        banco = _banco()
        _registrar(banco)

        assert _registrar(banco) is None
        assert len(banco.tabelas["nsp_avisos"]) == 1

    def test_o_modelo_fora_do_nucleo_e_recusado(self, caixa):
        with pytest.raises(ValueError):
            _registrar(_banco(), modelo="email_ouvidoria_aviso_admin.html")


# O detector: quem chama o provedor de e-mail no módulo do Núcleo.
_APP = Path(__file__).resolve().parents[1] / "app"


def _chamam_o_provedor() -> list[str]:
    arquivos = sorted((_APP / "services" / "seguranca_do_paciente").glob("*.py")) + sorted(
        (_APP / "routers").glob("seguranca_do_paciente*.py")
    )
    return [a.name for a in arquivos if re.search(r"\b_?enviar_email\b", a.read_text(encoding="utf-8"))]


class TestUmCaminhoSo:
    def test_o_detector_acha_quem_chama_o_provedor(self):
        """Piso do detector: o próprio registro chama o provedor."""
        assert "emails.py" in _chamam_o_provedor()

    def test_so_o_registro_chama_o_provedor_de_email_no_nucleo(self):
        """Mutante: a convocação volta a chamar o `_enviar_email` direto."""
        assert _chamam_o_provedor() == ["emails.py"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. Falha do provedor: espera crescente e, na terceira, falha e admin avisado
# ═══════════════════════════════════════════════════════════════════════════


def _iso(momento: datetime) -> str:
    return momento.astimezone(ZoneInfo("UTC")).isoformat()


class TestRetentativa:
    def test_a_primeira_recusa_devolve_o_registro_a_fila_em_5_minutos(self, caixa):
        caixa.falhas = 1
        banco = _banco()

        saiu = emails.despachar_se_puder(banco, _registrar(banco), SEGUNDA_10H)

        assert saiu is False
        linha = _linha(banco)
        assert linha["situacao"] == "pendente"
        assert linha["tentativas"] == 1
        assert linha["erro"]
        assert linha["enviar_a_partir_de"] == _iso(SEGUNDA_10H + timedelta(minutes=5))

    def test_o_provedor_que_explode_tambem_volta_a_fila(self, caixa):
        caixa.explode = True
        banco = _banco()

        emails.despachar_se_puder(banco, _registrar(banco), SEGUNDA_10H)

        assert _linha(banco)["situacao"] == "pendente"
        assert "RuntimeError" in _linha(banco)["erro"]

    def test_o_job_espera_a_vez_e_tenta_de_novo_com_espera_crescente(self, caixa):
        caixa.falhas = 2
        banco = _banco()
        emails.despachar_se_puder(banco, _registrar(banco), SEGUNDA_10H)

        assert emails.despachar_pendentes(banco, SEGUNDA_10H + timedelta(minutes=4)) == {"enviados": 0, "falhas": 0}
        assert emails.despachar_pendentes(banco, SEGUNDA_10H + timedelta(minutes=5)) == {"enviados": 0, "falhas": 1}
        assert _linha(banco)["enviar_a_partir_de"] == _iso(SEGUNDA_10H + timedelta(minutes=20))
        assert emails.despachar_pendentes(banco, SEGUNDA_10H + timedelta(minutes=20)) == {"enviados": 1, "falhas": 0}

        assert _para(caixa) == ["p2@hsm.test"]
        assert _linha(banco)["situacao"] == "enviado"
        assert _linha(banco)["tentativas"] == 3

    def test_a_terceira_falha_vira_falha_e_avisa_o_admin_tecnico(self, caixa):
        caixa.falhas = 3
        banco = _banco()
        emails.despachar_se_puder(banco, _registrar(banco), SEGUNDA_10H)
        emails.despachar_pendentes(banco, SEGUNDA_10H + timedelta(minutes=5))

        emails.despachar_pendentes(banco, SEGUNDA_10H + timedelta(minutes=20))

        linha = _linha(banco)
        assert linha["situacao"] == "falhou"
        assert linha["tentativas"] == 3
        assert _para(caixa) == ["sa1@hsm.test"]
        alerta = caixa.saidas[0]
        assert "Núcleo" in alerta["assunto"]
        assert linha["id"] in alerta["texto"]
        # Nada do conteúdo do e-mail que falhou vai ao admin.
        assert "31/01/2027" not in alerta["texto"]

    def test_o_registro_que_falhou_nao_volta_mais(self, caixa):
        caixa.falhas = 3
        banco = _banco()
        emails.despachar_se_puder(banco, _registrar(banco), SEGUNDA_10H)
        for minutos in (5, 20):
            emails.despachar_pendentes(banco, SEGUNDA_10H + timedelta(minutes=minutos))
        caixa.saidas.clear()

        assert emails.despachar_pendentes(banco, SEGUNDA_10H + timedelta(days=1)) == {"enviados": 0, "falhas": 0}
        assert caixa.saidas == []

    def test_a_pessoa_sem_email_vira_falha_sem_insistir_e_sem_alerta(self, caixa):
        banco = _banco()
        banco.tabelas["participantes"][0]["email"] = None

        emails.despachar_se_puder(banco, _registrar(banco), SEGUNDA_10H)

        assert _linha(banco)["situacao"] == "falhou"
        assert _linha(banco)["erro"] == "A pessoa não tem e-mail no cadastro."
        assert caixa.saidas == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. O job não manda o mesmo registro duas vezes
# ═══════════════════════════════════════════════════════════════════════════


class TestReivindicacao:
    def test_a_rodada_que_cruza_com_outra_nao_manda_de_novo(self, caixa):
        banco = _banco()
        _registrar(banco)
        # Durante a chamada ao provedor, outra rodada do job lê a fila.
        caixa.durante = lambda: (setattr(caixa, "durante", None), emails.despachar_pendentes(banco, SEGUNDA_10H))

        emails.despachar_pendentes(banco, SEGUNDA_10H)

        assert _para(caixa) == ["p2@hsm.test"]

    def test_a_leitura_velha_do_mesmo_registro_nao_manda_de_novo(self, caixa):
        banco = _banco()
        registro = _registrar(banco)
        emails.despachar_se_puder(banco, registro, SEGUNDA_10H)

        assert emails.despachar_se_puder(banco, registro, SEGUNDA_10H) is False
        assert _para(caixa) == ["p2@hsm.test"]

    def test_o_registro_antigo_sem_mensagem_nao_entra_na_fila(self, caixa):
        """A linha da Fase 1 que ficou pendente não tem o que mandar."""
        banco = _banco()
        banco.tabelas["nsp_avisos"].append(
            {"id": "velho", "marco": "assinatura_3", "situacao": "pendente", "destinatario_id": "P2"}
        )

        assert emails.despachar_pendentes(banco, SEGUNDA_10H) == {"enviados": 0, "falhas": 0}
        assert caixa.saidas == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. Urgente sai na hora; os demais esperam a janela comercial
# ═══════════════════════════════════════════════════════════════════════════


class TestJanelaComercial:
    def test_o_urgente_sai_na_hora_no_sabado_a_noite(self, caixa):
        banco = _banco()

        assert emails.despachar_se_puder(banco, _registrar(banco, SABADO_22H, urgente=True), SABADO_22H) is True

        assert _para(caixa) == ["p2@hsm.test"]

    def test_o_nao_urgente_do_sabado_a_noite_espera_a_segunda_as_8h(self, caixa):
        banco = _banco()

        assert emails.despachar_se_puder(banco, _registrar(banco, SABADO_22H), SABADO_22H) is False
        assert _linha(banco)["enviar_a_partir_de"] == _iso(SEGUNDA_8H)
        assert emails.despachar_pendentes(banco, SEGUNDA_8H - timedelta(minutes=10)) == {"enviados": 0, "falhas": 0}
        assert caixa.saidas == []

        assert emails.despachar_pendentes(banco, SEGUNDA_8H) == {"enviados": 1, "falhas": 0}
        assert _para(caixa) == ["p2@hsm.test"]

    def test_o_feriado_tambem_segura_o_nao_urgente(self, caixa):
        banco = _banco()
        _registrar(banco, SABADO_22H, feriados=frozenset({date(2026, 11, 16)}))

        assert _linha(banco)["enviar_a_partir_de"] == _iso(SEGUNDA_8H + timedelta(days=1))

    def test_o_nao_urgente_dentro_do_expediente_sai_na_hora(self, caixa):
        banco = _banco()

        assert emails.despachar_se_puder(banco, _registrar(banco), SEGUNDA_10H) is True


# ═══════════════════════════════════════════════════════════════════════════
# O job de 10 em 10 minutos
# ═══════════════════════════════════════════════════════════════════════════


class TestJob:
    def test_o_job_roda_a_cada_10_minutos(self):
        assert re.search(
            r"despachar_emails_nsp,\s*\"interval\",\s*minutes=10", inspect.getsource(scheduler.start_scheduler)
        )

    def test_o_job_chama_o_registro_com_o_banco(self, monkeypatch):
        chamadas: list = []
        monkeypatch.setattr(scheduler, "_supabase", lambda: "banco")
        monkeypatch.setattr(
            emails, "despachar_pendentes", lambda banco, agora: chamadas.append((banco, agora)) or {"enviados": 1}
        )

        scheduler.despachar_emails_nsp()

        assert [banco for banco, _ in chamadas] == ["banco"]

    def test_o_job_que_falha_nao_derruba_o_scheduler(self, monkeypatch):
        monkeypatch.setattr(scheduler, "_supabase", lambda: "banco")

        def _explode(*_a):
            raise RuntimeError("banco fora do ar")

        monkeypatch.setattr(emails, "despachar_pendentes", _explode)

        scheduler.despachar_emails_nsp()
