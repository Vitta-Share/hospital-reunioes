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

from typing import Any

from app.services.conduta import configuracoes

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


def pagina(supabase) -> dict[str, Any]:
    """A página como ela está hoje."""
    por_chave = configuracoes._todas_as_versoes(supabase, list(BLOCOS))
    blocos = []
    for chave in BLOCOS:
        versoes = por_chave[chave]
        vigente = versoes[0] if versoes else None
        blocos.append(
            {
                "chave": chave,
                "titulo": configuracoes.POR_CHAVE[chave].rotulo,
                "texto": vigente["texto"] if vigente else TEXTO_INICIAL[chave],
                "versao": vigente["versao"] if vigente else None,
                "versao_id": vigente["id"] if vigente else None,
            }
        )
    return {"blocos": blocos}
