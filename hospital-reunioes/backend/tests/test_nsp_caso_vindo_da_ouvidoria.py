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
import uuid
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
from app.services import ouvidoria_acionamentos, ouvidoria_notificacoes, ouvidoria_nucleo  # noqa: E402

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
                "id": str(uuid.uuid4()),
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


# =====================================================================
# 3. O e-mail abre o caso no módulo, com login, e abrir marca o Recebido
# =====================================================================


def _email_do_nucleo(emails: list[dict]) -> dict:
    do_nucleo = [e for e in emails if e["destinatario"] == "nsp@hsm.br"]
    assert len(do_nucleo) == 1
    return do_nucleo[0]


def _abrir_o_caso(client, caso_id: str):
    return client.get(f"/api/nsp/notificacoes/{caso_id}")


class TestOEmailAbreOCasoNoModulo:
    def test_o_email_de_ciencia_leva_ao_caso_no_modulo_e_nao_ao_link_sem_senha(self, monkeypatch, emails):
        client, supabase = _client(monkeypatch)

        assert _enviar_ao_nucleo(client).status_code == 200

        caso_id = supabase.notificacoes_do_nucleo[0]["id"]
        email = _email_do_nucleo(emails)
        for corpo in (email["html"], email["texto"]):
            assert f"/seguranca-do-paciente/notificacoes/{caso_id}" in corpo
            assert "/ouvidoria-setor/nsp/" not in corpo
            assert "sem senha" not in corpo
            assert RELATO not in corpo
        assert "login" in email["texto"]

    def test_abrir_o_caso_no_modulo_marca_o_recebido_com_o_nome_de_quem_abriu(self, monkeypatch):
        client, supabase = _client(monkeypatch)
        assert _enviar_ao_nucleo(client).status_code == 200
        caso_id = supabase.notificacoes_do_nucleo[0]["id"]

        r = _abrir_o_caso(client, caso_id)

        assert r.status_code == 200, r.text
        assert r.json()["relato"] == RELATO
        ciencia = _ciencia(supabase)
        assert ciencia["status"] == "ciente"
        assert ciencia["respondido_em"] == DENTRO_DO_EXPEDIENTE.isoformat()
        trilha = [m["observacao"] for m in supabase.tabelas["ouvidoria_movimentos"]]
        assert any(o.startswith("Recebido pelo NSP: Dra. Marta Membro") for o in trilha), trilha

    def test_abrir_o_caso_de_novo_nao_registra_outro_recebido(self, monkeypatch):
        client, supabase = _client(monkeypatch)
        assert _enviar_ao_nucleo(client).status_code == 200
        caso_id = supabase.notificacoes_do_nucleo[0]["id"]

        assert _abrir_o_caso(client, caso_id).status_code == 200
        assert _abrir_o_caso(client, caso_id).status_code == 200

        recebidos = [m for m in supabase.tabelas["ouvidoria_movimentos"] if "Recebido pelo NSP" in m["observacao"]]
        assert len(recebidos) == 1

    def test_quem_nao_tem_o_recurso_de_casos_nao_abre_nem_marca_o_recebido(self, monkeypatch):
        client, supabase = _client(monkeypatch, recursos=("ver_modulo",))
        assert _enviar_ao_nucleo(client).status_code == 200
        caso_id = supabase.notificacoes_do_nucleo[0]["id"]

        r = _abrir_o_caso(client, caso_id)

        assert r.status_code == 403
        assert _ciencia(supabase)["status"] == "pendente"

    def test_caso_que_nao_existe_responde_404(self, monkeypatch):
        client, _supabase = _client(monkeypatch)

        assert _abrir_o_caso(client, "33333333-3333-3333-3333-333333333333").status_code == 404

    def test_o_caso_sem_notificacao_no_modulo_recebe_o_link_sem_senha_com_o_texto_dele(self, monkeypatch, emails):
        """O caso confirmado antes da Fase 2 não foi importado ao módulo: a
        ciência dele (na fila, na retentativa ou no Reenviar) ainda sai com o
        link por token. O texto não pode prometer o login nem o Recebido ao
        abrir, que lá não valem: o Recebido é o botão da tela."""
        monkeypatch.setattr(ouvidoria_nucleo, "criar_a_notificacao_do_nucleo", lambda _sb, _manifestacao_id, _agora: {})
        client, supabase = _client(monkeypatch)

        assert _enviar_ao_nucleo(client).status_code == 200

        assert supabase.notificacoes_do_nucleo == []
        email = _email_do_nucleo(emails)
        for corpo in (email["html"], email["texto"]):
            assert re.search(r"/ouvidoria-setor/nsp/[A-Za-z0-9_-]{20,}", corpo), corpo
            assert "/seguranca-do-paciente/notificacoes/" not in corpo
            assert "login" not in corpo
            assert "confirma o recebimento" not in corpo
            assert "Recebido pelo NSP" in corpo
            assert "sem senha" in corpo
            assert RELATO not in corpo


# =====================================================================
# 4. A página por token não devolve o relato
# =====================================================================


