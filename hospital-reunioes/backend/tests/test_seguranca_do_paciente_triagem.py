"""A tela de triagem do Núcleo (issue #1992, PRD #1979, ADR 0095 e 0107).

Um bloco por critério de aceite do backend:

1. a fila mostra as notificações sem triagem confirmada, da mais antiga para a
   mais nova, com a faixa sugerida e sem nome de paciente ou profissional;
2. nas faixas A e B e nos casos de revisão forçada, confirmar exige todos os
   campos conferidos; não existe "aceitar tudo";
3. nas faixas C, D e E, confirmar é um clique;
4. ajustar grava a linha da pessoa com as divergências, e a sugestão original
   continua gravada;
5. recorrência, casos parecidos, frequência e prioridade saem calculados; os
   cortes de frequência se editam na Configuração;
6. a notificação "classificar manualmente" abre sem sugestão.

O banco é o dublê em memória do teste da notificação, com o que a migration
188 e a 189 fazem no insert da triagem: a versão em sequência e uma decisão de
pessoa por notificação. Nenhum dado de pessoa real.
"""

from __future__ import annotations

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
    _Banco,
    _Consulta,
    _participacao,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_triagem as triagem_router  # noqa: E402
from app.services.seguranca_do_paciente import triagem  # noqa: E402

OUTRO_SETOR = {"id": "44444444-4444-4444-4444-444444444444", "nome": "Centro Cirúrgico", "ativo": True}
RECUSA = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}
DIA = date(2026, 11, 10)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


# ═══════════════════════════════════════════════════════════════════════════
# O dublê: o que a 188 e a 189 fazem no insert da triagem
# ═══════════════════════════════════════════════════════════════════════════


class _ConsultaDaTriagem(_Consulta):
    def _inserir(self) -> list[dict]:
        if self._nome == "nsp_triagens":
            novas = self._valores if isinstance(self._valores, list) else [self._valores]
            for valores in novas:
                mesmas = [t for t in self._linhas if t["notificacao_id"] == valores["notificacao_id"]]
                if valores.get("autor_tipo") == "pessoa" and any(t["autor_tipo"] == "pessoa" for t in mesmas):
                    raise APIError({"code": "23505", "message": "duplicate key value"})
                valores["versao"] = max((t["versao"] for t in mesmas), default=0) + 1
        return super()._inserir()


class _BancoDaTriagem(_Banco):
    def table(self, nome: str):
        return _ConsultaDaTriagem(self, nome)

    @property
    def triagens(self) -> list[dict]:
        return self.tabelas.setdefault("nsp_triagens", [])


def _notificacao(numero: int, **campos) -> dict[str, Any]:
    base = {
        "id": f"00000000-0000-0000-0000-{numero:012d}",
        "protocolo": f"NSP-2026-{numero:04d}",
        "ano": 2026,
        "numero": numero,
        "origem": "qr",
        "estado": "recebida",
        "relato": f"Relato de teste {numero}: a bomba de infusão alarmou sem ninguém ouvir.",
        "leito_ou_atendimento": "Leito 4",
        "setor_id": SETOR["id"],
        "data_ocorrencia": DIA.isoformat(),
        "turno": "noite",
        "hora_aproximada": None,
        "chegou_ao_paciente": "sem_dano",
        "grave_ou_morte": None,
        "percebido_ou_reclamacao": None,
        "anonimo": False,
        "notificante_id": None,
        "notificante_nome": "Profissional Notificante",
        "notificante_contato": "notificante@hsm.test",
        "manifestacao_id": None,
        "classificar_manualmente": False,
        "motivo_classificar_manualmente": None,
        "criado_em": f"2026-11-{numero:02d}T10:00:00+00:00",
    }
    return {**base, **campos}


def _sugestao(notificacao: dict, versao: int = 1, **campos) -> dict[str, Any]:
    base = {
        "id": f"tri-{notificacao['numero']}-{versao}",
        "notificacao_id": notificacao["id"],
        "versao": versao,
        "autor_tipo": "agente",
        "autor_id": None,
        "assunto": "Alarme de bomba de infusão sem resposta",
        "natureza": "incidente_sem_dano",
        "grau_de_dano": "nenhum",
        "categoria": "EQP",
        "incidente": "Alarme inoperante",
        "evento_situacao": "nao",
        "evento_item": None,
        "evento_motivo": "Nenhum item da lista.",
        "iras": False,
        "risco_de_imagem": False,
        "protocolo_basico": "nenhum",
        "canais": ["NSP"],
        "motivo_do_encaminhamento": None,
        "faixa": "D",
        "revisao": "confirmacao_simples",
        "justificativa": "O alarme não foi atendido e o paciente não teve dano.",
        "confianca": "alta",
        "motivo_da_confianca": "O relato é claro.",
        "alertas": [],
        "perguntas_ao_notificante": [],
        "prompt_versao": "1.1",
        "base_versao": "1.1",
        "modelo": "modelo-de-teste",
        "tentativas": 1,
        "divergencias": None,
        "frequencia": None,
        "prioridade": None,
        "criado_em": notificacao["criado_em"],
    }
    return {**base, **campos}


