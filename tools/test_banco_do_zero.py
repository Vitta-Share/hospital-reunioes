"""O banco local monta do zero com o Supabase CLI 3 (achado do diretor, 25/11/2026).

A guarda de número repetido olha só a migration que o PR acrescenta contra a
`main` do momento; dois PRs paralelos passaram cada um sozinho e a pasta ficou
com 172 e 174 em dobro. Este teste olha a pasta inteira, que é o que o
`supabase start` lê. O job `banco-do-zero.yml` prova o resto num banco de verdade.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
SUPABASE = RAIZ / "hospital-reunioes" / "supabase"
WORKFLOW = RAIZ / ".github" / "workflows" / "banco-do-zero.yml"


def test_nenhum_numero_de_migration_se_repete_na_pasta() -> None:
    numeros = Counter(
        int(m.group(1))
        for p in (SUPABASE / "migrations").glob("*.sql")
        if (m := re.match(r"^(\d+)_", p.name))
    )
    repetidos = sorted(n for n, vezes in numeros.items() if vezes > 1)
    assert not repetidos, f"número de migration repetido na pasta: {repetidos}"


def test_config_usa_a_secao_do_cli_3() -> None:
    config = (SUPABASE / "config.toml").read_text(encoding="utf-8")
    assert re.search(r"^\[local_smtp\]$", config, re.M), "falta [local_smtp]"
    assert not re.search(r"^\[inbucket\]$", config, re.M), "[inbucket] é do CLI 2"


def test_job_monta_o_banco_com_o_cli_3_quando_a_pasta_muda() -> None:
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    gatilho = wf.get("on") or wf.get(True)
    for evento in ("push", "pull_request"):
        assert "hospital-reunioes/supabase/**" in gatilho[evento]["paths"], evento
    (job,) = wf["jobs"].values()
    assert re.fullmatch(r"supabase@3\.\d+\.\d+", job["env"]["SUPABASE_CLI"])
    comandos = " ".join(p.get("run", "") for p in job["steps"])
    assert '"$SUPABASE_CLI" start' in comandos
