"""Chave de API reserva quando o crédito da principal acaba (issue #1925).

O SDK `anthropic` é o de verdade: só o transporte HTTP é trocado
(`httpx2.MockTransport`), e o dublê responde conforme a chave que veio no
pedido. Assim o teste lê o que sairia para a Anthropic e qual chave foi usada,
pelos mesmos pontos que o app usa (`ai_processor._get_llm`, `ia._cliente` de
Contas médicas e `ouvidoria_agente_triagem._cliente`). Nenhum chega à rede.
"""

from __future__ import annotations

import json
import logging
import os
import sys

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anthropic_apoio import _eventos_do_stream, erro, mensagem  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import ai_processor, ia_chaves, ouvidoria_agente_triagem  # noqa: E402
from app.services.contas_medicas import ia as contas_ia  # noqa: E402

PRINCIPAL = "sk-ant-principal-plantada"
RESERVA_1 = "sk-ant-reserva-um-plantada"
RESERVA_2 = "sk-ant-reserva-dois-plantada"
TODAS = (PRINCIPAL, RESERVA_1, RESERVA_2)

SEM_SALDO_402 = ("billing_error", 402, "Your credit balance is too low to access the Anthropic API.")
SEM_SALDO_400 = (
    "invalid_request_error",
    400,
    "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade.",
)


class Relogio:
    """O relógio das chaves esgotadas, que o teste anda à mão."""

    def __init__(self):
        self.agora = 1_000_000.0

    def __call__(self) -> float:
        return self.agora

    def andar(self, segundos: float) -> None:
        self.agora += segundos


class Anthropic:
    """A API de mentira: cada chave responde do jeito que o teste mandar.
    Guarda a chave de cada pedido, na ordem."""

    def __init__(self):
        self.respostas: dict[str, httpx2.Response] = {}
        self.chaves_usadas: list[str] = []
        self.texto = lambda apelido: f"resposta da {apelido}"
        self.rede_caida = False

    def sem_saldo(self, chave: str, forma=SEM_SALDO_402) -> None:
        tipo, status, texto = forma
        self.respostas[chave] = erro(status, tipo, texto)

    def falhar(self, chave: str, status: int, tipo: str, texto: str) -> None:
        self.respostas[chave] = erro(status, tipo, texto)

    def __call__(self, pedido: httpx2.Request) -> httpx2.Response:
        cabecalhos = pedido.headers
        chave = cabecalhos.get("x-api-key") or cabecalhos.get("authorization", "").removeprefix("Bearer ")
        self.chaves_usadas.append(chave)
        if self.rede_caida:
            raise httpx2.ConnectError("sem rede")
        resposta = self.respostas.get(chave)
        if resposta is not None:
            return httpx2.Response(resposta.status_code, content=resposta.content, headers=resposta.headers)
        corpo = mensagem(self.texto(_apelido(chave)))
        if json.loads(pedido.content or b"{}").get("stream"):
            eventos = _eventos_do_stream(corpo)
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=eventos)
        return httpx2.Response(200, json=corpo)


def _apelido(chave: str) -> str:
    return {PRINCIPAL: "principal", RESERVA_1: "reserva 1", RESERVA_2: "reserva 2"}.get(chave, "outra")


@pytest.fixture
def api(monkeypatch) -> Anthropic:
    """Todo `anthropic.Anthropic(...)` construído no teste fala com a API de
    mentira, mantendo os argumentos de quem construiu."""
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    falsa = Anthropic()
    original = anthropic.Anthropic

    def construir(**kwargs):
        kwargs.pop("max_retries", None)
        transporte = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(falsa))
        return original(**kwargs, http_client=transporte, max_retries=0)

    monkeypatch.setattr(anthropic, "Anthropic", construir)
    return falsa


@pytest.fixture
def relogio(monkeypatch) -> Relogio:
    """As chaves esgotadas começam vazias em cada teste, no relógio do teste."""
    relogio = Relogio()
    monkeypatch.setattr(ia_chaves, "ESGOTADAS", ia_chaves.ChavesEsgotadas(relogio=relogio))
    return relogio


@pytest.fixture
def com_reservas(monkeypatch, relogio):
    monkeypatch.setattr(settings, "anthropic_api_key", PRINCIPAL)
    monkeypatch.setattr(settings, "anthropic_api_keys_reserva", f"{RESERVA_1}, {RESERVA_2}")


