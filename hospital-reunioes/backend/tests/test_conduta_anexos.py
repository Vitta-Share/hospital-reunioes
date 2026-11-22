"""Os anexos do relato do Canal de Conduta (issue #1844, especificação seção 4,
passo P4; ADR 0097, decisão 2).

Quem relata anexa imagem, PDF ou áudio. Antes de gravar, o backend apaga os
dados de origem do arquivo (EXIF e GPS da imagem, informações de documento e
XMP do PDF, etiquetas do áudio), cifra e guarda no bucket do Canal. A prova é
sempre o arquivo guardado, decifrado como o Comitê o recebe, e nunca o
retorno da função que limpa.
"""

from __future__ import annotations

import base64
import io
import os
import secrets
import sys

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import RequestContextMiddleware  # noqa: E402
from app.routers import conduta_publico  # noqa: E402
from app.services.conduta import agente_de_triagem, anexos, cifra  # noqa: E402

RELATOS = "/api/conduta/relatos"
ANEXOS = "/api/conduta/relatos/anexos"
TEXTO = "O encarregado da farmácia levou caixas de medicamento controlado para o carro."
CIENCIA = {"ciente": True, "versoes": {"aviso_p1_anonimato": None, "aviso_p1_protocolo": None, "aviso_p1_boa_fe": None}}
ENVIO = {"ciencia": CIENCIA, "identificacao": "anonimo", "direcao": "nao", "relato": TEXTO}
NOME_DO_ARQUIVO = "Foto da Joana Prudente no estacionamento.jpg"


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "conduta_canal_aberto", True)
    monkeypatch.setattr(agente_de_triagem, "agendar_triagem_do_caso", lambda *_a, **_kw: None)
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def banco():
    return Banco()


@pytest.fixture
def cliente(banco):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(conduta_publico.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def relatado(cliente) -> dict:
    resposta = cliente.post(RELATOS, json=ENVIO)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _anexar(cliente, relatado: dict, conteudo: bytes, nome: str = NOME_DO_ARQUIVO, tipo: str = "image/jpeg"):
    return cliente.post(
        ANEXOS,
        data={"protocolo": relatado["protocolo"], "codigo": relatado["codigo"]},
        files={"arquivo": (nome, conteudo, tipo)},
    )


def _guardado(banco) -> tuple[dict, bytes]:
    """A linha do anexo e o arquivo como o Comitê o recebe: lido do bucket e
    decifrado."""
    (linha,) = banco.tabelas[anexos.TABELA]
    cifrado = banco.storage.objetos[(anexos.BUCKET, linha["storage_path"])]
    return linha, cifra.decifrar_arquivo(cifrado)


# ── Imagem ──────────────────────────────────────────────────────────────────

GPS = 0x8825
FABRICANTE = 0x010F
MODELO = 0x0110


def _foto_com_exif_e_gps(formato: str = "JPEG") -> bytes:
    imagem = Image.new("RGB", (64, 48), (200, 30, 30))
    exif = Image.Exif()
    exif[FABRICANTE] = "Celular da Joana"
    exif[MODELO] = "Modelo-XR-77"
    exif[GPS] = {1: "S", 2: (22.0, 52.0, 12.0), 3: "W", 4: (43.0, 27.0, 36.0)}
    saida = io.BytesIO()
    imagem.save(saida, format=formato, exif=exif)
    foto = saida.getvalue()
    # Controle: a foto de entrada carrega mesmo o EXIF e o GPS.
    lida = Image.open(io.BytesIO(foto)).getexif()
    assert lida.get(FABRICANTE) == "Celular da Joana"
    assert lida.get_ifd(GPS)
    return foto


class TestImagem:
    @pytest.mark.parametrize(
        ("formato", "tipo"), [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")]
    )
    def test_a_foto_com_exif_e_gps_e_gravada_sem_eles(self, cliente, banco, relatado, formato, tipo):
        resposta = _anexar(cliente, relatado, _foto_com_exif_e_gps(formato), tipo=tipo)

        assert resposta.status_code == 201, resposta.text
        linha, guardado = _guardado(banco)
        imagem = Image.open(io.BytesIO(guardado))
        assert imagem.format == formato
        assert imagem.size == (64, 48)
        assert dict(imagem.getexif()) == {}
        assert not imagem.getexif().get_ifd(GPS)
        assert b"Celular da Joana" not in guardado
        assert b"Modelo-XR-77" not in guardado
        assert linha["tipo"] == "imagem"
        assert linha["content_type"] == tipo


# ── PDF ─────────────────────────────────────────────────────────────────────

XMP = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>Joana no XMP</dc:creator>'
    b"</rdf:Description></rdf:RDF></x:xmpmeta>"
)


def _pdf_com_autor_e_programa() -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(200, 200)
    escritor.add_blank_page(200, 200)
    escritor.add_metadata({"/Author": "Joana Prudente", "/Creator": "Digitalizador do RH", "/Producer": "Programa-Z 9"})
    escritor.xmp_metadata = XMP
    # O XMP também pode vir pendurado na página, não só no documento.
    da_pagina = DecodedStreamObject()
    da_pagina.set_data(b"<xmp>Joana na pagina</xmp>")
    da_pagina[NameObject("/Type")] = NameObject("/Metadata")
    escritor.pages[0][NameObject("/Metadata")] = escritor._add_object(da_pagina)
    saida = io.BytesIO()
    escritor.write(saida)
    pdf = saida.getvalue()
    # Controle: o PDF de entrada carrega mesmo o autor, o programa e o XMP.
    lido = PdfReader(io.BytesIO(pdf))
    assert lido.metadata.author == "Joana Prudente"
    assert lido.metadata.creator == "Digitalizador do RH"
    assert lido.xmp_metadata is not None
    assert b"Joana na pagina" in pdf
    return pdf


class TestPdf:
    def test_o_pdf_com_autor_e_programa_de_origem_e_gravado_sem_eles(self, cliente, banco, relatado):
        resposta = _anexar(cliente, relatado, _pdf_com_autor_e_programa(), "Denuncia da Joana.pdf", "application/pdf")

        assert resposta.status_code == 201, resposta.text
        linha, guardado = _guardado(banco)
        lido = PdfReader(io.BytesIO(guardado))
        assert len(lido.pages) == 2
        assert not lido.metadata
        assert lido.xmp_metadata is None
        assert "/Metadata" not in lido.pages[0]
        for marca in (b"Joana", b"Digitalizador", b"Programa-Z"):
            assert marca not in guardado
        assert linha["tipo"] == "pdf"
        assert linha["content_type"] == "application/pdf"
