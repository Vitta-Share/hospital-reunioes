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
                "rodada_do_voto": 1,  # o default da coluna (migration 216)
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

        segredos_dos_outros = {
            MEMBRO: ["Texto da Lia", "inconclusivo"],
            LEITOR: ["Texto do Bruno", "parcialmente_procedente"],
            COORDENACAO: ["Texto da Lia", "Texto do Bruno", "inconclusivo", "parcialmente_procedente"],
        }
        for pid, segredos in segredos_dos_outros.items():
            tela = json.dumps(comite.abrir(pid, caso), ensure_ascii=False)
            for segredo in segredos:
                assert segredo not in tela, (pid, segredo)
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


# ═══════════════════════════════════════════════════════════════════════════
# O resultado sai por maioria, e três medidas diferentes abrem a convocação
# da reunião curta
# ═══════════════════════════════════════════════════════════════════════════


class TestMaioria:
    def test_vale_a_maioria_do_resultado_e_da_medida(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, medida="suspensao", dias_de_suspensao=3)
        comite.votar(LEITOR, caso, medida="suspensao", dias_de_suspensao=3)
        comite.votar(COORDENACAO, caso, resultado="improcedente", medida=None)

        votacao = comite.abrir(COORDENACAO, caso)["votacao"]
        assert votacao["resultado"] == {"resultado": "procedente", "medida": "Suspensão de 3 dias"}
        assert votacao["reuniao_curta_convocada"] is False

    def test_tres_medidas_diferentes_convocam_a_reuniao_curta(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, medida="orientacao_registrada")
        comite.votar(LEITOR, caso, medida="advertencia_escrita")
        comite.votar(COORDENACAO, caso, medida="suspensao", dias_de_suspensao=2)

        votacao = comite.abrir(MEMBRO, caso)["votacao"]
        assert votacao["resultado"] is None
        assert votacao["reuniao_curta_convocada"] is True
        assert votacao["rodada"] == 2
        assert votacao["rodadas"][0]["reuniao_curta"] is True
        assert len(votacao["rodadas"][0]["votos"]) == 3
        convocacao = [t for t in comite.banco.tabelas["conduta_trilha"] if t["acao"] == "convocou_reuniao_curta"]
        assert len(convocacao) == 1
        avisos = [a for a in comite.banco.tabelas["conduta_avisos"] if a["motivo"] == "reuniao_curta"]
        assert sorted(a["participante_id"] for a in avisos) == sorted([MEMBRO, LEITOR, COORDENACAO])
        assert {a["referencia"] for a in avisos} == {"rodada-2"}

    def test_depois_da_reuniao_curta_os_tres_votam_de_novo(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, medida="orientacao_registrada")
        comite.votar(LEITOR, caso, medida="advertencia_escrita")
        comite.votar(COORDENACAO, caso, medida="suspensao", dias_de_suspensao=2)

        assert comite.votar(MEMBRO, caso, medida="advertencia_escrita").status_code == 200
        assert comite.abrir(LEITOR, caso)["votacao"]["meu_voto"] is None
        comite.votar(LEITOR, caso, medida="advertencia_escrita")
        comite.votar(COORDENACAO, caso, medida="advertencia_escrita")

        votacao = comite.abrir(LEITOR, caso)["votacao"]
        assert votacao["resultado"] == {"resultado": "procedente", "medida": "Advertência escrita"}
        assert [r["rodada"] for r in votacao["rodadas"]] == [1, 2]

    def _ultimo_voto_sem_convocacao(self, comite, caso, monkeypatch):
        """Três medidas diferentes, e a convocação cai depois de gravado o
        último voto: a rodada fecha sem maioria e o caso fica na rodada 1."""
        comite.votar(MEMBRO, caso, medida="orientacao_registrada")
        comite.votar(LEITOR, caso, medida="advertencia_escrita")
        registrar = voto.trilha.registrar

        def _cai_na_convocacao(supabase, caso_id, autor_id, acao, detalhe=""):
            if acao == "convocou_reuniao_curta":
                raise RuntimeError("trilha fora do ar")
            return registrar(supabase, caso_id, autor_id, acao, detalhe)

        monkeypatch.setattr(voto.trilha, "registrar", _cai_na_convocacao)
        with pytest.raises(RuntimeError):
            comite.votar(COORDENACAO, caso, medida="suspensao", dias_de_suspensao=2)
        monkeypatch.setattr(voto.trilha, "registrar", registrar)
        assert comite.linha_do_caso(caso)["rodada_do_voto"] == 1

    def _convocacoes(self, comite) -> list[dict]:
        return [t for t in comite.banco.tabelas["conduta_trilha"] if t["acao"] == "convocou_reuniao_curta"]

    def test_a_reuniao_curta_que_falhou_no_ultimo_voto_e_convocada_ao_abrir_o_caso(self, comite, monkeypatch):
        caso = comite.caso()
        self._ultimo_voto_sem_convocacao(comite, caso, monkeypatch)

        votacao = comite.abrir(MEMBRO, caso)["votacao"]

        assert votacao["rodada"] == 2
        assert votacao["reuniao_curta_convocada"] is True
        assert len(self._convocacoes(comite)) == 1
        avisos = [a for a in comite.banco.tabelas["conduta_avisos"] if a["motivo"] == "reuniao_curta"]
        assert sorted(a["participante_id"] for a in avisos) == sorted([MEMBRO, LEITOR, COORDENACAO])
        assert comite.votar(MEMBRO, caso, medida="advertencia_escrita").status_code == 200
        comite.abrir(LEITOR, caso)
        assert len(self._convocacoes(comite)) == 1

    def test_o_voto_seguinte_abre_a_rodada_que_a_convocacao_nao_abriu(self, comite, monkeypatch):
        caso = comite.caso()
        self._ultimo_voto_sem_convocacao(comite, caso, monkeypatch)

        resposta = comite.votar(MEMBRO, caso, medida="advertencia_escrita")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["voto"]["rodada"] == 2
        assert comite.linha_do_caso(caso)["rodada_do_voto"] == 2

    def test_a_conclusao_nao_diz_que_convocou_a_reuniao_que_nao_foi_convocada(self, comite, monkeypatch):
        caso = comite.caso()
        self._ultimo_voto_sem_convocacao(comite, caso, monkeypatch)

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")

        assert resposta.status_code == 409
        assert "Faltam votos" in resposta.json()["detail"]
        assert comite.linha_do_caso(caso)["rodada_do_voto"] == 2
        assert len(self._convocacoes(comite)) == 1

    def test_resultado_sem_maioria_tambem_convoca(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso)
        comite.votar(LEITOR, caso, resultado="improcedente", medida=None)
        comite.votar(COORDENACAO, caso, resultado="inconclusivo", medida=None)

        assert comite.abrir(MEMBRO, caso)["votacao"]["reuniao_curta_convocada"] is True

    def test_a_coordenacao_conclui_com_a_maioria_e_o_caso_vai_a_ata(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, resultado="improcedente", medida=None)
        comite.votar(LEITOR, caso, resultado="improcedente", medida=None)
        comite.votar(COORDENACAO, caso)

        assert comite.post(MEMBRO, f"/casos/{caso}/conclusao-da-votacao").status_code == 403
        resposta = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")

        assert resposta.status_code == 200, resposta.text
        linha = comite.linha_do_caso(caso)
        assert linha["resultado"] == "improcedente"
        assert linha["etapa"] == "ata"
        assert comite.abrir(COORDENACAO, caso)["trilho"][3] == {"nome": "Ata", "estado": "atual"}

    def test_sem_todos_os_votos_a_votacao_nao_conclui(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, resultado="improcedente", medida=None)
        comite.votar(LEITOR, caso, resultado="improcedente", medida=None)

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")

        assert resposta.status_code == 409
        assert "Faltam votos" in resposta.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# O agente preenche a trava depois de um clique, e cada item precisa da
