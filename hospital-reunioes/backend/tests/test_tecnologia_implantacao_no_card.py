"""A Implantação no card lida dos Cards de implantação (issue #2266, PRD
#2262, ADR 0113, decisão 9; antes, issue #2209 e ADR 0111, decisão 5).

O "Implantação X de Y" do Documento do card e o selo do Quadro saem das
sub-issues da raiz com a label `implantacao`: as fechadas sobre o total. A
sincronização (webhook e conferência de hora em hora) guarda essas sub-issues
na foto da Demanda, e a lista do chat deriva a Implantação dela. O registro do
Pedido de implantação deixa de ser fonte. Sem sub-issue `implantacao`, a
leitura vem com a Implantação nula, e o Card de implantação não conta como
Parte.

Pela ROTA de verdade (a lista do chat lê, o webhook sincroniza), com o
Supabase em memória e o GitHub dublado.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import test_tecnologia_webhook_github as webhook  # noqa: E402
from test_kit_conhecimento import ARQUIVO_DA_ABA  # noqa: E402
from test_kit_conhecimento import _texto as _texto_do_kit  # noqa: E402
from test_tecnologia_vinculo import _demanda, _montar, _pessoa, _SupabaseMock  # noqa: E402
from test_tecnologia_webhook_github import (  # noqa: E402, F401
    _pr_do_app,
    _segredo_configurado,
    _sem_github_de_verdade,
    _sem_pr_aberto,
)

from app.limiter import limiter  # noqa: E402
from app.services import github_client, tecnologia_sincronizacao  # noqa: E402
from app.services.tecnologia_vinculo import ETAPA_EM_DESENVOLVIMENTO, implantacao_da_foto  # noqa: E402

LISTA = "/api/admin/tecnologia/chat"

RAIZ = 1700
TESTE = "Testar o anonimato do Canal de Conduta"
ABERTURA = "Abrir o Canal de Conduta para todos"

DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
PEDRO = _pessoa("P001", "Pedro Rezende", github_login="pedrorezendefig")
DIRETORA = _pessoa("P004", "Diretora Clínica")


@pytest.fixture(autouse=True)
def _zera_o_limitador():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _issue(numero: int, titulo: str, *, estado: str = "open", labels=(), dono: str | None = None) -> dict:
    dados = {
        "number": numero,
        "title": titulo,
        "html_url": f"https://github.com/pedrorezendefig/hospital-reunioes/issues/{numero}",
        "state": estado,
        "state_reason": "completed" if estado == "closed" else None,
        "labels": [{"name": nome} for nome in labels],
        "body": "## Para o diretor\n\n**O que muda:** o relato anônimo.",
        "assignees": [{"login": dono}] if dono else [],
    }
    if estado == "closed":
        dados["closed_at"] = "2026-11-24T12:00:00Z"
    return dados


def _raiz(*, estado: str = "open") -> dict:
    return _issue(RAIZ, "Canal de Conduta", estado=estado)


def _fatia(numero: int = 1801, *, estado: str = "closed") -> dict:
    return _issue(numero, "Fatia do relato anônimo", estado=estado)


def _card(numero: int, titulo: str, *, estado: str = "open", dono: str | None = None) -> dict:
    return _issue(numero, titulo, estado=estado, labels=("implantacao",), dono=dono)


def _na_lista(foto: dict, monkeypatch) -> dict:
    """A Demanda como a lista do chat a devolve, com esta foto guardada pela
    sincronização."""
    linha = _demanda(
        DEMANDA,
        titulo="A Ata assinada no app",
        autor_id=PEDRO["id"],
        responsavel_id=PEDRO["id"],
        github_issue_numero=RAIZ,
        origem="vitta",
        apagada_em=None,
        github_foto=foto,
    )
    sb = _SupabaseMock(
        {
            "participantes": [dict(PEDRO), dict(DIRETORA)],
            "tecnologia_produtos": [{"id": "prod-1", "nome": "Reuniões", "ativo": True, "ordem": 1, "dono_id": "P001"}],
            "tecnologia_demandas": [linha],
        }
    )
    cliente, _, _ = _montar(logado=DIRETORA, supabase=sb, monkeypatch=monkeypatch)
    resposta = cliente.get(LISTA)
    assert resposta.status_code == 200, resposta.text
    [demanda] = [d for d in resposta.json() if d["id"] == DEMANDA]
    return demanda


class TestALeituraDaDemanda:
    def test_raiz_com_dois_cards_de_implantacao_e_um_fechado_mostra_1_de_2(self, monkeypatch):
        foto = github_client.montar_foto(
            _raiz(),
            [
                _fatia(),
                _card(1854, TESTE, estado="closed", dono="pedrorezendefig"),
                _card(1855, ABERTURA, dono="fulano-de-fora"),
            ],
        )

        demanda = _na_lista(foto, monkeypatch)

        assert demanda["implantacao"] == {
            "feitos": 1,
            "total": 2,
            "pedidos": [
                {"titulo": TESTE, "destinatario": "Pedro Rezende", "situacao": "feito", "espera": None},
                {"titulo": ABERTURA, "destinatario": "fulano-de-fora", "situacao": "aberto", "espera": None},
            ],
        }

    def test_raiz_sem_card_de_implantacao_vem_sem_a_secao(self, monkeypatch):
        """A Parte comum, mesmo com uma label qualquer, não vira Implantação."""
        foto = github_client.montar_foto(_raiz(), [_fatia(), _issue(1802, "Outra fatia", labels=("in-progress",))])

        demanda = _na_lista(foto, monkeypatch)

        assert demanda["implantacao"] is None


def _fechou_o_card(numero: int, *, raiz: int = RAIZ, labels=("implantacao",)) -> bytes:
    """O `issues.closed` do Card de implantação, como o GitHub manda: a
    sub-issue traz o endereço da raiz em `parent_issue_url`."""
    payload = {
        "action": "closed",
        "issue": {
            "number": numero,
            "state": "closed",
            "labels": [{"name": nome} for nome in labels],
            "parent_issue_url": f"https://api.github.com/repos/{webhook.REPO}/issues/{raiz}",
        },
        "repository": {"full_name": webhook.REPO},
    }
    return json.dumps(payload).encode("utf-8")


class TestPeloWebhook:
    def test_fechar_o_segundo_card_atualiza_a_raiz_para_2_de_2(self, monkeypatch):
        antes = webhook._GithubFalso(
            {RAIZ: _raiz()},
            sub_issues={RAIZ: [_fatia(), _card(1854, TESTE, estado="closed"), _card(1855, ABERTURA)]},
        )
        demanda = webhook._ja_sincronizada(antes, RAIZ)
        assert implantacao_da_foto(demanda["github_foto"])["feitos"] == 1
        depois = webhook._GithubFalso(
            {RAIZ: _raiz()},
            sub_issues={RAIZ: [_fatia(), _card(1854, TESTE, estado="closed"), _card(1855, ABERTURA, estado="closed")]},
        )
        cliente, sb, _ = webhook._montar(demandas=[demanda], github=depois, monkeypatch=monkeypatch)

        resposta = webhook._entregar(cliente, _fechou_o_card(1855))

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["sincronizada"] is True
        foto = webhook._demandas(sb)[0]["github_foto"]
        na_lista = _na_lista(foto, monkeypatch)
        assert (na_lista["implantacao"]["feitos"], na_lista["implantacao"]["total"]) == (2, 2)

    def test_a_parte_comum_continua_sem_ressincronizar_a_raiz(self, monkeypatch):
        """Só o Card de implantação puxa a raiz: o evento de uma Parte segue
        como antes, sem ler o GitHub."""
        gh = webhook._GithubFalso({RAIZ: _raiz()})
        cliente, _, _ = webhook._montar(
            demandas=[webhook._ja_sincronizada(gh, RAIZ)], github=gh, monkeypatch=monkeypatch
        )

        resposta = webhook._entregar(cliente, _fechou_o_card(1801, labels=()))

        assert resposta.status_code == 200, resposta.text
        assert gh.leituras == []


class TestNaoEParte:
    def test_o_card_de_implantacao_nao_entra_no_x_de_y_partes_entregues(self):
        """O resumo do GitHub conta toda sub-issue, o Card de implantação
        inclusive: com ele na raiz, a conta própria manda."""
        raiz = {**_raiz(), "sub_issues_summary": {"total": 3, "completed": 2}}
        foto = github_client.montar_foto(raiz, [_fatia(), _card(1854, TESTE, estado="closed"), _card(1855, ABERTURA)])

        mudanca = tecnologia_sincronizacao.mudanca_da_foto(foto)

        assert (mudanca["partes_entregues"], mudanca["partes_total"]) == (1, 1)
        assert [p["numero"] for p in mudanca["partes"]] == [1801]
        # A raiz aberta com a única Parte entregue e o Card aberto: em
        # desenvolvimento pela Parte, e não planejada pelo Card.
        assert mudanca["etapa"] == ETAPA_EM_DESENVOLVIMENTO


class TestKit:
    """O texto do Produto Tecnologia é o que o Assistente lê para responder
    ao diretor: ele diz o comportamento novo."""

    @pytest.fixture
    def texto(self) -> str:
        return _texto_do_kit(ARQUIVO_DA_ABA)

    @pytest.mark.parametrize(
        "frase",
        [
            "card de implantação no seu nome no GitHub",
            "Implantação 1 de 3",
            "Cada card de implantação fechado conta como feito",
            "não conta como parte da entrega",
            "a entrega fica Em produção mesmo com a implantação por fazer",
        ],
    )
    def test_o_kit_diz_que_a_implantacao_sai_dos_cards_de_implantacao(self, texto, frase):
        assert frase in texto