class TestAPaginaPorTokenSemORelato:
    def test_a_pagina_por_token_nao_devolve_o_relato_nem_a_justificativa(self, monkeypatch):
        """O link sem senha mandado antes da Fase 2 ainda abre, mas sem o
        relato: ele está no caso do módulo, com login."""
        caso = _caso(setor_id=SETOR_ID, nsp_justificativa_tecnica=JUSTIFICATIVA_TECNICA)
        client, supabase = _client(monkeypatch, _banco(caso))
        assert _enviar_ao_nucleo(client).status_code == 200
        link = ouvidoria_acionamentos.emitir_link(supabase, _ciencia(supabase))
        token = re.search(r"/ouvidoria-setor/nsp/([A-Za-z0-9_-]+)$", link).group(1)
        client.app.dependency_overrides.pop(get_current_user)

        r = client.get(f"/api/ouvidoria-setor/nsp/{token}")

        assert r.status_code == 200, r.text
        assert r.json()["protocolo"] == "2026-0007"
        assert RELATO not in r.text
        assert JUSTIFICATIVA_TECNICA not in r.text


# =====================================================================
# 5. Cada lado vê, numa palavra, em que pé está o outro
# =====================================================================


def _dossie(client) -> dict:
    r = client.get("/api/ouvidoria/manifestacoes/por-protocolo/2026-0007")
    assert r.status_code == 200, r.text
    return r.json()


class TestOEstadoDeCadaLado:
    def test_o_selo_da_ouvidoria_mostra_o_estado_do_caso_no_nucleo(self, monkeypatch):
        client, supabase = _client(monkeypatch)
        assert _enviar_ao_nucleo(client).status_code == 200

        assert _dossie(client)["nsp_estado"] == "Recebida"

        supabase.notificacoes_do_nucleo[0]["estado"] = "em_triagem"
        assert _dossie(client)["nsp_estado"] == "Em análise"

        supabase.notificacoes_do_nucleo[0]["estado"] = "encaminhada"
        assert _dossie(client)["nsp_estado"] == "Concluída"

    def test_sem_envio_ao_nucleo_o_dossie_nao_tem_estado_do_nucleo(self, monkeypatch):
        client, _supabase = _client(monkeypatch)

        assert _dossie(client)["nsp_estado"] is None

    def test_o_caso_do_nucleo_mostra_que_veio_da_ouvidoria_com_o_estado_da_manifestacao(self, monkeypatch):
        client, supabase = _client(monkeypatch)
        assert _enviar_ao_nucleo(client).status_code == 200
        caso_id = supabase.notificacoes_do_nucleo[0]["id"]

        lista = client.get("/api/nsp/notificacoes").json()["notificacoes"]
        aberto = _abrir_o_caso(client, caso_id).json()

        assert lista[0]["origem"] == "ouvidoria"
        assert lista[0]["ouvidoria"] == {"estado": "Em análise"}
        assert aberto["ouvidoria"] == {"estado": "Em análise"}
        assert "manifestacao_id" not in aberto

        supabase.tabelas["ouvidoria_protocolos"][0]["status"] = "encerrado"
        assert _abrir_o_caso(client, caso_id).json()["ouvidoria"] == {"estado": "Encerrada"}

    def test_o_caso_que_nao_veio_da_ouvidoria_nao_tem_o_selo(self, monkeypatch):
        client, supabase = _client(monkeypatch)
        supabase.tabelas["nsp_notificacoes"] = [
            {
                "id": "44444444-4444-4444-4444-444444444444",
                "protocolo": "NSP-2026-0001",
                "estado": "recebida",
                "origem": "qr",
                "relato": "A bomba de infusao alarmou e ninguem ouviu.",
                "data_ocorrencia": "2026-08-16",
                "anonimo": True,
                "criado_em": "2026-08-16T10:00:00+00:00",
            }
        ]

        caso = _abrir_o_caso(client, "44444444-4444-4444-4444-444444444444").json()

        assert "ouvidoria" not in caso
        assert supabase.tabelas["ouvidoria_movimentos"] == []

    def test_a_lista_do_nucleo_abre_com_centenas_de_casos_da_ouvidoria(self, monkeypatch):
        """A lista traz todos os casos, e os que vieram da Ouvidoria só
        crescem. O estado de cada manifestação é lido em lotes: com algumas
        centenas de UUIDs num `in_` só, a querystring estoura o header do
        proxy e a fila inteira do Núcleo deixa de abrir."""
        quantos = 250
        supabase = _BancoComProxy([], responsaveis=[])
        supabase.tabelas["ouvidoria_protocolos"] = [
            {"id": f"man-{i:04d}", "status": "aguardando_area" if i % 2 else "encerrado"} for i in range(quantos)
        ]
        supabase.tabelas["nsp_notificacoes"] = [
            {
                "id": f"nsp-{i:04d}",
                "protocolo": f"NSP-2026-{i + 1:04d}",
                "numero": i + 1,
                "estado": "recebida",
                "origem": "ouvidoria",
                "manifestacao_id": f"man-{i:04d}",
                "relato": "Relato que veio da Ouvidoria.",
                "data_ocorrencia": "2026-08-16",
                "anonimo": False,
                "criado_em": "2026-08-17T13:00:00+00:00",
            }
            for i in range(quantos)
        ]
        client, _supabase = _client(monkeypatch, supabase)

        r = client.get("/api/nsp/notificacoes")

        assert r.status_code == 200, r.text
        casos = {c["id"]: c for c in r.json()["notificacoes"]}
        assert len(casos) == quantos
        assert casos["nsp-0001"]["ouvidoria"] == {"estado": "Em análise"}
        assert casos["nsp-0248"]["ouvidoria"] == {"estado": "Encerrada"}
        assert casos["nsp-0249"]["ouvidoria"] == {"estado": "Em análise"}


