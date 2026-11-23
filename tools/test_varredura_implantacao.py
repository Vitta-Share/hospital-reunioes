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


def card(numero, titulo, *, raiz=DEMANDA_DO_CANAL, bloqueia=(), espera=(), labels=("ready-for-human",), pr=None, corpo=""):
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
