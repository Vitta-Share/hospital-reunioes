"""O `/pegar-issue` retoma o PR rascunho do diretor (issue #2300, ADR 0113, decisão 3).

A fatia que leva o link do PR do diretor na seção "Protótipo" continua nele:
o `pr_do_diretor.py` faz o checkout da branch do fork (sem branch nova), põe a
label `assumido` pela sessão de quem assumiu e, no `/ship`, tira o PR do
rascunho com o `Closes` da fatia. Sem edição por mantenedores, cria a Tarefa
do diretor e para. Os testes rodam o script como o agente roda, com um `gh` de
mentira no PATH que anota cada chamada: o GitHub de verdade não entra.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / ".claude" / "skills" / "pegar-issue" / "scripts" / "pr_do_diretor.py"

REPO = "hsm/hospital-reunioes"
DIRETOR = "felipe-hsm"
QUEM_ASSUME = "lucassampaioc1"

FATIA_COM_PROTOTIPO = f"""## 👔 Para o diretor

**O que muda:** o relatório sai por setor.

---

## Pai

#902: o PRD de onde esta fatia saiu.

## Protótipo

https://github.com/{REPO}/pull/77, o protótipo do diretor.

## O que construir

O relatório por setor.
"""

FATIA_SEM_PROTOTIPO = """## Pai

#902: o PRD de onde esta fatia saiu.

## O que construir

