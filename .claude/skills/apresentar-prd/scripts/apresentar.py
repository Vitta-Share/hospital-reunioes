#!/usr/bin/env python3
"""A Apresentação do PRD (issue #1891): monta e publica a página do plano para o diretor validar.

Uso, da raiz do repositório:
  apresentar.py coletar <PRD>                o PRD e as Fatias em JSON, com etapas e Partes numeradas
  apresentar.py montar <PRD> [--saida DIR]   a página de docs/comunicacao/planos/<PRD>/dados.json
  apresentar.py publicar <PRD>               tira o selo validado:diretor e publica o site inteiro
  apresentar.py email <PRD>                  grava o texto do e-mail (link com o código) fora do repo

O segredo do código fica em ~/.config/planos-hsm/segredo (ou $PLANOS_HSM_DIR), nunca no repositório.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
PLANOS = RAIZ / "docs" / "comunicacao" / "planos"
ASSETS = RAIZ / "docs" / "comunicacao" / "_assets"
PACOTE = RAIZ / "hospital-reunioes" / "frontend" / "package.json"
REPO = "pedrorezendefig/hospital-reunioes"
SITE = "https://planos-hsm.vercel.app"
SELO = "validado:diretor"

# A lista da /divulgar: palavra que não pode aparecer no texto que o diretor lê.
TECNICAS = (
    "migration", "endpoint", "API", "PR", "pull request", "deploy", "RLS", "schema",
    "backend", "frontend", "commit", "branch", "merge", "token", "env", "SQL",
    "Supabase", "Coolify", "prompt",
)  # fmt: skip
CAMPOS_DA_PARTE = ("id", "etapa", "titulo", "muda", "vale", "saber", "pronto", "depende")
MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)  # fmt: skip


def _esc(s: object) -> str:
    return _html.escape(str(s), quote=True)


def _textos(x: object) -> list[str]:
    """Todo texto dentro de um dado (dict, lista ou string)."""
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [t for v in x.values() for t in _textos(v)]
    if isinstance(x, list):
        return [t for v in x for t in _textos(v)]
    return []


def problemas(texto: str) -> list[str]:
    """O que impede o texto de ir para o diretor: travessão, número de issue, jargão."""
    erros = []
    if "—" in texto or "–" in texto:
        erros.append("travessão ou meia-risca")
    if re.search(r"#\d{2,}", texto):
        erros.append("número de issue")
    for p in TECNICAS:
        if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", texto, re.IGNORECASE):
            erros.append(f"palavra técnica: {p}")
    return erros


def _numeros(d: dict) -> str:
    return "\n".join(
        f'      <div class="num"><div class="v" data-conta="{int(n["valor"])}">0</div>'
        f'<div class="r">{_esc(n["rotulo"])}</div></div>'
        for n in d["numeros"]
    )


def _decidido(d: dict) -> str:
    dec = d.get("decidido")
    if not dec:
        return ""
    blocos = []
    for b in dec["blocos"]:
        tag = "ol" if b.get("numerado") else "ul"
        itens = "\n".join(
            f'          <li><span class="{"nn" if b.get("numerado") else "ck"}">'
            f"{i if b.get('numerado') else '✓'}</span><span>{_esc(t)}</span></li>"
            for i, t in enumerate(b["itens"], 1)
        )
        blocos.append(
            f'      <div class="bloco">\n        <h3>{_esc(b["titulo"])}</h3>\n'
            f"        <{tag}>\n{itens}\n        </{tag}>\n      </div>"
        )
    return (
        '  <section>\n    <div class="mark">O que você já decidiu</div>\n'
        f'    <h2>{_esc(dec["titulo"])}</h2>\n    <p class="lede">{_esc(dec["texto"])}</p>\n'
        '    <div class="duas">\n' + "\n".join(blocos) + "\n    </div>\n  </section>"
    )


def _fora(d: dict) -> str:
    fora = d.get("fora")
    if not fora:
        return ""
    itens = "".join(f"<span>{_esc(t)}</span>" for t in fora["itens"])
    return (
        '  <section>\n    <div class="mark">Fica de fora</div>\n'
        "    <h2>O que não entra neste pedido</h2>\n"
        f'    <div class="fora">{itens}</div>\n'
        f'    <p class="lede" style="margin-top:14px">{_esc(fora["texto"])}</p>\n  </section>'
    )


def _rodape(d: dict, hoje: dt.date) -> str:
    versao = json.loads(PACOTE.read_text(encoding="utf-8"))["version"]
    return (
        f"{d['contexto']} · Hospital São Matheus · apresentação do plano · "
        f"{MESES[hoje.month - 1]} de {hoje.year} · versão {versao} do app"
    )


def montar(dados: dict, hoje: dt.date | None = None) -> str:
    """O HTML da Apresentação. Recusa (ValueError) texto que o diretor não pode ler."""
    hoje = hoje or dt.date.today()
    plano = {
        "prd": int(dados["prd"]),
        "etapas": [{"nome": e["nome"], "texto": e["texto"]} for e in dados["etapas"]],
        "partes": [{k: p[k] for k in CAMPOS_DA_PARTE} for p in dados["partes"]],
    }
    pagina = {k: v for k, v in dados.items() if k not in ("prd", "etapas", "partes")}
    erros = problemas("\n".join(_textos(pagina) + _textos(plano)))
    if erros:
        raise ValueError("a página não pode ir ao diretor: " + ", ".join(sorted(set(erros))))

    html = (PLANOS / "modelo.html").read_text(encoding="utf-8")
    trocas = {
        "titulo_aba": _esc(dados["titulo_aba"]),
        "descricao": _esc(dados["descricao"]),
        "contexto": _esc(dados["contexto"]),
        "selo": _esc(dados["selo"]),
        "titulo": _esc(dados["titulo"]),
        "destaque": _esc(dados["destaque"]),
        "resumo": _esc(dados["resumo"]),
        "numeros": _numeros(dados),
        "decidido": _decidido(dados),
        "fora": _fora(dados),
        "rodape": _esc(_rodape(dados, hoje)),
    }
    for chave, valor in trocas.items():
        html = html.replace("{{" + chave + "}}", valor)
    json_plano = json.dumps(plano, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("__DADOS__", json_plano)
    sobra = re.findall(r"\{\{\w+\}\}", html)
    if sobra:
        raise ValueError(f"marcador sem valor no modelo: {sobra}")
    # O que o modelo escreve fora dos dados também passa pela mesma régua.
    visivel = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
    visivel = re.sub(r"<[^>]+>", " ", visivel)
    erros = problemas(visivel)
    if erros:
        raise ValueError("o modelo tem texto que o diretor não pode ler: " + ", ".join(erros))
    return html


def dados_do_prd(prd: int) -> dict:
    return json.loads((PLANOS / str(prd) / "dados.json").read_text(encoding="utf-8"))


# --- Coleta: o PRD e as Fatias pelo gh ---------------------------------------


def _campo(bloco: str, rotulo: str) -> str:
    m = re.search(r"\*\*" + re.escape(rotulo) + r":\*\*\s*(.+)", bloco)
    return m.group(1).strip() if m else ""


def _bloco_diretor(corpo: str) -> dict:
    bloco = corpo.split("\n---")[0]
    saber = re.search(r"(?s)O que você precisa saber:\*\*(.*)", bloco)
    return {
        "muda": _campo(bloco, "O que muda"),
        "vale": _campo(bloco, "Por que vale"),
        "saber": re.findall(r"^- (.+)$", saber.group(1), re.M) if saber else [],
    }


def _criterios(corpo: str) -> list[str]:
    m = re.search(r"(?s)## Critérios de aceite\n(.*?)(\n## |\Z)", corpo)
    if not m:
        return []
    return [re.sub(r"^- \[.\] ", "", x) for x in m.group(1).strip().splitlines() if x.startswith("- [")]


def plano(fatias: list[dict]) -> dict:
    """Partes numeradas por etapa (nível no grafo de bloqueios) e as Fatias humanas já fechadas.

    Cada fatia: numero, titulo, estado, labels, corpo, bloqueada_por, comentarios.
    A Parte guarda `issue` só para o agente escrever o texto; a página não leva o número.
    """
    humana_fechada = {
        f["numero"] for f in fatias if f["estado"] == "closed" and "ready-for-human" in f["labels"]
    }
    no_plano = {f["numero"]: f for f in fatias if f["numero"] not in humana_fechada}
    deps = {n: [d for d in f["bloqueada_por"] if d in no_plano] for n, f in no_plano.items()}
    nivel: dict[int, int] = {}

    def etapa(n: int, caminho: tuple = ()) -> int:
        if n in caminho:
            raise ValueError(f"bloqueio em círculo entre as Fatias {caminho + (n,)}")
        if n not in nivel:
            nivel[n] = 1 + max((etapa(d, caminho + (n,)) for d in deps[n]), default=0)
        return nivel[n]

    ordem = sorted(no_plano, key=lambda n: (etapa(n), n))
    parte_de = {n: i for i, n in enumerate(ordem, 1)}
    partes = [
        {
            "id": parte_de[n],
            "issue": n,
            "etapa": nivel[n],
            "titulo_da_issue": no_plano[n]["titulo"],
            **_bloco_diretor(no_plano[n]["corpo"]),
            "criterios": _criterios(no_plano[n]["corpo"]),
            "depende": sorted(parte_de[d] for d in deps[n]),
        }
        for n in ordem
    ]
    decididas = [
        {
            "issue": f["numero"],
            "titulo_da_issue": f["titulo"],
            "corpo": f["corpo"],
            "comentarios": f["comentarios"],
        }
        for f in fatias
        if f["numero"] in humana_fechada
    ]
    return {"partes": partes, "decididas": decididas}


def _gh_json(*args: str) -> object:
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(out.stdout or "null")


def coletar(prd: int) -> dict:
    """O PRD e as Fatias, com bloqueios e comentários de quem é do repositório."""
    base = f"repos/{REPO}/issues"
    pai = _gh_json("api", f"{base}/{prd}")
    subs = _gh_json("api", "--paginate", "--slurp", f"{base}/{prd}/sub_issues")
    fatias = []
    for s in [x for pagina in subs for x in pagina]:
        n = s["number"]
        bloq = _gh_json("api", f"{base}/{n}/dependencies/blocked_by")
        coments = _gh_json("api", "--paginate", "--slurp", f"{base}/{n}/comments")
        fatias.append(
            {
                "numero": n,
                "titulo": s["title"],
                "estado": s["state"],
                "labels": [lb["name"] for lb in s["labels"]],
                "corpo": s.get("body") or "",
                "bloqueada_por": [b["number"] for b in bloq],
                "comentarios": [
                    c["body"]
                    for pagina in coments
                    for c in pagina
                    if c.get("author_association") in {"OWNER", "MEMBER", "COLLABORATOR"}
                ],
            }
        )
    return {
        "prd": prd,
        "titulo": pai["title"],
        "corpo": pai.get("body") or "",
        "labels": [lb["name"] for lb in pai["labels"]],
        **plano(fatias),
    }


# --- O código do link e o rascunho do e-mail ---------------------------------


def _mac() -> Path:
    """A pasta do Mac do Pedro com o segredo e o vínculo da Vercel (fora do repositório)."""
    return Path(os.environ.get("PLANOS_HSM_DIR", "~/.config/planos-hsm")).expanduser()


def codigo(prd: int) -> str:
    """O mesmo código que `site/api/validar.js` confere: HMAC-SHA256 do número, 20 hex."""
    segredo = (_mac() / "segredo").read_text(encoding="utf-8").strip()
    return hmac.new(segredo.encode(), str(prd).encode(), hashlib.sha256).hexdigest()[:20]


def link(prd: int) -> str:
    return f"{SITE}/{prd}?c={codigo(prd)}"


def email(prd: int) -> Path:
    """Grava o texto do e-mail ao diretor (com o código) fora do repositório e devolve o caminho."""
    dados = dados_do_prd(prd)
    texto = (
        f"Assunto: Plano para validar: {dados['titulo_aba']}\n\n"
        "Bom dia,\n\n"
        "O plano do seu pedido está pronto para você conferir antes de o trabalho começar:\n\n"
        f"{link(prd)}\n\n"
        "A página mostra as etapas na ordem e o que cada parte entrega. No fim tem o botão "
        "Validar, com um campo para escrever se quiser mudar alguma coisa.\n\n"
        "Qualquer dúvida, me chama.\n\n"
        "Pedro\n"
    )
    destino = _mac() / f"email-{prd}.txt"
    destino.write_text(texto, encoding="utf-8")
    destino.chmod(0o600)
    return destino


# --- Publicar ----------------------------------------------------------------


def tirar_selo(prd: int) -> bool:
    """Tira a label validado:diretor do PRD: o selo vale só para a versão que o diretor viu."""
    base = f"repos/{REPO}/issues/{prd}/labels"
    out = subprocess.run(["gh", "api", base, "--jq", ".[].name"], capture_output=True, text=True, check=True)
    if SELO not in out.stdout.split():
        return False
    subprocess.run(["gh", "api", "-X", "DELETE", f"{base}/{SELO}"], capture_output=True, check=True)
    return True


def montar_site(destino: Path) -> list[int]:
    """O site inteiro numa pasta: o projeto da Vercel troca tudo a cada deploy."""
    shutil.copytree(PLANOS / "site", destino, dirs_exist_ok=True)
    for asset in (ASSETS / "logo-hsm.png", ASSETS / "fonts" / "HPSimplified_Rg.ttf"):
        shutil.copy(asset, destino / asset.name)
    prds = sorted(int(p.parent.name) for p in PLANOS.glob("*/dados.json"))
    for prd in prds:
        (destino / str(prd)).mkdir(exist_ok=True)
        (destino / str(prd) / "index.html").write_text(montar(dados_do_prd(prd)), encoding="utf-8")
    shutil.copytree(_mac() / "site" / ".vercel", destino / ".vercel")
    return prds


def publicar(prd: int) -> str:
    if not (PLANOS / str(prd) / "dados.json").exists():
        raise SystemExit(f"falta docs/comunicacao/planos/{prd}/dados.json")
    if tirar_selo(prd):
        print(f"label {SELO} tirada do PRD {prd}")
    with tempfile.TemporaryDirectory(prefix="planos-hsm-") as tmp:
        # Fora do repositório: de dentro, a Vercel recusa o autor do git (TEAM_ACCESS_REQUIRED).
        destino = Path(tmp) / "site"
        montar_site(destino)
        subprocess.run(["npx", "vercel@latest", "deploy", "--prod", "--yes"], cwd=destino, check=True)
    return f"{SITE}/{prd}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("coletar", "montar", "publicar", "email"):
        p = sub.add_parser(cmd)
        p.add_argument("prd", type=int)
        if cmd == "montar":
            p.add_argument("--saida", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "coletar":
        print(json.dumps(coletar(args.prd), ensure_ascii=False, indent=1))
    elif args.cmd == "publicar":
        print(publicar(args.prd))
    elif args.cmd == "email":
        print(email(args.prd))
    elif args.cmd == "montar":
        html = montar(dados_do_prd(args.prd))
        if args.saida:
            destino = args.saida / str(args.prd) / "index.html"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(html, encoding="utf-8")
            print(destino)
        else:
            sys.stdout.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
