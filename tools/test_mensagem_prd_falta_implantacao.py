"""O que falta para usar, na mensagem do PRD entregue (issue #2271, ADR 0113, decisão 9).

O `/mensagem-prd` roda `mensagem-prd/scripts/falta_implantacao.py <PRD>`: o
script lê no GitHub os Cards de implantação abertos do PRD (sub-issues com a
label `implantacao`) e imprime a linha "Para começar a usar, falta: ..." com o
título de cada um. Sem card aberto, não imprime nada e a mensagem fica como
era. Sem a ponte do app: o card mora no GitHub.

`gh` de mentira no PATH: o GitHub de verdade não entra no teste.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SKILL = RAIZ / ".claude" / "skills" / "mensagem-prd"
SCRIPT = SKILL / "scripts" / "falta_implantacao.py"

PRD = "2205"


def card(numero: int, titulo: str, labels: list[str], estado: str = "open") -> dict:
    return {"number": numero, "title": titulo, "state": estado, "labels": [{"name": n} for n in labels]}


def rodar(tmp_path: Path, paginas: list[list[dict]] | None, prd: str = PRD) -> subprocess.CompletedProcess:
    """`paginas` é o que o `gh api --paginate --slurp` devolve; None faz o `gh` falhar."""
    falso = tmp_path / "bin"
    falso.mkdir(exist_ok=True)
    (tmp_path / "resposta.json").write_text(json.dumps(paginas), encoding="utf-8")
    gh = falso / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$GH_LOG"\n'
        'if [ "$GH_FALHA" = 1 ]; then echo "HTTP 502: Bad Gateway" >&2; exit 1; fi\n'
        'cat "$GH_RESPOSTA"\n',
        encoding="utf-8",
    )
    gh.chmod(0o755)
    ambiente = dict(
        os.environ,
        PATH=f"{falso}:{os.environ['PATH']}",
        GH_LOG=str(tmp_path / "gh.log"),
        GH_RESPOSTA=str(tmp_path / "resposta.json"),
        GH_FALHA="1" if paginas is None else "0",
    )
    return subprocess.run([sys.executable, str(SCRIPT), prd], capture_output=True, text=True, env=ambiente)


def chamadas(tmp_path: Path) -> list[str]:
    return (tmp_path / "gh.log").read_text(encoding="utf-8").splitlines()


def test_lista_os_cards_de_implantacao_abertos_do_prd(tmp_path):
    paginas = [
        [
            card(2210, "Testar o anonimato do Canal de Conduta", ["implantacao", "ready-for-human"]),
            card(2211, "Tela do Canal", ["ready-for-agent"]),
            card(2212, "Treinar a recepção", ["implantacao", "ready-for-human"]),
        ],
        [
            card(2213, "Divulgar o Canal no hospital", ["ready-for-human", "implantacao"]),
            card(2214, "Configurar o e-mail do Canal", ["implantacao"], estado="closed"),
        ],
    ]

    feito = rodar(tmp_path, paginas)

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == (
        "Para começar a usar, falta: Testar o anonimato do Canal de Conduta, "
        "Treinar a recepção e Divulgar o Canal no hospital.\n"
    )
    assert chamadas(tmp_path) == [f"api --paginate --slurp repos/{{owner}}/{{repo}}/issues/{PRD}/sub_issues"]


def test_com_um_card_so_a_linha_nao_tem_juncao(tmp_path):
    feito = rodar(tmp_path, [[card(2210, "Testar o anonimato do Canal de Conduta", ["implantacao"])]])

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == "Para começar a usar, falta: Testar o anonimato do Canal de Conduta.\n"


def test_sem_card_de_implantacao_aberto_nao_imprime_nada(tmp_path):
    paginas = [
        [
            card(2211, "Tela do Canal", ["ready-for-agent"]),
            card(2214, "Configurar o e-mail do Canal", ["implantacao"], estado="closed"),
        ]
    ]

    feito = rodar(tmp_path, paginas)

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == ""


def test_github_que_nao_responde_sai_1_com_o_motivo_e_sem_a_linha(tmp_path):
    """A falha não pode passar por "nada falta": sai 1, e quem chama avisa o
    Pedro em vez de mandar a mensagem como se a entrega estivesse pronta."""
    feito = rodar(tmp_path, None)

    assert feito.returncode == 1
    assert feito.stdout == ""
    assert "502" in feito.stderr


def test_uso_errado_sai_2(tmp_path):
    feito = rodar(tmp_path, [[]], prd="abc")

    assert feito.returncode == 2


def test_a_skill_roda_o_script_e_le_os_cards_sem_a_ponte():
    texto = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    passo = texto[texto.index("3. **O que falta para usar**") : texto.index("4. **Escreva**")]

    assert "python3 .claude/skills/mensagem-prd/scripts/falta_implantacao.py <PRD>" in passo
    assert "Cards de implantação abertos" in passo
    assert '"Para começar a usar, falta:"' in texto
    assert "Pedido de implantação" not in texto and "Demanda" not in passo
