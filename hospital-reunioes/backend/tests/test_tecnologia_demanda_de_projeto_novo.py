"""A Demanda de um Projeto novo (issue #1967, PRD #1964).

A ponte de automação criava a Demanda do PRD de um Projeto que o app ainda não
conhece (o PedroOS, por exemplo), pelo par projeto mais número da issue: Origem
Vitta, com o nome do Projeto, o título e o link do PRD. Desde a issue #2281
(ADR 0113, decisão 7) a rota saiu e a Demanda nova não nasce mais; as que já
estão no banco seguem na aba. Essa Demanda não tem Etapa vinda do GitHub: o
app não lê o repositório desse Projeto, então ela fica fora do espelho e da
conferência de hora em hora, e o filtro Projeto a lista pelo nome.

Pela ROTA de verdade da aba, com o Supabase em memória de `test_tecnologia_vinculo`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_chat import _cenario  # noqa: E402
from test_tecnologia_entregas import AGORA  # noqa: E402
from test_tecnologia_vinculo import BASE as BASE_DA_ABA  # noqa: E402
from test_tecnologia_vinculo import DIRETOR as DIRETOR_DA_ABA  # noqa: E402
from test_tecnologia_vinculo import PEDRO as PEDRO_DA_ABA  # noqa: E402
from test_tecnologia_vinculo import _demanda  # noqa: E402
from test_tecnologia_webhook_github import _demanda as _demanda_do_webhook  # noqa: E402
from test_tecnologia_webhook_github import _GithubFalso as _GithubDoWebhook  # noqa: E402
from test_tecnologia_webhook_github import _issue  # noqa: E402
from test_tecnologia_webhook_github import _SupabaseMock as _SupabaseDoWebhook  # noqa: E402

from app.routers.admin import tecnologia as tecnologia_router  # noqa: E402
from app.services import github_client, tecnologia_sincronizacao  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

LINK_DO_PRD = "https://github.com/Vitta-Share/os/issues/915"


# ═══════════════════════════════════════════════════════════════════════════
# Fora do espelho e da conferência de hora em hora
# ═══════════════════════════════════════════════════════════════════════════


def _a_demanda_criada_pela_ponte() -> dict:
    """A linha que a ponte gravava para o PRD do PedroOS, antes de a rota sair."""
    return {
        **_demanda_do_webhook("x"),
        "id": "tecnologia_demandas-1",
        "titulo": "Perguntas do PedroOS no app",
        "tipo": "novo",
        "produto_id": "prod-1",
        "estado": "nova",
        "responsavel_id": None,
        "autor_id": "P1",
        "prioridade": "normal",
        "origem": "vitta",
        "projeto": "os",
        "projeto_nome": "PedroOS",
        "raiz_url": LINK_DO_PRD,
        "github_issue_numero": 915,
        "etapa": "registrada",
        "criado_em": "2026-09-10T12:00:00Z",
    }


class TestForaDoEspelho:
    def test_a_conferencia_de_hora_em_hora_nao_le_o_github_pela_demanda_do_projeto_novo(self, monkeypatch):
        """A #915 do Hospital e lida; a #915 do PedroOS nao e lida nem contada:
        o app nao le aquele repositorio, e ler a do Hospital no lugar dela daria
        a Etapa de outra issue."""
        gh = _GithubDoWebhook({915: _issue(915, labels=("in-progress",))})
        monkeypatch.setattr(github_client, "ler_issue", gh.ler_issue)
        monkeypatch.setattr(github_client, "ler_sub_issues", gh.ler_sub_issues)
        do_os = _a_demanda_criada_pela_ponte()
        sb = _SupabaseDoWebhook(
            {
                "tecnologia_demandas": [_demanda_do_webhook("DH", github_issue_numero=915), do_os],
                "tecnologia_conversas": [],
            }
        )

        contagem = tecnologia_sincronizacao.reconciliar_vinculos(sb)

        assert gh.leituras == [915]
        assert contagem["lidas"] == 1
        assert sb.tabelas["tecnologia_demandas"][1] == do_os

    def test_atualizar_a_demanda_do_projeto_novo_nao_le_o_github(self, monkeypatch):
        gh = _GithubDoWebhook({915: _issue(915, labels=("in-progress",))})
        monkeypatch.setattr(github_client, "ler_issue", gh.ler_issue)
        monkeypatch.setattr(github_client, "ler_sub_issues", gh.ler_sub_issues)
        do_os = _a_demanda_criada_pela_ponte()
        sb = _SupabaseDoWebhook({"tecnologia_demandas": [do_os], "tecnologia_conversas": []})

        mudou = tecnologia_sincronizacao.sincronizar_demanda(sb, do_os)

        assert mudou is False
        assert gh.leituras == []
        assert sb.tabelas["tecnologia_demandas"] == [do_os]


# ═══════════════════════════════════════════════════════════════════════════
# A migration 163
# ═══════════════════════════════════════════════════════════════════════════

MIGRATION_163 = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "163_tecnologia_projeto_novo.sql"


@pytest.fixture
def sql() -> str:
    """O SQL que o Studio roda, sem os comentarios. A prova de que ele roda (as
    Demandas de hoje intactas, o PedroOS aceito, o nome fora do formato
    recusado, rodar duas vezes) foi feita num Postgres descartavel e esta no
    corpo do PR."""
    return re.sub(r"--[^\n]*", "", MIGRATION_163.read_text(encoding="utf-8"))


class TestAMigracao163:
    def test_o_check_aceita_projeto_novo_no_mesmo_formato_da_ponte(self, sql):
        """A restricao deixa de ser a lista Hospital e Ana e passa a ser o
        formato que a rota da ponte aceita: as duas pontas sao a mesma regra."""
        velho = sql.index("DROP CONSTRAINT IF EXISTS tecnologia_demandas_projeto_check")
        achado = re.search(r"ADD CONSTRAINT tecnologia_demandas_projeto_check\s+CHECK \(projeto ~ '([^']*)'\)", sql)
        assert achado and velho < achado.start()
        assert achado.group(1) == github_client.FORMATO_DO_PROJETO
        for projeto in ("hospital", "ana", "os"):
            assert re.fullmatch(achado.group(1), projeto)

    def test_as_demandas_que_ja_existem_nao_mudam(self, sql):
        antes_do_recibo = sql.split("INSERT INTO migracoes_aplicadas", 1)[0]
        assert "tecnologia_demandas" in antes_do_recibo, "o caso perdeu o sentido: a migration nao mexe na Demanda"
        assert not re.search(r"\bUPDATE\b|\bDELETE\b|SET DEFAULT|DROP COLUMN", antes_do_recibo, re.IGNORECASE)

    def test_o_nome_do_projeto_e_o_link_do_prd_sao_colunas_opcionais(self, sql):
        assert "ADD COLUMN IF NOT EXISTS projeto_nome TEXT;" in sql
        assert "ADD COLUMN IF NOT EXISTS raiz_url TEXT;" in sql
        assert re.search(r"CHECK \(raiz_url IS NULL OR raiz_url LIKE 'https://%'\)", sql)

    def test_a_migration_grava_o_recibo_163_por_ultimo(self, sql):
        instrucoes = [i.strip() for i in sql.split(";") if i.strip()]
        assert instrucoes[-1] == "INSERT INTO migracoes_aplicadas (numero) VALUES (163) ON CONFLICT (numero) DO NOTHING"


# ═══════════════════════════════════════════════════════════════════════════
# O filtro Projeto do Quadro e das Entregas
# ═══════════════════════════════════════════════════════════════════════════


def _demandas_da_aba() -> list[dict]:
    """Uma do Hospital, uma da Ana e a do PedroOS que a ponte criou, mais uma
    lapide de outro Projeto novo, que nao conta como Projeto com Demanda."""
    do_os = _a_demanda_criada_pela_ponte()
    return [
        {**do_os, "id": "d-os", "criado_em": "2026-11-18T10:00:00Z"},
        _demanda("d-hospital", github_issue_numero=51, autor_id=DIRETOR_DA_ABA["id"], criado_em="2026-11-04T10:00:00Z"),
        _demanda("d-ana", projeto="ana", origem="vitta", github_issue_numero=50, criado_em="2026-11-03T10:00:00Z"),
        _demanda(
            "d-apagada",
            projeto="site",
            projeto_nome="Site",
            origem="vitta",
            github_issue_numero=3,
            apagada_em="2026-11-10T10:00:00Z",
        ),
    ]


@pytest.fixture
def aba(monkeypatch):
    monkeypatch.setattr(tecnologia_router, "agora_utc", lambda: AGORA)

    def pedir(rota: str, logado: dict | None = None):
        client, _, _ = _cenario(
            monkeypatch,
            logado=logado or DIRETOR_DA_ABA,
            participantes=[PEDRO_DA_ABA, DIRETOR_DA_ABA],
            demandas=_demandas_da_aba(),
        )
        return client.get(rota)

    return pedir


class TestOFiltroProjeto:
    def test_a_lista_de_projetos_do_filtro_traz_o_projeto_novo_pelo_nome(self, aba):
        resposta = aba(f"{BASE_DA_ABA}/projetos")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == [
            {"valor": "hospital", "nome": "Aplicativo do Hospital"},
            {"valor": "ana", "nome": "Ana"},
            {"valor": "os", "nome": "PedroOS"},
        ]

    def test_o_quadro_filtra_pelo_projeto_novo(self, aba):
        resposta = aba(f"{BASE_DA_ABA}/chat?projeto=os")

        assert resposta.status_code == 200, resposta.text
        assert [d["id"] for d in resposta.json()] == ["d-os"]

    @pytest.mark.parametrize("logado", ["diretor", "desenvolvedor"])
    def test_o_card_do_projeto_novo_mostra_o_nome_do_projeto_e_o_link_do_prd(self, aba, logado):
        resposta = aba(f"{BASE_DA_ABA}/chat?filtro=todas", DIRETOR_DA_ABA if logado == "diretor" else PEDRO_DA_ABA)

        cards = {d["id"]: d for d in resposta.json()}
        assert (cards["d-os"]["projeto"], cards["d-os"]["projeto_nome"]) == ("os", "PedroOS")
        assert cards["d-os"]["raiz_url"] == LINK_DO_PRD
        assert (cards["d-hospital"]["projeto_nome"], cards["d-hospital"]["raiz_url"]) == (
            "Aplicativo do Hospital",
            None,
        )

    def test_as_entregas_aceitam_o_filtro_do_projeto_novo(self, aba):
        resposta = aba(f"{BASE_DA_ABA}/entregas?projeto=os", PEDRO_DA_ABA)

        assert resposta.status_code == 200, resposta.text

    def test_projeto_fora_do_formato_e_recusado(self, aba):
        assert aba(f"{BASE_DA_ABA}/chat?projeto=Outro%20projeto").status_code == 422
        assert aba(f"{BASE_DA_ABA}/entregas?projeto=Outro%20projeto", PEDRO_DA_ABA).status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════


class TestOKit:
    def test_o_kit_da_tecnologia_diz_que_o_projeto_novo_da_vitta_so_tem_os_pedidos_que_ja_existiam(self):
        """O Assistente fala pela lingua do Kit: sem isto, ele diria que a aba
        so tem o Aplicativo do Hospital e a Ana, ou que o plano de um projeto
        novo ainda abre pedido (a rota saiu na issue #2281)."""
        abertura = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8").split("\n## ", 1)[0]

        for trecho in (
            "projeto novo da Vitta",
            "nome do projeto e o link do plano",
            "projeto novo não abre pedido novo",
            "o filtro Projeto lista cada projeto que tem pedido",
        ):
            assert trecho in abertura, trecho
        assert "junta os pedidos de dois Projetos" not in abertura
        assert "O mesmo plano nunca abre dois pedidos" not in abertura
