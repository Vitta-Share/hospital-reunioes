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
        ["bash", str(CONFERIR)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    ).stdout
    return [linha for linha in saida.splitlines() if "merge" in linha.lower()]


precisa_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="sem jq")


@precisa_jq
def test_conferir_mostra_falta_sem_a_negacao_do_merge_no_settings(
    tmp_path: Path,
) -> None:
    linhas = conferir({"permissions": {"deny": ["Bash(git push --force:*)"]}}, tmp_path)
    assert len(linhas) == 1, linhas
    assert linhas[0].split()[0] == "FALTA", linhas


@precisa_jq
def test_conferir_mostra_ok_com_a_negacao_do_merge_no_settings(tmp_path: Path) -> None:
    linhas = conferir(
        {"permissions": {"deny": ["Bash(git push --force:*)", *NEGA_MERGE]}}, tmp_path
    )
    assert len(linhas) == 1, linhas
    assert linhas[0].split()[0] == "OK", linhas


@precisa_jq
def test_a_trava_que_a_parte_5_grava_e_a_que_o_conferir_aceita(tmp_path: Path) -> None:
    """O comando da Parte 5 roda num settings.json com plugins e o conferir passa a dar OK."""
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    trecho = skill.split("grave a trava do merge", 1)[1]
    comando = re.search(r"```bash\n(.*?)```", trecho, re.DOTALL).group(1)
    casa = tmp_path / "casa"
    (casa / ".claude").mkdir(parents=True)
    antes = {
        "enabledPlugins": {"x@y": True},
        "permissions": {"deny": ["Bash(rm -rf:*)"]},
    }
    (casa / ".claude" / "settings.json").write_text(json.dumps(antes), encoding="utf-8")
    subprocess.run(
        ["bash", "-c", comando], env={**os.environ, "HOME": str(casa)}, check=True
    )
    depois = json.loads(
        (casa / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    assert depois["enabledPlugins"] == {"x@y": True}, (
        "a trava apagou o que já estava lá"
    )
    assert "Bash(rm -rf:*)" in depois["permissions"]["deny"]
    linhas = conferir(depois, tmp_path)
    assert [linha.split()[0] for linha in linhas] == ["OK"], linhas


def nao_ensina_bug_pelo_claude(texto: str) -> list[str]:
    """Os trechos que falam de bug sem mandar ao Assistente do app."""
    blocos = re.split(r"\n\s*\n|\n(?=\s*(?:[-*]|\d+\.|\|) )", texto)
    return [
        b
        for b in blocos
        if re.search(r"\bbugs?\b", b, re.IGNORECASE) and "Assistente do app" not in b
    ]


def test_nenhuma_parte_ensina_a_relatar_bug_pelo_claude_dele() -> None:
    arquivos = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
    for arquivo in arquivos:
        texto = arquivo.read_text(encoding="utf-8")
        assert not nao_ensina_bug_pelo_claude(texto), (
            f"{arquivo.name}: {nao_ensina_bug_pelo_claude(texto)}"
        )
    passo = (SKILL / "references" / "passo-a-passo.md").read_text(encoding="utf-8")
    assert re.search(r"\bbug\b[^\n]*Assistente do app", passo), (
        "o passo a passo não diz onde vai o bug"
    )


def test_label_da_skill_e_a_do_check_do_pr_do_diretor() -> None:
    check = (RAIZ / ".github" / "workflows" / "pr-do-diretor.yml").read_text(
        encoding="utf-8"
    )
    (label,) = set(re.findall(r"l\.name === '([^']+)'", check))
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    parte_8 = skill.split("### Parte 8: o protótipo", 1)[1].split("### ", 1)[0]
    assert f"label `{label}`" in parte_8, (
        f"a Parte 8 não cita a label `{label}` do check"
    )
    passo = (SKILL / "references" / "passo-a-passo.md").read_text(encoding="utf-8")
    assert f'etiqueta "{label}"' in passo, (
        f"o passo a passo não cita a etiqueta {label}"
    )


def partes() -> dict[str, str]:
    """As Partes do passo a passo: título (sem o número) e o texto até a próxima Parte."""
    texto = (SKILL / "references" / "passo-a-passo.md").read_text(encoding="utf-8")
    blocos = re.split(r"^## Parte \d+\. ", texto, flags=re.MULTILINE)[1:]
    return {b.split("\n", 1)[0].strip(): b for b in blocos}


@pytest.mark.parametrize(
    "assunto", ["convite", "Arquivo de apoio", "Tarefa do diretor"]
)
def test_passo_a_passo_tem_a_parte_nova_com_como_saber_que_acabou(assunto: str) -> None:
    achadas = [t for t in partes() if assunto.lower() in t.lower()]
    assert len(achadas) == 1, (
        f"nenhuma Parte (ou mais de uma) sobre {assunto}: {list(partes())}"
    )
    (titulo,) = achadas
    assert "**Como saber que acabou:**" in partes()[titulo], (
        f"a Parte '{titulo}' não fecha"
    )
