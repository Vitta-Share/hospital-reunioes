"""Nenhuma skill do Hospital chama as rotas que saíram da ponte (issue #2281, ADR 0113, decisão 7).

Desde a issue #2281 a ponte de automação (`/api/automacao/tecnologia/...`) só
tem a leitura dos anexos, que o `pegar-issue/scripts/anexos.py` chama. Uma
skill que ainda chamasse a Conversa, o Pedido da Vitta, os Destinatários, a
Demanda da issue, a implantação ou as validações bateria num 404 no meio do
fluxo. A varredura lê cada arquivo de texto das skills e dos agentes do
repositório e aceita a ponte só no caminho dos anexos.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTAS = (RAIZ / ".claude" / "skills", RAIZ / ".claude" / "agents")

PONTE = re.compile(r"automacao/tecnologia")
# O único caminho que fica: `/demandas/<id>/anexos`, com o id literal ou
# interpolado (`{urllib.parse.quote(demanda, safe='')}` tem espaço, e nenhuma barra).
SO_OS_ANEXOS = re.compile(r"/demandas/[^/]+/anexos")


def _arquivos_de_texto() -> list[Path]:
    arquivos = []
    for pasta in PASTAS:
        for caminho in sorted(pasta.rglob("*")):
            if not caminho.is_file() or "__pycache__" in caminho.parts:
                continue
            try:
                caminho.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            arquivos.append(caminho)
    return arquivos


def _chamadas_da_ponte() -> list[tuple[str, int, str]]:
    """Cada menção ao endereço da ponte: arquivo, linha e o resto da linha dali em diante."""
    achadas = []
    for caminho in _arquivos_de_texto():
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), start=1):
            for casou in PONTE.finditer(linha):
                achadas.append((str(caminho.relative_to(RAIZ)), numero, linha[casou.start() :]))
    return achadas


def test_a_varredura_olha_para_as_skills_de_verdade():
    """Contraprova: sem ela, a pasta errada daria uma lista vazia e o teste
    abaixo passaria sobre nada."""
    script_dos_anexos = ".claude/skills/pegar-issue/scripts/anexos.py"

    assert script_dos_anexos in {str(c.relative_to(RAIZ)) for c in _arquivos_de_texto()}
    assert script_dos_anexos in {arquivo for arquivo, _, _ in _chamadas_da_ponte()}


def test_nenhuma_skill_chama_rota_que_saiu_da_ponte():
    fora_dos_anexos = [
        f"{arquivo}:{numero}: {trecho.strip()}"
        for arquivo, numero, trecho in _chamadas_da_ponte()
        if not SO_OS_ANEXOS.match(trecho, len(PONTE.pattern))
    ]

    assert fora_dos_anexos == []
