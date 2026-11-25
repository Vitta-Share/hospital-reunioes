"""O diretor escolhe o modelo de cada Demanda (issue #1921, ADR 0103).

Na conversa da Demanda, um seletor "Sonnet 5.5 | Opus 5.5" mostra o modelo
atual e troca com um clique. A escolha mora em `tecnologia_planejamentos.modelo`
e vale da próxima chamada em diante: a pergunta, o resumo, a Revisão e o chat
da aba. Demanda nova nasce no Sonnet 5.5; a antiga mantém o modelo gravado. A
estimativa da Revisão usa o modelo escolhido. Fora dos dois, 422; quem não vê
a Demanda, 404.

Tudo pela ROTA, com o modelo dublado, no molde de `test_tecnologia_revisao`.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_planejamento_demanda import _ia, _pergunta  # noqa: E402
from test_tecnologia_chat import (  # noqa: E402
    _cenario,
    _chamadas,
    _conversas,
    _integracao_configurada,  # noqa: F401
    _llm_em_mock,  # noqa: F401
    _reset_rate_limiter,  # noqa: F401
    _turno,
)
from test_tecnologia_revisao import (  # noqa: E402
    CHAT,
    CONVERSA_ENVIADA,
    DEMANDA,
    REVISAO,
    _card,
    _montar_revisao,
    _retrato,
)
from test_tecnologia_vinculo import DIRETOR, PEDRO, _pessoa  # noqa: E402

SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"
MODELO = f"{CHAT}/{DEMANDA}/modelo"

# A melhoria no meio do planejamento: a pergunta espera a resposta.
CONVERSA_COM_PERGUNTA = CONVERSA_ENVIADA[:5]
# O bug no Roteiro: a IA perguntou onde aconteceu.
CONVERSA_DO_BUG = [
    {"tipo": "ia", "texto": "Isso é um bug ou uma melhoria?", "fonte": None, "opcoes": ["Bug", "Melhoria"]},
    {"tipo": "diretor", "texto": "Bug"},
    {
        "tipo": "ia",
        "texto": "Onde isso aconteceu?",
        "fonte": None,
        "opcoes": [],
        "classificacao": "bug",
        "confirmada": True,
        "roteiro": True,
    },
]


def _resumo_do_modelo() -> str:
    return '{"decisoes": [{"pergunta": 1, "porque": "É quem atende."}], "em_aberto": []}'


def _montar(monkeypatch, *, modelo: str | None = SONNET, mensagens=None, estado="em_andamento", logado=DIRETOR):
    client, sb, gh = _montar_revisao(monkeypatch, logado=logado, estado=estado)
    linha = _conversas(sb)[0]
    linha["mensagens"] = [dict(m) for m in (CONVERSA_COM_PERGUNTA if mensagens is None else mensagens)]
    if modelo is not None:
        linha["modelo"] = modelo
    return client, sb, gh


# ═══════════════════════════════════════════════════════════════════════════
# 1. O seletor: o modelo atual e a troca
# ═══════════════════════════════════════════════════════════════════════════


class TestOSeletorDoModelo:
    def test_a_conversa_da_demanda_mostra_o_modelo_atual(self, monkeypatch):
        client, _, _ = _montar(monkeypatch, modelo=OPUS)

        resposta = client.get(f"{CHAT}/{DEMANDA}")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["modelo"] == OPUS

    def test_o_diretor_troca_o_modelo_com_um_clique(self, monkeypatch):
        client, sb, _ = _montar(monkeypatch, modelo=SONNET)

        resposta = client.put(MODELO, json={"modelo": OPUS})

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["modelo"] == OPUS
        assert _conversas(sb)[0]["modelo"] == OPUS
        assert client.get(f"{CHAT}/{DEMANDA}").json()["modelo"] == OPUS

    def test_a_troca_nao_mexe_na_trava_da_conversa(self, monkeypatch):
        """O turno que estava no ar quando o diretor trocou o modelo grava
        normalmente: a troca nao e uma fala da conversa."""
        client, sb, _ = _montar(monkeypatch)
        antes = _conversas(sb)[0]["atualizado_em"]

        client.put(MODELO, json={"modelo": OPUS})

        assert _conversas(sb)[0]["atualizado_em"] == antes


# ═══════════════════════════════════════════════════════════════════════════
# 2. Depois da troca, a próxima chamada roda no modelo escolhido
# ═══════════════════════════════════════════════════════════════════════════


class TestAProximaChamadaUsaOModeloEscolhido:
    def test_a_proxima_pergunta_roda_no_modelo_escolhido_e_o_custo_grava_ele(self, monkeypatch):
        client, sb, _ = _montar(monkeypatch, modelo=SONNET)
        client.put(MODELO, json={"modelo": OPUS})
        cliente = _ia(monkeypatch, _pergunta())

        resposta = client.post(f"{CHAT}/{DEMANDA}", json={"opcao": "A"})

        assert resposta.status_code == 200, resposta.text
        assert cliente.chamadas[0]["model"] == OPUS
        assert _chamadas(sb)[-1]["modelo"] == OPUS

    def test_o_resumo_roda_no_modelo_escolhido(self, monkeypatch):
        client, sb, _ = _montar(monkeypatch, modelo=SONNET)
        client.put(MODELO, json={"modelo": OPUS})
        cliente = _ia(monkeypatch, _resumo_do_modelo())

        resposta = client.post(f"{CHAT}/{DEMANDA}/resumo")

        assert resposta.status_code == 200, resposta.text
        assert cliente.chamadas[0]["model"] == OPUS
        assert _chamadas(sb)[-1]["modelo"] == OPUS

    def test_a_revisao_roda_no_modelo_escolhido(self, monkeypatch):
        client, sb, _ = _montar(monkeypatch, modelo=SONNET, mensagens=CONVERSA_ENVIADA, estado="enviado")
        client.put(MODELO, json={"modelo": OPUS})
        cliente = _ia(monkeypatch, _retrato())

        resposta = client.post(REVISAO, json={"confirmado": True})

        assert resposta.status_code == 200, resposta.text
        assert [c["model"] for c in cliente.chamadas] == [OPUS]
        assert _chamadas(sb)[-1]["modelo"] == OPUS

    def test_o_chat_da_aba_roda_no_modelo_da_demanda(self, monkeypatch):
        client, sb, _ = _montar(monkeypatch, modelo=SONNET, mensagens=CONVERSA_DO_BUG)
        _card_do_bug(sb)
        client.put(MODELO, json={"modelo": OPUS})
        cliente = _ia(monkeypatch, _turno())

        resposta = client.post(f"{CHAT}/{DEMANDA}", json={"texto": "Na Ouvidoria"})

        assert resposta.status_code == 200, resposta.text
        assert cliente.chamadas[0]["model"] == OPUS
        assert _chamadas(sb)[-1]["modelo"] == OPUS


def _card_do_bug(sb) -> None:
    sb.tabelas["tecnologia_demandas"] = [_card(tipo="defeito", github_issue_numero=None, etapa="registrada")]
    _conversas(sb)[0]["resumo"] = None


# ═══════════════════════════════════════════════════════════════════════════
# 3. Demanda nova nasce no Sonnet; a antiga mantém o modelo
# ═══════════════════════════════════════════════════════════════════════════


class TestDemandaNovaEAntiga:
    def test_demanda_nova_nasce_no_sonnet(self, monkeypatch):
        client, sb, _ = _cenario(monkeypatch, participantes=[PEDRO, DIRETOR])
        cliente = _ia(monkeypatch, _pergunta())

        resposta = client.post(CHAT, json={"escolha": "melhoria"})

        assert resposta.status_code == 201, resposta.text
        assert resposta.json()["modelo"] == SONNET
        assert _conversas(sb)[0]["modelo"] == SONNET
        assert cliente.chamadas[0]["model"] == SONNET

    def test_demanda_antiga_mantem_o_modelo_que_tinha(self, monkeypatch):
        client, sb, _ = _montar(monkeypatch, modelo=OPUS)
        cliente = _ia(monkeypatch, _pergunta())

        client.post(f"{CHAT}/{DEMANDA}", json={"opcao": "A"})

        assert cliente.chamadas[0]["model"] == OPUS
        assert _conversas(sb)[0]["modelo"] == OPUS


# ═══════════════════════════════════════════════════════════════════════════
# 4. A estimativa da Revisão acompanha o modelo
# ═══════════════════════════════════════════════════════════════════════════


class TestAEstimativaAcompanhaOModelo:
    def test_a_estimativa_muda_conforme_o_modelo_escolhido(self, monkeypatch):
        client, _, _ = _montar(monkeypatch, modelo=SONNET, mensagens=CONVERSA_ENVIADA, estado="enviado")
        no_sonnet = client.get(REVISAO).json()

        client.put(MODELO, json={"modelo": OPUS})
        no_opus = client.get(REVISAO).json()

        assert no_sonnet["modelo"] == "Sonnet 5.5"
        assert no_opus["modelo"] == "Opus 5.5"
        # O Opus custa o dobro do Sonnet na entrada e na saída.
        assert no_opus["minimo_usd"] > no_sonnet["minimo_usd"]
        assert no_opus["maximo_usd"] > no_sonnet["maximo_usd"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. A recusa
# ═══════════════════════════════════════════════════════════════════════════


class TestARecusa:
    def test_modelo_fora_dos_dois_volta_422(self, monkeypatch):
        client, sb, _ = _montar(monkeypatch, modelo=SONNET)

        resposta = client.put(MODELO, json={"modelo": "claude-haiku-5-5"})

        assert resposta.status_code == 422
        assert _conversas(sb)[0]["modelo"] == SONNET

    def test_quem_nao_e_super_admin_nao_troca_o_modelo(self, monkeypatch):
        """Desde a issue #2265 (ADR 0113, decisao 6) todo Super admin ve a
        Demanda: quem fica de fora e quem nao e Super admin."""
        gestor = _pessoa("P9", "Gestora do Setor", access_profile="facilitador")
        client, sb, _ = _montar(monkeypatch, modelo=SONNET, logado=gestor)

        resposta = client.put(MODELO, json={"modelo": OPUS})

        assert resposta.status_code == 403
        assert _conversas(sb)[0]["modelo"] == SONNET
