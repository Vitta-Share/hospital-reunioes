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
import logging
import os
import secrets
import struct
import sys
import wave

import mutagen
import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mutagen.id3 import ID3, TPE1
from mutagen.ogg import OggPage
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import JsonFormatter, RequestContextMiddleware  # noqa: E402
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


# ── Áudio ───────────────────────────────────────────────────────────────────
# Cada áudio de entrada carrega o nome "Joana Prudente" numa etiqueta (e o M4A,
# o lugar da gravação). O som em si é um padrão de bytes que tem que chegar
# inteiro ao arquivo guardado.

SOM = bytes(range(16, 240)) * 4


def _caixa(tipo: bytes, corpo: bytes) -> bytes:
    return struct.pack(">I", 8 + len(corpo)) + tipo + corpo


def _m4a() -> bytes:
    """Um M4A mínimo, como o gravador do celular: uma trilha de som, a
    etiqueta de artista no `ilst` e o lugar da gravação (`©xyz`) no `udta`,
    antes do som."""
    mvhd = _caixa(b"mvhd", b"\x00" * 4 + struct.pack(">IIII", 3_700_000_000, 3_700_000_000, 1000, 5000) + b"\x00" * 80)
    mdhd = _caixa(b"mdhd", b"\x00" * 4 + struct.pack(">IIIIHH", 0, 0, 44100, 44100, 0x55C4, 0))
    som = _caixa(b"hdlr", b"\x00" * 8 + b"soun" + b"\x00" * 12)
    trak = _caixa(b"trak", _caixa(b"mdia", mdhd + som))
    artista = _caixa(b"\xa9ART", _caixa(b"data", struct.pack(">II", 1, 0) + "Joana Prudente".encode()))
    hdlr = _caixa(b"hdlr", b"\x00" * 8 + b"mdirappl" + b"\x00" * 9)
    meta = _caixa(b"meta", b"\x00" * 4 + hdlr + _caixa(b"ilst", artista))
    udta = _caixa(b"udta", meta + _caixa(b"\xa9xyz", b"+22.8712-043.4601/"))
    return _caixa(b"ftyp", b"M4A \x00\x00\x00\x00M4A isom") + _caixa(b"moov", mvhd + trak + udta) + _caixa(b"mdat", SOM)


def _mp3() -> bytes:
    quadro = b"\xff\xfb\x90\x64" + SOM[:413]
    arquivo = io.BytesIO(quadro * 10)
    etiquetas = ID3()
    etiquetas.add(TPE1(encoding=3, text="Joana Prudente"))
    etiquetas.save(arquivo)
    return arquivo.getvalue() + b"TAG" + b"Joana na v1".ljust(125, b"\x00")


def _ogg() -> bytes:
    cabeca = b"OpusHead" + bytes([1, 1]) + struct.pack("<HIhB", 312, 48000, 0, 0)
    comentario = b"ARTIST=Joana Prudente"
    etiquetas = b"OpusTags" + struct.pack("<I", 4) + b"vend" + struct.pack("<II", 1, len(comentario)) + comentario
    paginas = []
    for sequencia, (pacote, posicao) in enumerate([(cabeca, 0), (etiquetas, 0), (SOM, 960)]):
        pagina = OggPage()
        pagina.packets = [pacote]
        pagina.serial = 7
        pagina.sequence = sequencia
        pagina.position = posicao
        pagina.first = sequencia == 0
        pagina.last = sequencia == 2
        paginas.append(pagina.write())
    return b"".join(paginas)


def _wav() -> bytes:
    saida = io.BytesIO()
    with wave.open(saida, "wb") as gravador:
        gravador.setnchannels(1)
        gravador.setsampwidth(1)
        gravador.setframerate(8000)
        gravador.writeframes(SOM)
    nome = b"Joana Prudente\x00"
    info = _caixa_riff(b"LIST", b"INFO" + _caixa_riff(b"IART", nome))
    corpo = saida.getvalue()[12:] + info
    return b"RIFF" + struct.pack("<I", 4 + len(corpo)) + b"WAVE" + corpo


