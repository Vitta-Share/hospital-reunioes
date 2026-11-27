#!/usr/bin/env python3
"""Passa um card ao diretor (ADR 0113, decisão 4) a partir de um rascunho aprovado pelo Pedro.

Escreve no começo do corpo a seção "🔁 Por que este card passou para você", que o Claude
do diretor lê quando ele pergunta "o que está no meu nome?" (`/setup-diretor`, Parte 11),
comenta com a menção a ele e troca o dono e a label de estado. Quem chama é a Ala Pareamento do PedroOS, pelo acao.py,
(o botão Mandar ao diretor) ou a sessão de passagem, sempre depois do "pode" do Pedro.

Rascunho (JSON): {"tipo": "needs-info" | "ready-for-human", "por_que": "...", "preciso": "...",
"opcoes": ["...", ...], "recomendacao": "...", "devolver": "..."}.

Uso: python3 .claude/skills/pareamento/scripts/passagem.py --repo <dono/repo> --numero N --rascunho <arquivo.json>
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ESTADOS = ("needs-triage", "needs-info", "ready-for-agent", "ready-for-human")
TIPOS = ("needs-info", "ready-for-human")
SECAO = re.compile(r"^## 🔁 Por que este card (?:passou para você|está com você)[^\n]*\n.*?(?=^## |^---[ \t]*$|\Z)", re.M | re.S)
RAIZ = Path(__file__).resolve().parents[4]


def conferir(r: dict) -> dict:
    """O rascunho limpo, ou ValueError dizendo o que falta."""
    if r.get("tipo") not in TIPOS:
        raise ValueError("tipo precisa ser needs-info (pergunta) ou ready-for-human (coisa a fazer)")
    limpo = {k: str(r.get(k) or "").strip() for k in ("por_que", "preciso", "recomendacao", "devolver")}
    for k in ("por_que", "preciso", "devolver"):
        if not limpo[k]:
            raise ValueError(f"falta o campo {k}")
    opcoes = [str(o).strip() for o in r.get("opcoes") or [] if str(o).strip()]
    if r["tipo"] == "needs-info" and len(opcoes) > 1 and not limpo["recomendacao"]:
        raise ValueError("pergunta com opções precisa da recomendação")
    texto = " ".join([*limpo.values(), *opcoes])
    if chr(0x2014) in texto or chr(0x2013) in texto:
        raise ValueError("o rascunho tem travessão ou meia-risca")
    return {"tipo": r["tipo"], **limpo, "opcoes": opcoes}


def secao(r: dict, de: str, hoje: date) -> str:
    partes = [
        "## 🔁 Por que este card passou para você",
        f"**De:** {de}, em {hoje.strftime('%d/%m/%Y')}.",
        f"**Por quê:** {r['por_que']}",
        f"**O que preciso de você:** {r['preciso']}",
    ]
    if r["opcoes"]:
        titulo = "**As opções:**" if r["tipo"] == "needs-info" else "**Os passos:**"
        partes.append(titulo + "\n" + "\n".join(f"{i}. {o}" for i, o in enumerate(r["opcoes"], 1)))
    if r["recomendacao"]:
        partes.append(f"**Minha recomendação:** {r['recomendacao']}")
    partes.append(f"**Como devolver:** {r['devolver']}")
    return "\n\n".join(partes) + "\n"


def corpo_novo(corpo: str, nova: str) -> str:
    """A seção nova no começo; a antiga (de uma passagem anterior) sai, com o separador dela."""
    resto = SECAO.sub("", corpo or "", count=1)
    resto = re.sub(r"\A\s*---[ \t]*\n", "", resto.lstrip())
    return nova + "\n---\n\n" + resto.lstrip()


def comentario(diretor: str, numero: int) -> str:
    return (
        "<!-- automacao -->\n"
        f"@{diretor} este card passou para o seu nome. O motivo está no começo da descrição, na parte "
        f"\"Por que este card passou para você\". Se preferir, peça ao seu Claude: \"lê o card {numero} e me "
        "explica por que ele está comigo\".\n"
    )


def troca(tipo: str, labels: list[str], eu: str, diretor: str) -> list[str]:
    """Os argumentos do `gh issue edit` que passam o card: dono e uma label de estado só."""
    args = ["--add-assignee", diretor, "--remove-assignee", eu, "--add-label", tipo]
    for lab in labels:
        if lab in ESTADOS and lab != tipo:
            args += ["--remove-label", lab]
    return args


def pessoas_do_fluxo(raiz: Path = RAIZ) -> list[dict]:
    return json.loads((raiz / ".claude" / "fluxo.json").read_text(encoding="utf-8")).get("pessoas") or []


def diretor_do_fluxo(pessoas: list[dict]) -> str:
    achados = [p["login"] for p in pessoas if p.get("papel") == "diretor"]
    if len(achados) != 1:
        raise ValueError("o .claude/fluxo.json precisa de exatamente um diretor")
    return achados[0]


def _gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {r.stderr.strip()[:300]}")
    return r.stdout


def passar(repo: str, numero: int, rascunho: dict, gh=_gh, hoje: date | None = None, pessoas=None) -> dict:
    r = conferir(rascunho)
    issue = json.loads(gh("api", f"repos/{repo}/issues/{numero}"))
    if issue.get("state") != "open":
        raise ValueError("o card está fechado")
    labels = [lab["name"] for lab in issue.get("labels") or []]
    if "in-progress" in labels:
        raise ValueError("o card está rodando numa onda")
    eu = json.loads(gh("api", "user"))["login"]
    pessoas = pessoas_do_fluxo() if pessoas is None else pessoas
    diretor = diretor_do_fluxo(pessoas)
    de = next((p.get("nome") for p in pessoas if p.get("login") == eu), None) or eu
    corpo = corpo_novo(issue.get("body") or "", secao(r, de, hoje or date.today()))
    with tempfile.TemporaryDirectory() as tmp:
        arq_corpo, arq_coment = Path(tmp) / "corpo.md", Path(tmp) / "comentario.md"
        arq_corpo.write_text(corpo, encoding="utf-8")
        arq_coment.write_text(comentario(diretor, numero), encoding="utf-8")
        gh("issue", "edit", str(numero), "--repo", repo, "--body-file", str(arq_corpo))
        gh("issue", "comment", str(numero), "--repo", repo, "--body-file", str(arq_coment))
        gh("issue", "edit", str(numero), "--repo", repo, *troca(r["tipo"], labels, eu, diretor))
    return {"ok": True, "url": issue.get("html_url"), "diretor": diretor, "tipo": r["tipo"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--numero", type=int, required=True)
    ap.add_argument("--rascunho", type=Path, required=True)
    a = ap.parse_args()
    try:
        r = passar(a.repo, a.numero, json.loads(a.rascunho.read_text(encoding="utf-8")))
    except (ValueError, RuntimeError) as e:
        print(f"não passou: {e}", file=sys.stderr)
        return 1
    print(f"passado a {r['diretor']} ({r['tipo']}): {r['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
