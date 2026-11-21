"""O caso que a Ouvidoria manda ao Núcleo vira notificação (issue #1997, PRD
#1979, ADR 0107 decisão 7).

Confirmar o envio ao Núcleo na Ouvidoria cria, na mesma operação, a
notificação de origem Ouvidoria, com o relato integral, a justificativa
técnica, o setor por id e o vínculo à manifestação, sem quem manifestou. O
e-mail de ciência abre o caso no módulo, com login, e abrir o caso marca o
Recebido. A página por token deixa de mostrar o relato. Cada lado vê, numa
palavra, em que pé está o outro.

O banco é o dublê da validação (`test_ouvidoria_validacao_acionamento`), com a
notificação do Núcleo como o banco de verdade a grava: protocolo no insert e
uma notificação por manifestação (índice único da migration 183).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_ouvidoria_nucleo_seguranca_paciente import (  # noqa: E402
    JUSTIFICATIVA_TECNICA,
    NUCLEO,
    RELATO,
    _caso,
    _caso_apontado,
    _responsavel,
    _validar,
)
from test_ouvidoria_validacao_acionamento import (  # noqa: E402
    DENTRO_DO_EXPEDIENTE,
    OUVIDOR,
    _SupabaseFake,
    _TabelaFake,
)

from app import dependencies  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import RequestContextMiddleware  # noqa: E402
from app.routers import ouvidoria as ouvidoria_router  # noqa: E402
from app.routers import ouvidoria_setor as ouvidoria_setor_router  # noqa: E402
from app.routers import seguranca_do_paciente_notificacoes as nsp_router  # noqa: E402
from app.services import ouvidoria_acionamentos, ouvidoria_notificacoes  # noqa: E402

SETOR_ID = "11111111-1111-1111-1111-111111111111"
MEMBRO_DO_NUCLEO = {"id": "P20", "nome_completo": "Dra. Marta Membro", "email": "marta@hsm.br", "ativo": True}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def emails(monkeypatch) -> list[dict]:
    enviados: list[dict] = []

    def _fake(destinatario, assunto, html, texto=None, **_kwargs):
        enviados.append({"destinatario": destinatario, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(ouvidoria_notificacoes, "_enviar_email", _fake)
    return enviados


# =====================================================================
# O dublê do banco, com a notificação do Núcleo
# =====================================================================


class _TabelaComIn(_TabelaFake):
    """O `in_` do PostgREST, que a lista do Núcleo usa para ler os setores e
    as manifestações de uma vez."""

    def __init__(self, nome: str, rows: list[dict]):
        super().__init__(nome, rows)
        self._dentro: dict[str, list] = {}

    def in_(self, coluna, valores):
        self._dentro[coluna] = list(valores)
        return self

    def execute(self):
        if not self._dentro or self._insert is not None:
            return super().execute()
        todas = self.rows
        self.rows = [r for r in todas if all(r.get(c) in v for c, v in self._dentro.items())]
        try:
            return super().execute()
        finally:
            self.rows = todas


class _NotificacoesDoNucleo(_TabelaComIn):
    """O que o banco faz no insert da notificação: o protocolo (migration 174)
    e a recusa da segunda notificação da mesma manifestação (migration 183)."""

    def execute(self):
        if self._insert is not None:
            linha = self._insert
            if linha.get("manifestacao_id") and any(
                r.get("manifestacao_id") == linha["manifestacao_id"] for r in self.rows
            ):
                raise APIError({"code": "23505", "message": "duplicate key value violates unique constraint"})
            numero = len(self.rows) + 1
            self._insert = {
                "estado": "recebida",
                **linha,
                "numero": numero,
                "protocolo": f"NSP-2026-{numero:04d}",
                "criado_em": "2026-08-17T13:00:00+00:00",
            }
        return super().execute()


class _Banco(_SupabaseFake):
    def table(self, nome: str):
        if nome in self.indisponiveis:
            return super().table(nome)
        if nome == "nsp_notificacoes":
            return _NotificacoesDoNucleo(nome, self.tabelas.setdefault(nome, []))
        if nome in ("setores", "ouvidoria_protocolos"):
            return _TabelaComIn(nome, self.tabelas.setdefault(nome, []))
        return super().table(nome)

    @property
    def notificacoes_do_nucleo(self) -> list[dict]:
        return self.tabelas.get("nsp_notificacoes", [])


def _banco(caso: dict | None = None) -> _Banco:
    supabase = _Banco(
        [caso if caso is not None else _caso(setor_id=SETOR_ID)],
        responsaveis=[
            _responsavel(),
            _responsavel("titular", id="resp-nsp", setor=NUCLEO, nome="Dra. Helena Presidente", email="nsp@hsm.br"),
        ],
    )
    supabase.tabelas["setores"].append({"id": SETOR_ID, "nome": "Recepcao", "ativo": True})
    supabase.tabelas["ouvidoria_config"] = [{"id": True, "nsp_setor": NUCLEO}]
    return supabase


def _client(monkeypatch, supabase: _Banco | None = None, recursos=("casos",)):
    """O painel do ouvidor, o link do email e o módulo do Núcleo no mesmo app.
    A permissão do Núcleo é a da pessoa logada no módulo (`recursos`)."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(ouvidoria_router.router, prefix="/api")
    app.include_router(ouvidoria_setor_router.router, prefix="/api")
    app.include_router(nsp_router.router, prefix="/api")

    supabase = supabase if supabase is not None else _banco()

    async def _ouvidor(_user, _sb, fields=None):
        return OUVIDOR

    async def _membro(_user, _sb, fields=None):
        return MEMBRO_DO_NUCLEO

    monkeypatch.setattr(ouvidoria_router, "get_participante_for_user", _ouvidor)
    monkeypatch.setattr(dependencies, "get_participante_for_user", _membro)
    monkeypatch.setattr(dependencies, "recursos_nsp_da_pessoa", lambda _sb, _me: frozenset(recursos))
    monkeypatch.setattr(ouvidoria_router, "agora_utc", lambda: DENTRO_DO_EXPEDIENTE)
    monkeypatch.setattr(ouvidoria_setor_router, "agora_utc", lambda: DENTRO_DO_EXPEDIENTE)
    monkeypatch.setattr(nsp_router, "agora_utc", lambda: DENTRO_DO_EXPEDIENTE, raising=False)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "email": "u@hsm.br"}
    app.dependency_overrides[get_supabase_client] = lambda: supabase
    return TestClient(app), supabase