class _Leitura(BaseModel):
    texto: str


def _ler_conta() -> _Leitura:
    """Uma leitura de Contas médicas pelo adaptador de verdade, sem gravar a
    chamada no banco."""
    onde = contas_ia._Onde(supabase=None, conta_id=None, atendimento_id=None, passo="A")
    return contas_ia._chamar_a_ia(
        modelo="claude-sonnet-5-5", instrucao="instrucao", blocos=[("conta", False)], saida=_Leitura, onde=onde
    )


def _chat() -> str:
    client, model = ai_processor._get_llm()
    return ai_processor._pedir_texto(client, model, system="instrucao", conteudo="oi")


class TestReservaAssumeQuandoOSaldoAcaba:
    def test_saldo_acabado_na_principal_refaz_a_chamada_na_reserva(self, api, com_reservas):
        api.sem_saldo(PRINCIPAL)

        assert _chat() == "resposta da reserva 1"
        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1]

    def test_o_400_de_credito_baixo_tambem_troca_de_chave(self, api, com_reservas):
        api.sem_saldo(PRINCIPAL, SEM_SALDO_400)

        assert _chat() == "resposta da reserva 1"
        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1]

    def test_a_reserva_sem_saldo_passa_para_a_seguinte_na_ordem_cadastrada(self, api, com_reservas):
        api.sem_saldo(PRINCIPAL)
        api.sem_saldo(RESERVA_1)

        assert _chat() == "resposta da reserva 2"
        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1, RESERVA_2]

    def test_a_ata_em_streaming_troca_de_chave(self, api, com_reservas):
        api.sem_saldo(PRINCIPAL)
        client, model = ai_processor._get_llm()

        texto = ai_processor._pedir_texto(client, model, system="instrucao", conteudo="oi", ata=True)

        assert texto == "resposta da reserva 1"
        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1]

    def test_contas_medicas_le_a_conta_pela_reserva(self, api, com_reservas, monkeypatch):
        api.sem_saldo(PRINCIPAL)
        monkeypatch.setattr(contas_ia, "_gravar", lambda *a, **kw: None)
        api.texto = lambda apelido: json.dumps({"texto": f"lida pela {apelido}"})

        assert _ler_conta().texto == "lida pela reserva 1"
        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1]

    def test_a_triagem_da_ouvidoria_le_o_caso_pela_reserva(self, api, com_reservas):
        api.sem_saldo(PRINCIPAL)
        cliente = ouvidoria_agente_triagem._cliente()

        resposta = cliente.messages.create(model="claude-sonnet-5-5", max_tokens=10, messages=[])

        assert resposta.content[0].text == "resposta da reserva 1"
        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1]

    def test_o_laco_de_ferramentas_segue_na_reserva_a_cada_volta(self, api, com_reservas):
        api.sem_saldo(PRINCIPAL)
        client, model = ai_processor._get_llm()

        for _volta in range(3):
            client.messages.create(model=model, max_tokens=10, messages=[])

        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1, RESERVA_1, RESERVA_1]


