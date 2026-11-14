"""O `/divulgar` faz só a Página de divulgação: o estúdio de vídeo saiu em 14/11/2026.

A receita é texto que um agente segue: estes testes leem o `SKILL.md` como o agente lê.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SKILL = RAIZ / ".claude" / "skills" / "divulgar" / "SKILL.md"


def _texto() -> str:
    return SKILL.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "citacao",
    ["motion-studio", "Motion studio", "PedroDev/Videos", "regras-de-video", "skill `copy`", "skill `som`", "remotion", "render.mjs", "<video"],
)
def test_receita_nao_cita_o_estudio_de_video_apagado(citacao):
    assert citacao.lower() not in _texto().lower()


def test_sintaxe_e_so_o_numero_da_entrega():
    frente = _texto().split("---")[1]
    assert "`/divulgar <N>`" in frente
    for flag in ("--rapido", "--voz", "--completo", "--so-video", "--so-pagina"):
        assert flag not in frente
