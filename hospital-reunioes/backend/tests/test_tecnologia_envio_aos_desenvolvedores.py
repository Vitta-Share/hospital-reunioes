"""O Envio aos desenvolvedores pela Conversa da Demanda (issue #2011, PRD #2007, ADR 0108, decisões 3 a 5).

O diretor escreve na Conversa da Demanda quantas mensagens quiser e, no fim,
aperta "Enviar para os desenvolvedores". O agente lê as mensagens dele desde o
último envio (com o card e a última mensagem de um Desenvolvedor como
contexto) e devolve "Entendi assim:" em tópicos. Só com o "Enviar" nasce o
Ajuste do plano: sub-issue `ready-for-human` do dono na issue-raiz, com a
interpretação e nunca a fala do diretor (o repositório é público). A conversa
ganha a linha "Enviado aos desenvolvedores", e o que vem depois entra no
próximo envio.

Tudo pela ROTA, com o modelo e o GitHub dublados no molde de
`test_tecnologia_revisao`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_planejamento_demanda import _ia  # noqa: E402
from test_tecnologia_chat import (  # noqa: E402
    _cenario,
    _chamadas,
    _integracao_configurada,  # noqa: F401
    _llm_em_mock,  # noqa: F401
    _reset_rate_limiter,  # noqa: F401
)
from test_tecnologia_vinculo import BASE, DIRETOR, PEDRO, _demanda, _GithubFalso, _issue, _pessoa  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import github_client, tecnologia_email  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

LUCAS = _pessoa("P4", "Lucas Sampaio", github_login="lucas-vitta")

DEMANDA = "d-1"
CONVERSA = f"{BASE}/chat/{DEMANDA}/conversa"
INTERPRETAR = f"{CONVERSA}/interpretar"
ENVIAR = f"{CONVERSA}/enviar"

MIGRATION = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "165_tecnologia_envio_aos_desenvolvedores.sql"
)

# A frase que o diretor escreve e que nunca pode chegar ao GitHub.
FALA_DO_DIRETOR = "Quero que a enfermeira Joana do terceiro andar consiga imprimir a escala sozinha"
INTERPRETACAO = {
    "topicos": ["A enfermagem imprime a escala sem pedir ajuda.", "O botão de imprimir fica na própria escala."],
    "cards": [{"numero": 901, "muda": "A parte da escala ganha o botão de imprimir."}],
}


@pytest.fixture(autouse=True)
def _sem_email(monkeypatch):
    """A mensagem da Conversa avisa por e-mail: o envio fica gravado aqui, e
    nenhum transporte de verdade entra no teste."""
    monkeypatch.setattr(tecnologia_email, "_enviar_email", lambda *a, **kw: True)
    monkeypatch.setattr(settings, "frontend_url", "https://app.hsm.test")


class _GithubDoAjuste(_GithubFalso):
    """O GitHub do Validar: a issue nova ganha `id`, e a ligação de sub-issue
    fica registrada (raiz, id da filha)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.sub_issues_ligadas: list[tuple[int, int]] = []

    def criar_issue(self, **kw):
        dados = super().criar_issue(**kw)
        dados["id"] = 70_000 + dados["number"]
        return dados

    def adicionar_sub_issue(self, raiz: int, sub_issue_id: int, *, projeto: str) -> None:
        self.sub_issues_ligadas.append((raiz, sub_issue_id))


def _card(**campos) -> dict:
    base = {
        "autor_id": DIRETOR["id"],
        "responsavel_id": PEDRO["id"],
        "github_issue_numero": 900,
        "titulo": "Escala da enfermagem",
        "o_que_muda": "A enfermagem monta a escala no app.",
        "partes": [{"numero": 901, "o_que_muda": "A escala na tela.", "situacao": "planejada"}],
    }
    base.update(campos)
    return _demanda(DEMANDA, **base)


def _montar(monkeypatch, *, logado=DIRETOR, demanda: dict | None = None, sb=None, gh=None):
    gh = gh or _GithubDoAjuste({900: _issue(900)}, proximo_numero=950)
    client, sb, gh = _cenario(
        monkeypatch,
        logado=logado,
        participantes=[PEDRO, DIRETOR, LUCAS],
        demandas=[demanda or _card()],
        supabase=sb,
        github=gh,
    )
    monkeypatch.setattr(github_client, "adicionar_sub_issue", gh.adicionar_sub_issue, raising=False)
    return client, sb, gh


def _escrever(client, texto: str):
    resposta = client.post(CONVERSA, json={"texto": texto})
    assert resposta.status_code == 201, resposta.text


