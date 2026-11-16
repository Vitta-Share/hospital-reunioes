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
            "participacoes": [_participacao("P1", "presidencia")] + [dict(p) for p in participacoes],
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
