"""Os avisos do Termo sem assinatura e do fim da vigência (issue #1770, PRD #1764).

O que a issue promete, um bloco por critério de aceite:

1. cada marco avisa os destinatários certos, e rodar o job duas vezes no
   mesmo dia não envia de novo;
2. o aviso de assinatura para depois que o membro assina;
3. os e-mails trazem data absoluta, destinatário nominal e nenhum travessão;
4. o job não chama IA;
5. a falha de envio fica registrada e não derruba os outros avisos do dia;
6. o texto do Produto no Kit de conhecimento diz o comportamento novo.

O banco é um dublê em memória e o e-mail é sempre dublado. Nenhum nome ou
e-mail de pessoa real: as pessoas daqui são de teste. As datas saem de um dia
fixo.
"""

from __future__ import annotations

import inspect
import os
import re
import sys
import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.cron import scheduler  # noqa: E402
from app.services.seguranca_do_paciente import avisos  # noqa: E402

DIA = date(2026, 11, 16)
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}

# A chave única de cada tabela, como a migration declara.
_UNICAS = {"nsp_avisos": ("participacao_id", "marco", "referencia", "destinatario_id")}


# ═══════════════════════════════════════════════════════════════════════════
# O dublê do banco e do e-mail
# ═══════════════════════════════════════════════════════════════════════════


class _Consulta:
    def __init__(self, banco: _Banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._linhas = banco.tabelas.setdefault(nome, [])
        self._filtros: list = []
        self._ordem: tuple[str, bool] | None = None
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

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) <= str(valor))
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) >= str(valor))
        return self

    def order(self, coluna, desc=False, **_kw):
        self._ordem = (coluna, desc)
        return self

    def limit(self, n):
        self._teto = n
        return self

    def range(self, inicio, fim):
        self._inicio, self._teto = inicio, fim - inicio + 1
        return self

    def execute(self):
        if self._acao == "insert":
            return SimpleNamespace(data=self._inserir())
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._acao == "update":
            for linha in casam:
                linha.update(self._valores)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        if self._ordem:
            coluna, desc = self._ordem
            casam.sort(key=lambda linha: (linha.get(coluna) is None, str(linha.get(coluna))), reverse=desc)
        casam = casam[self._inicio :]
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)

    def _inserir(self) -> list[dict]:
        novas = self._valores if isinstance(self._valores, list) else [self._valores]
        chave = _UNICAS.get(self._nome)
        prontas = []
        for valores in novas:
            linha = {"id": str(uuid.uuid4()), **valores}
            if chave and any(all(linha.get(c) == outra.get(c) for c in chave) for outra in self._linhas):
                raise APIError({"code": "23505", "message": "duplicate key value violates unique constraint"})
            prontas.append(linha)
        self._linhas.extend(prontas)
        return [dict(linha) for linha in prontas]


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def table(self, nome: str):
        return _Consulta(self, nome)


@pytest.fixture
def emails(monkeypatch):
    """O e-mail é sempre dublado: guarda o que sairia."""
    enviados: list[dict] = []

    def _falso(destinatario, assunto, html_content, texto_fallback, **_kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html_content, "texto": texto_fallback})
        return True

    monkeypatch.setattr(avisos, "_enviar_email", _falso)
    return enviados


# ═══════════════════════════════════════════════════════════════════════════
# Pessoas e cenário
# ═══════════════════════════════════════════════════════════════════════════


def _pessoa(pid: str, **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "nome_completo": f"Pessoa de Teste {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "ativo": True,
        "perfil_ouvidoria": None,
        "perfil_nsp": None,
        "role": None,
    }
    return {**base, **campos}


PRESIDENTE = _pessoa("P1")
MEMBRO = _pessoa("P2")
DIRETOR = _pessoa("P9", perfil_ouvidoria="diretoria_executiva")