def _enviar_ao_nucleo(client):
    return client.post("/api/ouvidoria/manifestacoes/uuid-7/nsp")


def _ciencia(supabase) -> dict:
    ciencias = [a for a in supabase.tabelas.get("ouvidoria_acionamentos", []) if a.get("motivo_ciencia") == "nsp"]
    assert len(ciencias) == 1
    return ciencias[0]


# =====================================================================
# 1. Confirmar o envio cria a notificação; confirmar de novo não duplica
# =====================================================================


class TestConfirmarOEnvioCriaANotificacao:
    def test_enviar_ao_nsp_cria_a_notificacao_de_origem_ouvidoria_com_o_relato(self, monkeypatch):
        caso = _caso(setor_id=SETOR_ID, nsp_justificativa_tecnica=JUSTIFICATIVA_TECNICA)
        client, supabase = _client(monkeypatch, _banco(caso))

        r = _enviar_ao_nucleo(client)

        assert r.status_code == 200, r.text
        assert len(supabase.notificacoes_do_nucleo) == 1
        notificacao = supabase.notificacoes_do_nucleo[0]
        assert notificacao["origem"] == "ouvidoria"
        assert notificacao["manifestacao_id"] == "uuid-7"
        assert notificacao["relato"] == RELATO
        assert notificacao["justificativa_tecnica"] == JUSTIFICATIVA_TECNICA
        assert notificacao["setor_id"] == SETOR_ID
        assert notificacao["anonimo"] is False

    def test_confirmar_o_envio_na_validacao_tambem_cria_a_notificacao(self, monkeypatch):
        client, supabase = _client(monkeypatch, _banco(_caso_apontado(setor_id=SETOR_ID)))

        r = _validar(client, nsp_decisao="confirmado")

        assert r.status_code == 200, r.text
        assert [n["manifestacao_id"] for n in supabase.notificacoes_do_nucleo] == ["uuid-7"]
        assert supabase.notificacoes_do_nucleo[0]["justificativa_tecnica"] == JUSTIFICATIVA_TECNICA

    def test_confirmar_de_novo_nao_cria_outra_notificacao(self, monkeypatch):
        client, supabase = _client(monkeypatch)
        assert _enviar_ao_nucleo(client).status_code == 200

        de_novo = _enviar_ao_nucleo(client)

        assert de_novo.status_code == 409
        assert len(supabase.notificacoes_do_nucleo) == 1

    def test_a_nova_tentativa_de_um_envio_pela_metade_reusa_a_notificacao(self, monkeypatch, emails):
        """A notificação e a ciência gravaram, e a decisão não: a nova
        tentativa termina o envio com a mesma notificação."""
        supabase = _BancoQueFalhaNaDecisao(
            [_caso(setor_id=SETOR_ID)], responsaveis=_banco().tabelas["ouvidoria_setor_responsaveis"]
        )
        supabase.tabelas["ouvidoria_config"] = [{"id": True, "nsp_setor": NUCLEO}]
        client, supabase = _client(monkeypatch, supabase)

        assert _enviar_ao_nucleo(client).status_code == 500
        segunda = _enviar_ao_nucleo(client)

        assert segunda.status_code == 200, segunda.text
        assert len(supabase.notificacoes_do_nucleo) == 1
        assert supabase.tabelas["ouvidoria_protocolos"][0]["nsp_decisao"] == "confirmado"