def _caixa_riff(tipo: bytes, corpo: bytes) -> bytes:
    return tipo + struct.pack("<I", len(corpo)) + corpo + (b"\x00" if len(corpo) % 2 else b"")


AUDIOS = {
    "m4a": (_m4a, "audio/mp4"),
    "mp3": (_mp3, "audio/mpeg"),
    "ogg": (_ogg, "audio/ogg"),
    "wav": (_wav, "audio/wav"),
}


class TestAudio:
    @pytest.mark.parametrize("formato", sorted(AUDIOS))
    def test_o_audio_com_etiquetas_e_gravado_sem_elas(self, cliente, banco, relatado, formato):
        fabricar, content_type = AUDIOS[formato]
        audio = fabricar()
        assert b"Joana" in audio, "controle: o áudio de entrada carrega a etiqueta"

        resposta = _anexar(cliente, relatado, audio, f"Gravacao da Joana.{formato}", content_type)

        assert resposta.status_code == 201, resposta.text
        linha, guardado = _guardado(banco)
        assert b"Joana" not in guardado
        assert b"+22.87" not in guardado
        assert SOM in guardado or SOM[:413] in guardado
        lido = mutagen.File(io.BytesIO(guardado))
        assert lido is not None, "o arquivo guardado continua sendo um áudio que o leitor abre"
        assert not lido.tags
        assert linha["tipo"] == "audio"
        assert linha["content_type"] == content_type

    def test_o_wav_guardado_continua_tocando_o_mesmo_som(self, cliente, banco, relatado):
        _anexar(cliente, relatado, _wav(), "gravacao.wav", "audio/wav")

        _, guardado = _guardado(banco)
        assert b"LIST" not in guardado
        with wave.open(io.BytesIO(guardado)) as leitor:
            assert leitor.readframes(leitor.getnframes()) == SOM


# ── Formato fora da lista ───────────────────────────────────────────────────

# Um HEIC do iPhone, um documento do Word e um vídeo: o canal não sabe tirar
# os dados de origem deles, então não entram.
_HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64
_DOCX = b"PK\x03\x04" + b"\x00" * 26 + b"word/document.xml" + b"\x00" * 64


def _mp4_com_video() -> bytes:
    hdlr = _caixa(b"hdlr", b"\x00" * 8 + b"vide" + b"\x00" * 12)
    trak = _caixa(b"trak", _caixa(b"mdia", hdlr))
    return _caixa(b"ftyp", b"isom\x00\x00\x00\x00isom") + _caixa(b"moov", trak) + _caixa(b"mdat", SOM)


class TestFormatoForaDaLista:
    @pytest.mark.parametrize(
        ("conteudo", "nome"),
        [(_HEIC, "IMG_0042.HEIC"), (_DOCX, "relato.docx"), (_mp4_com_video(), "video.mp4"), (b"texto solto", "a.txt")],
        ids=["heic", "docx", "video", "texto"],
    )
    def test_o_formato_fora_da_lista_e_recusado_com_mensagem_clara(self, cliente, banco, relatado, conteudo, nome):
        resposta = _anexar(cliente, relatado, conteudo, nome, "application/octet-stream")

        assert resposta.status_code == 415
        assert resposta.json() == {"detail": anexos.RECUSA_DO_FORMATO}
        assert "JPG, PNG ou WEBP" in anexos.RECUSA_DO_FORMATO
        assert banco.tabelas.get(anexos.TABELA, []) == []
        assert banco.storage.objetos == {}

    def test_o_nome_ou_o_tipo_que_o_navegador_diz_nao_enganam(self, cliente, banco, relatado):
        """O tipo vem do conteúdo: um documento chamado .jpg é recusado."""
        resposta = _anexar(cliente, relatado, _DOCX, "foto.jpg", "image/jpeg")

        assert resposta.status_code == 415
        assert banco.tabelas.get(anexos.TABELA, []) == []

    def test_o_relato_fica_registrado_e_aceita_outro_anexo_depois_da_recusa(self, cliente, banco, relatado):
        _anexar(cliente, relatado, _DOCX, "relato.docx")

        resposta = _anexar(cliente, relatado, _foto_com_exif_e_gps())

        assert len(banco.tabelas["conduta_casos"]) == 1
        assert resposta.status_code == 201
        assert len(banco.tabelas[anexos.TABELA]) == 1

    def test_arquivo_corrompido_e_recusado_sem_gravar(self, cliente, banco, relatado):
        resposta = _anexar(cliente, relatado, b"\xff\xd8\xff\xe0" + b"lixo" * 50)

        assert resposta.status_code == 422
        assert resposta.json() == {"detail": anexos.RECUSA_ILEGIVEL}
        assert banco.storage.objetos == {}


