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
from app.services.conduta.ritos import FUSO  # noqa: E402

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
        # No fuso do código: no CI em UTC, das 21h às 24h de São Paulo já é outro dia.
        quando = datetime.now(FUSO) - timedelta(days=dias_atras)
        linha = self.linha(novo["id"])
        linha["recebido_em"] = quando.isoformat()
        if linha["rota"] == "especial":
            linha["prazo_em"] = (quando.date() + timedelta(days=60)).isoformat()
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


# ═══════════════════════════════════════════════════════════════════════════
# 2. "Não sei" e o sinal do agente: fila comum com o aviso, e o desvio
# ═══════════════════════════════════════════════════════════════════════════


class TestNaoSeiESinalDoAgente:
    def test_relato_com_nao_sei_entra_na_fila_comum_com_o_aviso(self, comite):
        caso_id = comite.caso("nao_sei")

        assert caso_id in comite.lista(COORDENACAO)
        tela = comite.abre(COORDENACAO, caso_id).json()
        assert tela["aviso_de_rota_especial"] == rota_especial.AVISO
        assert tela["pode_desviar"] is True
        assert not comite.banco.tabelas.get("conduta_selos")

    def test_caso_com_sinal_do_agente_entra_na_fila_comum_com_o_aviso(self, comite):
        caso_id = comite.caso("nao")
        rota_especial.marcar_sinal_do_agente(comite.banco, caso_id)

        assert caso_id in comite.lista(SEGUNDO_LEITOR)
        assert comite.abre(SEGUNDO_LEITOR, caso_id).json()["aviso_de_rota_especial"] == rota_especial.AVISO

    def test_um_membro_confirma_o_desvio_e_o_caso_sai_da_fila_comum(self, comite):
        caso_id = comite.caso("nao_sei")

        resposta = comite.agir(SEGUNDO_LEITOR, caso_id, "desvio-especial")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["caso"]["rota"] == "especial"
        assert caso_id not in comite.lista(COORDENACAO)
        assert comite.abre(SEGUNDO_LEITOR, caso_id).status_code == 403
        assert comite.grupo(caso_id) == GRUPO_CERTO
        assert caso_id in comite.lista(MEMBRO)
        assert "desvio_especial" in [linha["acao"] for linha in comite.trilha(caso_id)]
        assert len(comite.banco.tabelas["conduta_selos"]) == 1

    def test_o_desvio_conta_o_prazo_de_60_dias_do_envio(self, comite):
        caso_id = comite.caso("nao_sei", dias_atras=10)

        comite.agir(MEMBRO, caso_id, "desvio-especial")

        envio = datetime.fromisoformat(comite.linha(caso_id)["recebido_em"]).date()
        assert comite.linha(caso_id)["prazo_em"] == (envio + timedelta(days=60)).isoformat()

    def test_caso_sem_o_aviso_nao_se_desvia(self, comite):
        caso_id = comite.caso("nao")

        resposta = comite.agir(COORDENACAO, caso_id, "desvio-especial")

        assert resposta.status_code == 409
        assert comite.linha(caso_id)["rota"] == "comum"

    def test_quem_nao_e_membro_da_fila_comum_nao_desvia(self, comite):
        caso_id = comite.caso("nao_sei")

        assert comite.agir(SUPLENTE, caso_id, "desvio-especial").status_code == 403
        assert comite.linha(caso_id)["rota"] == "comum"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Só o Grupo Especial lista e abre, e nenhum diretor entra nele
# ═══════════════════════════════════════════════════════════════════════════


