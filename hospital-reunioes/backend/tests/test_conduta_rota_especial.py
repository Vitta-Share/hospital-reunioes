"""A Rota Especial do Canal de Conduta (issue #1829; especificação, seção 10;
decisões 16, 19 e 28 do diretor no PRD #1786).

Cada classe é um critério de aceite da issue. As pessoas e os casos são de
teste; o banco é o dublê de `conduta_apoio`, e o relato é cifrado de verdade,
com uma chave gerada na hora.

O Comitê de teste tem a coordenação e o segundo leitor diretores, um membro
não diretor, um suplente diretor (o mais antigo) e um suplente não diretor. O
Grupo Especial certo é o membro não diretor e o suplente não diretor.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sys
from datetime import datetime, timedelta
from typing import Any

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.routers import conduta_comite, conduta_rota_especial  # noqa: E402
from app.services.conduta import avisos, casos, cifra, rota_especial  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402

BASE = "/api/comite-de-conduta"
RELATO = "A diretora contratou a empresa do marido para a reforma da ala B sem cotação."
HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}

COORDENACAO, SEGUNDO_LEITOR, MEMBRO = "COORD", "LEITOR", "MEMB"
SUPLENTE_DIRETOR, SUPLENTE = "SUPDIR", "SUPL"
NOVO_MEMBRO = "NOVO"
GRUPO_CERTO = {MEMBRO, SUPLENTE}


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())


def _pessoa(pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": f"Pessoa {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "role": None,
        "ativo": True,
        "is_super_admin": False,
        "access_profile": None,
    }


def _participacao(pid: str, papel: str, *, diretor: bool, desde_dias: int = 30) -> dict:
    return {
        "id": f"part-{pid}",
        "colegiado_id": COMITE["id"],
        "participante_id": pid,
        "papel": papel,
        "e_diretor": diretor,
        "vigencia_inicio": (HOJE - timedelta(days=desde_dias)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=600)).isoformat(),
        "encerrada_em": None,
        "termo_assinado_em": "2026-10-01T12:00:00+00:00",
    }


class Comite:
    def __init__(self):
        self.banco = Banco(
            {
                "participantes": [
                    _pessoa(p) for p in (COORDENACAO, SEGUNDO_LEITOR, MEMBRO, SUPLENTE_DIRETOR, SUPLENTE, NOVO_MEMBRO)
                ],
                "colegiados": [dict(COMITE)],
                "participacoes": [
                    _participacao(COORDENACAO, "coordenacao", diretor=True),
                    _participacao(SEGUNDO_LEITOR, "segundo_leitor", diretor=True),
                    _participacao(MEMBRO, "membro", diretor=False),
                    _participacao(SUPLENTE_DIRETOR, "suplente", diretor=True, desde_dias=90),
                    _participacao(SUPLENTE, "suplente", diretor=False),
                ],
            }
        )

    def caso(self, direcao: str | None = None, *, dias_atras: int = 0) -> str:
        novo = casos.registrar_caso(self.banco, relato=RELATO, categoria=None, direcao_envolvida=direcao)
        quando = datetime.now().astimezone() - timedelta(days=dias_atras)
        self.linha(novo["id"])["recebido_em"] = quando.isoformat()
        return novo["id"]

    def linha(self, caso_id: str) -> dict:
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == caso_id)

    def cliente(self, pid: str) -> TestClient:
        app = FastAPI()
        app.include_router(conduta_comite.router, prefix="/api")
        app.include_router(conduta_rota_especial.router, prefix="/api")
        pessoa = next(p for p in self.banco.tabelas["participantes"] if p["id"] == pid)

        async def _usuario() -> dict[str, Any]:
            return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app)

    def lista(self, pid: str) -> list[str]:
        resposta = self.cliente(pid).get(f"{BASE}/casos")
        assert resposta.status_code == 200, resposta.text
        return [c["id"] for c in resposta.json()["casos"]]

    def abre(self, pid: str, caso_id: str):
        return self.cliente(pid).get(f"{BASE}/casos/{caso_id}")

    def agir(self, pid: str, caso_id: str, acao: str, corpo: dict | None = None):
        return self.cliente(pid).post(f"{BASE}/casos/{caso_id}/{acao}", json=corpo or {})

    def trilha(self, caso_id: str) -> list[dict]:
        return [linha for linha in self.banco.tabelas.get("conduta_trilha", []) if linha["caso_id"] == caso_id]

    def grupo(self, caso_id: str) -> set[str]:
        return {
            a["participante_id"]
            for a in self.banco.tabelas.get("conduta_atribuicoes", [])
            if a["caso_id"] == caso_id and a["motivo"] == "grupo_especial"
        }


@pytest.fixture
def comite() -> Comite:
    return Comite()


# ═══════════════════════════════════════════════════════════════════════════
# 1. "Sim" no passo 3: fora da fila comum, com o registro selado
# ═══════════════════════════════════════════════════════════════════════════


class TestSimNoPasso3:
    def test_relato_com_sim_nao_aparece_na_fila_comum_nem_para_a_coordenacao(self, comite):
        caso_id = comite.caso("sim")

        assert caso_id not in comite.lista(COORDENACAO)
        assert caso_id not in comite.lista(SEGUNDO_LEITOR)
        assert comite.abre(COORDENACAO, caso_id).status_code == 403
        assert comite.linha(caso_id)["rota"] == "especial"

    def test_relato_com_sim_vai_direto_ao_grupo_especial(self, comite):
        caso_id = comite.caso("sim")

        assert caso_id in comite.lista(MEMBRO)
        assert caso_id in comite.lista(SUPLENTE)
        assert comite.abre(MEMBRO, caso_id).status_code == 200

    def test_relato_com_sim_gera_o_registro_selado_com_data_hora_e_codigo(self, comite):
        caso_id = comite.caso("sim")

        selos = [s for s in comite.banco.tabelas["conduta_selos"] if s["caso_id"] == caso_id]
        assert len(selos) == 1
        selo = selos[0]
        assert cifra.decifrar_texto(selo["relato_cifrado"]) == RELATO
        assert datetime.fromisoformat(selo["selado_em"]) <= datetime.now().astimezone()
        assert len(selo["codigo"]) == 64
        assert selo["codigo"] != hashlib.sha256(b"").hexdigest()

    def test_o_codigo_do_selo_denuncia_o_relato_trocado(self, comite):
        caso_id = comite.caso("sim")
        selo = comite.banco.tabelas["conduta_selos"][0]

        assert rota_especial.selo_confere(selo)
        trocado = {**selo, "relato_cifrado": cifra.cifrar_texto(RELATO + " (editado)")}
        assert not rota_especial.selo_confere(trocado)
        assert caso_id

    def test_o_grupo_ve_o_selo_na_tela_do_caso(self, comite):
        caso_id = comite.caso("sim")

        tela = comite.abre(MEMBRO, caso_id).json()

        assert tela["rota_especial"]["selo"]["codigo"] == comite.banco.tabelas["conduta_selos"][0]["codigo"]
        assert tela["rota_especial"]["selo"]["confere"] is True

    def test_relato_com_nao_fica_na_fila_comum_sem_selo(self, comite):
        caso_id = comite.caso("nao")

        assert caso_id in comite.lista(COORDENACAO)
        assert not comite.banco.tabelas.get("conduta_selos")
        assert comite.abre(COORDENACAO, caso_id).json()["aviso_de_rota_especial"] is None
