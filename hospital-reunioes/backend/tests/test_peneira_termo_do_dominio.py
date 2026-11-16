"""A peneira de dado pessoal nao come termo do dominio (issue #1813).

A Demanda #1786 chegou ao GitHub com o nome do modulo, do colegiado e do
fornecedor trocados por `[NOME]`, a comecar pelo titulo ("[NOME] para quem
trabalha no hospital"). Dois defeitos diferentes:

* a troca cortava palavra no meio: "ClickSign" saiu "Click[NOME]" e
  "[NOME]Sign", porque a sequencia com cara de nome comecava ou terminava
  dentro de uma palavra;
* termo composto do dominio em maiuscula inicial ("Canal de Conduta",
  "Nucleo de Seguranca do Paciente") tem o desenho de nome de gente, e a
  camada do desenho nao tinha como saber que nao e.

Os trechos da #1786 abaixo foram reconstruidos a partir da issue publicada
(o texto original vive so na Demanda, dentro do app). Nome de pessoa continua
virando `[NOME]`: os testes de `test_ouvidoria_pseudonimizacao.py` seguem
como estao.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.ouvidoria_pseudonimizacao import pseudonimizar  # noqa: E402
from app.services.tecnologia_vinculo import texto_do_diretor, titulo_da_issue  # noqa: E402
from scripts.gerar_termos_do_dominio import termos_do_dominio  # noqa: E402

_ARQUIVO_DE_TERMOS = (
    pathlib.Path(__file__).resolve().parents[1] / "app" / "services" / "dados" / "termos_do_dominio.txt"
)
_TERMOS = [
    linha.strip()
    for linha in _ARQUIVO_DE_TERMOS.read_text(encoding="utf-8").splitlines()
    if linha.strip() and not linha.startswith("#")
]


class TestTrocaSoEmPalavraInteira:
    def test_fornecedor_antes_de_palavra_capitalizada_nao_perde_o_fim(self):
        assert pseudonimizar("integração ClickSign API (Envelope e webhook)") == (
            "integração ClickSign API (Envelope e webhook)"
        )

    def test_fornecedor_depois_de_palavra_capitalizada_nao_perde_o_comeco(self):
        assert pseudonimizar("Mandar o Envelope ClickSign agora") == "Mandar o Envelope ClickSign agora"


class TestNomeComApostrofoNoMeio:
    """A guarda de palavra inteira trata o apostrofo como parte da palavra.
    Nome com apostrofo no meio tem que caber inteiro no desenho, senao a
    guarda recusa a sequencia e o nome sai todo (review do PR #1895)."""

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Falei com a Maria Sant'Anna ontem.", "Falei com a [NOME] ontem."),
            ("A paciente Maria Sant'Anna Silva reclamou.", "A paciente [NOME] reclamou."),
            ("Manuela d'Ávila Souza foi atendida.", "[NOME] foi atendida."),
            ("Falei com a Maria Sant’Ana ontem.", "Falei com a [NOME] ontem."),
        ],
    )
    def test_nome_com_apostrofo_no_meio_vira_marcador(self, texto, esperado):
        assert pseudonimizar(texto) == esperado


class TestTermoDoDominioSaiInteiro:
    """Nome de modulo, colegiado ou setor do CONTEXT.md e do catalogo de
    Produtos da aba Tecnologia sai inteiro, mesmo com desenho de nome."""

    def test_titulo_da_1786_sai_com_o_nome_do_modulo(self):
        assert pseudonimizar("Canal de Conduta para quem trabalha no hospital") == (
            "Canal de Conduta para quem trabalha no hospital"
        )

    def test_colegiado_e_setor_saem_inteiros_no_corpo_da_1786(self):
        trecho = "O Núcleo de Segurança do Paciente recebe só uma nota do Comitê de Conduta."
        assert pseudonimizar(trecho) == trecho

    def test_quem_pede_o_afastamento_na_1786_sai_inteiro(self):
        trecho = "O GRupo Especial solicita formalmente à Coordenação do Comitê o pedido de afastamento."
        assert pseudonimizar(trecho) == trecho

    def test_termo_digitado_sem_acento_tambem_sai_inteiro(self):
        trecho = "O Nucleo de Seguranca do Paciente e o Comite de Conduta."
        assert pseudonimizar(trecho) == trecho

    def test_produto_do_catalogo_da_tecnologia_sai_inteiro(self):
        trecho = "Integração Ana x MV parou de mandar a ficha."
        assert pseudonimizar(trecho) == trecho

    def test_termo_em_caixa_alta_num_relato_em_caixa_mista_sai_inteiro(self):
        trecho = "Abri o caso no CANAL DE CONDUTA ontem."
        assert pseudonimizar(trecho) == trecho


