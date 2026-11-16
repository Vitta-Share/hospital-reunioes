#!/usr/bin/env python3
"""A Apresentação do PRD (issue #1891): monta e publica a página do plano para o diretor validar.

Uso, da raiz do repositório:
  apresentar.py montar <PRD> [--saida DIR]   página de docs/comunicacao/planos/<PRD>/dados.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as _html
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
PLANOS = RAIZ / "docs" / "comunicacao" / "planos"
PACOTE = RAIZ / "hospital-reunioes" / "frontend" / "package.json"

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("montar")
    m.add_argument("prd", type=int)
    m.add_argument("--saida", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "montar":
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
