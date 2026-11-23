"""A varredura dos cards abertos de hoje (issue #2214, ADR 0111, decisões 2 e 12).

Lista os cards `ready-for-human` abertos ligados a uma Demanda que cabem na
regra (vêm depois do código e não seguram nenhuma fatia), põe a label
`implantacao` neles e devolve a lista num comentário, sem mandar nenhum ao app.
Os cards de exemplo são os do Canal de Conduta, como estavam em 22/11/2026.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("varredura_implantacao", RAIZ / "tools" / "varredura_implantacao.py")
varredura = importlib.util.module_from_spec(_spec)
sys.modules["varredura_implantacao"] = varredura
_spec.loader.exec_module(varredura)

DEMANDA_DO_CANAL = {
    "numero": 1786,
    "titulo": "Canal de Conduta",
    "labels": {"type:feature", "ready-for-agent", "origem:diretor", "validado:diretor"},
    "corpo": "Quem trabalha no hospital relata conduta grave.",
}


def card(
    numero, titulo, *, raiz=DEMANDA_DO_CANAL, bloqueia=(), espera=(), labels=("ready-for-human",), pr=None, corpo=""
):
    return {
        "numero": numero,
        "titulo": titulo,
        "labels": set(labels),
        "corpo": corpo or (f"Pai: #{raiz['numero']}" if raiz else ""),
        "raiz": raiz,
        "bloqueia": list(bloqueia),
        "espera": list(espera),
        "pr_aberto": pr,
    }


def fatia(numero, titulo, *labels):
    return {"numero": numero, "titulo": titulo, "labels": set(labels or ("ready-for-agent",))}


TESTE = card(
    1853,
    "Canal de Conduta: teste de acesso e de anonimato por quem não desenvolveu",
    bloqueia=[fatia(1854, "Canal de Conduta: abertura do canal", "ready-for-human")],
)
ABERTURA = card(
    1854,
    "Canal de Conduta: abertura do canal",
    bloqueia=[fatia(1855, "Canal de Conduta: números para a Direção")],
    espera=[fatia(1853, TESTE["titulo"], "ready-for-human")],
)
BACKUP = card(2135, "Canal de Conduta: backup cifrado com teste de restauração e procedimento de vazamento")
CANAL_DE_HOJE = [TESTE, ABERTURA, BACKUP]


def por_numero(vereditos):
    return {v["numero"]: v for v in vereditos}


def test_candidato_vem_com_o_motivo_e_card_que_segura_fatia_aberta_fica_de_fora() -> None:
    vereditos = por_numero(varredura.classificar(CANAL_DE_HOJE))

    assert vereditos[2135]["candidato"] is True
    assert "#1786" in vereditos[2135]["motivo"]
    # Quem espera o teste é outro card humano, não uma fatia: o teste continua candidato.
    assert vereditos[1853]["candidato"] is True
    # A abertura segura a fatia #1855, que está aberta: não é implantação.
    assert vereditos[1854]["candidato"] is False
    assert "#1855" in vereditos[1854]["motivo"]


def test_card_sem_demanda_ou_com_pr_aberto_fica_de_fora() -> None:
    bug_raiz = card(1904, "Ata assinada por todos continua aguardando assinatura", raiz=None)
    codigo = card(1838, "Canal de Conduta: papel original, guarda, congelar e eliminação", pr=2170)
    comunicacao = card(2202, "Texto do ato", corpo="<!-- demanda-vitta: nenhuma, Card de comunicação -->")
    ferramenta = card(
        900, "Configurar o runner", raiz={"numero": 899, "titulo": "x", "labels": {"area:infra"}, "corpo": ""}
    )

    vereditos = por_numero(varredura.classificar([bug_raiz, codigo, comunicacao, ferramenta]))

    assert not any(v["candidato"] for v in vereditos.values())
    assert "#2170" in vereditos[1838]["motivo"]
    assert "#899" in vereditos[900]["motivo"]


class GitHubFalso:
    def __init__(self) -> None:
        self.chamadas: list[list[str]] = []

    def __call__(self, args: list[str]) -> str:
        self.chamadas.append(list(args))
        return ""


def test_aplicar_poe_a_label_so_nos_candidatos() -> None:
    gh = GitHubFalso()

    varredura.aplicar(varredura.classificar(CANAL_DE_HOJE), comentar=2214, rodar=gh)

    marcados = sorted(int(c[3]) for c in gh.chamadas if c[:3] == ["gh", "issue", "edit"] and "implantacao" in c)
    assert marcados == [1853, 2135]


def test_o_comentario_traz_a_lista_e_a_espera_da_abertura_pelo_teste() -> None:
    gh = GitHubFalso()

    varredura.aplicar(varredura.classificar(CANAL_DE_HOJE), comentar=2214, rodar=gh)

    [comentario] = [c for c in gh.chamadas if c[:4] == ["gh", "issue", "comment", "2214"]]
    texto = Path(comentario[comentario.index("--body-file") + 1]).read_text(encoding="utf-8")
    ganharam, ficaram = texto.split("**Ficaram de fora**")
    assert "#1853 " in ganharam and "#2135 " in ganharam
    assert "#1854 " in ficaram and "#1855" in ficaram
    [abertura] = [linha for linha in texto.splitlines() if linha.startswith("- #1854 ")]
    assert "Espera #1853." in abertura
    [teste] = [linha for linha in texto.splitlines() if linha.startswith("- #1853 ")]
    assert "#1854 espera este." in teste
    assert "tire o bloqueio nativo" in ficaram


def issue_rest(numero, titulo, *labels, corpo="", estado="open", pai=None):
    return {
        "number": numero,
        "title": titulo,
        "state": estado,
        "body": corpo,
        "labels": [{"name": n} for n in labels],
        "parent_issue_url": f"https://api.github.com/repos/o/r/issues/{pai}" if pai else None,
    }


def test_a_coleta_le_o_pai_as_dependencias_abertas_e_o_pr_que_fecha() -> None:
    respostas = {
        "repos/o/r/issues?state=open&labels=ready-for-human&per_page=100": [
            issue_rest(1963, "Limpeza", "ready-for-human", corpo="## Pai\n\n`#1913`: a Demanda."),
            issue_rest(1853, "Teste", "ready-for-human", pai=1786),
        ],
        "repos/o/r/issues/1913": issue_rest(1913, "Apagar testes", "origem:diretor"),
        "repos/o/r/issues/1786": DEMANDA_REST,
        "repos/o/r/issues/1963/dependencies/blocking": [],
        "repos/o/r/issues/1963/dependencies/blocked_by": [issue_rest(1962, "Script", "ready-for-agent")],
        "repos/o/r/issues/1853/dependencies/blocking": [issue_rest(1854, "Abertura", "ready-for-human")],
        "repos/o/r/issues/1853/dependencies/blocked_by": [
            issue_rest(1838, "Papel", "ready-for-human"),
            issue_rest(1836, "Afastamento", estado="closed"),
        ],
        "repos/o/r/pulls?state=open&per_page=100": [
            {"number": 2170, "body": "Closes #1838"},
            {"number": 9, "body": "Fixes #1963"},
        ],
    }

    cards = {c["numero"]: c for c in varredura.coletar("o/r", api=respostas.__getitem__)}

    assert cards[1963]["raiz"]["numero"] == 1913
    assert cards[1963]["pr_aberto"] == 9
    assert cards[1853]["raiz"]["numero"] == 1786
    assert [i["numero"] for i in cards[1853]["espera"]] == [1838]
    assert [i["numero"] for i in cards[1853]["bloqueia"]] == [1854]
    assert cards[1853]["pr_aberto"] is None


DEMANDA_REST = issue_rest(1786, "Canal de Conduta", "type:feature", "origem:diretor")


def test_a_varredura_nao_cria_pedido_no_app() -> None:
    gh = GitHubFalso()

    varredura.aplicar(varredura.classificar(CANAL_DE_HOJE), comentar=2214, rodar=gh)

    # Só duas escritas existem: a label no card e o comentário da lista. Nada
    # vai à ponte do app (o Pedido nasce pelo "Mandar ao hospital", decisão 4).
    assert gh.chamadas
    for chamada in gh.chamadas:
        assert chamada[:3] in (["gh", "issue", "edit"], ["gh", "issue", "comment"]), chamada
        assert not any("http" in parte or "pedido" in parte.lower() for parte in chamada), chamada
