"""O `/divulgar` publica só a página, sem vídeo.

O Estúdio de Vídeos antigo saiu em 27/11/2026, e com ele o pedido de vídeo pelo `pedir_video.py`.
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
    [
        "motion-studio", "Motion studio", "PedroDev/Videos", "regras-de-video", "skill `som`", "remotion", "render.mjs",
        "pedir_video", "profitize-estreia", "Nova Feature", "video_do_estudio", "video-start", "<video",
    ],
)
def test_receita_nao_cita_estudio_nem_pedido_de_video(citacao):
    assert citacao.lower() not in _texto().lower()


def test_script_do_pedido_de_video_saiu():
    assert not (SKILL.parent / "scripts" / "video_do_estudio.py").exists()


def test_descricao_nao_fala_de_video():
    frente = _texto().split("---")[1].lower()
    for termo in ("vídeo", "video", "mp4", "estúdio"):
        assert termo not in frente


def test_sintaxe_e_so_o_numero_da_entrega():
    frente = _texto().split("---")[1]
    assert "`/divulgar <N>`" in frente
    for flag in ("--rapido", "--voz", "--completo", "--so-video", "--so-pagina"):
        assert flag not in frente


def test_pagina_nova_sai_sem_as_abas_do_video():
    assert "tirar o que é do vídeo: a barra de abas, a aba Demonstração por Vídeo, o CTA e o script das abas" in _texto()


def test_publicacao_nao_copia_mp4():
    publicacao = _texto().split("**Publicação")[1].split("## Checklist")[0]
    assert "npx vercel@latest deploy --prod --yes" in publicacao
    assert ".mp4" not in publicacao


def test_link_na_issue_segue_pelo_marcar_demonstracao():
    assert "python3 .claude/skills/divulgar/scripts/marcar_demonstracao.py <N> https://<projeto>.vercel.app" in _texto()
