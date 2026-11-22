"""O plano validado pelo diretor e o Ajuste do plano no Documento do card
(issue #1915).

A foto da Demanda guarda, da issue-raiz, quando o diretor validou o plano (o
marcador `<!-- validacao-diretor: <ISO> -->` do comentário mais recente, ou a
hora da label `validado:diretor` sem ele) e o número do Ajuste do plano aberto
(a sub-issue com `<!-- ajuste-do-plano: <raiz> -->` no corpo). A API devolve
`validado_em` e `ajuste_aberto` a todos que veem a Demanda; o número e o link do
Ajuste, só ao Desenvolvedor. O Ajuste não é parte da entrega.

O exemplo é a Demanda do PRD #1757: validada em 16/11/2026, com o Ajuste #1911
aberto bloqueando quatro partes. Tudo em fixture: nada do GitHub vivo.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tecnologia_chat import CHAT, _cenario  # noqa: E402
from test_tecnologia_vinculo import DIRETOR, PEDRO  # noqa: E402
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

from app.services import github_client  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402

REPO_URL = "https://github.com/pedrorezendefig/hospital-reunioes/issues"

# O PRD #1757 como estava em 16/11/2026: validado, com o Ajuste #1911 aberto.
RAIZ = 1757
AJUSTE = 1911
VALIDADO_EM = "2026-11-16T13:05:00.000Z"
# As seis partes do PRD: as quatro iniciais esperam o Ajuste, as duas de
# depois esperam uma das iniciais.
PARTES = (1758, 1759, 1760, 1761, 1762, 1763)
TRAVADAS_PELO_AJUSTE = (1758, 1759, 1760, 1761)


def _raiz(*, validada: bool = True) -> dict:
    return _issue(RAIZ, labels=("validado:diretor",) if validada else ())


def _ajuste(*, estado: str = "open") -> dict:
    return {
        **_issue(
            AJUSTE, estado=estado, motivo="completed" if estado == "closed" else None, labels=("ready-for-human",)
        ),
        "body": f"<!-- ajuste-do-plano: {RAIZ} -->\n<!-- envio-aos-desenvolvedores -->\n## O que é este card\n",
    }


def _bloqueio(numero: int, estado: str = "open") -> dict:
    return {"numero": numero, "estado": estado, "url": f"{REPO_URL}/{numero}"}


def _github_do_1757(
    *, validada: bool = True, ajuste: str = "open", validacao: str | None | Exception = VALIDADO_EM
) -> _GithubFalso:
    bloqueadoras = {n: [_bloqueio(AJUSTE, ajuste)] for n in TRAVADAS_PELO_AJUSTE}
    bloqueadoras[1762] = [_bloqueio(1758)]
    bloqueadoras[1763] = [_bloqueio(1759)]
    return _GithubFalso(
        {RAIZ: _raiz(validada=validada)},
        sub_issues={RAIZ: [*(_issue(n) for n in PARTES), _ajuste(estado=ajuste)]},
        bloqueadoras=bloqueadoras,
        validacoes={RAIZ: validacao},
    )


def _sincronizar(gh: _GithubFalso, monkeypatch, *, guardada: dict | None = None, acao: str = "labeled") -> dict:
    """Entrega o evento da raiz e devolve a Demanda como ficou. `guardada` é a
    Demanda como a sincronização anterior a deixou; sem ela, a do Vínculo."""
    guardada = guardada or _ja_sincronizada(_GithubFalso({RAIZ: _issue(RAIZ)}), RAIZ)
    cliente, sb, _ = _montar(demandas=[guardada], github=gh, monkeypatch=monkeypatch)
    _entregar(cliente, _corpo(RAIZ, acao=acao))
    [demanda] = _demandas(sb)
    return demanda


class TestAFotoGuardaAValidacaoEOAjuste:
    def test_a_raiz_validada_guarda_a_data_da_validacao_e_o_ajuste_aberto(self, monkeypatch):
        demanda = _sincronizar(_github_do_1757(), monkeypatch)

        assert demanda["github_foto"]["validado_em"] == VALIDADO_EM
        assert demanda["github_foto"]["ajuste_aberto"] == AJUSTE

    def test_a_falha_na_leitura_mantem_a_data_da_foto_anterior(self, monkeypatch):
        antes = _sincronizar(_github_do_1757(), monkeypatch)

        depois = _sincronizar(
            _github_do_1757(validacao=github_client.GithubIndisponivelError("GitHub respondeu 502")),
            monkeypatch,
            guardada=antes,
            acao="edited",
        )

        assert depois["github_foto"]["validado_em"] == VALIDADO_EM
        assert depois["github_foto"]["ajuste_aberto"] == AJUSTE

    def test_tirar_a_label_tira_a_data_na_proxima_sincronizacao(self, monkeypatch):
        antes = _sincronizar(_github_do_1757(), monkeypatch)
        gh = _github_do_1757(validada=False)

        depois = _sincronizar(gh, monkeypatch, guardada=antes, acao="unlabeled")

        assert "validado_em" not in depois["github_foto"]
        # Sem a label nem se pergunta ao GitHub quando foi a validacao.
        assert gh.leituras_da_validacao == []

    def test_fechar_o_ajuste_tira_o_ajuste_aberto_da_foto(self, monkeypatch):
        antes = _sincronizar(_github_do_1757(), monkeypatch)

        depois = _sincronizar(_github_do_1757(ajuste="closed"), monkeypatch, guardada=antes, acao="edited")

        assert "ajuste_aberto" not in depois["github_foto"]

    def test_o_marcador_de_outra_raiz_nao_faz_o_ajuste(self, monkeypatch):
        gh = _github_do_1757()
        gh.sub_issues[RAIZ][-1]["body"] = "<!-- ajuste-do-plano: 1700 -->"

        demanda = _sincronizar(gh, monkeypatch)

        assert "ajuste_aberto" not in demanda["github_foto"]


class TestOClienteLeAValidacao:
    def _github(self, monkeypatch, *, comentarios: list[dict], eventos: list[dict]) -> list[str]:
        chamadas: list[str] = []

        def _chamar(metodo, caminho, *, projeto, **kw):
            chamadas.append(caminho)
            return comentarios if "/comments" in caminho else eventos

        monkeypatch.setattr(github_client, "_chamar", _chamar)
        return chamadas

    def test_vale_o_marcador_do_comentario_mais_recente_de_quem_e_do_repositorio(self, monkeypatch):
        self._github(
            monkeypatch,
            comentarios=[
                {"author_association": "OWNER", "body": "<!-- validacao-diretor: 2026-11-10T12:00:00.000Z -->"},
                {"author_association": "MEMBER", "body": f"Plano validado.\n<!-- validacao-diretor: {VALIDADO_EM} -->"},
                # De fora do repositorio: o repositorio e publico.
                {"author_association": "NONE", "body": "<!-- validacao-diretor: 2026-11-20T12:00:00.000Z -->"},
            ],
            eventos=[],
        )

        assert github_client.ler_validacao_do_diretor(RAIZ, projeto="hospital") == VALIDADO_EM

    def test_sem_o_comentario_vale_a_hora_em_que_a_label_entrou_por_ultimo(self, monkeypatch):
        chamadas = self._github(
            monkeypatch,
            comentarios=[{"author_association": "OWNER", "body": "Sem marcador."}],
            eventos=[
                {"event": "labeled", "label": {"name": "validado:diretor"}, "created_at": "2026-11-01T10:00:00Z"},
                {"event": "labeled", "label": {"name": "ready-for-agent"}, "created_at": "2026-11-17T10:00:00Z"},
                {"event": "labeled", "label": {"name": "validado:diretor"}, "created_at": "2026-11-16T13:04:00Z"},
            ],
        )

        assert github_client.ler_validacao_do_diretor(RAIZ, projeto="hospital") == "2026-11-16T13:04:00Z"
        assert chamadas == [
            f"/issues/{RAIZ}/comments?per_page=100&page=1",
            f"/issues/{RAIZ}/events?per_page=100&page=1",
        ]

    def test_resposta_fora_do_formato_levanta(self, monkeypatch):
        monkeypatch.setattr(github_client, "_chamar", lambda *a, **kw: {"message": "?"})

        with pytest.raises(github_client.GithubIndisponivelError):
            github_client.ler_validacao_do_diretor(RAIZ, projeto="hospital")


# ═══════════════════════════════════════════════════════════════════════════
# A API do Documento do card
# ═══════════════════════════════════════════════════════════════════════════

_CACHE = ("etapa", "partes_entregues", "partes_total", "o_que_muda", "partes", "plano_validado", "github_foto")


def _item_da_lista(monkeypatch, gh: _GithubFalso, *, logado: dict) -> dict:
    """A Demanda do PRD #1757 como a lista a devolve a quem está logado, com o
    cache que a sincronização deixou."""
    sincronizada = _sincronizar(gh, monkeypatch)
    client, _, _ = _cenario(
        monkeypatch,
        logado=logado,
        participantes=[DIRETOR, PEDRO],
        demandas=[
            _demanda_do_diretor(
                "d-1757",
                autor_id=DIRETOR["id"],
                github_issue_numero=RAIZ,
                **{c: sincronizada[c] for c in _CACHE},
            )
        ],
    )
    [item] = client.get(f"{CHAT}?filtro=todas" if logado is PEDRO else CHAT).json()
    return item


class TestAApiDoDocumento:
    def test_quem_nao_tem_github_login_recebe_a_data_e_o_ajuste_aberto_sem_numero_nem_link(self, monkeypatch):
        item = _item_da_lista(monkeypatch, _github_do_1757(), logado=DIRETOR)

        assert item["validado_em"] == VALIDADO_EM
        assert item["ajuste_aberto"] is True
        assert (item["ajuste_numero"], item["ajuste_url"]) == (None, None)
        assert str(AJUSTE) not in str(item)

    def test_o_desenvolvedor_recebe_o_numero_e_o_link_do_ajuste(self, monkeypatch):
        item = _item_da_lista(monkeypatch, _github_do_1757(), logado=PEDRO)

        assert (item["ajuste_numero"], item["ajuste_url"]) == (AJUSTE, f"{REPO_URL}/{AJUSTE}")

    def test_o_ajuste_fica_fora_das_partes_e_da_contagem(self, monkeypatch):
        item = _item_da_lista(monkeypatch, _github_do_1757(), logado=DIRETOR)

        assert [p["numero"] for p in item["partes"]] == list(PARTES)
        assert (item["partes_entregues"], item["partes_total"]) == (0, 6)

    def test_as_quatro_partes_travadas_esperam_o_ajuste_do_plano(self, monkeypatch):
        item = _item_da_lista(monkeypatch, _github_do_1757(), logado=DIRETOR)

        esperas = {p["numero"]: p["bloqueadoras"] for p in item["partes"]}
        ajuste = [{"numero": None, "de_outro_pedido": False, "ajuste_do_plano": True}]
        assert esperas == {
            1758: ajuste,
            1759: ajuste,
            1760: ajuste,
            1761: ajuste,
            1762: [{"numero": 1758, "de_outro_pedido": False, "ajuste_do_plano": False}],
            1763: [{"numero": 1759, "de_outro_pedido": False, "ajuste_do_plano": False}],
        }
        # O Ajuste nao empurra as partes para a Onda 2.
        assert [p["onda"] for p in item["partes"]] == [1, 1, 1, 1, 2, 2]

    def test_com_o_ajuste_fechado_some_a_faixa_e_as_partes_mostram_so_o_que_resta(self, monkeypatch):
        item = _item_da_lista(monkeypatch, _github_do_1757(ajuste="closed"), logado=DIRETOR)

        assert item["ajuste_aberto"] is False
        assert {p["numero"]: len(p["bloqueadoras"]) for p in item["partes"]} == {
            1758: 0,
            1759: 0,
            1760: 0,
            1761: 0,
            1762: 1,
            1763: 1,
        }
        # Fechado, o Ajuste conta como entregue no GitHub: aqui nao conta.
        assert (item["partes_entregues"], item["partes_total"]) == (0, 6)

    def test_sem_a_label_a_api_nao_manda_a_data(self, monkeypatch):
        item = _item_da_lista(monkeypatch, _github_do_1757(validada=False), logado=DIRETOR)

        assert item["validado_em"] is None


class TestOKit:
    def test_o_kit_da_tecnologia_diz_o_selo_a_faixa_e_o_espera_o_ajuste(self):
        """O kit é a língua em que o Assistente fala com o diretor: sem o
        comportamento novo escrito, ele não saberia explicar o selo nem por que
        uma parte ainda não começou."""
        texto = (CONHECIMENTO_DIR / "tecnologia.md").read_text(encoding="utf-8")
        secao = texto.split("## A Etapa", 1)[1].split("\n## ", 1)[0]

        for trecho in ("**Plano validado em**", "**Espera o ajuste do plano**", "ajustando o plano"):
            assert trecho in secao, trecho
        assert "\u2014" not in texto and "\u2013" not in texto