def _participacao(participante: str, papel: str = "membro", **campos) -> dict[str, Any]:
    """Vigente em DIA, com o Termo assinado e o fim longe."""
    base = {
        "id": f"part-{participante}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": participante,
        "papel": papel,
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": (DIA + timedelta(days=300)).isoformat(),
        "encerrada_em": None,
        "termo_gerado_em": "2025-01-02T12:00:00+00:00",
        "termo_enviado_em": "2025-01-02T12:00:00+00:00",
        "termo_assinado_em": "2025-01-03T12:00:00+00:00",
    }
    return {**base, **campos}


def _sem_assinatura(participante: str, gerado_em: date) -> tuple[dict, dict]:
    """A Participação esperando a assinatura, e o envio aberto do Termo,
    gerado ao meio-dia (horário de Brasília) do dia `gerado_em`."""
    carimbo = f"{gerado_em.isoformat()}T15:00:00+00:00"
    participacao = _participacao(
        participante, termo_gerado_em=carimbo, termo_enviado_em=carimbo, termo_assinado_em=None
    )
    envio = {
        "id": f"envio-{participante}",
        "participacao_id": participacao["id"],
        "situacao": "enviado",
        "created_at": carimbo,
    }
    return participacao, envio


def _banco(participacoes: list[dict], envios: list[dict] | None = None, pessoas: list[dict] | None = None) -> _Banco:
    return _Banco(
        {
            "participantes": [dict(p) for p in (pessoas or [PRESIDENTE, MEMBRO, DIRETOR])],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [_participacao("P1", "presidencia", vigencia_fim=(DIA + timedelta(days=800)).isoformat())]
            + [dict(p) for p in participacoes],
            "nsp_termos_envios": [dict(e) for e in (envios or [])],
            "nsp_avisos": [],
        }
    )


def _para(emails: list[dict]) -> list[str]:
    return sorted(e["para"] for e in emails)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Cada marco avisa os destinatários certos, uma vez só
# ═══════════════════════════════════════════════════════════════════════════


