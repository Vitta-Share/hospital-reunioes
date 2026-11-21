"""As Rotinas no Início (issue #1944, PRD #1932; ADR 0104 e ADR 0098, decisão 9).

O trilho mostra as Rotinas do ciclo corrente de quem é o responsável, com
quantas já têm Verificação. Realizada é um clique na Minha Fila; Não realizada
leva à tela da Rotina, que pede a Anotação. O ciclo que fechou sem marca fica
em Passou do prazo e ainda se marca. A Rotina a revisar (a revisão de 90 dias
do Facilitador, decisão 72 da #1757) entra na fila dele, e Manter é um clique.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# O banco de mentira das Rotinas (issue #1874) e os fixtures dele.
from test_rotina_verificacao import (  # noqa: E402, F401
    ADMIN,
    ANA,
    OUTRO,
    PEDRO,
    RT1,
    D,
    _sb_com_rotina,
    cliente_das_rotinas,
    fila,
    hoje,
)

RT2 = "00000000-0000-0000-0000-0000000000a2"


def _com_duas_rotinas_da_ana():
    """RT1 semanal (desde 23/11) e RT2 quinzenal (desde 16/11), as duas da Ana."""
    sb = _sb_com_rotina()
    sb.rotinas.append(
        {
            **sb.rotinas[0],
            "id": RT2,
            "quadro_pos": 2,
            "descricao": "Conferir o carrinho de parada",
            "frequencia": "QUINZENAL",
            "comeca_em": "2026-11-16",
        }
    )
    return sb


def _do_ciclo(resposta) -> list[tuple]:
    return [
        (r.titulo, r.ciclo_inicio.isoformat(), r.ciclo_fim.isoformat(), r.verificacao)
        for r in resposta.rotinas_do_ciclo
    ]


# ─── 1. O trilho: as Rotinas do ciclo corrente e o progresso ─────────────────


def test_o_trilho_mostra_as_rotinas_do_ciclo_com_quais_ja_tem_verificacao(fila, cliente_das_rotinas, hoje):  # noqa: F811
    hoje["valor"] = D("2026-11-25")
    sb = _com_duas_rotinas_da_ana()
    assert cliente_das_rotinas(sb, ANA).post(f"/api/rotinas/{RT1}/ciclos/2026-11-23/realizada").status_code == 201

    resposta = fila(sb, ANA, "2026-11-25")

    assert sorted(_do_ciclo(resposta)) == [
        ("Conferir o carrinho de parada", "2026-11-16", "2026-11-30", None),
        ("Reunir a equipe", "2026-11-23", "2026-11-29", "REALIZADA"),
    ]
    [rotina] = [r for r in resposta.rotinas_do_ciclo if r.id == RT1]
    assert rotina.destino == f"/rotinas#rotina-{RT1}"
