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

from app.services import github_client, tecnologia_sincronizacao  # noqa: E402

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
        **_issue(AJUSTE, estado=estado, motivo="completed" if estado == "closed" else None, labels=("ready-for-human",)),
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
