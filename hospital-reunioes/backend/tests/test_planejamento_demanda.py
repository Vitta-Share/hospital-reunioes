"""A porta da IA da aba Tecnologia (issue #1345, PRD #1344, ADR 0075).

Era o Planejamento da Demanda, a conversa da melhoria no chat. O chat saiu na
issue #2279 (ADR 0113, decisão 7), e o serviço ficou com a chamada ao modelo
que o Envio aos desenvolvedores usa. Aqui:

* **A migration 123**, lida do disco: as duas tabelas e o RLS default-deny.
* **A chamada ao modelo**, direto no serviço, com o cliente da Anthropic
  dublado (troca `ai_processor._get_llm`). Nenhum teste chega à API de
  verdade: o `_llm_provider` nasce em mock em todo teste, e a trava de rede da
  suíte (`conftest.py`) reprova quem tentar.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from app.config import settings  # noqa: E402
from app.services import planejamento_demanda  # noqa: E402
from app.services.conhecimento import carregar_kit  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION_123 = MIGRATIONS / "123_tecnologia_planejamento.sql"


# ═══════════════════════════════════════════════════════════════════════════
# 1. A migration 123
# ═══════════════════════════════════════════════════════════════════════════


def _sql() -> str:
    return MIGRATION_123.read_text(encoding="utf-8")


def _colunas_da_tabela(sql: str, tabela: str) -> dict[str, str]:
    """Coluna -> o resto da linha que a declara."""
    bloco = re.search(rf"CREATE TABLE IF NOT EXISTS {tabela} \((.*?)\n\);", sql, flags=re.DOTALL)
    assert bloco, f"a 123 nao cria {tabela}"
    colunas = {}
    for linha in bloco.group(1).splitlines():
        partes = linha.strip().split(None, 1)
        if partes and partes[0][0].isalpha() and partes[0].upper() != "CHECK":
            colunas[partes[0]] = partes[1] if len(partes) > 1 else ""
    return colunas


class TestMigracao:
    def test_cria_o_planejamento_um_por_demanda(self):
        colunas = _colunas_da_tabela(_sql(), "tecnologia_planejamentos")

        assert {"demanda_id", "estado", "mensagens", "decisoes", "modelo", "criado_em", "atualizado_em"} <= set(colunas)
        # Um planejamento por Demanda: a unicidade mora no banco.
        assert "UNIQUE" in colunas["demanda_id"]
        assert "REFERENCES tecnologia_demandas(id)" in colunas["demanda_id"]
        assert colunas["mensagens"].startswith("JSONB")
        assert colunas["decisoes"].startswith("JSONB")

    def test_cria_a_chamada_de_ia_da_tecnologia_no_molde_de_contas_medicas(self):
        colunas = _colunas_da_tabela(_sql(), "tecnologia_chamadas_ia")

        assert {
            "demanda_id",
            "modelo",
            "tokens_entrada",
            "tokens_saida",
            "tokens_cache",
            "custo_usd",
            "duracao_ms",
            "sucesso",
            "criado_em",
        } <= set(colunas)
        # O custo fica, mesmo que a Demanda saia.
        assert "ON DELETE SET NULL" in colunas["demanda_id"]

    def test_rls_default_deny_nas_duas_tabelas(self):
        sql = _sql()

        for tabela in ("tecnologia_planejamentos", "tecnologia_chamadas_ia"):
            assert f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;" in sql, tabela
        # Default-deny: quem le e escreve e o backend com a service_role.
        assert "CREATE POLICY" not in sql.upper()

    def test_termina_com_o_recibo_do_proprio_numero(self):
        corpo = "\n".join(linha for linha in _sql().splitlines() if not linha.startswith("--")).strip()

        assert corpo.endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (123) ON CONFLICT (numero) DO NOTHING;")


@pytest.fixture(autouse=True)
def _llm_em_mock(monkeypatch):
    """O pytest carrega o `.env` real (chave de PROD). Sem isto, qualquer teste
    que chegasse ao servico bateria no provedor de verdade."""
    from app.services import ai_processor

    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "mock")
    yield


# ═══════════════════════════════════════════════════════════════════════════
# 2. A chamada ao modelo (o servico, sem estado)
# ═══════════════════════════════════════════════════════════════════════════


def _uso(entrada: int = 1000, saida: int = 200, lidos: int = 0, escritos: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=entrada,
        output_tokens=saida,
        cache_read_input_tokens=lidos,
        cache_creation_input_tokens=escritos,
    )


class _ClienteFalso:
    """A Anthropic de mentira: guarda os argumentos de cada chamada e devolve o
    texto dado, com o `usage` dado. `texto` pode ser uma excecao."""

    def __init__(self, texto: str | BaseException, usage: SimpleNamespace | None = None, stop_reason="end_turn"):
        self.texto = texto
        self.usage = usage or _uso()
        self.stop_reason = stop_reason
        self.chamadas: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.chamadas.append(kwargs)
        if isinstance(self.texto, BaseException):
            raise self.texto
        # Com o thinking ligado, o bloco de texto vem depois do de pensamento.
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self.texto)],
            stop_reason=self.stop_reason,
            usage=self.usage,
        )


def _ia(monkeypatch, texto: str | BaseException, **kw) -> _ClienteFalso:
    """Troca o cliente do `ai_processor`, que e o mesmo do Assistente."""
    from app.services import ai_processor

    cliente = _ClienteFalso(texto, **kw)
    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "anthropic")
    monkeypatch.setattr(ai_processor, "_get_llm", lambda: (cliente, "modelo-do-resto-do-app"))
    return cliente


DEMANDA = {
    "id": "d-1",
    "titulo": "Agenda de retorno na recepção",
    "tipo": "novo",
    "descricao": "O que precisa: marcar o retorno do paciente na saída",
}

PROMPT = "envio_aos_desenvolvedores_system"


class _Saida(BaseModel):
    topicos: list[str]


def _chamar(conteudo: str = "O pedido que varia"):
    return planejamento_demanda.chamar_o_modelo(
        demanda=DEMANDA,
        passo="envio",
        conteudo=conteudo,
        kit=carregar_kit(),
        validar=_Saida.model_validate,
        prompt=PROMPT,
    )


RESPOSTA = json.dumps({"topicos": ["Marcar o retorno na saída"]})


class TestOPedidoAIA:
    def test_o_bloco_fixo_vai_com_cache_e_antes_de_tudo_que_varia(self, monkeypatch):
        """A instrucao e o kit sao o `system`, com o `cache_control` no ultimo
        bloco dele; o que varia vem DEPOIS, na mensagem do usuario."""
        cliente = _ia(monkeypatch, RESPOSTA)

        saida, _ = _chamar("Só no turno da noite.")

        assert saida.topicos == ["Marcar o retorno na saída"]
        enviado = cliente.chamadas[0]
        sistema = enviado["system"]
        assert [bloco.get("cache_control") for bloco in sistema] == [None, {"type": "ephemeral"}]
        fixo = "\n".join(bloco["text"] for bloco in sistema)
        assert "A Etapa nunca \u00e9 digitada \u00e0 m\u00e3o" in fixo  # uma frase que so existe no kit
        assert "Só no turno da noite." not in fixo
        assert enviado["messages"][0]["content"] == "Só no turno da noite."

    def test_usa_o_modelo_do_planejamento_sem_mexer_no_thinking_nem_no_effort(self, monkeypatch):
        cliente = _ia(monkeypatch, RESPOSTA)

        _chamar()

        enviado = cliente.chamadas[0]
        assert settings.llm_model_planejamento == "claude-sonnet-5-5"
        assert enviado["model"] == "claude-sonnet-5-5"
        assert "thinking" not in enviado
        assert "tools" not in enviado
        assert "effort" not in json.dumps(enviado.get("output_config", {}))


class TestOCustoDaChamada:
    def test_grava_modelo_tokens_custo_duracao_e_sucesso(self, monkeypatch):
        # Opus 5.5: US$ 4 entrada, US$ 20 saida, US$ 0,20 leitura e US$ 5 escrita de cache por milhao.
        monkeypatch.setattr(settings, "llm_model_planejamento", "claude-opus-5-5")
        _ia(monkeypatch, RESPOSTA, usage=_uso(entrada=1000, saida=500, lidos=20000, escritos=2000))

        _, chamada = _chamar()

        assert chamada["demanda_id"] == "d-1"
        assert chamada["passo"] == "envio"
        assert chamada["modelo"] == "claude-opus-5-5"
        assert chamada["tokens_entrada"] == 23000
        assert chamada["tokens_saida"] == 500
        assert chamada["tokens_cache"] == 20000
        # 1000*4 + 500*20 + 20000*0,20 + 2000*5 = 28000 por milhao
        assert chamada["custo_usd"] == 0.028
        assert isinstance(chamada["duracao_ms"], int)
        assert chamada["sucesso"] is True

    def test_modelo_fora_da_tabela_grava_custo_zero(self, monkeypatch):
        _ia(monkeypatch, RESPOSTA)
        monkeypatch.setattr(settings, "llm_model_planejamento", "modelo-sem-preco")

        assert _chamar()[1]["custo_usd"] == 0


def _erro_do_provedor() -> anthropic.APIStatusError:
    requisicao = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.InternalServerError("fora do ar", response=httpx.Response(500, request=requisicao), body=None)


class TestFalhaDaChamada:
    @pytest.mark.parametrize(
        ("texto", "rodadas"),
        [
            # Sem JSON nenhum, a chamada pede o JSON uma vez (rodada a mais).
            pytest.param("isto n\u00e3o \u00e9 JSON", 2, id="nao-e-json"),
            pytest.param(json.dumps({"outra": "coisa"}), 1, id="fora-do-esquema"),
        ],
    )
    def test_saida_que_nao_valida_volta_nula_e_a_chamada_fica_sem_sucesso(self, monkeypatch, texto, rodadas):
        cliente = _ia(monkeypatch, texto, usage=_uso(entrada=900, saida=300))

        saida, chamada = _chamar()

        assert saida is None
        # A resposta fora do formato foi cobrada: a chamada fica, sem sucesso.
        assert chamada["sucesso"] is False
        assert len(cliente.chamadas) == rodadas
        assert chamada["tokens_saida"] == 300 * rodadas

    def test_erro_do_provedor_volta_nulo(self, monkeypatch):
        _ia(monkeypatch, _erro_do_provedor())

        saida, chamada = _chamar()

        assert saida is None
        assert chamada["sucesso"] is False
        assert chamada["tokens_entrada"] == 0

    def test_recusa_do_modelo_volta_nula(self, monkeypatch):
        _ia(monkeypatch, RESPOSTA, stop_reason="refusal")

        assert _chamar()[0] is None