def _pedido_ao_modelo(cliente) -> str:
    [chamada] = cliente.chamadas
    return chamada["messages"][0]["content"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. A migration
# ═══════════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_a_tabela_do_envio_nasce_com_rls_e_o_recibo_165(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        assert "CREATE TABLE IF NOT EXISTS tecnologia_envios_aos_desenvolvedores" in sql
        for coluna in ("demanda_id", "enviado_por", "topicos", "ate_mensagem_em", "ajuste_numero", "enviado_em"):
            assert re.search(rf"^\s+{coluna}\s", sql, re.MULTILINE), coluna
        assert "ALTER TABLE tecnologia_envios_aos_desenvolvedores ENABLE ROW LEVEL SECURITY;" in sql
        assert "CREATE POLICY" not in sql.upper()
        assert "'envio'" in sql
        assert sql.rstrip().endswith(
            "INSERT INTO migracoes_aplicadas (numero) VALUES (165) ON CONFLICT (numero) DO NOTHING;"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. O interpretar
# ═══════════════════════════════════════════════════════════════════════════


class TestInterpretar:
    def test_le_so_as_mensagens_do_diretor_e_devolve_o_entendi_assim(self, monkeypatch):
        diretor, sb, _ = _montar(monkeypatch)
        lucas, _, _ = _montar(monkeypatch, logado=LUCAS, sb=sb)
        _escrever(diretor, FALA_DO_DIRETOR)
        _escrever(lucas, "Posso pôr o botão na tela da escala?")
        cliente = _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        resposta = diretor.post(INTERPRETAR)

        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert corpo["topicos"] == INTERPRETACAO["topicos"]
        assert corpo["cards"] == INTERPRETACAO["cards"]
        pedido = _pedido_ao_modelo(cliente)
        mensagens_do_diretor = pedido.split("MENSAGENS DO DIRETOR")[1]
        assert FALA_DO_DIRETOR in mensagens_do_diretor
        assert "Posso pôr o botão" not in mensagens_do_diretor
        # A última mensagem do Desenvolvedor vai como contexto, antes.
        assert "Posso pôr o botão na tela da escala?" in pedido.split("MENSAGENS DO DIRETOR")[0]

    def test_sem_mensagem_nova_do_diretor_recusa_com_motivo_e_nao_chama_o_modelo(self, monkeypatch):
        diretor, sb, _ = _montar(monkeypatch)
        lucas, _, _ = _montar(monkeypatch, logado=LUCAS, sb=sb)
        _escrever(lucas, "Alguma novidade?")
        cliente = _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        resposta = diretor.post(INTERPRETAR)

        assert resposta.status_code == 422
        assert "mensagem" in resposta.json()["detail"].lower()
        assert cliente.chamadas == []

    def test_o_custo_do_modelo_fica_gravado_na_demanda(self, monkeypatch):
        diretor, sb, _ = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        assert diretor.post(INTERPRETAR).status_code == 200

        [chamada] = _chamadas(sb)
        assert chamada["demanda_id"] == DEMANDA
        assert chamada["passo"] == "envio"
        assert chamada["sucesso"] is True
        assert chamada["custo_usd"] > 0
        # E a conversa da Demanda mostra o custo somado, como nas outras.
        from app.services import custo_da_conversa

        assert custo_da_conversa.da_demanda(sb, DEMANDA)["custo_usd"] == chamada["custo_usd"]

    def test_a_falha_do_modelo_devolve_502_e_nada_muda(self, monkeypatch):
        diretor, sb, _ = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        _ia(monkeypatch, "isto não é JSON")

        resposta = diretor.post(INTERPRETAR)

        assert resposta.status_code == 502
        assert sb.tabelas.get("tecnologia_envios_aos_desenvolvedores", []) == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. Quem envia
# ═══════════════════════════════════════════════════════════════════════════


class TestQuemEnvia:
    @pytest.mark.parametrize("rota", [INTERPRETAR, ENVIAR])
    def test_desenvolvedor_recebe_403_nas_duas_rotas(self, monkeypatch, rota):
        lucas, _, gh = _montar(monkeypatch, logado=LUCAS)
        cliente = _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        resposta = lucas.post(rota, json={"envio_id": "qualquer"})

        assert resposta.status_code == 403
        assert cliente.chamadas == []
        assert gh.criadas == []

    @pytest.mark.parametrize("rota", [INTERPRETAR, ENVIAR])
    def test_demanda_sem_issue_vinculada_e_recusada_com_motivo(self, monkeypatch, rota):
        diretor, _, gh = _montar(monkeypatch, demanda=_card(github_issue_numero=None))
        _escrever(diretor, FALA_DO_DIRETOR)
        cliente = _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))

        resposta = diretor.post(rota, json={"envio_id": "qualquer"})

        assert resposta.status_code == 422
        assert "card" in resposta.json()["detail"].lower()
        assert cliente.chamadas == []
        assert gh.criadas == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. O enviar abre o Ajuste do plano
