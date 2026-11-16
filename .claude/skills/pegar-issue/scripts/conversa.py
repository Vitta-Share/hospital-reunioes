#!/usr/bin/env python3
"""A pergunta ao diretor pela Conversa da Demanda (issue #1808, ADR 0096, decisões 5 a 7).

Quando a sessão do terminal para numa decisão que é do diretor (a baixa de uma
onda num PRD que ele planejou, as perguntas do Refino), o texto aprovado por
quem roda a sessão vai para a Conversa da Demanda no app, no perfil dessa
pessoa, e a resposta volta só para o terminal.

Uso:
  python3 .claude/skills/pegar-issue/scripts/conversa.py enviar <issue> <arquivo>
  python3 .claude/skills/pegar-issue/scripts/conversa.py ler <issue>

`enviar` sobe da issue até a raiz pelo pai nativo do GitHub, pede ao app a
Demanda vinculada à raiz, pega o login de quem roda com o `gh` e escreve o
texto do arquivo na conversa pela ponte de automação. Guarda o instante da
mensagem em `local/conversa/<demanda>.json` na raiz do clone principal (fora
do git): é a "última mensagem do terminal" que o `ler` usa.

`ler` acha a mesma Demanda e mostra no terminal as mensagens que chegaram
depois desse instante, na ordem em que chegaram (a rota já devolve assim). A
resposta do diretor não é gravada em arquivo, issue, PR nem commit (a conversa
vive só no app, ADR 0083, decisão 8).

Saídas:
  0  enviada, ou mensagens mostradas (ou "sem resposta ainda");
  1  não deu para falar com o app (chave ausente, ponte desligada, login que
     não é Desenvolvedor, app fora do ar), motivo no stderr;
  2  uso errado;
  3  a raiz não tem Demanda no app: o `enviar` imprime a mensagem para o
     WhatsApp, sem escrever em lugar nenhum (ADR 0096, decisão 5).

Mesmo endereço e mesma chave do `anexos.py` (`HOSPITAL_API_URL` e
`TECNOLOGIA_AUTOMACAO_API_KEY`). A chave nunca é impressa.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anexos  # noqa: E402

PROJETO = "hospital"
SEM_DEMANDA = 3
# Teto da subida até a raiz: uma árvore de issues com ciclo não prende o script.
MAX_NIVEIS = 10


class Falha(Exception):
    """O motivo, numa frase, de não ter falado com o app."""


def gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")


def raiz_da_issue(numero: str) -> str:
    """Sobe pelo pai nativo do GitHub até a issue que não tem pai."""
    atual = numero
    for _ in range(MAX_NIVEIS):
        feito = gh("api", f"repos/{{owner}}/{{repo}}/issues/{atual}/parent")
        if feito.returncode != 0:
            if "HTTP 404" in feito.stderr:
                return atual
            raise Falha(f"o gh não leu o pai da issue #{atual}")
        atual = str(json.loads(feito.stdout)["number"])
    raise Falha(f"a issue #{numero} tem mais de {MAX_NIVEIS} níveis de pai")


def login_do_gh() -> str:
    feito = gh("api", "user")
    if feito.returncode != 0:
        raise Falha("o gh não disse quem está logado (rode gh auth status)")
    return json.loads(feito.stdout)["login"]


def pedir(base: str, caminho: str, chave_api: str, corpo: dict | None = None) -> dict | None:
    """Chama a ponte; devolve o JSON, ou None no 404."""
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cabecalhos = {"X-API-Key": chave_api}
    if dados is not None:
        cabecalhos["Content-Type"] = "application/json"
    pedido = urllib.request.Request(f"{base}{caminho}", data=dados, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=anexos.TIMEOUT_S) as resposta:
            return json.load(resposta)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code == 503:
            raise Falha(f"a ponte está desligada no servidor: falta criar {anexos.CHAVE} na tela do Coolify") from exc
        if exc.code == 401:
            raise Falha(f"o app recusou a chave: confira {anexos.CHAVE} no tokens/.env (o mesmo valor do Coolify)") from exc
        if exc.code == 403:
            raise Falha("o login do gh não é de um Desenvolvedor ativo no app (confira o login no cadastro)") from exc
        raise Falha(f"o app respondeu {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise Falha(f"o app não respondeu ({type(exc).__name__})") from exc


def demanda_da_raiz(base: str, raiz: str, chave_api: str) -> str | None:
    achada = pedir(base, f"/automacao/tecnologia/projetos/{PROJETO}/issues/{raiz}/demanda", chave_api)
    if not achada:
        return None
    if not anexos.ID_VALIDO.match(achada["id"]):
        raise Falha("o id da Demanda que o app devolveu não é válido")
    return achada["id"]


def caminho_da_conversa(demanda: str) -> str:
    return f"/automacao/tecnologia/demandas/{urllib.parse.quote(demanda, safe='')}/conversa"


def arquivo_do_instante(demanda: str) -> Path:
    """Na raiz do clone principal: o worktree some, a espera da resposta não."""
    principal = Path(anexos.git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    return principal / "local" / "conversa" / f"{demanda}.json"


def enviar(numero: str, arquivo: str, env) -> int:
    texto = Path(arquivo).read_text(encoding="utf-8").strip()
    if not texto:
        print("O arquivo da mensagem está vazio.", file=sys.stderr)
        return 2
    chave_api = anexos.chave(env)
    if not chave_api:
        print(f"Mensagem não enviada: falta {anexos.CHAVE} no tokens/.env (peça ao Pedro).", file=sys.stderr)
        return 1
    base = anexos.base_da_api(env)
    raiz = raiz_da_issue(numero)
    demanda = demanda_da_raiz(base, raiz, chave_api)
    if demanda is None:
        print(f"A issue #{raiz} não tem Demanda no app: mande pelo WhatsApp.", file=sys.stderr)
        print(texto)
        return SEM_DEMANDA
    gravada = pedir(base, caminho_da_conversa(demanda), chave_api, {"texto": texto, "github_login": login_do_gh()})
    if not gravada:
        raise Falha("a Demanda sumiu do app entre a busca e a escrita")
    destino = arquivo_do_instante(demanda)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"issue": numero, "criado_em": gravada["criado_em"]}) + "\n", encoding="utf-8")
    print(f"Enviada na Conversa da Demanda da issue #{raiz} em {gravada['criado_em']}.")
    return 0


def main(argv: list[str], env=os.environ) -> int:
    try:
        if len(argv) == 3 and argv[0] == "enviar" and argv[1].isdigit():
            return enviar(argv[1], argv[2], env)
    except Falha as falha:
        print(f"Conversa da Demanda: {falha}.", file=sys.stderr)
        return 1
    print("uso: conversa.py enviar <issue> <arquivo> | ler <issue>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
