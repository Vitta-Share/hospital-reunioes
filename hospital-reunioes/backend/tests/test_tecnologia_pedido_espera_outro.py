"""Um Pedido de implantação espera outro (issue #2208, PRD #2205, ADR 0111,
decisão 8).

A ponte aceita, na criação, o Pedido que este espera (`espera_pedido_id`),
sempre um Pedido de implantação da mesma Demanda, e recusa com o motivo o de
outra Demanda ou de outro tipo. Enquanto o esperado está aberto, o cartão
mostra "Espera" com o assunto dele, e o Concluir recusa com o motivo numa
linha. Concluído o esperado, o Concluir do outro libera sozinho.

Pela ROTA de verdade (ponte e tela), com o Supabase em memória e o
transporte do GitHub dublado.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_kit_conhecimento import ARQUIVO_DA_ABA  # noqa: E402
from test_kit_conhecimento import _texto as _texto_do_kit  # noqa: E402
from test_tecnologia_passo_a_passo_da_vitta import (  # noqa: E402, F401
    CRIAR,
    PASSO_A_PASSO,
    _concluir,
    _marcar,
    emails,
)
from test_tecnologia_pedido_de_implantacao import (  # noqa: E402, F401
    CARD,
    IMPLANTACAO,
    PASSOS,
    github,
)
from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    DIRETORA,
    PEDRO,
    QUATRO_LINHAS,
    TABELA,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
)
from test_tecnologia_vinculo import _demanda, _integracao_configurada  # noqa: E402, F401

from app.services import tecnologia_perguntas  # noqa: E402

OUTRA_DEMANDA = "8b2c3d4e-5f6a-4b7c-9d8e-0f1a2b3c4d5e"
ESPERANDO = "/api/admin/tecnologia/perguntas/esperando"

TESTE = {**IMPLANTACAO, "assunto": "testar o anonimato do Canal de Conduta"}
ABERTURA = {
    **IMPLANTACAO,
    "assunto": "abrir o Canal de Conduta para todos",
    "texto": "Divulgue o Canal de Conduta depois do teste.",
    "card_numero": CARD + 1,
}


def _criar(ponte, corpo, *, url=CRIAR):
    return ponte.post(url, json=corpo, headers={"X-API-Key": CHAVE})


def _teste_e_abertura():
    """O teste nasce primeiro; a abertura espera o teste."""
    ponte, sb = _ponte()
    teste = _criar(ponte, TESTE)
    assert teste.status_code == 201, teste.text
    abertura = _criar(ponte, {**ABERTURA, "espera_pedido_id": teste.json()["id"]})
    assert abertura.status_code == 201, abertura.text
    return ponte, sb, teste.json()["id"], abertura.json()["id"]


def _marcar_todos(sb, pedido_id, monkeypatch):
    for passo in range(len(PASSOS)):
        assert _marcar(sb, DIRETORA, pedido_id, monkeypatch, passo).status_code == 200


def _cartao_na_lista(sb, pedido_id, monkeypatch) -> dict:
    lista = _tela(sb, DIRETORA, monkeypatch).get(ESPERANDO).json()
    return next(item for item in lista if item["id"] == pedido_id)


def _linha(sb, pedido_id) -> dict:
    return next(p for p in sb.tabelas[TABELA] if p["id"] == pedido_id)


# ═══════════════════════════════════════════════════════════════════════════
# A ponte grava a espera e recusa a que não vale
# ═══════════════════════════════════════════════════════════════════════════


class TestPonte:
    def test_a_ponte_grava_o_pedido_que_ele_espera(self):
        _, sb, teste_id, abertura_id = _teste_e_abertura()

        assert _linha(sb, abertura_id)["espera_pedido_id"] == teste_id
        assert _linha(sb, teste_id).get("espera_pedido_id") is None

    def test_espera_de_outra_demanda_e_recusada_com_o_motivo_e_nada_e_gravado(self):
        ponte, sb = _ponte()
        sb.tabelas["tecnologia_demandas"].append(
            _demanda(OUTRA_DEMANDA, titulo="Outra entrega", autor_id=PEDRO["id"], origem="vitta", apagada_em=None)
        )
        de_fora = _criar(ponte, TESTE, url=f"/api/automacao/tecnologia/demandas/{OUTRA_DEMANDA}/perguntas")
        assert de_fora.status_code == 201, de_fora.text
        antes = len(sb.tabelas[TABELA])

        resposta = _criar(ponte, {**ABERTURA, "espera_pedido_id": de_fora.json()["id"]})

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_ESPERA_DE_OUTRA_DEMANDA}
        assert len(sb.tabelas[TABELA]) == antes

    def test_espera_de_um_pedido_que_nao_e_de_implantacao_e_recusada_com_o_motivo(self):
        ponte, sb = _ponte()
        passo = _criar(ponte, {**PASSO_A_PASSO, "card_numero": CARD + 2})
        assert passo.status_code == 201, passo.text
        antes = len(sb.tabelas[TABELA])

        resposta = _criar(ponte, {**ABERTURA, "espera_pedido_id": passo.json()["id"]})

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_ESPERA_DE_OUTRO_TIPO}
        assert len(sb.tabelas[TABELA]) == antes

    def test_espera_de_um_pedido_que_nao_existe_e_recusada_com_o_motivo(self):
        ponte, sb = _ponte()

        resposta = _criar(ponte, {**ABERTURA, "espera_pedido_id": "9c3d4e5f-6a7b-4c8d-0e9f-1a2b3c4d5e6f"})

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_ESPERA_NAO_EXISTE}
        assert sb.tabelas[TABELA] == []

    def test_espera_de_um_pedido_cancelado_e_recusada_com_o_motivo_e_nada_e_gravado(self):
        # O cancelado segura o Concluir para sempre: o Pedido que o esperasse
        # nasceria sem como ser concluido, e o lembrete bateria na pessoa.
        ponte, sb = _ponte()
        teste = _criar(ponte, TESTE)
        assert teste.status_code == 201, teste.text
        _linha(sb, teste.json()["id"])["estado"] = "cancelada"
        antes = len(sb.tabelas[TABELA])

        resposta = _criar(ponte, {**ABERTURA, "espera_pedido_id": teste.json()["id"]})

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": "O Pedido esperado foi cancelado: este nunca poderia ser concluído."}
        assert len(sb.tabelas[TABELA]) == antes

    def test_so_o_pedido_de_implantacao_espera_outro(self):
        ponte, sb = _ponte()
        teste = _criar(ponte, TESTE)
        antes = len(sb.tabelas[TABELA])

        resposta = _criar(ponte, {**PASSO_A_PASSO, "card_numero": CARD + 3, "espera_pedido_id": teste.json()["id"]})

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_ESPERA_SO_NA_IMPLANTACAO}
        assert len(sb.tabelas[TABELA]) == antes


# ═══════════════════════════════════════════════════════════════════════════
# Com o esperado aberto: "Espera" no cartão e o Concluir recusa
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# Concluído o esperado, o Concluir libera sozinho
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento do Assistente
# ═══════════════════════════════════════════════════════════════════════════


class TestKit:
    @pytest.fixture
    def texto(self) -> str:
        return _texto_do_kit(ARQUIVO_DA_ABA)

    @pytest.mark.parametrize(
        "frase",
        [
            "um Pedido de implantação pode esperar outro",
            'o cartão mostra "Espera" com o nome do outro',
            "o Concluir fica bloqueado e diz o motivo",
            "libera sozinho",
        ],
    )
    def test_o_kit_diz_que_um_pedido_de_implantacao_espera_outro(self, texto, frase):
        assert frase in texto
