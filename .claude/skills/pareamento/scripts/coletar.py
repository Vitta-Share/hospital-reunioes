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
import hashlib
import json
import re
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


def versao(issue: dict, quem: str) -> str:
    """Muda quando muda o que a descrição conta: título, corpo, comentários ou dono.

    Label, atribuição a um agente e reações mudam o `updated_at` sem mudar a
    descrição; por isso o cache não usa a data.
    """
    base = "\x1f".join([issue.get("title") or "", issue.get("body") or "", str(issue.get("comments", 0)), quem])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


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


BLOQUEIO_NO_TEXTO = re.compile(
    r"(?:bloquead[oa] por|depende d[oa]s?|espera o|espere o|esperando o)[:\s]*((?:#\d+[\s,e]*)+)", re.IGNORECASE
)


def bloqueio_no_texto(corpo: str, espera: list[int], abertos: set[int], proprio: int) -> list[int]:
    """Cards abertos que o corpo diz que este espera, mas que o bloqueio nativo não tem.

    "Bloqueada por: #2330", "depende do #12", "espere o #9 fechar". O que já é bloqueio
    nativo, o próprio card e card fechado ficam de fora.
    """
    achados: set[int] = set()
    for m in BLOQUEIO_NO_TEXTO.finditer(corpo or ""):
        achados |= {int(n) for n in re.findall(r"#(\d+)", m.group(1))}
    return sorted(n for n in achados if n in abertos and n not in espera and n != proprio)


def voltou_do_diretor(dono_do_card: str, labels: list[str], comentarios: list[dict], diretores: set[str]) -> bool:
    """A pergunta que o diretor já respondeu: card de quem roda, ainda com `needs-info`, e o último
    comentário do time é do diretor. Pela ADR 0113 (decisão 4) quem perguntou grava a decisão e solta o card."""
    if dono_do_card != "eu" or "needs-info" not in labels:
        return False
    do_time = [c for c in comentarios if confiavel(c)]
    return bool(do_time) and do_time[-1]["user"]["login"] in diretores


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
                "criado_em": i.get("created_at", ""),
                "criado_por": nomes.get((i.get("user") or {}).get("login", ""), {}).get("nome", (i.get("user") or {}).get("login", "")),
                "versao": versao(i, quem),
                "corpo": corpo_do_card(i),
                "confiavel": confiavel(i),
                "no_texto": [
                    chave(p["nome"], m)
                    for m in bloqueio_no_texto(corpo_do_card(i), d.get("espera", []), set(por_numero), n)
                ] if confiavel(i) else [],
                "voltou": False,
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


JANELA_DIAS = 14
MOVIMENTOS_MAX = 40
DEPLOYS_MAX = 8
PAGINAS_DE_EVENTOS = 3


def _data(iso: str) -> datetime:
    return datetime.fromisoformat((iso or "1970-01-01T00:00:00+00:00").replace("Z", "+00:00"))


