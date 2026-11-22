"""A trilha com gavetas e o Dossiê do caso do Canal de Conduta (issue #1837;
especificação, seções 9.1 e 9.2; ADR 0097, decisões 2 e 9).

Cada classe é um critério de aceite da issue. O banco e o Storage são os
dublês de `conduta_apoio`, e a cifra é de verdade.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import secrets
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient
from test_conduta_voto import BASE, COORDENACAO, LEITOR, MEMBRO, NOMES, Comite, _pessoa

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.routers import conduta_depoimentos, conduta_trilha  # noqa: E402

AUDIO = b"ID3 audio do depoimento do acusado" + bytes(range(256))
TRANSCRICAO = "Rogério Valente: eu não ameacei ninguém, só levantei a voz.".encode()
TERMO = b"%PDF-1.4 termo de declaracao assinado a caneta"


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")


def _sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


class ComiteDaTrilha(Comite):
    def cliente(self, pid: str) -> TestClient:
        cliente = super().cliente(pid)
        cliente.app.include_router(conduta_depoimentos.router, prefix="/api")
        cliente.app.include_router(conduta_trilha.router, prefix="/api")
        return cliente

    def enviar(self, pid: str, caminho: str, nome: str, conteudo: bytes, campo: str = "arquivo"):
        return self.cliente(pid).post(f"{BASE}{caminho}", files={campo: (nome, conteudo, "application/octet-stream")})

    def caso_com_depoimento(self, *, termo: bool = True) -> tuple[str, str]:
        """Um caso do rito Rápido com o acusado ouvido: transcrição, áudio e,
        se pedido, o termo assinado, enviados pela tela. Volta na etapa Voto."""
        caso = self.caso(acusado_ouvido=False)
        self.linha_do_caso(caso)["etapa"] = "apuracao"
        resposta = self.post(
            COORDENACAO, f"/casos/{caso}/depoimentos", {"nome": "Rogério Valente", "cargo": "Supervisor", "papel": "acusado"}
        )
        assert resposta.status_code == 200, resposta.text
        depoimento = resposta.json()["depoimento"]["id"]
        base = f"/casos/{caso}/depoimentos/{depoimento}"
        assert self.enviar(COORDENACAO, f"{base}/transcricao", "depoimento.txt", TRANSCRICAO).status_code == 200
        assert self.enviar(MEMBRO, f"{base}/audio", "depoimento.mp3", AUDIO).status_code == 200
        if termo:
            assert self.enviar(COORDENACAO, f"{base}/termo-assinado", "termo.pdf", TERMO).status_code == 200
        self.linha_do_caso(caso)["etapa"] = "voto"
        return caso, depoimento

    def trilha_do_caso(self, caso: str, pid: str = COORDENACAO) -> dict:
        return self.abrir(pid, caso)["trilha"]


@pytest.fixture
def comite() -> ComiteDaTrilha:
    return ComiteDaTrilha()


# ═══════════════════════════════════════════════════════════════════════════
# A trilha mostra cada ato e documento com autor, data, origem e código de
# integridade
# ═══════════════════════════════════════════════════════════════════════════


class TestLinhaDoTempo:
    def test_o_documento_enviado_aparece_com_quem_enviou_quando_origem_e_codigo(self, comite):
        caso, _ = comite.caso_com_depoimento()

        documentos = [i for i in comite.trilha_do_caso(caso)["linha_do_tempo"] if i["tipo"] == "documento"]

        audio = next(d for d in documentos if d["titulo"] == "Áudio do depoimento, Acusado 1")
        assert audio["autor"] == NOMES[MEMBRO]
        assert audio["data"]
        assert audio["origem"] == "Upload"
        assert audio["codigo"] == _sha(AUDIO)
        assert audio["versao"] == 1

    def test_o_ato_aparece_com_autor_data_origem_e_o_codigo_da_linha(self, comite):
        caso, _ = comite.caso_com_depoimento()

        atos = [i for i in comite.trilha_do_caso(caso)["linha_do_tempo"] if i["tipo"] == "ato"]

        adicionou = next(a for a in atos if a["acao"] == "adicionou_pessoa_a_ouvir")
        linha = next(t for t in comite.banco.tabelas["conduta_trilha"] if t["acao"] == "adicionou_pessoa_a_ouvir")
        assert adicionou["autor"] == NOMES[COORDENACAO]
        assert adicionou["data"] == linha["registrado_em"]
        assert adicionou["origem"] == "Aplicação"
        assert adicionou["codigo"] == linha["codigo"]
        assert "Rogério" not in adicionou["titulo"]

    def test_a_correcao_entra_como_versao_nova_e_a_anterior_fica(self, comite):
        caso, depoimento = comite.caso_com_depoimento()
        comite.linha_do_caso(caso)["etapa"] = "apuracao"
        corrigida = TRANSCRICAO + b" Corrigida."
        comite.enviar(COORDENACAO, f"/casos/{caso}/depoimentos/{depoimento}/transcricao", "nova.txt", corrigida)

        transcricoes = [
            i
            for i in comite.trilha_do_caso(caso)["linha_do_tempo"]
            if i["titulo"] == "Transcrição do depoimento, Acusado 1"
        ]

        assert [(t["versao"], t["codigo"]) for t in transcricoes] == [(1, _sha(TRANSCRICAO)), (2, _sha(corrigida))]

    def test_a_ciencia_anexada_leva_o_codigo_do_arquivo(self, comite):
        caso, _ = comite.caso_com_depoimento()
        assert comite.anexar_ciencia(LEITOR, caso).status_code == 200

        ciencia = next(
            i for i in comite.trilha_do_caso(caso)["linha_do_tempo"] if i["titulo"] == "Ciência do Código pelo acusado"
        )

        assert (ciencia["autor"], ciencia["origem"]) == (NOMES[LEITOR], "Upload")
        assert ciencia["codigo"] == _sha(b"%PDF-1.4 ciencia do codigo")

    def test_o_documento_assinado_na_clicksign_leva_a_origem_e_o_codigo_da_copia(self, comite, monkeypatch):
        from app.services import clicksign_service
        from app.services.conduta import assinaturas

        caso, _ = comite.caso_com_depoimento()
        comite.ata_assinada(caso)
        pdf = b"%PDF-1.4 ata assinada pelos tres com o log da ClickSign"
        monkeypatch.setattr(clicksign_service, "get_signed_document", lambda _envelope: pdf)
        linha = next(a for a in comite.banco.tabelas["conduta_assinaturas"] if a["caso_id"] == caso)
        linha["assinado_em"] = "2026-11-20T15:00:00+00:00"
        assinaturas.processar_evento(comite.banco, linha, "document_closed")

        ata = next(
            i for i in comite.trilha_do_caso(caso)["linha_do_tempo"] if i["titulo"] == "Ata de deliberação assinada"
        )

        assert ata["origem"] == "ClickSign"
        assert ata["autor"] == ", ".join(NOMES[p] for p in (COORDENACAO, MEMBRO, LEITOR))
        assert ata["data"] == "2026-11-20T15:00:00+00:00"
        assert ata["codigo"] == _sha(pdf)


# ═══════════════════════════════════════════════════════════════════════════
# Cada rito cria as gavetas exigidas, com a situação de cada uma
# ═══════════════════════════════════════════════════════════════════════════


def _gavetas(trilha: dict) -> dict[str, str]:
    return {g["rotulo"]: g["situacao"] for g in trilha["gavetas"]}


class TestGavetas:
    def test_o_rito_rapido_cria_as_gavetas_do_termo_da_ciencia_e_da_ata(self, comite):
        caso, _ = comite.caso_com_depoimento(termo=False)

        assert _gavetas(comite.trilha_do_caso(caso)) == {
            "Termo de declaração, Acusado 1": "Aguardando",
            "Ciência do Código pelo acusado": "Aguardando",
            "Ata de deliberação": "Aguardando",
        }

    def test_a_gaveta_muda_para_assinado_quando_o_documento_chega(self, comite):
        caso, _ = comite.caso_com_depoimento(termo=True)
        comite.anexar_ciencia(COORDENACAO, caso)
        for pid in (MEMBRO, LEITOR, COORDENACAO):
            comite.votar(pid, caso)
        comite.ata_assinada(caso)

        assert set(_gavetas(comite.trilha_do_caso(caso)).values()) == {"Assinado"}

    def test_o_rito_completo_cria_tambem_a_do_relatorio_e_a_do_termo_do_apurador(self, comite):
        caso, _ = comite.caso_com_depoimento()
        comite.linha_do_caso(caso)["rito"] = "completo"
        comite.banco.tabelas.setdefault("conduta_atribuicoes", []).append(
            {"id": "atr-1", "caso_id": caso, "participante_id": "FORA", "motivo": "apurador", "termo_assinado_em": None}
        )

        gavetas = _gavetas(comite.trilha_do_caso(caso))

        assert gavetas["Relatório de apuração"] == "Aguardando"
        assert gavetas["Termo de confidencialidade, Apurador 1"] == "Aguardando"
        assert gavetas["Termo de declaração, Acusado 1"] == "Assinado"

    def test_o_encaminhamento_nao_cria_gaveta(self, comite):
        caso = comite.caso(acusado_ouvido=False)
        comite.linha_do_caso(caso).update({"rito": "encaminhamento", "etapa": "encaminhamento"})

        assert comite.trilha_do_caso(caso)["gavetas"] == []

    def test_toda_gaveta_do_rito_e_obrigatoria_e_diz_a_origem(self, comite):
        caso, _ = comite.caso_com_depoimento()

        origens = {g["rotulo"]: (g["obrigatoria"], g["origem"]) for g in comite.trilha_do_caso(caso)["gavetas"]}

        assert origens["Termo de declaração, Acusado 1"] == (True, "Upload")
        assert origens["Ata de deliberação"] == (True, "ClickSign")
