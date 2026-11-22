"""O aviso de assunto fora do canal na revisão do relato (issue #1848, PRD
#1786; especificação, seções 4.1 e P5, e a saída reduzida do Anexo A; ADR
0097, decisões 6 e 7).

Quando a pessoa abre a revisão (P5), a página pública pede uma leitura do
texto, uma vez. O agente responde só três campos (`parece_fora`, `destino`,
`tem_termo_de_protecao`), e o aviso existe só quando parece fora e não há
termo da regra de proteção. O app ainda confere os termos da regra por conta
própria (`tem_termo_de_protecao`): se o texto diz assédio, ameaça, fraude ou
outro termo da lista, o aviso não aparece, diga o agente o que disser.

O que sai do app é o relato pseudonimizado (ADR 0034), com os nomes dos
membros do Comitê trocados por marcador também, como na triagem do caso. A
leitura gasta uma vaga do mesmo teto diário do agente
(`agente_de_triagem.TETO_DIARIO`). Agente desligado, teto estourado, falha ou
resposta fora do formato: sem aviso, e o envio segue normal. Nada é gravado:
nem o texto, nem a resposta.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from html import escape

from app.config import settings
from app.services.conduta import agente_de_triagem as agente
from app.services.ia_chaves import ClienteDaAnthropic
from app.services.ouvidoria_pseudonimizacao import pseudonimizar
from app.services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

PROMPT = "conduta_aviso_fora_do_canal"
MAX_TOKENS = 200
TEMPO_LIMITE_S = 20.0
DESTINOS = agente.DESTINOS

# A regra de proteção da seção 4.1, pelas raízes das palavras, sem acento.
_TERMOS_DE_PROTECAO = re.compile(r"\b(assedi|discrimin|amea[cç]|violen|retali|fraud|desvi|falsific)")


def tem_termo_de_protecao(relato: str) -> bool:
    """Se o texto diz, com as palavras da regra de proteção, assédio,
    discriminação, ameaça, violência, retaliação, fraude, desvio ou
    falsificação. Conferido no app, sem IA."""
    return bool(_TERMOS_DE_PROTECAO.search(agente._sem_acento(relato or "")))


def montar_mensagem(relato: str, nomes_conhecidos: list[str] = ()) -> str:
    """Só o texto do relato, pseudonimizado. Nada de nome, contato ou campo do
    passo 4."""
    texto = pseudonimizar(agente._trocar_nomes_conhecidos(relato, list(nomes_conhecidos)))
    return f"<relato>\n  <texto>{escape(texto, quote=False)}</texto>\n</relato>"


def destino_do_aviso(saida) -> str | None:
    """O destino do aviso pela saída reduzida do agente, ou nada. Saída fora
    do formato também é nada."""
    if not isinstance(saida, dict):
        return None
    parece_fora, destino, termo = saida.get("parece_fora"), saida.get("destino"), saida.get("tem_termo_de_protecao")
    if parece_fora not in agente.SIM_NAO or termo not in agente.SIM_NAO:
        return None
    if parece_fora == "SIM" and termo == "NAO" and destino in DESTINOS:
        return destino
    return None


def _perguntar_o_aviso(cliente, modelo: str, mensagem: str):
    resposta = cliente.messages.create(
        model=modelo,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": load_prompt(PROMPT), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": mensagem}],
    )
    if resposta.stop_reason in ("refusal", "max_tokens"):
        return None
    bruto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text")
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    try:
        return json.loads(bruto[inicio : fim + 1] if 0 <= inicio < fim else bruto)
    except ValueError:
        return None


def ler_aviso_do_relato(
    cliente, relato: str, mensagem: str, *, modelo: str, reservar: Callable[[], bool]
) -> str | None:
    """Uma leitura do agente, com uma vaga da cota antes. É a mesma função que
    o comando do teste de aceite usa (`scripts/conduta_teste_de_aceite.py
    --aviso`). Nunca levanta."""
    if tem_termo_de_protecao(relato):
        # Com termo da regra, não há aviso: a leitura nem gasta a cota.
        return None
    try:
        if not reservar():
            return None
        return destino_do_aviso(_perguntar_o_aviso(cliente, modelo, mensagem))
    except Exception as exc:
        logger.warning("[CONDUTA] Leitura do aviso na revisão falhou (%s)", type(exc).__name__)
        return None


def versao_do_prompt() -> str:
    achada = re.search(r"^Versão (\d+(?:\.\d+)*)", load_prompt(PROMPT), re.MULTILINE)
    if not achada:
        raise ValueError("o prompt do aviso do Canal não diz a versão")
    return achada.group(1)


def _cliente() -> ClienteDaAnthropic:
    return ClienteDaAnthropic(max_retries=0, timeout=TEMPO_LIMITE_S)


def aviso_na_revisao(supabase, relato: str) -> str | None:
    """O destino do aviso para o texto que a pessoa vai enviar, ou nada.
    Síncrona: a rota chama pelo executor da IA (`chamar_ia_fora_do_loop`)."""
    if not agente.agente_ligado():
        return None
    try:
        mensagem = montar_mensagem(relato, agente._nomes_dos_membros(supabase))
        return ler_aviso_do_relato(
            _cliente(),
            relato,
            mensagem,
            modelo=settings.conduta_agente_modelo,
            reservar=lambda: agente._reservar_chamada(supabase),
        )
    except Exception as exc:
        logger.warning("[CONDUTA] Aviso na revisão sem leitura (%s)", type(exc).__name__)
        return None
