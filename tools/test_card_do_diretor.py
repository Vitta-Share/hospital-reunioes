"""O card do diretor e a skill /setup-diretor (grill de 24/11/2026).

O diretor planeja no Claude dele e abre o card no GitHub de um fork, sem acesso de
escrita, para o GitHub impedir o merge (repo de conta pessoal não tem papel Triage).
Sem acesso ele não põe label nem dono: a Action `card-do-diretor.yml` faz isso
quando o autor está na variável `DIRETOR_LOGINS`. Os testes rodam o script da Action
no Node com o GitHub simulado, como o `actions/github-script` roda, e leem a skill
como o Claude do diretor lê.
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
WORKFLOW = RAIZ / ".github" / "workflows" / "card-do-diretor.yml"
SKILL = RAIZ / ".claude" / "skills" / "setup-diretor"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def passo() -> dict:
    (job,) = workflow()["jobs"].values()
    (unico,) = job["steps"]
    return unico


def rodar_action(
    autor: str, diretor_logins: str, tipo: str = "User", donos: tuple[str, ...] = ()
) -> list[dict]:
    """Roda o script da Action e devolve as chamadas de escrita que ele fez à API.

    `donos` é quem já está designado na issue quando a Action relê o card.
    """
    script = passo()["with"]["script"]
    atuais = [{"login": d} for d in donos]
    harness = f"""
