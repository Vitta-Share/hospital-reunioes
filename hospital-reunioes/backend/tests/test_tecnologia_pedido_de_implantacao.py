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
from datetime import UTC, datetime, timedelta

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

    def test_o_github_recusando_deixa_o_pedido_criado_com_o_motivo_e_o_reenviar(self, monkeypatch, github):
        github["status"] = 403
        ponte, sb = _ponte()

        resposta = _criar(ponte)

        assert resposta.status_code == 201, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["estado"], pedido["fechamento_github"]) == ("aberta", "falhou")
        cartao = _tela(sb, DIRETORA, monkeypatch).get("/api/admin/tecnologia/perguntas/esperando").json()[0]
        assert cartao["fechamento"] == {"estado": "falhou", "motivo": "O GitHub não aceitou (GitHub respondeu 403)."}
        assert cartao["pode_reenviar"] is True

        github["status"] = 200
        github["chamadas"].clear()
        reenviado = _reenviar(sb, DIRETORA, pedido["id"], monkeypatch)

        assert reenviado.status_code == 200, reenviado.text
        assert reenviado.json()["fechamento"] == {"estado": "fechado", "motivo": None}
        assert reenviado.json()["estado"] == "aberta"
        assert _comentarios(github) == [COMENTARIO_DO_NASCIMENTO]
        assert _fechamentos(github) == [{"state": "closed", "state_reason": "completed"}]


# ═══════════════════════════════════════════════════════════════════════════
# O cartão na Esperando você, e o Concluir
# ═══════════════════════════════════════════════════════════════════════════


class TestCartao:
    def test_o_cartao_aparece_na_esperando_voce_com_os_checks(self, monkeypatch):
        _, sb, pedido_id = _uma_implantacao()
        _marcar(sb, DIRETORA, pedido_id, monkeypatch, 0)

        lista = _tela(sb, DIRETORA, monkeypatch).get("/api/admin/tecnologia/perguntas/esperando").json()

        [item] = lista
        assert (item["tipo"], item["assunto"], item["estado"]) == (
            "implantacao",
            "testar o anonimato do Canal de Conduta",
            "aberta",
        )
        assert [(p["texto"], p["marcado"]) for p in item["passos"]] == [
            (PASSOS[0], True),
            (PASSOS[1], False),
            (PASSOS[2], False),
        ]
        assert item["pode_responder"] is True

    def test_o_concluir_so_libera_com_todos_os_checks_marcados(self, monkeypatch, github):
        _, sb, pedido_id = _uma_implantacao()
        _marcar(sb, DIRETORA, pedido_id, monkeypatch, 0)
        _marcar(sb, DIRETORA, pedido_id, monkeypatch, 1)
        github["chamadas"].clear()

        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": tecnologia_perguntas.MOTIVO_FALTA_CHECK}
        assert sb.tabelas[TABELA][0]["estado"] == "aberta"
        assert github["chamadas"] == []


class TestConcluir:
    def test_concluir_comenta_na_issue_fechada_e_nao_chama_o_fechamento(self, monkeypatch, github):
        _, sb, pedido_id = _uma_implantacao()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        github["chamadas"].clear()
        monkeypatch.setattr(tecnologia_perguntas, "_agora", lambda: datetime(2026, 11, 22, 17, 30, tzinfo=UTC))

        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch, anotacao=ANOTACAO)

        assert resposta.status_code == 200, resposta.text
        assert _fechamentos(github) == []
        assert _comentarios(github) == [
            "<!-- pedido-da-vitta: implantacao-concluida -->\n"
            "Pedido de implantação concluído no app em 22/11 às 14:30, pelo Destinatário (Diretoria).\n"
            "\n"
            f"- [x] {PASSOS[0]}\n"
            f"- [x] {PASSOS[1]}\n"
            f"- [x] {PASSOS[2]}"
        ]
        assert all(f"/issues/{CARD}/comments" in url for _, url, _ in github["chamadas"])
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["estado"], pedido["concluida_como"], pedido["concluida_por"]) == (
            "concluida",
            "app",
            DIRETORA["id"],
        )
        # O fechamento é o do nascimento: o Concluir não o regrava.
        assert pedido["fechamento_github"] == "fechado"
        assert resposta.json()["pergunta"]["estado"] == "concluida"
        assert ("Pedido de implantação concluído: testar o anonimato do Canal de Conduta", "sistema") in [
            (m["texto"], m["origem"]) for m in sb.tabelas[CONVERSA]
        ]

    def test_o_comentario_da_conclusao_nao_leva_nome_nem_a_anotacao(self, monkeypatch, github):
        _, sb, pedido_id = _uma_implantacao()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        github["chamadas"].clear()

        _concluir(sb, DIRETORA, pedido_id, monkeypatch, anotacao=ANOTACAO)

        [comentario] = _comentarios(github)
        assert "Diretora Clínica" not in comentario
        assert "Fernanda" not in comentario

    def test_o_comentario_que_falha_nao_desfaz_a_conclusao(self, monkeypatch, github):
        _, sb, pedido_id = _uma_implantacao()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        github["chamadas"].clear()
        github["status"] = 502

        resposta = _concluir(sb, DIRETORA, pedido_id, monkeypatch)

        assert resposta.status_code == 200, resposta.text
        [pedido] = sb.tabelas[TABELA]
        assert (pedido["estado"], pedido["fechamento_github"]) == ("concluida", "fechado")
        assert _fechamentos(github) == []


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

    def test_o_card_reaberto_por_fora_nao_reabre_a_implantacao_concluida(self, monkeypatch, webhook):  # noqa: F811
        _, sb, pedido_id = _uma_implantacao()
        _marcar_todos(sb, DIRETORA, pedido_id, monkeypatch)
        _concluir(sb, DIRETORA, pedido_id, monkeypatch)
        antes = dict(sb.tabelas[TABELA][0])
        checks = len(sb.tabelas[CHECKS])

        webhook(sb, "reopened", numero=CARD)

        assert sb.tabelas[TABELA][0] == antes
        assert len(sb.tabelas[CHECKS]) == checks

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
