"""O ouvidor sinaliza ao Canal de Conduta a manifestação de paciente que relata
conduta grave de um profissional (issue #1849, PRD #1786, ADR 0097 decisão 14).

O botão do Dossiê abre um caso no Canal, na fila de triagem do Comitê, com a
origem Ouvidoria e o relato integral, sem o nome nem o contato de quem
manifestou. A manifestação não muda de estado: ganha só um movimento na trilha
dela. O ouvidor não passa a ver o caso do Canal.

O banco é o dublê de `conduta_apoio`, e o relato é cifrado de verdade, com uma
chave gerada na hora.
"""

from __future__ import annotations

import base64
import os
import secrets
import sys
from datetime import timedelta
from typing import Any

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import conduta_apoio  # noqa: E402

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import conduta_comite  # noqa: E402
from app.routers import ouvidoria as ouvidoria_router  # noqa: E402
from app.services.conduta import cifra  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402

MANIFESTACAO_ID = "6b1f7d1e-3c55-4a8e-9a77-0f5f1d2c9a01"
ROTA = f"/api/ouvidoria/manifestacoes/{MANIFESTACAO_ID}/canal-de-conduta"
NOME = "Josefa Aparecida Lima"
EMAIL = "josefa.lima@exemplo.com"
TELEFONE = "21987654321"
RELATO = (
    "O enfermeiro do plantão da noite gritou com a minha mãe, puxou o braço dela com força "
    "e disse que ela fingia a dor. Ela ficou com o braço roxo."
)
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}
HOJE = hoje_em_sao_paulo()


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    limiter._storage.reset()
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    # Uma sinalização por manifestação (índice único da migration 202).
    monkeypatch.setitem(conduta_apoio.UNICAS, "conduta_casos", ("manifestacao_id",))
    yield
    limiter._storage.reset()