class TestSoOGrupoEspecial:
    def test_o_grupo_e_o_membro_nao_diretor_e_um_suplente_nao_diretor(self, comite):
        caso_id = comite.caso("sim")

        assert comite.grupo(caso_id) == GRUPO_CERTO

    @pytest.mark.parametrize("pid", [COORDENACAO, SEGUNDO_LEITOR, SUPLENTE_DIRETOR])
    def test_nenhum_diretor_lista_nem_abre_o_caso_especial(self, comite, pid):
        caso_id = comite.caso("sim")

        resposta = comite.cliente(pid).get(f"{BASE}/casos")
        assert resposta.status_code == 403 or caso_id not in [c["id"] for c in resposta.json()["casos"]]
        assert comite.abre(pid, caso_id).status_code == 403

    def test_o_impedido_do_grupo_nao_e_trocado_por_suplente_diretor(self, comite):
        caso_id = comite.caso("sim")

        resposta = comite.agir(MEMBRO, caso_id, "impedimento", {"motivo": "parentesco"})

        assert resposta.status_code == 200, resposta.text
        assert comite.abre(SUPLENTE_DIRETOR, caso_id).status_code == 403
        convocados = [
            a["participante_id"]
            for a in comite.banco.tabelas["conduta_atribuicoes"]
            if a["caso_id"] == caso_id and a["motivo"] == "suplente_convocado"
        ]
        assert SUPLENTE_DIRETOR not in convocados

    def test_o_citado_nao_entra_no_grupo_pelo_desvio(self, comite):
        caso_id = comite.caso("nao_sei")
        comite.banco.tabelas.setdefault("conduta_citados", []).append(
            {"id": "cit-1", "caso_id": caso_id, "participante_id": MEMBRO, "nome_cifrado": None}
        )

        comite.agir(COORDENACAO, caso_id, "desvio-especial")

        assert comite.grupo(caso_id) == {SUPLENTE}

    def test_o_desvio_tira_quem_a_fila_comum_tinha_posto_no_caso(self, comite):
        caso_id = comite.caso("nao_sei")
        assert comite.agir(COORDENACAO, caso_id, "impedimento", {"motivo": "parentesco"}).status_code == 200
        comite.banco.tabelas["participantes"].append(_pessoa("APUR"))
        for pid, motivo in (("APUR", "apurador"), (NOVO_MEMBRO, "cipa")):
            comite.banco.tabelas["conduta_atribuicoes"].append(
                {
                    "id": f"atr-{pid}",
                    "caso_id": caso_id,
                    "participante_id": pid,
                    "motivo": motivo,
                    "termo_assinado_em": "2026-10-01T12:00:00+00:00",
                    "impedido_em": None,
                    "revogada_em": None,
                }
            )
        assert comite.abre(SUPLENTE_DIRETOR, caso_id).status_code == 200

        assert comite.agir(MEMBRO, caso_id, "desvio-especial").status_code == 200

        for pid in (SUPLENTE_DIRETOR, "APUR", NOVO_MEMBRO, COORDENACAO):
            assert comite.abre(pid, caso_id).status_code == 403, pid
            lista = comite.cliente(pid).get(f"{BASE}/casos")
            assert lista.status_code == 403 or caso_id not in [c["id"] for c in lista.json()["casos"]], pid
        assert comite.abre(MEMBRO, caso_id).status_code == 200
        resposta = comite.agir(
            SUPLENTE_DIRETOR, caso_id, "entrega-do-parecer", {"destinatario": "Conselho", "entregue_em": str(HOJE)}
        )
        assert resposta.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 4. Uma troca no Comitê não muda o grupo de um caso Especial aberto
# ═══════════════════════════════════════════════════════════════════════════