class TestSemReserva:
    def test_com_a_variavel_vazia_a_principal_e_a_unica_chave(self, api, relogio, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", PRINCIPAL)
        monkeypatch.setattr(settings, "anthropic_api_keys_reserva", "")

        assert _chat() == "resposta da principal"
        assert api.chaves_usadas == [PRINCIPAL]

    def test_com_a_variavel_vazia_o_saldo_acabado_sobe_o_erro_de_hoje(self, api, relogio, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", PRINCIPAL)
        monkeypatch.setattr(settings, "anthropic_api_keys_reserva", " , ")
        api.sem_saldo(PRINCIPAL)
        client, model = ai_processor._get_llm()

        with pytest.raises(anthropic.APIStatusError) as falha:
            client.messages.create(model=model, max_tokens=10, messages=[])

        assert falha.value.status_code == 402
        assert api.chaves_usadas == [PRINCIPAL]


class TestUmaHoraDeLado:
    def test_a_chave_esgotada_nao_e_tentada_durante_a_hora(self, api, com_reservas, relogio):
        api.sem_saldo(PRINCIPAL)
        _chat()
        api.chaves_usadas.clear()

        relogio.andar(59 * 60)

        assert _chat() == "resposta da reserva 1"
        assert api.chaves_usadas == [RESERVA_1]

    def test_passada_a_hora_a_principal_volta_a_ser_a_primeira(self, api, com_reservas, relogio):
        api.sem_saldo(PRINCIPAL)
        _chat()
        api.respostas.clear()  # o crédito da principal renovou
        api.chaves_usadas.clear()

        relogio.andar(60 * 60 + 1)

        assert _chat() == "resposta da principal"
        assert api.chaves_usadas == [PRINCIPAL]


class TestSoOSaldoTrocaDeChave:
    @pytest.mark.parametrize(
        ("status", "tipo", "texto"),
        [
            (429, "rate_limit_error", "Number of requests has exceeded your rate limit"),
            (529, "overloaded_error", "Overloaded"),
            (500, "api_error", "Internal server error"),
            (400, "invalid_request_error", "max_tokens: Field required"),
            (401, "authentication_error", "invalid x-api-key"),
        ],
    )
    def test_erro_que_nao_e_de_saldo_sobe_sem_trocar_de_chave(self, api, com_reservas, status, tipo, texto):
        api.falhar(PRINCIPAL, status, tipo, texto)
        client, model = ai_processor._get_llm()

        with pytest.raises(anthropic.APIStatusError) as falha:
            client.messages.create(model=model, max_tokens=10, messages=[])

        assert falha.value.status_code == status
        assert api.chaves_usadas == [PRINCIPAL]
        assert not ia_chaves.ESGOTADAS.esgotada(PRINCIPAL)

    def test_erro_de_rede_sobe_sem_trocar_de_chave(self, api, com_reservas):
        api.rede_caida = True
        client, model = ai_processor._get_llm()

        with pytest.raises(anthropic.APIConnectionError):
            client.messages.create(model=model, max_tokens=10, messages=[])

        assert api.chaves_usadas == [PRINCIPAL]


class TestTodasSemSaldo:
    def test_sobe_o_mesmo_erro_de_saldo_de_hoje(self, api, com_reservas):
        for chave in TODAS:
            api.sem_saldo(chave)
        client, model = ai_processor._get_llm()

        with pytest.raises(anthropic.APIStatusError) as falha:
            client.messages.create(model=model, max_tokens=10, messages=[])

        assert (falha.value.status_code, falha.value.type) == (402, "billing_error")
        assert api.chaves_usadas == list(TODAS)

    def test_contas_medicas_mostra_o_mesmo_aviso_de_sem_credito(self, api, com_reservas, monkeypatch):
        for chave in TODAS:
            api.sem_saldo(chave)
        monkeypatch.setattr(contas_ia, "_gravar", lambda *a, **kw: None)

        with pytest.raises(contas_ia.IASemCredito):
            _ler_conta()

    def test_com_todas_esgotadas_a_que_recebeu_credito_volta_na_hora(self, api, com_reservas):
        for chave in TODAS:
            api.sem_saldo(chave)
        with pytest.raises(anthropic.APIStatusError):
            _chat()
        api.respostas.pop(RESERVA_2)  # alguém pôs crédito na reserva 2
        api.chaves_usadas.clear()

        assert _chat() == "resposta da reserva 2"
        assert api.chaves_usadas == [PRINCIPAL, RESERVA_1, RESERVA_2]


class TestNenhumaChaveVaza:
    def test_o_log_da_troca_diz_o_apelido_e_nunca_a_chave(self, api, com_reservas, caplog):
        api.sem_saldo(PRINCIPAL)
        api.sem_saldo(RESERVA_1)

        with caplog.at_level(logging.DEBUG):
            _chat()

        avisos = [r.getMessage() for r in caplog.records if r.name == ia_chaves.logger.name]
        assert avisos == [
            "[IA] Chave principal sem saldo (HTTP 402): esgotada por 1 hora, a chamada vai para a reserva 1",
            "[IA] Chave reserva 1 sem saldo (HTTP 402): esgotada por 1 hora, a chamada vai para a reserva 2",
        ]
        todo_o_log = caplog.text + "".join(str(r.args) for r in caplog.records)
        for chave in TODAS:
            assert chave not in todo_o_log

    def test_o_erro_que_sobe_nao_carrega_a_chave(self, api, com_reservas):
        for chave in TODAS:
            api.sem_saldo(chave)

        with pytest.raises(anthropic.APIStatusError) as falha:
            _chat()

        for chave in TODAS:
            assert chave not in str(falha.value)
            assert chave not in repr(falha.value)