# ═══════════════════════════════════════════════════════════════════════════


def _interpretado(monkeypatch, client, *, interpretacao=INTERPRETACAO) -> str:
    _ia(monkeypatch, json.dumps(interpretacao, ensure_ascii=False))
    resposta = client.post(INTERPRETAR)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["id"]


class TestEnviar:
    def test_cria_a_sub_issue_ready_for_human_do_dono_na_raiz_com_os_dois_marcadores(self, monkeypatch):
        diretor, _, gh = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        envio_id = _interpretado(monkeypatch, diretor)

        resposta = diretor.post(ENVIAR, json={"envio_id": envio_id})

        assert resposta.status_code == 200, resposta.text
        [ajuste] = gh.criadas
        assert ajuste["labels"] == ["ready-for-human"]
        assert ajuste["assignees"] == [settings.github_login_dono]
        assert "<!-- ajuste-do-plano: 900 -->" in ajuste["corpo"]
        assert "<!-- envio-aos-desenvolvedores -->" in ajuste["corpo"]
        assert gh.sub_issues_ligadas == [(900, 70_950)]
        # A interpretação aprovada e o que muda em cada card, com o número.
        assert "A enfermagem imprime a escala sem pedir ajuda." in ajuste["corpo"]
        assert "#901" in ajuste["corpo"]
        assert "/grill-with-docs" in ajuste["corpo"]

    def test_o_corpo_do_ajuste_nao_contem_trecho_literal_da_fala_do_diretor(self, monkeypatch):
        diretor, _, gh = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        _escrever(diretor, "E também o relatório mensal de horas extras precisa sair em PDF")
        envio_id = _interpretado(monkeypatch, diretor)

        assert diretor.post(ENVIAR, json={"envio_id": envio_id}).status_code == 200

        [ajuste] = gh.criadas
        texto = f"{ajuste['titulo']}\n{ajuste['corpo']}"
        for fala in (FALA_DO_DIRETOR, "E também o relatório mensal de horas extras precisa sair em PDF"):
            palavras = fala.split()
            # Nenhum trecho de cinco palavras seguidas da fala entra no Ajuste.
            for i in range(len(palavras) - 4):
                trecho = " ".join(palavras[i : i + 5])
                assert trecho not in texto, f"o Ajuste cita a fala do diretor: {trecho!r}"

    def test_o_texto_da_interpretacao_passa_pela_peneira_e_sem_travessao(self, monkeypatch):
        diretor, _, gh = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        envio_id = _interpretado(
            monkeypatch,
            diretor,
            interpretacao={"topicos": ["Imprimir a escala — avisar @lucas-vitta"], "cards": []},
        )

        assert diretor.post(ENVIAR, json={"envio_id": envio_id}).status_code == 200

        [ajuste] = gh.criadas
        assert "—" not in ajuste["corpo"]
        assert "@lucas-vitta" not in ajuste["corpo"]

    def test_dois_cliques_em_enviar_abrem_um_ajuste_so(self, monkeypatch):
        diretor, sb, gh = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        envio_id = _interpretado(monkeypatch, diretor)
        segunda = []

        def o_segundo_clique_entra_aqui():
            outro, _, _ = _montar(monkeypatch, sb=sb, gh=gh)
            segunda.append(outro.post(ENVIAR, json={"envio_id": envio_id}))

        sb.ao_atualizar = o_segundo_clique_entra_aqui

        primeira = diretor.post(ENVIAR, json={"envio_id": envio_id})
        depois = diretor.post(ENVIAR, json={"envio_id": envio_id})

        assert sorted([primeira.status_code, segunda[0].status_code]) == [200, 422]
        assert depois.status_code == 422
        assert len(gh.criadas) == 1

    def test_duas_interpretacoes_das_mesmas_mensagens_abrem_um_ajuste_so(self, monkeypatch):
        """Duas abas: cada uma interpretou e cada uma clica em Enviar."""
        diretor, _, gh = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        primeira = _interpretado(monkeypatch, diretor)
        segunda = _interpretado(monkeypatch, diretor)

        assert diretor.post(ENVIAR, json={"envio_id": primeira}).status_code == 200
        assert diretor.post(ENVIAR, json={"envio_id": segunda}).status_code == 422
        assert len(gh.criadas) == 1

    def test_a_interpretacao_mais_antiga_nao_sai_depois_da_mais_nova(self, monkeypatch):
        """Duas abas (ou dois diretores no card de Origem Vitta): A interpretou,
        chegou mensagem nova, B interpretou e saiu. A ainda na tela não abre o
        segundo Ajuste com mensagens que já foram."""
        diretor, _, gh = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        antiga = _interpretado(monkeypatch, diretor)
        _escrever(diretor, "E também o relatório mensal de horas extras precisa sair em PDF")
        nova = _interpretado(monkeypatch, diretor)

        assert diretor.post(ENVIAR, json={"envio_id": nova}).status_code == 200
        velha = diretor.post(ENVIAR, json={"envio_id": antiga})

        assert velha.status_code == 422
        assert len(gh.criadas) == 1

    def test_a_falha_do_github_devolve_o_motivo_e_o_tente_de_novo_envia(self, monkeypatch):
        diretor, _, gh = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        envio_id = _interpretado(monkeypatch, diretor)
        gh.erro_ao_criar = github_client.GithubIndisponivelError("timeout")

        falhou = diretor.post(ENVIAR, json={"envio_id": envio_id})

        assert falhou.status_code == 502
        assert "tente de novo" in falhou.json()["detail"].lower()
        gh.erro_ao_criar = None
        assert diretor.post(ENVIAR, json={"envio_id": envio_id}).status_code == 200
        assert len(gh.criadas) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. A linha do envio na conversa e o próximo envio
