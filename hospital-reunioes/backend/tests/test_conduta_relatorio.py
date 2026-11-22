"""O relatório de apuração do Canal de Conduta e o envio para voto (issue
#1832; especificação, seções 6.3, 6.4, 8 e 11; ADR 0097, decisão 7).

Cada classe é um critério de aceite da issue. O banco e o Storage são os
dublês de `conduta_apoio`, a cifra é de verdade, e o modelo é um dublê que
guarda o que recebeu e devolve o texto pedido.
"""

from __future__ import annotations

import base64
import io
import os
import secrets
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pdfplumber
import pytest
from anthropic_apoio import resposta_de_texto
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.routers import conduta_comite, conduta_depoimentos  # noqa: E402
from app.services import clicksign_service  # noqa: E402
from app.services.conduta import assinaturas, casos, cifra, relatorio  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402
from app.services.seguranca_do_paciente.termo import gerar_pdf_do_termo  # noqa: E402

BASE = "/api/comite-de-conduta"
HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}
COORDENACAO, MEMBRO, APURADOR, APURADORA, DE_FORA = "COORD", "MEMB", "APUR1", "APUR2", "FORA"
NOMES = {
    COORDENACAO: "Ana Coordenadora",
    MEMBRO: "Bruno Membro",
    APURADOR: "Caio Apurador",
    APURADORA: "Dora Apuradora",
    DE_FORA: "Carla de Fora",
}
ACUSADO = {"nome": "Rogério Valente", "cargo": "Supervisor do almoxarifado", "papel": "acusado"}
TESTEMUNHA = {"nome": "Marlene Quintanilha", "cargo": "Auxiliar de almoxarifado", "papel": "testemunha"}
RELATO = (
    "O supervisor Rogério Valente grita com a equipe do almoxarifado. "
    "No dia 3 de outubro, a Marlene Quintanilha viu ele ameaçar cortar as horas de todos."
)
TRANSCRICAO = (
    "Entrevistadora: o senhor confirma o que aconteceu no dia 3? "
    "Rogério: confirmo que levantei a voz, mas não ameacei ninguém. A Marlene estava lá."
)
PONTOS = "Marlene Quintanilha disse que ouviu Rogério Valente falar em cortar as horas da equipe."

RELATORIO_DO_AGENTE = (
    "Fatos: no dia 3 de outubro, [PESSOA_1] teria ameaçado cortar as horas da equipe.\n"
    "Provas: o depoimento de [PESSOA_2], testemunha.\n"
    "Versão do acusado: [PESSOA_1] confirma que levantou a voz e nega a ameaça.\n"
    "Regra do Código: item sobre respeito nas relações de trabalho."
)
UMA_PAGINA = relatorio.TAMANHO_DA_PAGINA


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")


class Modelo:
    """O agente de mentira: guarda cada mensagem que recebeu e devolve, na
    ordem, os textos dados (o último se repete)."""

    def __init__(self, *textos: str):
        self.textos = list(textos) or [RELATORIO_DO_AGENTE]
        self.pedidos: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.pedidos.append(kwargs)
        texto = self.textos.pop(0) if len(self.textos) > 1 else self.textos[0]
        return resposta_de_texto(texto)

    def tudo_que_saiu(self) -> str:
        partes = []
        for pedido in self.pedidos:
            sistema = pedido.get("system")
            partes.append(sistema if isinstance(sistema, str) else str(sistema))
            partes += [str(m["content"]) for m in pedido["messages"]]
        return "\n".join(partes)