# confirmação de um membro
# ═══════════════════════════════════════════════════════════════════════════


def _itens(tela: dict) -> dict[str, dict]:
    return {i["item"]: i for i in tela["trava"]["itens"]}


class TestTravaPreenchidaEConfirmada:
    def test_sem_o_clique_o_agente_nao_roda(self, comite, modelo):
        caso = comite.caso()

        tela = comite.abrir(MEMBRO, caso)

        assert modelo.pedidos == []
        assert all(i["preenchimento"] is None for i in tela["trava"]["itens"])
        assert [i["item"] for i in tela["trava"]["itens"]] == list(ITENS_DA_TRAVA)

    def test_o_clique_preenche_os_sete_itens_sem_confirmar_nenhum(self, comite, modelo):
        caso = comite.caso()
        modelo.texto = _preenchimento_do_agente(prova={"atendido": False, "texto": "Só há o relato de [PESSOA_1]."})

        resposta = comite.post(MEMBRO, f"/casos/{caso}/trava/preenchimento")

        assert resposta.status_code == 200, resposta.text
        itens = _itens(comite.abrir(MEMBRO, caso))
        assert itens["prova"]["preenchimento"] == {"atendido": False, "texto": "Só há o relato de Rogério Valente."}
        assert itens["fato"]["preenchimento"]["atendido"] is True
        assert not any(i["confirmado"] for i in itens.values())
        assert len(modelo.pedidos) == 1

    def test_nenhum_nome_vai_ao_agente(self, comite, modelo):
        caso = comite.caso()

        comite.post(MEMBRO, f"/casos/{caso}/trava/preenchimento")

        saiu = modelo.tudo_que_saiu()
        assert "Rogério" not in saiu
        assert "Valente" not in saiu
        assert "[PESSOA_" in saiu

    def test_cada_item_precisa_da_confirmacao_de_um_membro(self, comite):
        caso = comite.caso()

        resposta = comite.confirmar(LEITOR, caso, "fato")

        assert resposta.status_code == 200, resposta.text
        itens = _itens(comite.abrir(MEMBRO, caso))
        assert itens["fato"]["confirmado"] is True
        assert itens["fato"]["confirmacoes"] == ["Lia Leitora"]
        assert itens["prova"]["confirmado"] is False
        assert any(t["acao"] == "confirmou_item_da_trava" for t in comite.banco.tabelas["conduta_trilha"])

    def test_quem_nao_vota_no_caso_nao_confirma(self, comite):
        caso = comite.caso()

        assert comite.confirmar(DE_FORA, caso, "fato").status_code == 403

    def test_a_ciencia_do_codigo_so_se_confirma_com_o_documento_anexado(self, comite):
        caso = comite.caso()

        sem_documento = comite.confirmar(MEMBRO, caso, "ciencia")
        assert sem_documento.status_code == 409
        assert "ciência do Código" in sem_documento.json()["detail"]

        assert comite.anexar_ciencia(MEMBRO, caso).status_code == 200
        assert comite.confirmar(MEMBRO, caso, "ciencia").status_code == 200

    def test_a_ciencia_fica_cifrada_e_sai_so_pelo_backend(self, comite):
        caso = comite.caso()
        comite.anexar_ciencia(MEMBRO, caso)

        guardado = list(comite.banco.storage.objetos.values())[0]
        assert b"ciencia do codigo" not in guardado
        aberta = comite.cliente(LEITOR).get(f"{BASE}/casos/{caso}/trava/ciencia")
        assert aberta.content == b"%PDF-1.4 ciencia do codigo"
        assert comite.banco.storage.urls_assinadas == []

    def test_o_item_dos_votos_espera_os_tres_votos(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso)

        assert comite.confirmar(MEMBRO, caso, "votos").status_code == 409
        comite.votar(LEITOR, caso)
        comite.votar(COORDENACAO, caso)
        assert comite.confirmar(MEMBRO, caso, "votos").status_code == 200

    def test_sem_o_acusado_ouvido_a_recusa_e_certificada_por_dois_membros(self, comite):
        caso = comite.caso(acusado_ouvido=False)

        comite.confirmar(MEMBRO, caso, "defesa")
        assert _itens(comite.abrir(MEMBRO, caso))["defesa"]["confirmado"] is False
        assert comite.confirmar(MEMBRO, caso, "defesa").status_code == 409

        comite.confirmar(LEITOR, caso, "defesa")
        assert _itens(comite.abrir(MEMBRO, caso))["defesa"]["confirmado"] is True

    def test_com_o_acusado_ouvido_a_defesa_pede_um_membro(self, comite):
        caso = comite.caso()

        comite.confirmar(MEMBRO, caso, "defesa")

        assert _itens(comite.abrir(MEMBRO, caso))["defesa"]["confirmado"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Com item da trava em aberto, concluir como procedente ou parcialmente
# procedente fica bloqueado, com o motivo
# ═══════════════════════════════════════════════════════════════════════════


class TestTravaBloqueiaAConclusao:
    def _votos(self, comite, caso, resultado):
        for pid in (MEMBRO, LEITOR, COORDENACAO):
            comite.votar(pid, caso, resultado=resultado, medida="advertencia_escrita")

    @pytest.mark.parametrize("resultado", ["procedente", "parcialmente_procedente"])
    def test_item_em_aberto_bloqueia_com_o_motivo(self, comite, resultado):
        caso = comite.caso()
        self._votos(comite, caso, resultado)
        comite.anexar_ciencia(COORDENACAO, caso)
        for item in ITENS_DA_TRAVA:
            if item != "regra":
                comite.confirmar(COORDENACAO, caso, item)

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")

        assert resposta.status_code == 409
        motivo = resposta.json()["detail"]
        assert motivo == "A trava de robustez tem item em aberto: Regra violada indicada (item do Código de Conduta)."
        assert comite.abrir(COORDENACAO, caso)["votacao"]["bloqueio_da_conclusao"] == motivo
        assert comite.linha_do_caso(caso).get("resultado") is None
        assert comite.linha_do_caso(caso)["etapa"] == "voto"

    def test_com_a_trava_inteira_conclui_como_procedente(self, comite):
        caso = comite.caso()
        self._votos(comite, caso, "procedente")
        comite.trava_completa(caso)

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")

        assert resposta.status_code == 200, resposta.text
        linha = comite.linha_do_caso(caso)
        assert linha["resultado"] == "procedente"
        assert json.loads(cifra.decifrar_texto(linha["medida_cifrada"])) == {
            "medida": "advertencia_escrita",
            "dias_de_suspensao": None,
        }

    def test_improcedente_conclui_com_a_trava_em_aberto(self, comite):
        caso = comite.caso()
        for pid in (MEMBRO, LEITOR, COORDENACAO):
            comite.votar(pid, caso, resultado="inconclusivo", medida=None)

        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 200
        assert comite.linha_do_caso(caso)["resultado"] == "inconclusivo"


# ═══════════════════════════════════════════════════════════════════════════
# O agente não redige justificativa de voto
# ═══════════════════════════════════════════════════════════════════════════


class TestAgenteNaoRedigeVoto:
    def test_a_justificativa_e_a_que_o_membro_escreveu(self, comite, modelo):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, justificativa="  Minhas palavras, exatamente.  ")

        assert comite.abrir(MEMBRO, caso)["votacao"]["meu_voto"]["justificativa"] == "Minhas palavras, exatamente."
        assert modelo.pedidos == []

    def test_o_agente_da_trava_nao_recebe_o_conteudo_dos_votos(self, comite, modelo):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, justificativa="Justificativa secreta do Bruno.")
        comite.votar(LEITOR, caso, medida="suspensao", dias_de_suspensao=7, justificativa="Outra da Lia.")

        comite.post(MEMBRO, f"/casos/{caso}/trava/preenchimento")

        saiu = modelo.tudo_que_saiu()
        assert "Justificativa secreta" not in saiu
        assert "Outra da Lia" not in saiu
        assert "Votos registrados: 2 de 3." in saiu

    def test_o_modulo_do_voto_nao_chama_a_ia(self):
        arvore = ast.parse(Path(voto.__file__).read_text(encoding="utf-8"))
        nomes = {n.id for n in ast.walk(arvore) if isinstance(n, ast.Name)}
        nomes |= {n.attr for n in ast.walk(arvore) if isinstance(n, ast.Attribute)}
        importados = {a.name for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom) for a in n.names}

        assert not {"messages", "ClienteDaAnthropic", "load_prompt"} & (nomes | importados)

    def test_nenhuma_rota_do_voto_chama_o_agente_alem_da_trava(self):
        rotas_com_ia = [
            rota.path
            for rota in conduta_voto.router.routes
            if "chamar_ia_fora_do_loop" in rota.endpoint.__code__.co_names
            or "ai_processor" in rota.endpoint.__code__.co_names
        ]
        assert rotas_com_ia == ["/comite-de-conduta/casos/{caso_id}/trava/preenchimento"]