class TestGrupoFixo:
    def test_mudar_a_composicao_nao_altera_o_grupo_do_caso_aberto(self, comite):
        caso_id = comite.caso("sim")
        participacoes = comite.banco.tabelas["participacoes"]
        saida = next(p for p in participacoes if p["participante_id"] == MEMBRO)
        saida["encerrada_em"] = (HOJE - timedelta(days=1)).isoformat()
        participacoes.append(_participacao(NOVO_MEMBRO, "membro", diretor=False))

        assert comite.grupo(caso_id) == GRUPO_CERTO
        assert comite.abre(MEMBRO, caso_id).status_code == 200
        assert comite.abre(NOVO_MEMBRO, caso_id).status_code == 403
        assert caso_id not in comite.lista(NOVO_MEMBRO)

    def test_o_caso_novo_ja_nasce_com_o_grupo_de_hoje(self, comite):
        participacoes = comite.banco.tabelas["participacoes"]
        next(p for p in participacoes if p["participante_id"] == MEMBRO)["encerrada_em"] = (
            HOJE - timedelta(days=1)
        ).isoformat()
        participacoes.append(_participacao(NOVO_MEMBRO, "membro", diretor=False))

        caso_id = comite.caso("sim")

        assert comite.grupo(caso_id) == {NOVO_MEMBRO, SUPLENTE}


# ═══════════════════════════════════════════════════════════════════════════
# 5. Avisos de 15, 30 e 60 dias, e "Caso não respondido no prazo"
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def emails(monkeypatch) -> list[str]:
    enviados: list[str] = []

    def _enviar(destino, *_a, **_kw):
        enviados.append(destino)
        return True

    monkeypatch.setattr(avisos, "_enviar_email", _enviar)
    monkeypatch.setattr(avisos, "_montar", lambda: ("<p>aviso</p>", "aviso"))
    return enviados


def _marcos(comite: Comite, caso_id: str) -> dict[str, set[str]]:
    saida: dict[str, set[str]] = {}
    for aviso in comite.banco.tabelas.get("conduta_avisos", []):
        if aviso["caso_id"] == caso_id and aviso["motivo"].startswith("marco_"):
            saida.setdefault(aviso["motivo"], set()).add(aviso["participante_id"])
    return saida


class TestMarcosEPrazo:
    @pytest.mark.parametrize(("dias", "marco"), [(15, "marco_15"), (30, "marco_30"), (60, "marco_60")])
    def test_o_aviso_do_marco_sai_ao_grupo(self, comite, emails, dias, marco):
        caso_id = comite.caso("sim", dias_atras=dias)

        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _marcos(comite, caso_id) == {marco: GRUPO_CERTO}
        assert {"memb@hsm.test", "supl@hsm.test"} <= set(emails)
        assert "coord@hsm.test" not in emails

    def test_antes_de_15_dias_nao_ha_aviso_de_marco(self, comite, emails):
        caso_id = comite.caso("sim", dias_atras=14)

        avisos.rodada_do_dia(comite.banco, HOJE)

        assert _marcos(comite, caso_id) == {}

    def test_o_marco_sai_uma_vez_e_o_de_15_nao_vem_depois_do_de_30(self, comite, emails):
        caso_id = comite.caso("sim", dias_atras=30)
        avisos.rodada_do_dia(comite.banco, HOJE)
        avisos.rodada_do_dia(comite.banco, HOJE)
        avisos.rodada_do_dia(comite.banco, HOJE - timedelta(days=13))

        marcos = [a["motivo"] for a in comite.banco.tabelas["conduta_avisos"] if a["caso_id"] == caso_id]
        assert sorted(m for m in marcos if m.startswith("marco_")) == ["marco_30", "marco_30"]

    def test_prazo_vencido_sem_parecer_grava_caso_nao_respondido_no_prazo(self, comite, emails):
        caso_id = comite.caso("sim", dias_atras=61)

        avisos.rodada_do_dia(comite.banco, HOJE)

        detalhes = [linha["detalhe"] for linha in comite.trilha(caso_id) if linha["acao"] == "prazo_vencido"]
        assert detalhes == ["Caso não respondido no prazo"]
        assert [v["caso_id"] for v in comite.banco.tabelas["conduta_prazos_vencidos"]] == [caso_id]
        tela = comite.abre(MEMBRO, caso_id).json()
        assert tela["rota_especial"]["nao_respondido_no_prazo"] is True

    def test_dentro_do_prazo_nao_ha_registro_de_nao_respondido(self, comite, emails):
        caso_id = comite.caso("sim", dias_atras=59)

        avisos.rodada_do_dia(comite.banco, HOJE)

        assert not comite.banco.tabelas.get("conduta_prazos_vencidos")
        assert comite.abre(MEMBRO, caso_id).json()["rota_especial"]["nao_respondido_no_prazo"] is False

    def test_o_prazo_que_venceu_na_fila_comum_nao_vira_nao_respondido(self, comite, emails):
        caso_id = comite.caso("nao_sei", dias_atras=25)
        linha = comite.linha(caso_id)
        envio = datetime.fromisoformat(linha["recebido_em"]).date()
        linha.update({"rito": "rapido", "etapa": "apuracao", "prazo_em": (envio + timedelta(days=20)).isoformat()})
        assert comite.abre(COORDENACAO, caso_id).status_code == 200
        assert len(comite.banco.tabelas["conduta_prazos_vencidos"]) == 1

        assert comite.agir(MEMBRO, caso_id, "desvio-especial").status_code == 200

        assert comite.abre(MEMBRO, caso_id).json()["rota_especial"]["nao_respondido_no_prazo"] is False

    def test_caso_com_o_parecer_entregue_nao_vira_nao_respondido(self, comite, emails):
        caso_id = comite.caso("sim", dias_atras=59)
        comite.agir(MEMBRO, caso_id, "entrega-do-parecer", {"destinatario": "Conselho", "entregue_em": str(HOJE)})

        avisos.rodada_do_dia(comite.banco, HOJE + timedelta(days=5))

        assert not comite.banco.tabelas.get("conduta_prazos_vencidos")
        assert _marcos(comite, caso_id) == {}


