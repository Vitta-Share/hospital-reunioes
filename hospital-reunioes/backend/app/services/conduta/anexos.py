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
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

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


# ── PDF ─────────────────────────────────────────────────────────────────────

# O que carrega origem num PDF fora do /Info: o XMP (no documento, na página
# ou numa imagem dentro dela) e os dados privados do programa que o gerou.
_CHAVES_DE_ORIGEM = ("/Metadata", "/PieceInfo")


def _tirar_origem(no, vistos: set[tuple[int, int]]) -> None:
    if isinstance(no, IndirectObject):
        if (no.idnum, no.generation) in vistos:
            return
        vistos.add((no.idnum, no.generation))
        no = no.get_object()
    if isinstance(no, DictionaryObject):
        for chave in _CHAVES_DE_ORIGEM:
            no.pop(chave, None)
        for chave, valor in list(no.items()):
            if chave != "/Parent":
                _tirar_origem(valor, vistos)
    elif isinstance(no, ArrayObject):
        for valor in no:
            _tirar_origem(valor, vistos)


def _limpar_pdf(dados: bytes) -> bytes:
    """Só as páginas, num PDF novo: sem /Info (autor, programa, datas), sem o
    XMP e sem os objetos que ficaram sem dono."""
    leitor = PdfReader(io.BytesIO(dados))
    if leitor.is_encrypted and not leitor.decrypt(""):
        raise AnexoRecusadoError(422, "PDF protegido por senha não pode ser anexado. Envie sem a senha.")
    escritor = PdfWriter()
    for pagina in leitor.pages:
        escritor.add_page(pagina)
    vistos: set[tuple[int, int]] = set()
    for pagina in escritor.pages:
        _tirar_origem(pagina, vistos)
    escritor.metadata = None
    escritor.compress_identical_objects(remove_duplicates=False, remove_unreferenced=True)
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


# ── A entrada ───────────────────────────────────────────────────────────────


def _reconhecer(dados: bytes) -> tuple[str, str] | None:
    """O tipo do anexo e o formato, pelos primeiros bytes."""
    formato = _formato_da_imagem(dados)
    if formato is not None:
        return "imagem", formato
    if dados.startswith(b"%PDF-"):
        return "pdf", "PDF"
    return None


_TETOS = {"imagem": "A imagem passa de 20 MB.", "pdf": "O PDF passa de 20 MB.", "audio": "O áudio passa de 50 MB."}


def limpar(dados: bytes) -> Limpo:
    """O arquivo regravado sem os dados de origem, reconhecido pelo conteúdo."""
    reconhecido = _reconhecer(dados)
    if reconhecido is None:
        raise AnexoRecusadoError(415, RECUSA_DO_FORMATO)
    tipo, formato = reconhecido
    if len(dados) > LIMITES[tipo]:
        raise AnexoRecusadoError(413, _TETOS[tipo])
    try:
        if tipo == "imagem":
            return Limpo(tipo, _IMAGENS[formato], _limpar_imagem(dados, formato))
        return Limpo(tipo, "application/pdf", _limpar_pdf(dados))
    except AnexoRecusadoError:
        raise
    except Exception as erro:  # noqa: BLE001 - arquivo de fora: qualquer falha do leitor é recusa
        raise AnexoRecusadoError(422, RECUSA_ILEGIVEL) from erro


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
