"""A linha de sistema de Em produção na Conversa da Demanda (issue #2117, PRD #2112).

A Demanda que chega à Etapa Em produção ganha uma linha de sistema na
Conversa, com a mesma origem `sistema` da linha do Envio aos desenvolvedores,
uma vez só: o webhook repetido e a reconciliação que chega depois não escrevem
outra.

Os dublês são os do webhook de deploy e dos avisos da entrega.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_avisos_da_entrega import _subir, emails  # noqa: E402, F401  (emails é autouse)
from test_tecnologia_webhook_deploy import (  # noqa: E402
    HISTORICO,
    _avisar,
    _corpo_do_deploy,
    _segredo_do_deploy_configurado,  # noqa: F401  (autouse)
)
from test_tecnologia_webhook_github import (  # noqa: E402
    _pr_do_app,  # noqa: F401  (autouse)
    _reset_rate_limiter,  # noqa: F401  (autouse)
    _segredo_configurado,  # noqa: F401  (autouse)
    _sem_github_de_verdade,  # noqa: F401  (autouse)
    _sem_pr_aberto,  # noqa: F401  (autouse)
)

from app.services import github_client, tecnologia_sincronizacao  # noqa: E402


def _linhas_da_conversa(sb) -> list[dict]:
    return list(sb.tabelas.get("tecnologia_conversa_da_demanda", []))


class TestLinhaDeEmProducao:
    def test_demanda_que_chega_a_em_producao_ganha_a_linha_de_sistema(self, monkeypatch):
        cliente, sb = _subir(monkeypatch)

        _avisar(cliente, _corpo_do_deploy())

        [linha] = _linhas_da_conversa(sb)
        assert linha["demanda_id"] == "D1"
        assert linha["origem"] == "sistema"
        assert linha["autor_id"] is None
        assert linha["mencoes"] == []
        assert linha["texto"] == "Entrou no ar na versão v0.169.0, em 07/10/2026."

    def test_webhook_repetido_e_reconciliacao_nao_escrevem_outra_linha(self, monkeypatch):
        cliente, sb = _subir(monkeypatch)

        _avisar(cliente, _corpo_do_deploy())
        _avisar(cliente, _corpo_do_deploy())
        monkeypatch.setattr(github_client, "ler_historico_de_deploys", lambda: HISTORICO)
        tecnologia_sincronizacao.reconciliar_em_producao(sb)

        assert len(_linhas_da_conversa(sb)) == 1

    def test_a_reconciliacao_escreve_a_linha_quando_o_webhook_nao_chegou(self, monkeypatch):
        _, sb = _subir(monkeypatch)
        monkeypatch.setattr(github_client, "ler_historico_de_deploys", lambda: HISTORICO)

        tecnologia_sincronizacao.reconciliar_em_producao(sb)
        tecnologia_sincronizacao.reconciliar_em_producao(sb)

        [linha] = _linhas_da_conversa(sb)
        assert linha["origem"] == "sistema"
        assert linha["texto"] == "Entrou no ar na versão v0.169.0, em 08/10/2026."
