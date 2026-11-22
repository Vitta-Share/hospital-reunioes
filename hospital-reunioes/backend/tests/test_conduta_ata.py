"""A ata de deliberação e a reunião do Comitê de Conduta (issue #1834;
especificação, seções 6.7, 7.3, 8 e Anexo D; ADR 0097, decisão 7).

Cada classe é um critério de aceite da issue. O banco e o Storage são os
dublês de `conduta_apoio`, a cifra é de verdade, o modelo é um dublê que
guarda o que recebeu, e a ClickSign é sempre dublada (o pytest carrega as
credenciais reais).
"""

from __future__ import annotations

import ast
import base64
import json
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_conduta_voto import (
    BASE,
    COORDENACAO,
    ITENS_DA_TRAVA,
    LEITOR,
    MEMBRO,
    SUPLENTE,
    Comite,
    Modelo,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.routers import conduta_ata  # noqa: E402
from app.services import clicksign_service  # noqa: E402
from app.services.conduta import assinaturas, ata, cifra  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

RELATORIO = "Rogério Valente, supervisor, ameaçou cortar as horas da equipe. Duas testemunhas confirmam."
TRANSCRICAO = (
    "Bruno Membro: eu voto improcedente, não vi prova.\n"
    "Lia Leitora: a testemunha confirmou a ameaça de Rogério Valente na reunião de outubro."
)


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")


def _ata_do_agente(**trocas: Any) -> str:
    resposta = {
        "resumo": "[PESSOA_1] ameaçou cortar as horas da equipe do almoxarifado.",
        "provas": ["Depoimento de duas testemunhas."],
        "defesa": "[PESSOA_1] negou a ameaça e admitiu ter levantado a voz.",
        "fundamentos": "Item 3.2 do Código de Conduta, respeito nas relações de trabalho.",
        "correcao": ["Revisar a escala do almoxarifado."],
        "encaminhamentos": ["Envio à Direção."],
        "pontos_a_confirmar": ["Na transcrição um membro diz improcedente; o voto registrado é procedente."],
        **trocas,
    }
    return json.dumps(resposta, ensure_ascii=False)


class ComiteDaAta(Comite):
    def cliente(self, pid: str) -> TestClient:
        cliente = super().cliente(pid)
        cliente.app.include_router(conduta_ata.router, prefix="/api")
        return cliente

    def caso_no_rito(self, rito: str = "rapido") -> str:
        caso = self.caso()
        self.linha_do_caso(caso)["rito"] = rito
        self.banco.tabelas.setdefault("conduta_relatorios", []).append(
            {
                "id": f"rel-{caso}",
                "caso_id": caso,
                "tipo": "relatorio",
                "versao": 1,
                "texto_cifrado": cifra.cifrar_texto(RELATORIO),
                "origem": "agente",
                "autor_id": COORDENACAO,
                "criado_em": "2026-11-10T12:00:00+00:00",
            }
        )
        return caso

    def tres_votos(self, caso: str, resultado: str = "procedente") -> None:
        medida = "advertencia_escrita" if resultado in ("procedente", "parcialmente_procedente") else None
        for pid in (MEMBRO, LEITOR, COORDENACAO):
            assert self.votar(pid, caso, resultado=resultado, medida=medida).status_code == 200

    def anexar_transcricao(self, caso: str, nome: str = "reuniao.txt", conteudo: bytes = TRANSCRICAO.encode()):
        return self.cliente(COORDENACAO).post(
            f"{BASE}/casos/{caso}/reuniao/transcricao", files={"arquivo": (nome, conteudo, "text/plain")}
        )

    def gerar(self, caso: str, pid: str = COORDENACAO):
        return self.post(pid, f"/casos/{caso}/ata")

    def assinar(self, caso: str) -> None:
        assert self.post(COORDENACAO, f"/casos/{caso}/ata/assinatura").status_code == 200
        linha = next(
            a
            for a in self.banco.tabelas["conduta_assinaturas"]
            if a["caso_id"] == caso and a["tipo"] == "ata_de_deliberacao" and a["situacao"] == "enviado"
        )
        assinaturas.processar_evento(self.banco, linha, "auto_close")

    def trilha(self, caso: str) -> list[dict]:
        return [t for t in self.banco.tabelas.get("conduta_trilha", []) if t["caso_id"] == caso]


@pytest.fixture
def comite() -> ComiteDaAta:
    return ComiteDaAta()


class ModeloQueLe(Modelo):
    """Como o `Modelo`, mas escreve o acusado com o marcador que ele recebeu
    no relatório, como o agente de verdade faria."""

    def _create(self, **kwargs):
        achado = re.search(r"<relatorio_de_apuracao>\n(\[PESSOA_\d+\])", kwargs["messages"][0]["content"])
        self.texto = _ata_do_agente().replace("[PESSOA_1]", achado.group(1) if achado else "[PESSOA_1]")
        return super()._create(**kwargs)


@pytest.fixture
def modelo(monkeypatch) -> Modelo:
    falso = ModeloQueLe()
    monkeypatch.setattr(ata, "_cliente_do_agente_da_ata", lambda: falso)
    return falso


class _ClickSign:
    def __init__(self, monkeypatch):
        self.signatarios: list[str] = []
        self.dados: list[dict] = []
        monkeypatch.setattr(clicksign_service, "create_envelope", lambda nome: "env-ata")
        monkeypatch.setattr(clicksign_service, "add_document", lambda env, pdf, nome: "doc-ata")
        monkeypatch.setattr(
            clicksign_service, "add_signer", lambda env, nome, email: self.signatarios.append(email) or f"sig-{email}"
        )
        monkeypatch.setattr(clicksign_service, "create_qualification_requirement", lambda *a: True)
        monkeypatch.setattr(clicksign_service, "create_auth_requirement", lambda *a: True)
        monkeypatch.setattr(clicksign_service, "activate_envelope", lambda env: True)
        monkeypatch.setattr(clicksign_service, "notify_signers", lambda env: True)
        self.cancelados: list[str] = []
        monkeypatch.setattr(clicksign_service, "cancel_envelope", lambda env: self.cancelados.append(env) or True)
        monkeypatch.setattr(clicksign_service, "get_signed_document", lambda env: b"%PDF-ata-assinada")
        monkeypatch.setattr(assinaturas, "gerar_pdf_do_termo", lambda dados: self.dados.append(dados) or b"%PDF-ata")


@pytest.fixture
def clicksign(monkeypatch) -> _ClickSign:
    return _ClickSign(monkeypatch)


def _ata_na_tela(comite, caso: str, pid: str = COORDENACAO) -> dict:
    return comite.abrir(pid, caso)["ata"]


# ═══════════════════════════════════════════════════════════════════════════
# No rito rápido, a ata é gerada do relatório e dos votos
# ═══════════════════════════════════════════════════════════════════════════


class TestAtaDoRitoRapido:
    def test_a_ata_sai_do_relatorio_e_dos_votos_sem_reuniao(self, comite, modelo):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)

        resposta = comite.gerar(caso)

        assert resposta.status_code == 200, resposta.text
        (pedido,) = modelo.pedidos
        mensagem = pedido["messages"][0]["content"]
        assert "<relatorio_de_apuracao>" in mensagem
        assert "ameaçou cortar as horas" in mensagem
        assert "Os depoimentos confirmam a ameaça." in mensagem
        assert "<transcricao_da_reuniao>" not in mensagem
        assert "Não houve reunião" in mensagem
        documento = _ata_na_tela(comite, caso)["documento"]
        assert documento["resumo"] == "Rogério Valente ameaçou cortar as horas da equipe do almoxarifado."
        assert documento["deliberacao"] == "Procedente, por unanimidade"
        assert documento["identificacao"]["rito"] == "Rápido"

    def test_sem_o_clique_o_agente_nao_roda(self, comite, modelo):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        comite.abrir(COORDENACAO, caso)

        assert modelo.pedidos == []

    def test_a_ata_espera_os_tres_votos(self, comite, modelo):
        caso = comite.caso_no_rito("rapido")
        comite.votar(MEMBRO, caso)

        resposta = comite.gerar(caso)

        assert resposta.status_code == 409
        assert "faltam votos" in resposta.json()["detail"]
        assert modelo.pedidos == []

    def test_so_a_coordenacao_gera_a_ata(self, comite, modelo):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)

        assert comite.gerar(caso, MEMBRO).status_code == 403
        assert modelo.pedidos == []

    def test_nenhum_nome_vai_ao_agente(self, comite, modelo):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        comite.gerar(caso)

        saiu = modelo.tudo_que_saiu()
        for nome in ("Rogério", "Valente", "Ana Coordenadora", "Bruno", "Lia Leitora"):
            assert nome not in saiu
        assert "[PESSOA_" in saiu


