"""Todo modulo de `app/` tem chamador dentro do app (issue #2308).

O `planejamento_demanda` ficou no app depois que o Envio aos desenvolvedores
saiu da ponte (PR #2306): so os testes o importavam, e a suite verde dizia que
estava tudo certo. Codigo assim e um caminho que alguem volta a usar por
engano. Esta varredura le os `import` de `app/` pelo `ast`, sem executar nada,
e reprova o modulo que ninguem do app importa.

Fica de fora so a entrada do servidor e o script de uma vez, que roda pela
linha de comando e e chamado de fora do app, cada um com o motivo.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).parent.parent
APP = BACKEND / "app"

# O que roda sem ser importado por ninguem do app.
SEM_CHAMADOR_NO_APP = {
    # A entrada do servidor: o `uvicorn app.main:app` do Dockerfile.
    "app.main": "entrada do servidor",
    # Script de uma vez, pelo `scripts/oneshot/migrar_fluxogramas_mermaid.py` (issue #224).
    "app.services.pops_fluxograma_migracao": "script de uma vez",
    # Script de uma vez, por `python -m app.services.tecnologia_carga_historico` (issue #1555).
    "app.services.tecnologia_carga_historico": "script de uma vez",
}


def _nome_do_modulo(caminho: Path) -> str:
    partes = list(caminho.relative_to(BACKEND).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes = partes[:-1]
    return ".".join(partes)


def _importados_por(caminho: Path, nome: str) -> set[str]:
    """Os nomes que o arquivo importa, ja resolvidos: `from app.services import x`
    conta para `app.services` e para `app.services.x`, e o import relativo vira
    absoluto."""
    pacote = nome if caminho.name == "__init__.py" else nome.rpartition(".")[0]
    importados: set[str] = set()
    for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            importados.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom):
            base = no.module or ""
            if no.level:
                acima = pacote.split(".")[: len(pacote.split(".")) - (no.level - 1)]
                base = ".".join([*acima, *([no.module] if no.module else [])])
            importados.add(base)
            importados.update(f"{base}.{alias.name}" for alias in no.names)
    return importados


def modulos_sem_chamador(raiz: Path = APP) -> list[str]:
    """Os modulos (arquivo `.py` que nao e pacote) que nenhum outro arquivo de
    `raiz` importa."""
    arquivos = {_nome_do_modulo(p): p for p in raiz.rglob("*.py")}
    chamados: set[str] = set()
    for nome, caminho in arquivos.items():
        chamados.update(i for i in _importados_por(caminho, nome) if i != nome)
    return sorted(nome for nome, caminho in arquivos.items() if caminho.name != "__init__.py" and nome not in chamados)


def test_todo_modulo_do_app_tem_chamador_no_app():
    """Mutante: devolver o `planejamento_demanda.py` ao app, so com os testes
    importando, reprova aqui com o nome dele."""
    assert [m for m in modulos_sem_chamador() if m not in SEM_CHAMADOR_NO_APP] == []


def test_a_lista_de_excecoes_so_tem_modulo_que_existe_e_segue_sem_chamador():
    """A excecao que perdeu o motivo (o script apagado, ou que ganhou chamador)
    sai da lista, senao ela vira lugar de esconder modulo orfao."""
    assert sorted(SEM_CHAMADOR_NO_APP) == sorted(m for m in modulos_sem_chamador() if m in SEM_CHAMADOR_NO_APP)


def test_a_configuracao_nao_tem_mais_o_modelo_do_planejamento():
    """O `LLM_MODEL_PLANEJAMENTO` so dava o modelo do `planejamento_demanda`.
    Sem ele, a variavel no Coolify nao muda nada, e o campo que sobrasse aqui
    diria que muda. Mutante: devolver o campo ao `Settings`."""
    from app.config import Settings

    assert "llm_model_planejamento" not in Settings.model_fields
