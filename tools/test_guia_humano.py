"""O Guia passo a passo do card humano: a página que o Pedro abre, lê e copia.

A skill `guia-humano` monta a página de `docs/comunicacao/guias/<N>/dados.json`
com o `modelo.html` e publica no projeto `guias-hsm` da Vercel; o marcador
`<!-- guia: <url> -->` no corpo da issue é o que o PedroOS lê.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
GUIAS = RAIZ / "docs" / "comunicacao" / "guias"
SCRIPT = RAIZ / ".claude" / "skills" / "guia-humano" / "scripts" / "guia.py"

spec = importlib.util.spec_from_file_location("guia", SCRIPT)
guia = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guia)


@pytest.fixture
def dados() -> dict:
    return json.loads((GUIAS / "1961" / "dados.json").read_text(encoding="utf-8"))


def test_todo_guia_do_repositorio_monta(dados: dict) -> None:
    for arquivo in GUIAS.glob("*/dados.json"):
        html = guia.montar(json.loads(arquivo.read_text(encoding="utf-8")))
        assert "{{" not in html, arquivo


def test_cada_passo_vira_um_cartao_com_a_caixa_de_feito(dados: dict) -> None:
    html = guia.montar(dados)

    assert html.count('<article class="passo"') == len(dados["passos"])
    assert html.count('class="marcar"><input type="checkbox"') == len(dados["passos"])


def test_todo_texto_para_copiar_tem_o_botao_e_sai_igual(dados: dict) -> None:
    html = guia.montar(dados)
    copias = [c for p in dados["passos"] for c in p.get("copias", [])]

    assert html.count("data-copiar=") == len(copias)
    for c in copias:
        assert guia._esc(c["copiar"]) in html


def test_rotulo_da_tela_sai_desenhado_como_botao(dados: dict) -> None:
    html = guia.montar(dados)

    assert '<span class="ui">Enviar para assinatura</span>' in html
    assert "[[" not in html


def test_recusa_travessao_ate_no_texto_para_copiar(dados: dict) -> None:
    ruim = copy.deepcopy(dados)
    ruim["passos"][0]["copias"][0]["copiar"] += " — fim"

    with pytest.raises(ValueError, match="travessão"):
        guia.montar(ruim)


def test_recusa_jargao_na_explicacao(dados: dict) -> None:
    ruim = copy.deepcopy(dados)
    ruim["passos"][0]["texto"].append("Depois do deploy, confira.")

    with pytest.raises(ValueError, match="palavra técnica: deploy"):
        guia.montar(ruim)


def test_comando_para_copiar_pode_ter_palavra_tecnica(dados: dict) -> None:
    bom = copy.deepcopy(dados)
    bom["passos"][0]["copias"][0]["copiar"] = "cat backend/.env"

    assert "cat backend/.env" in guia.montar(bom)


def test_marcador_entra_uma_vez_no_fim_sem_mudar_o_corpo() -> None:
    corpo = "Pai: #1764\n\nTexto do card.\n"
    uma = guia.com_marcador(corpo, 1961)

    assert uma.startswith(corpo)
    assert uma.endswith("<!-- guia: https://guias-hsm.vercel.app/1961 -->\n")
    assert "https://guias-hsm.vercel.app/1961\n<!--" in uma
    assert guia.com_marcador(uma, 1961) == uma


def test_site_leva_todos_os_guias_a_logo_e_a_fonte(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GUIAS_HSM_DIR", str(tmp_path / "sem-vinculo"))
    destino = tmp_path / "site"

    numeros = guia.montar_site(destino)

    assert 1961 in numeros
    for n in numeros:
        assert (destino / str(n) / "index.html").exists()
    assert (destino / "logo-hsm.png").exists()
    assert (destino / "HPSimplified_Rg.ttf").exists()
    assert (destino / "vercel.json").exists()