# ═══════════════════════════════════════════════════════════════════════════


class TestLinhaDoEnvio:
    def test_a_conversa_mostra_a_linha_com_data_hora_e_topicos(self, monkeypatch):
        diretor, _, _ = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        envio_id = _interpretado(monkeypatch, diretor)

        linha = diretor.post(ENVIAR, json={"envio_id": envio_id}).json()

        assert linha["sistema"] is True
        assert re.match(r"^Enviado aos desenvolvedores em \d{2}/\d{2}/\d{4}, às \d{2}:\d{2}", linha["texto"])
        for topico in INTERPRETACAO["topicos"]:
            assert topico in linha["texto"]
        mensagens = diretor.get(CONVERSA).json()["mensagens"]
        assert [m["sistema"] for m in mensagens] == [False, True]
        assert mensagens[-1]["texto"] == linha["texto"]

    def test_a_mensagem_seguinte_entra_no_proximo_envio_e_a_de_antes_nao(self, monkeypatch):
        diretor, _, _ = _montar(monkeypatch)
        _escrever(diretor, FALA_DO_DIRETOR)
        envio_id = _interpretado(monkeypatch, diretor)
        assert diretor.post(ENVIAR, json={"envio_id": envio_id}).status_code == 200

        # Logo depois do envio, nada novo: o botão desliga e o interpretar recusa.
        assert diretor.get(CONVERSA).json()["envio"] == {"mensagens_novas": 0}
        assert diretor.post(INTERPRETAR).status_code == 422

        _escrever(diretor, "Mais uma coisa: a escala de domingo é separada")
        assert diretor.get(CONVERSA).json()["envio"] == {"mensagens_novas": 1}
        cliente = _ia(monkeypatch, json.dumps(INTERPRETACAO, ensure_ascii=False))
        assert diretor.post(INTERPRETAR).status_code == 200

        mensagens_do_diretor = _pedido_ao_modelo(cliente).split("MENSAGENS DO DIRETOR")[1]
        assert "a escala de domingo é separada" in mensagens_do_diretor
        assert FALA_DO_DIRETOR not in mensagens_do_diretor
        assert "Enviado aos desenvolvedores" not in mensagens_do_diretor


# ═══════════════════════════════════════════════════════════════════════════
# 6. O botão: quem vê e quando liga
# ═══════════════════════════════════════════════════════════════════════════


class TestOBotao:
    def test_o_diretor_ve_o_envio_desligado_sem_mensagem_e_ligado_com_mensagem(self, monkeypatch):
        diretor, _, _ = _montar(monkeypatch)

        assert diretor.get(CONVERSA).json()["envio"] == {"mensagens_novas": 0}
        _escrever(diretor, FALA_DO_DIRETOR)
        assert diretor.get(CONVERSA).json()["envio"] == {"mensagens_novas": 1}

    def test_o_desenvolvedor_nao_ve_o_envio(self, monkeypatch):
        lucas, _, _ = _montar(monkeypatch, logado=LUCAS)

        assert lucas.get(CONVERSA).json()["envio"] is None

    def test_demanda_sem_issue_nao_mostra_o_envio(self, monkeypatch):
        diretor, _, _ = _montar(monkeypatch, demanda=_card(github_issue_numero=None))

        assert diretor.get(CONVERSA).json()["envio"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 7. O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


class TestKit:
    def test_o_texto_do_produto_tecnologia_diz_o_envio_aos_desenvolvedores(self):
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")
        assert "Enviar para os desenvolvedores" in texto
        assert "Entendi assim:" in texto
        assert "Enviado aos desenvolvedores" in texto
        assert "a IA não lê nem responde ali" not in texto
