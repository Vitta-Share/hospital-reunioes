"""Protótipo das telas públicas do Canal de Conduta (issue #1817, PRD #1786).

O protótipo é um HTML só, sem backend, que a Diretoria navega no celular para
aprovar o layout (#1818) antes de qualquer tela pública ser construída. Cada
teste é um critério de aceite da issue, lido do arquivo que vai para a Vercel.
"""

from __future__ import annotations

import itertools
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
    def __init__(self, tag: str, attrs: dict, pai: No | None):
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
    for atual, seguinte in itertools.pairwise(PASSOS_DO_RELATO):
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
        barras = [n for n in todas[nome].nos() if n.attrs.get("role") == "progressbar"]
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


def css() -> str:
    """O CSS da página, sem os comentários."""
    bruto = "\n".join(re.findall(r"<style>(.*?)</style>", fonte(), re.DOTALL))
    return re.sub(r"/\*.*?\*/", "", bruto, flags=re.DOTALL)


def script() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", fonte(), re.DOTALL))


def textos_visiveis(raiz: No) -> list[str]:
    """Todo texto que a pessoa pode ler: nós de texto, alt, placeholder,
    aria-label, o título da aba e as strings que o script escreve na tela."""
    textos = [raiz.texto()]
    for n in raiz.nos():
        for attr in ("alt", "placeholder", "aria-label", "title"):
            if n.attrs.get(attr):
                textos.append(n.attrs[attr])
    textos += re.findall(r'"((?:[^"\\]|\\.)*)"', script())
    textos.append(re.search(r"<title>(.*?)</title>", fonte()).group(1))
    return textos


# Critério 2: tudo funciona a 375 px de largura.


def test_a_pagina_cabe_em_375_px():
    assert (
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        in fonte()
    )
    # Nenhuma largura fixa maior que a tela do celular.
    for prop, valor in re.findall(
        r"(?<![\w-])((?:min-)?width|flex-basis)\s*:\s*(\d+)px", css()
    ):
        assert int(valor) <= 375, f"{prop}: {valor}px não cabe em 375 px"
    # Texto longo (código, protocolo, nome de arquivo) quebra em vez de vazar.
    assert re.search(r"body\s*\{[^}]*overflow-wrap\s*:\s*anywhere", css())
    assert not re.search(r"white-space\s*:\s*nowrap", css())


# Critério 3: a entrada mostra título, AGIR CERTO, os três selos e os blocos.


def test_a_entrada_mostra_titulo_proposito_selos_e_os_dois_blocos():
    p0 = telas(arvore())["P0"]
    titulos = [n.texto() for n in p0.nos() if n.tag in ("h1", "h2")]
    assert titulos[0] == "Canal de Conduta"
    # O h2 sai em caixa alta pela regra do título: AGIR CERTO.
    assert "Agir certo" in titulos
    assert "É um dos nossos propósitos. Este canal existe para isso." in p0.texto()
    [selos] = [n for n in p0.nos() if "selos" in n.attrs.get("class", "").split()]
    assert [li.texto() for li in selos.nos() if li.tag == "li"] == [
        "Sem login",
        "Sem registro de IP",
        "Só o Comitê lê",
    ]
    blocos = {n.attrs["data-bloco"]: n for n in p0.nos() if "data-bloco" in n.attrs}
    e_aqui = [li.texto() for li in blocos["e-aqui"].nos() if li.tag == "li"]
    assert blocos["e-aqui"].texto().startswith("É aqui")
    assert e_aqui == [
        "Assédio moral ou sexual",
        "Discriminação",
        "Violência",
        "Furto, desvio ou fraude",
        "Comissão ou propina",
        "Registro falso",
        "Acesso indevido a dados",
        "Retaliação",
    ]
    nao = blocos["nao-e-aqui"]
    assert nao.texto().startswith("Não é aqui")
    assert destinos(nao) == {"dp", "ouvidoria"}
    assert "Salário, contracheque, escala, férias, benefícios" in nao.texto()
    assert "Sou paciente ou acompanhante" in nao.texto()


# Critério 4: sem foto, sem ilustração decorativa, sem as palavras proibidas.

PALAVRAS_PROIBIDAS = ["independente", "100%", "risco zero"]


def test_nenhuma_tela_usa_foto_ilustracao_nem_palavra_proibida():
    raiz = arvore()
    imagens = [n for n in raiz.nos() if n.tag in ("img", "picture", "video", "canvas")]
    # A única imagem é a logo.
    assert [n.attrs.get("src") for n in imagens] == ["logo-hsm.png"]
    # Ícone simples é permitido; desenho grande não.
    for svg in (n for n in raiz.nos() if n.tag == "svg"):
        assert "icone" in svg.attrs.get("class", "").split()
    largura = re.search(r"\.icone\s*\{[^}]*width:\s*(\d+)px", css())
    assert largura and int(largura.group(1)) <= 24
    assert not re.search(r"background(-image)?\s*:[^;]*url\(", css())
    for texto in textos_visiveis(raiz):
        for palavra in PALAVRAS_PROIBIDAS:
            assert palavra not in texto.lower(), f"{palavra!r} em: {texto[:80]}"


