"""A Implantação no card da Demanda (issue #2209, PRD #2205, ADR 0111, decisão 5).

A leitura da Demanda traz os Pedidos de implantação dela (o título, o
Destinatário, a situação e a espera) e a contagem dos feitos sobre o total. É
o que o Documento do card desenha na seção Implantação e o Quadro, no selo
"Implantação X de Y". Demanda sem Pedido de implantação não muda: a leitura
vem com a Implantação nula. O Pedido cancelado não conta.

A Etapa continua sendo a do GitHub: o PRD fechado leva a Demanda a Em
produção mesmo com a implantação aberta.

Pela ROTA de verdade (a ponte cria, a lista do chat lê), com o Supabase em
memória e o transporte do GitHub dublado.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_kit_conhecimento import ARQUIVO_DA_ABA  # noqa: E402
from test_kit_conhecimento import _texto as _texto_do_kit  # noqa: E402
from test_tecnologia_passo_a_passo_da_vitta import _concluir, _marcar, emails  # noqa: E402, F401
from test_tecnologia_pedido_de_implantacao import IMPLANTACAO, PASSOS, _criar, github  # noqa: E402, F401
from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    DEMANDA,
    DIRETORA,
    PEDRO,
    TABELA,
    _a_demanda,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
)
from test_tecnologia_vinculo import _integracao_configurada, _TableQuery  # noqa: E402, F401

from app.services import tecnologia_perguntas  # noqa: E402

# O "Minhas" corta pelo autor desde a issue #2265: a Diretora le o card da
# Vitta no Todas.
LISTA = "/api/admin/tecnologia/chat?filtro=todas"

TESTE = "testar o anonimato do Canal de Conduta"
ABERTURA = "abrir o Canal de Conduta para todos"


def _a_demanda_na_lista(sb, monkeypatch) -> dict:
    resposta = _tela(sb, DIRETORA, monkeypatch).get(LISTA)
    assert resposta.status_code == 200, resposta.text
    [demanda] = [d for d in resposta.json() if d["id"] == DEMANDA]
    return demanda


def _dois_pedidos():
    """O teste, para a Diretora, e a abertura, para o Pedro, nessa ordem."""
    ponte, sb = _ponte()
    teste = _criar(ponte)
    abertura = _criar(ponte, assunto=ABERTURA, destinatario_id=PEDRO["id"], card_numero=1854)
    assert (teste.status_code, abertura.status_code) == (201, 201), (teste.text, abertura.text)
    return ponte, sb, teste.json()["id"], abertura.json()["id"]


def _concluir_o_pedido(sb, pedido_id, monkeypatch):
    for passo in range(len(PASSOS)):
        assert _marcar(sb, DIRETORA, pedido_id, monkeypatch, passo).status_code == 200
    assert _concluir(sb, DIRETORA, pedido_id, monkeypatch).status_code == 200


class TestALeituraDaDemanda:
    def test_a_lista_traz_cada_pedido_de_implantacao_com_o_destinatario_e_a_situacao(self, monkeypatch):
        _, sb, teste, _ = _dois_pedidos()
        _concluir_o_pedido(sb, teste, monkeypatch)

        demanda = _a_demanda_na_lista(sb, monkeypatch)

        assert demanda["implantacao"] == {
            "feitos": 1,
            "total": 2,
            "pedidos": [
                {"titulo": TESTE, "destinatario": "Diretora Clínica", "situacao": "feito", "espera": None},
                {"titulo": ABERTURA, "destinatario": "Pedro Rezende", "situacao": "aberto", "espera": None},
            ],
        }

    def test_o_pedido_cancelado_nao_conta(self, monkeypatch):
        ponte, sb, _, abertura = _dois_pedidos()
        cancelado = ponte.post(
            f"/api/automacao/tecnologia/perguntas/{abertura}/cancelar",
            json={"github_login": "pedrorezendefig", "motivo": "A abertura vai ser feita em outra entrega."},
            headers={"X-API-Key": CHAVE},
        )
        assert cancelado.status_code == 200, cancelado.text

        demanda = _a_demanda_na_lista(sb, monkeypatch)

        assert (demanda["implantacao"]["feitos"], demanda["implantacao"]["total"]) == (0, 1)
        assert [p["titulo"] for p in demanda["implantacao"]["pedidos"]] == [TESTE]

    def test_a_demanda_sem_pedido_de_implantacao_vem_sem_implantacao(self, monkeypatch):
        """O Passo a passo e a Pergunta não entram na Implantação."""
        ponte, sb = _ponte()
        passo = _criar(ponte, tipo="passo_a_passo")
        assert passo.status_code == 201, passo.text

        demanda = _a_demanda_na_lista(sb, monkeypatch)

        assert demanda["implantacao"] is None

    def test_a_demanda_com_o_prd_fechado_e_implantacao_aberta_fica_em_producao(self, monkeypatch):
        _, sb, _, _ = _dois_pedidos()
        [linha] = sb.tabelas["tecnologia_demandas"]
        linha.update({"etapa": "em_producao", "em_producao_em": "2026-11-22T12:00:00Z"})

        demanda = _a_demanda_na_lista(sb, monkeypatch)

        assert demanda["etapa"] == "em_producao"
        assert (demanda["implantacao"]["feitos"], demanda["implantacao"]["total"]) == (0, 2)
        assert {p["situacao"] for p in demanda["implantacao"]["pedidos"]} == {"aberto"}
        assert all(p["estado"] == "aberta" for p in sb.tabelas[TABELA])

    def test_a_lista_com_muitas_demandas_le_a_implantacao_em_lotes(self, monkeypatch):
        """O cliente do PostgREST poe o `in_` na querystring: algumas centenas
        de ids estouram o header do proxy e a lista do chat cairia em 500 para
        todos. A leitura vai em lotes, e a Demanda do lote do meio ainda traz a
        Implantacao dela."""
        ponte, sb = _ponte()
        assert _criar(ponte).status_code == 201
        outras = [{**_a_demanda(), "id": f"demanda-{i:04d}"} for i in range(250)]
        # A Demanda com o pedido no meio: nem no primeiro lote nem no ultimo.
        sb.tabelas["tecnologia_demandas"][:0] = outras[:125]
        sb.tabelas["tecnologia_demandas"].extend(outras[125:])
        tamanhos: list[int] = []
        in_original = _TableQuery.in_

        def in_que_mede(self, coluna, valores):
            if self._nome == TABELA and coluna == "demanda_id":
                tamanhos.append(len(list(valores)))
            return in_original(self, coluna, valores)

        monkeypatch.setattr(_TableQuery, "in_", in_que_mede)

        demanda = _a_demanda_na_lista(sb, monkeypatch)

        assert tamanhos and max(tamanhos) <= tecnologia_perguntas.LOTE_DE_IDS
        assert sum(tamanhos) == 251
        assert (demanda["implantacao"]["feitos"], demanda["implantacao"]["total"]) == (0, 1)
        assert [p["titulo"] for p in demanda["implantacao"]["pedidos"]] == [TESTE]


class TestKit:
    """O texto do Produto Tecnologia é o que o Assistente lê para responder
    ao diretor: ele diz o comportamento novo."""

    @pytest.fixture
    def texto(self) -> str:
        return _texto_do_kit(ARQUIVO_DA_ABA)

    @pytest.mark.parametrize(
        "frase",
        [
            "a parte Implantação",
            "Implantação 1 de 3",
            "some quando todos estão concluídos",
            "a entrega fica Em produção mesmo com a implantação por fazer",
        ],
    )
    def test_o_kit_diz_a_secao_implantacao_e_o_selo_no_quadro(self, texto, frase):
        assert frase in texto
