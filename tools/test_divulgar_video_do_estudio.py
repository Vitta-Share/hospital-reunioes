"""O vídeo da Demonstração sai do Estúdio de Vídeos (issue #1761).

`divulgar/scripts/video_do_estudio.py` liga o Estúdio pelo PedroOS, chama o
`pedir_video.py` do PedroOS e decide pelo código de saída dele: 0 é página com
vídeo; 1, 2 e 3 (e o comando que não existe neste Mac) são página sem vídeo,
com uma linha de aviso. Estes testes rodam o script como a sessão roda, com um
`pedir_video.py` de mentira que sai com o código pedido e guarda o que recebeu.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / ".claude" / "skills" / "divulgar" / "scripts" / "video_do_estudio.py"

COMANDO_FALSO = """\
import json, sys
from pathlib import Path
args = sys.argv[1:]
Path(__file__).with_name("argv.json").write_text(json.dumps(args))
codigo = int(Path(__file__).with_name("codigo.txt").read_text())
if codigo == 0:
    saida = Path(args[args.index("--saida") + 1])
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_bytes(b"mp4")
    print(saida)
elif codigo == 1:
    print("O Estúdio recusou (400): Estilo não instalado", file=sys.stderr)
elif codigo == 2:
    print("O Estúdio está desligado. Abra a Ala Vídeos para ligar.", file=sys.stderr)
elif codigo == 3:
    print("O vídeo ainda está sendo feito no Estúdio (trabalho job-42). Ele segue lá; nada foi cancelado.", file=sys.stderr)