@pytest.fixture
def modelo(monkeypatch) -> Modelo:
    falso = Modelo()
    monkeypatch.setattr(relatorio, "_cliente_do_agente_da_apuracao", lambda: falso)
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
    """Coordenação e membro do Comitê, dois apuradores convidados e alguém de
    fora, e casos já na etapa Apuração."""

    def __init__(self):
        self.banco = Banco(
            {
                "participantes": [_pessoa(p) for p in NOMES],
                "colegiados": [dict(COMITE)],
                "participacoes": [_participacao(COORDENACAO, "coordenacao"), _participacao(MEMBRO, "membro")],
            }
        )

    def caso(self, rito: str = "rapido") -> str:
        novo = casos.registrar_caso(self.banco, relato=RELATO, categoria=None)
        linha = next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == novo["id"])
        linha.update(
            {
                "recebido_em": datetime.now().astimezone().isoformat(),
                "etapa": "apuracao",
                "rito": rito,
                "escopo": "dentro",
            }
        )
        if rito == "completo":
            for pid in (APURADOR, APURADORA):
                self.banco.tabelas.setdefault("conduta_atribuicoes", []).append(
                    {
                        "id": f"atr-{pid}-{novo['id']}",
                        "caso_id": novo["id"],
                        "participante_id": pid,
                        "motivo": "apurador",
                        "termo_assinado_em": "2026-10-02T12:00:00+00:00",
                        "revogada_em": None,
                        "impedido_em": None,
                    }
                )
        return novo["id"]

    def cliente(self, pid: str) -> TestClient:
        app = FastAPI()
        app.include_router(conduta_comite.router, prefix="/api")
        app.include_router(conduta_depoimentos.router, prefix="/api")
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

    def depoimento(self, caso_id: str, pessoa: dict, *, concluido: bool = False, pid: str = MEMBRO) -> str:
        resposta = self.post(pid, f"/casos/{caso_id}/depoimentos", pessoa)
        assert resposta.status_code == 200, resposta.text
        dep = resposta.json()["depoimento"]["id"]
        if concluido:
            linha = next(d for d in self.banco.tabelas["conduta_depoimentos"] if d["id"] == dep)
            linha.update({"concluido_em": "2026-11-20T12:00:00+00:00", "concluido_por": pid})
        return dep

    def transcricao(self, caso_id: str, dep: str, texto: str, pid: str = MEMBRO):
        resposta = self.cliente(pid).post(
            f"{BASE}/casos/{caso_id}/depoimentos/{dep}/transcricao",
            files={"arquivo": ("transcricao.txt", texto.encode(), "text/plain")},
        )
        assert resposta.status_code == 200, resposta.text

    def gerar(self, pid: str, caso_id: str, tipo: str = "relatorio"):
        return self.post(pid, f"/casos/{caso_id}/{tipo}")

    def trilha(self, caso_id: str) -> list[dict]:
        return [linha for linha in self.banco.tabelas["conduta_trilha"] if linha["caso_id"] == caso_id]


@pytest.fixture
def comite() -> Comite:
    return Comite()


# ═══════════════════════════════════════════════════════════════════════════
# O relatório é gerado depois de um clique e cabe em uma página
# ═══════════════════════════════════════════════════════════════════════════


class TestRelatorioDeUmClique:
    def test_um_clique_gera_o_relatorio_com_os_nomes_de_volta(self, comite, modelo):
        caso = comite.caso()
        comite.depoimento(caso, ACUSADO)
        comite.depoimento(caso, TESTEMUNHA)

        resposta = comite.gerar(MEMBRO, caso)

        assert resposta.status_code == 200, resposta.text
        assert len(modelo.pedidos) == 1
        texto = comite.abrir(MEMBRO, caso)["relatorio"]["texto"]
        assert "Rogério Valente teria ameaçado cortar as horas" in texto
        assert "o depoimento de Marlene Quintanilha, testemunha" in texto
        assert "gerou_relatorio" in [linha["acao"] for linha in comite.trilha(caso)]

    def test_o_relatorio_cabe_em_uma_pagina(self, comite, modelo):
        """O agente que passa de uma página é chamado de novo, pedindo para
        encurtar; o texto guardado é o que cabe."""
        modelo.textos = ["Fatos: " + "muito longo. " * UMA_PAGINA, RELATORIO_DO_AGENTE]
        caso = comite.caso()

        assert comite.gerar(MEMBRO, caso).status_code == 200

        assert len(modelo.pedidos) == 2
        assert "uma página" in str(modelo.pedidos[1]["messages"][-1]["content"])
        texto = comite.abrir(MEMBRO, caso)["relatorio"]["texto"]
        assert len(texto) <= UMA_PAGINA

    def test_o_agente_que_insiste_em_mais_de_uma_pagina_nao_grava_nada(self, comite, modelo):
        modelo.textos = ["Fatos: " + "muito longo. " * UMA_PAGINA]
        caso = comite.caso()

        resposta = comite.gerar(MEMBRO, caso)

        assert resposta.status_code == 502
        assert "uma página" in resposta.json()["detail"]
        assert comite.abrir(MEMBRO, caso)["relatorio"] is None

    def test_quem_nao_apura_nao_gera(self, comite, modelo):
        caso = comite.caso(rito="completo")

        resposta = comite.gerar(MEMBRO, caso)

        assert resposta.status_code == 403
        assert "apuradores" in resposta.json()["detail"]
        assert modelo.pedidos == []

    def test_a_cronologia_dos_fatos_tambem_sai_de_um_clique(self, comite, modelo):
        modelo.textos = ["03/10: [PESSOA_1] ameaça cortar as horas da equipe."]
        caso = comite.caso()
        comite.depoimento(caso, ACUSADO)

        assert comite.gerar(MEMBRO, caso, "cronologia").status_code == 200

        tela = comite.abrir(MEMBRO, caso)
        assert tela["cronologia"]["texto"] == "03/10: Rogério Valente ameaça cortar as horas da equipe."
        assert tela["relatorio"] is None


