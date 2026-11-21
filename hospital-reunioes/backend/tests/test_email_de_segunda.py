"""O e-mail de segunda (issue #1876; Refino 19 e decisões 20, 21, 23, 27, 64 e
68 do diretor no PRD #1757).

Toda segunda, de hora em hora das 8h às 12h, o job manda um e-mail por pessoa:
ao Facilitador, o que foi concluído, atualizado e repactuado na semana nas
Reuniões dele, mais o que segue atrasado; ao responsável, só as Pendências
dele em aberto; a quem é as duas coisas, um e-mail com as duas partes. Quem não
tem nada para ver não recebe. A guarda por pessoa e por semana fica no banco,
e o modo de teste do e-mail (sem transporte) não marca como enviado.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.cron import scheduler as cron  # noqa: E402
from app.services import email_de_segunda  # noqa: E402

# Segunda, 23/11/2026: a semana que passou vai de 16/11 a 22/11.
SEGUNDA = date(2026, 11, 23)
PROXIMA_SEGUNDA = date(2026, 11, 30)
ATRASADA = "2026-11-20"
NO_PRAZO = "2026-12-10"


# ─── O banco de mentira ──────────────────────────────────────────────────────


@dataclass
class _Result:
    data: list


class _Negacao:
    def __init__(self, consulta):
        self._consulta = consulta

    def is_(self, coluna, valor):
        assert valor == "null"
        self._consulta._filtros.append(lambda linha: linha.get(coluna) is not None)
        return self._consulta


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []
        self._recorte: tuple[int, int] | None = None
        self._upsert = None
        self._apagar = False

    @property
    def not_(self):
        return _Negacao(self)

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) == str(valor))
        return self

    def in_(self, coluna, valores):
        valores = set(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) >= str(valor))
        return self

    def lt(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) < str(valor))
        return self

    def order(self, *_a, **_kw):
        return self

    def range(self, inicio, fim):
        self._recorte = (inicio, fim)
        return self

    def upsert(self, linhas, *, on_conflict, ignore_duplicates=False):
        assert ignore_duplicates
        self._upsert = (linhas, on_conflict.split(","))
        return self

    def delete(self):
        self._apagar = True
        return self

    def execute(self):
        if self._upsert is not None:
            novas, chave = self._upsert
            gravadas = []
            for nova in novas:
                if not any(all(str(v.get(c)) == str(nova.get(c)) for c in chave) for v in self._linhas):
                    self._linhas.append(dict(nova))
                    gravadas.append(dict(nova))
            return _Result(gravadas)
        achadas = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._apagar:
            for linha in achadas:
                self._linhas.remove(linha)
            return _Result([dict(linha) for linha in achadas])
        linhas = [dict(linha) for linha in achadas]
        if self._recorte is not None:
            inicio, fim = self._recorte
            linhas = linhas[inicio : fim + 1]
        return _Result(linhas)


@dataclass
class _Banco:
    participantes: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    pendencias: list = field(default_factory=list)
    pendencia_historico: list = field(default_factory=list)
    email_de_segunda: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


def _pessoa(pid, nome, *, perfil="regular", email=True, ativo=True) -> dict:
    return {
        "id": pid,
        "nome_completo": nome,
        "email": f"{pid.lower()}@hsm.test" if email else None,
        "access_profile": perfil,
        "ativo": ativo,
    }


def _reuniao(id_reuniao, facilitador_id, titulo) -> dict:
    return {"id_reuniao": id_reuniao, "titulo": titulo, "facilitador_id": facilitador_id, "deleted_at": None}


def _pendencia(id_acao, descricao, responsavel_id, *, id_reuniao, status="PENDENTE", prazo=NO_PRAZO, co=None):
    return {
        "id_acao": id_acao,
        "id_reuniao": id_reuniao,
        "descricao_acao": descricao,
        "responsavel_id": responsavel_id,
        "co_responsavel_id": co,
        "responsavel_nome": f"Nome {responsavel_id}",
        "status": status,
        "prazo": prazo,
        "deleted_at": None,
    }


def _evento(id_acao, comando, criado_em, anotacao="Anotado.", *, prazo_depois=None) -> dict:
    return {
        "id_acao": id_acao,
        "comando": comando,
        "anotacao": anotacao,
        "criado_em": criado_em,
        "prazo_depois": prazo_depois,
    }


@pytest.fixture
def job(monkeypatch):
    """O job de segunda, com o banco de mentira e o e-mail capturado."""
    estado: dict = {"banco": _Banco(), "hoje": SEGUNDA, "enviados": [], "falhar": False, "transporte": True}

    def _enviar(destinatario, assunto, html_content, texto_fallback, *a, **kw):
        estado["enviados"].append(
            {"para": destinatario, "assunto": assunto, "html": html_content, "texto": texto_fallback}
        )
        return not estado["falhar"]

    monkeypatch.setattr(cron, "_supabase", lambda: estado["banco"])
    monkeypatch.setattr(cron, "_hoje", lambda: estado["hoje"])
    monkeypatch.setattr(email_de_segunda, "_enviar_email", _enviar)
    monkeypatch.setattr(email_de_segunda, "transporte_configurado", lambda: estado["transporte"])
    monkeypatch.setattr(email_de_segunda, "reunioes_do_nucleo", lambda _sb: [])

    def rodar():
        cron.enviar_email_de_segunda()

    return rodar, estado


def _so_responsavel(banco: _Banco) -> _Banco:
    """Bruno é responsável por uma Pendência aberta de uma Reunião que Fábio facilita."""
    banco.participantes = [_pessoa("P_FABIO", "Fábio Lima"), _pessoa("P_BRUNO", "Bruno Reis")]
    banco.reunioes = [_reuniao("R1", "P_FABIO", "Reunião da UTI")]
    banco.pendencias = [_pendencia("A1", "Trocar o monitor do leito 4", "P_BRUNO", id_reuniao="R1")]
    return banco


def _para(estado, pid) -> list[dict]:
    return [e for e in estado["enviados"] if e["para"] == f"{pid.lower()}@hsm.test"]


# ─── 1. Um e-mail só por pessoa e por semana ─────────────────────────────────


def test_rodar_o_job_varias_vezes_na_mesma_segunda_manda_um_email_so_por_pessoa(job):
    rodar, estado = job
    _so_responsavel(estado["banco"])

    for _ in range(5):
        rodar()

    assert len(_para(estado, "P_BRUNO")) == 1
    # A segunda seguinte é outra semana, e ganha o e-mail dela.
    estado["hoje"] = PROXIMA_SEGUNDA
    rodar()
    rodar()
    assert len(_para(estado, "P_BRUNO")) == 2