sys.exit(codigo)
"""


@pytest.fixture
def entrega(tmp_path):
    pasta = tmp_path / "docs" / "comunicacao" / "reunioes" / "1761-video-volta"
    (pasta / "video").mkdir(parents=True)
    (pasta / "video" / "roteiro.md").write_text("A Dor.\n", encoding="utf-8")
    gravacao = tmp_path / "gravacao.webm"
    gravacao.write_bytes(b"webm")
    return pasta, gravacao


def _comando(tmp_path, codigo: int) -> Path:
    pasta = tmp_path / "os" / "scripts" / "estudio"
    pasta.mkdir(parents=True)
    (pasta / "codigo.txt").write_text(str(codigo))
    cmd = pasta / "pedir_video.py"
    cmd.write_text(COMANDO_FALSO, encoding="utf-8")
    return cmd


def _rodar(tmp_path, pasta, gravacao, comando, sessao=None):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--pasta",
            str(pasta),
            "--gravacao",
            str(gravacao),
            "--comando",
            str(comando),
            "--videos",
            str(tmp_path / "Videos" / "Hospital"),
            "--sessao",
            str(sessao or tmp_path / "sem-sessao.json"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _aviso(r) -> list[str]:
    return [linha for linha in r.stdout.splitlines() if linha.startswith("Só a página:")]


def test_sem_o_comando_neste_mac_a_demonstracao_sai_so_com_a_pagina(tmp_path, entrega):
    pasta, gravacao = entrega
    r = _rodar(tmp_path, pasta, gravacao, tmp_path / "nao-existe" / "pedir_video.py")
    assert r.returncode != 0
    aviso = _aviso(r)
    assert len(aviso) == 1
    assert "comando do Estúdio" in aviso[0]
    assert not (pasta / "video" / "meta.json").exists()


def test_estudio_desligado_codigo_2_sai_so_com_a_pagina(tmp_path, entrega):
    pasta, gravacao = entrega
    r = _rodar(tmp_path, pasta, gravacao, _comando(tmp_path, 2))
    assert r.returncode == 2
    aviso = _aviso(r)
    assert len(aviso) == 1
    assert "desligado" in aviso[0]
    assert not (pasta / "video" / "meta.json").exists()


def test_erro_do_estudio_codigo_1_sai_so_com_a_pagina_e_diz_o_motivo(tmp_path, entrega):
    pasta, gravacao = entrega
    r = _rodar(tmp_path, pasta, gravacao, _comando(tmp_path, 1))
    assert r.returncode == 1
    aviso = _aviso(r)
    assert len(aviso) == 1
    assert "Estilo não instalado" in aviso[0]


def test_tempo_esgotado_codigo_3_diz_o_id_do_trabalho_e_guarda_no_meta(tmp_path, entrega):
    pasta, gravacao = entrega
    r = _rodar(tmp_path, pasta, gravacao, _comando(tmp_path, 3))
    assert r.returncode == 3
    aviso = _aviso(r)
    assert len(aviso) == 1
    assert "job-42" in aviso[0]
    meta = json.loads((pasta / "video" / "meta.json").read_text(encoding="utf-8"))
    assert meta["estilo"] == "profitize-estreia"
    assert meta["trabalho"] == "job-42"
    assert meta["mp4"] is None


def test_video_pronto_chama_o_comando_no_estilo_nova_feature_e_grava_o_meta(tmp_path, entrega):
    pasta, gravacao = entrega
    cmd = _comando(tmp_path, 0)
    r = _rodar(tmp_path, pasta, gravacao, cmd)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _aviso(r) == []
    nome = f"{date.today().isoformat()}-1761-video-volta.mp4"
    esperado = tmp_path / "Videos" / "Hospital" / nome
    assert r.stdout.strip().splitlines()[-1] == str(esperado)
    assert esperado.read_bytes() == b"mp4"

    argv = json.loads((cmd.parent / "argv.json").read_text())
    pares = dict(zip(argv[::2], argv[1::2]))
    assert pares == {
        "--estilo": "profitize-estreia",
        "--texto": str(pasta / "video" / "roteiro.md"),
        "--gravacao": str(gravacao),
        "--saida": str(esperado),
        "--formato": "longo",
        "--obs": "Sem narração: música e legenda.",
    }
    meta = json.loads((pasta / "video" / "meta.json").read_text(encoding="utf-8"))
    assert meta["estilo"] == "profitize-estreia"
    assert meta["mp4"] == nome


def test_refazer_o_video_gera_v2_sem_sobrescrever(tmp_path, entrega):
    pasta, gravacao = entrega
    videos = tmp_path / "Videos" / "Hospital"
    videos.mkdir(parents=True)
    antigo = videos / f"{date.today().isoformat()}-1761-video-volta.mp4"
    antigo.write_bytes(b"antigo")
    r = _rodar(tmp_path, pasta, gravacao, _comando(tmp_path, 0))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].endswith("-1761-video-volta-v2.mp4")
    assert antigo.read_bytes() == b"antigo"


class _PedroOS(BaseHTTPRequestHandler):
    """O PedroOS de mentira: liga o Estúdio no pedido e diz `ligado` na segunda olhada."""

    estados: list[str] = []
    pedidos: list[tuple[str, str, str | None]] = []

    def log_message(self, *a):
        pass

    def _responder(self, corpo):
        dados = json.dumps(corpo).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self):
        self.pedidos.append(("POST", self.path, self.headers.get("x-pedroos-token")))
        self._responder({"estado": "ligando"})

    def do_GET(self):
        self.pedidos.append(("GET", self.path, self.headers.get("x-pedroos-token")))
        self._responder({"estado": self.estados.pop(0) if self.estados else "ligado"})


def test_liga_o_estudio_pelo_pedroos_com_o_token_e_espera_ligado(tmp_path, entrega):
    pasta, gravacao = entrega
    _PedroOS.estados = ["ligando", "ligado"]
    _PedroOS.pedidos = []
    servidor = HTTPServer(("127.0.0.1", 0), _PedroOS)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        sessao = tmp_path / "sessao.json"
        sessao.write_text(json.dumps({"porta": servidor.server_port, "token": "segredo"}))
        r = _rodar(tmp_path, pasta, gravacao, _comando(tmp_path, 0), sessao=sessao)
    finally:
        servidor.shutdown()
    assert r.returncode == 0, r.stdout + r.stderr
    assert _PedroOS.pedidos[0] == ("POST", "/api/estudio/ligar", "segredo")
    assert [p[:2] for p in _PedroOS.pedidos[1:]] == [("GET", "/api/estudio"), ("GET", "/api/estudio")]
    assert all(p[2] == "segredo" for p in _PedroOS.pedidos)
