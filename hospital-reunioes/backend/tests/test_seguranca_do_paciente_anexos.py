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

import pytest
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_seguranca_do_paciente_notificacoes import (  # noqa: E402, F401
    ANONIMO,
    DIRETOR,
    DIRETOR_EXECUTIVO,
    IDENTIFICADO,
    MEMBRO,
    PELO_MODULO,
    PRESIDENTE,
    PUBLICO,
    RECUSA_DO_CONTEUDO,
    SO_REUNIOES,
    SUPER_ADMIN,
    _banco,
    _cliente,
    _Consulta,
    _reset_rate_limiter,
    _secao_do_kit,
)

from app.routers import seguranca_do_paciente_notificacoes as notificacoes_router  # noqa: E402

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


def test_pelo_modulo_a_notificacao_tambem_leva_os_arquivos():
    banco = _banco_com_storage()

    resposta = _cliente(banco, SO_REUNIOES).post(
        PELO_MODULO, **_multipart(ANONIMO, [("IMG_0001.png", b"\x89PNG" + b"0" * 512, "image/png")])
    )

    assert resposta.status_code == 201, resposta.text
    (anexo,) = _anexos(banco)
    assert anexo["notificacao_id"] == banco.notificacoes[0]["id"]
    assert anexo["content_type"] == "image/png"


def test_tres_arquivos_entram_e_o_recibo_nao_traz_o_id_da_notificacao():
    banco = _banco_com_storage()
    tres = [(f"foto{n}.jpg", FOTO, "image/jpeg") for n in range(3)]

    resposta = _cliente(banco).post(PUBLICO, **_multipart({**IDENTIFICADO, "origem": "endereco"}, tres))

    assert resposta.status_code == 201, resposta.text
    assert len(_anexos(banco)) == 3
    assert "id" not in resposta.json()
    assert resposta.json()["anexos_guardados"] is True


@pytest.mark.parametrize(
    ("arquivos", "codigo", "trecho"),
    [
        ([(f"foto{n}.jpg", FOTO, "image/jpeg") for n in range(4)], 422, "até 3 arquivos"),
        ([("planilha.xlsx", b"PK" + b"0" * 64, "image/jpeg")], 415, "Envie foto"),
        ([("audio.mp3", b"ID3" + b"0" * 64, "audio/mpeg")], 415, "Envie foto"),
        ([("vazia.jpg", b"", "image/jpeg")], 422, "vazio"),
        (
            [("grande1.jpg", b"0" * (5 * MB), "image/jpeg"), ("grande2.pdf", b"0" * (4 * MB), "application/pdf")],
            413,
            "somam 9,0 MB e precisam somar menos de 9 MB",
        ),
    ],
    ids=["o quarto arquivo", "tipo não aceito", "áudio, que a Ouvidoria aceita", "arquivo vazio", "soma de 9 MB"],
)
def test_arquivo_recusado_volta_com_mensagem_clara_e_nada_fica_gravado(arquivos, codigo, trecho):
    banco = _banco_com_storage()

    resposta = _cliente(banco).post(PUBLICO, **_multipart({**ANONIMO, "origem": "qr"}, arquivos))

    assert resposta.status_code == codigo, resposta.text
    assert trecho in resposta.json()["detail"]
    assert banco.notificacoes == []
    assert _anexos(banco) == []
    assert banco.storage.arquivos == {}


def test_a_soma_logo_abaixo_de_9_mb_entra():
    banco = _banco_com_storage()
    arquivos = [("a.jpg", b"0" * (5 * MB), "image/jpeg"), ("b.pdf", b"0" * (4 * MB - 1), "application/pdf")]

    resposta = _cliente(banco).post(PUBLICO, **_multipart({**ANONIMO, "origem": "qr"}, arquivos))

    assert resposta.status_code == 201, resposta.text
    assert len(_anexos(banco)) == 2