def movimentos(nome: str, eventos: list[dict], issues: list[dict], comentarios: list[dict], eu: str,
               diretores: set[str], gente: dict, agora: str) -> list[dict]:
    """O que o diretor fez nos cards nos últimos 14 dias, o mais novo primeiro: criou, passou para você,
    assumiu, tirou do nome, comentou, fechou ou reabriu; e o card que você passou a ele.

    O "tirou do nome" que vem junto do "passou para você" (o mesmo card, até 2 minutos) não conta duas
    vezes. Título de issue aberta por quem não é do time não aparece.
    """
    limite = _data(agora).timestamp() - JANELA_DIAS * 86400
    nome_de = lambda login: gente.get(login, {}).get("nome", login)  # noqa: E731
    # O comentário não traz o título: vem da issue aberta ou, no card já fechado, do evento que a cita.
    por_numero = {**{e["issue"]["number"]: e["issue"] for e in eventos if e.get("issue")}, **{i["number"]: i for i in issues}}

    def titulo(item: dict | None, n: int) -> str:
        if not item:
            return f"#{n}"
        return (item.get("title") or f"#{n}") if confiavel(item) else "(título de fora do time)"

    def mov(quando, tipo, quem, n, item, url):
        return {"quando": quando, "tipo": tipo, "quem": nome_de(quem), "chave": chave(nome, n), "numero": n,
                "titulo": titulo(item, n), "url": url}

    passou_em = [(e["issue"]["number"], _data(e["created_at"]).timestamp()) for e in eventos
                 if e.get("event") == "assigned" and (e.get("assignee") or {}).get("login") == eu
                 and e["actor"]["login"] in diretores]
    saida = []
    for e in eventos:
        tipo, ator = e.get("event"), (e.get("actor") or {}).get("login", "")
        alvo = (e.get("assignee") or {}).get("login")
        i = e.get("issue") or {}
        n, quando = i.get("number"), e.get("created_at", "")
        if n is None or _data(quando).timestamp() < limite:
            continue
        if tipo == "assigned" and alvo in diretores:
            o_que = "assumiu" if ator in diretores else "passou_ao_diretor"
        elif tipo == "assigned" and alvo == eu and ator in diretores:
            o_que = "passou_a_voce"
        elif tipo == "unassigned" and alvo in diretores and ator in diretores:
            t = _data(quando).timestamp()
            if any(m == n and abs(t - s) <= 120 for m, s in passou_em):
                continue
            o_que = "soltou"
        elif tipo in ("closed", "reopened") and ator in diretores:
            o_que = "fechou" if tipo == "closed" else "reabriu"
        else:
            continue
        saida.append(mov(quando, o_que, ator, n, i, i.get("html_url", "")))
    for i in issues:
        quem = (i.get("user") or {}).get("login")
        if "pull_request" not in i and quem in diretores and _data(i.get("created_at", "")).timestamp() >= limite:
            saida.append(mov(i["created_at"], "criou", quem, i["number"], i, i["html_url"]))
    for c in comentarios:
        quem = (c.get("user") or {}).get("login")
        if quem not in diretores or not confiavel(c) or _data(c.get("created_at", "")).timestamp() < limite:
            continue
        n = int(c["issue_url"].rstrip("/").split("/")[-1])
        saida.append(mov(c["created_at"], "comentou", quem, n, por_numero.get(n), c.get("html_url", "")))
    saida.sort(key=lambda m: _data(m["quando"]), reverse=True)
    return saida[:MOVIMENTOS_MAX]


def deploys_recentes(historico: dict, repo: str) -> list[dict]:
    """Os últimos deploys do `docs/spec/deploy/history.json` do Projeto, o mais novo primeiro."""
    deploys = sorted((historico or {}).get("deploys") or [], key=lambda d: _data(d.get("at", "")), reverse=True)
    return [{"quando": d.get("at", ""), "versao": d.get("app_version") or "", "assunto": d.get("subject") or "",
             "resultado": d.get("result") or "", "url": f"https://github.com/{repo}/commit/{d['sha']}" if d.get("sha") else ""}
            for d in deploys[:DEPLOYS_MAX]]


