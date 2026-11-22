"""Responder a Pergunta da Vitta no cartão (issue #2119, PRD #2112, ADR 0109,
decisões 4 e 5).

O Destinatário responde por uma das opções prontas ou pelo campo livre, e a
Pergunta passa de aberta a respondida. A resposta entra também na Conversa da
Demanda, no nome de quem respondeu. O Desenvolvedor pode registrar a resposta
no lugar do Destinatário, e os dois nomes ficam gravados. Outro Super admin vê
o cartão sem poder responder. A resposta não muda Etapa e não vai ao GitHub.

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
    DEMANDA,
    DIRETOR,
    DIRETORA,
    PEDRO,
    TABELA,
    _criar,
    _ler,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
    emails,
)

from app.services import github_client  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402


def _responder_url(pergunta_id: str) -> str:
    return f"/api/admin/tecnologia/perguntas/{pergunta_id}/resposta"


def _uma_pergunta_aberta():
    """A Pergunta da Vitta para a Diretora, com as opções A e B (a B recomendada)."""
    ponte, sb = _ponte()
    pergunta_id = _criar(ponte).json()["id"]
    return ponte, sb, pergunta_id


def _responder(sb, logado, pergunta_id, monkeypatch, **corpo):
    return _tela(sb, logado, monkeypatch).post(_responder_url(pergunta_id), json=corpo)


@pytest.fixture(autouse=True)
def chamadas_ao_github(monkeypatch) -> list[tuple]:
    """Toda ida ao GitHub fica gravada aqui, em vez de sair para a rede."""
    chamadas: list[tuple] = []

    def _gravar(*a, **kw):
        chamadas.append((a, kw))
        raise AssertionError("A resposta da Pergunta foi ao GitHub.")

    monkeypatch.setattr(github_client.httpx, "request", _gravar)
    return chamadas


# ═══════════════════════════════════════════════════════════════════════════
# O Destinatário responde
# ═══════════════════════════════════════════════════════════════════════════


class TestODestinatarioResponde:
    def test_destinatario_responde_por_opcao_e_a_pergunta_passa_a_respondida(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()

        resposta = _responder(sb, DIRETORA, pergunta_id, monkeypatch, opcao="B")

        assert resposta.status_code == 200, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert pergunta["estado"] == "respondida"
        assert pergunta["resposta_opcao"] == "B"
        assert pergunta["resposta_texto"] is None
        assert pergunta["respondida_por"] == DIRETORA["id"]
        assert pergunta["respondida_em_nome_de"] is None
        assert pergunta["respondida_em"]

    def test_destinatario_responde_por_texto_livre(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()

        resposta = _responder(sb, DIRETORA, pergunta_id, monkeypatch, texto="  Quem estiver de plantão na diretoria.  ")

        assert resposta.status_code == 200, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert pergunta["estado"] == "respondida"
        assert (pergunta["resposta_opcao"], pergunta["resposta_texto"]) == (
            None,
            "Quem estiver de plantão na diretoria.",
        )

    @pytest.mark.parametrize(
        ("corpo", "motivo"),
        [
            ({}, "Escolha uma das opções ou escreva a sua resposta."),
            ({"texto": "   "}, "Escolha uma das opções ou escreva a sua resposta."),
            ({"opcao": "C"}, "A opção escolhida não é uma das opções da Pergunta."),
        ],
        ids=["vazia", "so-espacos", "opcao-que-nao-existe"],
    )
    def test_resposta_vazia_ou_com_opcao_que_nao_existe_e_recusada_e_nada_muda(self, corpo, motivo, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()
        conversa_antes = len(sb.tabelas[CONVERSA])

        resposta = _responder(sb, DIRETORA, pergunta_id, monkeypatch, **corpo)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": motivo}
        assert sb.tabelas[TABELA][0]["estado"] == "aberta"
        assert len(sb.tabelas[CONVERSA]) == conversa_antes

    def test_a_resposta_nao_muda_a_etapa_da_demanda(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()
        [demanda] = sb.tabelas["tecnologia_demandas"]
        antes = dict(demanda)

        _responder(sb, DIRETORA, pergunta_id, monkeypatch, opcao="A")

        assert (demanda["etapa"], demanda["estado"]) == (antes["etapa"], antes["estado"])


# ═══════════════════════════════════════════════════════════════════════════
# A resposta na Conversa da Demanda
# ═══════════════════════════════════════════════════════════════════════════


class TestNaConversa:
    def test_a_resposta_por_opcao_entra_na_conversa_no_nome_de_quem_respondeu(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()

        _responder(sb, DIRETORA, pergunta_id, monkeypatch, opcao="B")

        ultima = sb.tabelas[CONVERSA][-1]
        assert ultima["autor_id"] == DIRETORA["id"]
        assert ultima["origem"] == "app"
        assert ultima["texto"] == "Resposta: B) Quem presidiu a reunião"

    def test_a_resposta_livre_entra_na_conversa_com_o_texto(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()

        _responder(sb, DIRETORA, pergunta_id, monkeypatch, texto="Quem estiver de plantão.")

        ultima = sb.tabelas[CONVERSA][-1]
        assert (ultima["autor_id"], ultima["texto"]) == (DIRETORA["id"], "Resposta: Quem estiver de plantão.")

    def test_a_rota_devolve_o_cartao_respondido_e_a_mensagem_da_conversa(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()

        corpo = _responder(sb, DIRETORA, pergunta_id, monkeypatch, opcao="B").json()

        assert corpo["pergunta"]["id"] == pergunta_id
        assert corpo["pergunta"]["estado"] == "respondida"
        assert corpo["pergunta"]["resposta"]["opcao"] == "B"
        assert corpo["mensagem"]["autor"] == "Diretora Clínica"
        assert corpo["mensagem"]["texto"] == "Resposta: B) Quem presidiu a reunião"
        assert corpo["mensagem"]["minha"] is True

    def test_a_pergunta_respondida_fica_na_conversa_com_a_resposta(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()
        _responder(sb, DIRETORA, pergunta_id, monkeypatch, opcao="B")

        mensagens = _tela(sb, DIRETORA, monkeypatch).get(CONVERSA_DA_TELA).json()["mensagens"]

        [cartao] = [m["pergunta"] for m in mensagens if m["pergunta"]]
        assert cartao["estado"] == "respondida"
        assert cartao["resposta"]["opcao"] == "B"
        assert cartao["resposta"]["opcao_texto"] == "Quem presidiu a reunião"
        assert cartao["resposta"]["respondida_por"] == "Diretora Clínica"
        assert cartao["resposta"]["em_nome_de"] is None
        assert cartao["pode_responder"] is False
        assert mensagens[-1]["texto"] == "Resposta: B) Quem presidiu a reunião"


# ═══════════════════════════════════════════════════════════════════════════
# O Desenvolvedor registra no lugar do Destinatário
# ═══════════════════════════════════════════════════════════════════════════


class TestODesenvolvedorRegistra:
    def test_desenvolvedor_registra_a_resposta_no_lugar_do_destinatario_e_os_dois_nomes_ficam(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()

        resposta = _responder(sb, PEDRO, pergunta_id, monkeypatch, opcao="A")

        assert resposta.status_code == 200, resposta.text
        [pergunta] = sb.tabelas[TABELA]
        assert pergunta["estado"] == "respondida"
        assert (pergunta["respondida_por"], pergunta["respondida_em_nome_de"]) == (PEDRO["id"], DIRETORA["id"])
        ultima = sb.tabelas[CONVERSA][-1]
        assert ultima["autor_id"] == PEDRO["id"]
        assert ultima["texto"] == "Resposta em nome de Diretora Clínica: A) O diretor geral"

    def test_o_cartao_mostra_quem_registrou_e_em_nome_de_quem(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()
        _responder(sb, PEDRO, pergunta_id, monkeypatch, texto="Ela disse que é o diretor geral.")

        mensagens = _tela(sb, DIRETORA, monkeypatch).get(CONVERSA_DA_TELA).json()["mensagens"]

        [cartao] = [m["pergunta"] for m in mensagens if m["pergunta"]]
        assert cartao["resposta"]["respondida_por"] == "Pedro Rezende"
        assert cartao["resposta"]["em_nome_de"] == "Diretora Clínica"
        assert cartao["resposta"]["texto"] == "Ela disse que é o diretor geral."


# ═══════════════════════════════════════════════════════════════════════════
# Quem não responde
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemNaoResponde:
    def test_outro_super_admin_nao_responde_pela_rota_e_nada_muda(self, monkeypatch, emails):  # noqa: F811
        _, sb, pergunta_id = _uma_pergunta_aberta()
        conversa_antes = len(sb.tabelas[CONVERSA])
        emails_antes = len(emails)

        resposta = _responder(sb, DIRETOR, pergunta_id, monkeypatch, opcao="B")

        assert resposta.status_code == 403
        assert resposta.json() == {
            "detail": "Só quem recebeu a Pergunta, ou um Desenvolvedor no lugar dele, pode responder."
        }
        [pergunta] = sb.tabelas[TABELA]
        assert pergunta["estado"] == "aberta"
        assert pergunta.get("respondida_por") is None
        assert len(sb.tabelas[CONVERSA]) == conversa_antes
        assert len(emails) == emails_antes

    def test_o_cartao_diz_quem_pode_responder(self, monkeypatch):
        _, sb, _ = _uma_pergunta_aberta()

        def _pode(logado):
            mensagens = _tela(sb, logado, monkeypatch).get(CONVERSA_DA_TELA).json()["mensagens"]
            [cartao] = [m["pergunta"] for m in mensagens if m["pergunta"]]
            return cartao["pode_responder"]

        assert (_pode(DIRETORA), _pode(PEDRO), _pode(DIRETOR)) == (True, True, False)

    @pytest.mark.parametrize("estado", ["respondida", "resolvida", "cancelada"])
    def test_responder_pergunta_que_nao_esta_aberta_e_recusado(self, estado, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()
        sb.tabelas[TABELA][0]["estado"] = estado
        conversa_antes = len(sb.tabelas[CONVERSA])

        resposta = _responder(sb, DIRETORA, pergunta_id, monkeypatch, opcao="A")

        assert resposta.status_code == 409
        assert resposta.json() == {"detail": "Esta Pergunta já não espera resposta."}
        assert sb.tabelas[TABELA][0]["estado"] == estado
        assert sb.tabelas[TABELA][0].get("resposta_opcao") is None
        assert len(sb.tabelas[CONVERSA]) == conversa_antes

    def test_a_segunda_resposta_e_recusada_e_a_primeira_fica(self, monkeypatch):
        _, sb, pergunta_id = _uma_pergunta_aberta()
        _responder(sb, DIRETORA, pergunta_id, monkeypatch, opcao="B")

        segunda = _responder(sb, PEDRO, pergunta_id, monkeypatch, opcao="A")

        assert segunda.status_code == 409
        [pergunta] = sb.tabelas[TABELA]
        assert (pergunta["resposta_opcao"], pergunta["respondida_por"]) == ("B", DIRETORA["id"])

    def test_duas_respostas_ao_mesmo_tempo_so_a_primeira_grava(self, monkeypatch):
        """As duas leram a Pergunta aberta; a outra grava entre a leitura e a
        escrita desta, que é recusada sem sobrescrever nem escrever na Conversa."""
        _, sb, pergunta_id = _uma_pergunta_aberta()
        [linha] = sb.tabelas[TABELA]
        conversa_antes = len(sb.tabelas[CONVERSA])
        sb.ao_atualizar = lambda: linha.update(
            {"estado": "respondida", "resposta_opcao": "A", "respondida_por": PEDRO["id"]}
        )

        resposta = _responder(sb, DIRETORA, pergunta_id, monkeypatch, opcao="B")

        assert resposta.status_code == 409
        assert (linha["resposta_opcao"], linha["respondida_por"]) == ("A", PEDRO["id"])
        assert len(sb.tabelas[CONVERSA]) == conversa_antes

    def test_pergunta_que_nao_existe_e_404(self, monkeypatch):
        _, sb, _ = _uma_pergunta_aberta()

        resposta = _responder(sb, DIRETORA, "0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e", monkeypatch, opcao="A")

        assert resposta.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# A ponte lê a resposta, e nada vai ao GitHub
# ═══════════════════════════════════════════════════════════════════════════


class TestAPonte:
    def test_a_ponte_devolve_a_opcao_o_texto_quem_respondeu_e_quando(self, monkeypatch):
        ponte, sb, pergunta_id = _uma_pergunta_aberta()
        _responder(sb, PEDRO, pergunta_id, monkeypatch, opcao="B")

        corpo = _ler(ponte, pergunta_id).json()

        assert corpo["estado"] == "respondida"
        resposta = corpo["resposta"]
        assert (resposta["opcao"], resposta["opcao_texto"], resposta["texto"]) == (
            "B",
            "Quem presidiu a reunião",
            None,
        )
        assert (resposta["respondida_por"], resposta["em_nome_de"]) == ("Pedro Rezende", "Diretora Clínica")
        assert resposta["respondida_em"] == sb.tabelas[TABELA][0]["respondida_em"]

    def test_a_resposta_nao_vai_para_o_github(self, monkeypatch, chamadas_ao_github):
        _, sb, pergunta_id = _uma_pergunta_aberta()

        resposta = _responder(sb, DIRETORA, pergunta_id, monkeypatch, texto="Quem estiver de plantão.")

        assert resposta.status_code == 200, resposta.text
        assert chamadas_ao_github == []


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


class TestOKit:
    def test_o_kit_da_tecnologia_diz_que_a_pergunta_se_responde_no_cartao(self):
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")

        for trecho in (
            "você responde no próprio cartão",
            "uma das opções prontas",
            "o campo livre",
            "a sua resposta entra também na Conversa",
            "registrar a resposta no seu lugar",
        ):
            assert trecho in texto, trecho
        assert "Por enquanto o cartão só mostra a pergunta" not in texto
