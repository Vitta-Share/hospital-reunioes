"""O check do PR do diretor (ADR 0113, decisão 2; issue #2269).

O diretor é colaborador e não pode mergear. Uma das travas é este check: o PR
aberto por um login de `DIRETOR_LOGINS` reprova enquanto não tem a label
`assumido`, que um Desenvolvedor põe quando assume o protótipo, e a label só vale
se quem a pôs não é diretor (o histórico de labels da issue diz quem). Os testes
rodam o script da Action no Node com o evento e o histórico simulados, como o
`actions/github-script` roda, e conferem que o check roda de novo quando a label
entra ou sai.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOW = RAIZ / ".github" / "workflows" / "pr-do-diretor.yml"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def passo() -> dict:
    (job,) = workflow()["jobs"].values()
    (unico,) = job["steps"]
    return unico


def rodar_check(
    autor: str,
    labels: list[str],
    diretor_logins: str = "felipe-hsm",
    quem_pos: list[str] | None = None,
) -> str | None:
    """Roda o script do check e devolve a mensagem de reprovação, ou None se passou.

    `quem_pos` é a sequência de logins que puseram a label `assumido`, da mais velha
    para a mais nova; sem ela, quem está em `labels` com `assumido` foi posto pelo
    sócio `pedrorezendefig`.
    """
    script = passo()["with"]["script"]
    if quem_pos is None:
        quem_pos = ["pedrorezendefig"] if "assumido" in labels else []
    eventos = [{"event": "labeled", "label": {"name": "type:feature"}, "actor": {"login": "x"}}]
    eventos += [{"event": "labeled", "label": {"name": "assumido"}, "actor": {"login": q}} for q in quem_pos]
    harness = f"""
let reprovou = null;
const context = {{
  repo: {{ owner: "o", repo: "r" }},
  payload: {{ pull_request: {{
    number: 7,
    user: {{ login: {json.dumps(autor)} }},
    labels: {json.dumps([{"name": n} for n in labels])},
  }} }},
}};
const github = {{
  rest: {{ issues: {{ listEvents: "listEvents" }} }},
  paginate: async (rota, args) => {{
    if (rota !== "listEvents" || args.issue_number !== 7) throw new Error("rota errada");
    return {json.dumps(eventos)};
  }},
}};
const core = {{ info: () => {{}}, setFailed: (m) => {{ reprovou = m; }} }};
process.env.DIRETOR_LOGINS = {json.dumps(diretor_logins)};
(async () => {{
{script}
}})().then(() => console.log(JSON.stringify(reprovou)));
"""
    saida = subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


precisa_node = pytest.mark.skipif(shutil.which("node") is None, reason="sem Node")


@precisa_node
def test_pr_do_diretor_sem_assumido_reprova() -> None:
    motivo = rodar_check("Felipe-HSM", ["type:feature"], " outro, felipe-hsm ")
    assert motivo is not None and "assumido" in motivo


@precisa_node
def test_pr_do_diretor_com_assumido_passa() -> None:
    assert rodar_check("Felipe-HSM", ["type:feature", "assumido"]) is None


@precisa_node
def test_assumido_posta_pelo_proprio_diretor_reprova() -> None:
    motivo = rodar_check("Felipe-HSM", ["assumido"], quem_pos=["Felipe-HSM"])
    assert motivo is not None and "felipe-hsm" in motivo


@precisa_node
def test_assumido_sem_registro_de_quem_pos_reprova() -> None:
    assert rodar_check("felipe-hsm", ["assumido"], quem_pos=[]) is not None


@precisa_node
def test_vale_a_ultima_vez_que_a_label_entrou() -> None:
    assert rodar_check("felipe-hsm", ["assumido"], quem_pos=["pedrorezendefig", "felipe-hsm"]) is not None
    assert rodar_check("felipe-hsm", ["assumido"], quem_pos=["felipe-hsm", "lucassampaioc1"]) is None


@precisa_node
def test_pr_de_socio_passa_sem_label() -> None:
    assert rodar_check("lucassampaioc1", []) is None


@precisa_node
def test_login_que_so_contem_o_do_diretor_passa() -> None:
    assert rodar_check("felipe", []) is None


@precisa_node
def test_sem_diretor_configurado_ninguem_reprova() -> None:
    assert rodar_check("felipe-hsm", [], "") is None


def test_check_roda_de_novo_quando_a_label_entra_ou_sai_e_a_cada_push() -> None:
    wf = workflow()
    gatilho = wf.get("on") or wf.get(True)
    (evento,) = gatilho
    tipos = set(gatilho[evento]["types"])
    assert {"opened", "reopened", "synchronize", "labeled", "unlabeled"} <= tipos


def test_check_le_so_o_evento_sem_codigo_do_fork() -> None:
    """O PR vem do fork: o check decide pelo evento e pelo histórico de labels, e nunca faz checkout do código dele."""
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/checkout" not in texto
    assert "pull_request.title" not in texto and "pull_request.body" not in texto
    assert passo()["env"]["DIRETOR_LOGINS"] == "${{ vars.DIRETOR_LOGINS }}"
    assert re.search(r"@[0-9a-f]{40}", passo()["uses"]), "a action vai fixada por SHA"
    assert workflow()["permissions"] == {"issues": "read"}


def test_label_assumido_documentada() -> None:
    texto = (RAIZ / "docs" / "agents" / "triage-labels.md").read_text(encoding="utf-8")
    assert re.search(r"^\| `assumido` \|", texto, re.MULTILINE)