class _BancoQueFalhaNaDecisao(_Banco):
    """A segunda ciência do caso é recusada (índice da migration 139), e o
    update da decisão estoura uma vez, como o PostgREST em timeout."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.falhas_da_decisao = 1

    def table(self, nome: str):
        tabela = super().table(nome)
        if nome == "ouvidoria_acionamentos":
            insert_original = tabela.insert

            def _insert(payload):
                if payload.get("motivo_ciencia") == "nsp" and any(
                    a.get("motivo_ciencia") == "nsp" for a in tabela.rows
                ):
                    raise APIError({"code": "23505", "message": "duplicate key value violates unique constraint"})
                return insert_original(payload)

            tabela.insert = _insert
        if nome == "ouvidoria_protocolos":
            update_original = tabela.update

            def _update(payload: dict):
                if "nsp_decisao" in payload and self.falhas_da_decisao:
                    self.falhas_da_decisao -= 1
                    raise APIError({"code": "57014", "message": "canceling statement due to statement timeout"})
                return update_original(payload)

            tabela.update = _update
        return tabela


# =====================================================================
# 2. A notificação não traz nome nem contato de quem manifestou
# =====================================================================


class TestQuemManifestouNaoVai:
    def test_a_notificacao_nao_leva_o_nome_nem_o_contato_de_quem_manifestou(self, monkeypatch):
        caso = _caso(
            setor_id=SETOR_ID,
            manifestante_nome="Joana da Silva",
            manifestante_contato="joana@exemplo.com",
            manifestante_telefone="(31) 99999-0000",
        )
        client, supabase = _client(monkeypatch, _banco(caso))

        assert _enviar_ao_nucleo(client).status_code == 200

        notificacao = supabase.notificacoes_do_nucleo[0]
        assert notificacao.get("notificante_nome") is None
        assert notificacao.get("notificante_contato") is None
        assert notificacao.get("notificante_id") is None
        valores = " ".join(str(v) for v in notificacao.values())
        for dado in ("Joana da Silva", "joana@exemplo.com", "99999-0000"):
            assert dado not in valores

    def test_a_lista_do_nucleo_nao_mostra_quem_manifestou_nem_para_a_presidencia(self, monkeypatch):
        client, _supabase = _client(monkeypatch, recursos=("casos", "identidade_notificante"))
        assert _enviar_ao_nucleo(client).status_code == 200

        r = client.get("/api/nsp/notificacoes")

        assert r.status_code == 200, r.text
        assert "Joana da Silva" not in r.text
        assert r.json()["notificacoes"][0]["notificante"] is None
