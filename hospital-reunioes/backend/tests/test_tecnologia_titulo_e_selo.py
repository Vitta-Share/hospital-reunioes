"""O selo Bug ou Melhoria na lista (issue #1438, PRD #1436).

A lista do Quadro devolve a classificacao de cada Demanda ja traduzida do
Tipo (Defeito e bug, Novo e melhoria). O titulo que o turno do chat dava a
melhoria saiu com o chat (issue #2279, ADR 0113, decisao 7).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_chat import (  # noqa: E402
    DIRETOR,
    _cenario,
    _integracao_configurada,  # noqa: F401
    _llm_em_mock,  # noqa: F401
    _reset_rate_limiter,  # noqa: F401
)
from test_tecnologia_vinculo import BASE, _demanda  # noqa: E402

CHAT = f"{BASE}/chat"


class TestClassificacaoNaLista:
    def test_a_lista_devolve_bug_para_defeito_e_melhoria_para_novo(self, monkeypatch):
        demandas = [
            _demanda("d-bug", tipo="defeito", autor_id=DIRETOR["id"], criado_em="2026-11-02T10:00:00Z"),
            _demanda("d-melhoria", tipo="novo", autor_id=DIRETOR["id"], criado_em="2026-11-01T10:00:00Z"),
            _demanda("d-antiga", tipo="consultoria", autor_id=DIRETOR["id"], criado_em="2026-10-01T10:00:00Z"),
        ]
        client, _, _ = _cenario(monkeypatch, demandas=demandas)

        resposta = client.get(CHAT)

        assert resposta.status_code == 200, resposta.text
        assert [(d["id"], d["classificacao"]) for d in resposta.json()] == [
            ("d-bug", "bug"),
            ("d-melhoria", "melhoria"),
            # O Tipo de antes do chat nao e bug nem melhoria: fica sem selo.
            ("d-antiga", None),
        ]
