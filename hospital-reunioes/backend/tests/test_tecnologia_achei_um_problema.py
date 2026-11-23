"""Achei um problema no Pedido de implantação (issue #2210, PRD #2205, ADR
0111, decisão 9).

O cartão do Pedido de implantação abre o Assistente de Tecnologia em modo bug,
com o texto inicial que nomeia o Pedido e a entrega. No Criar o card desse
bug, a Demanda nova guarda de qual Demanda veio, a issue cita o PRD de origem
na parte técnica, e o Pedido passa a esperar a Demanda de bug: o cartão mostra
"Espera a Demanda N" e o Concluir recusa com o motivo até ela ficar Entregue.
O PRD de origem não reabre.

Pela ROTA de verdade (ponte e tela), com o Supabase em memória, o modelo e o
GitHub dublados.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_kit_conhecimento import ARQUIVO_DA_ABA  # noqa: E402
from test_kit_conhecimento import _texto as _texto_do_kit  # noqa: E402
from test_planejamento_demanda import _ia  # noqa: E402
from test_tecnologia_anexos import _StorageFake  # noqa: E402
from test_tecnologia_chat import CAMPOS_RESPONDIDOS, CRITERIOS, _turno  # noqa: E402
from test_tecnologia_passo_a_passo_da_vitta import _concluir, _marcar, emails  # noqa: E402, F401
from test_tecnologia_pedido_de_implantacao import CARD, IMPLANTACAO, PASSOS, github  # noqa: E402, F401
from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    CRIAR,
    DEMANDA,
    DIRETORA,
    TABELA,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
)
from test_tecnologia_vinculo import BASE, _GithubFalso, _integracao_configurada, _montar  # noqa: E402, F401

from app.services import tecnologia_perguntas  # noqa: E402

CHAT = f"{BASE}/chat"
ESPERANDO = f"{BASE}/perguntas/esperando"
# O PRD da entrega: o card da Demanda de origem (`_a_demanda` da Pergunta da Vitta).
PRD = 1700


@pytest.fixture(autouse=True)
def _llm_em_mock(monkeypatch):
    from app.services import ai_processor

    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "mock")


def _pedido_de_implantacao():
    """O Pedido de implantação nasce pela ponte, na Demanda da entrega."""
    ponte, sb = _ponte()
    sb.storage = _StorageFake()
    resposta = ponte.post(CRIAR, json=IMPLANTACAO, headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 201, resposta.text
    return sb, resposta.json()["id"]


def _na_tela(sb, monkeypatch, logado=DIRETORA):
    cliente, _, gh = _montar(logado=logado, supabase=sb, github=_GithubFalso({}), monkeypatch=monkeypatch)
    return cliente, gh


def _achei_um_problema(cliente, monkeypatch, pedido_id):
    _ia(monkeypatch, _turno(mensagem="Em qual passo deu errado?"))
    return cliente.post(CHAT, json={"escolha": "bug", "pedido_id": pedido_id})


def _demanda(sb, demanda_id) -> dict:
    return next(d for d in sb.tabelas["tecnologia_demandas"] if d["id"] == demanda_id)


def _pedido(sb, pedido_id) -> dict:
    return next(p for p in sb.tabelas[TABELA] if p["id"] == pedido_id)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Achei um problema abre o Assistente em modo bug
# ═══════════════════════════════════════════════════════════════════════════


class TestAbreOAssistente:
    def test_achei_um_problema_abre_o_bug_com_o_texto_inicial_do_pedido(self, monkeypatch):
        sb, pedido_id = _pedido_de_implantacao()
        cliente, _ = _na_tela(sb, monkeypatch)

        resposta = _achei_um_problema(cliente, monkeypatch, pedido_id)

        assert resposta.status_code == 201, resposta.text
        corpo = resposta.json()
        demanda = _demanda(sb, corpo["demanda_id"])
        assert demanda["tipo"] == "defeito"
        falas = [(m["autor"], m["texto"]) for m in corpo["mensagens"]]
        assert falas[1:] == [
            ("diretor", "Bug"),
            (
                "diretor",
                'Achei um problema no Pedido de implantação "testar o anonimato do Canal de Conduta",'
                ' da entrega "A Ata assinada no app".',
            ),
            ("ia", "Em qual passo deu errado?"),
        ]

    def test_so_o_pedido_de_implantacao_aberto_tem_o_achei_um_problema(self, monkeypatch):
        sb, pedido_id = _pedido_de_implantacao()
        _pedido(sb, pedido_id)["tipo"] = "passo_a_passo"
        cliente, _ = _na_tela(sb, monkeypatch)
        antes = len(sb.tabelas["tecnologia_demandas"])

        resposta = _achei_um_problema(cliente, monkeypatch, pedido_id)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_PROBLEMA_SO_NA_IMPLANTACAO}
        assert len(sb.tabelas["tecnologia_demandas"]) == antes


# ═══════════════════════════════════════════════════════════════════════════
# 2. O Criar o card liga o bug à Demanda de origem e ao Pedido
# ═══════════════════════════════════════════════════════════════════════════


def _bug_ate_o_resumo(sb, monkeypatch, pedido_id):
    cliente, gh = _na_tela(sb, monkeypatch)
    bug_id = _achei_um_problema(cliente, monkeypatch, pedido_id).json()["demanda_id"]
    _ia(
        monkeypatch,
        _turno(pronto=True, mensagem="Montei o resumo. Confere?", campos=CAMPOS_RESPONDIDOS, criterios=CRITERIOS),
    )
    resposta = cliente.post(f"{CHAT}/{bug_id}", json={"texto": "O relato de teste saiu com o meu nome."})
    assert resposta.json()["estado"] == "resumido", resposta.text
    return cliente, gh, bug_id


def _bug_com_card(monkeypatch):
    sb, pedido_id = _pedido_de_implantacao()
    cliente, gh, bug_id = _bug_ate_o_resumo(sb, monkeypatch, pedido_id)
    resposta = cliente.post(f"{CHAT}/{bug_id}/criar-card")
    assert resposta.status_code == 200, resposta.text
    return sb, gh, pedido_id, bug_id


class TestCriarOCardDoBug:
    def test_o_criar_o_card_grava_a_demanda_de_origem_e_liga_o_pedido_ao_bug(self, monkeypatch):
        sb, _, pedido_id, bug_id = _bug_com_card(monkeypatch)

        assert _demanda(sb, bug_id)["demanda_origem_id"] == DEMANDA
        assert _pedido(sb, pedido_id)["espera_demanda_id"] == bug_id

    def test_a_issue_do_bug_cita_o_prd_de_origem_na_parte_tecnica(self, monkeypatch):
        _, gh, _, _ = _bug_com_card(monkeypatch)

        [issue] = gh.criadas
        _, tecnica = issue["corpo"].split("\n---\n", 1)
        assert f"## PRD de origem\n\n#{PRD}" in tecnica

    def test_antes_do_criar_o_card_o_pedido_nao_espera_o_bug(self, monkeypatch):
        sb, pedido_id = _pedido_de_implantacao()
        _, _, bug_id = _bug_ate_o_resumo(sb, monkeypatch, pedido_id)

        assert _pedido(sb, pedido_id).get("espera_demanda_id") is None
        assert _demanda(sb, bug_id).get("demanda_origem_id") is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. "Espera a Demanda N" e o Concluir recusa até o bug ficar Entregue
# ═══════════════════════════════════════════════════════════════════════════

NUMERO_DO_BUG = 57


def _pedido_esperando_o_bug(monkeypatch):
    sb, _, pedido_id, bug_id = _bug_com_card(monkeypatch)
    _demanda(sb, bug_id)["numero"] = NUMERO_DO_BUG
    for passo in range(len(PASSOS)):
        assert _marcar(sb, DIRETORA, pedido_id, monkeypatch, passo).status_code == 200
    return sb, pedido_id, bug_id


def _cartao_na_lista(sb, pedido_id, monkeypatch) -> dict:
    lista = _tela(sb, DIRETORA, monkeypatch).get(ESPERANDO).json()
    return next(item for item in lista if item["id"] == pedido_id)


class TestEsperaADemandaDeBug:
    def test_o_cartao_mostra_espera_a_demanda_de_bug(self, monkeypatch):
        sb, pedido_id, bug_id = _pedido_esperando_o_bug(monkeypatch)

        cartao = _cartao_na_lista(sb, pedido_id, monkeypatch)

        assert cartao["espera_demanda"] == {"demanda_id": bug_id, "numero": NUMERO_DO_BUG}

    def test_o_concluir_recusa_com_o_motivo_ate_o_bug_ficar_entregue(self, monkeypatch):
        sb, pedido_id, _ = _pedido_esperando_o_bug(monkeypatch)

        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": "Este Pedido espera a Demanda 57 ser entregue."}
        assert _pedido(sb, pedido_id)["estado"] == "aberta"

    @pytest.mark.parametrize("etapa", ["entregue", "em_producao"])
    def test_com_o_bug_entregue_o_concluir_libera(self, monkeypatch, etapa):
        sb, pedido_id, bug_id = _pedido_esperando_o_bug(monkeypatch)
        _demanda(sb, bug_id)["etapa"] = etapa

        assert _cartao_na_lista(sb, pedido_id, monkeypatch)["espera_demanda"] is None
        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        assert _pedido(sb, pedido_id)["estado"] == "concluida"

    def test_o_bug_em_desenvolvimento_continua_segurando(self, monkeypatch):
        sb, pedido_id, bug_id = _pedido_esperando_o_bug(monkeypatch)
        _demanda(sb, bug_id)["etapa"] = "em_desenvolvimento"

        assert _concluir(sb, DIRETORA, pedido_id, monkeypatch).status_code == 422

    def test_o_bug_apagado_nao_segura_o_pedido_para_sempre(self, monkeypatch):
        sb, pedido_id, bug_id = _pedido_esperando_o_bug(monkeypatch)
        _demanda(sb, bug_id)["apagada_em"] = "2026-11-23T12:00:00+00:00"

        assert _concluir(sb, DIRETORA, pedido_id, monkeypatch).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 3b. Um bug por vez: o segundo não troca a espera do primeiro
# ═══════════════════════════════════════════════════════════════════════════


class TestUmBugPorVez:
    def test_o_pedido_que_espera_um_bug_recusa_o_segundo_achei_um_problema(self, monkeypatch):
        sb, pedido_id, bug_id = _pedido_esperando_o_bug(monkeypatch)
        cliente, _ = _na_tela(sb, monkeypatch)
        antes = len(sb.tabelas["tecnologia_demandas"])

        resposta = _achei_um_problema(cliente, monkeypatch, pedido_id)

        assert resposta.status_code == 422
        assert resposta.json() == {
            "detail": "Este Pedido já espera a Demanda 57. O próximo problema entra depois que ela for entregue."
        }
        assert len(sb.tabelas["tecnologia_demandas"]) == antes
        assert _pedido(sb, pedido_id)["espera_demanda_id"] == bug_id

    def test_com_o_bug_entregue_o_pedido_aceita_o_proximo_problema(self, monkeypatch):
        sb, pedido_id, bug_id = _pedido_esperando_o_bug(monkeypatch)
        _demanda(sb, bug_id)["etapa"] = "entregue"
        cliente, _ = _na_tela(sb, monkeypatch)

        assert _achei_um_problema(cliente, monkeypatch, pedido_id).status_code == 201

    def test_o_segundo_bug_aberto_em_paralelo_nao_ganha_card_nem_troca_a_espera(self, monkeypatch):
        sb, pedido_id = _pedido_de_implantacao()
        cliente, _, primeiro = _bug_ate_o_resumo(sb, monkeypatch, pedido_id)
        # A segunda montagem instala o GitHub dublado que as duas rotas usam.
        _, gh, segundo = _bug_ate_o_resumo(sb, monkeypatch, pedido_id)
        assert cliente.post(f"{CHAT}/{primeiro}/criar-card").status_code == 200
        _demanda(sb, primeiro)["numero"] = NUMERO_DO_BUG

        resposta = cliente.post(f"{CHAT}/{segundo}/criar-card")

        assert resposta.status_code == 422
        assert resposta.json() == {
            "detail": "Este Pedido já espera a Demanda 57. O próximo problema entra depois que ela for entregue."
        }
        assert _pedido(sb, pedido_id)["espera_demanda_id"] == primeiro
        assert _demanda(sb, segundo).get("demanda_origem_id") is None
        assert len(gh.criadas) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. O PRD de origem continua fechado
# ═══════════════════════════════════════════════════════════════════════════


class TestOPrdNaoReabre:
    def test_o_bug_com_card_nao_toca_no_prd_de_origem(self, monkeypatch, github):  # noqa: F811
        sb, pedido_id = _pedido_de_implantacao()
        origem = _demanda(sb, DEMANDA)
        antes = dict(origem)
        github["chamadas"].clear()
        cliente, _, bug_id = _bug_ate_o_resumo(sb, monkeypatch, pedido_id)

        assert cliente.post(f"{CHAT}/{bug_id}/criar-card").status_code == 200

        # Nenhuma chamada ao GitHub mexe no PRD, e a Demanda da entrega fica como estava.
        assert [chamada for chamada in github["chamadas"] if f"/issues/{PRD}" in chamada[1]] == []
        assert _demanda(sb, DEMANDA) == antes
        assert _pedido(sb, pedido_id)["estado"] == "aberta"


# ═══════════════════════════════════════════════════════════════════════════
# 5. O kit de conhecimento do Assistente
# ═══════════════════════════════════════════════════════════════════════════


class TestKit:
    @pytest.mark.parametrize(
        "frase",
        [
            "Achei um problema",
            "Espera a Demanda",
            "o Concluir fica bloqueado até a Demanda do bug ser entregue",
            "a entrega não é reaberta",
            "refaz só o passo que falhou",
        ],
    )
    def test_o_kit_diz_o_que_o_achei_um_problema_faz(self, frase):
        assert frase in _texto_do_kit(ARQUIVO_DA_ABA)
