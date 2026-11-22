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


# ═══════════════════════════════════════════════════════════════════════════
# 4. Na Rota Especial, a coordenação vê só o pedido
# ═══════════════════════════════════════════════════════════════════════════


def _pedido_especial(comite: Comite) -> tuple[str, str]:
    caso_id = comite.caso("sim")
    afastamento_id = _afastado(comite, caso_id, pid=MEMBRO)
    return caso_id, afastamento_id


class TestCoordenacaoNaRotaEspecial:
    def test_o_grupo_pede_o_afastamento_a_coordenacao(self, comite):
        caso_id, _ = _pedido_especial(comite)

        [afastamento] = comite.afastamentos(caso_id)
        assert afastamento["rota"] == "especial"
        assert comite.trilha(caso_id)[-1]["acao"] == "afastamento_pedido"
        tela = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso_id}").json()
        assert tela["afastamentos"][0]["resultado"] is None

    def test_a_coordenacao_abre_o_pedido_sem_nada_do_caso(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)
        protocolo = comite.linha(caso_id)["protocolo"]

        resposta = comite.cliente(COORDENACAO).get(f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["pedido"]["quem"] == ACUSADO
        assert "escala" not in resposta.text
        assert protocolo not in resposta.text
        assert resposta.json()["pode_anexar_parecer"] is True
        ultima = comite.trilha(caso_id)[-1]
        assert (ultima["acao"], ultima["autor_id"]) == ("leitura", COORDENACAO)

    def test_a_coordenacao_recebe_403_no_resto_do_caso(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)
        cliente = comite.cliente(COORDENACAO)

        assert cliente.get(f"{BASE}/casos/{caso_id}").status_code == 403
        assert cliente.post(f"{BASE}/casos/{caso_id}/citados", json={"nome": "Outra Pessoa"}).status_code == 403
        assert cliente.post(f"{BASE}/casos/{caso_id}/nota-ao-nsp", json={"texto": "risco"}).status_code == 403
        assert cliente.post(f"{BASE}/casos/{caso_id}/impedimento", json={"motivo": "parte"}).status_code == 403
        caso_ids = [c["id"] for c in cliente.get(f"{BASE}/casos").json()["casos"]]
        assert caso_id not in caso_ids
        assert comite.afastar(COORDENACAO, caso_id, comite.afastamentos(caso_id)[0]["citado_id"]).status_code == 403

    def test_a_coordenacao_lista_os_pedidos_da_rota_especial_sem_dado_do_caso(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)
        protocolo = comite.linha(caso_id)["protocolo"]

        resposta = comite.cliente(COORDENACAO).get(f"{BASE}/afastamentos/pedidos")

        assert resposta.status_code == 200, resposta.text
        [item] = resposta.json()["pedidos"]
        assert (item["id"], item["caso_id"]) == (afastamento_id, caso_id)
        assert item["parecer_anexado"] is False
        assert protocolo not in resposta.text
        assert ACUSADO not in resposta.text

    def test_so_a_coordenacao_lista_os_pedidos(self, comite):
        _pedido_especial(comite)

        assert comite.cliente(MEMBRO).get(f"{BASE}/afastamentos/pedidos").status_code == 403

    def test_a_coordenacao_citada_nem_o_pedido_ve(self, comite):
        caso_id = comite.caso("sim")
        comite.cliente(MEMBRO).post(f"{BASE}/casos/{caso_id}/citados", json={"participante_id": COORDENACAO})
        citado_id = next(c["id"] for c in comite.banco.tabelas["conduta_citados"] if c.get("participante_id"))
        assert comite.afastar(MEMBRO, caso_id, citado_id).status_code == 200
        afastamento_id = comite.afastamentos(caso_id)[0]["id"]

        cliente = comite.cliente(COORDENACAO)
        assert cliente.get(f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}").status_code == 403
        assert cliente.get(f"{BASE}/afastamentos/pedidos").json()["pedidos"] == []

    def test_outro_membro_de_fora_do_grupo_nao_abre_o_pedido(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)

        resposta = comite.cliente(SEGUNDO_LEITOR).get(f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}")

        assert resposta.status_code == 403

    def test_na_rota_especial_so_o_grupo_pede(self, comite):
        caso_id = comite.caso("sim")
        citado_id = comite.citar(MEMBRO, caso_id)

        assert comite.afastar(COORDENACAO, caso_id, citado_id).status_code == 403

    def test_o_grupo_nao_registra_a_entrega_nem_anexa_o_parecer(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)

        assert _entregar(comite, MEMBRO, caso_id, afastamento_id).status_code == 403
        assert _parecer(comite, MEMBRO, caso_id, afastamento_id, resultado="afastar").status_code == 403

    def test_a_coordenacao_registra_a_entrega_do_pedido_especial(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)

        assert _entregar(comite, COORDENACAO, caso_id, afastamento_id, "juridico").status_code == 200
        assert comite.afastamentos(caso_id)[0]["entregue_ao_juridico_em"] == HOJE.isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# 5. Na Rota Especial, o parecer leva a ciência do grupo e define o resultado
# ═══════════════════════════════════════════════════════════════════════════


class TestParecerNaRotaEspecial:
    @pytest.mark.parametrize("resultado", ["afastar", "nao_afastar"])
    def test_o_parecer_define_o_resultado(self, comite, resultado):
        caso_id, afastamento_id = _pedido_especial(comite)

        resposta = _parecer(comite, COORDENACAO, caso_id, afastamento_id, resultado=resultado)

        assert resposta.status_code == 200, resposta.text
        tela = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso_id}").json()
        assert tela["afastamentos"][0]["resultado"] == resultado

    def test_o_parecer_registra_a_ciencia_dos_membros_do_grupo(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)

        _parecer(comite, COORDENACAO, caso_id, afastamento_id, resultado="afastar")

        assert comite.afastamentos(caso_id)[0]["ciencia_de"] == sorted([MEMBRO, SUPLENTE])
        ultima = comite.trilha(caso_id)[-1]
        assert ultima["acao"] == "parecer_do_juridico_anexado"
        assert "afastar" in ultima["detalhe"] and "ciência de 2 membro(s) do grupo" in ultima["detalhe"]
        tela = comite.cliente(SUPLENTE).get(f"{BASE}/casos/{caso_id}").json()
        assert sorted(tela["afastamentos"][0]["parecer"]["ciencia_de"]) == [f"Pessoa {MEMBRO}", f"Pessoa {SUPLENTE}"]

    def test_parecer_sem_resultado_e_recusado(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)

        assert _parecer(comite, COORDENACAO, caso_id, afastamento_id).status_code == 422
        assert comite.afastamentos(caso_id)[0].get("parecer_anexado_em") is None

    def test_o_grupo_baixa_o_parecer(self, comite):
        caso_id, afastamento_id = _pedido_especial(comite)
        _parecer(comite, COORDENACAO, caso_id, afastamento_id, resultado="nao_afastar")

        resposta = comite.cliente(SUPLENTE).get(f"{BASE}/casos/{caso_id}/afastamentos/{afastamento_id}/parecer")

        assert resposta.content == PDF


