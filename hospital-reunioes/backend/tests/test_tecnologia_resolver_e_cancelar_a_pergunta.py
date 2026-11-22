"""Resolver e cancelar a Pergunta da Vitta pela ponte (issue #2121, PRD #2112,
ADR 0109, decisão 6).

A resposta não solta o trabalho sozinha: a Vitta lê e dá o ok no PedroOS, e
só então a ponte marca a Pergunta como resolvida, com o que foi decidido e o
que destravou. A Pergunta que deixou de ser necessária vira cancelada, com o
motivo. As duas passagens põem uma linha de sistema na Conversa da Demanda, e
a Pergunta resolvida ou cancelada não muda mais.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo`.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    CONVERSA,
    CONVERSA_DA_TELA,
    DIRETORA,
    PEDRO,
    TABELA,
    _criar,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
    emails,
)
from test_tecnologia_vinculo import _integracao_configurada, _montar  # noqa: E402, F401

from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

DECIDIDO = "Quem presidiu a reunião assina a Ata pela diretoria."
DESTRAVOU = "A tela de assinatura da Ata volta a andar e entra na próxima subida."
MOTIVO = "A diretoria decidiu na reunião de quinta, não precisa mais perguntar."


def _url(pergunta_id: str, acao: str) -> str:
    return f"/api/automacao/tecnologia/perguntas/{pergunta_id}/{acao}"


def _resolver(ponte, pergunta_id: str, **campos):
    corpo = {"github_login": "pedrorezendefig", "decidido": DECIDIDO, "destravou": DESTRAVOU, **campos}
    return ponte.post(_url(pergunta_id, "resolver"), json=corpo, headers={"X-API-Key": CHAVE})


def _cancelar(ponte, pergunta_id: str, **campos):
    corpo = {"github_login": "pedrorezendefig", "motivo": MOTIVO, **campos}
    return ponte.post(_url(pergunta_id, "cancelar"), json=corpo, headers={"X-API-Key": CHAVE})


def _pergunta(estado: str = "aberta"):
    """A Pergunta da Vitta para a Diretora, já no estado pedido. A resposta é
    gravada direto na linha, com as colunas da migration (o responder pela
    tela tem o próprio teste, #2119)."""
    ponte, sb = _ponte()
    pergunta_id = _criar(ponte).json()["id"]
    [linha] = sb.tabelas[TABELA]
    if estado != "aberta":
        linha.update(
            {
                "estado": estado,
                "resposta_opcao": "B",
                "respondida_por": DIRETORA["id"],
                "respondida_em": "2026-11-22T09:30:00Z",
            }
        )
    if estado == "resolvida":
        linha.update({"resolucao_decidido": "Outra decisão.", "resolucao_destravou": "Outra coisa.", "resolvida_em": "x"})
    if estado == "cancelada":
        linha.update({"resolucao_decidido": "Outro motivo.", "cancelada_em": "x"})
    return ponte, sb, pergunta_id


def _linhas_de_sistema(sb) -> list[str]:
    return [m["texto"] for m in sb.tabelas[CONVERSA] if m.get("origem") == "sistema"]


# ═══════════════════════════════════════════════════════════════════════════
# Resolver
# ═══════════════════════════════════════════════════════════════════════════


class TestResolver:
    def test_resolver_a_respondida_grava_a_decisao_e_o_que_destravou(self):
        ponte, sb, pergunta_id = _pergunta("respondida")

        resposta = _resolver(ponte, pergunta_id)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["estado"] == "resolvida"
        [linha] = sb.tabelas[TABELA]
        assert linha["estado"] == "resolvida"
        assert (linha["resolucao_decidido"], linha["resolucao_destravou"]) == (DECIDIDO, DESTRAVOU)
        assert linha["resolvida_em"]
        assert not linha.get("cancelada_em")

    def test_resolver_poe_na_conversa_a_linha_de_sistema_com_a_decisao_e_o_que_destravou(self):
        ponte, sb, pergunta_id = _pergunta("respondida")

        _resolver(ponte, pergunta_id)

        assert _linhas_de_sistema(sb)[-1] == (
            "Pergunta resolvida: quem assina a Ata pela diretoria\n"
            f"O que foi decidido: {DECIDIDO}\n"
            f"O que destravou: {DESTRAVOU}"
        )

    @pytest.mark.parametrize(
        ("estado", "motivo"),
        [
            ("aberta", "A Pergunta ainda não foi respondida: só a respondida se resolve."),
            ("resolvida", "Esta Pergunta já foi resolvida e não muda mais."),
            ("cancelada", "Esta Pergunta já foi cancelada e não muda mais."),
        ],
    )
    def test_resolver_a_aberta_a_resolvida_ou_a_cancelada_e_recusado_com_motivo_e_nada_muda(self, estado, motivo):
        ponte, sb, pergunta_id = _pergunta(estado)
        antes = dict(sb.tabelas[TABELA][0])
        linhas_antes = list(sb.tabelas[CONVERSA])

        resposta = _resolver(ponte, pergunta_id)

        assert resposta.status_code == 409
        assert resposta.json() == {"detail": motivo}
        assert sb.tabelas[TABELA][0] == antes
        assert sb.tabelas[CONVERSA] == linhas_antes

    @pytest.mark.parametrize(
        ("campos", "motivo"),
        [
            ({"decidido": "  "}, "Falta o que foi decidido."),
            ({"destravou": None}, "Falta o que destravou."),
        ],
        ids=["sem-decisao", "sem-o-que-destravou"],
    )
    def test_resolver_sem_a_decisao_ou_sem_o_que_destravou_e_recusado_e_nada_muda(self, campos, motivo):
        ponte, sb, pergunta_id = _pergunta("respondida")
        linhas_antes = list(sb.tabelas[CONVERSA])

        resposta = _resolver(ponte, pergunta_id, **campos)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": motivo}
        assert sb.tabelas[TABELA][0]["estado"] == "respondida"
        assert sb.tabelas[CONVERSA] == linhas_antes


# ═══════════════════════════════════════════════════════════════════════════
# Cancelar
# ═══════════════════════════════════════════════════════════════════════════


class TestCancelar:
    @pytest.mark.parametrize("estado", ["aberta", "respondida"])
    def test_cancelar_a_aberta_ou_a_respondida_grava_o_motivo(self, estado):
        ponte, sb, pergunta_id = _pergunta(estado)

        resposta = _cancelar(ponte, pergunta_id)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["estado"] == "cancelada"
        [linha] = sb.tabelas[TABELA]
        assert linha["estado"] == "cancelada"
        assert linha["resolucao_decidido"] == MOTIVO
        assert linha["cancelada_em"]
        assert not linha.get("resolvida_em")

    @pytest.mark.parametrize("estado", ["aberta", "respondida"])
    def test_cancelar_poe_na_conversa_a_linha_de_sistema_com_o_motivo(self, estado):
        ponte, sb, pergunta_id = _pergunta(estado)

        _cancelar(ponte, pergunta_id)

        assert _linhas_de_sistema(sb)[-1] == f"Pergunta cancelada: quem assina a Ata pela diretoria\nMotivo: {MOTIVO}"

    def test_a_cancelada_sai_da_lista_esperando_sua_resposta(self, monkeypatch):
        ponte, sb, pergunta_id = _pergunta("aberta")
        tela = _tela(sb, DIRETORA, monkeypatch)
        esperando = "/api/admin/tecnologia/perguntas/esperando"
        assert [p["id"] for p in tela.get(esperando).json()] == [pergunta_id]

        _cancelar(ponte, pergunta_id)

        assert tela.get(esperando).json() == []

    @pytest.mark.parametrize(
        ("estado", "motivo"),
        [
            ("resolvida", "Esta Pergunta já foi resolvida e não muda mais."),
            ("cancelada", "Esta Pergunta já foi cancelada e não muda mais."),
        ],
    )
    def test_cancelar_a_resolvida_ou_a_cancelada_e_recusado_com_motivo_e_nada_muda(self, estado, motivo):
        ponte, sb, pergunta_id = _pergunta(estado)
        antes = dict(sb.tabelas[TABELA][0])
        linhas_antes = list(sb.tabelas[CONVERSA])

        resposta = _cancelar(ponte, pergunta_id)

        assert resposta.status_code == 409
        assert resposta.json() == {"detail": motivo}
        assert sb.tabelas[TABELA][0] == antes
        assert sb.tabelas[CONVERSA] == linhas_antes

    def test_cancelar_sem_motivo_e_recusado_e_nada_muda(self):
        ponte, sb, pergunta_id = _pergunta("aberta")

        resposta = _cancelar(ponte, pergunta_id, motivo=" ")

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": "Falta o motivo do cancelamento."}
        assert sb.tabelas[TABELA][0]["estado"] == "aberta"


# ═══════════════════════════════════════════════════════════════════════════
# Duas vezes
# ═══════════════════════════════════════════════════════════════════════════


class TestDuasVezes:
    def test_resolver_duas_vezes_e_recusado_e_a_primeira_fica(self):
        ponte, sb, pergunta_id = _pergunta("respondida")
        _resolver(ponte, pergunta_id)

        segunda = _resolver(ponte, pergunta_id, decidido="Outra coisa.")

        assert segunda.status_code == 409
        assert sb.tabelas[TABELA][0]["resolucao_decidido"] == DECIDIDO
        assert [t.split(":")[0] for t in _linhas_de_sistema(sb)] == ["Pergunta aberta", "Pergunta resolvida"]

    def test_cancelar_duas_vezes_e_recusado_e_o_primeiro_motivo_fica(self):
        ponte, sb, pergunta_id = _pergunta("aberta")
        _cancelar(ponte, pergunta_id)

        segunda = _cancelar(ponte, pergunta_id, motivo="Outro motivo.")

        assert segunda.status_code == 409
        assert sb.tabelas[TABELA][0]["resolucao_decidido"] == MOTIVO
        assert [t.split(":")[0] for t in _linhas_de_sistema(sb)] == ["Pergunta aberta", "Pergunta cancelada"]

    def test_resolver_e_cancelar_ao_mesmo_tempo_so_o_primeiro_grava(self):
        """Os dois leram a Pergunta respondida antes de qualquer escrita: o
        cancelar entra no meio do resolver, e o resolver é recusado."""
        ponte, sb, pergunta_id = _pergunta("respondida")
        sb.ao_atualizar = lambda: _cancelar(ponte, pergunta_id)

        resposta = _resolver(ponte, pergunta_id)

        assert resposta.status_code == 409
        assert resposta.json() == {"detail": "Esta Pergunta já foi cancelada e não muda mais."}
        [linha] = sb.tabelas[TABELA]
        assert (linha["estado"], linha["resolucao_decidido"]) == ("cancelada", MOTIVO)
        assert not linha.get("resolvida_em")
        assert [t.split(":")[0] for t in _linhas_de_sistema(sb)] == ["Pergunta aberta", "Pergunta cancelada"]


# ═══════════════════════════════════════════════════════════════════════════
# A mesma chave e o mesmo teto da ponte
# ═══════════════════════════════════════════════════════════════════════════


def _fechar(acao: str):
    return _resolver if acao == "resolver" else _cancelar


@pytest.mark.parametrize("acao", ["resolver", "cancelar"])
class TestAPorta:
    def test_sem_a_chave_da_ponte_nada_muda(self, acao):
        ponte, sb, pergunta_id = _pergunta("respondida")

        resposta = ponte.post(
            _url(pergunta_id, acao),
            json={"github_login": "pedrorezendefig", "decidido": DECIDIDO, "destravou": DESTRAVOU, "motivo": MOTIVO},
            headers={"X-API-Key": "chave-errada"},
        )

        assert resposta.status_code == 401
        assert sb.tabelas[TABELA][0]["estado"] == "respondida"

    def test_o_61o_pedido_no_mesmo_minuto_e_429_mesmo_com_a_chave_certa(self, acao):
        ponte, sb, pergunta_id = _pergunta("respondida")
        # O teto conta antes da chave: 60 tentativas de chave errada esgotam o minuto.
        tentativas = [ponte.post(_url(pergunta_id, acao), json={}, headers={"X-API-Key": "x"}) for _ in range(60)]
        assert [r.status_code for r in tentativas] == [401] * 60

        passou_do_teto = _fechar(acao)(ponte, pergunta_id)

        assert passou_do_teto.status_code == 429
        assert sb.tabelas[TABELA][0]["estado"] == "respondida"

    def test_login_que_nao_e_de_desenvolvedor_e_recusado_e_nada_muda(self, acao):
        ponte, sb, pergunta_id = _pergunta("respondida")

        resposta = _fechar(acao)(ponte, pergunta_id, github_login="quem-nao-e")

        assert resposta.status_code == 403
        assert sb.tabelas[TABELA][0]["estado"] == "respondida"

    def test_pergunta_que_nao_existe_e_404(self, acao):
        ponte, _, _ = _pergunta("respondida")

        resposta = _fechar(acao)(ponte, "0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e")

        assert resposta.status_code == 404
