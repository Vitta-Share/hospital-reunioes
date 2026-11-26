"""O Pedido de implantação (issue #2207, PRD #2205, ADR 0111).

O terceiro tipo do Pedido da Vitta: o que o hospital faz depois que o código
sobe (teste de aceite, configuração, abertura, treinamento). Nasce pela ponte,
só para o card com a label `implantacao`, e o app fecha o card na hora como
concluído, com o comentário fixo "Virou Pedido de implantação no app". Se o
GitHub recusa, o Pedido nasce assim mesmo e o cartão mostra o motivo com o
Reenviar. O cartão é o do Passo a passo (passos, checks, Concluir só com
todos marcados), mas o Concluir só comenta na issue fechada, sem nunca chamar
o fechamento, e o Pedido não acompanha o GitHub (ADR 0111, decisão 7).

Pela ROTA de verdade (ponte, tela e webhook), com o Supabase em memória e o
transporte do GitHub dublado.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_kit_conhecimento import ARQUIVO_DA_ABA  # noqa: E402
from test_kit_conhecimento import _texto as _texto_do_kit  # noqa: E402
from test_tecnologia_passo_a_passo_da_vitta import (  # noqa: E402, F401
    CHECKS,
    CRIAR,
    PASSO_A_PASSO,
    _comentarios,
    _concluir,
    _fechamentos,
    _marcar,
    _reenviar,
    emails,
    webhook,
)
from test_tecnologia_pergunta_da_vitta import (  # noqa: E402, F401
    CHAVE,
    CONVERSA,
    DIRETORA,
    QUATRO_LINHAS,
    TABELA,
    _ler,
    _ponte,
    _tela,
    _zera_o_limitador,
    chave_configurada,
)
from test_tecnologia_vinculo import _integracao_configurada  # noqa: E402, F401

from app.services import github_client, tecnologia_perguntas  # noqa: E402

CARD = 1853

PASSOS = [
    "Escolha quem do hospital vai testar o Canal de Conduta e mande o link para essa pessoa.",
    "Peça que ela faça um relato de teste sem se identificar.",
    "Como saber que acabou: o relato de teste aparece na lista do Canal sem o nome de quem relatou.",
]
IMPLANTACAO = {
    "github_login": "pedrorezendefig",
    "tipo": "implantacao",
    "destinatario_id": DIRETORA["id"],
    "assunto": "testar o anonimato do Canal de Conduta",
    "texto": "Teste o Canal de Conduta com alguém do hospital antes de divulgar.",
    **QUATRO_LINHAS,
    "passos": PASSOS,
    "card_numero": CARD,
}

# A anotação de quem concluiu: fica só no app, nunca vai para a issue.
ANOTACAO = "A Dra. Fernanda testou pelo celular."

COMENTARIO_DO_NASCIMENTO = "<!-- pedido-da-vitta: virou-implantacao -->\nVirou Pedido de implantação no app."


@pytest.fixture(autouse=True)
def github(monkeypatch) -> dict:
    """O transporte do GitHub: a leitura do card devolve as `labels` que o
    teste puser; o resto grava a chamada e responde `status` (200 de saída)."""
    estado: dict = {"chamadas": [], "status": 200, "labels": ["implantacao", "ready-for-human"]}

    def _responder(metodo, url, *, headers=None, json=None, timeout=None):
        estado["chamadas"].append((metodo, url, json))
        if metodo == "GET":
            corpo = {"number": CARD, "state": "open", "labels": [{"name": nome} for nome in estado["labels"]]}
            return httpx.Response(200, json=corpo, request=httpx.Request(metodo, url))
        return httpx.Response(estado["status"], json={"number": CARD}, request=httpx.Request(metodo, url))

    monkeypatch.setattr(github_client.httpx, "request", _responder)
    return estado


def _criar(cliente, **campos):
    return cliente.post(CRIAR, json={**IMPLANTACAO, **campos}, headers={"X-API-Key": CHAVE})


def _uma_implantacao(**campos):
    ponte, sb = _ponte()
    resposta = _criar(ponte, **campos)
    assert resposta.status_code == 201, resposta.text
    return ponte, sb, resposta.json()["id"]


def _marcar_todos(sb, logado, pedido_id, monkeypatch):
    for passo in range(len(PASSOS)):
        assert _marcar(sb, logado, pedido_id, monkeypatch, passo).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Nasce pela ponte, só com a label
# ═══════════════════════════════════════════════════════════════════════════


class TestNascePelaPonte:
    def test_a_ponte_cria_o_pedido_de_implantacao_para_o_card_com_a_label(self, github):
        ponte, sb = _ponte()

        resposta = _criar(ponte)

        assert resposta.status_code == 201, resposta.text
        assert resposta.json()["tipo"] == "implantacao"
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["tipo"], pedido["estado"]) == ("implantacao", "aberta")
        assert pedido["passos"] == PASSOS
        assert (pedido["card_projeto"], pedido["card_numero"]) == ("hospital", CARD)
        assert ("GET", f"https://api.github.com/repos/pedrorezendefig/hospital-reunioes/issues/{CARD}", None) in [
            (m, u, j) for m, u, j in github["chamadas"]
        ]

    def test_o_card_sem_a_label_e_recusado_com_o_motivo_e_nada_e_gravado(self, github, emails):  # noqa: F811
        github["labels"] = ["ready-for-human"]
        ponte, sb = _ponte()

        resposta = _criar(ponte)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_SEM_LABEL_DE_IMPLANTACAO}
        assert "implantacao" in resposta.json()["detail"]
        assert sb.tabelas[TABELA] == []
        assert sb.tabelas[CONVERSA] == []
        assert emails == []
        assert _fechamentos(github) == []

    def test_a_conversa_ganha_a_linha_do_pedido_de_implantacao_aberto(self):
        _, sb, _ = _uma_implantacao()

        assert (
            sb.tabelas[CONVERSA][-1]["texto"] == "Pedido de implantação aberto: testar o anonimato do Canal de Conduta"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Nascer fecha o card
# ═══════════════════════════════════════════════════════════════════════════


class TestNascerFechaOCard:
    def test_criar_fecha_o_card_como_concluido_com_o_comentario_fixo(self, github):
        _, sb, _ = _uma_implantacao()

        assert _comentarios(github) == [COMENTARIO_DO_NASCIMENTO]
        assert _fechamentos(github) == [{"state": "closed", "state_reason": "completed"}]
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["estado"], pedido["fechamento_github"]) == ("aberta", "fechado")


# ═══════════════════════════════════════════════════════════════════════════
# O cartão na Esperando você, e o Concluir
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# O webhook não mexe no Pedido de implantação
# ═══════════════════════════════════════════════════════════════════════════


class TestWebhook:
    def test_o_card_fechado_por_fora_nao_muda_o_pedido_de_implantacao(self, webhook):  # noqa: F811
        """O próprio fechamento do nascimento volta pelo webhook como
        `closed completed`: o Pedido segue aberto, esperando o hospital."""
        _, sb, _ = _uma_implantacao()
        antes = dict(sb.tabelas[TABELA][0])
        conversa = len(sb.tabelas[CONVERSA])

        resposta = webhook(sb, "closed", motivo="completed", numero=CARD)

        assert resposta.status_code == 200, resposta.text
        assert sb.tabelas[TABELA][0] == antes
        assert len(sb.tabelas[CONVERSA]) == conversa

    def test_o_mesmo_evento_continua_mudando_o_passo_a_passo(self, webhook):  # noqa: F811
        ponte, sb = _ponte()
        criado = ponte.post(CRIAR, json={**PASSO_A_PASSO, "card_numero": CARD}, headers={"X-API-Key": CHAVE})
        assert criado.status_code == 201, criado.text

        webhook(sb, "closed", motivo="completed", numero=CARD)

        [pedido] = sb.tabelas[TABELA]
        assert (pedido["tipo"], pedido["estado"], pedido["concluida_como"]) == ("passo_a_passo", "concluida", "github")


# ═══════════════════════════════════════════════════════════════════════════
# O lembrete e a leitura pela ponte
# ═══════════════════════════════════════════════════════════════════════════


class TestLembrete:
    def test_o_pedido_de_implantacao_aberto_ha_3_dias_e_lembrado_uma_vez(self, emails):  # noqa: F811
        _, sb, _ = _uma_implantacao()
        sb.tabelas.pop("notificacoes", None)
        emails.clear()
        criado = datetime.fromisoformat(sb.tabelas[TABELA][0]["criado_em"].replace("Z", "+00:00"))

        assert tecnologia_perguntas.lembrar(sb, criado + timedelta(days=2, hours=23)) == 0
        assert tecnologia_perguntas.lembrar(sb, criado + timedelta(days=3)) == 1
        assert tecnologia_perguntas.lembrar(sb, criado + timedelta(days=4)) == 0

        [sino] = sb.tabelas["notificacoes"]
        assert (sino["destinatario_id"], sino["mensagem"]) == (DIRETORA["id"], "testar o anonimato do Canal de Conduta")
        assert len(emails) == 1


class TestLer:
    def test_ler_pela_ponte_devolve_o_tipo_o_card_e_o_fechamento(self):
        ponte, _, pedido_id = _uma_implantacao()

        corpo = _ler(ponte, pedido_id).json()

        assert (corpo["tipo"], corpo["estado"]) == ("implantacao", "aberta")
        assert corpo["card"] == {"projeto": "hospital", "numero": CARD}
        assert corpo["fechamento"] == {"estado": "fechado", "motivo": None}


# ═══════════════════════════════════════════════════════════════════════════
# O que falta para usar (issue #2213, ADR 0111, decisão 11)
# ═══════════════════════════════════════════════════════════════════════════

# A Demanda dos testes é a da issue-raiz 1700 do Hospital: o PRD dela.
FALTA = "/api/automacao/tecnologia/projetos/hospital/issues/1700/implantacao"


def _falta(ponte, caminho=FALTA):
    return ponte.get(caminho, headers={"X-API-Key": CHAVE})


class TestOQueFaltaParaUsar:
    """O `/mensagem-prd` lê pela ponte os Pedidos de implantação abertos da
    Demanda do PRD para escrever "Para começar a usar, falta: ..."."""

    def test_a_ponte_devolve_so_os_pedidos_de_implantacao_abertos_da_demanda_do_prd(self):
        ponte, sb, aberto = _uma_implantacao()
        concluido = _criar(ponte, assunto="treinar a recepção no Canal de Conduta").json()["id"]
        next(p for p in sb.tabelas[TABELA] if p["id"] == concluido)["estado"] = "concluida"
        assert ponte.post(CRIAR, json=PASSO_A_PASSO, headers={"X-API-Key": CHAVE}).status_code == 201

        resposta = _falta(ponte)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {
            "pedidos": [{"id": aberto, "assunto": "testar o anonimato do Canal de Conduta"}],
        }

    def test_a_demanda_sem_pedido_de_implantacao_aberto_devolve_a_lista_vazia(self):
        ponte, _ = _ponte()

        resposta = _falta(ponte)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {"pedidos": []}

    def test_o_prd_sem_demanda_e_404(self):
        ponte, _ = _ponte()

        resposta = _falta(ponte, "/api/automacao/tecnologia/projetos/hospital/issues/9999/implantacao")

        assert resposta.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento do Assistente
# ═══════════════════════════════════════════════════════════════════════════


class TestKit:
    """O texto do Produto Tecnologia é o que o Assistente lê para responder
    ao diretor: ele diz o comportamento novo."""

    @pytest.fixture
    def texto(self) -> str:
        return _texto_do_kit(ARQUIVO_DA_ABA)

    @pytest.mark.parametrize(
        "frase",
        [
            "Pedido de implantação",
            "o card da entrega fecha na hora",
            "não reabre nada",
            "se a Vitta fechar ou reabrir o card por fora, o pedido de implantação não muda",
        ],
    )
    def test_o_kit_diz_como_o_pedido_de_implantacao_funciona(self, texto, frase):
        assert frase in texto
