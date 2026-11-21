"""Anexos no formulário de notificação (issue #1988, PRD #1979, ADR 0107).

O que a issue promete, um bloco por critério de aceite do backend:

1. até 3 arquivos (foto ou PDF), somando menos de 9 MB, vão junto com a
   notificação; o quarto, o tipo não aceito e a soma acima do limite são
   recusados com mensagem clara, e nada fica gravado;
2. o arquivo só abre pelo backend para quem tem acesso ao caso; o super admin
   sem Acesso pleno e o anônimo sem sessão recebem recusa;
3. o texto que vai à IA não leva anexo: a notificação não guarda nada do
   arquivo, nem o nome.

O banco e o storage são dublês em memória, os mesmos do teste da notificação.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_seguranca_do_paciente_notificacoes import (  # noqa: E402, F401
    ANONIMO,
    IDENTIFICADO,
    PELO_MODULO,
    PUBLICO,
    SO_REUNIOES,
    _banco,
    _cliente,
    _reset_rate_limiter,
)

BUCKET = "nsp-anexos"
MB = 1024 * 1024
# Os primeiros bytes de um JPEG e de um PDF: o conteúdo é de mentira.
FOTO = b"\xff\xd8\xff\xe0" + b"0" * 2048
PDF = b"%PDF-1.7\n" + b"0" * 1024


class _Bucket:
    def __init__(self, storage: _Storage, nome: str):
        self._storage = storage
        self._nome = nome

    def upload(self, caminho, conteudo, opcoes=None):
        if self._storage.falhar_upload:
            raise RuntimeError("storage fora do ar")
        self._storage.arquivos[(self._nome, caminho)] = (bytes(conteudo), (opcoes or {}).get("content-type"))
        return SimpleNamespace(path=caminho)

    def download(self, caminho):
        return self._storage.arquivos[(self._nome, caminho)][0]

    def remove(self, caminhos):
        removidos = []
        for caminho in caminhos:
            if self._storage.arquivos.pop((self._nome, caminho), None) is not None:
                removidos.append({"name": caminho})
        return removidos


class _Storage:
    def __init__(self):
        self.arquivos: dict[tuple[str, str], tuple[bytes, str | None]] = {}
        self.falhar_upload = False

    def from_(self, nome: str) -> _Bucket:
        return _Bucket(self, nome)


def _banco_com_storage():
    banco = _banco()
    banco.storage = _Storage()
    return banco


def _multipart(envio: dict, arquivos: list[tuple[str, bytes, str]]) -> dict:
    """O corpo que o formulário manda quando há arquivo: o relato em `dados` e
    cada arquivo em `anexos`."""
    return {
        "data": {"dados": json.dumps(envio)},
        "files": [("anexos", (nome, conteudo, tipo)) for nome, conteudo, tipo in arquivos],
    }


def _anexos(banco) -> list[dict]:
    return banco.tabelas.get("nsp_notificacao_anexos", [])


# ═══════════════════════════════════════════════════════════════════════════
# 1. Até 3 arquivos, foto ou PDF, somando menos de 9 MB
# ═══════════════════════════════════════════════════════════════════════════


def test_a_notificacao_sem_login_leva_foto_e_pdf_ao_bucket_privado_do_nucleo():
    banco = _banco_com_storage()

    resposta = _cliente(banco).post(
        PUBLICO,
        **_multipart(
            {**ANONIMO, "origem": "qr"},
            [("foto do corredor.jpg", FOTO, "image/jpeg"), ("escala.pdf", PDF, "application/pdf")],
        ),
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["protocolo"]
    (notificacao,) = banco.notificacoes
    anexos = _anexos(banco)
    assert [a["notificacao_id"] for a in anexos] == [notificacao["id"], notificacao["id"]]
    assert [a["content_type"] for a in anexos] == ["image/jpeg", "application/pdf"]
    assert [a["tamanho_bytes"] for a in anexos] == [len(FOTO), len(PDF)]
    guardados = {caminho: conteudo for (bucket, caminho), (conteudo, _tipo) in banco.storage.arquivos.items()}
    assert {bucket for bucket, _ in banco.storage.arquivos} == {BUCKET}
    assert [guardados[a["storage_path"]] for a in anexos] == [FOTO, PDF]