# ═══════════════════════════════════════════════════════════════════════════
# Quem apurou edita o relatório, e cada edição vira versão nova
# ═══════════════════════════════════════════════════════════════════════════


class TestEdicaoViraVersao:
    def test_cada_edicao_vira_uma_versao_nova_e_a_anterior_fica(self, comite, modelo):
        caso = comite.caso()
        comite.depoimento(caso, ACUSADO)
        comite.gerar(MEMBRO, caso)

        primeira = comite.post(COORDENACAO, f"/casos/{caso}/relatorio/versoes", {"texto": "Fatos revistos."})
        segunda = comite.post(MEMBRO, f"/casos/{caso}/relatorio/versoes", {"texto": "Fatos revistos de novo."})

        assert (primeira.status_code, segunda.status_code) == (200, 200)
        tela = comite.abrir(MEMBRO, caso)["relatorio"]
        assert tela["texto"] == "Fatos revistos de novo."
        assert [(v["versao"], v["origem"], v["autor"]) for v in tela["versoes"]] == [
            (3, "edicao", "Bruno Membro"),
            (2, "edicao", "Ana Coordenadora"),
            (1, "agente", "Bruno Membro"),
        ]
        assert tela["versoes"][-1]["texto"].startswith("Fatos: no dia 3 de outubro, Rogério Valente")
        assert [linha["acao"] for linha in comite.trilha(caso)].count("editou_relatorio") == 2

    def test_a_edicao_tambem_cabe_em_uma_pagina(self, comite, modelo):
        caso = comite.caso()
        comite.gerar(MEMBRO, caso)

        resposta = comite.post(MEMBRO, f"/casos/{caso}/relatorio/versoes", {"texto": "x" * (UMA_PAGINA + 1)})

        assert resposta.status_code == 422
        assert len(comite.abrir(MEMBRO, caso)["relatorio"]["versoes"]) == 1

    def test_o_texto_guardado_fica_cifrado(self, comite, modelo):
        caso = comite.caso()
        comite.depoimento(caso, ACUSADO)
        comite.gerar(MEMBRO, caso)

        (linha,) = comite.banco.tabelas["conduta_relatorios"]
        assert linha["texto_cifrado"].startswith("v1:")
        assert "Rogério" not in linha["texto_cifrado"]
        assert cifra.decifrar_texto(linha["texto_cifrado"]).startswith("Fatos: no dia 3 de outubro, Rogério")


# ═══════════════════════════════════════════════════════════════════════════
# No rito Completo, o relatório vai à ClickSign para os apuradores, e a cópia
# assinada volta para a trilha
# ═══════════════════════════════════════════════════════════════════════════


class _ClickSign:
    def __init__(self, monkeypatch):
        self.signatarios: list[dict] = []
        self.pdfs: list[bytes] = []
        self.cancelados: list[str] = []
        monkeypatch.setattr(clicksign_service, "create_envelope", lambda nome: "env-1")
        monkeypatch.setattr(clicksign_service, "add_document", lambda env, pdf, nome: self.pdfs.append(pdf) or "doc-1")
        monkeypatch.setattr(
            clicksign_service, "add_signer", lambda env, nome, email: self.signatarios.append(email) or f"sig-{email}"
        )
        monkeypatch.setattr(clicksign_service, "create_qualification_requirement", lambda *a: True)
        monkeypatch.setattr(clicksign_service, "create_auth_requirement", lambda *a: True)
        monkeypatch.setattr(clicksign_service, "activate_envelope", lambda env: True)
        monkeypatch.setattr(clicksign_service, "notify_signers", lambda env: True)
        monkeypatch.setattr(clicksign_service, "cancel_envelope", lambda env: self.cancelados.append(env) or True)
        monkeypatch.setattr(clicksign_service, "get_signed_document", lambda env: b"%PDF-assinado")
        monkeypatch.setattr(
            assinaturas, "gerar_pdf_do_termo", lambda dados: b"%PDF-" + dados["relatorio"]["texto"].encode()
        )


