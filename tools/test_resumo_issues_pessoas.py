"""A lista de pessoas do Projeto no `.claude/fluxo.json` e o `/resumo-issues` lendo os nomes dali (issue #2272).

O `montar(issues)` recebe os nomes; o GitHub não entra no teste.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FLUXO = RAIZ / ".claude" / "fluxo.json"
SCRIPT = RAIZ / ".claude" / "skills" / "resumo-issues" / "scripts" / "resumo_issues.py"

_spec = importlib.util.spec_from_file_location("resumo_issues", SCRIPT)
ri = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ri)


def issue(n, donos=()):
    return {"number": n, "title": "t", "body": "", "assignees": list(donos), "parent": None}


def test_fluxo_do_hospital_tem_os_tres_socios_e_o_diretor():
    pessoas = json.loads(FLUXO.read_text(encoding="utf-8"))["pessoas"]
    assert pessoas == [
        {"login": "pedrorezendefig", "nome": "Pedro", "papel": "socio"},
        {"login": "pedroribbe", "nome": "Ribbe", "papel": "socio"},
        {"login": "lucassampaioc1", "nome": "Lucas", "papel": "socio"},
        {"login": "felipemalafaia", "nome": "Felipe", "papel": "diretor"},
    ]
