"""O portão de acesso ao caso do Canal de Conduta (issue #1820, ADR 0097, decisão 4).

Toda rota do lado do Comitê passa pelo mesmo portão, que autoriza pela
atribuição ao caso, barra o impedido e o Citado, não deixa o super admin
passar e grava a leitura na trilha na mesma chamada.

As pessoas e os casos daqui são de teste. O banco é o dublê de
`conduta_apoio`, e o relato é cifrado de verdade, com uma chave gerada na hora.
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
from app.limiter import limiter  # noqa: E402
from app.routers import conduta_comite  # noqa: E402
from app.services.conduta import casos  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402

ROTA_LISTA = "/api/comite-de-conduta/casos"
RELATO = "O encarregado da manutenção ameaçou demitir quem reclamasse das horas extras."
RECUSA = {"detail": "Sem acesso a este conteúdo do Canal de Conduta"}

HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente"}
SUPER_ADMIN = {"access_profile": "super_admin", "is_super_admin": True}


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    limiter._storage.reset()
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    yield
    limiter._storage.reset()


def _pessoa(pid: str = "P1", **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": "Pessoa de Teste",
        "email": f"{pid.lower()}@hsm.test",
        "role": None,
        "ativo": True,
        "is_super_admin": False,
        "access_profile": None,
    }
    return {**base, **campos}


def _participacao(pid="P1", *, papel="membro", termo=True, colegiado=COMITE, inicio=-30, fim=600) -> dict:
    return {
        "id": f"part-{pid}-{colegiado['slug']}",
        "colegiado_id": colegiado["id"],
        "participante_id": pid,
        "papel": papel,
        "vigencia_inicio": (HOJE + timedelta(days=inicio)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=fim)).isoformat(),
        "termo_assinado_em": "2026-10-01T12:00:00+00:00" if termo else None,
    }


class _Cenario:
    def __init__(self, pessoa: dict, participacoes: list[dict] | None = None):
        self.pessoa = pessoa
        self.banco = Banco(
            {
                "participantes": [pessoa],
                "colegiados": [dict(COMITE), dict(NUCLEO)],
                "participacoes": list(participacoes or []),
            }
        )

    def caso(self, rota: str = "comum") -> dict:
        novo = casos.registrar_caso(self.banco, relato=RELATO, categoria="assedio_moral", rota=rota)
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == novo["id"])

    def atribuir(self, caso: dict, motivo: str, **campos) -> None:
        self.banco.tabelas.setdefault("conduta_atribuicoes", []).append(
            {
                "caso_id": caso["id"],
                "participante_id": self.pessoa["id"],
                "motivo": motivo,
                "termo_assinado_em": None,
                "impedido_em": None,
                "revogada_em": None,
                **campos,
            }
        )

    def citar(self, caso: dict) -> None:
        self.banco.tabelas.setdefault("conduta_citados", []).append(
            {"caso_id": caso["id"], "participante_id": self.pessoa["id"], "nome_cifrado": None}
        )

    def leituras(self) -> list[dict]:
        return [linha for linha in self.banco.tabelas.get("conduta_trilha", []) if linha["acao"] == "leitura"]

    def cliente(self) -> TestClient:
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(conduta_comite.router, prefix="/api")
        pessoa = self.pessoa

        async def _usuario() -> dict[str, Any]:
            return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app)


def _rota_do_caso(caso: dict) -> str:
    return f"{ROTA_LISTA}/{caso['id']}"


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quem lista e abre
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemAbre:
    @pytest.mark.parametrize("papel", ["membro", "coordenacao", "segundo_leitor"])
    def test_membro_com_participacao_vigente_e_termo_lista_e_abre_caso_comum(self, papel):
        cenario = _Cenario(_pessoa(), [_participacao(papel=papel)])
        caso = cenario.caso()
        cliente = cenario.cliente()

        lista = cliente.get(ROTA_LISTA)
        assert lista.status_code == 200, lista.text
        assert [c["protocolo"] for c in lista.json()["casos"]] == [caso["protocolo"]]
        assert "relato" not in lista.text and "relato_cifrado" not in lista.text

        aberto = cliente.get(_rota_do_caso(caso))
        assert aberto.status_code == 200, aberto.text
        assert aberto.json()["relato"] == RELATO
        assert aberto.json()["protocolo"] == caso["protocolo"]

    def test_funcionario_comum_recebe_403(self):
        cenario = _Cenario(_pessoa())
        caso = cenario.caso()
        cliente = cenario.cliente()

        _assert_recusado(cliente.get(ROTA_LISTA))
        _assert_recusado(cliente.get(_rota_do_caso(caso)))

    def test_super_admin_recebe_403(self):
        """Mutante: deixar o super admin passar no portão, como nos outros módulos."""
        cenario = _Cenario(_pessoa(**SUPER_ADMIN))
        caso = cenario.caso()
        cliente = cenario.cliente()

        _assert_recusado(cliente.get(ROTA_LISTA))
        _assert_recusado(cliente.get(_rota_do_caso(caso)))

    def test_membro_sem_termo_recebe_403(self):
        cenario = _Cenario(_pessoa(), [_participacao(termo=False)])
        caso = cenario.caso()
        cliente = cenario.cliente()

        _assert_recusado(cliente.get(ROTA_LISTA))
        _assert_recusado(cliente.get(_rota_do_caso(caso)))

    def test_membro_do_nucleo_nao_e_membro_do_comite(self):
        cenario = _Cenario(_pessoa(), [_participacao(colegiado=NUCLEO)])
        caso = cenario.caso()

        _assert_recusado(cenario.cliente().get(_rota_do_caso(caso)))

    def test_participacao_vencida_recebe_403(self):
        cenario = _Cenario(_pessoa(), [_participacao(inicio=-800, fim=-1)])
        caso = cenario.caso()

        _assert_recusado(cenario.cliente().get(_rota_do_caso(caso)))

    def test_suplente_sem_convocacao_nao_abre(self):
        cenario = _Cenario(_pessoa(), [_participacao(papel="suplente")])
        caso = cenario.caso()

        _assert_recusado(cenario.cliente().get(_rota_do_caso(caso)))

    def test_suplente_convocado_abre_so_o_caso_da_convocacao(self):
        cenario = _Cenario(_pessoa(), [_participacao(papel="suplente")])
        convocado = cenario.caso()
        outro = cenario.caso()
        cenario.atribuir(convocado, "suplente_convocado")
        cliente = cenario.cliente()

        assert [c["id"] for c in cliente.get(ROTA_LISTA).json()["casos"]] == [convocado["id"]]
        assert cliente.get(_rota_do_caso(convocado)).status_code == 200
        _assert_recusado(cliente.get(_rota_do_caso(outro)))

    def test_apurador_sem_termo_do_caso_nao_abre_e_com_termo_abre(self):
        cenario = _Cenario(_pessoa())
        caso = cenario.caso()
        cenario.atribuir(caso, "apurador")
        _assert_recusado(cenario.cliente().get(_rota_do_caso(caso)))

        cenario.banco.tabelas["conduta_atribuicoes"][0]["termo_assinado_em"] = "2026-11-01T10:00:00+00:00"
        assert cenario.cliente().get(_rota_do_caso(caso)).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 2. Rota Especial, impedido e Citado
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemEBarrado:
    def test_caso_especial_nao_esta_na_fila_do_comite(self):
        cenario = _Cenario(_pessoa(), [_participacao(papel="coordenacao")])
        especial = cenario.caso(rota="especial")
        cliente = cenario.cliente()

        assert cliente.get(ROTA_LISTA).json()["casos"] == []
        _assert_recusado(cliente.get(_rota_do_caso(especial)))

    def test_grupo_especial_designado_abre_o_caso_especial(self):
        cenario = _Cenario(_pessoa(), [_participacao()])
        especial = cenario.caso(rota="especial")
        cenario.atribuir(especial, "grupo_especial")

        assert cenario.cliente().get(_rota_do_caso(especial)).status_code == 200

    def test_impedido_nao_abre_nem_ve_o_caso(self):
        cenario = _Cenario(_pessoa(), [_participacao(papel="coordenacao")])
        impedido = cenario.caso()
        livre = cenario.caso()
        cenario.atribuir(impedido, "membro_do_comite", impedido_em="2026-11-10T10:00:00+00:00")
        cliente = cenario.cliente()

        assert [c["id"] for c in cliente.get(ROTA_LISTA).json()["casos"]] == [livre["id"]]
        _assert_recusado(cliente.get(_rota_do_caso(impedido)))

    def test_citado_nao_abre_nem_ve_o_caso_em_nenhum_perfil(self):
        """Mutante: esquecer o Citado no portão."""
        cenario = _Cenario(_pessoa(), [_participacao(papel="coordenacao")])
        citado = cenario.caso(rota="especial")
        cenario.atribuir(citado, "grupo_especial")
        cenario.citar(citado)
        cliente = cenario.cliente()

        assert cliente.get(ROTA_LISTA).json()["casos"] == []
        _assert_recusado(cliente.get(_rota_do_caso(citado)))

    def test_caso_que_nao_existe_recebe_a_mesma_recusa(self):
        cenario = _Cenario(_pessoa(), [_participacao()])

        _assert_recusado(cenario.cliente().get(f"{ROTA_LISTA}/00000000-0000-4000-8000-000000000000"))


# ═══════════════════════════════════════════════════════════════════════════
# 3. A leitura na trilha
# ═══════════════════════════════════════════════════════════════════════════


class TestLeituraNaTrilha:
    def test_cada_abertura_grava_uma_linha_com_quem_quando_e_o_que(self):
        """Mutante: abrir o caso sem gravar a leitura."""
        cenario = _Cenario(_pessoa(), [_participacao()])
        caso = cenario.caso()
        cliente = cenario.cliente()

        cliente.get(_rota_do_caso(caso))
        cliente.get(_rota_do_caso(caso))

        leituras = cenario.leituras()
        assert len(leituras) == 2
        assert all(linha["caso_id"] == caso["id"] for linha in leituras)
        assert all(linha["autor_id"] == "P1" for linha in leituras)
        assert all(linha["registrado_em"] for linha in leituras)
        assert all(linha["detalhe"] == "abriu o caso" for linha in leituras)

    def test_a_recusa_nao_grava_leitura(self):
        cenario = _Cenario(_pessoa(**SUPER_ADMIN))
        caso = cenario.caso()

        cenario.cliente().get(_rota_do_caso(caso))

        assert cenario.leituras() == []

    def test_sem_a_leitura_gravada_o_caso_nao_abre(self):
        """Fail-closed: se a trilha não grava, o relato não sai."""
        cenario = _Cenario(_pessoa(), [_participacao()])
        caso = cenario.caso()
        cenario.banco.falhas_da_trilha = 10

        resposta = cenario.cliente().get(_rota_do_caso(caso))

        assert resposta.status_code == 503
        assert RELATO not in resposta.text


# ═══════════════════════════════════════════════════════════════════════════
# 4. Sem a chave de cifra
# ═══════════════════════════════════════════════════════════════════════════


class TestSemAChave:
    def test_sem_a_chave_o_portao_responde_503_e_nao_grava_nada(self, monkeypatch):
        cenario = _Cenario(_pessoa(), [_participacao()])
        caso = cenario.caso()
        trilha_antes = len(cenario.banco.tabelas["conduta_trilha"])
        monkeypatch.setattr(settings, "conduta_chave_cifra", "")
        cliente = cenario.cliente()

        assert cliente.get(ROTA_LISTA).status_code == 503
        resposta = cliente.get(_rota_do_caso(caso))
        assert resposta.status_code == 503
        assert len(cenario.banco.tabelas["conduta_trilha"]) == trilha_antes
