"""Os anexos do relato do Canal de Conduta (issue #1844; especificação, seção
4, passo P4; ADR 0097, decisão 2).

Quem relata anexa imagem, PDF ou áudio. Antes de gravar, o arquivo é regravado
sem os dados de origem: a imagem sem EXIF, GPS, XMP e perfil de cor; o PDF sem
as informações de documento e sem XMP; o áudio sem etiquetas. O tipo é
reconhecido pelo conteúdo, não pelo nome nem pelo tipo que o navegador diz.
Formato que o canal não sabe limpar é recusado, e o relato segue sem ele.

O arquivo limpo vai cifrado ao bucket privado do Canal (migration 175) e só
sai pela rota do Comitê, que passa pelo portão e grava a abertura na trilha.
O nome original do arquivo não é guardado em lugar nenhum.

`guardar` é a entrada única: o relato (P4) e o complemento do acompanhamento
gravam o anexo pelo mesmo caminho.
"""

from __future__ import annotations

import io
import logging
import uuid
import warnings
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps
from postgrest.exceptions import APIError

from app.services import storage
from app.services.conduta import cifra, trilha
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc

logger = logging.getLogger(__name__)

TABELA = "conduta_relato_anexos"
# O bucket privado do Canal (migration 175), sem policy e sem URL.
BUCKET = "conduta-arquivos"

_MB = 1024 * 1024
LIMITES = {"imagem": 20 * _MB, "pdf": 20 * _MB, "audio": 50 * _MB}
LIMITE_DO_ARQUIVO = max(LIMITES.values())
# Somando o relato e os complementos do mesmo caso.
ANEXOS_POR_CASO = 10

RECUSA_DO_FORMATO = (
    "Este arquivo não pode ser anexado. O canal aceita foto (JPG, PNG ou WEBP), PDF e áudio (MP3, M4A, OGG ou WAV)."
)
RECUSA_ILEGIVEL = "Não deu para abrir este arquivo. Confira se ele não está corrompido e tente de novo."
ROTULOS = {"imagem": "uma imagem", "pdf": "um PDF", "audio": "um áudio"}


class AnexoRecusadoError(Exception):
    """O anexo não entra. `status` vai para a resposta, e a mensagem diz o
    motivo numa linha, sem nada do arquivo."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


@dataclass(frozen=True)
class Limpo:
    tipo: str
    content_type: str
    conteudo: bytes


# ── Imagem ──────────────────────────────────────────────────────────────────

_IMAGENS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def _formato_da_imagem(dados: bytes) -> str | None:
    if dados.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "WEBP"
    return None


def _limpar_imagem(dados: bytes, formato: str) -> bytes:
    """Só os pixels, numa imagem nova: o que vinha junto (EXIF, GPS, XMP,
    perfil de cor, comentário) fica para trás. A rotação do EXIF é aplicada
    antes, para a foto não ficar deitada."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(dados), formats=[formato]) as aberta:
            aberta.load()
            imagem = ImageOps.exif_transpose(aberta)
    transparente = imagem.mode in ("RGBA", "LA", "PA") or "transparency" in imagem.info
    modo = "RGBA" if transparente and formato != "JPEG" else "RGB"
    pixels = imagem.convert(modo)
    limpa = Image.frombytes(modo, pixels.size, pixels.tobytes())
    saida = io.BytesIO()
    opcoes = {"quality": 90} if formato in ("JPEG", "WEBP") else {}
    limpa.save(saida, format=formato, **opcoes)
    return saida.getvalue()


# ── A entrada ───────────────────────────────────────────────────────────────


def limpar(dados: bytes) -> Limpo:
    """O arquivo regravado sem os dados de origem, reconhecido pelo conteúdo."""
    formato = _formato_da_imagem(dados)
    if formato is None:
        raise AnexoRecusadoError(415, RECUSA_DO_FORMATO)
    if len(dados) > LIMITES["imagem"]:
        raise AnexoRecusadoError(413, "A imagem passa de 20 MB.")
    try:
        conteudo = _limpar_imagem(dados, formato)
    except Exception as erro:  # noqa: BLE001 - arquivo de fora: qualquer falha do leitor é recusa
        raise AnexoRecusadoError(422, RECUSA_ILEGIVEL) from erro
    return Limpo("imagem", _IMAGENS[formato], conteudo)


def guardar(supabase, caso_id: str, dados: bytes, origem: str = "relato") -> dict[str, Any]:
    """Limpa, cifra e guarda o anexo no caso. A entrada única do relato e do
    complemento. Recusa antes de gravar qualquer coisa."""
    limpo = limpar(dados)
    cifrado = cifra.cifrar_arquivo(limpo.conteudo)
    caminho = f"anexos/{uuid.uuid4().hex}"
    if not storage.upload_private(supabase, BUCKET, caminho, cifrado):
        raise AnexoRecusadoError(503, "O anexo não foi guardado agora. Tente de novo em alguns minutos.")
    linha = {
        "caso_id": caso_id,
        "origem": origem,
        "tipo": limpo.tipo,
        "content_type": limpo.content_type,
        "tamanho_bytes": len(limpo.conteudo),
        "storage_path": caminho,
        "codigo_integridade": trilha.codigo_de_integridade(limpo.conteudo),
        "enviado_em": agora_utc().isoformat(),
    }
    try:
        gravada = supabase.table(TABELA).insert(linha).execute().data[0]
    except APIError:
        if not storage.delete_file(supabase, BUCKET, caminho):
            logger.error("Anexo de relato órfão no bucket do Canal: %s", caminho)
        raise
    return {"id": gravada["id"], "tipo": limpo.tipo}
