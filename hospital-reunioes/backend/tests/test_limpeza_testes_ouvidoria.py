"""A limpeza dos testes da Ouvidoria (issue #1962, PRD #1913, ADR 0102).

O script de `scripts/oneshot/limpeza_testes_ouvidoria.py` confere a janela,
lista o que sai, tira os arquivos do bucket e gera o SQL avulso que uma pessoa
roda à mão. A escolha do que sai é uma função pura; o resto passa por um
cliente falso do PostgREST e um bucket falso. Nada aqui fala com banco de
verdade.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.oneshot import limpeza_testes_ouvidoria as limpeza  # noqa: E402
from scripts.oneshot.limpeza_testes_ouvidoria import Avaliacao, Caso, escolher  # noqa: E402

# Os dois limites da janela, escritos à mão a partir da issue: 19/10/2026 à 0h
# de Brasília e 17/11/2026 às 18h31min43s de Brasília (21:31:43 UTC).
INICIO = datetime(2026, 10, 19, 3, 0, 0, tzinfo=UTC)
FIM = datetime(2026, 11, 17, 21, 31, 43, tzinfo=UTC)
MEIO = datetime(2026, 11, 1, 15, 0, 0, tzinfo=UTC)
UM_MICRO = timedelta(microseconds=1)


def _avaliacoes(n: int, quando: datetime = MEIO) -> list[Avaliacao]:
    return [Avaliacao(id=f"av-{i}", criada_em=quando) for i in range(n)]


def _caso(protocolo: str = "2026-0101", **campos) -> Caso:
    base = {
        "id": f"id-{protocolo}",
        "protocolo": protocolo,
        "canal": "qr",
        "t0": MEIO,
        "estado": "em_classificacao",
        "anonimo": False,
    }
    base.update(campos)
    return Caso(**base)


class TestJanela:
    def test_avaliacao_no_primeiro_instante_da_janela_entra_e_a_de_um_instante_antes_fica(self):
        escolha = escolher(
            [Avaliacao("dentro", INICIO), Avaliacao("antes", INICIO - UM_MICRO)],
            [],
        )
        assert [a.id for a in escolha.avaliacoes] == ["dentro"]

    def test_avaliacao_no_ultimo_segundo_da_janela_entra_e_a_do_segundo_seguinte_fica(self):
        escolha = escolher(
            [
                Avaliacao("no_fim", FIM),
                Avaliacao("fim_do_segundo", FIM + timedelta(microseconds=999_999)),
                Avaliacao("depois", FIM + timedelta(seconds=1)),
            ],
            [],
        )
        assert [a.id for a in escolha.avaliacoes] == ["no_fim", "fim_do_segundo"]

    def test_caso_conta_pelo_t0_nos_dois_limites(self):
        casos = [
            _caso("2026-0001", t0=INICIO - UM_MICRO),
            _caso("2026-0002", t0=INICIO),
            _caso("2026-0003", t0=FIM),
            _caso("2026-0004", t0=FIM + timedelta(seconds=1)),
        ]
        escolha = escolher(_avaliacoes(5), casos)
        assert [c.protocolo for c in escolha.saem] == ["2026-0002", "2026-0003"]