const chamadas = [];
const github = {{ rest: {{ issues: {{
  get: async () => ({{ data: {{ assignees: {json.dumps(atuais)} }} }}),
  addLabels: async (a) => chamadas.push({{ fn: 'addLabels', ...a }}),
  addAssignees: async (a) => chamadas.push({{ fn: 'addAssignees', ...a }}),
}} }} }};
const context = {{
  repo: {{ owner: 'Vitta-Share', repo: 'hospital-reunioes' }},
  payload: {{ issue: {{ number: 42, user: {{ login: {json.dumps(autor)}, type: {json.dumps(tipo)} }} }} }},
}};
const core = {{ info: () => {{}} }};
process.env.DIRETOR_LOGINS = {json.dumps(diretor_logins)};
(async () => {{
{script}
}})().then(() => console.log(JSON.stringify(chamadas)));
"""
    saida = subprocess.run(
        ["node", "-e", harness], capture_output=True, text=True, check=True
    )
    return json.loads(saida.stdout)


precisa_node = pytest.mark.skipif(shutil.which("node") is None, reason="sem Node")


def test_action_dispara_quando_a_issue_abre_e_le_a_variavel() -> None:
    wf = workflow()
    gatilho = wf.get("on") or wf.get(True)
    assert gatilho == {"issues": {"types": ["opened"]}}
    (job,) = wf["jobs"].values()
    assert "vars.DIRETOR_LOGINS" in job["if"], "sem a variável, o job não deve rodar"
    assert passo()["env"]["DIRETOR_LOGINS"] == "${{ vars.DIRETOR_LOGINS }}"
    assert re.search(r"@[0-9a-f]{40}", passo()["uses"]), "a action vai fixada por SHA"


def test_action_nao_filtra_por_colaborador() -> None:
    """O diretor não é colaborador: filtrar por author_association o deixaria de fora."""
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "author_association" not in texto


def test_action_nunca_le_titulo_nem_corpo_da_issue() -> None:
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "issue.title" not in texto and "issue.body" not in texto


@precisa_node
def test_card_do_diretor_ganha_as_labels_e_o_dono() -> None:
    chamadas = rodar_action("Felipe-HSM", " outro, felipe-hsm ")
    assert chamadas == [
        {
            "fn": "addLabels",
            "owner": "Vitta-Share",
            "repo": "hospital-reunioes",
            "issue_number": 42,
            "labels": ["needs-triage", "origem:diretor"],
        },
        {
            "fn": "addAssignees",
            "owner": "Vitta-Share",
            "repo": "hospital-reunioes",
            "issue_number": 42,
            "assignees": ["pedrorezendefig"],
        },
    ]


@precisa_node
def test_card_do_diretor_com_dono_mantem_o_dono() -> None:
    """O diretor é colaborador e pode pôr o card no nome de quem vai desenvolver."""
    chamadas = rodar_action("felipe-hsm", "felipe-hsm", donos=("lucassampaioc1",))
    assert [c["fn"] for c in chamadas] == ["addLabels"]
    assert chamadas[0]["labels"] == ["needs-triage", "origem:diretor"]


@precisa_node
def test_card_de_quem_nao_e_diretor_fica_como_esta() -> None:
    assert rodar_action("lucassampaioc1", "felipe-hsm") == []


@precisa_node
def test_login_que_so_contem_o_do_diretor_nao_passa() -> None:
    assert rodar_action("felipe", "felipe-hsm") == []


def ler(nome: str) -> str:
    return (SKILL / nome).read_text(encoding="utf-8")


def test_skill_proibe_o_caminho_de_producao() -> None:
    regras = ler("SKILL.md")
    for proibido in ("/ship", "/pegar-issue", "/onda-enxuta", "fechar_onda.py", "/deploy"):
        assert f"`{proibido}`" in regras.split("## Regras do modo diretor")[1].split("## ")[0], (
            f"as regras do modo diretor não proíbem {proibido}"
        )


def test_prototipo_vai_em_pr_rascunho_e_nao_fecha_o_card() -> None:
    skill = ler("SKILL.md")
    criar_pr = re.search(r"gh pr create[^\n]*(?:\n\s+[^\n]*)*", skill).group(0)
    assert "--draft" in criar_pr
    assert "--repo Vitta-Share/hospital-reunioes" in criar_pr
    assert "Refs #<N>" in skill and "nunca `Closes`" in skill


def test_card_nasce_no_repositorio_do_time_sem_label_no_comando() -> None:
    skill = ler("SKILL.md")
    (criar,) = re.findall(r"gh issue create[^\n]*", skill)
    assert "--repo Vitta-Share/hospital-reunioes" in criar
    assert "--label" not in criar and "--assignee" not in criar


def test_referencias_que_a_skill_cita_existem() -> None:
    skill = ler("SKILL.md")
    for ref in re.findall(r"`(references/[\w.-]+|scripts/[\w.-]+)`", skill):
        assert (SKILL / ref).exists(), f"{ref} citado e ausente"


def test_scripts_nao_tocam_producao_nem_imprimem_chave() -> None:
    for nome in ("scripts/conferir.sh", "scripts/env_local.sh"):
        texto = ler(nome)
        for termo in ("coolify", "COOLIFY", "tokens/.env", "op read", "sudo "):
            assert termo not in texto, f"{nome} cita {termo}"
    env = ler("scripts/env_local.sh")
    for linha in env.splitlines():
        if linha.lstrip().startswith("echo"):
            assert "$anon" not in linha and "$service" not in linha


def test_mensagens_ao_pedro_sem_travessao() -> None:
    for nome in ("references/pedro.md", "references/passo-a-passo.md", "SKILL.md"):
        texto = ler(nome)
        assert "\u2014" not in texto and "\u2013" not in texto, nome


def test_ask_pedro_roteia_a_skill() -> None:
    ask = (RAIZ / ".claude" / "skills" / "ask-pedro" / "SKILL.md").read_text(encoding="utf-8")
    assert "`/setup-diretor`" in ask


DONO_DO_CARD = RAIZ / ".github" / "workflows" / "dono-do-card.yml"


def rodar_dono_do_card(autor: str, diretor_logins: str) -> list[dict]:
    """Roda o script da dono-do-card.yml numa issue sem dono e devolve as escritas."""
    (job,) = yaml.safe_load(DONO_DO_CARD.read_text(encoding="utf-8"))["jobs"].values()
    (unico,) = job["steps"]
    assert unico["env"]["DIRETOR_LOGINS"] == "${{ vars.DIRETOR_LOGINS }}"
    harness = f"""
const chamadas = [];
const github = {{ rest: {{ issues: {{
  get: async () => ({{ data: {{ assignees: [] }} }}),
  addAssignees: async (a) => chamadas.push({{ fn: 'addAssignees', ...a }}),
}} }} }};
const context = {{
  repo: {{ owner: 'Vitta-Share', repo: 'hospital-reunioes' }},
  payload: {{ issue: {{ number: 42, user: {{ login: {json.dumps(autor)} }} }} }},
}};
const core = {{ info: () => {{}} }};
process.env.DIRETOR_LOGINS = {json.dumps(diretor_logins)};
(async () => {{
{unico["with"]["script"]}
}})().then(() => console.log(JSON.stringify(chamadas)));
"""
    saida = subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


@precisa_node
def test_dono_do_card_deixa_o_card_do_diretor_com_a_action_dele() -> None:
    """Colaborador, o diretor passaria no filtro da dono-do-card e viraria dono do próprio card."""
    assert rodar_dono_do_card("Felipe-HSM", "outro, felipe-hsm") == []


@precisa_node
def test_dono_do_card_segue_designando_o_socio_autor() -> None:
    chamadas = rodar_dono_do_card("lucassampaioc1", "felipe-hsm")
    assert [c["assignees"] for c in chamadas] == [["lucassampaioc1"]]