def ler_linha_do_tempo(repo: str, issues: list[dict], eu: str, diretores: set[str], gente: dict, nome: str, agora: str) -> dict:
    """Os deploys e os movimentos do diretor de um Projeto. Falha de leitura vira lista vazia: a linha do
    tempo é um extra da Ala, não pode derrubar a coleta."""
    try:
        historico = gh("api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/docs/spec/deploy/history.json")
    except (RuntimeError, ValueError):
        historico = {}
    eventos: list[dict] = []
    try:
        for pagina in range(1, PAGINAS_DE_EVENTOS + 1):
            lote = gh("api", f"repos/{repo}/issues/events?per_page=100&page={pagina}") or []
            eventos += lote
            if len(lote) < 100:
                break
        desde = datetime.fromtimestamp(_data(agora).timestamp() - JANELA_DIAS * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        comentarios = gh_paginado(f"repos/{repo}/issues/comments?since={desde}&per_page=100")
    except (RuntimeError, ValueError):
        eventos, comentarios = [], []
    return {"deploys": deploys_recentes(historico, repo),
            "movimentos": movimentos(nome, eventos, issues, comentarios, eu, diretores, gente, agora)}


def ler_projeto(cfg: dict) -> dict:
    repo = cfg["repo"]
    issues = [i for i in gh_paginado(f"repos/{repo}/issues?state=open&per_page=100") if "pull_request" not in i]
    pais, prds = {}, []
    for i in issues:
        if eh_prd(i):
            s = i["sub_issues_summary"]
            prds.append({"chave": chave(cfg["nome"], i["number"]), "numero": i["number"], "titulo": i["title"],
                         "url": i["html_url"], "feitas": s.get("completed", 0), "total": s.get("total", 0),
                         "atualizado": i["updated_at"], "versao": versao(i, "PRD"),
                         "corpo": corpo_do_card(i), "confiavel": confiavel(i)})
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
    versao_app = migracao = None
    if cfg.get("health"):
        try:
            with urllib.request.urlopen(cfg["health"], timeout=10) as r:
                h = json.load(r)
            versao_app, migracao = h.get("version"), h.get("migracao")
        except (OSError, ValueError):
            pass
    return {"nome": cfg["nome"], "repo": repo, "issues": issues, "deps": deps, "pais": pais,
            "prds": prds, "prs": prs, "versao": versao_app, "migracao": migracao}


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
    titulo = item["titulo"] if item.get("confiavel", True) else "(título omitido: a issue foi aberta por quem não é do time)"
    partes = [f"## {k} ({rotulo})", f"versao: {item['versao']}", ""]
    partes.append(_cercado("título da issue", titulo))
    partes.append(_cercado("corpo da issue", item.get("corpo") or ""))
    for c in comentarios:
        partes.append(_cercado(f"comentário de {c['user']['login']}", (c.get("body") or "")[:1200]))
    return "\n".join(partes) + "\n"


def faltam(cards: dict, prds: list[dict], descricoes: dict) -> list[str]:
    """Chaves sem descrição, ou com descrição de antes da última mudança do card."""
    itens = [c for c in cards.values() if not c.get("satelite")] + prds
    return [x["chave"] for x in itens if (descricoes.get(x["chave"]) or {}).get("versao") != x["versao"]]


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
    comentarios: dict[str, list] = {}
    repo_de = {p["nome"]: p["repo"] for p in projetos}
    for c in cards.values():
        if c["dono"] == "eu" and "needs-info" in c["labels"]:
            comentarios[c["chave"]] = gh("api", f"repos/{repo_de[c['projeto']]}/issues/{c['numero']}/comments?per_page=100")
            c["voltou"] = voltou_do_diretor(c["dono"], c["labels"], comentarios[c["chave"]], diretores)

    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for p in projetos:
        p.update(ler_linha_do_tempo(p["repo"], p["issues"], eu, diretores, gente, p["nome"], agora))

    estado = {
        "gerado_em": agora,
        "eu": {"login": eu, "nome": gente.get(eu, {}).get("nome", eu)},
        "diretor": {"login": ",".join(sorted(diretores)),
                    "nome": ", ".join(gente[d]["nome"] for d in sorted(diretores)) or "diretor"},
        "projetos": [{"nome": p["nome"], "repo": p["repo"], "versao": p["versao"], "migracao": p["migracao"],
                      "abertas": len(p["issues"]), "prs": p["prs"], "prds": p["prds"],
                      "deploys": p["deploys"], "movimentos": p["movimentos"]} for p in projetos],
        "cards": cards,
    }
    (args.pasta / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    # O que a Ala fez vale para a coleta anterior: a nova já vê o card passado e o bloqueio gravado.
    (args.pasta / "feitos.json").unlink(missing_ok=True)

    arq_desc = args.pasta / "descricoes.json"
    descricoes = json.loads(arq_desc.read_text(encoding="utf-8")) if arq_desc.exists() else {}
    lista = faltam(cards, prds, descricoes)
    itens = {**{c["chave"]: c for c in cards.values()}, **{p["chave"]: p for p in prds}}
    partes = []
    for k in lista:
        x = itens[k]
        proj = next(p for p in projetos if p["nome"] == k.split("#")[0])
        coment = comentarios.get(k) or gh("api", f"repos/{proj['repo']}/issues/{x['numero']}/comments?per_page=100")
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
