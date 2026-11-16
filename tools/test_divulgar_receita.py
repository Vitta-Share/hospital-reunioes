"""O `/divulgar` faz o vídeo pelo Estúdio de Vídeos e a página com ele (issue #1761).

O estúdio antigo (Motion studio) saiu em 14/11/2026; o vídeo volta pelo Estúdio do PedroOS.
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
    ["motion-studio", "Motion studio", "PedroDev/Videos", "regras-de-video", "skill `som`", "remotion", "render.mjs"],
)
def test_receita_nao_cita_o_estudio_de_video_apagado(citacao):
    assert citacao.lower() not in _texto().lower()


def test_sintaxe_e_so_o_numero_da_entrega():
    frente = _texto().split("---")[1]
    assert "`/divulgar <N>`" in frente
    for flag in ("--rapido", "--voz", "--completo", "--so-video", "--so-pagina"):
        assert flag not in frente


def test_receita_nao_diz_mais_que_a_demonstracao_e_sem_video():
    texto = _texto()
    assert "sem vídeo" not in texto.lower()
    assert "não faz vídeo" not in texto.lower()


@pytest.mark.parametrize(
    "passo",
    [
        "playwright-cli video-start",  # a gravação nas telas reais
        "playwright-cli video-stop",
        "video/roteiro.md",  # o texto
        "scripts/video_do_estudio.py",  # o pedido ao Estúdio
        "~/PedroDev/OS/scripts/estudio/pedir_video.py",
        "<video controls",  # a página com o vídeo embutido
    ],
)
def test_receita_descreve_gravacao_texto_pedido_e_pagina_com_video(passo):
    assert passo in _texto()


def test_receita_decide_pelos_codigos_de_saida_do_comando():
    texto = _texto()
    for codigo in ("Saída 0", "Saída 1", "Saída 2", "Saída 3"):
        assert codigo in texto
    assert "Só a página:" in texto


def test_link_na_issue_segue_pelo_marcar_demonstracao():
    assert "python3 .claude/skills/divulgar/scripts/marcar_demonstracao.py <N> https://<projeto>.vercel.app" in _texto()