# ═══════════════════════════════════════════════════════════════════════════
# No rito completo, o upload na etapa Voto gera a ata, e não existe seletor de
# tipo de transcrição
# ═══════════════════════════════════════════════════════════════════════════


class TestAtaDoRitoCompleto:
    def test_a_transcricao_anexada_na_etapa_voto_entra_na_ata(self, comite, modelo):
        caso = comite.caso_no_rito("completo")
        assert comite.anexar_transcricao(caso).status_code == 200
        comite.tres_votos(caso)

        assert comite.gerar(caso).status_code == 200

        mensagem = modelo.pedidos[0]["messages"][0]["content"]
        assert "<transcricao_da_reuniao>" in mensagem
        assert "a testemunha confirmou a ameaça" in mensagem

    def test_sem_a_transcricao_a_ata_do_completo_nao_sai(self, comite, modelo):
        caso = comite.caso_no_rito("completo")
        comite.tres_votos(caso)

        resposta = comite.gerar(caso)

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "Anexe a transcrição da reunião do Comitê antes de gerar a ata."
        assert modelo.pedidos == []

    def test_a_transcricao_fica_cifrada_no_bucket(self, comite):
        caso = comite.caso_no_rito("completo")
        comite.anexar_transcricao(caso)

        (linha,) = comite.banco.tabelas["conduta_reuniao_transcricoes"]
        guardado = comite.banco.storage.objetos[("conduta-arquivos", linha["storage_path"])]
        assert b"testemunha" not in guardado
        assert cifra.decifrar_arquivo(guardado) == TRANSCRICAO.encode()

    def test_no_rito_rapido_nao_ha_transcricao_da_reuniao(self, comite):
        caso = comite.caso_no_rito("rapido")

        resposta = comite.anexar_transcricao(caso)

        assert resposta.status_code == 409
        assert comite.abrir(COORDENACAO, caso)["reuniao"] is None

    def test_a_transcricao_e_da_etapa_voto_e_da_coordenacao(self, comite):
        caso = comite.caso_no_rito("completo")
        de_membro = comite.cliente(MEMBRO).post(
            f"{BASE}/casos/{caso}/reuniao/transcricao", files={"arquivo": ("r.txt", b"texto", "text/plain")}
        )
        comite.linha_do_caso(caso)["etapa"] = "apuracao"

        assert de_membro.status_code == 403
        assert comite.anexar_transcricao(caso).status_code == 409

    def test_o_botao_da_reuniao_nao_tem_seletor_de_tipo(self):
        esquema = TestClient(_app()).get("/openapi.json").json()
        rota = esquema["paths"]["/api/comite-de-conduta/casos/{caso_id}/reuniao/transcricao"]["post"]
        corpo = rota["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
        assert list(esquema["components"]["schemas"][corpo]["properties"]) == ["arquivo"]
        assert [p["name"] for p in rota.get("parameters", [])] == ["caso_id"]


def _app():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(conduta_ata.router, prefix="/api")
    return app


# ═══════════════════════════════════════════════════════════════════════════
# Os votos da ata são os registrados no aplicativo, e a divergência com a
# transcrição aparece nos "Pontos a confirmar"
# ═══════════════════════════════════════════════════════════════════════════


class TestVotosDaAta:
    def test_a_deliberacao_e_os_votos_sao_os_registrados(self, comite, monkeypatch):
        caso = comite.caso_no_rito("completo")
        comite.anexar_transcricao(caso)
        comite.votar(MEMBRO, caso, resultado="procedente", medida="suspensao", dias_de_suspensao=5)
        comite.votar(LEITOR, caso, resultado="procedente", medida="suspensao", dias_de_suspensao=5)
        comite.votar(COORDENACAO, caso, resultado="improcedente", medida=None, justificativa="Faltou prova.")
        falso = Modelo(_ata_do_agente(deliberacao="Improcedente", votos=[{"membro": "x", "resultado": "Improcedente"}]))
        monkeypatch.setattr(ata, "_cliente_do_agente_da_ata", lambda: falso)

        assert comite.gerar(caso).status_code == 200

        documento = _ata_na_tela(comite, caso)["documento"]
        assert documento["deliberacao"] == "Procedente, por maioria"
        assert documento["medida"] == "Suspensão de 5 dias"
        assert sorted((v["membro"], v["resultado"], v["medida"]) for v in documento["votos"]) == [
            ("Ana Coordenadora", "Improcedente", None),
            ("Bruno Membro", "Procedente", "Suspensão de 5 dias"),
            ("Lia Leitora", "Procedente", "Suspensão de 5 dias"),
        ]
        assert next(v for v in documento["votos"] if v["membro"] == "Ana Coordenadora")["justificativa"] == (
            "Faltou prova."
        )

    def test_o_agente_recebe_os_votos_registrados_e_a_regra_da_divergencia(self, comite, modelo):
        caso = comite.caso_no_rito("completo")
        comite.anexar_transcricao(caso)
        comite.tres_votos(caso)
        comite.gerar(caso)

        pedido = modelo.pedidos[0]
        assert "<votos_registrados_no_aplicativo>" in pedido["messages"][0]["content"]
        assert 'resultado="Procedente"' in pedido["messages"][0]["content"]
        assert "vale o registro" in pedido["system"]
        assert "pontos_a_confirmar" in pedido["system"]

    def test_a_divergencia_aparece_nos_pontos_a_confirmar_como_sugestao(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("completo")
        comite.anexar_transcricao(caso)
        comite.tres_votos(caso)
        comite.gerar(caso)

        pontos = _ata_na_tela(comite, caso)["documento"]["pontos"]
        assert pontos["rotulo"] == "Sugestão"
        assert pontos["itens"] == ["Na transcrição um membro diz improcedente; o voto registrado é procedente."]
        comite.post(COORDENACAO, f"/casos/{caso}/ata/assinatura")
        assert "Na transcrição um membro" not in json.dumps(clicksign.dados[0], ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════
# A ata vai à ClickSign para os três votantes, a assinatura volta para a
# trilha e a cópia do PDF fica no aplicativo
# ═══════════════════════════════════════════════════════════════════════════


class TestAssinaturaDaAta:
    def test_a_ata_vai_aos_tres_votantes_e_a_copia_volta(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        comite.gerar(caso)

        envio = comite.post(COORDENACAO, f"/casos/{caso}/ata/assinatura")

        assert envio.status_code == 200, envio.text
        assert sorted(clicksign.signatarios) == ["coord@hsm.test", "leit@hsm.test", "memb@hsm.test"]
        assert _ata_na_tela(comite, caso)["documento"]["assinatura"]["situacao"] == "enviado"
        (linha,) = [a for a in comite.banco.tabelas["conduta_assinaturas"] if a["tipo"] == "ata_de_deliberacao"]
        assert linha["ata_id"] == comite.banco.tabelas["conduta_atas"][0]["id"]

        assinaturas.processar_evento(comite.banco, linha, "auto_close")

        acoes = [(t["acao"], t["detalhe"]) for t in comite.trilha(caso)]
        assert ("ata_assinada", "ata de deliberação, versão 1, assinada pelos três votantes") in acoes
        guardada = next(a for a in comite.banco.tabelas["conduta_assinaturas"] if a["id"] == linha["id"])
        copia = comite.banco.storage.objetos[("conduta-arquivos", guardada["arquivo_assinado_path"])]
        assert cifra.decifrar_arquivo(copia) == b"%PDF-ata-assinada"
        baixada = comite.cliente(LEITOR).get(f"{BASE}/casos/{caso}/ata/assinada")
        assert baixada.status_code == 200
        assert baixada.content == b"%PDF-ata-assinada"
        assert comite.banco.storage.urls_assinadas == []

    def test_o_retorno_repetido_nao_duplica_a_linha_da_trilha(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        comite.gerar(caso)
        comite.assinar(caso)
        (linha,) = [a for a in comite.banco.tabelas["conduta_assinaturas"] if a["tipo"] == "ata_de_deliberacao"]

        assinaturas.processar_evento(comite.banco, linha, "document_closed")

        assert [t["acao"] for t in comite.trilha(caso)].count("ata_assinada") == 1

    def test_a_ata_assinada_nao_ganha_versao_nova(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        comite.gerar(caso)
        comite.assinar(caso)

        resposta = comite.gerar(caso)

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "A ata já foi assinada pelos três."

    def test_o_pdf_leva_os_votos_registrados(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        comite.gerar(caso)
        comite.post(COORDENACAO, f"/casos/{caso}/ata/assinatura")

        (dados,) = clicksign.dados
        assert dados["modelo"] == "conduta_ata_de_deliberacao.html"
        assert {v["membro"] for v in dados["ata"]["votos"]} == {"Ana Coordenadora", "Bruno Membro", "Lia Leitora"}
        assert sorted(dados["votantes"]) == ["Ana Coordenadora", "Bruno Membro", "Lia Leitora"]


# ═══════════════════════════════════════════════════════════════════════════
# "CONCLUIR REUNIÃO" só libera com os quatro itens da lista
# ═══════════════════════════════════════════════════════════════════════════


def _lista(comite, caso: str) -> dict[str, str]:
    return {i["item"]: i["estado"] for i in comite.abrir(COORDENACAO, caso)["reuniao"]["lista"]}


class TestConcluirReuniao:
    def _pronta_ate_a_ata(self, comite, caso: str) -> None:
        comite.anexar_transcricao(caso)
        comite.tres_votos(caso)
        comite.gerar(caso)
        comite.assinar(caso)

    def test_os_quatro_itens_e_a_conclusao(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("completo")
        self._pronta_ate_a_ata(comite, caso)
        assert _lista(comite, caso) == {
            "transcricao": "feito",
            "ata_assinada": "feito",
            "gravacao_apagada": "pendente",
            "arquivos_apagados": "pendente",
        }

        cedo = comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conclusao")
        assert cedo.status_code == 409
        assert "Apaguei a gravação de áudio" in cedo.json()["detail"]
        for item in ("gravacao_apagada", "arquivos_apagados"):
            assert comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conferencia", {"item": item}).status_code == 200
        assert comite.abrir(COORDENACAO, caso)["reuniao"]["pode_concluir"] is True

        assert comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conclusao").status_code == 200
        assert comite.linha_do_caso(caso)["reuniao_concluida_por"] == COORDENACAO

    def test_sem_a_ata_assinada_a_reuniao_nao_conclui(self, comite, modelo):
        caso = comite.caso_no_rito("completo")
        comite.anexar_transcricao(caso)
        for item in ("gravacao_apagada", "arquivos_apagados"):
            comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conferencia", {"item": item})

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conclusao")

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "Falta marcar: Ata assinada pelos três."

    def test_os_itens_automaticos_nao_se_marcam_a_mao(self, comite):
        caso = comite.caso_no_rito("completo")

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conferencia", {"item": "ata_assinada"})

        assert resposta.status_code == 422

    def test_a_declaracao_e_da_coordenacao_com_quem_e_quando(self, comite):
        caso = comite.caso_no_rito("completo")

        assert (
            comite.post(MEMBRO, f"/casos/{caso}/reuniao/conferencia", {"item": "gravacao_apagada"}).status_code == 403
        )
        comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conferencia", {"item": "gravacao_apagada"})

        item = next(i for i in comite.abrir(COORDENACAO, caso)["reuniao"]["lista"] if i["item"] == "gravacao_apagada")
        assert item["marcado_por"] == "Ana Coordenadora"
        assert item["marcado_em"]


# ═══════════════════════════════════════════════════════════════════════════
# Ao concluir a reunião, a transcrição é eliminada do banco e do bucket, e a
# eliminação fica na trilha
# ═══════════════════════════════════════════════════════════════════════════


class TestEliminacaoDaTranscricao:
    def _concluida(self, comite, caso: str) -> None:
        comite.anexar_transcricao(caso)
        comite.anexar_transcricao(caso, conteudo=b"segunda versao")
        comite.tres_votos(caso)
        comite.gerar(caso)
        comite.assinar(caso)
        for item in ("gravacao_apagada", "arquivos_apagados"):
            comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conferencia", {"item": item})
        assert comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conclusao").status_code == 200

    def test_a_transcricao_sai_do_banco_e_do_bucket(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("completo")
        self._concluida(comite, caso)

        assert comite.banco.tabelas["conduta_reuniao_transcricoes"] == []
        assert not any(c.startswith("reunioes/") for (_b, c) in comite.banco.storage.objetos)
        assert comite.linha_do_caso(caso)["transcricao_eliminada_em"]

    def test_a_eliminacao_fica_na_trilha(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("completo")
        self._concluida(comite, caso)

        acoes = [t["acao"] for t in comite.trilha(caso)]
        assert acoes.count("eliminou_transcricao") == 1
        assert acoes.index("concluiu_reuniao") < acoes.index("eliminou_transcricao")
        assert _lista(comite, caso)["transcricao"] == "feito"

    def test_o_que_o_bucket_nao_apagou_sai_na_proxima_abertura(self, comite, modelo, clicksign, monkeypatch):
        caso = comite.caso_no_rito("completo")
        from app.services import storage

        apagar = storage.delete_file
        monkeypatch.setattr(storage, "delete_file", lambda *a: False)
        self._concluida(comite, caso)
        assert len(comite.banco.tabelas["conduta_reuniao_transcricoes"]) == 2
        monkeypatch.setattr(storage, "delete_file", apagar)

        comite.abrir(COORDENACAO, caso)

        assert comite.banco.tabelas["conduta_reuniao_transcricoes"] == []
        assert [t["acao"] for t in comite.trilha(caso)].count("eliminou_transcricao") == 1


# ═══════════════════════════════════════════════════════════════════════════
# Não existe lugar para anexar o áudio da reunião
# ═══════════════════════════════════════════════════════════════════════════


class TestSemAudioDaReuniao:
    @pytest.mark.parametrize("nome", ["reuniao.mp3", "reuniao.m4a", "reuniao.ogg", "reuniao.wav"])
    def test_o_audio_e_recusado_no_botao_da_transcricao(self, comite, nome):
        caso = comite.caso_no_rito("completo")

        resposta = comite.anexar_transcricao(caso, nome=nome, conteudo=b"ID3 audio")

        assert resposta.status_code == 422
        assert "O áudio da reunião não é anexado." in resposta.json()["detail"]
        assert comite.banco.tabelas.get("conduta_reuniao_transcricoes", []) == []

    def test_nenhuma_rota_da_reuniao_recebe_audio(self):
        esquema = TestClient(_app()).get("/openapi.json").json()
        caminhos = [c for c in esquema["paths"] if "/reuniao" in c]
        assert caminhos
        assert not any("audio" in c for c in caminhos)
        assert not any(ct.startswith("audio/") for ct in ata.CONTENT_TYPES_DA_TRANSCRICAO.values())


# ═══════════════════════════════════════════════════════════════════════════
# A trava e a votação esperam a ata (o 7º item, "Votos registrados e ata
# assinada", ficou desta fatia na #1833)
# ═══════════════════════════════════════════════════════════════════════════


class TestTravaEsperaAAta:
    def test_o_item_dos_votos_espera_a_ata_assinada(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)

        cedo = comite.confirmar(MEMBRO, caso, "votos")
        assert cedo.status_code == 409
        assert "ata assinada" in cedo.json()["detail"]
        comite.gerar(caso)
        comite.assinar(caso)
        assert comite.confirmar(MEMBRO, caso, "votos").status_code == 200

    def test_o_rotulo_do_item_diz_a_ata(self, comite):
        caso = comite.caso_no_rito("rapido")
        itens = {i["item"]: i["rotulo"] for i in comite.abrir(MEMBRO, caso)["trava"]["itens"]}
        assert itens["votos"] == "Votos registrados e ata assinada"

    def test_sem_a_ata_a_votacao_nao_conclui(self, comite):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso, resultado="improcedente")

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "Falta a ata assinada pelos três votantes."

    def test_no_completo_a_votacao_espera_a_reuniao_concluida(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("completo")
        comite.anexar_transcricao(caso)
        comite.tres_votos(caso, resultado="improcedente")
        comite.gerar(caso)
        comite.assinar(caso)

        cedo = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")
        assert cedo.status_code == 409
        assert cedo.json()["detail"] == "Falta concluir a reunião do Comitê."
        for item in ("gravacao_apagada", "arquivos_apagados"):
            comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conferencia", {"item": item})
        comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conclusao")
        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 200

    def test_o_procedente_conclui_com_a_ata_e_a_trava(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        comite.gerar(caso)
        comite.assinar(caso)
        assert comite.anexar_ciencia(COORDENACAO, caso).status_code == 200
        for item in ITENS_DA_TRAVA:
            assert comite.confirmar(COORDENACAO, caso, item).status_code == 200

        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 200
        assert comite.linha_do_caso(caso)["resultado"] == "procedente"

    def test_quem_nao_coordena_nao_gera(self, comite):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        tela = comite.abrir(MEMBRO, caso)["ata"]
        assert tela["pode_gerar"] is False
        assert tela["bloqueio_da_geracao"] == "Só a coordenação gera a ata."


# ═══════════════════════════════════════════════════════════════════════════
# A ata fica presa à rodada e aos votantes de que saiu: impedimento ou Citado
# depois dos votos tiram a ata de valer, e a ata não vaza o voto oculto
# ═══════════════════════════════════════════════════════════════════════════

JUSTIFICATIVAS = {
    MEMBRO: "O membro viu a prova da ameaça.",
    LEITOR: "A leitora ouviu as duas testemunhas.",
    COORDENACAO: "Faltou prova da ameaça.",
}


def _ata_procedente_por_maioria(comite, caso: str) -> None:
    """Procedente por maioria (membro e leitora), a coordenação vencida."""
    for pid in (MEMBRO, LEITOR):
        comite.votar(pid, caso, resultado="procedente", medida="advertencia_escrita", justificativa=JUSTIFICATIVAS[pid])
    comite.votar(COORDENACAO, caso, resultado="improcedente", medida=None, justificativa=JUSTIFICATIVAS[COORDENACAO])
    assert comite.gerar(caso).status_code == 200


def _impedir(comite, caso: str, pid: str = LEITOR) -> None:
    resposta = comite.post(pid, f"/casos/{caso}/impedimento", {"motivo": "parentesco"})
    assert resposta.status_code == 200, resposta.text


def _envios_da_ata(comite, caso: str) -> list[dict]:
    return [
        a
        for a in comite.banco.tabelas.get("conduta_assinaturas", [])
        if a["caso_id"] == caso and a["tipo"] == "ata_de_deliberacao"
    ]


class TestAtaPresaAosVotos:
    def test_o_impedimento_depois_da_ata_assinada_pede_ata_nova(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        _ata_procedente_por_maioria(comite, caso)
        comite.assinar(caso)
        _impedir(comite, caso)
        comite.votar(SUPLENTE, caso, resultado="improcedente", medida=None, justificativa="Voto do suplente.")

        cedo = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")
        assert cedo.status_code == 409
        assert cedo.json()["detail"] == "Falta a ata assinada pelos três votantes."
        assert comite.linha_do_caso(caso).get("resultado") is None

        assert comite.gerar(caso).status_code == 200
        documento = _ata_na_tela(comite, caso)["documento"]
        assert documento["versao"] == 2
        assert documento["deliberacao"] == "Improcedente, por maioria"
        assert {v["membro"] for v in documento["votos"]} == {"Ana Coordenadora", "Bruno Membro", "Sérgio Suplente"}
        assert documento["identificacao"]["impedimentos"] == ["Lia Leitora"]
        comite.assinar(caso)
        assert sorted(clicksign.signatarios[-3:]) == ["coord@hsm.test", "memb@hsm.test", "supl@hsm.test"]
        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 200
        assert comite.linha_do_caso(caso)["resultado"] == "improcedente"

    def test_o_citado_depois_da_ata_assinada_tira_a_ata_e_o_item_dos_votos(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        _ata_procedente_por_maioria(comite, caso)
        comite.assinar(caso)
        assert comite.confirmar(MEMBRO, caso, "votos").status_code == 200
        comite.banco.tabelas.setdefault("conduta_citados", []).append(
            {"id": "cit-ata", "caso_id": caso, "participante_id": LEITOR}
        )

        tela = comite.abrir(MEMBRO, caso)
        assert tela["ata"]["documento"] is None
        votos = next(i for i in tela["trava"]["itens"] if i["item"] == "votos")
        assert votos["confirmado"] is False
        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 409

    def test_a_ata_de_votos_que_mudaram_nao_vai_a_assinatura(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        _ata_procedente_por_maioria(comite, caso)
        _impedir(comite, caso)

        aberta = comite.post(COORDENACAO, f"/casos/{caso}/ata/assinatura")
        assert aberta.status_code == 409
        assert aberta.json()["detail"] == "A rodada de voto está aberta: a ata espera os três votos."
        comite.votar(SUPLENTE, caso, resultado="improcedente", medida=None, justificativa="Voto do suplente.")
        velha = comite.post(COORDENACAO, f"/casos/{caso}/ata/assinatura")
        assert velha.status_code == 409
        assert velha.json()["detail"] == "Os votos mudaram depois da ata. Gere a ata de novo."
        assert clicksign.signatarios == []
        assert _envios_da_ata(comite, caso) == []

    @pytest.mark.parametrize("pid", [SUPLENTE, COORDENACAO, MEMBRO])
    def test_a_rodada_reaberta_nao_mostra_a_ata_com_os_votos(self, comite, modelo, clicksign, pid):
        caso = comite.caso_no_rito("rapido")
        _ata_procedente_por_maioria(comite, caso)
        comite.assinar(caso)
        _impedir(comite, caso)

        tela = comite.abrir(pid, caso)

        assert tela["ata"]["documento"] is None
        saida = json.dumps(tela, ensure_ascii=False)
        assert [j for quem, j in JUSTIFICATIVAS.items() if quem != pid and j in saida] == []
        assert comite.cliente(pid).get(f"{BASE}/casos/{caso}/ata/assinada").status_code == 404

    def test_a_ata_concluida_segue_na_tela(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso, resultado="improcedente")
        comite.gerar(caso)
        comite.assinar(caso)
        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 200

        assert _ata_na_tela(comite, caso, LEITOR)["documento"]["deliberacao"] == "Improcedente, por unanimidade"

    def test_a_ata_na_clicksign_nao_e_gerada_de_novo(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        comite.tres_votos(caso)
        comite.gerar(caso)
        assert comite.post(COORDENACAO, f"/casos/{caso}/ata/assinatura").status_code == 200

        tela = _ata_na_tela(comite, caso)
        resposta = comite.gerar(caso)

        assert tela["pode_gerar"] is False
        assert resposta.status_code == 409
        assert resposta.json()["detail"] == (
            "A ata está na ClickSign, à espera da assinatura dos três: ela não é gerada de novo."
        )
        assert len(modelo.pedidos) == 1
        assert len(comite.banco.tabelas["conduta_atas"]) == 1

    def test_a_ata_de_votos_que_mudaram_sai_da_clicksign_com_a_versao_nova(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("rapido")
        _ata_procedente_por_maioria(comite, caso)
        assert comite.post(COORDENACAO, f"/casos/{caso}/ata/assinatura").status_code == 200
        _impedir(comite, caso)
        comite.votar(SUPLENTE, caso, resultado="improcedente", medida=None, justificativa="Voto do suplente.")

        assert comite.gerar(caso).status_code == 200

        (velho,) = _envios_da_ata(comite, caso)
        assert velho["situacao"] == "cancelado"
        assert clicksign.cancelados == ["env-ata"]
        assinaturas.processar_evento(comite.banco, velho, "auto_close")
        assert "ata_assinada" not in [t["acao"] for t in comite.trilha(caso)]

    def test_no_completo_com_a_reuniao_concluida_a_ata_nova_sai_sem_a_transcricao(self, comite, modelo, clicksign):
        caso = comite.caso_no_rito("completo")
        comite.anexar_transcricao(caso)
        _ata_procedente_por_maioria(comite, caso)
        comite.assinar(caso)
        for item in ("gravacao_apagada", "arquivos_apagados"):
            comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conferencia", {"item": item})
        assert comite.post(COORDENACAO, f"/casos/{caso}/reuniao/conclusao").status_code == 200
        _impedir(comite, caso)
        comite.votar(SUPLENTE, caso, resultado="improcedente", medida=None, justificativa="Voto do suplente.")

        resposta = comite.gerar(caso)

        assert resposta.status_code == 200, resposta.text
        mensagem = modelo.pedidos[-1]["messages"][0]["content"]
        assert "<transcricao_da_reuniao>" not in mensagem
        assert "a transcrição, eliminada" in mensagem
        comite.assinar(caso)
        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 200


class TestAgenteDaAtaForaDoLoop:
    def test_a_rota_da_ata_chama_o_agente_pelo_executor_da_ia(self):
        arvore = ast.parse(Path(conduta_ata.__file__).read_text(encoding="utf-8"))
        chamadas = [
            ast.unparse(no)
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and "gerar_ata_de_deliberacao" in ast.unparse(no)
        ]
        assert chamadas
        assert all("chamar_ia_fora_do_loop" in c for c in chamadas)


# ═══════════════════════════════════════════════════════════════════════════
# O texto do Produto Canal de Conduta no kit de conhecimento diz o
# comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    @pytest.mark.parametrize(
        "frase",
        [
            "## A ata de deliberação e a reunião do Comitê",
            "GERAR ATA",
            "ANEXAR TRANSCRIÇÃO DA REUNIÃO DO COMITÊ",
            "vale o voto registrado",
            "Pontos a confirmar",
            "CONCLUIR REUNIÃO",
            "a transcrição é eliminada",
            "O áudio da reunião não é anexado",
            "Votos registrados e ata assinada",
        ],
    )
    def test_o_kit_diz_o_comportamento_novo(self, frase):
        assert frase in (CONHECIMENTO_DIR / "canal-de-conduta.md").read_text(encoding="utf-8")