# ═══════════════════════════════════════════════════════════════════════════
# 6. Nenhuma medida cautelar recai sobre quem relatou
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemRelatou:
    def test_nao_se_afasta_o_denunciante_identificado(self, comite):
        caso_id = comite.caso(etapa="apuracao")
        resposta = comite.cliente(COORDENACAO).post(
            f"{BASE}/casos/{caso_id}/depoimentos",
            json={"nome": "Ana Lúcia Souza", "cargo": "Técnica de enfermagem", "papel": "denunciante"},
        )
        assert resposta.status_code == 200, resposta.text
        citado_id = comite.citar(MEMBRO, caso_id, nome="ana lucia  SOUZA")

        resposta = comite.afastar(COORDENACAO, caso_id, citado_id)

        assert resposta.status_code == 422
        assert resposta.json()["detail"] == "Nenhuma medida cautelar recai sobre quem relatou."
        assert comite.afastamentos(caso_id) == []

    def test_nao_se_afasta_quem_manifestou_na_ouvidoria(self, comite):
        caso_id = comite.caso()
        comite.linha(caso_id)["manifestacao_id"] = "man-1"
        comite.banco.tabelas["ouvidoria_protocolos"] = [{"id": "man-1", "manifestante_nome": "Bruno Dias"}]
        citado_id = comite.citar(MEMBRO, caso_id, nome="Bruno Dias")

        assert comite.afastar(COORDENACAO, caso_id, citado_id).status_code == 422

    def test_a_testemunha_ouvida_pode_ser_afastada(self, comite):
        caso_id = comite.caso(etapa="apuracao")
        comite.cliente(COORDENACAO).post(
            f"{BASE}/casos/{caso_id}/depoimentos",
            json={"nome": ACUSADO, "cargo": "Supervisor", "papel": "acusado"},
        )
        citado_id = comite.citar(MEMBRO, caso_id)

        assert comite.afastar(COORDENACAO, caso_id, citado_id).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 7. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_do_canal_diz_o_afastamento_cautelar():
    from pathlib import Path

    kit = (Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "canal-de-conduta.md").read_text(
        encoding="utf-8"
    )
    assert "## O afastamento cautelar" in kit
    assert "O afastamento cautelar é remunerado e não é punição." in kit
    assert "o coordenador do Comitê registra a decisão de afastar" in kit
    assert "só quem afastar e o motivo" in kit
    assert "a coordenação vê só o pedido" in kit
    assert "é o parecer que define" in kit
    assert "com ciência dos membros do grupo" in kit
    assert "nunca recai sobre quem relatou" in kit
