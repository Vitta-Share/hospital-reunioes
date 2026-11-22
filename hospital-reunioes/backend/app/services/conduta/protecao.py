"""A página "Como este canal protege você" (issue #1846, especificação seção 4.3).

Cada bloco é um item das Configurações (`configuracoes.ITENS`). A página
mostra a versão vigente de cada um; o bloco que a coordenação ainda não salvou
mostra o texto inicial daqui, o da especificação com as decisões do diretor:
a Direção só lê a conclusão e a ata (decisão 10), a IA guarda o texto até 30
dias e não treina com ele (decisão 38), e a frase sobre a empresa que
desenvolve o sistema fica (decisão 6).

O contato do encarregado de dados não tem texto inicial: o valor é do hospital
e não entra no código. Sem ele salvo, o bloco não aparece.

As versões das configurações nunca se apagam e guardam a data, então a página
de qualquer dia é refeita a partir delas: é esse o arquivo por data.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.services.conduta import configuracoes

SAO_PAULO = ZoneInfo("America/Sao_Paulo")

TEXTO_INICIAL: dict[str, str] = {
    "protecao_abertura": (
        "Este canal é do hospital. Por isso foi construído para que nem o hospital consiga saber quem relatou."
    ),
    "protecao_quem_relata": (
        "Não pedimos login nem guardamos IP. Os dados de origem dos anexos são apagados. "
        "Retaliação é falta grave, e verificamos por 180 dias se ela ocorreu."
    ),
    "protecao_quem_e_citado": (
        "Ninguém é punido só com base em relato anônimo. Você sempre será ouvido antes de qualquer decisão. "
        "Caso não confirmado não deixa marca. O assunto fica restrito ao Comitê."
    ),
    "protecao_quem_le": (
        "Leem os três membros do Comitê. A Direção só lê a conclusão e a ata do caso, nunca o relato. "
        "Não leem TI, DP, chefia nem a empresa que desenvolve o sistema."
    ),
    "protecao_ia": (
        "Usamos inteligência artificial para organizar o relato. Nenhuma decisão é tomada por IA. "
        "O serviço de IA guarda o texto por até 30 dias e não o usa para treinar a IA."
    ),
    "protecao_direcao": "O relato não passa pelo Comitê comum.",
    "protecao_prazos": "Leitura em até 5 dias úteis. Conclusão em 20 ou 30 dias, conforme o caso.",
    "protecao_nao_garante": (
        "O anonimato também depende de você: evite detalhes que só você saberia. "
        "Em equipes pequenas, o próprio fato pode indicar quem relatou."
    ),
}

BLOCOS: tuple[str, ...] = tuple(TEXTO_INICIAL)
ENCARREGADO = "contato_encarregado"

# Tudo o que a página mostra, e que por isso passa pelo filtro de palavras.
CHAVES_DA_PAGINA: tuple[str, ...] = (*BLOCOS, ENCARREGADO)

# A especificação (4.3) proíbe "independente", "100%" e "risco zero" na
# página: prometem mais do que o canal entrega.
_PROIBIDAS = re.compile(r"independent|100\s*%|risco\s+zero", re.IGNORECASE)


def palavra_proibida(texto: str) -> str | None:
    """A palavra proibida que o texto usa, ou None."""
    achada = _PROIBIDAS.search(texto)
    return achada.group(0) if achada else None


def _dia(linha: dict) -> date:
    """O dia da versão em São Paulo (o CI roda em UTC)."""
    return datetime.fromisoformat(linha["criado_em"]).astimezone(SAO_PAULO).date()


def pagina(supabase, em: date | None = None) -> dict[str, Any]:
    """A página como ela está hoje, ou como estava no fim do dia `em`.

    `versoes` são os dias em que a página mudou, do mais novo ao mais antigo:
    cada um é uma versão arquivada, que se abre passando o dia em `em`."""
    por_chave = configuracoes._todas_as_versoes(supabase, list(CHAVES_DA_PAGINA))
    dias = {_dia(linha) for versoes in por_chave.values() for linha in versoes}

    def vigente_em(chave: str) -> dict | None:
        return next((linha for linha in por_chave[chave] if em is None or _dia(linha) <= em), None)

    blocos = []
    for chave in BLOCOS:
        vigente = vigente_em(chave)
        blocos.append(
            {
                "chave": chave,
                "titulo": configuracoes.POR_CHAVE[chave].rotulo,
                "texto": vigente["texto"] if vigente else TEXTO_INICIAL[chave],
                "versao": vigente["versao"] if vigente else None,
                "versao_id": vigente["id"] if vigente else None,
            }
        )
    encarregado = vigente_em(ENCARREGADO)
    return {
        "em": em.isoformat() if em else None,
        "blocos": blocos,
        "encarregado": (
            {"texto": encarregado["texto"], "versao": encarregado["versao"], "versao_id": encarregado["id"]}
            if encarregado
            else None
        ),
        "versoes": [dia.isoformat() for dia in sorted(dias, reverse=True)],
    }
