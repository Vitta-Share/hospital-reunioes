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
    return {
        "number": n,
        "title": "t",
        "body": "",
        "assignees": list(donos),
        "parent": None,
    }


def test_fluxo_do_hospital_tem_os_tres_socios_e_o_diretor():
    pessoas = json.loads(FLUXO.read_text(encoding="utf-8"))["pessoas"]
    assert pessoas == [
        {"login": "pedrorezendefig", "nome": "Pedro", "papel": "socio"},
        {"login": "pedroribbe", "nome": "Ribbe", "papel": "socio"},
        {"login": "lucassampaioc1", "nome": "Lucas", "papel": "socio"},
        {"login": "felipemalafaia", "nome": "Felipe", "papel": "diretor"},
    ]


def test_resumo_mostra_felipe_lendo_o_nome_do_fluxo_json():
    nomes = ri.nomes_do_fluxo(ri.ler_fluxo(RAIZ))
    saida = ri.montar([issue(1, donos=["felipemalafaia"])], "Hospital", nomes)
    assert "\nFelipe (1)\n" in saida
    assert "felipemalafaia" not in saida


def test_sem_a_lista_pessoas_o_resumo_mostra_o_login(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "fluxo.json").write_text(
        json.dumps({"nome": "Outro"}), encoding="utf-8"
    )
    nomes = ri.nomes_do_fluxo(ri.ler_fluxo(tmp_path))
    saida = ri.montar(
        [issue(1, donos=["felipemalafaia"]), issue(2, donos=["pedroribbe"])],
        "Outro",
        nomes,
    )
    assert "\nfelipemalafaia (1)\n" in saida
    assert "\npedroribbe (1)\n" in saida


def test_sem_fluxo_json_o_resumo_mostra_o_login(tmp_path):
    saida = ri.montar(
        [issue(1, donos=["felipemalafaia"])],
        "Outro",
        ri.nomes_do_fluxo(ri.ler_fluxo(tmp_path)),
    )
    assert "\nfelipemalafaia (1)\n" in saida
