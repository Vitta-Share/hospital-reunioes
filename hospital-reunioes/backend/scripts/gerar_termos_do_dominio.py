"""Gera a lista de termos do domínio que a peneira de dado pessoal deixa passar (issue #1813).

Saída: `app/services/dados/termos_do_dominio.txt`, um termo por linha, que o
`ouvidoria_pseudonimizacao` carrega no import. Termo composto em maiúscula
inicial ("Canal de Conduta", "Núcleo de Segurança do Paciente") tem o desenho
de nome de gente, e sem esta lista a peneira o trocava por `[NOME]` no texto
que vai para a issue pública.

Como a base de nomes próprios, este script NÃO roda em produção nem em teste:
a imagem do backend só leva `app/`, e o `CONTEXT.md` mora na raiz do
repositório. O arquivo gerado é congelado e revisado como código. Termo novo
no glossário ou Produto novo no catálogo entra rodando o script de novo.

Duas fontes:

1. **CONTEXT.md**: os verbetes (`**Termo**:`) e os títulos de seção (`## `).
   O complemento entre parênteses que começa por "do", "da" ou "de" vira uma
   segunda forma ("Coordenação (do Comitê)" dá "Coordenação" e "Coordenação
   do Comitê"); qualquer outro parêntese sai.
2. **Catálogo de Produtos da aba Tecnologia**: os nomes que as migrations
   inserem em `tecnologia_produtos`.

Fica só o termo de duas palavras ou mais, em maiúscula inicial e feito de
letras. Palavra sozinha não entra: a peneira nunca troca uma palavra sozinha
pelo desenho, e proteger "Ana" deixaria o prenome de "Ana Paula" no texto.

Uso:

    uv run python scripts/gerar_termos_do_dominio.py
"""

from __future__ import annotations

import pathlib
import re

BACKEND = pathlib.Path(__file__).resolve().parent.parent
CONTEXT_MD = BACKEND.parent.parent / "CONTEXT.md"
MIGRATIONS = BACKEND.parent / "supabase" / "migrations"
DESTINO = BACKEND / "app" / "services" / "dados" / "termos_do_dominio.txt"

_VERBETE = re.compile(r"^\*\*([^*]+)\*\*:", re.MULTILINE)
_TITULO_DE_SECAO = re.compile(r"^## (.+)$", re.MULTILINE)
_COMPLEMENTO = re.compile(r"^(?P<termo>[^(]+?)\s*\((?P<complemento>[^)]*)\)\s*$")
_CONECTIVO_DO_COMPLEMENTO = re.compile(r"^d[oae]s?\s", re.IGNORECASE)
_INSERCAO_DE_PRODUTO = re.compile(r"INSERT INTO tecnologia_produtos\b(?P<bloco>.*?);", re.IGNORECASE | re.DOTALL)
_NOME_DO_PRODUTO = re.compile(r"\(\s*'([^']+)'")
_TERMO_ACEITO = re.compile(r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ-]*(?: [A-Za-zÀ-ÖØ-öø-ÿ-]+)+$")


def formas_do_rotulo(rotulo: str) -> list[str]:
    """O rótulo de um verbete, com e sem o complemento entre parênteses."""
    rotulo = " ".join(rotulo.split())
    partes = _COMPLEMENTO.match(rotulo)
    if partes is None:
        return [rotulo]
    termo, complemento = partes.group("termo"), partes.group("complemento")
    if _CONECTIVO_DO_COMPLEMENTO.match(complemento):
        return [termo, f"{termo} {complemento}"]
    return [termo]


def termos_do_glossario(texto: str) -> set[str]:
    rotulos = _VERBETE.findall(texto) + _TITULO_DE_SECAO.findall(texto)
    return {forma for rotulo in rotulos for forma in formas_do_rotulo(rotulo)}


def produtos_do_catalogo(sqls: list[str]) -> set[str]:
    return {
        nome.strip()
        for sql in sqls
        for insercao in _INSERCAO_DE_PRODUTO.finditer(sql)
        for nome in _NOME_DO_PRODUTO.findall(insercao.group("bloco"))
    }


def termos_do_dominio(glossario: str, sqls: list[str]) -> list[str]:
    candidatos = termos_do_glossario(glossario) | produtos_do_catalogo(sqls)
    return sorted(termo for termo in candidatos if _TERMO_ACEITO.match(termo))


def main() -> None:
    sqls = [caminho.read_text(encoding="utf-8") for caminho in sorted(MIGRATIONS.glob("*.sql"))]
    termos = termos_do_dominio(CONTEXT_MD.read_text(encoding="utf-8"), sqls)
    cabecalho = [
        "# Termos do domínio que a peneira de dado pessoal deixa passar (issue #1813).",
        "# GERADO por scripts/gerar_termos_do_dominio.py. Não edite à mão.",
        "# Fontes: verbetes e seções do CONTEXT.md e o catálogo de Produtos da aba",
        "# Tecnologia (migrations de tecnologia_produtos). Um termo por linha.",
    ]
    DESTINO.write_text("\n".join(cabecalho + termos) + "\n", encoding="utf-8")
    print(f"{len(termos)} termos em {DESTINO}")


if __name__ == "__main__":
    main()
