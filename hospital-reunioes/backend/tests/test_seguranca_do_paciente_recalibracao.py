"""O período de sombra e a recalibração do agente do Núcleo (issue #2001,
PRD #1979, ADR 0107 decisão 10; Anexo F, seções 4, 5 e 7).

Um bloco por critério de aceite do backend:

1. a concordância entre a sugestão do agente e a decisão da Presidência, por
   eixo, na Configuração, com os casos em que a Presidência subiu o grau de
   dano sugerido listados à parte;
2. o job diário, sem IA e sem e-mail, cria a pendência "Recalibrar o agente do
   NSP" aos 30 e aos 60 dias da primeira notificação, uma vez cada, para quem
   tem Acesso pleno;
3. a tela dos itens do Anexo F calcula o que tem dado nesta fase e marca o
   resto como "sem dados nesta fase";
4. concluir a pendência exige uma das três decisões e grava quem decidiu e
   quando.

O banco é o dublê em memória da tela de triagem. Nenhum dado de pessoa real.
"""

from __future__ import annotations

import inspect
import os
import sys
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import (  # noqa: E402
    DIRETOR_EXECUTIVO,
    MEMBRO,
    NUCLEO,
    PRESIDENTE,
    SETOR,
    SUPER_ADMIN,
    _participacao,
    _pessoa,
)
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    GRAVE,
    MODERADO,
    OBITO,
    _BancoDaTriagem,
    _ConsultaDaTriagem,
    _notificacao,
    _sugestao,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_recalibracao as recalibracao_router  # noqa: E402
from app.services.seguranca_do_paciente import recalibracao  # noqa: E402

RECUSA = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}
CONCORDANCIA = "/api/nsp/configuracao/concordancia"
OUTRO_PLENO = _pessoa("P7", perfil_nsp="acesso_pleno")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


# ═══════════════════════════════════════════════════════════════════════════
# O dublê: a triagem, mais o `is_` e a função de ação da Pendência
# ═══════════════════════════════════════════════════════════════════════════


class _ConsultaDaRecalibracao(_ConsultaDaTriagem):
    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def _inserir(self) -> list[dict]:
        if self._nome == "nsp_recalibracoes":
            novas = self._valores if isinstance(self._valores, list) else [self._valores]
            for valores in novas:
                if any(r["marco"] == valores["marco"] for r in self._linhas):
                    raise APIError({"code": "23505", "message": "duplicate key value"})
                valores.setdefault("pendencias", [])
                valores.setdefault("decisao", None)
                valores.setdefault("decidido_por", None)
                valores.setdefault("decidido_em", None)
        return super()._inserir()


class _BancoDaRecalibracao(_BancoDaTriagem):
    def table(self, nome: str):
        return _ConsultaDaRecalibracao(self, nome)

    def rpc(self, nome: str, params: dict):
        """A função `registrar_acao_da_pendencia` (migration 169): confere o
        estado lido e muda a Pendência."""
        banco = self

        class _Exec:
            def execute(self_inner):  # noqa: N805
                assert nome == "registrar_acao_da_pendencia"
                pendencia = next(p for p in banco.tabelas["pendencias"] if p["id_acao"] == params["p_id_acao"])
                if pendencia["status"] != params["p_status_esperado"]:
                    raise APIError({"code": "PT409", "message": "A pendencia mudou."})
                pendencia["status"] = params["p_status_novo"]
                banco.tabelas.setdefault("pendencia_historico", []).append(dict(params))
                return type("R", (), {"data": None})()

        return _Exec()

    @property
    def recalibracoes(self) -> list[dict]:
        return self.tabelas.setdefault("nsp_recalibracoes", [])

    @property
    def pendencias(self) -> list[dict]:
        return self.tabelas.setdefault("pendencias", [])


