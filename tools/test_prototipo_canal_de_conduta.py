"""Protótipo das telas públicas do Canal de Conduta (issue #1817, PRD #1786).

O protótipo é um HTML só, sem backend, que a Diretoria navega no celular para
aprovar o layout (#1818) antes de qualquer tela pública ser construída. Cada
teste é um critério de aceite da issue, lido do arquivo que vai para a Vercel.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

ARQUIVO = (
    Path(__file__).resolve().parent.parent
    / "docs/comunicacao/conduta/1817-prototipo-telas-publicas/index.html"
)

PASSOS = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]
PASSOS_DO_RELATO = ["P1", "P2", "P3", "P4", "P5", "P6"]
VAZIOS = {"meta", "link", "input", "br", "img", "hr", "source", "path", "circle"}


class No:
    def __init__(self, tag: str, attrs: dict, pai: "No | None"):
        self.tag = tag
        self.attrs = attrs
        self.pai = pai
        self.filhos: list[No | str] = []

    def nos(self):
        yield self
        for f in self.filhos:
            if isinstance(f, No):
                yield from f.nos()

    def texto(self) -> str:
        partes = []
        for f in self.filhos:
            partes.append(f if isinstance(f, str) else f.texto())
        return " ".join(" ".join(partes).split())

    def dentro_de(self, tag: str) -> bool:
        atual = self.pai
        while atual:
            if atual.tag == tag:
                return True
            atual = atual.pai
        return False


class _Arvore(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = No("#doc", {}, None)
        self.atual = self.raiz

    def handle_starttag(self, tag, attrs):
        no = No(tag, dict(attrs), self.atual)
        self.atual.filhos.append(no)
        if tag not in VAZIOS:
            self.atual = no

    def handle_startendtag(self, tag, attrs):
        self.atual.filhos.append(No(tag, dict(attrs), self.atual))

    def handle_endtag(self, tag):
        atual = self.atual
        while atual is not None and atual.tag != tag:
            atual = atual.pai
        if atual is not None and atual.pai is not None:
            self.atual = atual.pai

    def handle_data(self, data):
        if self.atual.tag not in ("script", "style"):
            self.atual.filhos.append(data)


def fonte() -> str:
    return ARQUIVO.read_text(encoding="utf-8")


def arvore() -> No:
    p = _Arvore()
    p.feed(fonte())
    return p.raiz


def telas(raiz: No) -> dict[str, No]:
    return {n.attrs["data-tela"]: n for n in raiz.nos() if "data-tela" in n.attrs}


def destinos(tela: No) -> set[str]:
    return {n.attrs["data-ir"] for n in tela.nos() if "data-ir" in n.attrs}


# Critério 1: P0 a P7 e a página de proteção navegam do início ao fim, com
# barra de progresso e Voltar sem perder o que foi digitado.


def test_todos_os_passos_e_a_protecao_se_alcancam_a_partir_da_entrada():
    todas = telas(arvore())
    for nome in [*PASSOS, "protecao"]:
        assert nome in todas, f"falta a tela {nome}"
    vistos, fila = {"P0"}, ["P0"]
    while fila:
        for d in destinos(todas[fila.pop()]):
            assert d in todas, f"botão leva a uma tela que não existe: {d}"
            if d not in vistos:
                vistos.add(d)
                fila.append(d)
    assert set(PASSOS) | {"protecao"} <= vistos
    # O relato anda em ordem: cada passo leva ao seguinte.
    for atual, seguinte in zip(PASSOS_DO_RELATO, PASSOS_DO_RELATO[1:]):
        assert seguinte in destinos(todas[atual]), f"{atual} não leva a {seguinte}"


def test_so_a_entrada_abre_visivel_e_as_outras_telas_comecam_escondidas():
    todas = telas(arvore())
    assert "hidden" not in todas["P0"].attrs
    for nome, tela in todas.items():
        if nome != "P0":
            assert "hidden" in tela.attrs, f"{nome} abre visível junto da entrada"


def test_todo_passo_e_a_protecao_tem_voltar():
    todas = telas(arvore())
    for nome in [*PASSOS[1:], "protecao"]:
        voltar = [
            n
            for n in todas[nome].nos()
            if n.tag == "button" and "data-voltar" in n.attrs
        ]
        assert voltar, f"{nome} sem botão Voltar"
        assert voltar[0].texto().startswith("Voltar")


def test_os_passos_do_relato_tem_barra_de_progresso_que_avanca():
    todas = telas(arvore())
    valores = []
    for nome in PASSOS_DO_RELATO:
        barras = [
            n for n in todas[nome].nos() if n.attrs.get("role") == "progressbar"
        ]
        assert len(barras) == 1, f"{nome} sem barra de progresso"
        barra = barras[0]
        assert barra.attrs["aria-valuemax"] == str(len(PASSOS_DO_RELATO))
        valores.append(int(barra.attrs["aria-valuenow"]))
    assert valores == list(range(1, len(PASSOS_DO_RELATO) + 1))


def test_voltar_nao_apaga_o_que_foi_digitado():
    """Os campos moram num formulário só, que nunca é refeito.

    O script só esconde e mostra telas: não troca o HTML do formulário, não
    chama reset() e não escreve valor em campo. É isso que mantém o texto ao
    voltar (a navegação real foi conferida no navegador, no PR).
    """
    raiz = arvore()
    campos = [n for n in raiz.nos() if n.tag in ("input", "textarea", "select")]
    assert campos
    for c in campos:
        assert c.dentro_de("form"), f"campo fora do formulário: {c.attrs}"
    formularios = [n for n in raiz.nos() if n.tag == "form"]
    assert len(formularios) == 1
    script = "\n".join(re.findall(r"<script>(.*?)</script>", fonte(), re.DOTALL))
    assert script
    assert not re.search(r"\.reset\s*\(", script)
    assert not re.search(r"\.(value|checked)\s*=(?!=)", script)
    assert not re.search(r"(form|relato|campo)\w*\.(inner|outer)HTML", script)
    assert not re.search(r"\.remove\s*\(\s*\)", script)
