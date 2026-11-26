"""O que o chat da aba Tecnologia herdou do Assistente de entrada (PRD #726,
ADR 0056).

O Assistente de entrada, que montava o rascunho do formulario a mao, saiu do
codigo com a ADR 0077 (issue #1386), e o chat da aba saiu na issue #2279
(ADR 0113, decisao 7). Ficaram aqui a cerca do kit no prompt, que o Envio aos
desenvolvedores usa, e a tabela dos tipos de anexo, que o bug do Assistente do
app usa.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.services.transcricao_extractor import CONTENT_TYPE_BY_EXT, MAX_BYTES_BINARY, MAX_BYTES_TEXT

logger = logging.getLogger(__name__)

# A cerca do kit (ADR 0056). O kit e texto curado pela Vitta, mas entra cercado
# do mesmo jeito: a moldura e o que deixa dito no prompt onde acaba a instrucao
# e comeca o material de consulta.
MARCA_INICIO_KIT = "--- início do kit ---"
MARCA_FIM_KIT = "--- fim do kit ---"

# A primeira linha de dentro da cerca e do backend, e nao do kit: e ela que faz
# `recuar_continuacao` empurrar TODAS as linhas do material para a direita. Com
# a primeira coluna sempre nossa, nenhuma linha escrita la dentro consegue
# passar por marca de fim.
TITULO_DO_KIT = "Material escrito pela Vitta sobre a plataforma:"


# ─── O print de tela (issue #730) ────────────────────────────────────────────
#
# A primeira chamada MULTIMODAL do app (ADR 0056, decisao 4).

# As imagens que o assistente le, e o TIPO de cada uma.
#
# A tabela mora aqui, e nao na rota, porque quem precisa do tipo e quem monta o
# payload: a rota so peneira o nome do arquivo, contra esta mesma tabela. Duas
# listas para a mesma regra divergiriam calado (o 422 recusando o que o payload
# saberia rotular, ou o contrario).
#
# O tipo vem da EXTENSAO, nunca do `content-type` que o cliente declarou, pela
# mesma razao do Anexo da Manifestacao (ADR 0034): o cabecalho e escrito do lado
# de la e pode mentir.
#
# Desde a issue #1520 a tabela e a de TUDO que entra pelo botao de anexo do
# chat (`TIPOS_DE_ANEXO`, logo abaixo), e esta e a parte dela que e imagem.

# 3,75 MB. A API da Anthropic recusa imagem acima de 5 MB, e quem ela mede e o
# `data` em base64, que cresce 4/3: o arquivo maior que 3,75 MB chegaria la, a
# leitura falharia e a frase de "tente de novo" mandaria o mesmo print para
# falhar de novo (revisao do PR #1313). Print de tela cheia em PNG num monitor
# grande nao passa de dois; o que passa disto e foto de celular de um monitor.
LIMITE_DA_IMAGEM_EM_BASE64 = 5 * 1024 * 1024
LIMITE_DA_IMAGEM = LIMITE_DA_IMAGEM_EM_BASE64 * 3 // 4


# ─── O que entra pelo botao de anexo (issue #1520, ADR 0069) ─────────────────
#
# UMA tabela so decide o tipo, o `content-type` e o teto de cada extensao: o
# servico de anexos e o print do bug do Assistente do app. O espelho da tela
# saiu com o chat da aba (issue #2279). Duas listas para a mesma regra
# divergiriam calado.
#
# Os tetos do documento sao os do extrator da Ata Guiada, que e quem le o
# arquivo: 5 MB para o que e texto puro, 15 MB para o que pede parser.


@dataclass(frozen=True)
class TipoDeAnexo:
    classe: Literal["imagem", "documento"]
    content_type: str
    teto_bytes: int


TIPOS_DE_ANEXO: dict[str, TipoDeAnexo] = {
    ".png": TipoDeAnexo("imagem", "image/png", LIMITE_DA_IMAGEM),
    ".jpg": TipoDeAnexo("imagem", "image/jpeg", LIMITE_DA_IMAGEM),
    ".jpeg": TipoDeAnexo("imagem", "image/jpeg", LIMITE_DA_IMAGEM),
    ".webp": TipoDeAnexo("imagem", "image/webp", LIMITE_DA_IMAGEM),
    ".md": TipoDeAnexo("documento", CONTENT_TYPE_BY_EXT[".md"], MAX_BYTES_TEXT),
    ".txt": TipoDeAnexo("documento", CONTENT_TYPE_BY_EXT[".txt"], MAX_BYTES_TEXT),
    ".pdf": TipoDeAnexo("documento", CONTENT_TYPE_BY_EXT[".pdf"], MAX_BYTES_BINARY),
    ".docx": TipoDeAnexo("documento", CONTENT_TYPE_BY_EXT[".docx"], MAX_BYTES_BINARY),
    # A planilha conta como documento (issue #1521): o agente le o texto dela.
    ".csv": TipoDeAnexo("documento", CONTENT_TYPE_BY_EXT[".csv"], MAX_BYTES_TEXT),
    ".xlsx": TipoDeAnexo("documento", CONTENT_TYPE_BY_EXT[".xlsx"], MAX_BYTES_BINARY),
}

TIPOS_DE_IMAGEM: dict[str, str] = {ext: t.content_type for ext, t in TIPOS_DE_ANEXO.items() if t.classe == "imagem"}
TIPOS_DE_DOCUMENTO: dict[str, str] = {
    ext: t.content_type for ext, t in TIPOS_DE_ANEXO.items() if t.classe == "documento"
}


def _ou(itens: list[str]) -> str:
    return f"{', '.join(itens[:-1])} ou {itens[-1]}" if len(itens) > 1 else "".join(itens)


def _em_mb(teto: int) -> str:
    mb = teto / (1024 * 1024)
    return f"{mb:.0f}" if mb == int(mb) else f"{mb:.2f}".replace(".", ",")


# A recusa do tipo que nao entra: diz quais entram, da tabela, para a pessoa
# saber o que fazer com o arquivo que tem na mao.
MOTIVO_TIPO_FORA_DA_LISTA = (
    "Esse tipo de arquivo não entra na conversa. "
    f"Entram print ({_ou(list(TIPOS_DE_IMAGEM))}) e documento ({_ou(list(TIPOS_DE_DOCUMENTO))})."
)


def motivo_documento_grande(extensao: str) -> str:
    """A recusa do documento acima do teto do tipo dele, com o numero."""
    teto = TIPOS_DE_ANEXO[extensao].teto_bytes
    return (
        f"O arquivo {extensao} passou do limite de {_em_mb(teto)} MB. "
        "Divida o documento em partes menores e mande uma de cada vez."
    )


_LIMITE_DA_IMAGEM_EM_MB = f"{LIMITE_DA_IMAGEM / (1024 * 1024):.2f}".replace(".", ",")

MOTIVO_IMAGEM_GRANDE = (
    f"O print passou do limite de {_LIMITE_DA_IMAGEM_EM_MB} MB. "
    "Anexe uma imagem menor, ou escreva o que aparece na tela."
)
