#!/usr/bin/env python3
"""O Guia passo a passo de um card humano: a página que o Pedro abre, lê e copia.

Uso, da raiz do repositório:
  guia.py montar <N> [--saida DIR]   a página de docs/comunicacao/guias/<N>/dados.json
  guia.py publicar <N>               publica o site inteiro na Vercel (guias-hsm) e marca a issue
  guia.py marcar <N>                 só grava na issue o marcador com o endereço do guia

O vínculo com o projeto da Vercel fica em ~/.config/guias-hsm/site/.vercel (ou $GUIAS_HSM_DIR),
criado no primeiro publicar.
"""

from __future__ import annotations

import argparse
import datetime as dt
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
GUIAS = RAIZ / "docs" / "comunicacao" / "guias"
ASSETS = RAIZ / "docs" / "comunicacao" / "_assets"
REPO = "pedrorezendefig/hospital-reunioes"
SITE = "https://guias-hsm.vercel.app"
PROJETO = "guias-hsm"

# A lista da /divulgar e da Apresentação do PRD: o guia é para leigo.
TECNICAS = (
    "migration", "endpoint", "API", "PR", "pull request", "deploy", "RLS", "schema",
    "backend", "frontend", "commit", "branch", "merge", "token", "env", "SQL",
    "Supabase", "Coolify", "prompt",
)  # fmt: skip
MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)  # fmt: skip


def _esc(s: object) -> str:
    return _html.escape(str(s), quote=True)


def _rico(s: str) -> str:
    """Texto escapado com `[[Botão]]` virando o rótulo da tela, desenhado como no app."""
    return re.sub(r"\[\[(.+?)\]\]", r'<span class="ui">\1</span>', _esc(s))


def _textos(x: object, fora: tuple[str, ...] = ()) -> list[str]:
    """Todo texto dentro de um dado, menos o das chaves em `fora`."""
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [t for k, v in x.items() if k not in fora for t in _textos(v, fora)]
    if isinstance(x, list):
        return [t for v in x for t in _textos(v, fora)]
    return []


def problemas(dados: dict) -> list[str]:
    """O que impede o guia de sair: travessão em qualquer lugar, jargão ou número de issue na explicação.

    O que vai para a área de transferência (`copiar`) e o endereço (`url`) só passam pela régua do travessão:
    um comando ou uma mensagem pronta saem como são.
    """
    erros = []
    if any("—" in t or "–" in t for t in _textos(dados)):
        erros.append("travessão ou meia-risca")
    explicacao = "\n".join(_textos(dados, fora=("copiar", "url", "issue")))
    if re.search(r"#\d{2,}", explicacao):
        erros.append("número de issue")
    for p in TECNICAS:
        if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", explicacao, re.IGNORECASE):
            erros.append(f"palavra técnica: {p}")
    return sorted(set(erros))


def _numeros(d: dict) -> str:
    return "\n".join(
        f'      <div class="num"><div class="v">{_esc(n["valor"])}</div>'
        f'<div class="r">{_esc(n["rotulo"])}</div></div>'
        for n in d["numeros"]
    )


def _quem(d: dict) -> str:
    return "\n".join(
        f'      <div class="pessoa"><div class="n">{_esc(q["nome"])}</div>'
        f'<div class="p">{_rico(q["faz"])}</div></div>'
        for q in d["quem"]
    )


def _copia(c: dict, id_: str) -> str:
    como = f'<p class="copia-como">{_rico(c["como"])}</p>' if c.get("como") else ""
    classe = "copia cmd" if c.get("comando") else "copia"
    return (
        f'<div class="{classe}"><div class="copia-top"><span class="copia-r">{_esc(c["rotulo"])}</span>'
        f'<button class="btn peq" type="button" data-copiar="{id_}">Copiar</button></div>'
        f'<pre id="{id_}">{_esc(c["copiar"])}</pre>{como}</div>'
    )


def _passo(p: dict, n: int) -> str:
    partes = []
    if p.get("espera"):
        partes.append(
            f'<div class="espera"><span class="ic">⏳</span><span>{_rico(p["espera"])}</span></div>'
        )
    partes += [f'<p class="p-txt">{_rico(t)}</p>' for t in p["texto"]]
    partes += [_copia(c, f"c{n}-{i}") for i, c in enumerate(p.get("copias", []), 1)]
    if p.get("abrir"):
        a = p["abrir"]
        partes.append(
            f'<div class="abrir"><a class="btn" href="{_esc(a["url"])}" target="_blank" rel="noreferrer">'
            f"{_esc(a['rotulo'])}</a></div>"
        )
    if p.get("ver"):
        partes.append(
            '<div class="ver"><span class="ic">✓</span><span><span class="r">O que aparece</span>'
            f"{_rico(p['ver'])}</span></div>"
        )
    corpo = "\n          ".join(partes)
    return (
        f'        <article class="passo" id="passo-{n}">\n'
        f'          <div><div class="bola">{n}</div></div>\n'
        f'          <div>\n          <h3 class="p-tit">{_esc(p["titulo"])}</h3>\n          {corpo}\n'
        f'          <label class="marcar"><input type="checkbox" data-passo="{n}" /> Já fiz este passo</label>\n'
        "          </div>\n        </article>"
    )


def _rodape(d: dict, hoje: dt.date) -> str:
    return (
        f"{d['contexto']} · Hospital São Matheus · guia passo a passo · "
        f"{MESES[hoje.month - 1]} de {hoje.year}"
    )


