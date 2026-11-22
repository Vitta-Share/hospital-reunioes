"""A Action de higiene só fecha o PRD pela última fatia concluída (PR #1577).

O "Atualizar o card" da aba Tecnologia (issue #1558) fecha as partes não
começadas como `not_planned`, com o token do Pedro, e devolve a raiz para
`needs-triage`. Esse fechamento dispara a Action (a anti-recursão do GitHub só
vale para o `GITHUB_TOKEN`); se ela fechasse a raiz como concluída, o card iria
para Entregue em vez de Em análise.

E o contrário (issue #2191): issue fechada como concluída com sub-issue aberta
volta a abrir, porque o PRD só fecha pela última fatia. Os testes rodam o script do job `higiene`
de verdade, no node, com o cliente do GitHub falso.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOW = RAIZ / ".github" / "workflows" / "higiene-issues.yml"

HARNESS = """
const chamadas = [];
const comentarios = {};
const issue = %(issue)s;
const parent = %(parent)s;
const subIssues = %(sub_issues)s;
const context = { repo: { owner: 'o', repo: 'r' }, payload: { issue } };
const core = { info: () => {} };
const github = {
  graphql: async () => ({ repository: { issue: { parent, subIssues } } }),
  rest: { issues: {
    removeLabel: async (a) => { chamadas.push(['removeLabel', a.issue_number, a.name]); },
    createComment: async (a) => {
      chamadas.push(['createComment', a.issue_number]);
      comentarios[a.issue_number] = a.body;
    },
    update: async (a) => { chamadas.push(['update', a.issue_number, a.state, a.state_reason]); },
  } },
};
(async () => {
%(script)s
})().then(() => console.log(JSON.stringify({ chamadas, comentarios })));
"""


def script_da_higiene() -> str:
    w = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return w["jobs"]["higiene"]["steps"][0]["with"]["script"]


PRD_COM_FATIAS_FECHADAS = {
    "number": 10,
    "state": "OPEN",
    "labels": {"nodes": [{"name": "needs-triage"}]},
    "subIssues": {"totalCount": 2, "nodes": [{"state": "CLOSED"}, {"state": "CLOSED"}]},
}


def sub_issue(number: int, state: str) -> dict:
    return {"number": number, "title": f"Fatia {number}", "state": state}


def rodar_tudo(
    tmp_path: Path,
    *,
    state_reason: str,
    parent: dict | None = PRD_COM_FATIAS_FECHADAS,
    sub_issues: list[dict] | None = None,
) -> dict:
    issue = {"number": 20, "state_reason": state_reason, "labels": [{"name": "ready-for-agent"}]}
    nodes = sub_issues or []
    arquivo = tmp_path / "higiene.js"
    arquivo.write_text(
        HARNESS
        % {
            "issue": json.dumps(issue),
            "parent": json.dumps(parent),
            "sub_issues": json.dumps({"totalCount": len(nodes), "nodes": nodes}),
            "script": script_da_higiene(),
        },
        encoding="utf-8",
    )
    node = shutil.which("node")
    assert node, "o teste roda o script da Action no node"
    saida = subprocess.run([node, str(arquivo)], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


def rodar(tmp_path: Path, *, state_reason: str) -> list[list]:
    return rodar_tudo(tmp_path, state_reason=state_reason)["chamadas"]


def test_ultima_fatia_concluida_fecha_o_prd(tmp_path):
    chamadas = rodar(tmp_path, state_reason="completed")
    assert ["createComment", 10] in chamadas
    assert ["update", 10, "closed", "completed"] in chamadas


def test_ultima_fatia_nao_planejada_deixa_o_prd_aberto(tmp_path):
    chamadas = rodar(tmp_path, state_reason="not_planned")
    # A fatia que fechou ainda perde as labels de estado.
    assert ["removeLabel", 20, "ready-for-agent"] in chamadas
    # O PRD não é tocado: nem comentário, nem fechamento, nem label.
    assert [c for c in chamadas if c[1] == 10] == []


def test_prd_fechado_como_concluido_com_fatia_aberta_volta_a_abrir(tmp_path):
    saida = rodar_tudo(
        tmp_path,
        state_reason="completed",
        parent=None,
        sub_issues=[sub_issue(31, "CLOSED"), sub_issue(32, "OPEN"), sub_issue(33, "OPEN")],
    )
    assert ["update", 20, "open", None] in saida["chamadas"]
    comentario = saida["comentarios"]["20"]
    assert comentario.startswith("<!-- automacao -->\n")
    assert "#32" in comentario
    assert "#33" in comentario
    assert "#31" not in comentario


def reaberturas(chamadas: list[list]) -> list[list]:
    return [c for c in chamadas if c[0] == "update" and c[2] == "open"]


def test_fechada_como_nao_planejada_com_fatia_aberta_continua_fechada(tmp_path):
    saida = rodar_tudo(
        tmp_path,
        state_reason="not_planned",
        parent=None,
        sub_issues=[sub_issue(32, "OPEN")],
    )
    assert reaberturas(saida["chamadas"]) == []
    assert saida["comentarios"] == {}


def test_sem_fatia_ou_com_todas_fechadas_continua_fechada(tmp_path):
    for fatias in ([], [sub_issue(31, "CLOSED"), sub_issue(32, "CLOSED")]):
        saida = rodar_tudo(tmp_path, state_reason="completed", parent=None, sub_issues=fatias)
        assert reaberturas(saida["chamadas"]) == [], fatias
        assert saida["comentarios"] == {}, fatias


def test_ultima_fatia_fecha_o_prd_e_ninguem_e_reaberto(tmp_path):
    saida = rodar_tudo(tmp_path, state_reason="completed", sub_issues=[])
    assert ["update", 10, "closed", "completed"] in saida["chamadas"]
    assert reaberturas(saida["chamadas"]) == []