# ═══════════════════════════════════════════════════════════════════════════
# 6. O grupo registra a entrega do parecer, com data e destinatário
# ═══════════════════════════════════════════════════════════════════════════

DESTINATARIO = "Presidente do Conselho de Administração"


class TestEntregaDoParecer:
    def test_o_grupo_registra_a_entrega_com_data_e_destinatario(self, comite):
        caso_id = comite.caso("sim", dias_atras=20)
        dia = HOJE - timedelta(days=2)

        resposta = comite.agir(
            SUPLENTE, caso_id, "entrega-do-parecer", {"destinatario": DESTINATARIO, "entregue_em": str(dia)}
        )

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["caso"]["desfecho"] == "parecer_entregue"
        entrega = comite.abre(MEMBRO, caso_id).json()["rota_especial"]["entrega"]
        assert entrega == {"destinatario": DESTINATARIO, "entregue_em": dia.isoformat()}
        gravada = comite.banco.tabelas["conduta_entregas_do_parecer"][0]
        assert DESTINATARIO not in gravada["destinatario_cifrado"]
        assert "entrega_do_parecer" in [linha["acao"] for linha in comite.trilha(caso_id)]

    def test_a_entrega_encerra_o_caso_e_nao_se_registra_duas_vezes(self, comite):
        caso_id = comite.caso("sim", dias_atras=20)
        corpo = {"destinatario": DESTINATARIO, "entregue_em": str(HOJE)}
        comite.agir(MEMBRO, caso_id, "entrega-do-parecer", corpo)

        assert comite.linha(caso_id)["encerrado_em"]
        assert comite.agir(MEMBRO, caso_id, "entrega-do-parecer", corpo).status_code == 409
        assert len(comite.banco.tabelas["conduta_entregas_do_parecer"]) == 1

    def test_entrega_sem_destinatario_ou_com_data_futura_e_recusada(self, comite):
        caso_id = comite.caso("sim", dias_atras=20)

        sem_nome = {"destinatario": "  ", "entregue_em": str(HOJE)}
        assert comite.agir(MEMBRO, caso_id, "entrega-do-parecer", sem_nome).status_code == 422
        futura = {"destinatario": DESTINATARIO, "entregue_em": str(HOJE + timedelta(days=1))}
        assert comite.agir(MEMBRO, caso_id, "entrega-do-parecer", futura).status_code == 422
        assert not comite.linha(caso_id).get("encerrado_em")

    def test_quem_nao_e_do_grupo_nao_registra_a_entrega(self, comite):
        caso_id = comite.caso("nao")

        corpo = {"destinatario": DESTINATARIO, "entregue_em": str(HOJE)}
        assert comite.agir(COORDENACAO, caso_id, "entrega-do-parecer", corpo).status_code == 403
        assert not comite.banco.tabelas.get("conduta_entregas_do_parecer")


