"""A pergunta ao diretor pela Conversa da Demanda (issue #1808, ADR 0096, decisões 5 a 7).

O `pegar-issue/scripts/conversa.py` tem dois comandos:

- `enviar <issue> <arquivo>`: sobe da fatia até a raiz pelo pai nativo do
  GitHub, pede ao app a Demanda da raiz, pega o login com o `gh` e escreve o
  texto aprovado na Conversa da Demanda pela ponte. Sem Demanda, sai com o
  código próprio e imprime a mensagem para o WhatsApp.
- `ler <issue>`: mostra no terminal as mensagens que chegaram depois da última
  que o terminal escreveu. Não grava a resposta em lugar nenhum.

Estes testes rodam o script como o agente roda, num repositório git de mentira,
com um `gh` falso no PATH e um app falso num servidor HTTP local. A fala do
diretor só existe na memória do app falso: nenhum teste a grava em disco.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / ".claude" / "skills" / "pegar-issue" / "scripts" / "conversa.py"

CHAVE = "chave-falsa-do-teste-1808"
DEMANDA = "5b1c2d3e-4f50-4a61-8b72-9c83d4e5f601"
LOGIN = "dev-do-teste"
# A fatia 1808, filha da 1805, filha da raiz 1803, a issue da Demanda.
PAIS = {"1808": "1805", "1805": "1803"}
RAIZ_DA_DEMANDA = "1803"
TEXTO = "E aí, travou numa decisão sua. Opção A ou B? Recomendo a A."
CRIADO_EM_DA_PERGUNTA = "2026-11-16T15:00:00.123456+00:00"
RESPOSTA = "Vai de B, por causa do faturamento."

GH_FALSO = """#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
pais = json.loads(os.environ["GH_PAIS"])
if args[:2] == ["api", "user"]:
    print(json.dumps({{"login": os.environ["GH_LOGIN"]}}))
    sys.exit(0)
if args and args[0] == "api" and args[1].endswith("/parent"):
    numero = args[1].split("/")[-2]
    if numero in pais:
        print(json.dumps({{"number": int(pais[numero])}}))
        sys.exit(0)
    sys.stderr.write("gh: No parent issue found (HTTP 404)\\n")
    sys.exit(1)
