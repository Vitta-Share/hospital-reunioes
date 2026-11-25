"""A Tarefa do diretor nas ondas e nas skills do fluxo (issue #2271, ADR 0113, decisões 4, 9 e 12).

O que o diretor precisa fazer ou responder vira card no nome dele no GitHub,
com menção: pergunta em `needs-info`, coisa a fazer em `ready-for-human`. A
ponte do app (Conversa da Demanda, Pedido de implantação) e as Mensagens a
enviar do PedroOS saem das skills. O teste lê o trecho certo de cada arquivo,
como o agente lê.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CLAUDE = RAIZ / ".claude"
SKILLS = CLAUDE / "skills"
LABELS = RAIZ / "docs" / "agents" / "triage-labels.md"
TRACKER = RAIZ / "docs" / "agents" / "issue-tracker.md"

PONTE = re.compile(r"conversa\.py|enviar-no-app|mensagem_a_enviar|/implantacao\b|Mandar ao hospital")


def secao(texto: str, titulo: str) -> str:
    """O trecho do título até o próximo título de nível igual ou maior."""
    m = re.search(rf"^(#+) {re.escape(titulo)}\s*$", texto, re.MULTILINE)
    assert m, f"seção '{titulo}' não encontrada"
    nivel = len(m.group(1))
    resto = texto[m.end() :]
    fim = re.search(rf"^#{{1,{nivel}}} ", resto, re.MULTILINE)
    return resto[: fim.start()] if fim else resto


def ler(skill: str) -> str:
    return (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")


def notas(skill: str) -> str:
    return subprocess.run(
        [sys.executable, str(SKILLS / "onda-enxuta" / "scripts" / "fluxo.py"), "notas", skill],
        capture_output=True,
        text=True,
        check=True,
        cwd=RAIZ,
    ).stdout


def test_nenhuma_skill_chama_a_ponte_nem_as_mensagens_a_enviar():
    achados = []
    for arquivo in sorted(SKILLS.rglob("*")):
        if not arquivo.is_file() or "__pycache__" in arquivo.parts or "node_modules" in arquivo.parts:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        achados += [f"{arquivo.relative_to(RAIZ)}: {m.group(0)}" for m in PONTE.finditer(texto)]
    assert not (SKILLS / "pegar-issue" / "scripts" / "conversa.py").exists()
    assert achados == []


def test_as_notas_da_onda_nao_chamam_a_ponte():
    # A nota do Refino (`grill-with-docs`) é da #2270; aqui só a da onda.
    assert PONTE.search(notas("onda-enxuta")) is None


def test_a_baixa_que_espera_o_diretor_vira_tarefa_do_diretor():
    texto = notas("onda-enxuta")
    regra = texto[texto.index("**Baixa que espera o diretor") :]

    assert "Tarefa do diretor" in regra
    assert "DIRETOR_LOGINS" in regra
    # Pergunta espera em needs-info no nome dele; coisa a fazer é card próprio que bloqueia a fatia.
    assert "--remove-label ready-for-human --add-label needs-info" in regra
    assert "--add-assignee" in regra
    assert "blocked_by" in regra
    assert "<!-- automacao -->" in regra and "@<login>" in regra
    # A resposta volta pelo comentário dele na issue, e a fatia volta à Fila.
    assert "--remove-label needs-info --add-label ready-for-agent" in regra
    assert "WhatsApp" not in regra


def test_to_issues_cria_o_card_de_implantacao_no_nome_do_diretor():
    fatia = secao(ler("to-issues"), "A fatia humana depois do código (label `implantacao`)")

    assert "Card de implantação" in fatia
    assert "--label implantacao" in fatia and "--label ready-for-human" in fatia
    assert "--assignee" in fatia and "DIRETOR_LOGINS" in fatia
    assert "Mandar ao hospital" not in fatia and "Pedido de implantação" not in fatia


def test_triage_poe_o_card_de_implantacao_no_nome_do_diretor():
    passo = secao(ler("triage"), "Triage a specific issue")
    linha = [li for li in passo.splitlines() if "`implantacao`" in li][0]

    assert "--add-assignee" in linha and "DIRETOR_LOGINS" in linha


def test_triage_labels_descreve_a_tarefa_do_diretor():
    labels = LABELS.read_text(encoding="utf-8")
    tarefa = secao(labels, "Tarefa do diretor (ADR 0113)")
    implantacao = secao(labels, "Label de implantação (ADR 0111)")

    for trecho in ("`needs-info`", "`ready-for-human`", "no nome dele", "menção"):
        assert trecho in tarefa, trecho
    assert "Card de implantação" in implantacao
    assert "Mandar ao hospital" not in implantacao


def test_issue_tracker_descreve_a_tarefa_do_diretor():
    tarefa = secao(TRACKER.read_text(encoding="utf-8"), "Tarefa do diretor (ADR 0113)")

    for trecho in ("needs-info", "ready-for-human", "--add-assignee", "blocked_by", "fecha o card"):
        assert trecho in tarefa, trecho


def test_ask_pedro_aponta_a_tarefa_do_diretor():
    texto = ler("ask-pedro")
    item = [li for li in texto.splitlines() if "**Tarefa do diretor**" in li]

    assert item, "o /ask-pedro não cita a Tarefa do diretor"
    assert "docs/agents/issue-tracker.md" in item[0]
