"""O /setup-diretor do diretor colaborador (issue #2276, ADR 0113, decisões 1, 2, 4 e 11).

O diretor vira colaborador do repositório sem poder mergear: o Claude dele nega o
merge pelo `gh` e pela API (no `settings.json` dele), e o check do PR do diretor
reprova até um Desenvolvedor pôr a label `assumido`. Os testes rodam o
`conferir.sh` como o Claude dele roda, com um `settings.json` de mentira, e leem o
passo a passo como ele lê.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SKILL = RAIZ / ".claude" / "skills" / "setup-diretor"
CONFERIR = SKILL / "scripts" / "conferir.sh"

NEGA_MERGE = ["Bash(gh pr merge:*)", "Bash(gh api *merge*)"]


def conferir(settings: dict, tmp_path: Path) -> list[str]:
    """Roda o conferir.sh com o settings.json dado e devolve as linhas da trava do merge."""
    (tmp_path / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path)
    saida = subprocess.run(
        ["bash", str(CONFERIR)], capture_output=True, text=True, env=env, timeout=180
    ).stdout
    return [linha for linha in saida.splitlines() if "merge" in linha.lower()]


precisa_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="sem jq")


@precisa_jq
def test_conferir_mostra_falta_sem_a_negacao_do_merge_no_settings(tmp_path: Path) -> None:
    linhas = conferir({"permissions": {"deny": ["Bash(git push --force:*)"]}}, tmp_path)
    assert len(linhas) == 1, linhas
    assert linhas[0].split()[0] == "FALTA", linhas


@precisa_jq
def test_conferir_mostra_ok_com_a_negacao_do_merge_no_settings(tmp_path: Path) -> None:
    linhas = conferir({"permissions": {"deny": ["Bash(git push --force:*)", *NEGA_MERGE]}}, tmp_path)
    assert len(linhas) == 1, linhas
    assert linhas[0].split()[0] == "OK", linhas
