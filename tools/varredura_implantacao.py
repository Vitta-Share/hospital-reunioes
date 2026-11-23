#!/usr/bin/env python3
"""A varredura dos cards abertos de hoje (issue #2214, ADR 0111, decisões 2 e 12).

Lista os cards `ready-for-human` abertos ligados a uma Demanda que cabem na
regra da ADR 0111, decisão 2: vêm depois do código e não seguram nenhuma fatia.
Com `--aplicar`, põe a label `implantacao` neles e comenta a lista no card
indicado. Não manda nenhum ao app: o Pedido de implantação só nasce pelo clique
"Mandar ao hospital" do PedroOS (decisão 4).

A regra, na ordem:

- o card fora do espelho (`<!-- demanda-vitta: nenhuma ... -->`) fica de fora;
- o card sem pai é a própria raiz, não um card de uma Demanda;
- o pai precisa ser Demanda: `origem:diretor`, o marcador `<!-- demanda-vitta`
  ou a regra do espelho (`type:` mais uma `area:` do app);
- card que segura fatia aberta (uma issue aberta que não é card humano tem o
  `blocked_by` apontando para ele) é o Passo a passo da ADR 0110;
- card com PR aberto que o fecha é código esperando decisão, não implantação;
- `--fora N=motivo` tira um card pelo juízo de quem roda, com o motivo.

Card humano que espera ou é esperado por outro card humano continua candidato:
a ordem vira a espera entre Pedidos (decisão 8) e vai no comentário.

Rodar (lê o GitHub; só escreve com `--aplicar`):

    python3 tools/varredura_implantacao.py
    python3 tools/varredura_implantacao.py --aplicar --comentar 2214
"""

from __future__ import annotations

import re
from typing import Any

LABEL = "implantacao"
LABEL_HUMANA = "ready-for-human"
TIPOS = frozenset({"type:feature", "type:fix", "type:bug"})
AREAS_DO_APP = frozenset({"area:backend", "area:frontend", "area:supabase"})
_FORA_DO_ESPELHO = re.compile(r"<!--\s*demanda-vitta:\s*nenhuma", re.IGNORECASE)
_MARCADOR_DA_DEMANDA = re.compile(r"<!--\s*demanda-vitta\b", re.IGNORECASE)


def _e_demanda(raiz: dict[str, Any]) -> bool:
    labels = set(raiz.get("labels") or ())
    corpo = str(raiz.get("corpo") or "")
    if _FORA_DO_ESPELHO.search(corpo):
        return False
    if "origem:diretor" in labels or _MARCADOR_DA_DEMANDA.search(corpo):
        return True
    return bool(labels & TIPOS) and bool(labels & AREAS_DO_APP)


def _e_humano(issue: dict[str, Any]) -> bool:
    return LABEL_HUMANA in set(issue.get("labels") or ())


def _lista(issues: list[dict[str, Any]]) -> str:
    return ", ".join(f"#{i['numero']}" for i in issues)


def _veredito(card: dict[str, Any], fora: dict[int, str]) -> tuple[bool, str]:
    if _FORA_DO_ESPELHO.search(str(card.get("corpo") or "")):
        return False, "card fora do espelho, sem Demanda"
    raiz = card.get("raiz")
    if not raiz:
        return False, "não tem pai: é a própria raiz, não um card de uma Demanda"
    if not _e_demanda(raiz):
        return False, f"o pai #{raiz['numero']} não é Demanda"
    fatias = [i for i in card.get("bloqueia") or () if not _e_humano(i)]
    if fatias:
        return False, f"segura fatia aberta: {_lista(fatias)}"
    if card.get("pr_aberto"):
        return False, f"é código: o PR #{card['pr_aberto']} que fecha o card está aberto"
    if card["numero"] in fora:
        return False, fora[card["numero"]]
    return True, f"card da Demanda #{raiz['numero']}, vem depois do código e não segura fatia"


def classificar(cards: list[dict[str, Any]], fora: dict[int, str] | None = None) -> list[dict[str, Any]]:
    """Um veredito por card: `candidato`, `motivo` e as esperas entre cards humanos."""
    fora = fora or {}
    vereditos = []
    for card in sorted(cards, key=lambda c: c["numero"]):
        candidato, motivo = _veredito(card, fora)
        vereditos.append(
            {
                "numero": card["numero"],
                "titulo": card["titulo"],
                "candidato": candidato,
                "motivo": motivo,
                "ja_tinha_a_label": LABEL in set(card.get("labels") or ()),
                "espera": list(card.get("espera") or ()),
                "esperado_por": [i for i in card.get("bloqueia") or () if _e_humano(i)],
            }
        )
    return vereditos
