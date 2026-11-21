"""Os anexos da Notificação de incidente (issue #1988, PRD #1979, ADR 0107).

Quem notifica anexa até três fotos ou PDFs, somando menos de 9 MB, abaixo do
corte de 10 MB do proxy do Next (ADR 0107, decisão 6). As regras de arquivo
são as da Ouvidoria (`ouvidoria_anexos.validar_anexo`: extensão, arquivo
vazio, content-type pela extensão, nunca pelo que o navegador declarou), com a
lista estreitada para foto e PDF.

O binário vai para o bucket privado do Núcleo, num caminho sorteado, e só os
metadados ficam no banco, numa tabela à parte. O nome original do arquivo não é
guardado: pode identificar quem notificou sem se identificar. Nada daqui vai
para a IA: a linha da notificação não ganha campo nenhum.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.services import storage
from app.services.ouvidoria_anexos import (
    AnexoGrandeDemaisError,
    AnexoRecusadoError,
    TipoNaoPermitidoError,
    validar_anexo,
)

logger = logging.getLogger(__name__)

MAXIMO_DE_ARQUIVOS = 3
# "Somando menos de 9 MB" (ADR 0107): a soma tem de ficar abaixo.
LIMITE_DA_SOMA = 9 * 1024 * 1024
LIMITE_DA_SOMA_LEGIVEL = "9 MB"
EXTENSOES_ACEITAS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"})

TABELA = "nsp_notificacao_anexos"


class ArquivosDemaisError(AnexoRecusadoError):
    """Mais de três arquivos."""


class AnexoIndisponivelError(Exception):
    """O anexo existe no banco, mas o storage não o devolveu agora."""


@dataclass(frozen=True)
class ArquivoRecebido:
    nome: str
    conteudo: bytes


@dataclass(frozen=True)
class ArquivoAceito:
    conteudo: bytes
    extensao: str
    content_type: str


def conferir_os_arquivos(arquivos: list[ArquivoRecebido]) -> list[ArquivoAceito]:
    """Devolve os arquivos aceitos, ou levanta a recusa com a mensagem que
    quem notifica lê na tela. Nada é gravado antes desta conferência."""
    if len(arquivos) > MAXIMO_DE_ARQUIVOS:
        raise ArquivosDemaisError(f"Você pode anexar até {MAXIMO_DE_ARQUIVOS} arquivos. Tire um e envie de novo.")
    aceitos = []
    for arquivo in arquivos:
        nome = (arquivo.nome or "").strip()
        extensao = nome[nome.rfind(".") :].lower() if "." in nome else ""
        if extensao not in EXTENSOES_ACEITAS:
            raise TipoNaoPermitidoError(
                f"O arquivo {nome or 'sem nome'} não é aceito. Envie foto (JPG, PNG, WEBP ou HEIC) ou PDF."
            )
        extensao, content_type = validar_anexo(nome, len(arquivo.conteudo))
        aceitos.append(ArquivoAceito(arquivo.conteudo, extensao, content_type))
    soma = sum(len(a.conteudo) for a in aceitos)
    if soma >= LIMITE_DA_SOMA:
        raise AnexoGrandeDemaisError(
            f"Os arquivos somam {soma / (1024 * 1024):.1f} MB e precisam somar menos de "
            f"{LIMITE_DA_SOMA_LEGIVEL}. Tire um arquivo ou envie um menor."
        )
    return aceitos


def _bucket() -> str:
    return settings.supabase_storage_bucket_nsp_anexos


def subir_ao_bucket(supabase, aceitos: list[ArquivoAceito]) -> list[str] | None:
    """Sobe cada arquivo num caminho sorteado e devolve os caminhos, ou `None`
    quando algum não subiu (e aí os que subiram saem do bucket)."""
    caminhos: list[str] = []
    for arquivo in aceitos:
        caminho = f"{uuid.uuid4().hex}{arquivo.extensao}"
        if not storage.upload_private(
            supabase, bucket=_bucket(), path=caminho, content=arquivo.conteudo, content_type=arquivo.content_type
        ):
            tirar_do_bucket(supabase, caminhos)
            return None
        caminhos.append(caminho)
    return caminhos


def tirar_do_bucket(supabase, caminhos: list[str]) -> None:
    for caminho in caminhos:
        if not storage.delete_file(supabase, _bucket(), caminho):
            # Sem a linha no banco, o caminho escrito no log é o único jeito de
            # achar o arquivo depois.
            logger.error("Anexo de notificação órfão no bucket: %s", caminho)


def ligar_a_notificacao(supabase, notificacao_id: str, aceitos: list[ArquivoAceito], caminhos: list[str]) -> None:
    """Grava os metadados numa instrução só: ou entram todos, ou nenhum."""
    supabase.table(TABELA).insert(
        [
            {
                "notificacao_id": notificacao_id,
                "storage_path": caminho,
                "content_type": arquivo.content_type,
                "tamanho_bytes": len(arquivo.conteudo),
            }
            for arquivo, caminho in zip(aceitos, caminhos, strict=True)
        ]
    ).execute()


def anexos_dos_casos(supabase, notificacao_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Os anexos de cada caso, sem o caminho no bucket: o arquivo só sai pela
    rota que confere o acesso."""
    if not notificacao_ids:
        return {}
    linhas = (
        supabase.table(TABELA)
        .select("id, notificacao_id, content_type, tamanho_bytes, criado_em")
        .in_("notificacao_id", notificacao_ids)
        .order("criado_em")
        .execute()
        .data
    ) or []
    por_caso: dict[str, list[dict[str, Any]]] = {}
    for linha in linhas:
        por_caso.setdefault(linha["notificacao_id"], []).append(
            {"id": linha["id"], "content_type": linha["content_type"], "tamanho_bytes": linha["tamanho_bytes"]}
        )
    return por_caso


def abrir_o_anexo(supabase, notificacao_id: str, anexo_id: str) -> tuple[bytes, str, str] | None:
    """O binário, o content-type e a extensão do anexo DESTE caso, ou `None`.
    Sem o casamento com o caso, o id de um anexo viraria caminho lateral."""
    linhas = (
        supabase.table(TABELA)
        .select("id, notificacao_id, storage_path, content_type")
        .eq("id", anexo_id)
        .eq("notificacao_id", notificacao_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not linhas:
        return None
    caminho = linhas[0]["storage_path"]
    conteudo = storage.download_file(supabase, _bucket(), caminho)
    if conteudo is None:
        raise AnexoIndisponivelError(caminho)
    return conteudo, linhas[0]["content_type"], caminho[caminho.rfind(".") :]