def test_o_relato_incompleto_no_multipart_e_recusado_como_no_json():
    banco = _banco_com_storage()

    resposta = _cliente(banco).post(
        PUBLICO, **_multipart({**ANONIMO, "origem": "qr", "relato": "  "}, [("foto.jpg", FOTO, "image/jpeg")])
    )

    assert resposta.status_code == 422
    assert banco.notificacoes == []
    assert banco.storage.arquivos == {}


def test_storage_fora_do_ar_pede_para_tentar_de_novo_sem_gravar_a_notificacao():
    banco = _banco_com_storage()
    banco.storage.falhar_upload = True

    resposta = _cliente(banco).post(
        PUBLICO, **_multipart({**ANONIMO, "origem": "qr"}, [("foto.jpg", FOTO, "image/jpeg")])
    )

    assert resposta.status_code == 503
    assert resposta.json()["detail"] == notificacoes_router.FALHA_DOS_ANEXOS
    assert banco.notificacoes == []


def _falhar_no_insert(monkeypatch, tabela: str) -> None:
    executar = _Consulta.execute

    def _falhar(self):
        if self._nome == tabela and self._acao == "insert":
            raise APIError({"message": "connection reset", "code": "08006"})
        return executar(self)

    monkeypatch.setattr(_Consulta, "execute", _falhar)


def test_banco_fora_do_ar_tira_do_bucket_o_que_subiu(monkeypatch):
    banco = _banco_com_storage()
    _falhar_no_insert(monkeypatch, "nsp_notificacoes")

    resposta = _cliente(banco).post(
        PUBLICO, **_multipart({**ANONIMO, "origem": "qr"}, [("foto.jpg", FOTO, "image/jpeg")])
    )

    assert resposta.status_code == 503
    assert banco.storage.arquivos == {}


