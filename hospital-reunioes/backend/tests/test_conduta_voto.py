"""O voto e a trava de robustez do Canal de Conduta (issue #1833; especificação,
seções 6.6, 6.7 e 11; ADR 0097).

Cada classe é um critério de aceite da issue. O banco e o Storage são os
dublês de `conduta_apoio`, a cifra é de verdade, e o modelo é um dublê que
guarda o que recebeu e devolve o texto pedido.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from anthropic_apoio import resposta_de_texto
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.routers import conduta_comite, conduta_voto  # noqa: E402
from app.services.conduta import casos, cifra, trava, voto  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

BASE = "/api/comite-de-conduta"
HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}
COORDENACAO, MEMBRO, LEITOR, SUPLENTE, DE_FORA = "COORD", "MEMB", "LEIT", "SUPL", "FORA"
NOMES = {
    COORDENACAO: "Ana Coordenadora",
    MEMBRO: "Bruno Membro",
    LEITOR: "Lia Leitora",
    SUPLENTE: "Sérgio Suplente",
    DE_FORA: "Carla de Fora",
}
RELATO = "O supervisor Rogério Valente ameaçou cortar as horas da equipe do almoxarifado no dia 3 de outubro."
JUSTIFICATIVA = "Os depoimentos confirmam a ameaça.\nO acusado admitiu ter levantado a voz."
ITENS_DA_TRAVA = ("fato", "prova", "defesa", "regra", "ciencia", "medida", "votos")


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")


def _preenchimento_do_agente(**trocas: Any) -> str:
    itens = [{"item": item, "atendido": True, "texto": f"O item {item} consta do caso."} for item in ITENS_DA_TRAVA]
    for item in itens:
        if item["item"] in trocas:
            item.update(trocas[item["item"]])
    return json.dumps({"itens": itens})


class Modelo:
    """O agente de mentira: guarda cada pedido e devolve o texto dado."""

    def __init__(self, texto: str | None = None):
        self.texto = texto or _preenchimento_do_agente()
        self.pedidos: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.pedidos.append(kwargs)
        return resposta_de_texto(self.texto)

    def tudo_que_saiu(self) -> str:
        partes = []
        for pedido in self.pedidos:
            partes.append(str(pedido.get("system")))
            partes += [str(m["content"]) for m in pedido["messages"]]
        return "\n".join(partes)


@pytest.fixture
def modelo(monkeypatch) -> Modelo:
    falso = Modelo()
    monkeypatch.setattr(trava, "_cliente_do_agente_da_trava", lambda: falso)
    return falso


def _pessoa(pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": NOMES[pid],
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


class Comite:
    """Os três votantes (coordenação, membro e segundo leitor), um suplente,
    alguém de fora, e casos já na etapa Voto."""

    def __init__(self):
        self.banco = Banco(
            {
                "participantes": [_pessoa(p) for p in NOMES],
                "colegiados": [dict(COMITE)],
                "participacoes": [
                    _participacao(COORDENACAO, "coordenacao"),
                    _participacao(MEMBRO, "membro"),
                    _participacao(LEITOR, "segundo_leitor"),
                    _participacao(SUPLENTE, "suplente"),
                ],
            }
        )

    def caso(self, *, acusado_ouvido: bool = True) -> str:
        novo = casos.registrar_caso(self.banco, relato=RELATO, categoria=None)
        linha = next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == novo["id"])
        linha.update(
            {
                "recebido_em": datetime.now().astimezone().isoformat(),
                "etapa": "voto",
                "rito": "rapido",
                "escopo": "dentro",
            }
        )
        if acusado_ouvido:
            self.banco.tabelas.setdefault("conduta_depoimentos", []).append(
                {
                    "id": f"dep-{novo['id']}",
                    "caso_id": novo["id"],
                    "nome_cifrado": cifra.cifrar_texto("Rogério Valente"),
                    "cargo_cifrado": cifra.cifrar_texto("Supervisor do almoxarifado"),
                    "papel": "acusado",
                    "sem_gravacao_em": "2026-11-10T12:00:00+00:00",
                    "sem_gravacao_motivo_cifrado": cifra.cifrar_texto("O acusado não aceitou a gravação."),
                    "sem_gravacao_por": COORDENACAO,
                    "pontos_cifrados": cifra.cifrar_texto("Rogério Valente nega a ameaça e admite ter gritado."),
                    "concluido_em": "2026-11-10T13:00:00+00:00",
                    "criado_em": "2026-11-10T11:00:00+00:00",
                }
            )
        return novo["id"]

    def linha_do_caso(self, caso_id: str) -> dict:
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == caso_id)

    def cliente(self, pid: str) -> TestClient:
        app = FastAPI()
        app.include_router(conduta_comite.router, prefix="/api")
        app.include_router(conduta_voto.router, prefix="/api")
        pessoa = next(p for p in self.banco.tabelas["participantes"] if p["id"] == pid)

        async def _usuario() -> dict[str, Any]:
            return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app)

    def abrir(self, pid: str, caso_id: str) -> dict:
        resposta = self.cliente(pid).get(f"{BASE}/casos/{caso_id}")
        assert resposta.status_code == 200, resposta.text
        return resposta.json()

    def post(self, pid: str, caminho: str, json: dict | None = None):
        return self.cliente(pid).post(f"{BASE}{caminho}", json=json or {})

    def votar(self, pid: str, caso_id: str, **voto_dado):
        corpo = {
            "resultado": "procedente",
            "medida": "advertencia_escrita",
            "justificativa": JUSTIFICATIVA,
            **voto_dado,
        }
        return self.post(pid, f"/casos/{caso_id}/voto", corpo)

    def anexar_ciencia(self, pid: str, caso_id: str):
        return self.cliente(pid).post(
            f"{BASE}/casos/{caso_id}/trava/ciencia",
            files={"arquivo": ("ciencia.pdf", b"%PDF-1.4 ciencia do codigo", "application/pdf")},
        )

    def confirmar(self, pid: str, caso_id: str, item: str):
        return self.post(pid, f"/casos/{caso_id}/trava/confirmacao", {"item": item})

    def trava_completa(self, caso_id: str) -> None:
        assert self.anexar_ciencia(COORDENACAO, caso_id).status_code == 200
        for item in ITENS_DA_TRAVA:
            resposta = self.confirmar(COORDENACAO, caso_id, item)
            assert resposta.status_code == 200, resposta.text


@pytest.fixture
def comite() -> Comite:
    return Comite()


# ═══════════════════════════════════════════════════════════════════════════
# Cada membro vota com resultado, medida da Matriz e justificativa própria
# ═══════════════════════════════════════════════════════════════════════════


class TestCadaMembroVota:
    def test_o_membro_vota_e_ve_o_proprio_voto(self, comite):
        caso = comite.caso()

        resposta = comite.votar(MEMBRO, caso, resultado="procedente", medida="suspensao", dias_de_suspensao=5)

        assert resposta.status_code == 200, resposta.text
        votacao = comite.abrir(MEMBRO, caso)["votacao"]
        assert votacao["meu_voto"] == {
            "resultado": "procedente",
            "medida": "suspensao",
            "dias_de_suspensao": 5,
            "justificativa": JUSTIFICATIVA,
        }
        assert votacao["votaram"] == 1
        assert votacao["votantes"] == 3

    def test_o_voto_fica_cifrado_no_banco(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso)

        linha = comite.banco.tabelas["conduta_votos"][0]
        assert linha["voto_cifrado"].startswith("v1:")
        assert "Os depoimentos confirmam" not in json.dumps(linha)
        assert "procedente" not in json.dumps(linha)

    def test_a_medida_sai_da_matriz_de_consequencias(self, comite):
        caso = comite.caso()

        fora_da_matriz = comite.votar(MEMBRO, caso, medida="multa")
        sem_medida = comite.votar(MEMBRO, caso, medida=None)

        assert fora_da_matriz.status_code == 422
        assert sem_medida.status_code == 422
        assert "Matriz" in sem_medida.json()["detail"]

    def test_a_suspensao_vai_de_1_a_30_dias(self, comite):
        caso = comite.caso()

        assert comite.votar(MEMBRO, caso, medida="suspensao", dias_de_suspensao=31).status_code == 422
        assert comite.votar(MEMBRO, caso, medida="suspensao").status_code == 422
        assert comite.votar(MEMBRO, caso, medida="suspensao", dias_de_suspensao=30).status_code == 200

    def test_improcedente_nao_leva_medida(self, comite):
        caso = comite.caso()

        assert comite.votar(MEMBRO, caso, resultado="improcedente", medida="advertencia_escrita").status_code == 422
        assert comite.votar(MEMBRO, caso, resultado="improcedente", medida=None).status_code == 200

    def test_a_justificativa_tem_de_uma_a_tres_linhas(self, comite):
        caso = comite.caso()

        assert comite.votar(MEMBRO, caso, justificativa="  ").status_code == 422
        assert comite.votar(MEMBRO, caso, justificativa="um\ndois\ntrês\nquatro").status_code == 422
        assert comite.votar(MEMBRO, caso, justificativa="um\ndois\ntrês").status_code == 200

    def test_cada_membro_vota_uma_vez(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso)

        assert comite.votar(MEMBRO, caso).status_code == 409

    def test_quem_nao_e_votante_nao_vota(self, comite):
        caso = comite.caso()

        assert comite.votar(DE_FORA, caso).status_code == 403

    def test_so_se_vota_na_etapa_voto(self, comite):
        caso = comite.caso()
        comite.linha_do_caso(caso)["etapa"] = "apuracao"

        assert comite.votar(MEMBRO, caso).status_code == 409

    def test_o_voto_entra_na_trilha_sem_o_conteudo(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso)

        linha = [t for t in comite.banco.tabelas["conduta_trilha"] if t["acao"] == "votou"]
        assert len(linha) == 1
        assert linha[0]["autor_id"] == MEMBRO
        assert "procedente" not in linha[0]["detalhe"]
        assert "advert" not in linha[0]["detalhe"]

    def test_a_caixa_do_caso_mostra_votar_ao_votante(self, comite):
        caso = comite.caso()

        caixa = comite.abrir(MEMBRO, caso)["o_que_fazer_agora"]
        assert caixa["botao"] == "VOTAR"
        assert caixa["bloqueio"] is None

        comite.votar(MEMBRO, caso)
        assert "já votou" in comite.abrir(MEMBRO, caso)["o_que_fazer_agora"]["bloqueio"]


# ═══════════════════════════════════════════════════════════════════════════
# Enquanto faltar voto, nenhum membro vê o voto dos outros, nem pela API
# ═══════════════════════════════════════════════════════════════════════════


class TestVotoOculto:
    def test_com_dois_votos_ninguem_ve_o_voto_do_outro(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, resultado="parcialmente_procedente", justificativa="Texto do Bruno, só dele.")
        comite.votar(LEITOR, caso, resultado="inconclusivo", medida=None, justificativa="Texto da Lia, só dela.")

        for pid in (MEMBRO, LEITOR, COORDENACAO):
            tela = json.dumps(comite.abrir(pid, caso), ensure_ascii=False)
            de_quem = {MEMBRO: "Lia", LEITOR: "Bruno", COORDENACAO: "Bruno"}[pid]
            assert f"Texto d{'a' if de_quem == 'Lia' else 'o'} {de_quem}" not in tela
            votacao = comite.abrir(pid, caso)["votacao"]
            assert votacao["votaram"] == 2
            assert votacao["rodadas"] == []
            assert votacao["resultado"] is None

    def test_com_os_tres_votos_todos_veem_os_votos(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, justificativa="Texto do Bruno.")
        comite.votar(LEITOR, caso, justificativa="Texto da Lia.")
        comite.votar(COORDENACAO, caso, resultado="improcedente", medida=None, justificativa="Texto da Ana.")

        rodada = comite.abrir(MEMBRO, caso)["votacao"]["rodadas"][0]
        assert {v["membro"]: v["justificativa"] for v in rodada["votos"]} == {
            "Bruno Membro": "Texto do Bruno.",
            "Lia Leitora": "Texto da Lia.",
            "Ana Coordenadora": "Texto da Ana.",
        }

    def test_nenhuma_rota_devolve_o_voto_de_outro_antes_da_hora(self, comite):
        """Toda rota GET do router do voto, chamada por quem já votou."""
        caso = comite.caso()
        comite.votar(LEITOR, caso, justificativa="Segredo da Lia.")
        comite.votar(MEMBRO, caso)
        comite.anexar_ciencia(COORDENACAO, caso)
        cliente = comite.cliente(MEMBRO)

        rotas = [r.path for r in conduta_voto.router.routes if "GET" in r.methods]
        rotas.append("/comite-de-conduta/casos/{caso_id}")
        for rota in rotas:
            resposta = cliente.get("/api" + rota.replace("{caso_id}", caso))
            assert resposta.status_code == 200, rota
            assert b"Segredo da Lia" not in resposta.content
