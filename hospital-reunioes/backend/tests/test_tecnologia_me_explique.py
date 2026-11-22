"""O Me explique no cartão da Pergunta da Vitta (issue #2122, PRD #2112, ADR
0109, decisão 8).

O botão abre uma conversa particular com o Assistente de Tecnologia, uma por
Pergunta e por pessoa, que já começa com a Demanda e a Pergunta no contexto.
O Assistente explica na língua do Kit e propõe um rascunho de resposta. Nada
daqui entra na Conversa da Demanda, cria resposta ou vai ao GitHub. O custo
entra na conta do Assistente, no modelo padrão.

Pela ROTA de verdade, com o Supabase em memória de `test_tecnologia_vinculo` e
o modelo trocado pelo dublê dos testes do Assistente (`_ia`).
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_planejamento_demanda import _ia, _llm_em_mock  # noqa: E402, F401
from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    CONVERSA,
    DIRETOR,
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

from app.config import settings  # noqa: E402
from app.services import github_client  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

CONVERSAS = "tecnologia_conversas_do_me_explique"
CHAMADAS = "tecnologia_chamadas_ia"

EXPLICACAO = "A Vitta quer saber quem assina a ata quando a diretora clínica não está na reunião."
RASCUNHO = "Quem presidiu a reunião assina."


def _url(pergunta_id: str) -> str:
    return f"/api/admin/tecnologia/perguntas/{pergunta_id}/me-explique"


def _fala(mensagem: str = EXPLICACAO, rascunho: str | None = RASCUNHO) -> str:
    return json.dumps({"mensagem": mensagem, "rascunho": rascunho}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def chamadas_ao_github(monkeypatch) -> list[tuple]:
    """Toda ida ao GitHub fica gravada aqui, em vez de sair para a rede."""
    chamadas: list[tuple] = []

    def _gravar(*a, **kw):
        chamadas.append((a, kw))
        raise AssertionError("O Me explique foi ao GitHub.")

    monkeypatch.setattr(github_client.httpx, "request", _gravar)
    return chamadas


def _uma_pergunta():
    ponte, sb = _ponte()
    pergunta_id = _criar(ponte).json()["id"]
    return sb, pergunta_id


def _abrir(sb, logado, pergunta_id, monkeypatch, **corpo):
    return _tela(sb, logado, monkeypatch).post(_url(pergunta_id), json=corpo)


def _ler(sb, logado, pergunta_id, monkeypatch):
    return _tela(sb, logado, monkeypatch).get(_url(pergunta_id))


def _pedido_ao_modelo(cliente) -> str:
    """O texto que variou na chamada: o último pedido da pessoa ao modelo."""
    conteudo = cliente.chamadas[-1]["messages"][0]["content"]
    return conteudo if isinstance(conteudo, str) else "".join(b.get("text", "") for b in conteudo)


# ═══════════════════════════════════════════════════════════════════════════
# O botão abre a conversa já com a explicação
# ═══════════════════════════════════════════════════════════════════════════


class TestAbrir:
    def test_o_botao_abre_a_conversa_com_a_explicacao_da_demanda_e_da_pergunta(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        cliente = _ia(monkeypatch, _fala())

        resposta = _abrir(sb, DIRETORA, pergunta_id, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["mensagens"] == [{"papel": "assistente", "texto": EXPLICACAO, "rascunho": RASCUNHO}]
        pedido = _pedido_ao_modelo(cliente)
        assert "A Ata assinada no app" in pedido
        assert "Quem assina a Ata em nome da diretoria quando a senhora não está?" in pedido
        assert "A tela de assinatura da Ata espera essa regra para sair." in pedido
        assert "Quem presidiu a reunião" in pedido

    def test_sem_ia_configurada_o_botao_responde_com_o_aviso_do_mock(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()

        resposta = _abrir(sb, DIRETORA, pergunta_id, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        [fala] = resposta.json()["mensagens"]
        assert fala["texto"].startswith("[MOCK]")

    def test_falha_do_modelo_e_502_e_nada_fica_gravado(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        _ia(monkeypatch, "isto não é JSON")

        resposta = _abrir(sb, DIRETORA, pergunta_id, monkeypatch)

        assert resposta.status_code == 502
        assert resposta.json() == {"detail": "O assistente não conseguiu responder agora. Tente de novo."}
        assert sb.tabelas.get(CONVERSAS, []) == []

    def test_quem_nao_ve_a_demanda_nem_recebeu_a_pergunta_nao_abre(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        sb.tabelas["tecnologia_demandas"][0]["origem"] = None
        cliente = _ia(monkeypatch, _fala())

        resposta = _abrir(sb, DIRETOR, pergunta_id, monkeypatch)

        assert resposta.status_code == 404
        assert cliente.chamadas == []


# ═══════════════════════════════════════════════════════════════════════════
# A pessoa pergunta e o Assistente responde sem jargão do repositório
# ═══════════════════════════════════════════════════════════════════════════


class TestPerguntar:
    def test_a_pessoa_pergunta_e_recebe_resposta_sem_numero_de_issue_label_nem_tabela(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        _ia(monkeypatch, _fala())
        _abrir(sb, DIRETORA, pergunta_id, monkeypatch)
        cliente = _ia(
            monkeypatch,
            _fala(
                "Isso está na issue #2116 (#2119), com a label ready-for-agent, "
                "e fica gravado na `tecnologia_perguntas`. A ata sai no mesmo dia.",
                rascunho=None,
            ),
        )

        resposta = _abrir(sb, DIRETORA, pergunta_id, monkeypatch, texto="Isso muda a ata de ontem?")

        assert resposta.status_code == 200, resposta.text
        pessoa, assistente = resposta.json()["mensagens"][1:]
        assert pessoa == {"papel": "pessoa", "texto": "Isso muda a ata de ontem?", "rascunho": None}
        assert assistente["texto"] == "Isso está na issue, com a label, e fica gravado na. A ata sai no mesmo dia."
        assert assistente["rascunho"] is None
        pedido = _pedido_ao_modelo(cliente)
        assert "Pessoa: Isso muda a ata de ontem?" in pedido
        assert EXPLICACAO in pedido
        # O número do card não entra no contexto: a fala é para quem não é da Vitta.
        assert "1700" not in pedido

    def test_o_rascunho_tambem_sai_sem_jargao(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        _ia(monkeypatch, _fala(rascunho="Quem presidiu assina, como no #2116."))

        resposta = _abrir(sb, DIRETORA, pergunta_id, monkeypatch)

        assert resposta.json()["mensagens"][0]["rascunho"] == "Quem presidiu assina, como no."


# ═══════════════════════════════════════════════════════════════════════════
# Nenhuma resposta sem o clique de enviar, e nada na Conversa nem no GitHub
# ═══════════════════════════════════════════════════════════════════════════


class TestNadaSaiDaqui:
    def test_o_me_explique_nao_cria_resposta_nem_mexe_na_pergunta(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        [pergunta] = sb.tabelas[TABELA]
        antes = dict(pergunta)
        _ia(monkeypatch, _fala())

        _abrir(sb, DIRETORA, pergunta_id, monkeypatch)
        _abrir(sb, DIRETORA, pergunta_id, monkeypatch, texto="Pode responder por mim que é a B.")

        assert pergunta == antes
        assert pergunta["estado"] == "aberta"
        assert pergunta.get("respondida_em") is None

    def test_nada_do_me_explique_entra_na_conversa_da_demanda_nem_vai_ao_github(self, monkeypatch, chamadas_ao_github):
        sb, pergunta_id = _uma_pergunta()
        conversa_antes = [dict(linha) for linha in sb.tabelas[CONVERSA]]
        avisos_antes = len(sb.tabelas.get("notificacoes", []))
        _ia(monkeypatch, _fala())

        _abrir(sb, DIRETORA, pergunta_id, monkeypatch)
        _abrir(sb, DIRETORA, pergunta_id, monkeypatch, texto="E se eu não souber?")

        assert sb.tabelas[CONVERSA] == conversa_antes
        assert len(sb.tabelas.get("notificacoes", [])) == avisos_antes
        assert chamadas_ao_github == []
        assert len(sb.tabelas[CONVERSAS]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# A conversa é de uma pessoa só
# ═══════════════════════════════════════════════════════════════════════════


class TestParticular:
    def test_a_conversa_de_uma_pessoa_nao_aparece_para_outra_nem_para_o_desenvolvedor(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        _ia(monkeypatch, _fala())
        _abrir(sb, DIRETORA, pergunta_id, monkeypatch, texto="Segredo da diretora clínica")

        do_diretor = _ler(sb, DIRETOR, pergunta_id, monkeypatch)
        do_desenvolvedor = _ler(sb, PEDRO, pergunta_id, monkeypatch)

        assert (do_diretor.status_code, do_diretor.json()) == (200, {"mensagens": []})
        assert (do_desenvolvedor.status_code, do_desenvolvedor.json()) == (200, {"mensagens": []})

    def test_outra_pessoa_abre_a_propria_conversa_sem_a_fala_da_primeira(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        _ia(monkeypatch, _fala())
        _abrir(sb, DIRETORA, pergunta_id, monkeypatch, texto="Segredo da diretora clínica")
        cliente = _ia(monkeypatch, _fala("Outra explicação."))

        resposta = _abrir(sb, DIRETOR, pergunta_id, monkeypatch)

        assert [m["texto"] for m in resposta.json()["mensagens"]] == ["Outra explicação."]
        assert "Segredo da diretora clínica" not in _pedido_ao_modelo(cliente)
        assert sorted(linha["participante_id"] for linha in sb.tabelas[CONVERSAS]) == [DIRETOR["id"], DIRETORA["id"]]


# ═══════════════════════════════════════════════════════════════════════════
# A conversa persiste
# ═══════════════════════════════════════════════════════════════════════════


class TestPersiste:
    def test_reabrir_o_me_explique_da_mesma_pergunta_mostra_o_que_ja_foi_dito_sem_chamar_a_ia(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        cliente = _ia(monkeypatch, _fala())
        _abrir(sb, DIRETORA, pergunta_id, monkeypatch)
        _abrir(sb, DIRETORA, pergunta_id, monkeypatch, texto="E se eu não souber?")
        chamadas = len(cliente.chamadas)

        lida = _ler(sb, DIRETORA, pergunta_id, monkeypatch)
        reaberta = _abrir(sb, DIRETORA, pergunta_id, monkeypatch)

        textos = [EXPLICACAO, "E se eu não souber?", EXPLICACAO]
        assert [m["texto"] for m in lida.json()["mensagens"]] == textos
        assert [m["texto"] for m in reaberta.json()["mensagens"]] == textos
        assert len(cliente.chamadas) == chamadas


# ═══════════════════════════════════════════════════════════════════════════
# O custo entra na conta do Assistente
# ═══════════════════════════════════════════════════════════════════════════


class TestCusto:
    def test_o_custo_da_chamada_entra_na_conta_do_assistente_no_modelo_padrao(self, monkeypatch):
        sb, pergunta_id = _uma_pergunta()
        _ia(monkeypatch, _fala())

        _abrir(sb, DIRETORA, pergunta_id, monkeypatch)

        [chamada] = sb.tabelas[CHAMADAS]
        assert chamada["demanda_id"] == sb.tabelas[TABELA][0]["demanda_id"]
        assert chamada["passo"] == "pergunta"
        assert chamada["modelo"] == settings.llm_model_planejamento
        assert chamada["sucesso"] is True
        assert chamada["tokens_entrada"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_do_produto_tecnologia_diz_o_me_explique():
    kit = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")

    assert "**Me explique**" in kit
    assert "A conversa com o Assistente no Me explique é só sua" in kit
    assert "Usar este rascunho" in kit
