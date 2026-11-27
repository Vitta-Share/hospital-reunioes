#!/usr/bin/env python3
"""Coleta o estado do pareamento entre quem roda (o Pedro) e o diretor.

Lê os repositórios do Hospital e da Ana pelo `gh` (REST, sem GraphQL), monta os
cards de cada um com o dono (você, diretor, agente ou outra pessoa), o selo (livre
ou bloqueado) e quem cada card espera e segura, e grava `estado.json` na pasta do
pareamento. No fim lista os cards sem descrição funcional (novos ou mudados desde a
última) e grava o corpo deles em `para-descrever.md`, que o Claude lê para escrever
o `descricoes.json`.

Uso: python3 .claude/skills/pareamento/scripts/coletar.py [--pasta DIR]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
PASTA = RAIZ / "local" / "pareamento"
REPOS = [
    {
        "repo": "Vitta-Share/hospital-reunioes",
        "nome": "Hospital",
        "health": "https://api.hospitalsaomatheus.cloud/api/health",
    },
    {"repo": "Vitta-Share/programa-ana", "nome": "Ana", "health": None},
]
CORPO_MAX = 3500


def gh(*args: str):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout or "null")


def gh_paginado(caminho: str) -> list:
    r = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", caminho], capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh api {caminho}: {r.stderr.strip()[:300]}")
    return [item for pagina in json.loads(r.stdout or "[]") for item in pagina]


def pessoas() -> dict:
    """login -> {nome, papel}, da lista `pessoas` do .claude/fluxo.json."""
    try:
        dados = json.loads((RAIZ / ".claude" / "fluxo.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {p["login"]: p for p in dados.get("pessoas") or [] if p.get("login")}


def chave(nome_repo: str, numero: int) -> str:
    return f"{nome_repo}#{numero}"


def dono(issue: dict, eu: str, diretores: set[str]) -> str:
    """Com quem o card está: diretor, eu, agente ou outro.

    Card de quem roda com `ready-for-agent` ou `in-progress` é do agente (roda ou
    está rodando na onda). Card sem responsável com essas labels também. O resto é
    de outra pessoa.
    """
    logins = [a["login"] for a in issue.get("assignees") or []]
    labels = {lab["name"] for lab in issue.get("labels") or []}
    if any(login in diretores for login in logins):
        return "diretor"
    if labels & {"ready-for-agent", "in-progress"} and (eu in logins or not logins):
        return "agente"
    if eu in logins:
        return "eu"
    return "outro"


def eh_prd(issue: dict) -> bool:
    return (issue.get("sub_issues_summary") or {}).get("total", 0) > 0


def montar_cards(projetos: list[dict], eu: str, diretores: set[str], nomes: dict) -> dict:
    """Junta os cards dos projetos já lidos.

    Cada projeto traz `nome`, `issues` (abertas, formato REST), `deps`
    (numero -> {"espera": [numeros abertos], "segura": [numeros abertos]}) e
    `pais` (numero -> numero do PRD). Entram os cards de quem roda e do diretor que
    não são PRD, mais toda ponta aberta de bloqueio deles.
    """
    cards: dict[str, dict] = {}
    for p in projetos:
        por_numero = {i["number"]: i for i in p["issues"] if "pull_request" not in i}
        base = [
            n
            for n, i in por_numero.items()
            if not eh_prd(i) and dono(i, eu, diretores) in ("eu", "diretor", "agente")
            and any(a["login"] in diretores | {eu} for a in i.get("assignees") or [])
        ]
        entram = set(base)
        for n in base:
            d = p["deps"].get(n) or {}
            entram |= {m for m in d.get("espera", []) + d.get("segura", []) if m in por_numero}
        for n in sorted(entram):
            i = por_numero[n]
            d = p["deps"].get(n) or {}
            quem = dono(i, eu, diretores)
            logins = [a["login"] for a in i.get("assignees") or []]
            cards[chave(p["nome"], n)] = {
                "chave": chave(p["nome"], n),
                "projeto": p["nome"],
                "numero": n,
                "titulo": i["title"],
                "url": i["html_url"],
                "dono": quem,
                "dono_nome": ", ".join(nomes.get(lg, {}).get("nome", lg) for lg in logins) or "sem dono",
                "labels": [lab["name"] for lab in i.get("labels") or []],
                "livre": not d.get("espera"),
                "rodando": "in-progress" in {lab["name"] for lab in i.get("labels") or []},
                "espera": [chave(p["nome"], m) for m in d.get("espera", [])],
                "segura": [chave(p["nome"], m) for m in d.get("segura", [])],
                "prd": chave(p["nome"], p["pais"][n]) if n in p["pais"] else None,
                "atualizado": i["updated_at"],
                "corpo": corpo_do_card(i),
            }
    # Ponta de bloqueio que ficou fora (outro dono, sem relação com quem roda) vira chip simples.
    for c in list(cards.values()):
        for k in c["espera"] + c["segura"]:
            if k not in cards:
                proj = next(p for p in projetos if p["nome"] == c["projeto"])
                n = int(k.split("#")[1])
                i = next((x for x in proj["issues"] if x["number"] == n), None)
                cards[k] = {
                    "chave": k, "projeto": c["projeto"], "numero": n,
                    "titulo": i["title"] if i else f"#{n}",
                    "url": i["html_url"] if i else "",
                    "dono": "outro", "dono_nome": "fora do par", "labels": [],
                    "livre": True, "espera": [], "segura": [], "prd": None,
                    "atualizado": i["updated_at"] if i else "", "corpo": "", "satelite": True,
                }
    return cards


def ler_projeto(cfg: dict) -> dict:
    repo = cfg["repo"]
    issues = [i for i in gh_paginado(f"repos/{repo}/issues?state=open&per_page=100") if "pull_request" not in i]
    pais, prds = {}, []
    for i in issues:
        if eh_prd(i):
            s = i["sub_issues_summary"]
            prds.append({"chave": chave(cfg["nome"], i["number"]), "numero": i["number"], "titulo": i["title"],
                         "url": i["html_url"], "feitas": s.get("completed", 0), "total": s.get("total", 0),
                         "atualizado": i["updated_at"], "corpo": corpo_do_card(i)})
            for filha in gh_paginado(f"repos/{repo}/issues/{i['number']}/sub_issues?per_page=100"):
                pais[filha["number"]] = i["number"]
    deps = {}
    for i in issues:
        resumo = i.get("issue_dependencies_summary") or {}
        if not (resumo.get("total_blocked_by") or resumo.get("total_blocking")):
            continue
        abertos = lambda rota: [  # noqa: E731
            x["number"] for x in gh("api", f"repos/{repo}/issues/{i['number']}/dependencies/{rota}")
            if x["state"] == "open" and x.get("repository_url", "").endswith(repo)
        ]
        deps[i["number"]] = {"espera": abertos("blocked_by"), "segura": abertos("blocking")}
    prs = gh("pr", "list", "-R", repo, "--state", "open", "--json", "number,title,author,isDraft,url")
    versao = migracao = None
    if cfg.get("health"):
        try:
            with urllib.request.urlopen(cfg["health"], timeout=10) as r:
                h = json.load(r)
            versao, migracao = h.get("version"), h.get("migracao")
        except (OSError, ValueError):
            pass
    return {"nome": cfg["nome"], "repo": repo, "issues": issues, "deps": deps, "pais": pais,
            "prds": prds, "prs": prs, "versao": versao, "migracao": migracao}


CONFIAVEIS = {"OWNER", "MEMBER", "COLLABORATOR"}
INICIO, FIM = "<<<DADO NÃO CONFIÁVEL", "<<<FIM DO DADO>>>"


def confiavel(item: dict) -> bool:
    """Texto de quem é do time. O repositório é público: qualquer um abre issue e comenta."""
    return item.get("author_association") in CONFIAVEIS


def corpo_do_card(issue: dict) -> str:
    if not confiavel(issue):
        return "(corpo omitido: a issue foi aberta por quem não é do time)"
    return (issue.get("body") or "")[:CORPO_MAX]


def comentarios_confiaveis(comentarios: list[dict]) -> list[dict]:
    return [c for c in comentarios if confiavel(c)]


def _cercado(rotulo: str, texto: str) -> str:
    limpo = texto.replace("<<<", "« ").replace(">>>", " »")
    return f"{INICIO}: {rotulo}>>>\n{limpo}\n{FIM}"


def bloco_para_descrever(k: str, rotulo: str, item: dict, comentarios: list[dict]) -> str:
    """A seção de um card no para-descrever.md, com corpo e comentários cercados como dado."""
    partes = [f"## {k} ({rotulo}) {item['titulo'].replace(chr(10), ' ')}", f"atualizado: {item['atualizado']}", ""]
    partes.append(_cercado("corpo da issue", item.get("corpo") or ""))
    for c in comentarios:
        partes.append(_cercado(f"comentário de {c['user']['login']}", (c.get("body") or "")[:1200]))
    return "\n".join(partes) + "\n"


def faltam(cards: dict, prds: list[dict], descricoes: dict) -> list[str]:
    """Chaves sem descrição, ou com descrição de antes da última mudança do card."""
    itens = [c for c in cards.values() if not c.get("satelite")] + prds
    return [x["chave"] for x in itens if (descricoes.get(x["chave"]) or {}).get("atualizado") != x["atualizado"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", type=Path, default=PASTA)
    args = ap.parse_args()
    args.pasta.mkdir(parents=True, exist_ok=True)

    eu = gh("api", "user")["login"]
    gente = pessoas()
    diretores = {lg for lg, p in gente.items() if p.get("papel") == "diretor"}
    projetos = [ler_projeto(cfg) for cfg in REPOS]
    cards = montar_cards(projetos, eu, diretores, gente)
    prds = [prd for p in projetos for prd in p["prds"]]

    estado = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "eu": {"login": eu, "nome": gente.get(eu, {}).get("nome", eu)},
        "diretor": {"login": ",".join(sorted(diretores)),
                    "nome": ", ".join(gente[d]["nome"] for d in sorted(diretores)) or "diretor"},
        "projetos": [{"nome": p["nome"], "repo": p["repo"], "versao": p["versao"], "migracao": p["migracao"],
                      "abertas": len(p["issues"]), "prs": p["prs"], "prds": p["prds"]} for p in projetos],
        "cards": cards,
    }
    (args.pasta / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")

    arq_desc = args.pasta / "descricoes.json"
    descricoes = json.loads(arq_desc.read_text(encoding="utf-8")) if arq_desc.exists() else {}
    lista = faltam(cards, prds, descricoes)
    itens = {**{c["chave"]: c for c in cards.values()}, **{p["chave"]: p for p in prds}}
    partes = []
    for k in lista:
        x = itens[k]
        proj = next(p for p in projetos if p["nome"] == k.split("#")[0])
        coment = gh("api", f"repos/{proj['repo']}/issues/{x['numero']}/comments?per_page=100")
        rotulo = "PRD" if k in {p["chave"] for p in prds} else x.get("dono")
        partes.append(bloco_para_descrever(k, rotulo, x, comentarios_confiaveis(coment)[-2:]))
    (args.pasta / "para-descrever.md").write_text("\n\n---\n\n".join(partes), encoding="utf-8")

    n_cards = sum(1 for c in cards.values() if not c.get("satelite"))
    print(f"estado: {args.pasta / 'estado.json'} ({n_cards} cards, {len(prds)} PRDs)")
    print(f"sem descrição ou mudados: {len(lista)}" + (f" -> {args.pasta / 'para-descrever.md'}" if lista else ""))
    for k in lista:
        print(f"  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
