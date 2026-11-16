#!/usr/bin/env python3
"""Pede o vídeo da Demonstração ao Estúdio de Vídeos e diz se a página leva vídeo (issue #1761).

Uso:
  python3 .claude/skills/divulgar/scripts/video_do_estudio.py --pasta docs/comunicacao/<contexto>/<N>-<slug> --gravacao <gravação>

Liga o Estúdio pelo PedroOS (porta e token de ~/.pedroos/sessao.json), chama o `pedir_video.py` do PedroOS no
Estilo Nova Feature com o `video/roteiro.md` da pasta e grava o MP4 em ~/Videos/Hospital/AAAA-MM-DD-<N>-<slug>.mp4
(-v2, -v3 quando já existe: nunca sobrescreve).

Saída 0: o caminho do MP4 na última linha; a página embute o vídeo.
Outra saída: uma linha "Só a página: <motivo>"; a página sai sem vídeo. O código é o do comando (1 erro, 2 Estúdio
desligado, 3 tempo esgotado, com o id do trabalho que segue no Estúdio); sem o comando neste Mac, 2.
Com vídeo pronto ou trabalho em andamento, grava video/meta.json com o Estilo, o id do trabalho e o MP4.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

ESTILO = "profitize-estreia"  # o Nova Feature, item `estreia` da Biblioteca (os#783)
OBS = "Sem narração: música e legenda."
ESPERA_LIGAR = 120  # segundos até o Estúdio dizer `ligado`
HOME = Path.home()


def ligar_estudio(sessao: Path) -> None:
    """Pede ao PedroOS que ligue o Estúdio e espera o `ligado`. Sem PedroOS, segue: o comando dá o código 2."""
    try:
        s = json.loads(sessao.read_text(encoding="utf-8"))
        base, cabecalho = f"http://127.0.0.1:{s['porta']}", {"x-pedroos-token": s["token"]}

        def estado(caminho, metodo):
            pedido = urllib.request.Request(base + caminho, data=b"" if metodo == "POST" else None, headers=cabecalho, method=metodo)
            with urllib.request.urlopen(pedido, timeout=10) as r:
                return json.loads(r.read()).get("estado")

        atual, inicio = estado("/api/estudio/ligar", "POST"), time.monotonic()
        while time.monotonic() - inicio < ESPERA_LIGAR:
            atual = estado("/api/estudio", "GET")
            if atual in ("ligado", "falhou", "nao-instalado"):
                return
            time.sleep(1)
    except (OSError, ValueError, KeyError):
        return


def saida_livre(videos: Path, nome: str) -> Path:
    alvo, n = videos / f"{nome}.mp4", 2
    while alvo.exists():
        alvo, n = videos / f"{nome}-v{n}.mp4", n + 1
    return alvo


def gravar_meta(pasta: Path, trabalho: str | None, mp4: str | None) -> None:
    meta = {"estilo": ESTILO, "trabalho": trabalho, "mp4": mp4, "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds")}
    (pasta / "video" / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv) -> int:
    p = argparse.ArgumentParser(description="Pede o vídeo da Demonstração ao Estúdio.")
    p.add_argument("--pasta", required=True, type=Path)
    p.add_argument("--gravacao", required=True, type=Path)
    p.add_argument("--comando", type=Path, default=HOME / "PedroDev/OS/scripts/estudio/pedir_video.py")
    p.add_argument("--videos", type=Path, default=HOME / "Videos/Hospital")
    p.add_argument("--sessao", type=Path, default=HOME / ".pedroos/sessao.json")
    a = p.parse_args(argv)

    if not a.comando.is_file():
        print(f"Só a página: o comando do Estúdio não está neste Mac ({a.comando}).")
        return 2
    ligar_estudio(a.sessao)
    saida = saida_livre(a.videos, f"{date.today().isoformat()}-{a.pasta.name}")
    r = subprocess.Popen(
        [sys.executable, str(a.comando), "--estilo", ESTILO, "--texto", str(a.pasta / "video" / "roteiro.md"),
         "--gravacao", str(a.gravacao), "--saida", str(saida), "--formato", "longo", "--obs", OBS],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    motivo = ""
    for linha in r.stderr:  # o andamento do Estúdio passa direto; a última linha é o motivo, quando falha
        print(linha, end="", file=sys.stderr, flush=True)
        motivo = linha.strip() or motivo
    r.wait()
    motivo = motivo or f"o comando saiu com o código {r.returncode}"
    if r.returncode == 0:
        gravar_meta(a.pasta, None, saida.name)
        print(saida)
        return 0
    if r.returncode == 3:
        achado = re.search(r"trabalho (\S+?)\)", motivo)
        gravar_meta(a.pasta, achado.group(1) if achado else None, None)
    print(f"Só a página: {motivo}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