def montar(dados: dict, hoje: dt.date | None = None) -> str:
    """O HTML do guia. Recusa (ValueError) texto que não pode sair."""
    hoje = hoje or dt.date.today()
    erros = problemas(dados)
    if erros:
        raise ValueError("o guia não pode sair: " + ", ".join(erros))
    html = (GUIAS / "modelo.html").read_text(encoding="utf-8")
    trocas = {
        "titulo_aba": _esc(dados["titulo_aba"]),
        "descricao": _esc(dados["descricao"]),
        "contexto": _esc(dados["contexto"]),
        "estado": _esc(dados["estado"]),
        "selo": _esc(dados["selo"]),
        "titulo": _esc(dados["titulo"]),
        "destaque": _esc(dados["destaque"]),
        "resumo": _rico(dados["resumo"]),
        "numeros": _numeros(dados),
        "quem": _quem(dados),
        "passos": "\n".join(_passo(p, n) for n, p in enumerate(dados["passos"], 1)),
        "acabou": "\n".join(
            f'        <li><span class="ck">✓</span><span>{_rico(t)}</span></li>'
            for t in dados["acabou"]
        ),
        "ajuda": _rico(dados["ajuda"]),
        "rodape": _esc(_rodape(dados, hoje)),
        "chave": str(int(dados["issue"])),
    }
    for chave, valor in trocas.items():
        html = html.replace("{{" + chave + "}}", valor)
    sobra = re.findall(r"\{\{\w+\}\}", html)
    if sobra:
        raise ValueError(f"marcador sem valor no modelo: {sobra}")
    visivel = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.DOTALL)
    if "—" in visivel or "–" in visivel:
        raise ValueError("o modelo tem travessão ou meia-risca")
    return html


def dados_da_issue(n: int) -> dict:
    return json.loads((GUIAS / str(n) / "dados.json").read_text(encoding="utf-8"))


def _mac() -> Path:
    return Path(os.environ.get("GUIAS_HSM_DIR", Path.home() / ".config" / PROJETO))


def montar_site(destino: Path) -> list[int]:
    """O site inteiro numa pasta: o projeto da Vercel troca tudo a cada deploy."""
    shutil.copytree(GUIAS / "site", destino, dirs_exist_ok=True)
    for asset in (ASSETS / "logo-hsm.png", ASSETS / "fonts" / "HPSimplified_Rg.ttf"):
        shutil.copy(asset, destino / asset.name)
    numeros = sorted(int(p.parent.name) for p in GUIAS.glob("*/dados.json"))
    for n in numeros:
        (destino / str(n)).mkdir(exist_ok=True)
        (destino / str(n) / "index.html").write_text(
            montar(dados_da_issue(n)), encoding="utf-8"
        )
    vinculo = _mac() / "site" / ".vercel"
    if vinculo.exists():
        shutil.copytree(vinculo, destino / ".vercel")
    return numeros


def endereco(n: int) -> str:
    return f"{SITE}/{n}"


def com_marcador(corpo: str, n: int) -> str:
    """O corpo com o link do guia e o marcador no fim, uma vez só, sem mudar outro byte."""
    marcador = f"<!-- guia: {endereco(n)} -->"
    if marcador in corpo:
        return corpo
    separador = "" if not corpo else "\n" if corpo.endswith("\n") else "\n\n"
    return f"{corpo}{separador}Guia passo a passo, para abrir e copiar: {endereco(n)}\n{marcador}\n"


def marcar(n: int) -> str:
    """Grava na issue o marcador `<!-- guia: <url> -->`, que o PedroOS lê. Já marcada, não grava nada."""
    issue = f"repos/{REPO}/issues/{n}"
    sai = subprocess.run(
        ["gh", "api", issue], capture_output=True, text=True, check=True
    )
    corpo = json.loads(sai.stdout).get("body") or ""
    novo = com_marcador(corpo, n)
    if novo != corpo:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"body": novo}, f, ensure_ascii=False)
        try:
            subprocess.run(
                ["gh", "api", "-X", "PATCH", issue, "--input", f.name],
                capture_output=True,
                check=True,
            )
        finally:
            os.unlink(f.name)
    return endereco(n)


def publicar(n: int) -> str:
    if not (GUIAS / str(n) / "dados.json").exists():
        raise SystemExit(f"falta docs/comunicacao/guias/{n}/dados.json")
    with tempfile.TemporaryDirectory(prefix="guias-") as tmp:
        # Fora do repositório (de dentro, a Vercel recusa o autor do git) e numa pasta com o nome do
        # projeto: sem o vínculo, o primeiro deploy cria o projeto com o nome da pasta.
        destino = Path(tmp) / PROJETO
        montar_site(destino)
        subprocess.run(
            ["npx", "vercel@latest", "deploy", "--prod", "--yes"],
            cwd=destino,
            check=True,
        )
        vinculo = _mac() / "site" / ".vercel"
        if not vinculo.exists() and (destino / ".vercel").exists():
            vinculo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(destino / ".vercel", vinculo)
    # Depois do deploy que deu certo: deploy falho sai antes, pelo check=True.
    return marcar(n)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("montar", "publicar", "marcar"):
        p = sub.add_parser(cmd)
        p.add_argument("n", type=int)
        if cmd == "montar":
            p.add_argument("--saida", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "publicar":
        print(publicar(args.n))
    elif args.cmd == "marcar":
        print(marcar(args.n))
    else:
        html = montar(dados_da_issue(args.n))
        if args.saida:
            destino = args.saida / str(args.n) / "index.html"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(html, encoding="utf-8")
            print(destino)
        else:
            sys.stdout.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
