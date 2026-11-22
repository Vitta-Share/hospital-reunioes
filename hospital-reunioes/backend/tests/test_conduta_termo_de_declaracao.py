"""O termo de declaração redigido pelo agente (issue #1831, PRD #1786; ADR
0097, decisão 7; especificação, 7.1 e Anexos C e E.1).

Cada classe é um critério de aceite da issue. O banco, o Storage e a ClickSign
são dublês, a cifra é de verdade, e a IA é o `ClienteFalso`: o teste lê o que
sairia para o modelo e escolhe o que ele responde.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
from typing import Any

import httpx
import pdfplumber
import pytest
from anthropic_apoio import ClienteFalso
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_conduta_convites import _ClickSign
from test_conduta_depoimentos import (  # noqa: F401  (a fixture da chave vale aqui)
    BASE,
    COORDENACAO,
    MEMBRO,
    Comite,
    _chave,
)

from app.config import settings
from app.dependencies import get_current_user, get_supabase_client
from app.limiter import limiter
from app.routers import conduta_comite, conduta_depoimentos, webhooks
from app.services import clicksign_service
from app.services.conduta import cifra, termo_de_declaracao, trilha
from app.services.conhecimento import CONHECIMENTO_DIR

TRANSCRICAO = (
    "Entrevistador: Fulano de Tal, o senhor confirma que estava no almoxarifado?\n"
    "Fulano de Tal: Confirmo. Eu estava lá com a Maria Souza, das 14h às 15h.\n"
    "Fulano de Tal: Acho que levantei a voz, mas não ameacei ninguém.\n"
).encode()

IDENTIFICACAO = {
    "data": "2026-11-20",
    "hora": "14:30",
    "local": "Sala do Comitê",
    "conduziram": ["Ana Coordenadora", "Bruno Membro"],
    "cpf": "",
}


def _marcador(enviado: str, antes: str) -> str:
    """O marcador que o app pôs logo depois de `antes` no texto enviado."""
    achado = re.search(re.escape(antes) + r"(\[PESSOA_\d+\])", enviado)
    assert achado, f"sem marcador depois de {antes!r}"
    return achado.group(1)


def termo_que_ecoa(enviado: str, **campos) -> str:
    """O agente bem-comportado: usa os marcadores que recebeu, nunca o nome."""
    declarante = _marcador(enviado, "Entrevistador: ")
    maria = _marcador(enviado, "estava lá com a ")
    termo = {
        "declaracoes": [f"{declarante} declarou que estava no almoxarifado com {maria}, das 14h às 15h."],
        "documentos": [],
        "consentimento": "dado",
        "notas": [f"Perguntar a {maria} o que ouviu."],
    }
    return json.dumps({**termo, **campos})


class Agente(ClienteFalso):
    """O `ClienteFalso` que responde conforme o que recebeu: `responder`
    recebe tudo o que saiu para o modelo (instrução e mensagem)."""

    def __init__(self):
        super().__init__()
        self.responder = termo_que_ecoa

    def _create(self, **kwargs):
        self.texto = self.responder(_texto_da_chamada(kwargs))
        return super()._create(**kwargs)


def _texto_da_chamada(chamada: dict) -> str:
    return str(chamada.get("system", "")) + "\n" + json.dumps(chamada["messages"], ensure_ascii=False)


@pytest.fixture
def agente(monkeypatch) -> Agente:
    cliente = Agente()
    monkeypatch.setattr(termo_de_declaracao, "_cliente_do_agente_do_termo", lambda: cliente)
    return cliente


def _enviado(agente: Agente) -> str:
    """Tudo o que saiu para o modelo na última chamada."""
    return _texto_da_chamada(agente.chamadas[-1])


def _cartao(comite: Comite, caso: str, dep: str, pid: str = MEMBRO) -> dict[str, Any]:
    return next(d for d in comite.abrir(pid, caso)["depoimentos"] if d["id"] == dep)


def _redigir(comite: Comite, caso: str, dep: str, pid: str = MEMBRO, **corpo):
    return comite.cliente(pid).post(f"{BASE}/casos/{caso}/depoimentos/{dep}/termo", json={**IDENTIFICACAO, **corpo})


def _com_transcricao(comite: Comite) -> tuple[str, str]:
    caso = comite.caso()
    dep = comite.depoimento(caso)
    resposta = comite.anexar(MEMBRO, caso, dep, "transcricao", "depoimento.txt", TRANSCRICAO)
    assert resposta.status_code == 200, resposta.text
    return caso, dep


# ═══════════════════════════════════════════════════════════════════════════
# 1. O termo nasce de um clique, da transcrição ou dos pontos digitados
# ═══════════════════════════════════════════════════════════════════════════


class TestOTermoNasceDeUmClique:
    def test_o_clique_redige_o_termo_a_partir_da_transcricao(self, agente):
        comite = Comite()
        caso, dep = _com_transcricao(comite)
        assert _cartao(comite, caso, dep)["termo"] is None
        assert agente.chamadas == []

        resposta = _redigir(comite, caso, dep)

        assert resposta.status_code == 200, resposta.text
        assert len(agente.chamadas) == 1
        assert "não ameacei ninguém" in _enviado(agente)
        termo = _cartao(comite, caso, dep)["termo"]
        assert termo["versao"] == 1
        assert termo["declaracoes"] == [
            "Fulano de Tal declarou que estava no almoxarifado com Maria Souza, das 14h às 15h."
        ]

    def test_sem_gravacao_o_termo_sai_dos_pontos_digitados(self, agente):
        comite = Comite()
        caso = comite.caso()
        dep = comite.depoimento(caso)
        pontos = "Entrevistador: Fulano de Tal confirmou. Disse que estava lá com a Maria Souza no almoxarifado."
        comite.cliente(MEMBRO).post(
            f"{BASE}/casos/{caso}/depoimentos/{dep}/sem-gravacao", json={"motivo": "Não quis gravar", "pontos": pontos}
        )

        resposta = _redigir(comite, caso, dep)

        assert resposta.status_code == 200, resposta.text
        assert "no almoxarifado" in _enviado(agente)
        termo = _cartao(comite, caso, dep)["termo"]
        assert termo["gravacao"] == "Não houve gravação. Os pontos da conversa foram registrados por quem conduziu."
        texto = _texto_do_pdf(_imprimir(comite, caso, dep).content)
        assert "Não houve gravação." in texto
        assert (
            "Texto elaborado com apoio de inteligência artificial a partir dos pontos da conversa e revisado por "
            "quem conduziu a conversa." in texto
        )
        assert "a partir da gravação" not in texto

    def test_sem_transcricao_nem_pontos_o_clique_e_recusado_sem_chamar_o_agente(self, agente):
        comite = Comite()
        caso = comite.caso()
        dep = comite.depoimento(caso)

        resposta = _redigir(comite, caso, dep)

        assert resposta.status_code == 409
        assert "Anexe a transcrição" in resposta.json()["detail"]
        assert agente.chamadas == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. Marcadores na ida, nomes na volta
# ═══════════════════════════════════════════════════════════════════════════

NOMES_DA_CONVERSA = ("Fulano", "Maria Souza", "Ana Coordenadora", "Bruno Membro", "Joana Citada", "529.982.247-25")


class TestNenhumNomeVaiAoModelo:
    def test_o_texto_enviado_leva_marcadores_e_o_termo_exibido_traz_os_nomes(self, agente):
        comite = Comite()
        caso = comite.caso()
        comite.banco.tabelas.setdefault("conduta_citados", []).append(
            {
                "id": "cit-1",
                "caso_id": caso,
                "participante_id": None,
                "nome_cifrado": cifra.cifrar_texto("Joana Citada"),
            }
        )
        dep = comite.depoimento(caso)
        conversa = TRANSCRICAO + "Fulano de Tal: A joana citada viu tudo. Meu CPF é 529.982.247-25.\n".encode()
        comite.anexar(MEMBRO, caso, dep, "transcricao", "depoimento.txt", conversa)

        assert _redigir(comite, caso, dep).status_code == 200

        enviado = _enviado(agente)
        for nome in NOMES_DA_CONVERSA:
            assert nome.lower() not in enviado.lower(), f"{nome} foi ao modelo"
        assert "[PESSOA_" in enviado and "[CPF_1]" in enviado
        termo = _cartao(comite, caso, dep)["termo"]
        assert termo["declaracoes"] == [
            "Fulano de Tal declarou que estava no almoxarifado com Maria Souza, das 14h às 15h."
        ]
        assert termo["notas"]["itens"] == ["Perguntar a Maria Souza o que ouviu."]

    def test_quem_conduziu_tambem_vira_marcador_e_o_modelo_sabe_quem_e_quem(self, agente):
        comite = Comite()
        caso, dep = _com_transcricao(comite)

        _redigir(comite, caso, dep)

        mensagem = agente.chamadas[-1]["messages"][0]["content"]
        achado = re.search(
            r"Quem é quem: (\[PESSOA_\d+\]) é o declarante\. (\[PESSOA_\d+\]) e (\[PESSOA_\d+\])", mensagem
        )
        assert achado, mensagem
        assert len(set(achado.groups())) == 3
        assert achado.group(1) == _marcador(mensagem, "Entrevistador: ")


# ═══════════════════════════════════════════════════════════════════════════
# 3. Relato anônimo: o termo não cita quem relatou
# ═══════════════════════════════════════════════════════════════════════════

AVISO_DE_ANONIMO = "O relato do caso é ANÔNIMO"
REGRA_8 = "Quando o relato é anônimo, não escreva nome, marcador, cargo ou pista de quem relatou."


class TestRelatoAnonimo:
    def test_no_caso_anonimo_o_agente_e_proibido_de_citar_quem_relatou(self, agente):
        comite = Comite()
        caso, dep = _com_transcricao(comite)

        _redigir(comite, caso, dep)

        assert AVISO_DE_ANONIMO in agente.chamadas[-1]["messages"][0]["content"]
        assert REGRA_8 in agente.chamadas[-1]["system"]

    def test_com_denunciante_identificado_no_caso_o_relato_deixa_de_ser_anonimo(self, agente):
        comite = Comite()
        caso, dep = _com_transcricao(comite)
        comite.adicionar(MEMBRO, caso, {"nome": "Beltrana Souto", "cargo": "Auxiliar", "papel": "denunciante"})

        _redigir(comite, caso, dep)

        mensagem = agente.chamadas[-1]["messages"][0]["content"]
        assert AVISO_DE_ANONIMO not in mensagem
        assert "Não cite quem relatou." in mensagem
        assert "beltrana" not in mensagem.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 4 e 5. As notas são Sugestão e ficam fora do PDF; IMPRIMIR TERMO e a correção
# ═══════════════════════════════════════════════════════════════════════════


def _texto_do_pdf(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as documento:
        texto = "\n".join(pagina.extract_text() or "" for pagina in documento.pages)
    return re.sub(r"\s+", " ", texto)


def _imprimir(comite: Comite, caso: str, dep: str, pid: str = MEMBRO):
    return comite.cliente(pid).get(f"{BASE}/casos/{caso}/depoimentos/{dep}/termo/pdf")


def _corrigir(comite: Comite, caso: str, dep: str, termo: dict, pid: str = MEMBRO):
    campos = ("identificacao", "gravacao", "declaracoes", "documentos", "lido_em_voz_alta")
    corpo = {campo: termo[campo] for campo in campos}
    corpo["identificacao"] = {k: v for k, v in corpo["identificacao"].items() if k not in ("nome", "cargo")}
    return comite.cliente(pid).post(f"{BASE}/casos/{caso}/depoimentos/{dep}/termo/correcoes", json=corpo)


def _termo_redigido(comite: Comite, **corpo) -> tuple[str, str]:
    caso, dep = _com_transcricao(comite)
    resposta = _redigir(comite, caso, dep, **corpo)
    assert resposta.status_code == 200, resposta.text
    return caso, dep


class TestNotasParaQuemApura:
    def test_as_notas_aparecem_marcadas_como_sugestao_e_nao_entram_no_pdf(self, agente):
        comite = Comite()
        caso, dep = _termo_redigido(comite)
        notas = _cartao(comite, caso, dep)["termo"]["notas"]
        assert notas == {"rotulo": "Sugestão", "itens": ["Perguntar a Maria Souza o que ouviu."]}

        resposta = _imprimir(comite, caso, dep)

        assert resposta.status_code == 200, resposta.text
        texto = _texto_do_pdf(resposta.content)
        assert "estava no almoxarifado com Maria Souza" in texto
        assert "o que ouviu" not in texto
        assert "Sugestão" not in texto and "Notas para quem apura" not in texto


class TestImprimirTermo:
    def test_imprimir_termo_gera_o_pdf_com_os_blocos_do_anexo_e1(self, agente):
        comite = Comite()
        caso, dep = _termo_redigido(comite, cpf="529.982.247-25")
        protocolo = comite.abrir(MEMBRO, caso)["protocolo"]

        resposta = _imprimir(comite, caso, dep)

        assert resposta.status_code == 200, resposta.text
        assert resposta.headers["content-type"] == "application/pdf"
        texto = _texto_do_pdf(resposta.content)
        for trecho in (
            # Cabeçalho
            "Hospital São Matheus · Canal de Conduta · Termo de declaração",
            protocolo,
            # Identificação
            "Fulano de Tal",
            "529.982.247-25",
            "Supervisor do almoxarifado",
            "20/11/2026",
            "14:30",
            "Sala do Comitê",
            "Ana Coordenadora e Bruno Membro",
            # Gravação
            "Esta conversa foi gravada com meu consentimento.",
            # Declarações, numeradas
            "1. Fulano de Tal declarou que estava no almoxarifado com Maria Souza, das 14h às 15h.",
            # Encerramento
            "Li este termo (ou ouvi sua leitura) e ele corresponde ao que declarei.",
            # Compromissos
            "dever de dizer a verdade",
            "sigilo sobre o caso",
            "retaliação é falta grave",
            # Rodapé
            "Texto elaborado com apoio de inteligência artificial a partir da gravação e revisado por quem "
            "conduziu a conversa.",
            # Assinaturas e rubrica
            "Declarante",
            "Quem conduziu",
            "Rubrica",
        ):
            assert trecho in texto, f"falta no PDF: {trecho!r}"

    def test_imprimir_fica_na_trilha(self, agente):
        comite = Comite()
        caso, dep = _termo_redigido(comite)

        _imprimir(comite, caso, dep)

        acoes = [linha["acao"] for linha in comite.banco.tabelas["conduta_trilha"] if linha["caso_id"] == caso]
        assert acoes[-2:] == ["redigiu_termo", "imprimiu_termo"]

    def test_uma_correcao_gera_versao_nova_e_a_anterior_fica(self, agente):
        comite = Comite()
        caso, dep = _termo_redigido(comite)
        termo = _cartao(comite, caso, dep)["termo"]
        termo["declaracoes"] = ["Fulano de Tal declarou que estava no almoxarifado com Maria Souza, das 13h às 15h."]
        termo["lido_em_voz_alta"] = True

        resposta = _corrigir(comite, caso, dep, termo)

        assert resposta.status_code == 200, resposta.text
        novo = _cartao(comite, caso, dep)["termo"]
        assert (novo["versao"], novo["origem"]) == (2, "correcao")
        assert novo["notas"]["itens"] == ["Perguntar a Maria Souza o que ouviu."]
        assert [v["versao"] for v in comite.banco.tabelas["conduta_depoimento_termos"]] == [1, 2]
        texto = _texto_do_pdf(_imprimir(comite, caso, dep).content)
        assert "das 13h às 15h" in texto and "das 14h às 15h" not in texto
        assert "Versão 2" in texto
        assert "Este termo foi lido em voz alta ao declarante por quem conduziu a conversa." in texto

    def test_correcao_sem_mudanca_nao_gera_versao(self, agente):
        comite = Comite()
        caso, dep = _termo_redigido(comite)

        resposta = _corrigir(comite, caso, dep, _cartao(comite, caso, dep)["termo"])

        assert resposta.status_code == 409
        assert len(comite.banco.tabelas["conduta_depoimento_termos"]) == 1

    def test_sem_termo_redigido_nao_ha_o_que_imprimir(self, agente):
        comite = Comite()
        caso, dep = _com_transcricao(comite)

        assert _imprimir(comite, caso, dep).status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# 7. O PDF não tem travessão
# ═══════════════════════════════════════════════════════════════════════════

TRACOS = ("—", "–")


class TestSemTravessao:
    def test_o_pdf_sai_sem_travessao_mesmo_quando_o_agente_escreve_um(self, agente):
        comite = Comite()

        def com_travessao(enviado: str) -> str:
            termo = json.loads(termo_que_ecoa(enviado))
            termo["declaracoes"] = ["Declarou que — naquele dia – estava no almoxarifado."]
            termo["documentos"] = ["Escala de novembro — cópia"]
            return json.dumps(termo)

        agente.responder = com_travessao
        caso, dep = _termo_redigido(comite, local="Sala 2 — térreo")

        texto = _texto_do_pdf(_imprimir(comite, caso, dep).content)

        assert "naquele dia" in texto and "Escala de novembro" in texto and "térreo" in texto
        assert not any(traco in texto for traco in TRACOS)


# ═══════════════════════════════════════════════════════════════════════════
# 6. A certidão de recusa vai à ClickSign para dois membros e volta à trilha
# ═══════════════════════════════════════════════════════════════════════════

SEGREDO_DO_WEBHOOK = "segredo-de-teste-do-webhook"


@pytest.fixture
def clicksign(monkeypatch) -> _ClickSign:
    dubla = _ClickSign()
    for nome in (
        "create_envelope",
        "add_document",
        "add_signer",
        "create_qualification_requirement",
        "create_auth_requirement",
        "activate_envelope",
        "notify_signers",
        "cancel_envelope",
        "get_envelope_status",
        "get_signed_document",
    ):
        monkeypatch.setattr(clicksign_service, nome, getattr(dubla, nome))
    monkeypatch.setattr(settings, "clicksign_webhook_secret", SEGREDO_DO_WEBHOOK)
    return dubla


class ComiteComWebhook(Comite):
    def cliente(self, pid: str) -> TestClient:
        app = FastAPI()
        app.state.limiter = limiter
        for router in (conduta_comite.router, conduta_depoimentos.router, webhooks.router):
            app.include_router(router, prefix="/api")
        pessoa = next(p for p in self.banco.tabelas["participantes"] if p["id"] == pid)

        async def _usuario() -> dict[str, Any]:
            return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app)

    def assinar(self, documento_key: str):
        corpo = json.dumps({"event": {"name": "auto_close"}, "document": {"key": documento_key}}).encode()
        carimbo = hmac.new(SEGREDO_DO_WEBHOOK.encode(), corpo, hashlib.sha256).hexdigest()
        return self.cliente(MEMBRO).post(
            "/api/webhooks/clicksign",
            content=corpo,
            headers={"content-hmac": f"sha256={carimbo}", "content-type": "application/json"},
        )


def _recusar(comite: Comite, caso: str, dep: str, pid: str = MEMBRO, membro: str = COORDENACAO):
    return comite.cliente(pid).post(f"{BASE}/casos/{caso}/depoimentos/{dep}/recusa", json={"membro_id": membro})


def _certidoes(comite: Comite) -> list[dict]:
    return [a for a in comite.banco.tabelas.get("conduta_assinaturas", []) if a["tipo"] == "certidao_de_recusa"]


def _acoes(comite: Comite, caso: str) -> list[str]:
    return [linha["acao"] for linha in comite.banco.tabelas["conduta_trilha"] if linha["caso_id"] == caso]


class TestCertidaoDeRecusa:
    def test_a_certidao_vai_a_clicksign_para_dois_membros(self, agente, clicksign):
        comite = ComiteComWebhook()
        caso, dep = _termo_redigido(comite)

        resposta = _recusar(comite, caso, dep)

        assert resposta.status_code == 200, resposta.text
        assert sorted(email for *_, email in clicksign.signatarios()) == ["coord@hsm.test", "memb@hsm.test"]
        [certidao] = _certidoes(comite)
        assert (certidao["caso_id"], certidao["depoimento_id"], certidao["situacao"]) == (caso, dep, "enviado")
        assert sorted(certidao["signatarios"]) == sorted([COORDENACAO, MEMBRO])
        assert _acoes(comite, caso)[-1] == "enviou_certidao_de_recusa"
        assert _cartao(comite, caso, dep)["recusa"]["situacao"] == "enviado"

    def test_assinada_pelos_dois_a_certidao_volta_para_a_trilha_e_vale_pelo_termo_assinado(self, agente, clicksign):
        comite = ComiteComWebhook()
        caso, dep = _termo_redigido(comite)
        _recusar(comite, caso, dep)
        [certidao] = _certidoes(comite)

        resposta = comite.assinar(certidao["documento_key"])

        assert resposta.status_code == 200, resposta.text
        assert _acoes(comite, caso)[-1] == "certidao_de_recusa_assinada"
        cartao = _cartao(comite, caso, dep)
        assert cartao["recusa"]["situacao"] == "assinado"
        [item] = [i for i in cartao["lista"] if i["item"] == "termo_assinado"]
        assert item["estado"] == "nao_se_aplica"
        assert "certidão de recusa" in item["motivo"]
        assert cartao["situacao"] != "Aguardando assinatura"

    def test_se_a_trilha_falha_no_fechamento_o_reenvio_da_clicksign_grava_a_linha(self, agente, clicksign, monkeypatch):
        comite = ComiteComWebhook()
        caso, dep = _termo_redigido(comite)
        _recusar(comite, caso, dep)
        [certidao] = _certidoes(comite)
        registrar_de_verdade = trilha.registrar
        falhas = []

        def registrar_que_cai_uma_vez(supabase, caso_id, autor_id, acao, detalhe=""):
            if acao == "certidao_de_recusa_assinada" and not falhas:
                falhas.append(acao)
                raise httpx.ReadTimeout("trilha fora do ar")
            return registrar_de_verdade(supabase, caso_id, autor_id, acao, detalhe)

        monkeypatch.setattr(trilha, "registrar", registrar_que_cai_uma_vez)

        assert comite.assinar(certidao["documento_key"]).status_code == 500
        assert "certidao_de_recusa_assinada" not in _acoes(comite, caso)

        assert comite.assinar(certidao["documento_key"]).status_code == 200
        assert comite.assinar(certidao["documento_key"]).status_code == 200
        assert _acoes(comite, caso).count("certidao_de_recusa_assinada") == 1

    def test_a_certidao_nao_leva_o_protocolo_para_a_clicksign(self, agente, clicksign):
        comite = ComiteComWebhook()
        caso, dep = _termo_redigido(comite)
        protocolo = comite.abrir(MEMBRO, caso)["protocolo"]

        _recusar(comite, caso, dep)

        texto = _texto_do_pdf(clicksign.documentos[-1])
        assert "Certidão de recusa de assinatura" in texto
        assert "Fulano de Tal" in texto
        assert protocolo not in texto

    def test_o_segundo_membro_tem_que_ser_outro_membro_do_caso(self, agente, clicksign):
        comite = ComiteComWebhook()
        caso, dep = _termo_redigido(comite)

        assert _recusar(comite, caso, dep, membro=MEMBRO).status_code == 422
        assert _recusar(comite, caso, dep, membro="FORA").status_code == 422
        assert clicksign.signatarios() == []

    def test_sem_termo_redigido_nao_ha_certidao(self, agente, clicksign):
        comite = ComiteComWebhook()
        caso, dep = _com_transcricao(comite)

        assert _recusar(comite, caso, dep).status_code == 409
        assert clicksign.signatarios() == []


# ═══════════════════════════════════════════════════════════════════════════
# O roteiro de perguntas, por clique
# ═══════════════════════════════════════════════════════════════════════════


class TestRoteiroDePerguntas:
    def test_o_clique_pede_o_roteiro_ao_agente_sem_nome_e_o_cartao_mostra_com_os_nomes(self, agente):
        comite = Comite()
        caso = comite.caso()
        dep = comite.depoimento(caso)

        def roteiro(enviado: str) -> str:
            assert "Fulano" not in enviado
            declarante = re.search(r"(\[PESSOA_\d+\]) é a pessoa ouvida", enviado).group(1)
            return json.dumps({"perguntas": [f"{declarante}, onde o senhor estava naquela tarde?"]})

        agente.responder = roteiro

        resposta = comite.cliente(MEMBRO).post(f"{BASE}/casos/{caso}/depoimentos/{dep}/roteiro")

        assert resposta.status_code == 200, resposta.text
        assert "supervisor grita com a equipe" in _enviado(agente)
        cartao = _cartao(comite, caso, dep)
        assert cartao["roteiro"] == {
            "rotulo": "Sugestão",
            "perguntas": ["Fulano de Tal, onde o senhor estava naquela tarde?"],
        }
        assert "sugeriu_roteiro" in _acoes(comite, caso)

    def test_sem_o_clique_nao_ha_roteiro_nem_chamada(self, agente):
        comite = Comite()
        caso = comite.caso()
        dep = comite.depoimento(caso)

        assert _cartao(comite, caso, dep)["roteiro"] is None
        assert agente.chamadas == []

    def test_agente_fora_do_ar_diz_para_tentar_de_novo_e_nada_e_gravado(self, agente):
        comite = Comite()
        caso, dep = _com_transcricao(comite)

        def fora(_enviado: str) -> str:
            raise TimeoutError("sem resposta")

        agente.responder = fora

        resposta = _redigir(comite, caso, dep)

        assert resposta.status_code == 503
        assert resposta.json()["detail"] == termo_de_declaracao.AGENTE_FORA
        assert comite.banco.tabelas.get("conduta_depoimento_termos", []) == []


# ═══════════════════════════════════════════════════════════════════════════
# 8. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    @pytest.fixture
    def texto(self) -> str:
        return (CONHECIMENTO_DIR / "canal-de-conduta.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "frase",
        [
            "## O termo de declaração",
            '"REDIGIR TERMO"',
            "o agente redige o termo de declaração",
            "os nomes viram marcadores numerados",
            "Quando o relato é anônimo, o termo não cita quem relatou",
            '"Notas para quem apura"',
            '"Sugestão"',
            '"IMPRIMIR TERMO"',
            "Cada correção lançada gera uma versão nova",
            "lido em voz alta",
            "certidão de recusa",
            '"SUGERIR ROTEIRO DE PERGUNTAS"',
        ],
    )
    def test_o_texto_do_produto_diz_o_comportamento_novo(self, texto, frase):
        assert frase in texto