def _pessoa(pid: str, **campos) -> dict[str, Any]:
    return {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": f"Pessoa {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "role": None,
        "ativo": True,
        "is_super_admin": False,
        "access_profile": None,
        **campos,
    }


OUVIDOR = _pessoa("P1", perfil_ouvidoria="ouvidor")
DIRETORA = _pessoa("P2", perfil_ouvidoria="diretoria_executiva")
SUPER_ADMIN = _pessoa("P3", access_profile="super_admin", is_super_admin=True)
MEMBRO_DO_COMITE = _pessoa("P4")


def _manifestacao(**campos) -> dict[str, Any]:
    return {
        "id": MANIFESTACAO_ID,
        "protocolo": "2026-000123",
        "status": "aguardando_area",
        "relato_integral": RELATO,
        "manifestante_nome": NOME,
        "manifestante_email": EMAIL,
        "manifestante_telefone": TELEFONE,
        "anonimo": False,
        "sigilo_reforcado": True,
        "anonimizada_em": None,
        "apagamento_pedido_em": None,
        "conduta_sinalizada_em": None,
        **campos,
    }


def _banco(**manifestacao) -> Banco:
    return Banco(
        {
            "participantes": [dict(OUVIDOR), dict(DIRETORA), dict(SUPER_ADMIN), dict(MEMBRO_DO_COMITE)],
            "colegiados": [dict(COMITE)],
            "participacoes": [
                {
                    "id": "part-P4",
                    "colegiado_id": COMITE["id"],
                    "participante_id": "P4",
                    "papel": "coordenacao",
                    "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
                    "vigencia_fim": (HOJE + timedelta(days=600)).isoformat(),
                    "termo_assinado_em": "2026-10-01T12:00:00+00:00",
                }
            ],
            "ouvidoria_protocolos": [_manifestacao(**manifestacao)],
        }
    )


def _cliente(banco: Banco, pessoa: dict) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(ouvidoria_router.router, prefix="/api")
    app.include_router(conduta_comite.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _casos(banco: Banco) -> list[dict]:
    return banco.tabelas.get("conduta_casos", [])


class TestOCasoNoCanal:
    def test_ouvidor_sinaliza_e_o_caso_nasce_na_triagem_com_o_relato_integral_e_a_origem_ouvidoria(self):
        banco = _banco()

        resposta = _cliente(banco, OUVIDOR).post(ROTA)

        assert resposta.status_code == 200, resposta.text
        (caso,) = _casos(banco)
        assert cifra.decifrar_texto(caso["relato_cifrado"]) == RELATO
        assert caso["origem"] == "ouvidoria"
        assert caso["etapa"] == "triagem"
        assert caso["rota"] == "comum"
        assert caso["manifestacao_id"] == MANIFESTACAO_ID

    def test_o_caso_nao_traz_o_nome_nem_o_contato_de_quem_manifestou(self):
        banco = _banco()

        resposta = _cliente(banco, OUVIDOR).post(ROTA)

        assert resposta.status_code == 200, resposta.text
        (caso,) = _casos(banco)
        tudo_do_canal = repr(banco.tabelas["conduta_casos"]) + repr(banco.tabelas["conduta_trilha"])
        tudo_do_canal += cifra.decifrar_texto(caso["relato_cifrado"])
        for dado in (NOME, "Josefa", EMAIL, TELEFONE):
            assert dado not in tudo_do_canal
        # E nada do caso do Canal volta para o ouvidor.
        assert caso["protocolo"] not in resposta.text
        assert caso["id"] not in resposta.text

    def test_a_coordenacao_do_comite_ve_o_caso_na_fila_com_a_origem_ouvidoria(self):
        banco = _banco()
        _cliente(banco, OUVIDOR).post(ROTA)

        lista = _cliente(banco, MEMBRO_DO_COMITE).get("/api/comite-de-conduta/casos")

        assert lista.status_code == 200, lista.text
        (caso,) = lista.json()["casos"]
        assert caso["origem"] == "ouvidoria"
        assert caso["situacao"] == "em_triagem"


class TestAManifestacaoSegueNaOuvidoria:
    def test_a_manifestacao_nao_muda_de_estado_e_ganha_o_movimento_da_sinalizacao(self):
        banco = _banco()

        _cliente(banco, OUVIDOR).post(ROTA)

        (manifestacao,) = banco.tabelas["ouvidoria_protocolos"]
        assert manifestacao["status"] == "aguardando_area"
        assert manifestacao["conduta_sinalizada_em"] is not None
        (movimento,) = banco.tabelas["ouvidoria_movimentos"]
        assert movimento["manifestacao_id"] == MANIFESTACAO_ID
        assert movimento["estado_anterior"] == movimento["estado_novo"] == "aguardando_area"
        assert movimento["autor_id"] == OUVIDOR["id"]
        assert "Canal de Conduta" in movimento["observacao"]


class TestOOuvidorNaoVeOCaso:
    def test_o_ouvidor_recebe_403_ao_tentar_abrir_o_caso_no_canal(self):
        banco = _banco()
        cliente = _cliente(banco, OUVIDOR)
        cliente.post(ROTA)
        (caso,) = _casos(banco)

        resposta = cliente.get(f"/api/comite-de-conduta/casos/{caso['id']}")

        assert resposta.status_code == 403, resposta.text
        assert not [linha for linha in banco.tabelas["conduta_trilha"] if linha["acao"] == "leitura"]


class TestUmCasoPorManifestacao:
    def test_sinalizar_duas_vezes_nao_cria_dois_casos(self):
        banco = _banco()
        cliente = _cliente(banco, OUVIDOR)

        primeira = cliente.post(ROTA)
        segunda = cliente.post(ROTA)

        assert primeira.status_code == 200, primeira.text
        assert segunda.status_code == 409, segunda.text
        assert len(_casos(banco)) == 1
        assert len(banco.tabelas["ouvidoria_movimentos"]) == 1

    def test_a_sinalizacao_que_parou_depois_do_caso_termina_sem_abrir_outro(self):
        banco = _banco()
        cliente = _cliente(banco, OUVIDOR)
        cliente.post(ROTA)
        # O caso ficou, o carimbo e o movimento não.
        banco.tabelas["ouvidoria_protocolos"][0]["conduta_sinalizada_em"] = None
        banco.tabelas["ouvidoria_movimentos"].clear()

        resposta = cliente.post(ROTA)

        assert resposta.status_code == 200, resposta.text
        assert len(_casos(banco)) == 1
        assert banco.tabelas["ouvidoria_protocolos"][0]["conduta_sinalizada_em"] is not None
        assert len(banco.tabelas["ouvidoria_movimentos"]) == 1


class TestQuemSinaliza:
    def test_a_diretoria_executiva_tambem_sinaliza(self):
        banco = _banco()

        resposta = _cliente(banco, DIRETORA).post(ROTA)

        assert resposta.status_code == 200, resposta.text
        assert len(_casos(banco)) == 1

    @pytest.mark.parametrize("pessoa", [SUPER_ADMIN, MEMBRO_DO_COMITE], ids=["super_admin", "membro_do_comite"])
    def test_quem_nao_tem_o_perfil_da_ouvidoria_recebe_403(self, pessoa):
        banco = _banco()

        resposta = _cliente(banco, pessoa).post(ROTA)

        assert resposta.status_code == 403, resposta.text
        assert _casos(banco) == []

    def test_caso_apagado_nao_e_sinalizado(self):
        banco = _banco(anonimizada_em="2026-10-01T12:00:00+00:00")

        resposta = _cliente(banco, OUVIDOR).post(ROTA)

        assert resposta.status_code == 409, resposta.text
        assert _casos(banco) == []

    def test_sem_a_chave_do_canal_nada_e_gravado(self, monkeypatch):
        monkeypatch.setattr(settings, "conduta_chave_cifra", "")
        banco = _banco()

        resposta = _cliente(banco, OUVIDOR).post(ROTA)

        assert resposta.status_code == 503, resposta.text
        assert _casos(banco) == []
        assert banco.tabelas["ouvidoria_protocolos"][0]["conduta_sinalizada_em"] is None


class TestODossie:
    def test_o_dossie_diz_que_o_caso_foi_sinalizado(self):
        banco = _banco()
        cliente = _cliente(banco, OUVIDOR)
        cliente.post(ROTA)

        dossie = cliente.get(f"/api/ouvidoria/manifestacoes/{MANIFESTACAO_ID}")

        assert dossie.status_code == 200, dossie.text
        assert (
            dossie.json()["conduta_sinalizada_em"] == banco.tabelas["ouvidoria_protocolos"][0]["conduta_sinalizada_em"]
        )
