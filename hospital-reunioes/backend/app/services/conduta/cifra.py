"""A cifra do conteúdo do Canal de Conduta (ADR 0097, decisões 1 e 2).

AES-256-GCM na aplicação, com a chave em `CONDUTA_CHAVE_CIFRA` (32 bytes em
base64, no Coolify). Cada cifra usa um nonce novo, então o mesmo relato gravado
duas vezes não se repete no banco.

Fail-closed: sem a chave, com a chave malformada ou com um texto que a chave
não abre, tudo levanta `CifraIndisponivel`. Quem chama responde 503 e não grava
nem mostra nada. A chave é lida a cada chamada, para o resto do app subir sem
ela e para a troca no Coolify valer no restart.

A cifra protege backup, dump e leitura pelo Studio; não protege de quem opera
o deploy, que alcança a chave (ADR 0097, decisão 1).
"""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

# A versão no começo do texto cifrado deixa trocar o formato um dia sem
# confundir o que já está gravado.
_VERSAO = "v1:"
_BYTES_DA_CHAVE = 32
_BYTES_DO_NONCE = 12


class CifraIndisponivel(RuntimeError):
    """O módulo não pode gravar nem ler conteúdo de caso agora."""


def _chave() -> bytes | None:
    try:
        chave = base64.b64decode(settings.conduta_chave_cifra or "", validate=True)
    except (binascii.Error, ValueError):
        return None
    return chave if len(chave) == _BYTES_DA_CHAVE else None


def chave_configurada() -> bool:
    return _chave() is not None


def _aes() -> AESGCM:
    chave = _chave()
    if chave is None:
        raise CifraIndisponivel("chave de cifra do Canal de Conduta ausente ou malformada")
    return AESGCM(chave)


def cifrar_arquivo(dados: bytes) -> bytes:
    aes = _aes()
    nonce = os.urandom(_BYTES_DO_NONCE)
    return nonce + aes.encrypt(nonce, dados, None)


def decifrar_arquivo(dados: bytes) -> bytes:
    aes = _aes()
    try:
        return aes.decrypt(dados[:_BYTES_DO_NONCE], dados[_BYTES_DO_NONCE:], None)
    except (InvalidTag, ValueError) as erro:
        raise CifraIndisponivel("conteúdo que esta chave não abre") from erro


def cifrar_texto(texto: str) -> str:
    return _VERSAO + base64.b64encode(cifrar_arquivo(texto.encode("utf-8"))).decode("ascii")


def decifrar_texto(cifrado: str) -> str:
    if not cifrado.startswith(_VERSAO):
        raise CifraIndisponivel("texto sem a versão da cifra")
    try:
        dados = base64.b64decode(cifrado[len(_VERSAO) :], validate=True)
    except (binascii.Error, ValueError) as erro:
        raise CifraIndisponivel("texto cifrado malformado") from erro
    return decifrar_arquivo(dados).decode("utf-8")
