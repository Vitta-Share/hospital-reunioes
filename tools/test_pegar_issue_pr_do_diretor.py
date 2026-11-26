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
