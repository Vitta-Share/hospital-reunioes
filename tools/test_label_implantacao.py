"""A label `implantacao` no fluxo (issue #2212, ADR 0111, decisões 2 e 3).

Só ganha a label o card humano que vem depois do código e não segura nenhuma
fatia (teste de aceite, configuração, abertura, treinamento). O card humano que
segura código (chave no Coolify, decisão sobre migration, layout aprovado antes)
continua sem ela. Quem põe é o `/to-issues`, ao criar a fatia, e o `/triage`,
pela mesma regra; a regra vive em `docs/agents/triage-labels.md`. O teste lê o
trecho certo de cada arquivo, como o agente lê.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SKILLS = RAIZ / ".claude" / "skills"
LABELS = RAIZ / "docs" / "agents" / "triage-labels.md"


def ler(skill: str) -> str:
    return (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")


def secao(texto: str, titulo: str) -> str:
    """O trecho do título até o próximo título de nível igual ou maior."""
    m = re.search(rf"^(#+) {re.escape(titulo)}\s*$", texto, re.MULTILINE)
    assert m, f"seção '{titulo}' não encontrada"
    nivel = len(m.group(1))
    resto = texto[m.end() :]
    fim = re.search(rf"^#{{1,{nivel}}} ", resto, re.MULTILINE)
    return resto[: fim.start()] if fim else resto


def regra_da_label() -> str:
    return secao(LABELS.read_text(encoding="utf-8"), "Label de implantação (ADR 0111)")


def test_triage_labels_descreve_a_label_implantacao_com_a_regra() -> None:
    regra = regra_da_label()

    assert "`implantacao`" in regra, "a seção não nomeia a label"
    assert "depois do código" in regra, (
        "a regra não diz que o card vem depois do código"
    )
    assert "não segura nenhuma fatia" in regra, (
        "a regra não diz que o card não segura fatia"
    )
    for uso in ("teste de aceite", "configuração", "abertura", "treinamento"):
        assert uso in regra, f"a regra não cita {uso} como exemplo de implantação"
    assert "chave no Coolify" in regra, (
        "a regra não mostra o card humano que segura código"
    )


def exemplo(trecho: str, rotulo: str) -> str:
    linhas = [li for li in trecho.splitlines() if li.startswith(f"- **{rotulo}:**")]
    assert linhas, f"falta o exemplo '{rotulo}'"
    return linhas[0]


def test_to_issues_diz_quando_a_fatia_humana_ganha_a_label() -> None:
    fatia = secao(
        ler("to-issues"), "A fatia humana depois do código (label `implantacao`)"
    )

    assert "--label implantacao" in fatia, (
        "a seção não mostra o comando que aplica a label"
    )
    assert "docs/agents/triage-labels.md" in fatia, (
        "a seção não aponta a regra da label"
    )
    assert "não segura nenhuma fatia" in fatia, "a seção não diz a regra"
    assert "teste de aceite" in exemplo(fatia, "Ganha").lower(), (
        "o exemplo que ganha não é de uso"
    )
    assert "espera" in exemplo(fatia, "Não ganha"), (
        "o exemplo que não ganha não diz que segura código"
    )


def test_triage_poe_ou_tira_a_label_pela_mesma_regra() -> None:
    passo = secao(ler("triage"), "Triage a specific issue")
    linha = [li for li in passo.splitlines() if "`implantacao`" in li]

    assert linha, "o /triage não fala da label implantacao ao aplicar o papel"
    regra = linha[0]
    assert "--add-label implantacao" in regra, "o /triage não mostra como pôr a label"
    assert "--remove-label implantacao" in regra, (
        "o /triage não mostra como tirar a label"
    )
    assert "docs/agents/triage-labels.md" in regra, (
        "o /triage não aponta a mesma regra do /to-issues"
    )
    assert "não segura nenhuma fatia" in regra, "o /triage não diz a regra"


def test_ask_pedro_cita_o_pedido_de_implantacao_no_pos_entrega() -> None:
    pos = secao(ler("ask-pedro"), "Pós-entrega")
    item = [li for li in pos.splitlines() if "Pedido de implantação" in li]

    assert item, "o Pós-entrega do /ask-pedro não cita o Pedido de implantação"
    assert "`implantacao`" in item[0], "o item não diz qual label marca o card"
    assert "Mandar ao hospital" in item[0], "o item não diz como o card vira Pedido"