Outra parte do PRD.
"""

GH_FALSO = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args, ensure_ascii=False) + "\n")
estado = json.loads(Path(os.environ["GH_ESTADO"]).read_text(encoding="utf-8"))


def valor(flag):
    return args[args.index(flag) + 1] if flag in args else None


def gravar():
    Path(os.environ["GH_ESTADO"]).write_text(json.dumps(estado), encoding="utf-8")


def campos(dado):
    pedidos = (valor("--json") or "").split(",")
    return {k: v for k, v in dado.items() if k in pedidos}


if args[:2] == ["repo", "view"]:
    print(estado["repo"])
elif args[:2] == ["api", "user"]:
    print(estado["login"])
elif args[:3] == ["variable", "get", "DIRETOR_LOGINS"]:
    print(estado["diretor_logins"])
elif args[:2] == ["issue", "view"]:
    print(json.dumps(campos(estado["issues"][args[2]])))
elif args[:2] == ["pr", "view"]:
    pr = estado["prs"].get(args[2])
    if pr is None:
        sys.stderr.write("no pull requests found\n")
        sys.exit(1)
    print(json.dumps(campos(pr)))
elif args[:2] == ["pr", "checkout"]:
    estado["checkout"] = args[2:]
    gravar()
elif args[:2] == ["pr", "edit"]:
    pr = estado["prs"][args[2]]
    if valor("--add-label"):
        pr.setdefault("labels", []).append({"name": valor("--add-label")})
        estado.setdefault("quem_pos", []).append(estado["login"])
    if valor("--body-file"):
        pr["body"] = Path(valor("--body-file")).read_text(encoding="utf-8")
    gravar()
elif args[:2] == ["pr", "ready"]:
    estado["prs"][args[2]]["isDraft"] = False
    gravar()
elif args[:2] == ["issue", "create"]:
    numero = str(990 + len(estado.setdefault("criadas", [])))
    estado["criadas"].append({
        "numero": numero,
        "titulo": valor("--title"),
        "corpo": Path(valor("--body-file")).read_text(encoding="utf-8"),
        "labels": [args[i + 1] for i, a in enumerate(args) if a == "--label"],
        "assignees": [args[i + 1] for i, a in enumerate(args) if a == "--assignee"],
    })
    gravar()
    print(f"https://github.com/{estado['repo']}/issues/{numero}")
elif args[:1] == ["api"]:
    caminho = next(a for a in args[1:] if a.startswith("repos/"))
    if "-X" in args or "--method" in args:
        estado.setdefault("posts", []).append([caminho] + [a for a in args if "=" in a])
        gravar()
        print("{}")
    else:
        print(int(caminho.rsplit("/", 1)[1]) * 1000)
else:
    sys.stderr.write(f"gh de mentira: chamada que o teste não conhece: {args}\n")
    sys.exit(9)
'''


def pr_do_diretor(**mudar) -> dict:
    pr = {
        "number": 77,
        "state": "OPEN",
        "isDraft": True,
        "author": {"login": DIRETOR},
        "maintainerCanModify": True,
        "headRefName": "prototype/902-relatorio-por-setor",
        "url": f"https://github.com/{REPO}/pull/77",
        "body": "O protótipo responde se o relatório por setor faz sentido.\n\nRefs #902\n",
        "labels": [],
    }
    pr.update(mudar)
    return pr


def rodar(tmp_path: Path, *args: str, corpo: str = FATIA_COM_PROTOTIPO, pr: dict | None = None,
          login: str = QUEM_ASSUME) -> tuple[subprocess.CompletedProcess, dict, list[list[str]]]:
    falso = tmp_path / "bin"
    falso.mkdir(exist_ok=True)
    gh = falso / "gh"
    gh.write_text(f"#!{sys.executable}\n" + GH_FALSO.split("\n", 1)[1], encoding="utf-8")
    gh.chmod(0o755)
    estado_arq = tmp_path / "estado.json"
    if not estado_arq.exists():
        estado_arq.write_text(json.dumps({
            "repo": REPO,
            "login": login,
            "diretor_logins": DIRETOR,
            "issues": {"2300": {"body": corpo, "number": 2300}},
            "prs": {"77": pr if pr is not None else pr_do_diretor()},
        }), encoding="utf-8")
    log = tmp_path / "gh.log"
    ambiente = {k: v for k, v in os.environ.items() if k != "DIRETOR_LOGINS"}
    ambiente.update(PATH=f"{falso}{os.pathsep}{os.environ['PATH']}", GH_LOG=str(log), GH_ESTADO=str(estado_arq))
    feito = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                           encoding="utf-8", env=ambiente)
    chamadas = [json.loads(linha) for linha in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return feito, json.loads(estado_arq.read_text(encoding="utf-8")), chamadas


def test_fatia_com_o_pr_do_diretor_faz_checkout_da_branch_do_fork_sem_branch_nova(tmp_path):
    feito, estado, chamadas = rodar(tmp_path, "2300")

    assert feito.returncode == 0, feito.stderr
    assert estado["checkout"] == ["77"]
    assert feito.stdout.strip() == "assumido: #77 na branch prototype/902-relatorio-por-setor"
    assert not [c for c in chamadas if c[:2] == ["pr", "create"]]


def test_label_assumido_entra_pela_sessao_de_quem_assumiu_e_o_check_passa(tmp_path):
    from test_pr_do_diretor import rodar_check

    feito, estado, _ = rodar(tmp_path, "2300")

    assert feito.returncode == 0, feito.stderr
    labels = [l["name"] for l in estado["prs"]["77"]["labels"]]
    assert labels == ["assumido"]
    assert estado["quem_pos"] == [QUEM_ASSUME]
    assert rodar_check(DIRETOR, labels, diretor_logins=DIRETOR, quem_pos=estado["quem_pos"]) is None


def test_sessao_do_proprio_diretor_nao_assume_o_pr(tmp_path):
    feito, estado, _ = rodar(tmp_path, "2300", login=DIRETOR)

    assert feito.returncode == 4
    assert "checkout" not in estado
    assert estado["prs"]["77"]["labels"] == []


def test_sem_edicao_por_mantenedores_cria_a_tarefa_do_diretor_e_para(tmp_path):
    feito, estado, _ = rodar(tmp_path, "2300", pr=pr_do_diretor(maintainerCanModify=False))

    assert feito.returncode == 3
    assert feito.stdout.strip().startswith("tarefa do diretor: #990;")
    (tarefa,) = estado["criadas"]
    assert tarefa["labels"] == ["ready-for-human"]
    assert tarefa["assignees"] == [DIRETOR]
    assert f"https://github.com/{REPO}/pull/77\n" in tarefa["corpo"]
    assert "Allow edits and access to secrets by maintainers" in tarefa["corpo"]
    assert "## Como saber que acabou" in tarefa["corpo"]
    # a fatia espera a Tarefa (bloqueio nativo), que vira filha do PRD do "Pai"
    assert estado["posts"] == [
        [f"repos/{REPO}/issues/2300/dependencies/blocked_by", "issue_id=990000"],
        [f"repos/{REPO}/issues/902/sub_issues", "sub_issue_id=990000"],
    ]
    # e a sessão para: nada de checkout nem label
    assert "checkout" not in estado
    assert estado["prs"]["77"]["labels"] == []


def test_fatia_sem_prototipo_nao_mexe_em_pr_nenhum(tmp_path):
    feito, estado, chamadas = rodar(tmp_path, "2300", corpo=FATIA_SEM_PROTOTIPO)

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == ""
    assert "checkout" not in estado
    assert not [c for c in chamadas if c[:1] == ["pr"]]


def test_pr_do_prototipo_ja_fechado_avisa_e_segue_com_a_branch_de_sempre(tmp_path):
    feito, estado, _ = rodar(tmp_path, "2300", pr=pr_do_diretor(state="CLOSED"))

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.startswith("aviso: o PR #77 do Protótipo está CLOSED")
    assert "checkout" not in estado


def test_qual_imprime_o_pr_e_a_branch_do_fork(tmp_path):
    feito, _, _ = rodar(tmp_path, "qual", "2300")

    assert feito.stdout.strip() == "#77 prototype/902-relatorio-por-setor"


def test_ship_nao_abre_pr_novo_tira_o_do_diretor_do_rascunho_com_o_closes_da_fatia(tmp_path):
    corpo_do_ship = tmp_path / "pr-corpo.md"
    corpo_do_ship.write_text("## Valor entregue\n\n**O que muda:** sai por setor.\n\nCloses #2300\n", encoding="utf-8")

    feito, estado, chamadas = rodar(tmp_path, "pronto", "2300", "--corpo", str(corpo_do_ship))

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.strip() == "77"
    pr = estado["prs"]["77"]
    assert pr["isDraft"] is False
    assert pr["body"].startswith("## Valor entregue")
    assert pr["body"].count("Closes #2300") == 1
    # o que o diretor escreveu fica, embaixo
    assert "## Protótipo do diretor\n\nO protótipo responde se o relatório por setor faz sentido." in pr["body"]
    assert not [c for c in chamadas if c[:2] == ["pr", "create"]]


def test_pronto_sem_corpo_novo_acrescenta_o_closes_ao_corpo_do_diretor(tmp_path):
    feito, estado, _ = rodar(tmp_path, "pronto", "2300")

    assert feito.returncode == 0, feito.stderr
    assert estado["prs"]["77"]["body"].rstrip().endswith("Refs #902\n\nCloses #2300")


def test_pronto_de_novo_no_resume_nao_empilha_o_corpo_do_diretor(tmp_path):
    corpo_do_ship = tmp_path / "pr-corpo.md"
    corpo_do_ship.write_text("## Valor entregue\n\nCloses #2300\n", encoding="utf-8")
    rodar(tmp_path, "pronto", "2300", "--corpo", str(corpo_do_ship))

    _, estado, _ = rodar(tmp_path, "pronto", "2300", "--corpo", str(corpo_do_ship))

    assert estado["prs"]["77"]["body"].count("## Protótipo do diretor") == 1


# ------------------------------------------------ as skills que usam o script

SKILLS = RAIZ / ".claude" / "skills"


def secao_md(texto: str, titulo: str) -> str:
    """O trecho do título até o próximo título de nível igual ou maior."""
    import re

    m = re.search(rf"^(#+) {re.escape(titulo)}\s*$", texto, re.MULTILINE)
    assert m, f"seção '{titulo}' não encontrada"
    resto = texto[m.end() :]
    fim = re.search(rf"^#{{1,{len(m.group(1))}}} ", resto, re.MULTILINE)
    return resto[: fim.start()] if fim else resto


def ler(skill: str) -> str:
    return (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")


def test_to_issues_leva_o_link_do_pr_do_diretor_para_uma_fatia_so():
    regra = secao_md(ler("to-issues"), "A fatia que continua o protótipo do diretor")

    assert "uma fatia só" in regra
    assert "## Protótipo" in regra
    # a seção do modelo do corpo é a que o script lê
    modelo = ler("to-issues").split("<issue-template>", 1)[1].split("</issue-template>", 1)[0]
    assert "\n## Protótipo\n" in modelo


def test_pegar_issue_assume_o_pr_do_diretor_no_lugar_da_branch_nova():
    passo = secao_md(ler("pegar-issue"), "6. Criar o worktree da issue a partir da `origin/main`")

    assert "pr_do_diretor.py <N>" in passo
    assert "assumido:" in passo
    assert "saída 3" in passo.lower()


def test_ship_usa_o_pr_do_diretor_no_lugar_do_gh_pr_create():
    regra = secao_md(ler("ship"), "PR do diretor")

    assert "pr_do_diretor.py qual <N>" in regra
    assert "pr_do_diretor.py pronto <N> --corpo" in regra
    assert "`git push`" in regra


def test_implementador_da_onda_assume_o_pr_do_diretor():
    agente = (RAIZ / ".claude" / "agents" / "onda-implementador.md").read_text(encoding="utf-8")

    assert "pr_do_diretor.py <N>" in agente


# ------------------------------------- a conferência do lote acha o PR do fork


def test_conferencia_do_lote_le_o_head_do_pr_do_diretor_pela_refs_pull(tmp_path, monkeypatch):
    """A branch do PR do diretor mora no fork: neste repositório só há a `refs/pull/<n>/head`."""
    import importlib.util

    env_git = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
               "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    for k, v in env_git.items():
        monkeypatch.setenv(k, v)

    def git(cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    obra = tmp_path / "obra"
    obra.mkdir()
    git(obra, "init", "-q", "-b", "main")
    (obra / "a.txt").write_text("1\n")
    git(obra, "add", "a.txt")
    git(obra, "commit", "-q", "-m", "base")
    git(obra, "checkout", "-q", "-b", "prototipo")
    (obra / "a.txt").write_text("2\n")
    git(obra, "commit", "-q", "-am", "prototipo")
    head = git(obra, "rev-parse", "HEAD")
    remoto = tmp_path / "remoto.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remoto))
    git(obra, "push", "-q", str(remoto), "main", "prototipo:refs/pull/77/head")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(remoto), str(clone))

    falso = tmp_path / "bin"
    falso.mkdir()
    (falso / "gh").write_text(
        "#!/bin/sh\necho '{\"headRefName\": \"prototype/902-relatorio\", \"isCrossRepository\": true}'\n"
    )
    (falso / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{falso}{os.pathsep}{os.environ['PATH']}")
    spec = importlib.util.spec_from_file_location(
        "conferir_lote", RAIZ / ".claude" / "skills" / "onda-enxuta" / "scripts" / "conferir_lote.py"
    )
    conferir_lote = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conferir_lote)

    assert conferir_lote.prs_do_github(clone, [77]) == [
        {"number": 77, "branch": "prototype/902-relatorio", "head": head}
    ]
