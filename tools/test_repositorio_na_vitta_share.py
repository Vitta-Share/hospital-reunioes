"""O repositório do Hospital mora na organização Vitta-Share (issue #2303, PRD #2301).

Referência fixa ao endereço antigo dependia do redirecionamento do GitHub, que pode
falhar em gravação. Login de pessoa (`pedrorezendefig` como dono de card) não muda,
e o histórico (registro das subidas, ADRs, snapshots e a documentação gerada deles)
fica como foi escrito.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

ANTIGOS = ("pedrorezendefig/hospital-reunioes", "ghcr.io/pedrorezendefig")

HISTORICO = (
    ":!docs/spec/deploy/history.json",
    ":!docs/adr",
    ":!docs/spec/snapshots",
    ":!docs/documentacao.html",
    ":!tools/test_repositorio_na_vitta_share.py",
)


def referencias_antigas(raiz: Path) -> list[str]:
    padroes = [arg for p in ANTIGOS for arg in ("-e", p)]
    feito = subprocess.run(
        ["git", "grep", "-n", "-i", "-F", *padroes, "--", ".", *HISTORICO],
        cwd=raiz,
        capture_output=True,
        text=True,
    )
    assert feito.returncode in (0, 1), feito.stderr
    return feito.stdout.splitlines()


def test_nenhuma_referencia_ao_endereco_antigo_fora_do_historico() -> None:
    assert referencias_antigas(RAIZ) == []


def test_a_varredura_acha_o_endereco_antigo_num_arquivo_novo(tmp_path: Path) -> None:
    """Prova que a varredura não é cega: um arquivo com o endereço antigo aparece."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "script.sh").write_text("gh repo clone PedroRezendeFig/hospital-reunioes\n")
    (tmp_path / "ci.yml").write_text("IMAGEM: ghcr.io/pedrorezendefig/hospital-reunioes-backend\n")
    (tmp_path / "pessoa.py").write_text('DONO = "pedrorezendefig"\n')
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    achados = referencias_antigas(tmp_path)
    assert sorted(a.split(":", 1)[0] for a in achados) == ["ci.yml", "script.sh"]


def test_fork_feito_antes_da_troca_recebe_o_set_url_do_upstream(tmp_path: Path) -> None:
    """O upstream de um fork feito antes da troca já existe: o conserto troca o endereço."""
    script = tmp_path / ".claude" / "skills" / "setup-diretor" / "scripts" / "conferir.sh"
    script.parent.mkdir(parents=True)
    shutil.copy(RAIZ / ".claude" / "skills" / "setup-diretor" / "scripts" / "conferir.sh", script)
    antigo = "https://github.com/" + "pedrorezendefig" + "/hospital-reunioes.git"
    fork = "https://github.com/felipe-hsm/hospital-reunioes.git"
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", fork], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "upstream", antigo], check=True)
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path)
    saida = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=env, timeout=180, check=False
    ).stdout
    linhas = [linha for linha in saida.splitlines() if "upstream no time" in linha]
    assert len(linhas) == 1, saida
    assert linhas[0].split()[0] == "FALTA", linhas
    assert linhas[0].endswith(
        "git remote set-url upstream https://github.com/Vitta-Share/hospital-reunioes.git"
    ), linhas