# Faixa A: óbito.
OBITO = {
    "natureza": "evento_adverso",
    "grau_de_dano": "obito",
    "faixa": "A",
    "revisao": "campo_a_campo",
}
# Faixa B: dano grave.
GRAVE = {"natureza": "evento_adverso", "grau_de_dano": "grave", "faixa": "B", "revisao": "campo_a_campo"}
# Faixa C: dano moderado.
MODERADO = {"natureza": "evento_adverso", "grau_de_dano": "moderado", "faixa": "C"}
# Faixa E: quase erro.
QUASE_ERRO = {"natureza": "quase_erro", "grau_de_dano": "nenhum", "faixa": "E"}


def _banco(notificacoes: list[dict] | None = None, triagens: list[dict] | None = None) -> _BancoDaTriagem:
    return _BancoDaTriagem(
        {
            "participantes": [dict(p) for p in (PRESIDENTE, MEMBRO, SUPER_ADMIN, DIRETOR_EXECUTIVO)],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [_participacao("P1", "presidencia"), _participacao("P2", "membro")],
            "setores": [dict(SETOR), dict(OUTRO_SETOR)],
            "nsp_notificacoes": [dict(n) for n in (notificacoes or [])],
            "nsp_triagens": [dict(t) for t in (triagens or [])],
            "nsp_categorias": [
                {"codigo": "EQP", "nome": "Equipamentos e materiais", "ordem": 11},
                {"codigo": "MED", "nome": "Medicamentos e soluções", "ordem": 2},
            ],
            "nsp_eventos_que_nunca_deveriam_ocorrer": [
                {"item": 11, "evento": "Óbito associado a queda do paciente durante o atendimento"},
            ],
            "nsp_notificacoes_anexos": [],
        }
    )


def _cliente(banco: _BancoDaTriagem, pessoa: dict[str, Any] = PRESIDENTE) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(triagem_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


FILA = "/api/nsp/triagem"


def _caso(notificacao_id: str) -> str:
    return f"/api/nsp/triagem/{notificacao_id}"


# ═══════════════════════════════════════════════════════════════════════════
# 1. A fila
# ═══════════════════════════════════════════════════════════════════════════


def test_a_fila_vem_da_mais_antiga_para_a_mais_nova_com_a_faixa_sugerida():
    nova, velha, do_meio = _notificacao(9), _notificacao(2), _notificacao(5)
    banco = _banco(
        [nova, velha, do_meio],
        [_sugestao(velha, **OBITO), _sugestao(do_meio, **MODERADO), _sugestao(nova)],
    )

    resposta = _cliente(banco).get(FILA)

    assert resposta.status_code == 200, resposta.text
    fila = resposta.json()["fila"]
    assert [(c["protocolo"], c["faixa"]) for c in fila] == [
        ("NSP-2026-0002", "A"),
        ("NSP-2026-0005", "C"),
        ("NSP-2026-0009", "D"),
    ]
    assert fila[0]["setor"] == "UTI Adulto"
    assert fila[0]["assunto"] == "Alarme de bomba de infusão sem resposta"


def test_a_fila_deixa_de_fora_o_que_ja_tem_triagem_confirmada():
    pendente, confirmada, classificada = _notificacao(1), _notificacao(2), _notificacao(3, estado="classificada")
    decisao = {**_sugestao(confirmada, versao=2), "autor_tipo": "pessoa", "autor_id": "P1", "divergencias": []}
    banco = _banco([pendente, confirmada, classificada], [_sugestao(pendente), _sugestao(confirmada), decisao])

    fila = _cliente(banco).get(FILA).json()["fila"]

    assert [c["protocolo"] for c in fila] == ["NSP-2026-0001"]


def test_a_fila_nao_traz_o_relato_nem_quem_notificou():
    caso = _notificacao(1, relato="O paciente Fulano Beltrano caiu do leito.")
    banco = _banco([caso], [_sugestao(caso)])

    corpo = _cliente(banco).get(FILA).text

    for dado in ("Fulano", "Beltrano", "Profissional Notificante", "notificante@hsm.test", "Leito 4"):
        assert dado not in corpo, dado


def test_a_notificacao_para_classificar_manualmente_entra_na_fila_sem_faixa():
    caso = _notificacao(1, classificar_manualmente=True, motivo_classificar_manualmente="agente_fora")
    banco = _banco([caso])

    [item] = _cliente(banco).get(FILA).json()["fila"]

    assert item["faixa"] is None
    assert item["assunto"] is None
    assert item["classificar_manualmente"] is True


@pytest.mark.parametrize("pessoa", [MEMBRO, SUPER_ADMIN], ids=["membro do Núcleo", "super admin sem Acesso pleno"])
def test_so_a_presidencia_e_o_acesso_pleno_abrem_a_fila(pessoa):
    banco = _banco([_notificacao(1)])

    assert _cliente(banco, pessoa).get(FILA).json() == RECUSA
    assert _cliente(banco, DIRETOR_EXECUTIVO).get(FILA).status_code == 200
