"""O que acontece ao confirmar a triagem: a reunião de análise e os avisos
(issue #1994, PRD #1979, ADR 0107 decisão 1).

Um bloco por critério de aceite:

1. confirmar um caso A cria a reunião de análise Programada na data-limite,
   com o protocolo na pauta;
2. a lesão por pressão dos itens 8 a 10 sem óbito não cria reunião e entra na
   pauta da ordinária seguinte;
3. confirmar A ou B registra o aviso à Diretoria na hora; C, D e E não;
4. o identificado com e-mail recebe o aviso; o anônimo vê o estado novo na
   página de acompanhamento;
5. confirmar duas vezes o mesmo caso não cria segunda reunião nem segundo
   aviso;
6. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória dos testes da triagem e dos prazos, com o que a
migration 218 faz: uma reunião de análise por caso e um aviso por caso, marco
e destinatário. O e-mail é sempre dublado. As pessoas são de teste.

As datas são as dos testes de prazos: o caso chega na terça 10/11/2026 e a
triagem é confirmada na quinta 12/11 às 15h de São Paulo. A reunião de análise
da faixa A vence em 7 dias úteis da confirmação, na segunda 23/11.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_prazos import (  # noqa: E402
    DO_CASO,
    LESAO_POR_PRESSAO,
    _BancoDoNucleo,
    _ConsultaDoNucleo,
)
from test_seguranca_do_paciente_prazos import _banco as _banco_dos_prazos  # noqa: E402
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    OBITO,
    PRESIDENTE,
    TODOS_OS_CAMPOS,
    _notificacao,
    _sugestao,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_notificacoes as notificacoes_router  # noqa: E402
from app.routers import seguranca_do_paciente_reunioes as reunioes_router  # noqa: E402
from app.routers import seguranca_do_paciente_triagem as triagem_router  # noqa: E402
from app.services.seguranca_do_paciente import emails  # noqa: E402

SP = ZoneInfo("America/Sao_Paulo")
ANALISE_DE_EVENTO = "Análise de evento"
ORDINARIA = "Ordinária mensal"

# O que a migration 218 (e as anteriores) seguram no banco.
_UNICAS = {
    "reunioes": ("nsp_caso_id",),
    "nsp_pautas": ("id_reuniao",),
    "nsp_avisos": ("caso_id", "marco", "referencia", "destinatario_id"),
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def enviados(monkeypatch) -> list[dict[str, str]]:
    """O provedor de e-mail dublado: anota cada envio."""
    caixa: list[dict[str, str]] = []

    def _enviar(destino, assunto, html, texto, **_kw):
        caixa.append({"para": destino, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(emails, "_enviar_email", _enviar)
    return caixa


class _Consulta(_ConsultaDoNucleo):
    """O dublê dos prazos, com as chaves únicas do banco."""

    def _inserir(self) -> list[dict]:
        chave = _UNICAS.get(self._nome)
        if chave:
            novas = self._valores if isinstance(self._valores, list) else [self._valores]
            for valores in novas:
                if all(valores.get(c) is None for c in chave):
                    continue
                if any(all(linha.get(c) == valores.get(c) for c in chave) for linha in self._linhas):
                    raise APIError({"code": "23505", "message": "duplicate key value"})
        return super()._inserir()


class _Banco(_BancoDoNucleo):
    def table(self, nome: str):
        return _Consulta(self, nome)


def _banco(notificacoes: list[dict], triagens: list[dict]) -> _Banco:
    return _Banco(_banco_dos_prazos(notificacoes, triagens).tabelas)


def _cliente(banco, pessoa: dict[str, Any] = PRESIDENTE) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(triagem_router.router, prefix="/api")
    app.include_router(notificacoes_router.router, prefix="/api")
    app.include_router(reunioes_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _confirmar(banco, caso) -> None:
    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})
    assert resposta.status_code == 201, resposta.text


def _caso_confirmado(sugestao: dict, numero: int = 1, **campos) -> tuple[_Banco, dict]:
    caso = _notificacao(numero, **{**DO_CASO, **campos})
    banco = _banco([caso], [_sugestao(caso, **sugestao)])
    _confirmar(banco, caso)
    return banco, caso


def _reunioes(banco, tipo: str = ANALISE_DE_EVENTO) -> list[dict]:
    return [r for r in banco.tabelas.get("reunioes", []) if r.get("tipo") == tipo]


def _textos_da_pauta(banco, id_reuniao: str) -> list[str]:
    resposta = _cliente(banco).get(f"/api/nsp/reunioes/{id_reuniao}/pauta")
    assert resposta.status_code == 200, resposta.text
    return [item["texto"] for bloco in resposta.json()["blocos"] for item in bloco["itens"]]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Faixa A: a reunião de análise nasce Programada na data-limite
# ═══════════════════════════════════════════════════════════════════════════


def test_confirmar_um_caso_a_cria_a_reuniao_de_analise_programada_na_data_limite_com_o_protocolo_na_pauta():
    banco, caso = _caso_confirmado(OBITO)

    [reuniao] = _reunioes(banco)
    assert reuniao["status_ata"] == "PROGRAMADA"
    assert reuniao["data"] == "2026-11-23"
    assert reuniao["colegiado_id"] == "col-nsp"
    assert reuniao["nsp_caso_id"] == caso["id"]
    assert any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, reuniao["id_reuniao"]))
