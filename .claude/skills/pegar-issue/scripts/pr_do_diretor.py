"""O PR rascunho do diretor como ponto de partida da fatia (issue #2300, ADR 0113, decisão 3).

O `/to-issues` põe o link do PR do protótipo do diretor na seção "Protótipo" de
uma fatia só. Quem pega essa fatia continua na branch do fork (edição por
mantenedores), põe a label `assumido` pela própria sessão (o check `PR do
diretor assumido` só aceita a label posta por quem não é diretor) e o `/ship`
usa esse PR em vez de abrir outro.

Uso:
  python3 pr_do_diretor.py <N>          no worktree da fatia: `gh pr checkout` da branch
                                        do PR do diretor e a label `assumido`. Imprime
                                        `assumido: #<PR> na branch <branch>`. Sem PR no
                                        "Protótipo" (ou PR fechado), não imprime nada além
                                        de um `aviso:`: siga com a branch de sempre.
  python3 pr_do_diretor.py qual <N>     imprime `#<PR> <branch>` do PR do diretor aberto
                                        da fatia, ou nada.
  python3 pr_do_diretor.py pronto <N> [--corpo <arquivo>]
                                        o PR do diretor sai do rascunho com `Closes #<N>`
                                        no corpo. Com `--corpo`, o corpo do `/ship` vem
                                        antes e o do diretor fica embaixo, em
                                        "Protótipo do diretor". Imprime o número do PR.

Saídas: 0 ok; 2 uso errado; 3 sem edição por mantenedores, a Tarefa do diretor foi
criada e a sessão para (`tarefa do diretor: #<T> ...`); 4 quem roda é diretor e não
assume o próprio PR.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CAMPOS_DO_PR = "number,state,isDraft,author,maintainerCanModify,headRefName,url"
SECAO_DO_DIRETOR = "## Protótipo do diretor"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def gh_com_arquivo(texto: str, *args: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as f:
        f.write(texto)
    try:
        return gh(*args, "--body-file", f.name)
    finally:
        Path(f.name).unlink(missing_ok=True)


def secao(corpo: str, titulo: str) -> str:
    """O texto de `## titulo` até o próximo `## `; vazio sem a seção."""
    m = re.search(rf"^## {re.escape(titulo)}[ \t]*$", corpo, re.MULTILINE)
    if not m:
        return ""
    fim = re.search(r"^## ", corpo[m.end() :], re.MULTILINE)
    return corpo[m.end() : m.end() + fim.start()] if fim else corpo[m.end() :]


def numero_do_prototipo(corpo: str, repo: str) -> str | None:
    """O número do PR deste repositório linkado na seção "Protótipo" da fatia."""
    m = re.search(rf"https://github\.com/{re.escape(repo)}/pull/(\d+)", secao(corpo, "Protótipo"))
    return m.group(1) if m else None


def diretores() -> list[str]:
    logins = os.environ.get("DIRETOR_LOGINS")
    if logins is None:
        try:
            logins = gh("variable", "get", "DIRETOR_LOGINS")
        except subprocess.CalledProcessError:
            logins = ""
    return [login.strip().lower() for login in logins.split(",") if login.strip()]


def pr_da_fatia(n: str, repo: str) -> dict | None:
    """O PR do diretor aberto que a fatia linka, ou None (com um aviso se ele existe e não está aberto)."""
    corpo = json.loads(gh("issue", "view", n, "--json", "body"))["body"] or ""
    numero = numero_do_prototipo(corpo, repo)
    if not numero:
        return None
    pr = json.loads(gh("pr", "view", numero, "--json", CAMPOS_DO_PR))
    if pr["state"] != "OPEN":
        print(f"aviso: o PR #{numero} do Protótipo está {pr['state']}; siga com a branch de sempre")
        return None
    pr["corpo_da_fatia"] = corpo
    return pr


def criar_tarefa_do_diretor(n: str, repo: str, pr: dict, diretor: str | None) -> str:
    """A Tarefa do diretor (`ready-for-human`, no nome dele) que pede a edição por mantenedores.

    A fatia fica bloqueada por ela (`blocked_by`) e ela vira sub-issue do PRD do "Pai".
    """
    mencao = f"@{diretor}, " if diretor else ""
    corpo = (
        f"{mencao}a Vitta vai continuar o seu protótipo, mas ele está fechado para edição. "
        "Falta um clique seu para liberar.\n\n"
        "## Passo a passo\n\n"
        "1. Abra o seu protótipo no GitHub:\n\n"
        f"{pr['url']}\n\n"
        '2. Na coluna da direita, lá embaixo, marque a caixa "Allow edits and access to secrets by maintainers".\n'
        '3. Volte a este card e clique em "Close issue".\n\n'
        "## Como saber que acabou\n\n"
        "A caixa aparece marcada no protótipo e este card está fechado. A Vitta continua dali sozinha.\n\n"
        "---\n\n"
        f"Fatia que espera: #{n}. PR do protótipo: #{pr['number']}.\n"
    )
    args = ["issue", "create", "--title", f"Liberar a edição do protótipo do PR #{pr['number']}",
            "--label", "ready-for-human"]
    if diretor:
        args += ["--assignee", diretor]
    tarefa = gh_com_arquivo(corpo, *args).strip().rsplit("/", 1)[1]
    tarefa_id = gh("api", f"repos/{repo}/issues/{tarefa}", "--jq", ".id").strip()
    gh("api", "-X", "POST", f"repos/{repo}/issues/{n}/dependencies/blocked_by", "-F", f"issue_id={tarefa_id}")
    pai = re.search(r"#(\d+)", secao(pr["corpo_da_fatia"], "Pai"))
    if pai:
        try:
            gh("api", "-X", "POST", f"repos/{repo}/issues/{pai.group(1)}/sub_issues", "-F",
               f"sub_issue_id={tarefa_id}")
        except subprocess.CalledProcessError:
            print(f"aviso: a #{tarefa} não virou sub-issue do PRD #{pai.group(1)}")
    return tarefa


def assumir(n: str, repo: str) -> int:
    pr = pr_da_fatia(n, repo)
    if pr is None:
        return 0
    lista = diretores()
    autor = (pr.get("author") or {}).get("login", "").lower()
    if gh("api", "user", "--jq", ".login").strip().lower() in lista:
        print(f"o PR #{pr['number']} é do diretor: quem assume é a Vitta, não a sessão dele", file=sys.stderr)
        return 4
    if not pr["maintainerCanModify"]:
        diretor = autor if autor in lista else (lista[0] if lista else None)
        tarefa = criar_tarefa_do_diretor(n, repo, pr, diretor)
        print(f"tarefa do diretor: #{tarefa}; o PR #{pr['number']} está sem edição por mantenedores, pare")
        return 3
    gh("pr", "checkout", str(pr["number"]))
    gh("pr", "edit", str(pr["number"]), "--add-label", "assumido")
    print(f"assumido: #{pr['number']} na branch {pr['headRefName']}")
    return 0


def qual(n: str, repo: str) -> int:
    pr = pr_da_fatia(n, repo)
    if pr:
        print(f"#{pr['number']} {pr['headRefName']}")
    return 0


def pronto(n: str, repo: str, arquivo_do_corpo: str | None) -> int:
    pr = pr_da_fatia(n, repo)
    if pr is None:
        return 0
    numero = str(pr["number"])
    atual = json.loads(gh("pr", "view", numero, "--json", "body,isDraft"))
    do_diretor = atual["body"] or ""
    if SECAO_DO_DIRETOR in do_diretor:  # o /ship rodou antes (--resume): o do diretor é o que está embaixo
        do_diretor = do_diretor.split(SECAO_DO_DIRETOR, 1)[1].strip()
    corpo = do_diretor
    if arquivo_do_corpo:
        novo = Path(arquivo_do_corpo).read_text(encoding="utf-8").rstrip()
        corpo = f"{novo}\n\n{SECAO_DO_DIRETOR}\n\n{do_diretor.strip()}\n"
    if not re.search(rf"\b(close[sd]?|fix(e[sd])?|resolve[sd]?) #{n}\b", corpo, re.IGNORECASE):
        corpo = f"{corpo.rstrip()}\n\nCloses #{n}\n"
    if corpo != (atual["body"] or ""):
        gh_com_arquivo(corpo, "pr", "edit", numero)
    if atual["isDraft"]:
        gh("pr", "ready", numero)
    print(numero)
    return 0


def main(argv: list[str]) -> int:
    corpo = None
    if "--corpo" in argv:
        i = argv.index("--corpo")
        corpo = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2 :]
        if corpo is None:
            print(__doc__, file=sys.stderr)
            return 2
    modo, resto = (argv[0], argv[1:]) if argv and argv[0] in ("qual", "pronto") else ("assumir", argv)
    if len(resto) != 1 or not resto[0].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    repo = gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
    if modo == "qual":
        return qual(resto[0], repo)
    if modo == "pronto":
        return pronto(resto[0], repo, corpo)
    return assumir(resto[0], repo)


if __name__ == "__main__":
    for fluxo in (sys.stdout, sys.stderr):  # Windows: o pipe sai em cp1252
        fluxo.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