# ═══════════════════════════════════════════════════════════════════════════
# Suplente convocado vota no lugar do impedido
# ═══════════════════════════════════════════════════════════════════════════


class TestSuplenteVota:
    def test_o_suplente_convocado_vota_no_lugar_do_impedido(self, comite):
        caso = comite.caso()
        assert comite.votar(SUPLENTE, caso).status_code == 403

        impedido = comite.post(MEMBRO, f"/casos/{caso}/impedimento", {"motivo": "parentesco"})
        assert impedido.status_code == 200, impedido.text

        assert comite.votar(SUPLENTE, caso, justificativa="Voto do suplente.").status_code == 200
        assert comite.votar(MEMBRO, caso).status_code == 403
        comite.votar(LEITOR, caso)
        comite.votar(COORDENACAO, caso)

        votacao = comite.abrir(SUPLENTE, caso)["votacao"]
        assert votacao["votantes"] == 3
        assert {v["membro"] for v in votacao["rodadas"][0]["votos"]} == {
            "Sérgio Suplente",
            "Lia Leitora",
            "Ana Coordenadora",
        }

    def test_o_voto_de_quem_ficou_impedido_depois_sai_da_conta(self, comite):
        caso = comite.caso()
        comite.votar(MEMBRO, caso, justificativa="Voto que sai da conta.")
        comite.post(MEMBRO, f"/casos/{caso}/impedimento", {"motivo": "interesse"})

        votacao = comite.abrir(LEITOR, caso)["votacao"]
        assert votacao["votaram"] == 0
        assert votacao["votantes"] == 3

    def test_a_confirmacao_da_trava_de_quem_ficou_impedido_depois_sai_da_conta(self, comite):
        caso = comite.caso()
        assert comite.confirmar(MEMBRO, caso, "prova").status_code == 200
        comite.post(MEMBRO, f"/casos/{caso}/impedimento", {"motivo": "interesse"})
        for pid in (SUPLENTE, LEITOR, COORDENACAO):
            assert comite.votar(pid, caso).status_code == 200
        comite.anexar_ciencia(COORDENACAO, caso)
        for item in ITENS_DA_TRAVA:
            if item != "prova":
                comite.confirmar(COORDENACAO, caso, item)

        prova = _itens(comite.abrir(LEITOR, caso))["prova"]
        assert prova["confirmado"] is False
        assert prova["confirmacoes"] == []
        resposta = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")
        assert resposta.status_code == 409
        assert resposta.json()["detail"] == (
            "A trava de robustez tem item em aberto: "
            "Prova além do relato (relato anônimo sozinho não sustenta punição)."
        )
        assert comite.confirmar(LEITOR, caso, "prova").status_code == 200

    def test_a_certificacao_da_recusa_por_um_citado_nao_vale(self, comite):
        caso = comite.caso(acusado_ouvido=False)
        comite.confirmar(MEMBRO, caso, "defesa")
        comite.confirmar(LEITOR, caso, "defesa")
        comite.banco.tabelas.setdefault("conduta_citados", []).append(
            {"id": "cit-1", "caso_id": caso, "participante_id": LEITOR}
        )

        defesa = _itens(comite.abrir(MEMBRO, caso))["defesa"]
        assert defesa["confirmado"] is False
        assert defesa["confirmacoes"] == ["Bruno Membro"]


# ═══════════════════════════════════════════════════════════════════════════
# O texto do Produto Canal de Conduta no kit de conhecimento diz o
# comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    @pytest.mark.parametrize(
        "frase",
        [
            "## O voto e a trava de robustez",
            "VOTAR",
            "oculto até os três votarem",
            "reunião curta",
            "PREENCHER TRAVA",
            "ciência do Código",
            "CONCLUIR VOTAÇÃO",
            "não redige",
            "suplente convocado vota",
        ],
    )
    def test_o_kit_diz_o_comportamento_novo(self, frase):
        assert frase in (CONHECIMENTO_DIR / "canal-de-conduta.md").read_text(encoding="utf-8")
