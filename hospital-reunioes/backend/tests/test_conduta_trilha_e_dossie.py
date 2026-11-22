"""A trilha com gavetas e o Dossiê do caso do Canal de Conduta (issue #1837;
especificação, seções 9.1 e 9.2; ADR 0097, decisões 2 e 9).

Cada classe é um critério de aceite da issue. O banco e o Storage são os
dublês de `conduta_apoio`, e a cifra é de verdade.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import secrets
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient
from test_conduta_voto import BASE, COORDENACAO, LEITOR, MEMBRO, NOMES, RELATO, Comite, _pessoa

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
            COORDENACAO,
            f"/casos/{caso}/depoimentos",
            {"nome": "Rogério Valente", "cargo": "Supervisor", "papel": "acusado"},
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

    def baixar(self, pid: str, caso: str):
        return self.cliente(pid).get(f"{BASE}/casos/{caso}/dossie")


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


# ═══════════════════════════════════════════════════════════════════════════
# Gaveta obrigatória vazia bloqueia a conclusão como procedente, com o motivo
# ═══════════════════════════════════════════════════════════════════════════


class TestGavetaVaziaBloqueia:
    def _pronto_para_concluir(self, comite, caso: str, resultado: str) -> None:
        medida = "advertencia_escrita" if resultado != "improcedente" else None
        for pid in (MEMBRO, LEITOR, COORDENACAO):
            assert comite.votar(pid, caso, resultado=resultado, medida=medida).status_code == 200
        if resultado == "improcedente":
            comite.ata_assinada(caso)
        else:
            comite.trava_completa(caso)
            # O depoimento do acusado segue aberto: a defesa pede dois membros.
            assert comite.confirmar(MEMBRO, caso, "defesa").status_code == 200

    @pytest.mark.parametrize("resultado", ["procedente", "parcialmente_procedente"])
    def test_sem_o_termo_assinado_o_caso_nao_conclui_como_procedente(self, comite, resultado):
        caso, _ = comite.caso_com_depoimento(termo=False)
        self._pronto_para_concluir(comite, caso, resultado)

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao")

        assert resposta.status_code == 409
        motivo = "Gaveta obrigatória vazia: Termo de declaração, Acusado 1."
        assert resposta.json()["detail"] == motivo
        assert comite.abrir(COORDENACAO, caso)["votacao"]["bloqueio_da_conclusao"] == motivo
        assert comite.linha_do_caso(caso).get("resultado") is None

    def test_com_as_gavetas_cheias_conclui_como_procedente(self, comite):
        caso, _ = comite.caso_com_depoimento(termo=True)
        self._pronto_para_concluir(comite, caso, "procedente")

        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 200
        assert comite.linha_do_caso(caso)["resultado"] == "procedente"

    def test_a_gaveta_pela_certidao_de_recusa_conta_como_assinada(self, comite):
        caso, depoimento = comite.caso_com_depoimento(termo=False)
        comite.banco.tabelas.setdefault("conduta_assinaturas", []).append(
            {
                "id": "certidao-1",
                "tipo": "certidao_de_recusa",
                "caso_id": caso,
                "depoimento_id": depoimento,
                "signatarios": [COORDENACAO, MEMBRO],
                "situacao": "assinado",
            }
        )

        gaveta = next(
            g for g in comite.trilha_do_caso(caso)["gavetas"] if g["rotulo"].startswith("Termo de declaração")
        )

        assert (gaveta["situacao"], gaveta["origem"]) == ("Assinado", "ClickSign")

    def test_improcedente_conclui_com_gaveta_vazia(self, comite):
        caso, _ = comite.caso_com_depoimento(termo=False)
        self._pronto_para_concluir(comite, caso, "improcedente")

        assert comite.post(COORDENACAO, f"/casos/{caso}/conclusao-da-votacao").status_code == 200
        assert comite.linha_do_caso(caso)["resultado"] == "improcedente"


# ═══════════════════════════════════════════════════════════════════════════
# A conferência da cadeia da trilha acusa linha adulterada
# ═══════════════════════════════════════════════════════════════════════════


class TestConferenciaDaCadeia:
    def _linhas(self, comite, caso: str) -> list[dict]:
        return sorted(
            (t for t in comite.banco.tabelas["conduta_trilha"] if t["caso_id"] == caso), key=lambda t: t["seq"]
        )

    def test_a_trilha_intacta_confere(self, comite):
        caso, _ = comite.caso_com_depoimento()

        conferencia = comite.trilha_do_caso(caso)["conferencia"]

        assert conferencia == {"intacta": True, "linhas_adulteradas": [], "texto": "A cadeia da trilha confere."}

    def test_a_linha_trocada_no_banco_aparece_na_conferencia(self, comite):
        caso, _ = comite.caso_com_depoimento()
        trocada = next(t for t in self._linhas(comite, caso) if t["acao"] == "adicionou_pessoa_a_ouvir")
        trocada["detalhe"] = "nada aconteceu"

        conferencia = comite.trilha_do_caso(caso)["conferencia"]

        assert conferencia["intacta"] is False
        assert conferencia["linhas_adulteradas"] == [trocada["seq"]]
        assert conferencia["texto"] == f"A cadeia da trilha não confere na linha {trocada['seq']}."

    def test_a_linha_apagada_no_banco_aparece_na_conferencia(self, comite):
        caso, _ = comite.caso_com_depoimento()
        linhas = self._linhas(comite, caso)
        apagada = linhas[2]
        comite.banco.tabelas["conduta_trilha"].remove(apagada)

        conferencia = comite.trilha_do_caso(caso)["conferencia"]

        assert conferencia["linhas_adulteradas"] == [linhas[3]["seq"]]

    def test_o_registro_de_acessos_do_dossie_traz_a_conferencia(self, comite):
        caso, _ = comite.caso_com_depoimento()
        trocada = next(t for t in self._linhas(comite, caso) if t["acao"] == "anexou_arquivo")
        trocada["autor_id"] = LEITOR

        pacote = _pacote(comite.baixar(COORDENACAO, caso))

        assert f"A cadeia da trilha não confere na linha {trocada['seq']}." in pacote["09-registro-de-acessos.txt"]


# ═══════════════════════════════════════════════════════════════════════════
# "BAIXAR DOSSIÊ" gera o pacote com índice e todos os itens da especificação,
# decifrados
# ═══════════════════════════════════════════════════════════════════════════

ATA = {
    "resumo": "Rogério Valente ameaçou cortar as horas da equipe do almoxarifado.",
    "provas": ["Depoimento de duas testemunhas."],
    "defesa": "Negou a ameaça e admitiu ter levantado a voz.",
    "deliberacao": "Procedente por unanimidade.",
    "fundamentos": "Item 3.2 do Código de Conduta.",
    "medida": "Advertência escrita",
}


def _pacote(resposta) -> dict[str, str | bytes]:
    assert resposta.status_code == 200, resposta.text
    with zipfile.ZipFile(io.BytesIO(resposta.content)) as pacote:
        saida: dict[str, str | bytes] = {}
        for nome in pacote.namelist():
            conteudo = pacote.read(nome)
            saida[nome] = conteudo.decode("utf-8") if nome.endswith(".txt") else conteudo
        return saida


def _arquivo(pacote: dict, pasta: str, trecho: str) -> tuple[str, bytes]:
    [achado] = [(nome, c) for nome, c in pacote.items() if nome.startswith(pasta) and trecho in nome]
    return achado


class ComiteDoDossie(ComiteDaTrilha):
    def caso_votado(self) -> str:
        from app.services.conduta import cifra

        caso, _ = self.caso_com_depoimento()
        for pid in (MEMBRO, LEITOR, COORDENACAO):
            assert self.votar(pid, caso, justificativa=f"Justificativa de {NOMES[pid]}.").status_code == 200
        self.ata_assinada(caso)
        linha = next(a for a in self.banco.tabelas["conduta_atas"] if a["caso_id"] == caso)
        linha["ata_cifrada"] = cifra.cifrar_texto(json.dumps(ATA, ensure_ascii=False))
        return caso


@pytest.fixture
def dossie() -> ComiteDoDossie:
    return ComiteDoDossie()


class TestDossie:
    def test_o_pacote_traz_o_indice_e_as_secoes_da_especificacao(self, dossie):
        pacote = _pacote(dossie.baixar(COORDENACAO, dossie.caso_votado()))

        for secao in (
            "00-indice.txt",
            "01-relato-original.txt",
            "05-votos.txt",
            "06-ata-de-deliberacao.txt",
            "07-decisao-da-direcao.txt",
            "08-mensagens-com-o-denunciante.txt",
            "09-registro-de-acessos.txt",
        ):
            assert secao in pacote
        assert any(nome.startswith("02-documentos/") for nome in pacote)
        assert any(nome.startswith("03-audios/") for nome in pacote)
        assert any(nome.startswith("04-transcricoes-de-depoimentos/") for nome in pacote)

    def test_os_itens_saem_decifrados(self, dossie):
        caso = dossie.caso_votado()

        pacote = _pacote(dossie.baixar(COORDENACAO, caso))

        assert pacote["01-relato-original.txt"].strip().endswith(RELATO)
        assert _arquivo(pacote, "03-audios/", "acusado-1")[1] == AUDIO
        assert _arquivo(pacote, "04-transcricoes-de-depoimentos/", "acusado-1")[1] == TRANSCRICAO.decode()
        assert _arquivo(pacote, "02-documentos/", "termo-de-declaracao")[1] == TERMO
        votos = pacote["05-votos.txt"]
        for pid in (MEMBRO, LEITOR, COORDENACAO):
            assert f"{NOMES[pid]}: Procedente, Advertência escrita" in votos
            assert f"Justificativa de {NOMES[pid]}." in votos
        assert ATA["resumo"] in pacote["06-ata-de-deliberacao.txt"]
        assert ATA["deliberacao"] in pacote["06-ata-de-deliberacao.txt"]

    def test_o_indice_lista_cada_arquivo_com_o_codigo_de_integridade(self, dossie):
        pacote = _pacote(dossie.baixar(COORDENACAO, dossie.caso_votado()))

        indice = pacote["00-indice.txt"]
        nome_do_audio, _ = _arquivo(pacote, "03-audios/", "acusado-1")
        assert nome_do_audio in indice
        assert f"Código de integridade: {_sha(AUDIO)}" in indice
        assert f"Código de integridade: {_sha(TERMO)}" in indice
        assert "Origem: Upload" in indice
        for secao in ("01-relato-original.txt", "05-votos.txt", "09-registro-de-acessos.txt"):
            assert secao in indice

    def test_o_arquivo_trocado_no_bucket_aparece_no_indice(self, dossie):
        from app.services.conduta import cifra

        caso = dossie.caso_votado()
        audio = next(a for a in dossie.banco.tabelas["conduta_depoimento_arquivos"] if a["tipo"] == "audio")
        dossie.banco.storage.objetos[("conduta-arquivos", audio["storage_path"])] = cifra.cifrar_arquivo(b"outro")

        indice = _pacote(dossie.baixar(COORDENACAO, caso))["00-indice.txt"]

        assert "não confere com o código registrado no envio" in indice

    def test_o_voto_ainda_oculto_nao_entra_no_pacote(self, dossie):
        caso, _ = dossie.caso_com_depoimento()
        dossie.votar(MEMBRO, caso, justificativa="Segredo do membro até os três votarem.")

        votos = _pacote(dossie.baixar(COORDENACAO, caso))["05-votos.txt"]

        assert "Segredo do membro" not in votos
        assert "Nenhuma rodada de voto fechada" in votos

    def test_o_pacote_nao_fica_no_cache(self, dossie):
        resposta = dossie.baixar(COORDENACAO, dossie.caso_votado())

        assert resposta.headers["cache-control"] == "no-store"
        assert resposta.headers["content-disposition"].startswith("attachment;")


# ═══════════════════════════════════════════════════════════════════════════
# Cada download registra quem baixou e quando
# ═══════════════════════════════════════════════════════════════════════════


class TestDownloadRegistrado:
    def test_o_download_entra_na_trilha_com_quem_e_quando(self, dossie):
        caso = dossie.caso_votado()

        dossie.baixar(LEITOR, caso)

        [linha] = [t for t in dossie.banco.tabelas["conduta_trilha"] if t["acao"] == "baixou_dossie"]
        assert linha["caso_id"] == caso
        assert linha["autor_id"] == LEITOR
        assert linha["registrado_em"]

    def test_o_proprio_download_vai_no_registro_de_acessos_do_pacote(self, dossie):
        pacote = _pacote(dossie.baixar(MEMBRO, dossie.caso_votado()))

        ultima = pacote["09-registro-de-acessos.txt"].strip().splitlines()[-1]
        assert "baixou o Dossiê do caso" in ultima
        assert NOMES[MEMBRO] in ultima

    def test_sem_o_registro_na_trilha_o_pacote_nao_sai(self, dossie):
        caso = dossie.caso_votado()
        dossie.banco.falhas_da_trilha = 3

        resposta = dossie.baixar(COORDENACAO, caso)

        assert resposta.status_code == 503
        assert not [t for t in dossie.banco.tabelas["conduta_trilha"] if t["acao"] == "baixou_dossie"]


# ═══════════════════════════════════════════════════════════════════════════
# Presidente, diretoria executiva, apurador de outro caso e super admin
# recebem 403 no download
# ═══════════════════════════════════════════════════════════════════════════


class TestSoOComiteBaixa:
    def _com_pessoa(self, dossie, pid: str, **campos) -> None:
        dossie.banco.tabelas["participantes"].append(
            {**_pessoa(MEMBRO), "id": pid, "auth_user_id": f"auth-{pid}", "email": f"{pid}@hsm.test", **campos}
        )

    @pytest.mark.parametrize(
        "pid, campos",
        [
            ("PRES", {"nome_completo": "Paulo Presidente", "perfil_conduta": "presidente"}),
            ("DIRE", {"nome_completo": "Dora Diretora", "perfil_conduta": "diretoria_executiva"}),
            ("ADM", {"nome_completo": "Sara Super", "is_super_admin": True, "role": "super_admin"}),
        ],
    )
    def test_quem_nao_e_do_comite_recebe_403(self, dossie, pid, campos):
        caso = dossie.caso_votado()
        self._com_pessoa(dossie, pid, **campos)

        resposta = dossie.baixar(pid, caso)

        assert resposta.status_code == 403
        assert not [t for t in dossie.banco.tabelas["conduta_trilha"] if t["acao"] == "baixou_dossie"]

    def test_o_apurador_de_outro_caso_recebe_403(self, dossie):
        caso = dossie.caso_votado()
        outro = dossie.caso(acusado_ouvido=False)
        self._com_pessoa(dossie, "APUR", nome_completo="Ivo Apurador")
        dossie.banco.tabelas.setdefault("conduta_atribuicoes", []).append(
            {
                "id": "atr-apur",
                "caso_id": outro,
                "participante_id": "APUR",
                "motivo": "apurador",
                "termo_assinado_em": "2026-11-01T12:00:00+00:00",
            }
        )

        assert dossie.baixar("APUR", caso).status_code == 403

    def test_o_apurador_do_proprio_caso_tambem_nao_baixa(self, dossie):
        caso = dossie.caso_votado()
        self._com_pessoa(dossie, "APUR", nome_completo="Ivo Apurador")
        dossie.banco.tabelas.setdefault("conduta_atribuicoes", []).append(
            {
                "id": "atr-apur",
                "caso_id": caso,
                "participante_id": "APUR",
                "motivo": "apurador",
                "termo_assinado_em": "2026-11-01T12:00:00+00:00",
            }
        )

        assert dossie.abrir("APUR", caso)["trilha"]["pode_baixar_dossie"] is False
        assert dossie.baixar("APUR", caso).status_code == 403

    def test_o_membro_do_comite_no_caso_baixa(self, dossie):
        caso = dossie.caso_votado()

        assert dossie.abrir(MEMBRO, caso)["trilha"]["pode_baixar_dossie"] is True
        assert dossie.baixar(MEMBRO, caso).status_code == 200
