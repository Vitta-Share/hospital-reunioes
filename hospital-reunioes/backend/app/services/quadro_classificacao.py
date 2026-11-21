"""Ação, Rotina e Processo: o tipo de cada linha do quadro da Ata (ADR 0098,
decisão 9; issue #1872).

Fonte única da regra: o parser das três gerações (transcrição, correção e
Ata Guiada), a edição na validação, a trava do envio e o nascimento das
Pendências leem o tipo por aqui. Linha sem tipo (ou com tipo desconhecido)
vale como Ação, o que mantém as Atas antigas como sempre foram.
"""

from __future__ import annotations

import unicodedata

ACAO = "ACAO"
ROTINA = "ROTINA"
PROCESSO = "PROCESSO"
TIPOS = (ACAO, ROTINA, PROCESSO)
FREQUENCIAS = ("SEMANAL", "QUINZENAL", "MENSAL")

# Comparado sem acento e em maiúscula. "NAO INFORMADO" é o que o prompt da
# transcrição manda a IA escrever quando o texto não cita o responsável.
_SEM_NOME = ("", "NULL", "NONE", "N/A", "A DEFINIR", "NAO INFORMADO")


def _chave(valor) -> str:
    if not isinstance(valor, str):
        return ""
    sem_acento = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
    return sem_acento.strip().upper()


def tipo_da_linha(item: dict) -> str:
    """O tipo da linha; sem tipo ou com tipo desconhecido, Ação."""
    tipo = _chave(item.get("tipo"))
    return tipo if tipo in TIPOS else ACAO


def frequencia_da_linha(item: dict) -> str | None:
    """A frequência da Rotina; nos outros tipos, ou se inválida, None."""
    if tipo_da_linha(item) != ROTINA:
        return None
    frequencia = _chave(item.get("frequencia"))
    return frequencia if frequencia in FREQUENCIAS else None


def classificar_quadro(quadro) -> list[dict]:
    """Grava `tipo` e `frequencia` normalizados em cada linha do quadro."""
    linhas = []
    for item in quadro or []:
        if not isinstance(item, dict):
            continue
        linha = dict(item)
        linha["tipo"] = tipo_da_linha(item)
        linha["frequencia"] = frequencia_da_linha(item)
        linhas.append(linha)
    return linhas


def rotinas_incompletas(quadro) -> list[str]:
    """Uma frase por Rotina sem responsável ou sem frequência: o que trava o
    envio da Ata (decisão 88 da #1757)."""
    faltas = []
    for posicao, item in enumerate(quadro or [], start=1):
        if not isinstance(item, dict) or tipo_da_linha(item) != ROTINA:
            continue
        falta = []
        if _chave(str(item.get("responsavel") or "")) in _SEM_NOME:
            falta.append("responsável")
        if frequencia_da_linha(item) is None:
            falta.append("frequência")
        if falta:
            nome = str(item.get("acao") or "").strip() or "sem descrição"
            faltas.append(f'linha {posicao} ("{nome}") sem {" e sem ".join(falta)}')
    return faltas
