"""A nota do Comitê de Conduta ao Núcleo de Segurança do Paciente (issue #1850,
PRD #1786, ADR 0097, decisão 14).

Cada classe é um critério de aceite da issue:

1. um membro escreve a nota e a coordenação a envia, com registro na trilha;
2. a Presidência do Núcleo lê a nota na lista de Segurança do Paciente;
3. a nota não leva protocolo, relato, anexo nem quem relatou, e nada liga a
   nota ao caso do lado do Núcleo;
4. quem lê a nota recebe 403 em qualquer rota de caso do Canal.

O banco é o dublê de `conduta_apoio`, e o relato é cifrado de verdade. As
pessoas são de teste.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from test_conduta_triagem import (
    COORDENACAO,
    DE_FORA,
    HOJE,
    MEMBRO,
    RELATO,
    SEGUNDO_LEITOR,
    Comite,
    _chave,  # noqa: F401  (a chave de cifra de teste, autouse)
    _pessoa,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import conduta_comite  # noqa: E402
from app.routers import seguranca_do_paciente as nsp_router  # noqa: E402

ROTA_DO_NUCLEO = "/api/nsp/notas-do-comite"
NOTA = "Há risco de queda no corredor da ala B: o piso molhado fica sem sinalização à noite."
PRESIDENCIA, MEMBRO_DO_NUCLEO = "PRESNSP", "MEMBNSP"
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _no_nucleo(pid: str, papel: str) -> dict:
    return {
        "id": f"part-{pid}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": pid,
        "papel": papel,
        "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=600)).isoformat(),
        "termo_assinado_em": "2026-10-01T12:00:00+00:00",
    }


class ComiteENucleo(Comite):
    """O Comitê inteiro e, ao lado, o Núcleo: a Presidência e um membro."""

    def __init__(self):
        super().__init__()
        tabelas = self.banco.tabelas
        tabelas["participantes"] += [_pessoa(PRESIDENCIA), _pessoa(MEMBRO_DO_NUCLEO)]
        tabelas["colegiados"].append(dict(NUCLEO))
        tabelas["participacoes"] += [_no_nucleo(PRESIDENCIA, "presidencia"), _no_nucleo(MEMBRO_DO_NUCLEO, "membro")]

    def cliente_do_nucleo(self, pid: str) -> TestClient:
        app = FastAPI()
        app.include_router(nsp_router.router, prefix="/api")
        pessoa = next(p for p in self.banco.tabelas["participantes"] if p["id"] == pid)

        async def _usuario() -> dict:
            return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app)

    def escrever(self, pid: str, caso_id: str, texto: str = NOTA):
        return self.agir(pid, caso_id, "nota-ao-nsp", {"texto": texto})

    def enviar(self, pid: str, caso_id: str):
        return self.agir(pid, caso_id, "nota-ao-nsp/envio")

    def notas_no_nucleo(self, pid: str = PRESIDENCIA):
        return self.cliente_do_nucleo(pid).get(ROTA_DO_NUCLEO)


@pytest.fixture
def comite() -> ComiteENucleo:
    return ComiteENucleo()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Um membro escreve a nota e a coordenação a envia, com registro na trilha
# ═══════════════════════════════════════════════════════════════════════════


class TestMembroEscreveCoordenacaoEnvia:
    def test_o_membro_escreve_a_coordenacao_envia_e_a_trilha_registra(self, comite):
        caso = comite.caso()

        assert comite.escrever(MEMBRO, caso).status_code == 200
        assert comite.enviar(COORDENACAO, caso).status_code == 200

        assert comite.trilha(caso)[-2:] == ["nota_ao_nsp_escrita", "nota_ao_nsp_enviada"]
        (nota,) = comite.abrir(MEMBRO, caso)["notas_ao_nsp"]
        assert nota["texto"] == NOTA
        assert nota["enviada_em"] is not None

    def test_so_a_coordenacao_envia(self, comite):
        caso = comite.caso()
        comite.escrever(MEMBRO, caso)

        for pid in (MEMBRO, SEGUNDO_LEITOR):
            resposta = comite.enviar(pid, caso)
            assert resposta.status_code == 403
            assert resposta.json()["detail"] == "Só a coordenação envia a nota ao Núcleo."
        assert "nota_ao_nsp_enviada" not in comite.trilha(caso)
        assert comite.notas_no_nucleo().json()["notas"] == []

    def test_quem_nao_e_do_comite_nao_escreve(self, comite):
        caso = comite.caso()

        assert comite.escrever(DE_FORA, caso).status_code == 403
        assert comite.banco.tabelas.get("conduta_notas_nsp", []) == []

    def test_sem_nota_escrita_nao_ha_o_que_enviar(self, comite):
        caso = comite.caso()

        resposta = comite.enviar(COORDENACAO, caso)

        assert resposta.status_code == 409
        assert "nota_ao_nsp_enviada" not in comite.trilha(caso)

    def test_a_nota_enviada_nao_se_envia_de_novo(self, comite):
        caso = comite.caso()
        comite.escrever(MEMBRO, caso)
        comite.enviar(COORDENACAO, caso)

        assert comite.enviar(COORDENACAO, caso).status_code == 409
        assert len(comite.notas_no_nucleo().json()["notas"]) == 1

    def test_se_o_nucleo_nao_recebe_a_nota_volta_a_esperar_o_envio(self, comite, monkeypatch):
        caso = comite.caso()
        comite.escrever(MEMBRO, caso)
        gravar = comite.banco.gravar

        def _nucleo_fora(nome, linha):
            if nome == "nsp_notas_do_comite":
                raise APIError({"code": "08006", "message": "conexão perdida"})
            return gravar(nome, linha)

        monkeypatch.setattr(comite.banco, "gravar", _nucleo_fora)
        assert comite.enviar(COORDENACAO, caso).status_code == 503
        monkeypatch.setattr(comite.banco, "gravar", gravar)

        (nota,) = comite.abrir(MEMBRO, caso)["notas_ao_nsp"]
        assert nota["enviada_em"] is None
        assert comite.enviar(COORDENACAO, caso).status_code == 200
        assert len(comite.notas_no_nucleo().json()["notas"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 2. A Presidência do Núcleo lê a nota na lista de Segurança do Paciente
# ═══════════════════════════════════════════════════════════════════════════


class TestPresidenciaLeANota:
    def test_a_presidencia_le_a_nota_enviada(self, comite):
        caso = comite.caso()
        comite.escrever(MEMBRO, caso)
        comite.enviar(COORDENACAO, caso)

        resposta = comite.notas_no_nucleo(PRESIDENCIA)

        assert resposta.status_code == 200, resposta.text
        (nota,) = resposta.json()["notas"]
        assert nota["texto"] == NOTA

    def test_a_nota_que_espera_a_coordenacao_nao_chega_ao_nucleo(self, comite):
        caso = comite.caso()
        comite.escrever(MEMBRO, caso)

        assert comite.notas_no_nucleo(PRESIDENCIA).json()["notas"] == []

    def test_o_membro_do_nucleo_e_quem_e_de_fora_nao_leem(self, comite):
        caso = comite.caso()
        comite.escrever(MEMBRO, caso)
        comite.enviar(COORDENACAO, caso)

        for pid in (MEMBRO_DO_NUCLEO, COORDENACAO, DE_FORA):
            assert comite.notas_no_nucleo(pid).status_code == 403, pid


# ═══════════════════════════════════════════════════════════════════════════
# 3. A nota não leva protocolo, relato, anexo nem quem relatou, e nada liga a
#    nota ao caso do lado do Núcleo
# ═══════════════════════════════════════════════════════════════════════════


class TestANotaNaoLevaOCaso:
    def _enviada(self, comite) -> tuple[str, dict]:
        caso = comite.caso()
        comite.escrever(MEMBRO, caso)
        comite.enviar(COORDENACAO, caso)
        (nota,) = comite.notas_no_nucleo().json()["notas"]
        return caso, nota

    def test_o_nucleo_recebe_so_o_texto_e_a_data(self, comite):
        caso, nota = self._enviada(comite)
        protocolo = comite._linha(caso)["protocolo"]

        assert set(nota) == {"id", "texto", "enviada_em"}
        corpo = comite.notas_no_nucleo().text
        assert protocolo not in corpo
        assert caso not in corpo
        assert RELATO[:40] not in corpo

    def test_a_linha_do_nucleo_nao_aponta_para_o_caso_nem_para_quem_agiu(self, comite):
        caso, nota = self._enviada(comite)

        (linha,) = comite.banco.tabelas["nsp_notas_do_comite"]
        assert set(linha) <= {"id", "texto", "enviada_em"}
        assert caso not in linha.values()
        (do_comite,) = comite.banco.tabelas["conduta_notas_nsp"]
        assert nota["id"] not in do_comite.values()

    def test_a_nota_com_o_protocolo_e_recusada(self, comite):
        caso = comite.caso()
        protocolo = comite._linha(caso)["protocolo"]

        resposta = comite.escrever(MEMBRO, caso, f"Sobre o caso {protocolo.lower()}: risco de queda.")

        assert resposta.status_code == 422
        assert resposta.json()["detail"] == "A nota não leva o protocolo do caso."
        assert comite.banco.tabelas.get("conduta_notas_nsp", []) == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. Quem lê a nota recebe 403 em qualquer rota de caso do Canal
# ═══════════════════════════════════════════════════════════════════════════


def _rotas_de_caso() -> list[tuple[str, str]]:
    rotas = []
    for rota in conduta_comite.router.routes:
        if isinstance(rota, APIRoute) and "{caso_id}" in rota.path:
            rotas += [(metodo, rota.path) for metodo in sorted(rota.methods)]
    return rotas


ROTAS_DE_CASO = _rotas_de_caso()


def test_a_varredura_acha_as_rotas_de_caso():
    """Piso do detector: sem rota achada, o teste abaixo passaria sobre nada."""
    assert ("GET", "/comite-de-conduta/casos/{caso_id}") in ROTAS_DE_CASO
    assert ("POST", "/comite-de-conduta/casos/{caso_id}/nota-ao-nsp/envio") in ROTAS_DE_CASO


@pytest.mark.parametrize("metodo,caminho", ROTAS_DE_CASO, ids=[f"{m} {c}" for m, c in ROTAS_DE_CASO])
@pytest.mark.parametrize("quem", [PRESIDENCIA, MEMBRO_DO_NUCLEO])
def test_quem_le_a_nota_nao_abre_caso_do_canal(comite, metodo, caminho, quem):
    caso = comite.caso()
    comite.escrever(MEMBRO, caso)
    comite.enviar(COORDENACAO, caso)
    assert comite.notas_no_nucleo().status_code == 200

    url = "/api" + caminho.replace("{caso_id}", caso)
    resposta = comite.cliente(quem).request(metodo, url, json={})

    assert resposta.status_code == 403, resposta.text
    assert RELATO[:40] not in resposta.text