class _BancoComProxy(_Banco):
    """O proxy de produção recusa a consulta com ids demais na querystring."""

    TETO_DE_IDS = 100

    def table(self, nome: str):
        tabela = super().table(nome)
        if nome != "ouvidoria_protocolos":
            return tabela
        filtrar = tabela.in_

        def in_(coluna, valores):
            valores = list(valores)
            if len(valores) > self.TETO_DE_IDS:
                raise RuntimeError(f"431 Request Header Fields Too Large ({len(valores)} ids)")
            return filtrar(coluna, valores)

        tabela.in_ = in_
        return tabela


# =====================================================================
# 6. A manifestação segue o curso dela; nada do Núcleo reabre nem bloqueia
# =====================================================================


class TestAManifestacaoSegueOCursoDela:
    def test_abrir_o_caso_no_nucleo_nao_mexe_no_estado_da_manifestacao(self, monkeypatch):
        client, supabase = _client(monkeypatch)
        assert _enviar_ao_nucleo(client).status_code == 200
        caso_id = supabase.notificacoes_do_nucleo[0]["id"]

        assert _abrir_o_caso(client, caso_id).status_code == 200

        assert supabase.tabelas["ouvidoria_protocolos"][0]["status"] == "aguardando_area"

    def test_o_nucleo_abre_o_caso_da_manifestacao_ja_encerrada_sem_reabrir(self, monkeypatch):
        client, supabase = _client(monkeypatch, _banco(_caso(status="encerrado", setor_id=SETOR_ID)))
        assert _enviar_ao_nucleo(client).status_code == 200
        caso_id = supabase.notificacoes_do_nucleo[0]["id"]

        r = _abrir_o_caso(client, caso_id)

        assert r.status_code == 200, r.text
        assert supabase.tabelas["ouvidoria_protocolos"][0]["status"] == "encerrado"
        assert _ciencia(supabase)["status"] == "ciente"

    def test_falha_ao_marcar_o_recebido_nao_tira_o_caso_da_tela(self, monkeypatch):
        client, supabase = _client(monkeypatch)
        assert _enviar_ao_nucleo(client).status_code == 200
        caso_id = supabase.notificacoes_do_nucleo[0]["id"]
        supabase.indisponiveis.add("ouvidoria_acionamentos")

        r = _abrir_o_caso(client, caso_id)

        assert r.status_code == 200, r.text
        assert r.json()["relato"] == RELATO


# =====================================================================
# 7 e 8. O kit de conhecimento diz o comportamento novo
# =====================================================================

CONHECIMENTO = Path(__file__).resolve().parents[1] / "app" / "conhecimento"


def _paragrafo(arquivo: str, marca: str) -> str:
    texto = (CONHECIMENTO / arquivo).read_text(encoding="utf-8")
    achados = [p for p in re.split(r"\n\n|\n- ", texto) if marca in p]
    assert len(achados) == 1, f"o kit {arquivo} precisa de um trecho com {marca!r}"
    return achados[0]


class TestOKitDeConhecimento:
    def test_o_kit_de_seguranca_do_paciente_diz_que_o_caso_da_ouvidoria_vira_notificacao(self):
        trecho = _paragrafo("seguranca-do-paciente.md", "Veio da Ouvidoria")
        for termo in (
            "notificação de origem Ouvidoria",
            "relato integral",
            "não traz o nome nem o contato de quem manifestou",
            "Confirmar de novo não cria outra",
            "com login",
            "abrir o caso já marca o recebido",
            "segue o curso dela",
            "não foram trazidos",
        ):
            assert termo in trecho, termo

    def test_o_kit_da_ouvidoria_diz_que_o_email_abre_o_caso_no_modulo_e_o_link_perdeu_o_relato(self):
        trecho = _paragrafo("ouvidoria.md", "Recebido pelo NSP")
        for termo in (
            "notificação no módulo de Segurança do Paciente",
            "estado do caso no Núcleo numa palavra",
            "com login",
            "abrir o caso já vale como Recebido pelo NSP",
            "não mostra mais o relato",
            "sem o nome nem o contato de quem manifestou",
        ):
            assert termo in trecho, termo
        assert "O link abre sem senha e mostra o relato integral" not in trecho