class TestMarcos:
    def test_tres_dias_sem_assinatura_avisa_o_membro(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=3))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p2@hsm.test"]
        assert emails[0]["assunto"].startswith("Assine o Termo de Adesão")

    @pytest.mark.parametrize(
        ("dias", "assunto"),
        [
            (0, "gerado em"),
            (7, "pendente desde"),
        ],
    )
    def test_documento_gerado_e_sete_dias_avisam_so_o_membro(self, emails, dias, assunto):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=dias))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p2@hsm.test"]
        assert assunto in emails[0]["assunto"]

    def test_quatorze_dias_sem_assinatura_avisam_o_membro_e_a_presidencia(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=14))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p1@hsm.test", "p2@hsm.test"]
        para_presidencia = next(e for e in emails if e["para"] == "p1@hsm.test")
        assert para_presidencia["assunto"].startswith("Cobre a assinatura do Termo de Adesão de Pessoa de Teste P2")

    def test_dois_dias_depois_do_documento_gerado_nada_novo_sai(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=2))
        banco = _banco([participacao], [envio])
        avisos.avisar(banco, DIA - timedelta(days=2))
        emails.clear()

        avisos.avisar(banco, DIA)

        assert emails == []

    def test_o_job_parado_uns_dias_manda_so_o_marco_mais_adiantado(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=8))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert len(emails) == 1
        assert [a["marco"] for a in banco.tabelas["nsp_avisos"]] == ["assinatura_7"]

    @pytest.mark.parametrize("faltam", [60, 30])
    def test_sessenta_e_trinta_dias_do_fim_avisam_o_membro_e_a_presidencia(self, emails, faltam):
        banco = _banco([_participacao("P2", vigencia_fim=(DIA + timedelta(days=faltam)).isoformat())])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p1@hsm.test", "p2@hsm.test"]
        fim = (DIA + timedelta(days=faltam)).strftime("%d/%m/%Y")
        assert all(fim in e["assunto"] for e in emails)

    def test_sessenta_e_um_dias_do_fim_ainda_nao_avisam(self, emails):
        banco = _banco([_participacao("P2", vigencia_fim=(DIA + timedelta(days=61)).isoformat())])

        avisos.avisar(banco, DIA)

        assert emails == []

    def test_o_aviso_de_trinta_dias_vem_depois_do_de_sessenta(self, emails):
        fim = DIA + timedelta(days=30)
        banco = _banco([_participacao("P2", vigencia_fim=fim.isoformat())])
        avisos.avisar(banco, fim - timedelta(days=60))

        avisos.avisar(banco, DIA)

        marcos = sorted({a["marco"] for a in banco.tabelas["nsp_avisos"]})
        assert marcos == ["vigencia_30", "vigencia_60"]
        assert len(emails) == 4

    def test_fim_da_carencia_sem_renovacao_avisa_a_presidencia_e_a_diretoria_executiva(self, emails):
        fim = DIA - timedelta(days=31)
        banco = _banco([_participacao("P2", vigencia_fim=fim.isoformat())])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p1@hsm.test", "p9@hsm.test"]
        fim_da_carencia = (fim + timedelta(days=30)).strftime("%d/%m/%Y")
        assert all(fim_da_carencia in e["assunto"] for e in emails)

    def test_o_ultimo_dia_da_carencia_ainda_nao_avisa(self, emails):
        banco = _banco([_participacao("P2", vigencia_fim=(DIA - timedelta(days=30)).isoformat())])

        avisos.avisar(banco, DIA)

        assert emails == []

    def test_participacao_encerrada_nao_recebe_aviso(self, emails):
        fim = DIA + timedelta(days=30)
        banco = _banco([_participacao("P2", vigencia_fim=fim.isoformat(), encerrada_em=fim.isoformat())])

        avisos.avisar(banco, DIA)

        assert emails == []

    def test_a_presidencia_que_e_o_proprio_membro_recebe_um_aviso_so(self, emails):
        banco = _banco([])
        banco.tabelas["participacoes"][0]["vigencia_fim"] = (DIA + timedelta(days=30)).isoformat()

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p1@hsm.test"]
        assert emails[0]["assunto"].startswith("Renove a sua participação")

    def test_rodar_duas_vezes_no_mesmo_dia_nao_envia_de_novo(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=14))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)
        primeira = len(emails)
        segunda = avisos.avisar(banco, DIA)

        assert primeira == 2
        assert len(emails) == primeira
        assert segunda == {"enviados": 0, "falhas": 0}

    def test_cada_aviso_nasce_registrado_e_nominal(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=14))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        registros = banco.tabelas["nsp_avisos"]
        assert sorted(a["destinatario_id"] for a in registros) == ["P1", "P2"]
        assert {a["situacao"] for a in registros} == {"enviado"}

    def test_a_renovacao_recomeca_os_avisos_da_vigencia(self, emails):
        banco = _banco([_participacao("P2", vigencia_fim=(DIA + timedelta(days=30)).isoformat())])
        avisos.avisar(banco, DIA)
        banco.tabelas["participacoes"][1]["vigencia_fim"] = (DIA + timedelta(days=395)).isoformat()
        emails.clear()

        avisos.avisar(banco, DIA + timedelta(days=365))

        assert _para(emails) == ["p1@hsm.test", "p2@hsm.test"]

    def test_o_reenvio_do_termo_recomeca_a_contagem(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=3))
        banco = _banco([participacao], [envio])
        avisos.avisar(banco, DIA)
        banco.tabelas["nsp_termos_envios"][0]["situacao"] = "cancelado"
        banco.tabelas["nsp_termos_envios"].append(
            {**envio, "id": "envio-novo", "created_at": f"{(DIA + timedelta(days=1)).isoformat()}T15:00:00+00:00"}
        )
        emails.clear()

        avisos.avisar(banco, DIA + timedelta(days=4))

        assert _para(emails) == ["p2@hsm.test"]
        assert (DIA + timedelta(days=1)).strftime("%d/%m/%Y") in emails[0]["assunto"]