def _banco(notificacoes: list[dict] | None = None, triagens: list[dict] | None = None, **tabelas):
    return _BancoDaRecalibracao(
        {
            "participantes": [dict(p) for p in (PRESIDENTE, MEMBRO, SUPER_ADMIN, DIRETOR_EXECUTIVO)],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [_participacao("P1", "presidencia"), _participacao("P2", "membro")],
            "setores": [dict(SETOR)],
            "nsp_notificacoes": [dict(n) for n in (notificacoes or [])],
            "nsp_triagens": [dict(t) for t in (triagens or [])],
            "pendencias": [],
            **tabelas,
        }
    )


def _cliente(banco: _BancoDaRecalibracao, pessoa: dict[str, Any] = PRESIDENTE) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(recalibracao_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _decisao(notificacao: dict, divergencias: list[str] | None, **campos) -> dict[str, Any]:
    """A linha da pessoa: a triagem confirmada, com as divergências."""
    return {
        **_sugestao(notificacao, versao=9, **campos),
        "id": f"dec-{notificacao['numero']}",
        "autor_tipo": "pessoa",
        "autor_id": "P1",
        "divergencias": divergencias,
        "criado_em": notificacao["criado_em"].replace("T10:", "T12:"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. A concordância por eixo, na Configuração
# ═══════════════════════════════════════════════════════════════════════════


def _cenario_da_concordancia() -> _BancoDaRecalibracao:
    acatada, subiu, categoria, manual, canal = (_notificacao(n, estado="classificada") for n in range(1, 6))
    return _banco(
        [acatada, subiu, categoria, manual, canal],
        [
            _sugestao(acatada),
            _decisao(acatada, []),
            _sugestao(subiu, **MODERADO),
            _decisao(subiu, ["grau_de_dano", "faixa"], **GRAVE),
            _sugestao(categoria),
            _decisao(categoria, ["categoria"], categoria="MED"),
            # Classificar manualmente: não havia sugestão, não entra na conta.
            _decisao(manual, None),
            _sugestao(canal),
            _decisao(canal, ["canais", "iras"], canais=["NSP", "SST"], iras=True),
        ],
    )


def test_a_configuracao_mostra_a_concordancia_por_eixo_so_dos_casos_com_sugestao():
    resposta = _cliente(_cenario_da_concordancia()).get(CONCORDANCIA)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["casos"] == 4
    assert [(e["rotulo"], e["acatadas"], e["total"], e["percentual"]) for e in corpo["eixos"]] == [
        ("Natureza", 4, 4, 100),
        ("Grau de dano", 3, 4, 75),
        ("Categoria", 3, 4, 75),
        ("Faixa", 3, 4, 75),
        ("Canal", 3, 4, 75),
        ("Marcadores", 3, 4, 75),
    ]


def test_os_casos_em_que_a_presidencia_subiu_o_grau_aparecem_a_parte():
    corpo = _cliente(_cenario_da_concordancia()).get(CONCORDANCIA).json()

    assert corpo["erros_para_baixo"] == [
        {
            "notificacao_id": "00000000-0000-0000-0000-000000000002",
            "protocolo": "NSP-2026-0002",
            "sugerido": "moderado",
            "decidido": "grave",
            "grave_ou_obito": True,
        }
    ]


def test_a_configuracao_diz_as_versoes_do_prompt_e_da_base_em_uso():
    corpo = _cliente(_banco()).get(CONCORDANCIA).json()

    assert corpo["versoes"] == {"prompt": "1.0.1", "base": "1.1"}
    assert corpo["casos"] == 0
    assert all(e["percentual"] is None for e in corpo["eixos"])


@pytest.mark.parametrize("pessoa", [MEMBRO, SUPER_ADMIN])
def test_quem_nao_confirma_triagem_nao_ve_a_concordancia(pessoa):
    resposta = _cliente(_cenario_da_concordancia(), pessoa).get(CONCORDANCIA)

    assert resposta.status_code == 403
    assert resposta.json() == RECUSA