# ═══════════════════════════════════════════════════════════════════════════
# 7. Fora do grupo, só a contagem
# ═══════════════════════════════════════════════════════════════════════════


class TestContagem:
    def test_fora_do_grupo_so_se_ve_a_contagem(self, comite):
        aberto = comite.caso("sim")
        concluido = comite.caso("sim", dias_atras=10)
        comite.agir(MEMBRO, concluido, "entrega-do-parecer", {"destinatario": DESTINATARIO, "entregue_em": str(HOJE)})
        comite.caso("sim")
        comite.caso("nao")

        resposta = comite.cliente(COORDENACAO).get(f"{BASE}/rota-especial/contagem")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {"recebidos": 3, "concluidos": 1, "em_aberto": 2}
        ids = comite.lista(COORDENACAO)
        assert aberto not in ids and concluido not in ids

    def test_quem_nao_esta_no_comite_nao_ve_nem_a_contagem(self, comite):
        comite.banco.tabelas["participantes"].append(_pessoa("FORA"))
        comite.caso("sim")

        assert comite.cliente("FORA").get(f"{BASE}/rota-especial/contagem").status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# A tela do caso e a MINHA VEZ do grupo
# ═══════════════════════════════════════════════════════════════════════════


class TestTelaDoGrupo:
    def test_a_caixa_do_caso_especial_diz_o_que_o_grupo_faz(self, comite):
        caso_id = comite.caso("sim")

        tela = comite.abre(MEMBRO, caso_id).json()

        assert "Rota Especial" in tela["o_que_fazer_agora"]["frase"]
        assert [etapa["nome"] for etapa in tela["trilho"]] == ["Apuração", "Parecer entregue"]
        assert tela["rota_especial"]["pode_registrar_entrega"] is True

    def test_o_caso_especial_aparece_na_minha_vez_do_grupo(self, comite):
        caso_id = comite.caso("sim")

        resposta = comite.cliente(SUPLENTE).get(f"{BASE}/minha-vez")

        assert [item["id"] for item in resposta.json()["itens"]] == [caso_id]

    def test_o_caso_encerrado_diz_que_o_parecer_foi_entregue(self, comite):
        caso_id = comite.caso("sim")
        comite.agir(MEMBRO, caso_id, "entrega-do-parecer", {"destinatario": DESTINATARIO, "entregue_em": str(HOJE)})

        tela = comite.abre(MEMBRO, caso_id).json()

        assert "parecer" in tela["o_que_fazer_agora"]["frase"]
        assert "Encaminhado" not in tela["o_que_fazer_agora"]["frase"]
        assert tela["rota_especial"]["pode_registrar_entrega"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 8. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_do_canal_diz_a_rota_especial():
    from pathlib import Path

    kit = (Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "canal-de-conduta.md").read_text(
        encoding="utf-8"
    )
    assert "## A Rota Especial" in kit
    assert "nunca entra na fila comum, e nem a coordenação o vê" in kit
    assert "qualquer membro do Comitê confirma o desvio para a Rota Especial" in kit
    assert "não muda até o fim" in kit
    assert "aos 15, aos 30 e aos 60 dias" in kit
    assert '"Caso não respondido no prazo"' in kit
    assert "registra na tela do caso a quem entregou e em que data" in kit
    assert "vê só a contagem" in kit
    assert "a Rota Especial, as perguntas ao relator" not in kit
