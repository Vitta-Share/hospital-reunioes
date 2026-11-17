"""As Partes do Documento do card com número, o que trava e Onda (issue #1902,
PRD #1901, ADR 0100).

A foto da Demanda guarda, em cada parte, as bloqueadoras lidas do GitHub
(`blocked_by`); um módulo puro calcula a Onda de cada parte; a API devolve o
número da raiz e de cada parte, a Onda e as bloqueadoras abertas para todos que
veem a Demanda; e o kit diz o comportamento novo.
"""

from __future__ import annotations

import pytest

from app.services.tecnologia_ondas import ondas_das_partes


def _parte(numero: int, *bloqueadoras: int | tuple[int, bool]) -> dict:
    """A parte com as bloqueadoras: um número é bloqueadora da mesma Demanda, e
    `(numero, False)` é bloqueadora de outro pedido."""
    lista = []
    for b in bloqueadoras:
        numero_b, da_demanda = b if isinstance(b, tuple) else (b, True)
        lista.append({"numero": numero_b, "estado": "open", "da_demanda": da_demanda})
    return {"numero": numero, "bloqueadoras": lista}


class TestAOndaDeCadaParte:
    @pytest.mark.parametrize(
        ("partes", "ondas"),
        [
            pytest.param([_parte(10)], [1], id="uma-parte-so"),
            pytest.param([_parte(10), _parte(11)], [1, 1], id="sem-dependencia-tudo-na-onda-1"),
            pytest.param([_parte(10), _parte(11, 10)], [1, 2], id="espera-uma-fica-uma-onda-depois"),
            pytest.param(
                [_parte(10), _parte(11, 10), _parte(12, 11), _parte(13, 10)],
                [1, 2, 3, 2],
                id="cadeia-e-irma",
            ),
            pytest.param(
                [_parte(10), _parte(11), _parte(12, 10, 11), _parte(13, 12, 10)],
                [1, 1, 2, 3],
                id="vale-a-maior-onda-das-esperadas",
            ),
            pytest.param([_parte(10), _parte(11, (900, False))], [1, 1], id="bloqueadora-de-outro-pedido-nao-conta"),
            pytest.param(
                [_parte(10), _parte(11, (10, False))],
                [1, 1],
                id="outro-pedido-com-o-mesmo-numero-de-uma-parte-nao-conta",
            ),
            pytest.param([_parte(10, 11), _parte(11, 10)], [1, 1], id="ciclo-fica-na-onda-1"),
            pytest.param([_parte(10, 10)], [1], id="parte-que-espera-a-si-mesma-fica-na-onda-1"),
            pytest.param(
                [_parte(10, 11), _parte(11, 10), _parte(12, 11)],
                [1, 1, 2],
                id="quem-espera-o-ciclo-fica-uma-onda-depois",
            ),
            pytest.param([_parte(12, 11), _parte(11, 10), _parte(10)], [3, 2, 1], id="a-ordem-da-lista-nao-importa"),
            pytest.param([{"numero": 10}, _parte(11, 10)], [1, 2], id="parte-sem-bloqueadoras-lidas"),
        ],
    )
    def test_a_onda_segue_as_dependencias_dentro_da_demanda(self, partes, ondas):
        assert ondas_das_partes(partes) == ondas

    def test_o_bloqueio_ja_resolvido_continua_contando(self):
        """A sequência não muda quando uma parte fecha (ADR 0100, decisão 3)."""
        partes = [
            {"numero": 10, "bloqueadoras": []},
            {"numero": 11, "bloqueadoras": [{"numero": 10, "estado": "closed", "da_demanda": True}]},
        ]

        assert ondas_das_partes(partes) == [1, 2]