# ── Quem pode anexar ────────────────────────────────────────────────────────


class TestQuemAnexa:
    def test_codigo_errado_nao_grava_e_nao_diz_se_o_protocolo_existe(self, cliente, banco, relatado):
        errado = {**relatado, "codigo": "AAAAAAAAAA"}

        resposta = _anexar(cliente, errado, _foto_com_exif_e_gps())

        assert resposta.status_code == 404
        assert relatado["protocolo"] not in resposta.text
        assert banco.tabelas.get(anexos.TABELA, []) == []
        assert banco.storage.objetos == {}

    def test_o_caso_aceita_ate_10_anexos(self, cliente, banco, relatado):
        respostas = []
        for _ in range(anexos.ANEXOS_POR_CASO + 1):
            limiter._storage.reset()  # o teto aqui é o do caso, não o da rajada
            respostas.append(_anexar(cliente, relatado, FOTO).status_code)

        assert respostas == [201] * 10 + [409]
        assert len(banco.tabelas[anexos.TABELA]) == 10

    def test_com_o_canal_fechado_a_rota_responde_404(self, cliente, banco, relatado, monkeypatch):
        monkeypatch.setattr(settings, "conduta_canal_aberto", False)

        assert _anexar(cliente, relatado, _foto_com_exif_e_gps()).status_code == 404


# ── O nome original ─────────────────────────────────────────────────────────


class _Captura(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.linhas: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.linhas.append(self.format(record))


@pytest.fixture
def log():
    """Tudo o que o app escreve no log, já como sai no stdout do container."""
    captura = _Captura()
    raiz = logging.getLogger()
    nivel = raiz.level
    raiz.addHandler(captura)
    raiz.setLevel(logging.DEBUG)
    yield captura
    raiz.removeHandler(captura)
    raiz.setLevel(nivel)


# Feita fora da captura do log: o que interessa é o que o app escreve.
FOTO = _foto_com_exif_e_gps()


class TestNomeOriginal:
    @pytest.mark.parametrize("aceito", [True, False], ids=["aceito", "recusado"])
    def test_o_nome_original_do_arquivo_nao_fica_em_tabela_nem_em_log(self, cliente, banco, relatado, log, aceito):
        conteudo = FOTO if aceito else _DOCX

        resposta = _anexar(cliente, relatado, conteudo, NOME_DO_ARQUIVO)

        assert resposta.status_code == (201 if aceito else 415)
        assert log.linhas, "controle: o log da requisição tem que ter sido escrito"
        rastro = "\n".join([repr(banco.tabelas), repr(list(banco.storage.objetos)), *log.linhas, resposta.text])
        for trecho in ("Prudente", "estacionamento", "Foto da"):
            assert trecho not in rastro

    def test_nem_o_que_o_arquivo_carregava_vai_ao_log(self, cliente, relatado, log):
        _anexar(cliente, relatado, FOTO)

        assert "Celular da Joana" not in "\n".join(log.linhas)
