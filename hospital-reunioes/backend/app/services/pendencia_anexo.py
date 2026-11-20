"""Foto ou PDF anexado na conclusão da Pendência (issue #1865, PRD #1757).

Ao concluir, o responsável pode anexar uma imagem ou um PDF de até 10 MB, além
da anotação, que continua obrigatória. O binário vai para o bucket privado
`anexos-pendencias` com caminho sorteado; os metadados ficam em
`pendencia_anexos`, ligados ao evento de conclusão do Histórico (migration
170). Abrir é só por link assinado de curta duração, e só para o responsável,
o Facilitador da Reunião e o Super admin (decisão 47 da #1757, confirmada pelo
diretor na #1859).

Toda recusa vem antes do bucket: arquivo recusado não deixa rastro.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterable

from app.config import settings
from app.services import storage
from app.services.pendencia_ciclo import Papel

LIMITE_BYTES = 10 * 1024 * 1024

# Pela extensão, como o resto da casa (ADR 0034), e conferido pelos primeiros
# bytes: um executável renomeado para .jpg não entra.
TIPOS: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def _assinatura_confere(content_type: str, conteudo: bytes) -> bool:
    if content_type == "image/jpeg":
        return conteudo.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return conteudo.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP"
    return conteudo.startswith(b"%PDF-")


# Cinco minutos: quem clica abre na hora. Link colado fora do app morre antes
# de virar acesso permanente.
VALIDADE_DO_LINK_SEGUNDOS = 5 * 60

PAPEIS_QUE_ABREM = frozenset({Papel.RESPONSAVEL, Papel.FACILITADOR, Papel.SUPER_ADMIN})

MOTIVO_TIPO = "O anexo precisa ser uma foto (JPG, PNG ou WEBP) ou um PDF. Escolha outro arquivo."
MOTIVO_GRANDE = "O anexo passa de 10 MB. Mande uma foto menor ou um PDF mais leve."
MOTIVO_VAZIO = "O arquivo chegou vazio. Escolha o arquivo de novo."
MOTIVO_NAO_GUARDOU = "Não foi possível guardar o anexo agora. Tente de novo em instantes."
RECUSA_DO_LINK = "Só o responsável, o facilitador da reunião e quem administra o aplicativo abrem este anexo."


class AnexoRecusado(Exception):  # noqa: N818, o nome do domínio
    """A recusa, com a frase que a pessoa lê e o status HTTP da rota."""

    def __init__(self, motivo: str, status_code: int = 422):
        super().__init__(motivo)
        self.motivo = motivo
        self.status_code = status_code


def bucket() -> str:
    return settings.supabase_storage_bucket_anexos_pendencias


def conferir(nome: str, conteudo: bytes) -> tuple[str, str]:
    """A extensão e o `content-type` do anexo, ou a recusa."""
    extensao = os.path.splitext(nome or "")[1].lower()
    content_type = TIPOS.get(extensao)
    if content_type is None:
        raise AnexoRecusado(MOTIVO_TIPO)
    if not conteudo:
        raise AnexoRecusado(MOTIVO_VAZIO)
    if len(conteudo) > LIMITE_BYTES:
        raise AnexoRecusado(MOTIVO_GRANDE, status_code=413)
    if not _assinatura_confere(content_type, conteudo):
        raise AnexoRecusado(MOTIVO_TIPO)
    return extensao, content_type


def guardar(supabase, *, id_acao: str, extensao: str, conteudo: bytes, content_type: str) -> str:
    """Sobe o binário ao bucket privado e devolve o caminho sorteado."""
    # O nome original pode carregar dado pessoal e não vira parte de caminho.
    path = f"pendencia-{id_acao}/{uuid.uuid4().hex}{extensao}"
    if not storage.upload_private(supabase, bucket=bucket(), path=path, content=conteudo, content_type=content_type):
        raise AnexoRecusado(MOTIVO_NAO_GUARDOU, status_code=503)
    return path


def descartar(supabase, path: str) -> None:
    """Tira do bucket o binário cuja conclusão não entrou."""
    storage.delete_file(supabase, bucket(), path)


def pode_abrir(papeis: Iterable[Papel]) -> bool:
    return bool(PAPEIS_QUE_ABREM.intersection(papeis))


def link(supabase, path: str) -> str | None:
    return storage.signed_url(supabase, bucket(), path, VALIDADE_DO_LINK_SEGUNDOS)
