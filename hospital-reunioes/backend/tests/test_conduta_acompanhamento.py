"""A página de acompanhamento do Canal de Conduta e as Mensagens do caso
(issue #1845; especificação, P7 e 6.1).

Quem relatou entra com o protocolo e o código, vê a situação do caso em
linguagem simples e as mensagens do Comitê, e manda o complemento pela mesma
página. Do lado do Comitê, a coordenação pergunta, e o pedido sem resposta em
15 dias libera arquivar por falta de elementos; o caso arquivado reabre quando
a informação chega depois.

Tudo é exercitado pelas rotas (TestClient), com o limitador e o middleware de
log de produção. O banco é o dublê de `conduta_apoio`, e o texto é cifrado de
verdade, com uma chave gerada na hora.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import JsonFormatter, RequestContextMiddleware  # noqa: E402
from app.routers import conduta_acompanhamento, conduta_comite, conduta_mensagens  # noqa: E402
from app.services import ouvidoria_acompanhamento  # noqa: E402
from app.services.conduta import acompanhamento, casos, cifra  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402

ACOMPANHAR = "/api/conduta/acompanhamento"
COMPLEMENTO = "/api/conduta/acompanhamento/complemento"
IP_DE_QUEM_ACOMPANHA = "203.0.113.45"
APARELHO = "Mozilla/5.0 (Linux; Android 10; SM-A105M) Celular-de-Entrada/77"
RELATO = "O encarregado da manutenção ameaçou demitir quem reclamasse das horas extras."
PERGUNTA = "Em que dia e em que setor isso aconteceu?"
COMPLEMENTO_TEXTO = "Foi na oficina, numa terça de manhã, na frente de três técnicos."
RECUSA = {"detail": "Não encontramos um relato com esse protocolo e esse código. Confira os dois e tente de novo."}

HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}
COORDENACAO = "P1"
MEMBRO = "P2"
NOME_DA_COORDENACAO = "Marina Coordenadora Sigilosa"
NOME_DO_MEMBRO = "Otávio Membro Sigiloso"


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "conduta_canal_aberto", True)
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _pessoa(pid: str, nome: str) -> dict:
    return {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": nome,
        "email": f"{pid.lower()}@hsm.test",
        "role": None,
        "ativo": True,
        "is_super_admin": False,
        "access_profile": None,
    }


def _participacao(pid: str, papel: str) -> dict:
    return {
        "id": f"part-{pid}",
        "colegiado_id": COMITE["id"],
        "participante_id": pid,
        "papel": papel,
        "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=600)).isoformat(),
        "termo_assinado_em": "2026-10-01T12:00:00+00:00",
    }


class _Canal:
    """O banco, um caso recebido pela página pública e os dois lados: quem
    relatou, sem login, e o Comitê, logado."""

    def __init__(self):
        self.banco = Banco(
            {
                "participantes": [_pessoa(COORDENACAO, NOME_DA_COORDENACAO), _pessoa(MEMBRO, NOME_DO_MEMBRO)],
                "colegiados": [dict(COMITE)],
                "participacoes": [_participacao(COORDENACAO, "coordenacao"), _participacao(MEMBRO, "membro")],
            }
        )
        novo = casos.registrar_caso(self.banco, relato=RELATO, categoria="A")
        self.caso_id = novo["id"]
        self.protocolo = novo["protocolo"]
        self.codigo = novo["codigo"]

    @property
    def caso(self) -> dict:
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == self.caso_id)

    def mudar_caso(self, **campos) -> None:
        self.caso_mutavel().update(campos)

    def caso_mutavel(self) -> dict:
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == self.caso_id)

    def publico(self, ip: str = IP_DE_QUEM_ACOMPANHA) -> TestClient:
        app = FastAPI()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(RequestContextMiddleware)
        app.include_router(conduta_acompanhamento.router, prefix="/api")
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app, client=(ip, 50123), raise_server_exceptions=False)

    def comite(self, pid: str = COORDENACAO) -> TestClient:
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(conduta_comite.router, prefix="/api")
        app.include_router(conduta_mensagens.router, prefix="/api")

        async def _usuario() -> dict:
            return {"id": f"auth-{pid}", "email": f"{pid.lower()}@hsm.test", "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app, raise_server_exceptions=False)

    def acompanhar(self, protocolo: str | None = None, codigo: str | None = None, **kwargs):
        corpo = {"protocolo": protocolo or self.protocolo, "codigo": codigo or self.codigo}
        return self.publico(**kwargs).post(ACOMPANHAR, json=corpo, headers={"User-Agent": APARELHO})

    def complementar(self, texto: str = COMPLEMENTO_TEXTO):
        corpo = {"protocolo": self.protocolo, "codigo": self.codigo, "texto": texto}
        return self.publico().post(COMPLEMENTO, json=corpo, headers={"User-Agent": APARELHO})

    def perguntar(self, texto: str = PERGUNTA, pid: str = COORDENACAO):
        return self.comite(pid).post(f"/api/comite-de-conduta/casos/{self.caso_id}/mensagens", json={"texto": texto})

    def tela(self, pid: str = COORDENACAO) -> dict:
        resposta = self.comite(pid).get(f"/api/comite-de-conduta/casos/{self.caso_id}")
        assert resposta.status_code == 200, resposta.text
        return resposta.json()

    def recuar_mensagens(self, dias: int) -> None:
        """Faz as mensagens gravadas terem sido enviadas `dias` atrás."""
        for linha in self.banco.tabelas.get("conduta_mensagens", []):
            momento = datetime.fromisoformat(linha["enviada_em"]) - timedelta(days=dias)
            linha["enviada_em"] = momento.isoformat()


@pytest.fixture
def canal() -> _Canal:
    return _Canal()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Protocolo e código certos abrem; qualquer erro, a mesma resposta no mesmo tempo
# ═══════════════════════════════════════════════════════════════════════════


class TestEntrada:
    def test_protocolo_e_codigo_certos_abrem_a_situacao_e_as_mensagens(self, canal):
        resposta = canal.acompanhar()

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {"protocolo": canal.protocolo, "situacao": "Recebido", "mensagens": []}

    def test_o_codigo_vale_com_minuscula_e_sem_o_hifen(self, canal):
        resposta = canal.acompanhar(protocolo=canal.protocolo.lower(), codigo=canal.codigo.replace("-", "").lower())

        assert resposta.status_code == 200

    @pytest.mark.parametrize("erro", ["codigo_errado", "protocolo_que_nao_existe", "protocolo_de_outro_caso"])
    def test_qualquer_erro_devolve_a_mesma_resposta(self, canal, erro):
        outro = casos.registrar_caso(canal.banco, relato=RELATO, categoria="A")
        protocolo, codigo = {
            "codigo_errado": (canal.protocolo, "ABCDE-23456"),
            "protocolo_que_nao_existe": ("CC-ZZZZ-9999", canal.codigo),
            "protocolo_de_outro_caso": (outro["protocolo"], canal.codigo),
        }[erro]

        resposta = canal.acompanhar(protocolo=protocolo, codigo=codigo)

        assert resposta.status_code == 404
        assert resposta.json() == RECUSA

    def test_envio_malformado_tambem_recebe_a_mesma_recusa(self, canal):
        resposta = canal.publico().post(ACOMPANHAR, json={"protocolo": canal.protocolo, "codigo": "x" * 500})

        assert resposta.status_code == 404
        assert resposta.json() == RECUSA
        assert "xxxx" not in resposta.text

    @pytest.mark.parametrize("erro", ["codigo_errado", "protocolo_que_nao_existe", "malformado"])
    def test_toda_recusa_gasta_uma_conferencia_lenta_como_o_acerto(self, canal, monkeypatch, erro):
        """O mesmo tempo: a recusa pelo protocolo que não existe faz a mesma
        derivação lenta do código que a recusa pelo código errado e que o
        acerto. Contar a derivação é o que não depende do relógio da máquina."""
        ouvidoria_acompanhamento._gastar_o_tempo_de_uma_conferencia("aquecer")
        derivacoes: list[int] = []
        original = ouvidoria_acompanhamento._derivar

        def _contar(codigo, sal, iteracoes):
            derivacoes.append(iteracoes)
            return original(codigo, sal, iteracoes)

        monkeypatch.setattr(ouvidoria_acompanhamento, "_derivar", _contar)
        protocolo, codigo = {
            "codigo_errado": (canal.protocolo, "ABCDE-23456"),
            "protocolo_que_nao_existe": ("CC-ZZZZ-9999", canal.codigo),
            "malformado": ("x" * 300, canal.codigo),
        }[erro]

        assert canal.acompanhar().status_code == 200
        acerto = list(derivacoes)
        derivacoes.clear()
        assert canal.acompanhar(protocolo=protocolo, codigo=codigo).status_code == 404

        assert acerto == [ouvidoria_acompanhamento._ITERACOES]
        assert derivacoes == acerto
