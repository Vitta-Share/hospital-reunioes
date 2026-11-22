"""O afastamento cautelar do Canal de Conduta (issue #1836; especificação,
seção 6.5; decisões 20 a 23, 35 e 36 do diretor no PRD #1786).

Cada classe é um critério de aceite da issue. As pessoas e os casos são de
teste; o banco é o dublê de `conduta_apoio`, e o conteúdo é cifrado de
verdade, com uma chave gerada na hora.

O Comitê de teste tem a coordenação e o segundo leitor diretores, um membro
não diretor e um suplente não diretor. Na Rota Especial, o grupo é o membro
e o suplente.
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

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.routers import conduta_afastamento, conduta_comite, conduta_depoimentos  # noqa: E402
from app.services.conduta import casos, cifra  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402

BASE = "/api/comite-de-conduta"
RELATO = "O supervisor Carlos Pereira ameaçou demitir quem depuser contra ele no caso da escala."
ACUSADO = "Carlos Pereira"
MOTIVO = "Ameaça às testemunhas durante a apuração."
HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}
PDF = b"%PDF-1.4\n% parecer do Juridico\n"

COORDENACAO, SEGUNDO_LEITOR, MEMBRO, SUPLENTE = "COORD", "LEITOR", "MEMB", "SUPL"


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


def _participacao(pid: str, papel: str, *, diretor: bool) -> dict:
    return {
        "id": f"part-{pid}",
        "colegiado_id": COMITE["id"],
        "participante_id": pid,
        "papel": papel,
        "e_diretor": diretor,
        "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=600)).isoformat(),
        "encerrada_em": None,
        "termo_assinado_em": "2026-10-01T12:00:00+00:00",
    }


class Comite:
    def __init__(self):
        self.banco = Banco(
            {
                "participantes": [_pessoa(p) for p in (COORDENACAO, SEGUNDO_LEITOR, MEMBRO, SUPLENTE)],
                "colegiados": [dict(COMITE)],
                "participacoes": [
                    _participacao(COORDENACAO, "coordenacao", diretor=True),
                    _participacao(SEGUNDO_LEITOR, "segundo_leitor", diretor=True),
                    _participacao(MEMBRO, "membro", diretor=False),
                    _participacao(SUPLENTE, "suplente", diretor=False),
                ],
            }
        )

    def caso(self, direcao: str | None = None, *, etapa: str | None = None) -> str:
        novo = casos.registrar_caso(self.banco, relato=RELATO, categoria=None, direcao_envolvida=direcao)
        if etapa:
            self.linha(novo["id"])["etapa"] = etapa
        return novo["id"]

    def linha(self, caso_id: str) -> dict:
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == caso_id)

    def cliente(self, pid: str) -> TestClient:
        app = FastAPI()
        app.include_router(conduta_comite.router, prefix="/api")
        app.include_router(conduta_depoimentos.router, prefix="/api")
        app.include_router(conduta_afastamento.router, prefix="/api")
        pessoa = next(p for p in self.banco.tabelas["participantes"] if p["id"] == pid)

        async def _usuario() -> dict[str, Any]:
            return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app)

    def citar(self, pid: str, caso_id: str, nome: str = ACUSADO) -> str:
        resposta = self.cliente(pid).post(f"{BASE}/casos/{caso_id}/citados", json={"nome": nome})
        assert resposta.status_code == 200, resposta.text
        return next(
            c["id"]
            for c in self.banco.tabelas["conduta_citados"]
            if c["caso_id"] == caso_id and cifra.decifrar_texto(c["nome_cifrado"]) == nome
        )

    def afastar(self, pid: str, caso_id: str, citado_id: str, motivo: str = MOTIVO):
        return self.cliente(pid).post(
            f"{BASE}/casos/{caso_id}/afastamentos", json={"citado_id": citado_id, "motivo": motivo}
        )

    def afastamentos(self, caso_id: str) -> list[dict]:
        return [a for a in self.banco.tabelas.get("conduta_afastamentos", []) if a["caso_id"] == caso_id]

    def trilha(self, caso_id: str) -> list[dict]:
        return [linha for linha in self.banco.tabelas.get("conduta_trilha", []) if linha["caso_id"] == caso_id]


@pytest.fixture
def comite() -> Comite:
    return Comite()


# ═══════════════════════════════════════════════════════════════════════════
# 1. O coordenador registra o afastamento em qualquer etapa de um caso comum
# ═══════════════════════════════════════════════════════════════════════════


class TestCoordenadorRegistraNoCasoComum:
    @pytest.mark.parametrize("etapa", ["triagem", "apuracao", "voto"])
    def test_coordenador_registra_o_afastamento_em_qualquer_etapa(self, comite, etapa):
        caso_id = comite.caso(etapa=etapa)
        citado_id = comite.citar(MEMBRO, caso_id)

        resposta = comite.afastar(COORDENACAO, caso_id, citado_id)

        assert resposta.status_code == 200, resposta.text
        [afastamento] = comite.afastamentos(caso_id)
        assert cifra.decifrar_texto(afastamento["quem_cifrado"]) == ACUSADO
        assert cifra.decifrar_texto(afastamento["motivo_cifrado"]) == MOTIVO
        assert afastamento["registrado_por"] == COORDENACAO
        assert comite.trilha(caso_id)[-1]["acao"] == "afastamento_decidido"

    def test_membro_que_nao_e_a_coordenacao_nao_registra(self, comite):
        caso_id = comite.caso()
        citado_id = comite.citar(MEMBRO, caso_id)

        assert comite.afastar(MEMBRO, caso_id, citado_id).status_code == 403
        assert comite.afastar(SEGUNDO_LEITOR, caso_id, citado_id).status_code == 403
        assert comite.afastamentos(caso_id) == []

    def test_a_tela_do_caso_mostra_o_afastamento_e_o_aviso(self, comite):
        caso_id = comite.caso()
        citado_id = comite.citar(MEMBRO, caso_id)
        comite.afastar(COORDENACAO, caso_id, citado_id)

        tela = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso_id}").json()

        assert tela["aviso_do_afastamento"] == "O afastamento cautelar é remunerado e não é punição."
        [visto] = tela["afastamentos"]
        assert visto["quem"] == ACUSADO
        assert visto["motivo"] == MOTIVO
        assert visto["resultado"] == "afastar"
        assert tela["pode_registrar_afastamento"] is False
        assert comite.cliente(COORDENACAO).get(f"{BASE}/casos/{caso_id}").json()["pode_registrar_afastamento"] is True

    def test_caso_encerrado_nao_recebe_afastamento(self, comite):
        caso_id = comite.caso()
        citado_id = comite.citar(MEMBRO, caso_id)
        comite.linha(caso_id)["encerrado_em"] = "2026-11-01T12:00:00+00:00"

        assert comite.afastar(COORDENACAO, caso_id, citado_id).status_code == 409

    def test_uma_pessoa_tem_um_afastamento_por_caso(self, comite):
        caso_id = comite.caso()
        citado_id = comite.citar(MEMBRO, caso_id)

        assert comite.afastar(COORDENACAO, caso_id, citado_id).status_code == 200
        assert comite.afastar(COORDENACAO, caso_id, citado_id).status_code == 409

    def test_so_se_afasta_um_citado_do_caso(self, comite):
        caso_id, outro = comite.caso(), comite.caso()
        citado_de_outro = comite.citar(MEMBRO, outro)

        assert comite.afastar(COORDENACAO, caso_id, citado_de_outro).status_code == 422


def _afastado(comite: Comite, caso_id: str, pid: str = COORDENACAO) -> str:
    citado_id = comite.citar(MEMBRO, caso_id)
    resposta = comite.afastar(pid, caso_id, citado_id)
    assert resposta.status_code == 200, resposta.text
    return comite.afastamentos(caso_id)[0]["id"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. O pedido leva só quem afastar e o motivo
# ═══════════════════════════════════════════════════════════════════════════


class TestOPedidoGerado:
    def test_o_pedido_traz_so_quem_afastar_e_o_motivo(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)
        protocolo = comite.linha(caso_id)["protocolo"]

        resposta = comite.cliente(COORDENACAO).get(f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}")

        assert resposta.status_code == 200, resposta.text
        pedido = resposta.json()["pedido"]
        assert set(pedido) == {"quem", "motivo", "texto"}
        assert pedido["quem"] == ACUSADO
        assert pedido["motivo"] == MOTIVO
        assert ACUSADO in pedido["texto"] and MOTIVO in pedido["texto"]
        assert "O afastamento cautelar é remunerado e não é punição." in pedido["texto"]
        bruto = resposta.text
        assert "escala" not in bruto
        assert protocolo not in bruto

    def test_o_motivo_com_protocolo_de_caso_e_recusado(self, comite):
        caso_id = comite.caso()
        outro = comite.linha(comite.caso())["protocolo"]
        citado_id = comite.citar(MEMBRO, caso_id)

        resposta = comite.afastar(COORDENACAO, caso_id, citado_id, motivo=f"Mesmo caso do {outro}.")

        assert resposta.status_code == 422
        assert comite.afastamentos(caso_id) == []

    def test_abrir_o_pedido_fica_na_trilha(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}")

        ultima = comite.trilha(caso_id)[-1]
        assert (ultima["acao"], ultima["autor_id"]) == ("leitura", MEMBRO)
        assert ultima["detalhe"] == "abriu o pedido de afastamento"

    def test_afastamento_de_outro_caso_nao_abre_pelo_caso_errado(self, comite):
        caso_id, outro = comite.caso(), comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        resposta = comite.cliente(COORDENACAO).get(f"{BASE}/casos/{outro}/afastamentos/{afastamento_id}")

        assert resposta.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 3. A entrega ao DP e ao Jurídico e o parecer do Jurídico na trilha
# ═══════════════════════════════════════════════════════════════════════════


def _parecer(comite: Comite, pid: str, caso_id: str, afastamento_id: str, resultado: str | None = None, pdf=PDF):
    dados = {"resultado": resultado} if resultado else {}
    return comite.cliente(pid).post(
        f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}/parecer",
        files={"arquivo": ("parecer.pdf", pdf, "application/pdf")},
        data=dados,
    )


def _entregar(comite: Comite, pid: str, caso_id: str, afastamento_id: str, destino: str = "dp", quando=HOJE):
    return comite.cliente(pid).post(
        f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}/entrega",
        json={"destino": destino, "entregue_em": quando.isoformat()},
    )


class TestEntregaEParecer:
    @pytest.mark.parametrize(
        ("destino", "coluna", "rotulo"),
        [("dp", "entregue_ao_dp_em", "ao DP"), ("juridico", "entregue_ao_juridico_em", "ao Jurídico")],
    )
    def test_a_entrega_do_pedido_fica_registrada(self, comite, destino, coluna, rotulo):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        resposta = _entregar(comite, COORDENACAO, caso_id, afastamento_id, destino)

        assert resposta.status_code == 200, resposta.text
        assert comite.afastamentos(caso_id)[0][coluna] == HOJE.isoformat()
        ultima = comite.trilha(caso_id)[-1]
        assert ultima["acao"] == "afastamento_entregue"
        assert rotulo in ultima["detalhe"]
        tela = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso_id}").json()
        assert tela["afastamentos"][0]["entregas"][destino] == HOJE.isoformat()

    def test_entrega_registrada_nao_se_registra_de_novo(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        assert _entregar(comite, COORDENACAO, caso_id, afastamento_id).status_code == 200
        assert _entregar(comite, COORDENACAO, caso_id, afastamento_id).status_code == 409

    def test_so_a_coordenacao_registra_a_entrega(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        assert _entregar(comite, MEMBRO, caso_id, afastamento_id).status_code == 403

    def test_entrega_no_futuro_e_recusada(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        resposta = _entregar(comite, COORDENACAO, caso_id, afastamento_id, quando=HOJE + timedelta(days=1))

        assert resposta.status_code == 422

    def test_o_parecer_do_juridico_e_anexado_a_trilha_cifrado(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        resposta = _parecer(comite, COORDENACAO, caso_id, afastamento_id)

        assert resposta.status_code == 200, resposta.text
        ultima = comite.trilha(caso_id)[-1]
        assert (ultima["acao"], ultima["autor_id"]) == ("parecer_do_juridico_anexado", COORDENACAO)
        [guardado] = comite.banco.storage.objetos.values()
        assert PDF not in guardado
        assert cifra.decifrar_arquivo(guardado) == PDF
        assert comite.banco.storage.urls_assinadas == []
        tela = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso_id}").json()
        assert tela["afastamentos"][0]["parecer"]["anexado_em"]
        assert tela["afastamentos"][0]["resultado"] == "afastar"

    def test_quem_abre_o_caso_baixa_o_parecer_decifrado(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)
        _parecer(comite, COORDENACAO, caso_id, afastamento_id)

        resposta = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}/parecer")

        assert resposta.status_code == 200
        assert resposta.content == PDF
        assert resposta.headers["cache-control"] == "no-store"
        assert comite.trilha(caso_id)[-1]["detalhe"] == "abriu o parecer do Jurídico"

    def test_o_parecer_so_aceita_pdf(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        resposta = _parecer(comite, COORDENACAO, caso_id, afastamento_id, pdf=b"nao e pdf")

        assert resposta.status_code == 422
        assert comite.banco.storage.objetos == {}

    def test_o_parecer_anexado_nao_se_troca(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        assert _parecer(comite, COORDENACAO, caso_id, afastamento_id).status_code == 200
        assert _parecer(comite, COORDENACAO, caso_id, afastamento_id).status_code == 409
        assert len(comite.banco.storage.objetos) == 1

    def test_no_caso_comum_o_parecer_e_consultivo_e_nao_leva_resultado(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        assert _parecer(comite, COORDENACAO, caso_id, afastamento_id, resultado="nao_afastar").status_code == 422

    def test_so_a_coordenacao_anexa_o_parecer(self, comite):
        caso_id = comite.caso()
        afastamento_id = _afastado(comite, caso_id)

        assert _parecer(comite, MEMBRO, caso_id, afastamento_id).status_code == 403
