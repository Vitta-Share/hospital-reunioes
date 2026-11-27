#!/usr/bin/env python3
"""O painel local do pareamento: a mesma página, com os botões que abrem sessões no Claude Agents.

Serve `pareamento.html` em http://127.0.0.1:4479 e atende os cliques da página:

  POST /api/sessoes  {"acoes": [{"tipo", "chave"} | {"tipo": "onda", "projeto"}]}  abre uma sessão de fundo por ação
  POST /api/passar   {"chave", "rascunho"}   passa o card ao diretor (passagem.py)
  POST /api/bloqueio {"chave", "espera"}     grava o bloqueio nativo que só estava no texto
  POST /api/agents   {"projeto"}             traz o Claude Agents da pasta do Projeto para a frente

Só 127.0.0.1 e localhost na porta certa (contra DNS rebinding), Origin igual ao Host quando
vier e o token desta subida no cabeçalho x-pareamento-token, como a guarda do PedroOS. O
navegador manda só o tipo e o card: o pedido da sessão sai do acoes.py, a partir do
estado.json e do descricoes.json lidos a cada clique.

Uso: python3 .claude/skills/pareamento/scripts/painel.py [--fundo] [--porta 4479] [--pasta DIR]
--fundo sobe o painel solto do terminal (ou reaproveita o que já roda com o mesmo código) e sai.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import acoes  # noqa: E402
import passagem  # noqa: E402

RAIZ = AQUI.parents[3]
PASTA = RAIZ / "local" / "pareamento"
PORTA = 4479
VERSAO = hashlib.sha1(b"".join((AQUI / n).read_bytes() for n in ("painel.py", "acoes.py", "passagem.py"))).hexdigest()[:10]
CAMINHO = f"PATH={Path.home() / '.local' / 'bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}"


def guarda(porta: int, token: str):
    hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}

    def host_ok(headers) -> bool:
        return headers.get("Host", "") in hosts

    def autorizado(headers) -> bool:
        if not host_ok(headers):
            return False
        origem = headers.get("Origin")
        if origem and origem.replace("http://", "", 1) not in hosts:
            return False
        t = headers.get("x-pareamento-token") or ""
        return hmac.compare_digest(t.encode(), token.encode())

    return host_ok, autorizado


def ler(pasta: Path, nome: str, padrao):
    arq = pasta / nome
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else padrao


def repo_de(estado: dict, projeto: str) -> str:
    return next(p["repo"] for p in estado["projetos"] if p["nome"] == projeto)


def sessoes_vivas() -> set[str]:
    try:
        r = subprocess.run(["/usr/bin/env", CAMINHO, "claude", "agents", "--json"], capture_output=True, text=True, timeout=30)
        return {s.get("name") for s in json.loads(r.stdout or "[]") if s.get("state") not in ("done", "stopped")}
    except (OSError, ValueError, subprocess.SubprocessError):
        return set()


def lancar(projeto: str, nome: str, prompt: str, executar=subprocess.run) -> dict:
    """Abre a sessão de fundo pelo lancar_sessao.sh do Projeto (ambiente limpo, cobra da assinatura)."""
    pasta = acoes.PASTAS.get(projeto)
    script = pasta / ".claude" / "skills" / "onda-enxuta" / "scripts" / "lancar_sessao.sh" if pasta else None
    if not script or not script.exists():
        return {"erro": f"o {projeto} não tem o lancar_sessao.sh neste Mac"}
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        arq = f.name
    try:
        r = executar(["/usr/bin/env", CAMINHO, "/bin/bash", str(script), nome, arq, "--cwd", str(pasta)],
                     capture_output=True, text=True, timeout=120, cwd=str(pasta))
    finally:
        os.unlink(arq)
    if r.returncode != 0:
        return {"erro": ((r.stderr or "").strip() or "o lançador falhou")[-300:]}
    achado = re.search(r"claude attach (\S+)", r.stdout or "")
    return {"ok": True, "id": achado.group(1) if achado else None}


def abrir_sessoes(pedidos: list[dict], pasta: Path, lancador=lancar, vivas=sessoes_vivas) -> list[dict]:
    estado = ler(pasta, "estado.json", {"cards": {}, "projetos": []})
    descricoes = ler(pasta, "descricoes.json", {})
    ja = vivas()
    saida = []
    for p in pedidos[:12]:
        tipo = p.get("tipo")
        try:
            if tipo == "onda":
                projeto = p.get("projeto")
                if projeto not in acoes.PASTAS:
                    raise ValueError("Projeto desconhecido")
                nome, prompt, chave = f"par-{projeto.lower()[:4]}-onda", acoes.pedido_da_onda(projeto), projeto
            else:
                chave = p.get("chave")
                card = estado["cards"].get(chave)
                if not card:
                    raise ValueError("card fora do pareamento")
                nome = acoes.nome_da_sessao(tipo, chave)
                prompt = acoes.pedido(tipo, card, repo_de(estado, card["projeto"]), descricoes.get(chave))
                projeto = card["projeto"]
        except (ValueError, KeyError, StopIteration) as e:
            saida.append({"chave": p.get("chave") or p.get("projeto"), "tipo": tipo, "erro": str(e)})
            continue
        if nome in ja:
            saida.append({"chave": chave, "tipo": tipo, "nome": nome, "viva": True})
            continue
        r = lancador(projeto, nome, prompt)
        saida.append({"chave": chave, "tipo": tipo, "nome": nome, **r})
        if r.get("ok"):
            ja.add(nome)
    return saida


def marcar(pasta: Path, nome: str, chave: str, valor) -> dict:
    arq = pasta / nome
    dados = ler(pasta, nome, {})
    dados[chave] = valor
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return dados


def gravar_bloqueio(chave: str, espera: str, pasta: Path, gh=passagem._gh) -> dict:
    estado = ler(pasta, "estado.json", {"cards": {}, "projetos": []})
    card = estado["cards"].get(chave)
    if not card or espera not in (card.get("no_texto") or []):
        raise ValueError("esse bloqueio não está no texto do card")
    repo = repo_de(estado, card["projeto"])
    alvo = json.loads(gh("api", f"repos/{repo}/issues/{espera.split('#')[1]}"))
    gh("api", "-X", "POST", f"repos/{repo}/issues/{card['numero']}/dependencies/blocked_by", "-F", f"issue_id={alvo['id']}")
    marcar(pasta, "feitos.json", f"bloqueio:{chave}:{espera}", agora())
    return {"ok": True}


def focar_agents(projeto: str) -> dict:
    pasta = acoes.PASTAS.get(projeto)
    if not pasta or not pasta.exists():
        return {"erro": "Projeto sem pasta neste Mac"}
    linha = f"cd {shlex.quote(str(pasta))} && claude agents"
    script = f'tell application "Terminal"\nactivate\ndo script {json.dumps(linha)}\nend tell'
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=20)
    return {"ok": True}


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pagina(pasta: Path, token: str) -> bytes:
    html = (pasta / "pareamento.html").read_text(encoding="utf-8")
    painel = {"token": token, "feitos": ler(pasta, "feitos.json", {})}
    return html.replace("/*PAINEL*/null", json.dumps(painel, ensure_ascii=False).replace("</", "<\\/"), 1).encode()


def servidor(porta: int, pasta: Path, token: str) -> ThreadingHTTPServer:
    host_ok, autorizado = guarda(porta, token)

    class Atende(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def responder(self, codigo: int, corpo: bytes, tipo="application/json; charset=utf-8"):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def json(self, codigo: int, dados):
            self.responder(codigo, json.dumps(dados, ensure_ascii=False).encode())

        def do_GET(self):
            if not host_ok(self.headers):
                return self.json(403, {"erro": "host recusado"})
            if self.path == "/api/saude":
                return self.json(200, {"ok": True, "versao": VERSAO, "pid": os.getpid()})
            if self.path.split("?")[0] in ("/", "/index.html"):
                try:
                    return self.responder(200, pagina(pasta, token), "text/html; charset=utf-8")
                except OSError:
                    return self.json(404, {"erro": "rode o montar.py antes"})
            self.json(404, {"erro": "não achei"})

        def do_POST(self):
            if not autorizado(self.headers):
                return self.json(403, {"erro": "pedido recusado: recarregue a página do painel"})
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
                corpo = json.loads(self.rfile.read(min(tamanho, 200_000)) or b"{}")
                rota = self.path
                if rota == "/api/sessoes":
                    return self.json(200, {"resultados": abrir_sessoes(corpo.get("acoes") or [], pasta)})
                if rota == "/api/passar":
                    estado = ler(pasta, "estado.json", {"cards": {}, "projetos": []})
                    card = estado["cards"].get(corpo.get("chave"))
                    if not card or card["dono"] != "eu":
                        raise ValueError("só card seu passa ao diretor")
                    r = passagem.passar(repo_de(estado, card["projeto"]), card["numero"], corpo.get("rascunho") or {})
                    marcar(pasta, "feitos.json", f"passado:{card['chave']}", agora())
                    return self.json(200, r)
                if rota == "/api/bloqueio":
                    return self.json(200, gravar_bloqueio(corpo.get("chave"), corpo.get("espera"), pasta))
                if rota == "/api/agents":
                    return self.json(200, focar_agents(corpo.get("projeto")))
                self.json(404, {"erro": "não achei"})
            except (ValueError, RuntimeError, KeyError, StopIteration) as e:
                self.json(400, {"erro": str(e)})

    return ThreadingHTTPServer(("127.0.0.1", porta), Atende)


def no_ar(porta: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/saude", timeout=2) as r:
            return json.load(r)
    except (OSError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=PORTA)
    ap.add_argument("--pasta", type=Path, default=PASTA)
    ap.add_argument("--fundo", action="store_true")
    a = ap.parse_args()
    url = f"http://127.0.0.1:{a.porta}/"
    if a.fundo:
        vivo = no_ar(a.porta)
        if vivo and vivo.get("versao") == VERSAO:
            print(f"painel: {url} (já no ar)")
            return 0
        if vivo:
            os.kill(int(vivo["pid"]), 15)
        subprocess.Popen([sys.executable, __file__, "--porta", str(a.porta), "--pasta", str(a.pasta)],
                         start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        for _ in range(30):
            if no_ar(a.porta):
                print(f"painel: {url}")
                return 0
            subprocess.run(["sleep", "0.2"])
        print("o painel não subiu", file=sys.stderr)
        return 1
    servidor(a.porta, a.pasta, secrets.token_hex(24)).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