def test_o_prototipo_nao_chama_backend_nem_carrega_nada_de_fora():
    for chamada in ("fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket"):
        assert chamada not in script()
    for n in arvore().nos():
        for attr in ("src", "href", "action"):
            valor = n.attrs.get(attr) or ""
            assert not re.match(r"(https?:)?//", valor), f"{n.tag} {attr}={valor}"
    assert not re.search(r"url\(\s*['\"]?(https?:)?//", css())


# Critério 5: os textos seguem as decisões 4, 10 e 38 do diretor.


def test_porta_do_dp_so_mostra_o_contato_sem_envio_por_email():
    """Decisão 4: sem e-mail, a página só mostra o contato do DP."""
    raiz = arvore()
    dp = telas(raiz)["dp"]
    assert [n for n in dp.nos() if "data-contato-dp" in n.attrs]
    assert "Este canal não envia nada ao DP e não abre protocolo." in dp.texto()
    # Nenhum caminho de envio ao DP: nem o botão da especificação, nem campo
    # de contato para o DP ligar de volta.
    tudo = " ".join(textos_visiveis(raiz)).lower()
    assert "encaminhar ao dp" not in tudo
    assert "enviado ao departamento pessoal" not in tudo
    assert not [n for n in raiz.nos() if n.attrs.get("type") in ("email", "tel")]
    # A sugestão da revisão leva à porta do DP, e não a um envio.
    [sugestao] = [
        n for n in telas(raiz)["P5"].nos() if n.attrs.get("data-sugestao") == "dp"
    ]
    assert destinos(sugestao) == {"dp"}


def test_pagina_de_protecao_diz_que_a_direcao_so_le_a_conclusao_e_a_ata():
    """Decisão 10."""
    protecao = telas(arvore())["protecao"]
    [quem_le] = [n for n in protecao.nos() if "data-quem-le" in n.attrs]
    texto = quem_le.texto()
    assert "Leem os três membros do Comitê." in texto
    assert "A Direção só lê a conclusão e a ata do caso, nunca o relato." in texto
    assert "Direção" not in texto.split("Não leem", 1)[1]


def test_aviso_de_ia_diz_ate_30_dias_e_sem_treino():
    """Decisão 38: a página diz que a IA guarda até 30 dias, sem treinar."""
    todas = telas(arvore())
    frase = (
        "O serviço de IA guarda o texto por até 30 dias e não o usa para treinar a IA."
    )
    for nome in ("P1", "protecao"):
        avisos = [n for n in todas[nome].nos() if "data-aviso-ia" in n.attrs]
        assert avisos, f"{nome} sem o aviso de IA"
        assert frase in avisos[0].texto()
        assert "Nenhuma decisão é tomada por IA." in avisos[0].texto()


# Critério 6: sem travessão, e caixa alta só em título, botão e aba.

SIGLAS = {"DP", "IP", "IA", "TI", "PDF", "NSP", "CIPA", "RH"}
CAIXA_ALTA_PERMITIDA = {"h1", "h2", "h3", "button", '[role="tab"]'}


def test_nenhum_texto_tem_travessao_nem_meia_risca():
    assert "—" not in fonte()
    assert "–" not in fonte()


def test_caixa_alta_so_aparece_em_titulo_botao_e_aba():
    # A exibição vira caixa alta só nesses elementos (ADR 0080).
    for seletores, corpo in re.findall(r"([^{}]+)\{([^}]*)\}", css()):
        if re.search(r"text-transform\s*:\s*uppercase", corpo):
            alvos = {s.strip() for s in seletores.split(",")}
            assert alvos <= CAIXA_ALTA_PERMITIDA, f"caixa alta em {alvos}"
    for n in arvore().nos():
        assert "text-transform" not in (n.attrs.get("style") or "")
    assert "textTransform" not in script()
    # O texto da fonte é escrito em caixa de frase: palavra toda em maiúscula
    # só se for sigla.
    for texto in textos_visiveis(arvore()):
        texto = re.sub(r"\b[a-z]{2}-[A-Z]{2}\b", "", texto)  # locale, ex.: pt-BR
        for palavra in re.findall(r"[A-Za-zÀ-ÿ]+", texto):
            if len(palavra) >= 2 and palavra.isupper():
                assert palavra in SIGLAS, (
                    f"caixa alta à mão: {palavra!r} em {texto[:60]}"
                )
