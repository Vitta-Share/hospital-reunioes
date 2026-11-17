"""As Partes do Documento do card com número, o que trava e Onda (issue #1902,
PRD #1901, ADR 0100).

A foto da Demanda guarda, em cada parte, as bloqueadoras lidas do GitHub
(`blocked_by`); um módulo puro calcula a Onda de cada parte; a API devolve o
número da raiz e de cada parte, a Onda e as bloqueadoras abertas para todos que
veem a Demanda; e o kit diz o comportamento novo.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_chat import CHAT, _cenario  # noqa: E402
from test_tecnologia_vinculo import DIRETOR  # noqa: E402
from test_tecnologia_vinculo import _demanda as _demanda_do_diretor  # noqa: E402
from test_tecnologia_webhook_github import (  # noqa: E402
    _corpo,
    _demandas,
    _entregar,
    _GithubFalso,
    _issue,
    _ja_sincronizada,
    _montar,
    _pr_do_app,  # noqa: F401  (autouse)
    _reset_rate_limiter,  # noqa: F401  (autouse)
    _segredo_configurado,  # noqa: F401  (autouse)
    _sem_github_de_verdade,  # noqa: F401  (autouse)
    _sem_pr_aberto,  # noqa: F401  (autouse)
)

from app.services import github_client, tecnologia_sincronizacao  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402
from app.services.tecnologia_ondas import ondas_das_partes  # noqa: E402


class TestOKitDizAsPartesComOnda:
    def test_o_kit_da_tecnologia_diz_a_onda_o_numero_e_o_espera_a(self):
        """O kit é a língua em que o Assistente fala com o diretor: sem o
        comportamento novo escrito, ele diria que as partes não têm número."""
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")
        secao = texto.split("## A Etapa", 1)[1].split("\n## ", 1)[0]

        for trecho in ("**Onda 1**", "**Espera a #", "de outro pedido", "número do pedido inteiro"):
            assert trecho in secao, trecho
        assert "sem número nem link do card" not in texto


def _parte(numero: int, *bloqueadoras: int | tuple[int, bool]) -> dict:
    """A parte com as bloqueadoras: um número é bloqueadora da mesma Demanda, e
    `(numero, False)` é bloqueadora de outro pedido."""
    lista = []
    for b in bloqueadoras:
        numero_b, da_demanda = b if isinstance(b, tuple) else (b, True)
        lista.append({"numero": numero_b, "estado": "open", "da_demanda": da_demanda})
    return {"numero": numero, "bloqueadoras": lista}


class TestAOndaDeCadaParte:
    @pytest.mark.parametrize(
        ("partes", "ondas"),
        [
            pytest.param([_parte(10)], [1], id="uma-parte-so"),
            pytest.param([_parte(10), _parte(11)], [1, 1], id="sem-dependencia-tudo-na-onda-1"),
            pytest.param([_parte(10), _parte(11, 10)], [1, 2], id="espera-uma-fica-uma-onda-depois"),
            pytest.param(
                [_parte(10), _parte(11, 10), _parte(12, 11), _parte(13, 10)],
                [1, 2, 3, 2],
                id="cadeia-e-irma",
            ),
            pytest.param(
                [_parte(10), _parte(11), _parte(12, 10, 11), _parte(13, 12, 10)],
                [1, 1, 2, 3],
                id="vale-a-maior-onda-das-esperadas",
            ),
            pytest.param([_parte(10), _parte(11, (900, False))], [1, 1], id="bloqueadora-de-outro-pedido-nao-conta"),
            pytest.param(
                [_parte(10), _parte(11, (10, False))],
                [1, 1],
                id="outro-pedido-com-o-mesmo-numero-de-uma-parte-nao-conta",
            ),
            pytest.param([_parte(10, 11), _parte(11, 10)], [1, 1], id="ciclo-fica-na-onda-1"),
            pytest.param([_parte(10, 10)], [1], id="parte-que-espera-a-si-mesma-fica-na-onda-1"),
            pytest.param(
                [_parte(10, 11), _parte(11, 10), _parte(12, 11)],
                [1, 1, 2],
                id="quem-espera-o-ciclo-fica-uma-onda-depois",
            ),
            pytest.param([_parte(12, 11), _parte(11, 10), _parte(10)], [3, 2, 1], id="a-ordem-da-lista-nao-importa"),
            pytest.param([{"numero": 10}, _parte(11, 10)], [1, 2], id="parte-sem-bloqueadoras-lidas"),
        ],
    )
    def test_a_onda_segue_as_dependencias_dentro_da_demanda(self, partes, ondas):
        assert ondas_das_partes(partes) == ondas

    def test_o_bloqueio_ja_resolvido_continua_contando(self):
        """A sequência não muda quando uma parte fecha (ADR 0100, decisão 3)."""
        partes = [
            {"numero": 10, "bloqueadoras": []},
            {"numero": 11, "bloqueadoras": [{"numero": 10, "estado": "closed", "da_demanda": True}]},
        ]

        assert ondas_das_partes(partes) == [1, 2]


# ═══════════════════════════════════════════════════════════════════════════
# A foto guarda as bloqueadoras de cada parte
# ═══════════════════════════════════════════════════════════════════════════

REPO_URL = "https://github.com/pedrorezendefig/hospital-reunioes/issues"


def _bloqueadora(numero: int, estado: str = "open", *, url: str | None = None) -> dict:
    """A bloqueadora como o cliente do GitHub a devolve."""
    return {"numero": numero, "estado": estado, "url": url or f"{REPO_URL}/{numero}"}


def _partes_da_foto(demanda: dict) -> dict[int, list[dict] | None]:
    return {p["numero"]: p.get("bloqueadoras") for p in demanda["github_foto"]["partes"]}


class TestAFotoGuardaAsBloqueadoras:
    def test_cada_parte_guarda_numero_estado_e_se_a_bloqueadora_e_da_mesma_demanda(self, monkeypatch):
        gh = _GithubFalso(
            {673: _issue(673)},
            sub_issues={673: [_issue(678), _issue(679), _issue(680)]},
            bloqueadoras={
                679: [_bloqueadora(678, "closed")],
                680: [_bloqueadora(679), _bloqueadora(1830, url="https://github.com/outro/repo/issues/1830")],
            },
        )
        cliente, sb, _ = _montar(demandas=[_ja_sincronizada(gh, 673)], github=gh, monkeypatch=monkeypatch)

        _entregar(cliente, _corpo())

        [demanda] = _demandas(sb)
        assert _partes_da_foto(demanda) == {
            678: None,
            679: [{"numero": 678, "estado": "closed", "da_demanda": True}],
            680: [
                {"numero": 679, "estado": "open", "da_demanda": True},
                {"numero": 1830, "estado": "open", "da_demanda": False},
            ],
        }

    def test_a_falha_na_leitura_mantem_as_da_foto_anterior_e_nao_derruba_a_sincronizacao(self, monkeypatch):
        antes = _GithubFalso(
            {673: _issue(673)},
            sub_issues={673: [_issue(678), _issue(679)]},
            bloqueadoras={679: [_bloqueadora(678)]},
        )
        guardada = _ja_sincronizada(antes, 673)
        guardada["github_foto"]["partes"][1]["bloqueadoras"] = [{"numero": 678, "estado": "open", "da_demanda": True}]
        # Agora a raiz ganhou uma label e a leitura das dependencias da 679 falha.
        gh = _GithubFalso(
            {673: _issue(673, labels=("ready-for-agent",))},
            sub_issues={673: [_issue(678), _issue(679)]},
            bloqueadoras={679: github_client.GithubIndisponivelError("GitHub respondeu 502")},
        )
        cliente, sb, _ = _montar(demandas=[guardada], github=gh, monkeypatch=monkeypatch)

        resposta = _entregar(cliente, _corpo())

        assert resposta.status_code == 200
        [demanda] = _demandas(sb)
        assert demanda["github_foto"]["labels"] == ["ready-for-agent"]
        assert _partes_da_foto(demanda)[679] == [{"numero": 678, "estado": "open", "da_demanda": True}]

    def test_com_a_raiz_fechada_as_dependencias_nao_sao_lidas_e_ficam_as_da_foto_anterior(self, monkeypatch):
        antes = _GithubFalso({673: _issue(673)}, sub_issues={673: [_issue(678), _issue(679)]})
        guardada = _ja_sincronizada(antes, 673)
        guardada["github_foto"]["partes"][1]["bloqueadoras"] = [{"numero": 678, "estado": "closed", "da_demanda": True}]
        gh = _GithubFalso(
            {673: _issue(673, estado="closed", motivo="completed")},
            sub_issues={673: [_issue(678, estado="closed", motivo="completed"), _issue(679, estado="closed")]},
        )
        cliente, sb, _ = _montar(demandas=[guardada], github=gh, monkeypatch=monkeypatch)

        _entregar(cliente, _corpo(acao="closed"))

        [demanda] = _demandas(sb)
        assert gh.leituras_das_bloqueadoras == []
        assert _partes_da_foto(demanda)[679] == [{"numero": 678, "estado": "closed", "da_demanda": True}]


# ═══════════════════════════════════════════════════════════════════════════
# A API do Documento do card
# ═══════════════════════════════════════════════════════════════════════════


def _foto_com_partes() -> dict:
    """A foto como a sincronizacao a deixa: a raiz aberta e tres partes, a 679
    esperando a 678 (ja fechada) e a 680 esperando a 679 e um pedido de fora."""
    gh = _GithubFalso(
        {673: _issue(673)},
        sub_issues={673: [_issue(678, estado="closed", motivo="completed"), _issue(679), _issue(680)]},
    )
    foto = github_client.montar_foto(gh.issues[673], gh.sub_issues[673])
    foto["partes"][1]["bloqueadoras"] = [{"numero": 678, "estado": "closed", "da_demanda": True}]
    foto["partes"][2]["bloqueadoras"] = [
        {"numero": 679, "estado": "open", "da_demanda": True},
        {"numero": 1830, "estado": "open", "da_demanda": False},
    ]
    return foto


class TestAApiDoDocumento:
    def test_quem_nao_tem_github_login_recebe_numeros_onda_e_bloqueadoras_abertas_sem_link(self, monkeypatch):
        cache = tecnologia_sincronizacao.mudanca_da_foto(_foto_com_partes())
        client, _, _ = _cenario(
            monkeypatch,
            logado=DIRETOR,
            participantes=[DIRETOR],
            demandas=[_demanda_do_diretor("d-1", autor_id=DIRETOR["id"], github_issue_numero=673, **cache)],
        )

        [item] = client.get(CHAT).json()

        assert item["raiz_numero"] == 673
        assert (item["issue_numero"], item["issue_url"]) == (None, None)
        assert [(p["numero"], p["onda"], p["bloqueadoras"]) for p in item["partes"]] == [
            (678, 1, []),
            # A 678 ja fechou: conta para a Onda, mas nao aparece como espera.
            (679, 2, []),
            (680, 3, [{"numero": 679, "de_outro_pedido": False}, {"numero": 1830, "de_outro_pedido": True}]),
        ]
        textos = [str(v) for p in item["partes"] for v in p.values()]
        assert not [t for t in textos if "github.com" in t or "Tecnologia: webhook" in t]
        assert all("labels" not in p and "titulo" not in p and "url" not in p for p in item["partes"])


class TestOClienteLeAsBloqueadoras:
    def test_le_o_blocked_by_da_parte_com_numero_estado_e_endereco(self, monkeypatch):
        chamadas = []

        def _chamar(metodo, caminho, *, projeto, **kw):
            chamadas.append((metodo, caminho, projeto))
            return [
                {"number": 1884, "state": "closed", "html_url": f"{REPO_URL}/1884", "title": "Tecnico"},
                {"id": 7, "title": "sem numero"},
            ]

        monkeypatch.setattr(github_client, "_chamar", _chamar)

        lidas = github_client.ler_bloqueadoras(1886, projeto="hospital")

        assert chamadas == [("GET", "/issues/1886/dependencies/blocked_by?per_page=100", "hospital")]
        assert lidas == [{"numero": 1884, "estado": "closed", "url": f"{REPO_URL}/1884"}]