def test_falha_ao_ligar_os_anexos_mantem_a_notificacao_e_avisa(monkeypatch):
    banco = _banco_com_storage()
    _falhar_no_insert(monkeypatch, "nsp_notificacao_anexos")

    resposta = _cliente(banco).post(
        PUBLICO, **_multipart({**ANONIMO, "origem": "qr"}, [("foto.jpg", FOTO, "image/jpeg")])
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["protocolo"]
    assert resposta.json()["anexos_guardados"] is False
    assert len(banco.notificacoes) == 1
    assert banco.storage.arquivos == {}


# ═══════════════════════════════════════════════════════════════════════════
# 2. O arquivo só abre pelo backend, para quem tem acesso ao caso
# ═══════════════════════════════════════════════════════════════════════════


def _caso_com_anexos() -> tuple:
    banco = _banco_com_storage()
    resposta = _cliente(banco).post(
        PUBLICO,
        **_multipart(
            {**ANONIMO, "origem": "qr"},
            [("foto do corredor.jpg", FOTO, "image/jpeg"), ("escala.pdf", PDF, "application/pdf")],
        ),
    )
    assert resposta.status_code == 201, resposta.text
    return banco, banco.notificacoes[0]["id"], _anexos(banco)


def _endereco_do_anexo(notificacao_id: str, anexo_id: str) -> str:
    return f"/api/nsp/notificacoes/{notificacao_id}/anexos/{anexo_id}"


@pytest.mark.parametrize(
    "pessoa", [PRESIDENTE, MEMBRO, DIRETOR_EXECUTIVO], ids=["Presidência", "membro", "Acesso pleno"]
)
def test_quem_tem_acesso_ao_caso_abre_o_arquivo_pelo_backend(pessoa):
    banco, notificacao_id, (foto, pdf) = _caso_com_anexos()
    cliente = _cliente(banco, pessoa)

    resposta = cliente.get(_endereco_do_anexo(notificacao_id, foto["id"]))

    assert resposta.status_code == 200, resposta.text
    assert resposta.content == FOTO
    assert resposta.headers["content-type"] == "image/jpeg"
    assert resposta.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in resposta.headers["cache-control"]
    # O nome original não volta: pode identificar quem notificou.
    assert "corredor" not in resposta.headers.get("content-disposition", "")
    assert cliente.get(_endereco_do_anexo(notificacao_id, pdf["id"])).content == PDF


@pytest.mark.parametrize(
    "pessoa",
    [SUPER_ADMIN, SO_REUNIOES, DIRETOR],
    ids=["super admin sem Acesso pleno", "só nas Reuniões", "diretoria"],
)
def test_quem_nao_tem_acesso_ao_caso_recebe_recusa_e_nao_o_arquivo(pessoa):
    banco, notificacao_id, (foto, _pdf) = _caso_com_anexos()

    resposta = _cliente(banco, pessoa).get(_endereco_do_anexo(notificacao_id, foto["id"]))

    assert resposta.status_code == 403
    assert resposta.json() == RECUSA_DO_CONTEUDO
    assert FOTO not in resposta.content


def test_o_anonimo_sem_sessao_recebe_recusa():
    banco, notificacao_id, (foto, _pdf) = _caso_com_anexos()

    resposta = _cliente(banco).get(_endereco_do_anexo(notificacao_id, foto["id"]))

    assert resposta.status_code == 401
    assert FOTO not in resposta.content


def test_o_anexo_de_outro_caso_nao_abre_por_este():
    banco, _notificacao_id, (foto, _pdf) = _caso_com_anexos()
    outro = _cliente(banco).post(PUBLICO, json={**ANONIMO, "origem": "qr"})
    assert outro.status_code == 201
    outro_id = banco.notificacoes[1]["id"]

    resposta = _cliente(banco, PRESIDENTE).get(_endereco_do_anexo(outro_id, foto["id"]))

    assert resposta.status_code == 404
    assert FOTO not in resposta.content


def test_a_lista_de_casos_diz_os_anexos_sem_o_caminho_no_bucket():
    banco, notificacao_id, (foto, pdf) = _caso_com_anexos()

    resposta = _cliente(banco, PRESIDENTE).get(PELO_MODULO)

    assert resposta.status_code == 200, resposta.text
    (caso,) = resposta.json()["notificacoes"]
    assert caso["anexos"] == [
        {"id": foto["id"], "content_type": "image/jpeg", "tamanho_bytes": len(FOTO)},
        {"id": pdf["id"], "content_type": "application/pdf", "tamanho_bytes": len(PDF)},
    ]
    assert foto["storage_path"] not in resposta.text


# ═══════════════════════════════════════════════════════════════════════════
# 3. O texto que vai à IA não leva anexo
# ═══════════════════════════════════════════════════════════════════════════


def test_a_notificacao_nao_guarda_nada_do_arquivo():
    """A IA lê a linha da notificação: nela não entra o nome, o tipo, o
    caminho nem o conteúdo de arquivo nenhum, e o nome original não fica em
    lugar nenhum do banco."""
    banco, _notificacao_id, _anexos_do_caso = _caso_com_anexos()

    (notificacao,) = banco.notificacoes
    texto_da_linha = json.dumps(notificacao, ensure_ascii=False, default=str)
    for rastro in ("corredor", "escala", ".jpg", ".pdf", "image/", "application/pdf", BUCKET):
        assert rastro not in texto_da_linha, rastro
    assert not any("anexo" in campo for campo in notificacao)
    tudo_no_banco = json.dumps(banco.tabelas, ensure_ascii=False, default=str)
    assert "corredor" not in tudo_no_banco
    assert "escala.pdf" not in tudo_no_banco


# ═══════════════════════════════════════════════════════════════════════════
# 4. O texto do Produto no Kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    def test_o_que_ja_esta_no_ar_diz_os_anexos(self):
        secao = _secao_do_kit("O que já está no ar")
        for termo in (
            "até três fotos ou PDFs",
            "menos de 9 MB",
            "reduzida no próprio celular",
            "só abrem para quem abre os casos",
            "nenhum anexo vai para a inteligência artificial",
        ):
            assert termo in secao, termo

    def test_o_que_ainda_nao_faz_deixa_de_dizer_que_os_anexos_nao_chegaram(self):
        secao = _secao_do_kit("O que ele ainda não faz")
        assert "anexos (fotos e arquivos)" not in secao