@pytest.fixture
def clicksign(monkeypatch) -> _ClickSign:
    return _ClickSign(monkeypatch)


class TestAssinaturaDosApuradores:
    def test_o_relatorio_vai_aos_dois_apuradores_e_a_copia_assinada_volta_para_a_trilha(
        self, comite, modelo, clicksign
    ):
        caso = comite.caso(rito="completo")
        comite.depoimento(caso, ACUSADO, pid=APURADOR)
        comite.gerar(APURADOR, caso)

        envio = comite.post(APURADOR, f"/casos/{caso}/relatorio/assinatura")

        assert envio.status_code == 200, envio.text
        assert clicksign.signatarios == ["apur1@hsm.test", "apur2@hsm.test"]
        assert "Rogério Valente".encode() in clicksign.pdfs[0]
        tela = comite.abrir(APURADOR, caso)["relatorio"]
        assert tela["assinatura"]["situacao"] == "enviado"

        (linha,) = [a for a in comite.banco.tabelas["conduta_assinaturas"] if a["tipo"] == "relatorio_de_apuracao"]
        assinaturas.processar_evento(comite.banco, linha, "auto_close")

        acoes = [(t["acao"], t["detalhe"]) for t in comite.trilha(caso)]
        assert ("relatorio_assinado", "relatório de apuração, versão 1, assinado pelos apuradores") in acoes
        guardada = next(a for a in comite.banco.tabelas["conduta_assinaturas"] if a["id"] == linha["id"])
        copia = comite.banco.storage.objetos[("conduta-arquivos", guardada["arquivo_assinado_path"])]
        assert cifra.decifrar_arquivo(copia) == b"%PDF-assinado"
        assert comite.abrir(APURADOR, caso)["relatorio"]["assinatura"]["situacao"] == "assinado"

        baixado = comite.cliente(APURADOR).get(f"{BASE}/casos/{caso}/relatorio/assinado")
        assert baixado.status_code == 200
        assert baixado.content == b"%PDF-assinado"

    def test_o_retorno_repetido_nao_duplica_a_linha_da_trilha(self, comite, modelo, clicksign):
        caso = comite.caso(rito="completo")
        comite.gerar(APURADOR, caso)
        comite.post(APURADOR, f"/casos/{caso}/relatorio/assinatura")
        (linha,) = [a for a in comite.banco.tabelas["conduta_assinaturas"] if a["tipo"] == "relatorio_de_apuracao"]

        assinaturas.processar_evento(comite.banco, linha, "auto_close")
        assinada = next(a for a in comite.banco.tabelas["conduta_assinaturas"] if a["id"] == linha["id"])
        assinaturas.processar_evento(comite.banco, assinada, "document_closed")

        assert [t["acao"] for t in comite.trilha(caso)].count("relatorio_assinado") == 1

    def test_o_pdf_no_teto_com_tres_apuradores_sai_em_uma_pagina(self, comite, modelo, clicksign, monkeypatch):
        """O PDF de verdade (WeasyPrint, fonte e logo do app), com o texto no
        teto, em 12 parágrafos, e o bloco de assinatura de três apuradores."""
        monkeypatch.setattr(assinaturas, "gerar_pdf_do_termo", gerar_pdf_do_termo)
        caso = comite.caso(rito="completo")
        comite.banco.tabelas["conduta_atribuicoes"].append(
            {
                "id": f"atr-{DE_FORA}-{caso}",
                "caso_id": caso,
                "participante_id": DE_FORA,
                "motivo": "apurador",
                "termo_assinado_em": "2026-10-02T12:00:00+00:00",
                "revogada_em": None,
                "impedido_em": None,
            }
        )
        frase = "A testemunha relatou que o supervisor levantou a voz com a equipe e falou em cortar as horas. "
        corpo = (frase * (UMA_PAGINA // len(frase) + 1))[: UMA_PAGINA - 11]
        passo = len(corpo) // 12
        texto = "\n".join(corpo[i * passo : (i + 1) * passo] for i in range(12)).ljust(UMA_PAGINA, ".")
        assert len(texto) == UMA_PAGINA
        comite.post(APURADOR, f"/casos/{caso}/relatorio/versoes", {"texto": texto})

        assert comite.post(APURADOR, f"/casos/{caso}/relatorio/assinatura").status_code == 200

        assert len(clicksign.signatarios) == 3
        with pdfplumber.open(io.BytesIO(clicksign.pdfs[0])) as pdf:
            assert len(pdf.pages) == 1, "o relatório no teto passou de uma página"

    def test_com_duas_versoes_assinadas_abre_a_copia_da_ultima(self, comite, modelo, clicksign, monkeypatch):
        caso = comite.caso(rito="completo")
        comite.gerar(APURADOR, caso)

        def assinar(copia: bytes) -> None:
            monkeypatch.setattr(clicksign_service, "get_signed_document", lambda env: copia)
            comite.post(APURADOR, f"/casos/{caso}/relatorio/assinatura")
            linha = next(
                a
                for a in reversed(comite.banco.tabelas["conduta_assinaturas"])
                if a["tipo"] == "relatorio_de_apuracao" and a["situacao"] == "enviado"
            )
            assinaturas.processar_evento(comite.banco, linha, "auto_close")

        def baixar():
            return comite.cliente(APURADOR).get(f"{BASE}/casos/{caso}/relatorio/assinado")

        assinar(b"%PDF-versao-1")
        comite.post(APURADORA, f"/casos/{caso}/relatorio/versoes", {"texto": "Fatos revistos."})

        assert baixar().status_code == 404, "a versão 2 ainda não foi assinada"

        assinar(b"%PDF-versao-2")

        assert baixar().content == b"%PDF-versao-2"

    def test_no_rito_rapido_o_relatorio_nao_vai_a_clicksign(self, comite, modelo, clicksign):
        caso = comite.caso()
        comite.gerar(MEMBRO, caso)

        resposta = comite.post(MEMBRO, f"/casos/{caso}/relatorio/assinatura")

        assert resposta.status_code == 409
        assert clicksign.signatarios == []

    def test_a_versao_nova_pede_assinatura_de_novo(self, comite, modelo, clicksign):
        caso = comite.caso(rito="completo")
        comite.gerar(APURADOR, caso)
        comite.post(APURADOR, f"/casos/{caso}/relatorio/assinatura")
        (linha,) = [a for a in comite.banco.tabelas["conduta_assinaturas"] if a["tipo"] == "relatorio_de_apuracao"]
        assinaturas.processar_evento(comite.banco, linha, "auto_close")

        comite.post(APURADORA, f"/casos/{caso}/relatorio/versoes", {"texto": "Fatos revistos."})

        tela = comite.abrir(COORDENACAO, caso)
        assert tela["relatorio"]["assinatura"] is None
        assert tela["o_que_fazer_agora"]["bloqueio"] == "Falta a assinatura dos apuradores no relatório."


# ═══════════════════════════════════════════════════════════════════════════
# "ENVIAR PARA VOTO" fica bloqueado, com o motivo, enquanto houver depoimento
# em aberto
# ═══════════════════════════════════════════════════════════════════════════


class TestEnvioParaVoto:
    def test_com_depoimento_em_aberto_o_botao_fica_bloqueado_com_o_motivo(self, comite, modelo):
        caso = comite.caso()
        comite.depoimento(caso, ACUSADO, concluido=True)
        comite.depoimento(caso, TESTEMUNHA)
        comite.gerar(MEMBRO, caso)

        caixa = comite.abrir(COORDENACAO, caso)["o_que_fazer_agora"]
        resposta = comite.post(COORDENACAO, f"/casos/{caso}/envio-para-voto")

        assert (caixa["botao"], caixa["acao"]) == ("ENVIAR PARA VOTO", "enviar_para_voto")
        assert caixa["bloqueio"] == "A Apuração só avança com todos os depoimentos concluídos. Falta 1."
        assert resposta.status_code == 409
        assert resposta.json()["detail"] == caixa["bloqueio"]
        assert comite.abrir(COORDENACAO, caso)["etapa"] == "apuracao"

    def test_com_todos_concluidos_e_o_relatorio_o_caso_vai_para_voto(self, comite, modelo):
        caso = comite.caso()
        comite.depoimento(caso, ACUSADO, concluido=True)
        comite.gerar(MEMBRO, caso)
        assert comite.abrir(COORDENACAO, caso)["o_que_fazer_agora"]["bloqueio"] is None

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/envio-para-voto")

        assert resposta.status_code == 200, resposta.text
        tela = comite.abrir(COORDENACAO, caso)
        assert tela["etapa"] == "voto"
        assert [e["nome"] for e in tela["trilho"] if e["estado"] == "atual"] == ["Voto"]
        assert "enviou_para_voto" in [linha["acao"] for linha in comite.trilha(caso)]

    def test_sem_relatorio_o_botao_diz_que_falta_o_relatorio(self, comite):
        caso = comite.caso()
        comite.depoimento(caso, ACUSADO, concluido=True)

        caixa = comite.abrir(COORDENACAO, caso)["o_que_fazer_agora"]

        assert caixa["botao"] == "ENVIAR PARA VOTO"
        assert caixa["bloqueio"] == "Gere o relatório antes de enviar para voto."
        assert comite.post(COORDENACAO, f"/casos/{caso}/envio-para-voto").status_code == 409

    def test_no_rito_completo_falta_a_assinatura_dos_apuradores(self, comite, modelo):
        caso = comite.caso(rito="completo")
        comite.depoimento(caso, ACUSADO, concluido=True, pid=APURADOR)
        comite.gerar(APURADOR, caso)

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/envio-para-voto")

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "Falta a assinatura dos apuradores no relatório."


# ═══════════════════════════════════════════════════════════════════════════
# O texto enviado ao modelo não leva nomes
# ═══════════════════════════════════════════════════════════════════════════


class TestSemNomesNoModelo:
    def test_nenhum_nome_do_caso_sai_para_o_modelo(self, comite, modelo):
        caso = comite.caso()
        acusado = comite.depoimento(caso, ACUSADO)
        comite.transcricao(caso, acusado, TRANSCRICAO)
        testemunha = comite.depoimento(caso, TESTEMUNHA)
        comite.post(
            MEMBRO, f"/casos/{caso}/depoimentos/{testemunha}/sem-gravacao", {"motivo": "Recusou", "pontos": PONTOS}
        )

        assert comite.gerar(MEMBRO, caso).status_code == 200

        saiu = modelo.tudo_que_saiu()
        for nome in ("Rogério", "Valente", "Marlene", "Quintanilha", "Bruno Membro", "Ana Coordenadora"):
            assert nome not in saiu, f"{nome} foi para o modelo"
        assert "[PESSOA_1]" in saiu and "[PESSOA_2]" in saiu
        assert "levantei a voz" in saiu, "a transcrição do depoimento não chegou ao modelo"
        assert "cortar as horas da equipe" in saiu, "os pontos do depoimento sem gravação não chegaram ao modelo"

    def test_o_nome_escrito_sem_acento_tambem_nao_sai_para_o_modelo(self, comite, modelo):
        caso = comite.caso()
        acusado = comite.depoimento(caso, ACUSADO)
        comite.transcricao(caso, acusado, "Rogerio confirmou que levantou a voz. Depois o rogerio gritou.")

        assert comite.gerar(MEMBRO, caso).status_code == 200

        saiu = modelo.tudo_que_saiu().casefold()
        assert "rogerio" not in saiu and "rogério" not in saiu, "o nome sem acento foi para o modelo"
        assert "[pessoa_1] confirmou que levantou a voz" in saiu

    def test_o_nome_com_acento_decomposto_vira_o_marcador(self):
        decomposto = "Rogério Valente negou."

        texto, _ = relatorio.marcar_nomes(decomposto, ["Rogério Valente"])

        assert texto == "[PESSOA_1] negou."

    def test_nome_fora_da_lista_do_caso_tambem_nao_sai(self):
        texto, _ = relatorio.marcar_nomes("A colega Josefina Bittencourt viu tudo.", [])

        assert "Josefina" not in texto and "Bittencourt" not in texto

    def test_o_marcador_volta_a_ser_o_nome_dentro_do_app(self):
        texto, marcadores = relatorio.marcar_nomes("Rogério gritou. Rogério Valente negou.", ["Rogério Valente"])

        assert texto == "[PESSOA_1] gritou. [PESSOA_1] negou."
        assert relatorio.desmarcar("[PESSOA_1] negou.", marcadores) == "Rogério Valente negou."


# ═══════════════════════════════════════════════════════════════════════════
# O texto do Produto Canal de Conduta no kit de conhecimento diz o
# comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    @pytest.fixture
    def texto(self) -> str:
        return (CONHECIMENTO_DIR / "canal-de-conduta.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "frase",
        [
            "## O relatório da apuração",
            "GERAR RELATÓRIO",
            "cabe em uma página",
            "versão nova",
            "ClickSign",
            "ENVIAR PARA VOTO",
            "nenhum nome",
            "MONTAR CRONOLOGIA",
        ],
    )
    def test_o_kit_diz_o_comportamento_novo(self, texto, frase):
        assert frase in texto