class TestNomeDePessoaContinuaSaindo:
    def test_pessoa_ao_lado_do_colegiado_vira_marcador(self):
        assert pseudonimizar("Só o Pedro Rezende cadastra o Comitê de Conduta.") == (
            "Só o [NOME] cadastra o Comitê de Conduta."
        )

    def test_pessoa_colada_no_modulo_vira_marcador_e_o_modulo_fica(self):
        assert pseudonimizar("relato de Maria Souza do Canal de Conduta") == "relato de [NOME] do Canal de Conduta"

    def test_pessoa_em_minusculas_colada_no_termo_vira_marcador(self):
        assert pseudonimizar("maria souza comite de conduta") == "[NOME] comite de conduta"

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Abri o Retrato da Ana Souza ontem.", "Abri o [NOME] ontem."),
            ("A API da Ana Maria caiu.", "A [NOME] caiu."),
            ("Abri o Retrato da Ana Kowalski ontem.", "Abri o [NOME] ontem."),
        ],
    )
    def test_termo_que_termina_em_prenome_nao_rouba_o_prenome_da_pessoa(self, texto, esperado):
        """ "Retrato da Ana" e "API da Ana" terminam num prenome. Com uma Ana
        de sobrenome logo depois, guardar o termo deixava o nome inteiro no
        texto (review do PR #1895): ali a pessoa vence o termo."""
        assert pseudonimizar(texto) == esperado

    def test_termo_que_termina_em_prenome_sai_inteiro_sem_pessoa_ao_lado(self):
        trecho = "O Retrato da Ana mostra a sala."
        assert pseudonimizar(trecho) == trecho

    def test_termo_em_minusculas_nao_e_guardado_e_a_base_ve_a_pessoa(self):
        """O termo só é guardado com maiúscula inicial no texto. Em minúsculas
        quem protege o nome é a base, e o termo guardado a cegaria."""
        assert pseudonimizar("o api da ana maria caiu") == "o api da [NOME] caiu"


class TestRegressaoDaDemanda1786:
    """O titulo e tres trechos do corpo da #1786, pelas funcoes que montam a
    issue publica (`titulo_da_issue` e `texto_do_diretor`)."""

    def test_titulo_da_issue_sai_com_o_nome_do_modulo(self):
        assert titulo_da_issue("Canal de Conduta para quem trabalha no hospital") == (
            "Canal de Conduta para quem trabalha no hospital"
        )

    @pytest.mark.parametrize(
        "trecho",
        [
            "Um módulo novo, Canal de Conduta, com dois lados.",
            "Dossiê do ouvidor (botão Sinalizar ao Comitê de Conduta), integração ClickSign API (Envelope e webhook).",
            "O GRupo Especial solicita formalmente à Coordenação do Comitê o pedido de afastamento, "
            "e o Núcleo de Segurança do Paciente recebe só uma nota.",
        ],
    )
    def test_trecho_do_corpo_sai_sem_marcador(self, trecho):
        assert texto_do_diretor(trecho) == trecho

    def test_pessoa_no_corpo_continua_virando_marcador(self):
        assert texto_do_diretor("Só o Pedro Rezende cadastra o Comitê de Conduta.") == (
            "Só o [NOME] cadastra o Comitê de Conduta."
        )


class TestListaDeTermos:
    @pytest.mark.parametrize("termo", _TERMOS)
    def test_todo_termo_da_lista_sai_inteiro_numa_frase(self, termo):
        frase = f"Hoje {termo} foi citado."
        assert pseudonimizar(frase) == frase

    def test_gerador_le_verbete_secao_complemento_e_produto(self):
        glossario = (
            "## Canal de Conduta\n\n"
            "**Coordenação (do Comitê)**:\nA coordenação.\n\n"
            "**Faixa (A a E)**:\nA faixa.\n\n"
            "**Rito**:\nO rito.\n\n"
            "**Ação, Rotina e Processo**:\nTrês coisas.\n"
        )
        sql = "INSERT INTO tecnologia_produtos (nome, ordem) VALUES\n  ('Central de Comando', 1),\n  ('Site', 2);"
        assert termos_do_dominio(glossario, [sql]) == [
            "Canal de Conduta",
            "Central de Comando",
            "Coordenação do Comitê",
        ]