sys.stderr.write("gh falso: comando inesperado " + " ".join(args) + "\\n")
sys.exit(9)
"""


@pytest.fixture
def app_falso():
    """O app de mentira: as três rotas da ponte que o script usa.

    `estado["mensagens"]` é a conversa (autor, criado_em, texto) e
    `estado["demandas"]` diz qual issue-raiz tem Demanda. `pedidos` guarda cada
    chamada, com a chave e o corpo."""
    pedidos: list[dict] = []
    estado: dict = {"demandas": {RAIZ_DA_DEMANDA: DEMANDA}, "mensagens": [], "status_escrita": 201}
    base_da_conversa = f"/api/automacao/tecnologia/demandas/{DEMANDA}/conversa"

    class _Rota(BaseHTTPRequestHandler):
        def _responder(self, codigo: int, corpo: dict) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(corpo).encode())

        def do_GET(self):  # noqa: N802
            partes = urlsplit(self.path)
            pedidos.append({"metodo": "GET", "caminho": partes.path, "query": partes.query, "chave": self.headers.get("X-API-Key")})
            prefixo = "/api/automacao/tecnologia/projetos/hospital/issues/"
            if partes.path.startswith(prefixo) and partes.path.endswith("/demanda"):
                numero = partes.path[len(prefixo) : -len("/demanda")]
                if numero in estado["demandas"]:
                    return self._responder(200, {"id": estado["demandas"][numero]})
                return self._responder(404, {"detail": "Demanda não encontrada."})
            if partes.path == base_da_conversa:
                depois = parse_qs(partes.query).get("depois", [None])[0]
                mensagens = [
                    m
                    for m in estado["mensagens"]
                    if depois is None or datetime.fromisoformat(m["criado_em"]) > datetime.fromisoformat(depois)
                ]
                return self._responder(200, {"mensagens": mensagens})
            self._responder(404, {"detail": "rota desconhecida"})

        def do_POST(self):  # noqa: N802
            corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            pedidos.append({"metodo": "POST", "caminho": self.path, "corpo": corpo, "chave": self.headers.get("X-API-Key")})
            if self.path == base_da_conversa and estado["status_escrita"] == 201:
                estado["mensagens"].append({"autor": "Dev do Teste", "criado_em": CRIADO_EM_DA_PERGUNTA, "texto": corpo["texto"]})
                return self._responder(201, {"id": "a1", "criado_em": CRIADO_EM_DA_PERGUNTA})
            self._responder(estado["status_escrita"], {"detail": "recusado"})

        def log_message(self, *_a):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), _Rota)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_port}/api", pedidos, estado
    servidor.shutdown()


@pytest.fixture
def repo(tmp_path):
    """Um clone de mentira, com o `/local/` fora do git como no de verdade."""
    raiz = tmp_path.resolve() / "clone"
    raiz.mkdir()
    subprocess.run(["git", "init", "-q", str(raiz)], check=True)
    (raiz / ".gitignore").write_text("/local/\n/tokens/\n", encoding="utf-8")
    (raiz / "tokens").mkdir()
    (raiz / "tokens" / ".env").write_text(f"TECNOLOGIA_AUTOMACAO_API_KEY='{CHAVE}'\n", encoding="utf-8")
    return raiz


def rodar(repo: Path, base: str, *args: str, pais: dict | None = None) -> subprocess.CompletedProcess:
    falso = repo.parent / "bin"
    falso.mkdir(exist_ok=True)
    gh = falso / "gh"
    gh.write_text(GH_FALSO.format(python=sys.executable), encoding="utf-8")
    gh.chmod(0o755)
    ambiente = {k: v for k, v in os.environ.items() if k != "TECNOLOGIA_AUTOMACAO_API_KEY"}
    ambiente.update(
        PATH=f"{falso}:{os.environ['PATH']}",
        GH_LOG=str(repo.parent / "gh.log"),
        GH_PAIS=json.dumps(PAIS if pais is None else pais),
        GH_LOGIN=LOGIN,
        HOSPITAL_API_URL=base,
    )
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=ambiente, cwd=repo)


def chamadas_do_gh(repo: Path) -> list[list[str]]:
    log = repo.parent / "gh.log"
    return [json.loads(linha) for linha in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def texto_aprovado(repo: Path) -> Path:
    arquivo = repo.parent / "mensagem.txt"
    arquivo.write_text(TEXTO + "\n", encoding="utf-8")
    return arquivo


# ------------------------------------------------- enviar


def test_enviar_sobe_da_fatia_ate_a_raiz_e_escreve_na_conversa_da_demanda(repo, app_falso):
    base, pedidos, _ = app_falso

    feito = rodar(repo, base, "enviar", "1808", str(texto_aprovado(repo)))

    assert feito.returncode == 0, feito.stderr
    # Subiu pelo pai nativo até a 1803, que não tem pai.
    pais = [c[1] for c in chamadas_do_gh(repo) if c[1].endswith("/parent")]
    assert pais == [
        "repos/{owner}/{repo}/issues/1808/parent",
        "repos/{owner}/{repo}/issues/1805/parent",
        "repos/{owner}/{repo}/issues/1803/parent",
    ]
    # Pediu a Demanda da raiz e escreveu nela, no perfil do login do gh, com a chave.
    assert [(p["metodo"], p["caminho"]) for p in pedidos] == [
        ("GET", "/api/automacao/tecnologia/projetos/hospital/issues/1803/demanda"),
        ("POST", f"/api/automacao/tecnologia/demandas/{DEMANDA}/conversa"),
    ]
    assert pedidos[1]["corpo"] == {"texto": TEXTO, "github_login": LOGIN}
    assert {p["chave"] for p in pedidos} == {CHAVE}


def test_raiz_sem_demanda_sai_com_o_codigo_proprio_e_imprime_a_mensagem_para_o_whatsapp(repo, app_falso):
    base, pedidos, estado = app_falso
    estado["demandas"] = {}

    feito = rodar(repo, base, "enviar", "1808", str(texto_aprovado(repo)))

    assert feito.returncode == 3, feito.stderr
    assert feito.stdout.strip() == TEXTO
    assert "WhatsApp" in feito.stderr
    # Perguntou pela Demanda e parou: nada foi escrito, nem o login foi pedido.
    assert [p["metodo"] for p in pedidos] == ["GET"]
    assert ["api", "user"] not in chamadas_do_gh(repo)
    assert not (repo / "local").exists()


# ------------------------------------------------- ler


def _arquivos_com(raiz: Path, trecho: str) -> list[Path]:
    achados = []
    for caminho in raiz.rglob("*"):
        if caminho.is_file() and ".git" not in caminho.parts and trecho.encode() in caminho.read_bytes():
            achados.append(caminho)
    return achados


def _estado_do_git(repo: Path) -> tuple[str, str]:
    """O que o git vê: arquivos versionáveis mexidos e commits, em todas as refs."""
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    log = subprocess.run(["git", "log", "--all", "--oneline"], cwd=repo, capture_output=True, text=True).stdout
    return status, log


def test_ler_mostra_so_o_que_chegou_depois_da_ultima_mensagem_do_terminal(repo, app_falso):
    base, pedidos, estado = app_falso
    estado["mensagens"] = [
        {"autor": "Diretor", "criado_em": "2026-11-10T09:00:00+00:00", "texto": "Conversa antiga, antes da pergunta."}
    ]
    assert rodar(repo, base, "enviar", "1808", str(texto_aprovado(repo))).returncode == 0
    estado["mensagens"].append({"autor": "Diretor", "criado_em": "2026-11-16T15:30:00+00:00", "texto": RESPOSTA})
    pedidos.clear()

    feito = rodar(repo, base, "ler", "1808")

    assert feito.returncode == 0, feito.stderr
    assert RESPOSTA in feito.stdout and "Diretor" in feito.stdout
    assert "Conversa antiga" not in feito.stdout
    assert TEXTO not in feito.stdout
    # Leu a conversa depois do instante da pergunta do terminal.
    leitura = [p for p in pedidos if p["caminho"].endswith("/conversa")]
    assert len(leitura) == 1 and leitura[0]["metodo"] == "GET"
    assert parse_qs(leitura[0]["query"])["depois"] == [CRIADO_EM_DA_PERGUNTA]


def test_ler_nao_grava_a_resposta_em_arquivo_issue_pr_nem_commit(repo, app_falso, tmp_path):
    base, pedidos, estado = app_falso
    assert rodar(repo, base, "enviar", "1808", str(texto_aprovado(repo))).returncode == 0
    estado["mensagens"].append({"autor": "Diretor", "criado_em": "2026-11-16T15:30:00+00:00", "texto": RESPOSTA})
    antes = len(chamadas_do_gh(repo))
    git_antes = _estado_do_git(repo)

    feito = rodar(repo, base, "ler", "1808")

    assert RESPOSTA in feito.stdout
    # Nenhum arquivo, dentro ou fora do clone, guarda a fala do diretor.
    assert _arquivos_com(tmp_path, RESPOSTA) == []
    # O gh só subiu pelos pais: nada de comentário, edição de issue, PR ou commit.
    assert all(c[0] == "api" and c[1].endswith("/parent") and len(c) == 2 for c in chamadas_do_gh(repo)[antes:])
    assert _estado_do_git(repo) == git_antes
    # E a ponte só foi lida: a escrita foi a do enviar, antes.
    assert [p["metodo"] for p in pedidos].count("POST") == 1


def test_ler_sem_pergunta_do_terminal_nesta_maquina_avisa_e_nao_mostra_a_conversa(repo, app_falso):
    base, pedidos, estado = app_falso
    estado["mensagens"] = [{"autor": "Diretor", "criado_em": "2026-11-10T09:00:00+00:00", "texto": RESPOSTA}]

    feito = rodar(repo, base, "ler", "1808")

    assert feito.returncode == 1
    assert "enviar" in feito.stderr
    assert RESPOSTA not in feito.stdout
    assert not any(p["caminho"].endswith("/conversa") for p in pedidos)
