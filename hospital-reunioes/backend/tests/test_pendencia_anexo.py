"""Foto ou PDF anexado na conclusão da Pendência (issue #1865, PRD #1757).

`POST /pendencias/{id}/conclusao` conclui com a anotação obrigatória e, se
vier, um anexo (imagem ou PDF até 10 MB) que sobe ao bucket privado e fica
ligado ao evento de conclusão. `GET /pendencias/{id}/anexos/{anexo}/link`
devolve o link assinado de curta duração só ao responsável, ao Facilitador da
Reunião e ao Super admin. O banco aqui é de mentira; a prova da migration 174
num Postgres de verdade está em `test_pendencia_anexo_banco.py`.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

from test_pendencia_acoes import HOJE, PESSOAS, _Banco, _banco, _Result  # noqa: E402

from app.dependencies import get_current_user, get_supabase_client, require_acesso_reunioes  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import pendencias as pendencias_router  # noqa: E402
from app.services import pendencia_anexo  # noqa: E402
from app.services.pendencias_recorte import recorte_das_pendencias  # noqa: E402

JPG = b"\xff\xd8\xff\xe0" + b"0" * 2000
PDF = b"%PDF-1.7\n" + b"0" * 2000
DEZ_MB = 10 * 1024 * 1024


class _BancoComAnexos(_Banco):
    """O banco de mentira da 169, mais a função de conclusão com anexo da 174."""

    def __init__(self, base: _Banco):
        super().__init__(
            pendencias=base.pendencias,
            reunioes=base.reunioes,
            participantes=base.participantes,
        )

    def rpc(self, nome, params):
        if nome != "registrar_conclusao_com_anexo":
            return super().rpc(nome, params)
        banco = self

        class _Exec:
            def execute(self_inner):  # noqa: N805
                acao = {k: v for k, v in params.items() if k not in _DO_ANEXO}
                acao.update({"p_comando": "concluir", "p_prazo_novo": None})
                _Banco.rpc(banco, "registrar_acao_da_pendencia", acao).execute()
                evento = banco.pendencia_historico[-1]["id"]
                banco.pendencia_anexos.append(
                    {
                        "id": len(banco.pendencia_anexos) + 1,
                        "id_acao": params["p_id_acao"],
                        "evento_id": evento,
                        "storage_path": params["p_storage_path"],
                        "nome_original": params["p_nome_original"],
                        "content_type": params["p_content_type"],
                        "tamanho_bytes": params["p_tamanho_bytes"],
                    }
                )
                return _Result([evento])

        self.chamadas.append((nome, params))
        return _Exec()


_DO_ANEXO = {"p_storage_path", "p_nome_original", "p_content_type", "p_tamanho_bytes"}


@pytest.fixture
def cliente(monkeypatch):
    estado: dict = {"quem": "resp", "banco": _BancoComAnexos(_banco(status="EM_PROGRESSO")), "bucket": {}}

    async def _participante(_user, _sb, fields=None):
        return PESSOAS[estado["quem"]]

    async def _recorte(_user, _sb):
        quem = estado["quem"]
        return recorte_das_pendencias(
            PESSOAS[quem]["id"],
            super_admin=quem == "admin",
            facilitadas=["R1"] if quem == "facil" else [],
            do_nucleo=[],
            ocultas=[],
        )

    def _upload(_sb, bucket, path, content, content_type="application/octet-stream"):
        estado["bucket"][(bucket, path)] = (content, content_type)
        return True

    def _assinar(_sb, bucket, path, expires_in):
        estado["assinado"] = (bucket, path, expires_in)
        return f"https://storage.exemplo/{bucket}/{path}?token=t&expira={expires_in}"

    def _apagar(_sb, bucket, path):
        estado["bucket"].pop((bucket, path), None)
        return True

    monkeypatch.setattr(pendencias_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(pendencias_router, "get_recorte_das_pendencias", _recorte)
    monkeypatch.setattr(pendencias_router, "hoje_em_brasilia", lambda: HOJE)
    monkeypatch.setattr(pendencia_anexo.storage, "upload_private", _upload)
    monkeypatch.setattr(pendencia_anexo.storage, "signed_url", _assinar)
    monkeypatch.setattr(pendencia_anexo.storage, "delete_file", _apagar)

    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "email": "x@x"}
    app.dependency_overrides[get_supabase_client] = lambda: estado["banco"]
    app.dependency_overrides[require_acesso_reunioes] = lambda: None
    try:
        yield TestClient(app), estado
    finally:
        app.dependency_overrides.clear()


def _concluir(client, anotacao="Entreguei ao almoxarifado", arquivo=None):
    files = {"arquivo": arquivo} if arquivo else None
    return client.post("/api/pendencias/A001/conclusao", data={"anotacao": anotacao}, files=files)


# ── Concluir sem anexo funciona; concluir sem anotação não ──────────────────


def test_concluir_sem_anexo_funciona(cliente):
    client, estado = cliente
    r = _concluir(client)

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONCLUIDO"
    assert estado["banco"].pendencia_historico[-1]["comando"] == "concluir"
    assert estado["banco"].pendencia_anexos == []
    assert estado["bucket"] == {}


@pytest.mark.parametrize("anotacao", ["", "   "])
def test_concluir_sem_anotacao_e_recusado_mesmo_com_anexo(cliente, anotacao):
    client, estado = cliente
    r = _concluir(client, anotacao=anotacao, arquivo=("foto.jpg", JPG, "image/jpeg"))

    assert r.status_code == 422
    assert estado["banco"].chamadas == []
    assert estado["bucket"] == {}
    assert estado["banco"].pendencias[0]["status"] == "EM_PROGRESSO"


# ── O anexo fica no evento de conclusão ─────────────────────────────────────


def test_concluir_com_foto_guarda_no_bucket_privado_ligada_ao_evento_de_conclusao(cliente):
    client, estado = cliente
    r = _concluir(client, arquivo=("almoxarifado do João.jpg", JPG, "image/jpeg"))

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "CONCLUIDO"
    [anexo] = estado["banco"].pendencia_anexos
    evento = next(e for e in estado["banco"].pendencia_historico if e["id"] == anexo["evento_id"])
    assert evento["comando"] == "concluir"
    assert anexo["nome_original"] == "almoxarifado do João.jpg"
    assert anexo["content_type"] == "image/jpeg"
    assert anexo["tamanho_bytes"] == len(JPG)
    [(bucket, path)] = estado["bucket"]
    assert bucket == "anexos-pendencias"
    assert path == anexo["storage_path"]
    # O nome original pode ter dado pessoal e não vira caminho.
    assert "João" not in path


def test_concluir_com_pdf_tambem_entra(cliente):
    client, estado = cliente
    r = _concluir(client, arquivo=("nota.pdf", PDF, "application/pdf"))
    assert r.status_code == 200, r.text
    assert estado["banco"].pendencia_anexos[0]["content_type"] == "application/pdf"


def test_historico_mostra_o_anexo_no_evento_de_conclusao(cliente):
    client, _ = cliente
    _concluir(client, arquivo=("foto.jpg", JPG, "image/jpeg"))

    corpo = client.get("/api/pendencias/A001/historico").json()
    [conclusao] = [e for e in corpo["eventos"] if e["comando"] == "concluir"]
    assert conclusao["anexo"]["nome"] == "foto.jpg"
    assert conclusao["anexo"]["tipo"] == "image/jpeg"
    assert isinstance(conclusao["anexo"]["id"], int)
    assert corpo["pode_abrir_anexos"] is True


def test_conclusao_recusada_no_banco_tira_o_binario_do_bucket(cliente):
    client, estado = cliente
    from postgrest.exceptions import APIError

    def _recusa(nome, params):
        class _Exec:
            def execute(self_inner):  # noqa: N805
                raise APIError({"code": "PT409", "message": "A pendencia mudou.", "details": None, "hint": None})

        return _Exec()

    estado["banco"].rpc = _recusa
    r = _concluir(client, arquivo=("foto.jpg", JPG, "image/jpeg"))

    assert r.status_code == 409
    assert estado["bucket"] == {}


# ── Tipo e tamanho ──────────────────────────────────────────────────────────


def test_arquivo_acima_de_10_mb_e_recusado_com_mensagem_clara(cliente):
    client, estado = cliente
    grande = b"\xff\xd8\xff\xe0" + b"0" * DEZ_MB
    r = _concluir(client, arquivo=("foto.jpg", grande, "image/jpeg"))

    assert r.status_code == 413
    assert "10 MB" in r.json()["detail"]
    assert estado["bucket"] == {}
    assert estado["banco"].chamadas == []


def test_arquivo_de_exatos_10_mb_entra(cliente):
    client, _ = cliente
    r = _concluir(client, arquivo=("foto.jpg", (b"\xff\xd8\xff\xe0" + b"0" * DEZ_MB)[:DEZ_MB], "image/jpeg"))
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "nome,conteudo",
    [
        ("planilha.xlsx", b"PK\x03\x04" + b"0" * 100),
        ("video.mp4", b"\x00\x00\x00\x18ftypmp42"),
        # Extensão de foto com outra coisa dentro.
        ("foto.jpg", b"MZ\x90\x00 executavel"),
    ],
)
def test_arquivo_de_outro_tipo_e_recusado_com_mensagem_clara(cliente, nome, conteudo):
    client, estado = cliente
    r = _concluir(client, arquivo=(nome, conteudo, "application/octet-stream"))

    assert r.status_code == 422
    assert "foto" in r.json()["detail"] and "PDF" in r.json()["detail"]
    assert estado["bucket"] == {}
    assert estado["banco"].chamadas == []


# ── O link assinado ─────────────────────────────────────────────────────────


def _anexo_gravado(client) -> int:
    r = _concluir(client, arquivo=("foto.jpg", JPG, "image/jpeg"))
    assert r.status_code == 200, r.text
    return client.get("/api/pendencias/A001/historico").json()["eventos"][-1]["anexo"]["id"]


@pytest.mark.parametrize("quem", ["resp", "facil", "admin"])
def test_os_tres_papeis_abrem_o_anexo_por_link_assinado_de_poucos_minutos(cliente, quem):
    client, estado = cliente
    anexo_id = _anexo_gravado(client)
    estado["quem"] = quem

    r = client.get(f"/api/pendencias/A001/anexos/{anexo_id}/link")

    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://storage.exemplo/anexos-pendencias/")
    bucket, path, expira = estado["assinado"]
    assert bucket == "anexos-pendencias"
    assert path == estado["banco"].pendencia_anexos[0]["storage_path"]
    assert 0 < expira <= 5 * 60


@pytest.mark.parametrize("quem", ["coresp", "outro"])
def test_quem_esta_fora_dos_tres_papeis_recebe_403_ao_pedir_o_link(cliente, quem):
    client, estado = cliente
    anexo_id = _anexo_gravado(client)
    estado["quem"] = quem
    estado.pop("assinado", None)

    r = client.get(f"/api/pendencias/A001/anexos/{anexo_id}/link")

    assert r.status_code == 403
    assert "assinado" not in estado


def test_historico_diz_a_quem_esta_fora_dos_tres_papeis_que_nao_abre(cliente):
    client, estado = cliente
    _anexo_gravado(client)
    estado["quem"] = "coresp"
    assert client.get("/api/pendencias/A001/historico").json()["pode_abrir_anexos"] is False


def test_anexo_de_outra_pendencia_nao_abre_pelo_link_desta(cliente):
    client, estado = cliente
    anexo_id = _anexo_gravado(client)
    estado["banco"].pendencia_anexos[0]["id_acao"] = "A999"
    r = client.get(f"/api/pendencias/A001/anexos/{anexo_id}/link")
    assert r.status_code == 404


# ── O kit de conhecimento ───────────────────────────────────────────────────


def test_o_texto_de_reunioes_no_kit_diz_o_anexo_da_conclusao():
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "reunioes.md").read_text(encoding="utf-8")
    assert "Ao concluir, dá para anexar uma foto ou um PDF de até 10 MB" in texto
    assert "só o responsável, o facilitador da reunião e quem administra o aplicativo abrem" in texto
