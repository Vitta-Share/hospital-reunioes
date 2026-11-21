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


# ═══════════════════════════════════════════════════════════════════════════
# 2. A pendência aos 30 e aos 60 dias, uma vez cada, sem e-mail
# ═══════════════════════════════════════════════════════════════════════════

# A primeira notificação registrada chega em 01/10/2026, às 22h de Brasília
# (01h de 02/10 em UTC): o dia que conta é o de Brasília.
PRIMEIRA = _notificacao(1, criado_em="2026-10-02T01:00:00+00:00")
DEPOIS = _notificacao(2, criado_em="2026-10-20T10:00:00+00:00")
TRINTA_DIAS = date(2026, 10, 31)
SESSENTA_DIAS = date(2026, 11, 30)


def _cenario_do_lembrete(*pessoas: dict) -> _BancoDaRecalibracao:
    banco = _banco([DEPOIS, PRIMEIRA])
    banco.tabelas["participantes"].extend(dict(p) for p in pessoas)
    return banco


def _recalibrar(banco: _BancoDaRecalibracao) -> list[dict]:
    return [p for p in banco.pendencias if p["descricao_acao"].startswith("Recalibrar o agente do NSP")]


def test_aos_30_dias_nasce_a_pendencia_para_cada_pessoa_com_acesso_pleno():
    banco = _cenario_do_lembrete(OUTRO_PLENO)

    criadas = recalibracao.lembrar(banco, TRINTA_DIAS)

    assert criadas == 2
    pendencias = _recalibrar(banco)
    assert sorted(p["responsavel_id"] for p in pendencias) == ["P5", "P7"]
    assert all(p["descricao_acao"] == "Recalibrar o agente do NSP (30 dias)" for p in pendencias)
    assert all(p.get("id_reuniao") is None and p["status"] == "PENDENTE" for p in pendencias)
    assert banco.recalibracoes[0]["marco"] == 30
    assert sorted(banco.recalibracoes[0]["pendencias"]) == sorted(p["id_acao"] for p in pendencias)


def test_antes_dos_30_dias_nada_nasce():
    banco = _cenario_do_lembrete()

    assert recalibracao.lembrar(banco, TRINTA_DIAS - timedelta(days=1)) == 0
    assert _recalibrar(banco) == []
    assert banco.recalibracoes == []


def test_cada_marco_nasce_uma_vez_so():
    banco = _cenario_do_lembrete()

    recalibracao.lembrar(banco, TRINTA_DIAS)
    assert recalibracao.lembrar(banco, TRINTA_DIAS) == 0
    assert recalibracao.lembrar(banco, TRINTA_DIAS + timedelta(days=5)) == 0
    assert recalibracao.lembrar(banco, SESSENTA_DIAS) == 1
    assert recalibracao.lembrar(banco, SESSENTA_DIAS + timedelta(days=1)) == 0

    assert [p["descricao_acao"] for p in _recalibrar(banco)] == [
        "Recalibrar o agente do NSP (30 dias)",
        "Recalibrar o agente do NSP (60 dias)",
    ]


def test_a_pendencia_nao_vai_para_quem_nao_tem_acesso_pleno_nem_para_o_desligado():
    banco = _cenario_do_lembrete(_pessoa("P8", perfil_nsp="acesso_pleno", ativo=False))

    recalibracao.lembrar(banco, TRINTA_DIAS)

    assert [p["responsavel_id"] for p in _recalibrar(banco)] == ["P5"]


def test_sem_notificacao_nenhuma_nada_nasce():
    banco = _banco()

    assert recalibracao.lembrar(banco, SESSENTA_DIAS) == 0
    assert banco.recalibracoes == []


def test_o_marco_sem_ninguem_com_acesso_pleno_nasce_quando_alguem_chega():
    banco = _banco([PRIMEIRA])
    banco.tabelas["participantes"] = [dict(PRESIDENTE)]

    assert recalibracao.lembrar(banco, TRINTA_DIAS) == 0
    banco.tabelas["participantes"].append(dict(DIRETOR_EXECUTIVO))
    assert recalibracao.lembrar(banco, TRINTA_DIAS + timedelta(days=1)) == 1
    assert [p["responsavel_id"] for p in _recalibrar(banco)] == ["P5"]


# O que denuncia IA ou e-mail no código: os módulos do app que falam com
# provedor de modelo ou de e-mail e os SDKs.
_MARCAS_DE_IA_E_EMAIL = ("ai_processor", "anthropic", "openai", "openrouter", "email", "resend", "smtp")


def _marcas(codigo: str) -> list[str]:
    return [marca for marca in _MARCAS_DE_IA_E_EMAIL if marca in codigo.lower()]


def test_o_detector_reconhece_um_modulo_que_chama_ia_e_email():
    """Piso do detector: o agente de triagem e o serviço de e-mail têm marca."""
    from app.services import email_service
    from app.services.seguranca_do_paciente import agente_de_triagem

    assert _marcas(inspect.getsource(agente_de_triagem))
    assert _marcas(inspect.getsource(email_service))


def test_o_job_nao_fala_com_ia_nem_com_email():
    from app.cron import scheduler

    assert _marcas(inspect.getsource(recalibracao.lembrar)) == []
    assert _marcas(inspect.getsource(scheduler.lembrar_recalibracao_do_agente)) == []
    assert "recalibracao.lembrar(" in inspect.getsource(scheduler.lembrar_recalibracao_do_agente)
    assert 'lembrar_recalibracao_do_agente,\n        "cron"' in inspect.getsource(scheduler.start_scheduler)
