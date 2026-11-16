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
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.ouvidoria_pseudonimizacao import pseudonimizar  # noqa: E402


class TestTrocaSoEmPalavraInteira:
    def test_fornecedor_colado_num_nome_nao_e_cortado_no_fim(self):
        assert pseudonimizar("integração ClickSign API (Envelope e webhook)") == (
            "integração ClickSign API (Envelope e webhook)"
        )

    def test_fornecedor_depois_de_palavra_capitalizada_nao_e_cortado_no_comeco(self):
        assert pseudonimizar("Mandar o Envelope ClickSign agora") == "Mandar o Envelope ClickSign agora"
