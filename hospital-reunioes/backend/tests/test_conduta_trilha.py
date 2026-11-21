"""A trilha do caso em cadeia (issue #1820, ADR 0097, decisão 9).

Cada linha carrega o código da anterior do mesmo caso, e o código de cada
linha cobre quem, quando e o quê. A conferência refaz a cadeia e aponta a
linha trocada ou a lacuna deixada por uma linha apagada. A recusa de UPDATE e
DELETE no banco está em `test_conduta_migration_banco.py`.
"""

from __future__ import annotations

import os
import sys

import pytest
from conduta_apoio import Banco

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.conduta import trilha  # noqa: E402

CASO = "caso-1"


def _tres_linhas(banco: Banco) -> list[dict]:
    trilha.registrar(banco, CASO, None, "recebimento", "caso recebido")
    trilha.registrar(banco, CASO, "P1", "leitura", "abriu o caso")
    trilha.registrar(banco, CASO, "P2", "leitura", "abriu o caso")
    return banco.tabelas["conduta_trilha"]


class TestCadeia:
    def test_cada_linha_carrega_o_codigo_da_anterior(self):
        linhas = _tres_linhas(Banco())

        assert linhas[0]["codigo_anterior"] is None
        assert linhas[1]["codigo_anterior"] == linhas[0]["codigo"]
        assert linhas[2]["codigo_anterior"] == linhas[1]["codigo"]
        assert len({linha["codigo"] for linha in linhas}) == 3

    def test_a_linha_guarda_quem_quando_e_o_que(self):
        banco = Banco()
        linha = trilha.registrar(banco, CASO, "P1", "leitura", "abriu o caso")

        assert linha["autor_id"] == "P1"
        assert linha["acao"] == "leitura"
        assert linha["detalhe"] == "abriu o caso"
        assert linha["registrado_em"]

    def test_cada_caso_tem_a_propria_cadeia(self):
        banco = Banco()
        _tres_linhas(banco)
        primeira_do_outro = trilha.registrar(banco, "caso-2", "P1", "leitura", "abriu o caso")

        assert primeira_do_outro["codigo_anterior"] is None

    def test_a_gravacao_recusada_pela_cadeia_e_refeita(self):
        """Duas gravações ao mesmo tempo: o banco recusa a segunda, e o serviço
        lê a última de novo e refaz."""
        banco = Banco()
        banco.falhas_da_trilha = 1

        trilha.registrar(banco, CASO, "P1", "leitura", "abriu o caso")

        assert len(banco.tabelas["conduta_trilha"]) == 1


class TestConferencia:
    def test_trilha_intacta_nao_tem_linha_adulterada(self):
        assert trilha.linhas_adulteradas(_tres_linhas(Banco())) == []

    @pytest.mark.parametrize("campo, valor", [("detalhe", "nada aconteceu"), ("autor_id", "P9"), ("acao", "envio")])
    def test_a_conferencia_aponta_a_linha_trocada(self, campo, valor):
        linhas = _tres_linhas(Banco())
        linhas[1][campo] = valor

        assert trilha.linhas_adulteradas(linhas) == [linhas[1]["seq"]]

    def test_a_conferencia_aponta_a_data_trocada(self):
        linhas = _tres_linhas(Banco())
        linhas[1]["registrado_em"] = "2020-01-01T00:00:00+00:00"

        assert trilha.linhas_adulteradas(linhas) == [linhas[1]["seq"]]

    def test_a_conferencia_aponta_a_linha_apagada(self):
        linhas = _tres_linhas(Banco())
        sem_a_do_meio = [linhas[0], linhas[2]]

        assert trilha.linhas_adulteradas(sem_a_do_meio) == [linhas[2]["seq"]]

    def test_a_data_lida_do_banco_em_outro_formato_confere(self):
        """O PostgREST devolve a data no fuso do banco; o código é o mesmo."""
        linhas = _tres_linhas(Banco())
        for linha in linhas:
            from datetime import datetime, timedelta, timezone

            data = datetime.fromisoformat(linha["registrado_em"]).astimezone(timezone(timedelta(hours=-3)))
            linha["registrado_em"] = data.isoformat()

        assert trilha.linhas_adulteradas(linhas) == []
