"""A assinatura da ata do Núcleo pelos presentes, o encerramento em 5 dias
úteis e a limpeza da transcrição (issue #1776, PRD #1764, ADR 0095).

O que a issue promete, um bloco por critério:

1. a ata vai para assinatura só dos presentes, e só depois da validação da
   Presidência;
2. o encerramento conta 5 dias úteis com os feriados cadastrados e registra
   quem não assinou;
3. a transcrição de reunião do Núcleo é apagada 30 dias corridos depois da ata
   assinada; a de outras reuniões não é tocada;
4. a ata encerrada aparece nos Documentos com número sequencial;
5. rodar os jobs duas vezes não muda o resultado;
6. o kit de conhecimento diz o comportamento novo.

E a decisão da triagem: a ata assinada sai só pela rota do Núcleo, com a
permissão do módulo, e nunca pelo super admin sem Acesso pleno.

O banco é o dublê em memória das reuniões do Núcleo. A IA, a assinatura
eletrônica e o Storage são sempre dublados: a função da assinatura que não
estiver no dublê explode. Nenhum nome, registro ou e-mail de pessoa real.
"""

from __future__ import annotations

import copy
import os
import sys
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_seguranca_do_paciente_ata import (  # noqa: E402, F401
    DIA_DA_REUNIAO,
    R_ATA,
    _ata_gravada,
    _BancoDaAta,
    _com_ata,
    _ConsultaComLt,
    _ia,
    _reset_rate_limiter,
    _status,
    _validar,
)
from test_seguranca_do_paciente_reunioes import (  # noqa: E402
    HOJE,
    MEMBRO,
    MEMBRO_SEM_TERMO,
    PRESIDENCIA,
    R_COMUM,
    SUPER_ADMIN,
    SUPER_ADMIN_PLENO,
    _assert_recusado,
    _cliente,
)

from app.config import settings  # noqa: E402
from app.services import clicksign_service, storage  # noqa: E402
from app.services.seguranca_do_paciente import assinatura_da_ata  # noqa: E402

FERIADO = date(2026, 11, 20)
# O PDF de verdade, guardado antes do dublê do fixture.
_GERAR_PDF = assinatura_da_ata.gerar_pdf_da_ata
DIA_DA_ATA = DIA_DA_REUNIAO.strftime("%d/%m/%Y")


# ─── A assinatura eletrônica e o Storage dublados ───────────────────────────


class _Assinatura:
    """O envelope de mentira. `assinaram` diz quem já assinou (por e-mail)."""

    def __init__(self):
        self.chamadas: list[tuple] = []
        self.signatarios: dict[str, list[dict]] = {}
        self.assinaram: set[str] = set()
        self.status = "running"
        self.falhar_em: str | None = None
        self._n = 0

    def _passo(self, nome: str, *args) -> bool:
        self.chamadas.append((nome, *args))
        return self.falhar_em != nome

    def create_envelope(self, nome):
        self._n += 1
        return f"env-{self._n}" if self._passo("create_envelope", nome) else None

    def add_document(self, envelope_id, pdf, nome_do_arquivo):
        return f"doc-{envelope_id}" if self._passo("add_document", envelope_id, nome_do_arquivo) else None

    def add_signer(self, envelope_id, nome, email):
        if not self._passo("add_signer", envelope_id, nome, email):
            return None
        lista = self.signatarios.setdefault(envelope_id, [])
        lista.append({"signer_id": f"sig-{len(lista) + 1}", "nome": nome, "email": email})
        return lista[-1]["signer_id"]

    def create_qualification_requirement(self, envelope_id, documento_id, signatario_id):
        return "req-q" if self._passo("create_qualification_requirement", envelope_id) else None

    def create_auth_requirement(self, envelope_id, documento_id, signatario_id):
        return "req-a" if self._passo("create_auth_requirement", envelope_id) else None

    def activate_envelope(self, envelope_id):
        return self._passo("activate_envelope", envelope_id)

    def notify_signers(self, envelope_id):
        return self._passo("notify_signers", envelope_id)

    def get_envelope_status(self, envelope_id):
        self._passo("get_envelope_status", envelope_id)
        return self.status

    def close_envelope(self, envelope_id):
        if not self._passo("close_envelope", envelope_id):
            return False
        self.status = "closed"
        return True

    def list_signers(self, envelope_id):
        self._passo("list_signers", envelope_id)
        return [
            {
                **s,
                "status": "signed" if s["email"] in self.assinaram else "pending",
                "signed_at": "2026-11-17T10:00:00+00:00" if s["email"] in self.assinaram else None,
            }
            for s in self.signatarios.get(envelope_id, [])
        ]

    def get_signed_document(self, envelope_id):
        self._passo("get_signed_document", envelope_id)
        return b"%PDF-1.4 ata assinada" if self.status == "closed" else None

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


@pytest.fixture(autouse=True)
def assinatura(monkeypatch, request) -> _Assinatura:
    # Depois do dublê da IA do teste da ata, que também derruba a assinatura.
    request.getfixturevalue("_ia")
    dubla = _Assinatura()
    for nome in (
        "create_envelope",
        "add_document",
        "add_signer",
        "create_qualification_requirement",
        "create_auth_requirement",
        "activate_envelope",
        "notify_signers",
        "get_envelope_status",
        "close_envelope",
        "list_signers",
        "get_signed_document",
    ):
        monkeypatch.setattr(clicksign_service, nome, getattr(dubla, nome))
    # O PDF de verdade tem o próprio teste; aqui ele é só bytes.
    monkeypatch.setattr(assinatura_da_ata, "gerar_pdf_da_ata", lambda reuniao, ata: b"%PDF-1.4 ata")
    return dubla


class _Storage:
    def __init__(self):
        self.arquivos: dict[tuple[str, str], bytes] = {}

    def upload_private(self, supabase, bucket, path, content, content_type="application/octet-stream"):
        self.arquivos[(bucket, path)] = content
        return True

    def signed_url(self, supabase, bucket, path, expires_in):
        return f"https://storage.test/{bucket}/{path}?expira={expires_in}" if (bucket, path) in self.arquivos else None

    def remover(self, bucket, caminhos):
        return [{"name": c} for c in caminhos if self.arquivos.pop((bucket, c), None) is not None]


@pytest.fixture(autouse=True)
def arquivos(monkeypatch) -> _Storage:
    dublado = _Storage()
    monkeypatch.setattr(storage, "upload_private", dublado.upload_private)
    monkeypatch.setattr(storage, "signed_url", dublado.signed_url)
    monkeypatch.setattr(
        assinatura_da_ata, "_remover_do_storage", lambda supabase, bucket, caminhos: dublado.remover(bucket, caminhos)
    )
    return dublado


def _emails_convidados(dubla: _Assinatura) -> list[str]:
    return sorted(c[3] for c in dubla.chamadas if c[0] == "add_signer")


def _reuniao_gravada(banco, rid: str = R_ATA) -> dict[str, Any]:
    return next(r for r in banco.tabelas["reunioes"] if r["id_reuniao"] == rid)


class _ConsultaComId(_ConsultaComLt):
    """O banco de verdade dá o id do documento na inserção (gen_random_uuid)."""

    def insert(self, linhas):
        if self._tabela == "nsp_documentos" and isinstance(linhas, dict):
            linhas = {"id": f"doc-{uuid4()}", "publicado_em": "2026-11-26T08:00:00+00:00", **linhas}
        return super().insert(linhas)


class _BancoComDocumentos(_BancoDaAta):
    def table(self, nome: str):
        return _ConsultaComId(self, nome)


def _validada() -> Any:
    banco = _com_ata()
    banco.__class__ = _BancoComDocumentos
    resposta = _validar(_cliente(PRESIDENCIA, banco))
    assert resposta.status_code == 200, resposta.text
    return banco


# ═══════════════════════════════════════════════════════════════════════════
# 1. Só os presentes assinam, e só depois da validação
# ═══════════════════════════════════════════════════════════════════════════


class TestSoOsPresentesAssinam:
    def test_a_ata_validada_vai_para_assinatura_so_dos_presentes(self, assinatura):
        banco = _com_ata()
        assert assinatura.chamadas == []

        resposta = _validar(_cliente(PRESIDENCIA, banco))

        assert resposta.status_code == 200, resposta.text
        # PRES1, MEMB1 e MEMB3 presentes; SUPL1 ausente com justificativa.
        assert _emails_convidados(assinatura) == ["memb1@hsm.test", "memb3@hsm.test", "pres1@hsm.test"]
        assert "activate_envelope" in assinatura.nomes()
        assert _status(banco) == "AGUARDANDO_ASSINATURA"
        assert resposta.json()["status"] == "AGUARDANDO_ASSINATURA"

    def test_a_ata_em_validacao_nao_sai_para_assinatura_pelo_job(self, assinatura):
        banco = _com_ata()

        assinatura_da_ata.encerrar_atas(banco, HOJE)

        assert assinatura.chamadas == []
        assert _status(banco) == "AGUARDANDO_VALIDACAO"

    def test_o_envio_que_falhou_na_validacao_sai_no_job(self, assinatura):
        assinatura.falhar_em = "activate_envelope"
        banco = _com_ata()

        resposta = _validar(_cliente(PRESIDENCIA, banco))

        assert resposta.json()["status"] == "APROVADA"
        assert resposta.json()["aviso"]
        assert _status(banco) == "APROVADA"
        assinatura.falhar_em = None
        assinatura.chamadas.clear()

        assinatura_da_ata.encerrar_atas(banco, HOJE)

        assert _emails_convidados(assinatura) == ["memb1@hsm.test", "memb3@hsm.test", "pres1@hsm.test"]
        assert _status(banco) == "AGUARDANDO_ASSINATURA"


# ═══════════════════════════════════════════════════════════════════════════
# 2. O encerramento conta 5 dias úteis com os feriados e registra quem faltou
# ═══════════════════════════════════════════════════════════════════════════

# Quarta-feira. Os 5 dias úteis, com o feriado de sexta (20/11), vencem na
# quinta seguinte, 26/11; sem o feriado, venceriam na quarta, 25/11.
ENVIADA_EM = "2026-11-18T15:00:00-03:00"
QUARTA_SEGUINTE = date(2026, 11, 25)
QUINTA_SEGUINTE = date(2026, 11, 26)


def _enviada(assinatura: _Assinatura, *assinaram: str):
    banco = _validada()
    reuniao = _reuniao_gravada(banco)
    reuniao["json_ata"]["assinatura"]["enviada_em"] = ENVIADA_EM
    banco.tabelas["ouvidoria_feriados"] = [{"data": FERIADO.isoformat()}]
    assinatura.assinaram = set(assinaram)
    return banco


class TestEncerramento:
    def test_antes_do_quinto_dia_util_a_ata_continua_esperando(self, assinatura):
        banco = _enviada(assinatura, "pres1@hsm.test")

        assinatura_da_ata.encerrar_atas(banco, QUARTA_SEGUINTE)

        assert _status(banco) == "AGUARDANDO_ASSINATURA"
        assert "close_envelope" not in assinatura.nomes()

    def test_no_quinto_dia_util_a_ata_encerra_e_registra_quem_nao_assinou(self, assinatura):
        banco = _enviada(assinatura, "pres1@hsm.test", "memb1@hsm.test")

        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)

        reuniao = _reuniao_gravada(banco)
        assert reuniao["status_ata"] == "ASSINADA"
        assert reuniao["data_assinatura"] == QUINTA_SEGUINTE.isoformat()
        assert "close_envelope" in assinatura.nomes()
        encerramento = reuniao["json_ata"]["encerramento"]
        assert encerramento["assinaram"] == ["Pessoa de Teste MEMB1", "Pessoa de Teste PRES1"]
        assert encerramento["nao_assinaram"] == ["Pessoa de Teste MEMB3"]
        assinaturas = next(b for b in reuniao["json_ata"]["blocos"] if b["chave"] == "assinaturas")["itens"]
        assert "Assinaram: Pessoa de Teste MEMB1, Pessoa de Teste PRES1." in assinaturas
        assert "Presentes que não assinaram: Pessoa de Teste MEMB3." in assinaturas

    def test_com_todos_assinados_a_ata_encerra_antes_do_prazo(self, assinatura):
        banco = _enviada(assinatura, "pres1@hsm.test", "memb1@hsm.test", "memb3@hsm.test")
        assinatura.status = "closed"

        assinatura_da_ata.encerrar_atas(banco, date(2026, 11, 19))

        assert _status(banco) == "ASSINADA"
        assert _ata_gravada(banco)["encerramento"]["nao_assinaram"] == []

    def test_a_reuniao_comum_nao_entra_no_encerramento(self, assinatura):
        banco = _enviada(assinatura)
        comum = _reuniao_gravada(banco, R_COMUM)
        comum.update({"status_ata": "AGUARDANDO_ASSINATURA", "json_ata": copy.deepcopy(_ata_gravada(banco))})

        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)

        assert comum["status_ata"] == "AGUARDANDO_ASSINATURA"
        assert "encerramento" not in comum["json_ata"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. A ata encerrada entra nos Documentos, com número sequencial
# ═══════════════════════════════════════════════════════════════════════════


def _ata_anterior_nos_documentos(banco) -> None:
    banco.tabelas["nsp_documentos"] = [
        {
            "id": "doc-ata-1",
            "tipo": "ata",
            "versao": 1,
            "titulo": "Ata de uma reunião anterior",
            "texto": None,
            "natureza_revisao": None,
            "vigente": False,
            "arquivo_assinado_path": "atas/RD_ANTERIOR-assinada.pdf",
            "publicado_por": "PRES1",
            "publicado_em": "2026-10-20T12:00:00+00:00",
            "reuniao_id": "RD_ANTERIOR",
        },
        {
            "id": "doc-regimento-1",
            "tipo": "regimento",
            "versao": 1,
            "titulo": "Regimento Interno",
            "texto": "Art. 1",
            "natureza_revisao": "material",
            "vigente": True,
            "arquivo_assinado_path": "regimentos/1-assinado.pdf",
            "publicado_por": "PRES1",
            "publicado_em": "2026-10-01T12:00:00+00:00",
            "reuniao_id": None,
        },
    ]


def _documento_da_ata(banco) -> dict[str, Any] | None:
    return next((d for d in banco.tabelas.get("nsp_documentos", []) if d.get("reuniao_id") == R_ATA), None)


def _cliente_dos_documentos(pessoa, banco):
    from app.routers import seguranca_do_paciente_documentos as documentos_router

    cliente = _cliente(pessoa, banco)
    cliente.app.include_router(documentos_router.router, prefix="/api")
    return cliente


class TestDocumentos:
    def test_a_ata_encerrada_aparece_nos_documentos_com_o_numero_seguinte(self, assinatura, arquivos):
        banco = _enviada(assinatura, "pres1@hsm.test")
        _ata_anterior_nos_documentos(banco)

        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)

        documento = _documento_da_ata(banco)
        assert documento is not None
        assert (documento["tipo"], documento["versao"], documento["vigente"]) == ("ata", 2, False)
        assert documento["publicado_por"] == "PRES1"
        assert arquivos.arquivos[(settings.supabase_storage_bucket_nsp_documentos, documento["arquivo_assinado_path"])]
        lista = _cliente_dos_documentos(MEMBRO, banco).get("/api/nsp/documentos").json()["documentos"]
        da_ata = next(d for d in lista if d["id"] == documento["id"])
        assert (da_ata["versao"], da_ata["tem_arquivo_assinado"]) == (2, True)
        assert DIA_DA_ATA in da_ata["titulo"]

    def test_sem_o_pdf_assinado_pronto_o_documento_entra_na_rodada_seguinte(self, assinatura, monkeypatch):
        banco = _enviada(assinatura, "pres1@hsm.test")
        monkeypatch.setattr(clicksign_service, "get_signed_document", lambda envelope_id: None)

        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)

        assert _status(banco) == "ASSINADA"
        assert _documento_da_ata(banco) is None
        monkeypatch.setattr(clicksign_service, "get_signed_document", assinatura.get_signed_document)

        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE + timedelta(days=1))

        assert _documento_da_ata(banco)["versao"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# A ata assinada sai só pela rota do Núcleo (decisão da triagem)
# ═══════════════════════════════════════════════════════════════════════════


def _encerrada(assinatura) -> Any:
    banco = _enviada(assinatura, "pres1@hsm.test")
    _ata_anterior_nos_documentos(banco)
    assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)
    return banco


def _baixar(cliente, documento_id: str):
    return cliente.get(f"/api/nsp/reunioes/atas/{documento_id}/arquivo-assinado")


class TestArquivoAssinado:
    def test_o_membro_baixa_a_ata_assinada_pela_rota_do_nucleo(self, assinatura):
        banco = _encerrada(assinatura)
        cliente = _cliente(MEMBRO, banco)
        documento_id = cliente.get(f"/api/nsp/reunioes/{R_ATA}/ata").json()["documento_id"]
        assert documento_id == _documento_da_ata(banco)["id"]

        resposta = _baixar(cliente, documento_id)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["url"].startswith("https://storage.test/nsp-documentos/atas/")

    @pytest.mark.parametrize(
        "pessoa", [pytest.param(SUPER_ADMIN, id="super_admin"), pytest.param(MEMBRO_SEM_TERMO, id="sem_termo")]
    )
    def test_quem_nao_abre_a_ata_do_nucleo_nao_baixa(self, assinatura, pessoa):
        banco = _encerrada(assinatura)

        _assert_recusado(_baixar(_cliente(pessoa, banco), _documento_da_ata(banco)["id"]))

    def test_o_acesso_pleno_baixa(self, assinatura):
        banco = _encerrada(assinatura)

        assert _baixar(_cliente(SUPER_ADMIN_PLENO, banco), _documento_da_ata(banco)["id"]).status_code == 200

    def test_a_rota_da_ata_nao_entrega_documento_de_outro_tipo(self, assinatura):
        banco = _encerrada(assinatura)

        resposta = _baixar(_cliente(MEMBRO, banco), "doc-regimento-1")

        assert resposta.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 3. A transcrição do Núcleo some 30 dias corridos depois da ata assinada
# ═══════════════════════════════════════════════════════════════════════════

TRANSCRICOES = settings.supabase_storage_bucket_transcricoes


def _com_transcricoes(assinatura, arquivos) -> Any:
    """A ata do Núcleo assinada em 26/11 e uma reunião comum assinada há mais
    tempo, com o mesmo `json_ata` (para o filtro ser o do Núcleo, e não a
    forma da ata). As duas com a transcrição importada no bucket."""
    banco = _encerrada(assinatura)
    comum = _reuniao_gravada(banco, R_COMUM)
    comum.update(
        {
            "data_assinatura": "2026-10-01",
            "json_ata": copy.deepcopy(_ata_gravada(banco)),
            "url_transcricao": "https://storage.test/transcricoes/RD_COMUM_01/transcricao.docx",
        }
    )
    _reuniao_gravada(banco)["url_transcricao"] = "https://storage.test/transcricoes/RD_NUCLEO_ATA/transcricao.docx"
    for rid in (R_ATA, R_COMUM):
        arquivos.arquivos[(TRANSCRICOES, f"{rid}/transcricao.docx")] = b"original"
        arquivos.arquivos[(TRANSCRICOES, f"{rid}/transcricao.txt")] = b"texto"
    return banco


def _transcricoes_de(arquivos, rid: str) -> list[str]:
    return sorted(c for b, c in arquivos.arquivos if b == TRANSCRICOES and c.startswith(f"{rid}/"))


class TestLimpezaDaTranscricao:
    def test_a_transcricao_do_nucleo_some_no_trigesimo_dia_e_a_da_comum_fica(self, assinatura, arquivos):
        banco = _com_transcricoes(assinatura, arquivos)

        assinatura_da_ata.apagar_transcricoes(banco, QUINTA_SEGUINTE + timedelta(days=29))

        assert _transcricoes_de(arquivos, R_ATA) == [f"{R_ATA}/transcricao.docx", f"{R_ATA}/transcricao.txt"]

        assinatura_da_ata.apagar_transcricoes(banco, QUINTA_SEGUINTE + timedelta(days=30))

        assert _transcricoes_de(arquivos, R_ATA) == []
        assert _reuniao_gravada(banco)["url_transcricao"] is None
        assert (
            _ata_gravada(banco)["encerramento"]["transcricao_apagada_em"]
            == (QUINTA_SEGUINTE + timedelta(days=30)).isoformat()
        )
        # A reunião comum, assinada há mais de 30 dias, não é tocada.
        assert _transcricoes_de(arquivos, R_COMUM) == [f"{R_COMUM}/transcricao.docx", f"{R_COMUM}/transcricao.txt"]
        assert _reuniao_gravada(banco, R_COMUM)["url_transcricao"].endswith("transcricao.docx")

    def test_falha_do_storage_deixa_para_a_rodada_seguinte(self, assinatura, arquivos, monkeypatch):
        banco = _com_transcricoes(assinatura, arquivos)

        def _fora_do_ar(*_a):
            raise RuntimeError("Storage fora do ar")

        monkeypatch.setattr(assinatura_da_ata, "_remover_do_storage", _fora_do_ar)

        assinatura_da_ata.apagar_transcricoes(banco, QUINTA_SEGUINTE + timedelta(days=30))

        assert "transcricao_apagada_em" not in _ata_gravada(banco)["encerramento"]
        assert _reuniao_gravada(banco)["url_transcricao"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. Rodar os jobs duas vezes não muda o resultado
# ═══════════════════════════════════════════════════════════════════════════


class TestJobsDeNovo:
    def test_os_dois_jobs_rodados_duas_vezes_dao_o_mesmo_resultado(self, assinatura, arquivos):
        banco = _com_transcricoes(assinatura, arquivos)
        trigesimo = QUINTA_SEGUINTE + timedelta(days=30)
        assinatura_da_ata.apagar_transcricoes(banco, trigesimo)
        depois_da_primeira = copy.deepcopy(banco.tabelas)
        arquivos_da_primeira = dict(arquivos.arquivos)
        assinatura.chamadas.clear()

        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)
        assinatura_da_ata.encerrar_atas(banco, trigesimo)
        assinatura_da_ata.apagar_transcricoes(banco, trigesimo)

        assert banco.tabelas == depois_da_primeira
        assert arquivos.arquivos == arquivos_da_primeira
        assert [d for d in banco.tabelas["nsp_documentos"] if d.get("reuniao_id") == R_ATA][0]["versao"] == 2
        assert {"close_envelope", "add_signer", "get_signed_document"}.isdisjoint(assinatura.nomes())

    def test_o_encerramento_rodado_duas_vezes_no_mesmo_dia_nao_duplica(self, assinatura):
        banco = _enviada(assinatura, "pres1@hsm.test")

        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)
        primeira = copy.deepcopy(banco.tabelas)
        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)

        assert banco.tabelas == primeira
        assert assinatura.nomes().count("close_envelope") == 1
        assert len([d for d in banco.tabelas["nsp_documentos"] if d.get("reuniao_id") == R_ATA]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Os jobs não chamam IA e estão no relógio
# ═══════════════════════════════════════════════════════════════════════════

_MARCAS_DE_IA = ("ai_processor", "anthropic", "openai", "openrouter")


def _marcas(codigo: str) -> list[str]:
    return [marca for marca in _MARCAS_DE_IA if marca in codigo.lower()]


class TestSemIa:
    def test_os_jobs_rodam_sem_chamar_a_ia(self, assinatura, arquivos, request):
        ia = request.getfixturevalue("_ia")
        banco = _enviada(assinatura, "pres1@hsm.test")
        minutas_pedidas = len(ia.chamadas)

        assinatura_da_ata.encerrar_atas(banco, QUINTA_SEGUINTE)
        assinatura_da_ata.apagar_transcricoes(banco, QUINTA_SEGUINTE + timedelta(days=30))

        assert _status(banco) == "ASSINADA"
        assert len(ia.chamadas) == minutas_pedidas

    def test_o_servico_dos_jobs_nao_fala_com_ia(self):
        import inspect

        assert _marcas(inspect.getsource(assinatura_da_ata)) == []

    def test_os_dois_jobs_estao_no_scheduler_e_so_chamam_o_servico(self, monkeypatch):
        import inspect

        from app.cron import scheduler

        assert 'encerrar_atas_do_nucleo,\n        "cron"' in inspect.getsource(scheduler.start_scheduler)
        assert 'apagar_transcricoes_do_nucleo,\n        "cron"' in inspect.getsource(scheduler.start_scheduler)
        chamadas: list[tuple] = []
        monkeypatch.setattr(scheduler, "_supabase", lambda: "banco")
        monkeypatch.setattr(scheduler, "_hoje_em_sao_paulo", lambda: QUINTA_SEGUINTE)
        monkeypatch.setattr(assinatura_da_ata, "encerrar_atas", lambda b, hoje: chamadas.append(("encerrar", hoje)))
        monkeypatch.setattr(assinatura_da_ata, "apagar_transcricoes", lambda b, hoje: chamadas.append(("apagar", hoje)))

        scheduler.encerrar_atas_do_nucleo()
        scheduler.apagar_transcricoes_do_nucleo()

        assert chamadas == [("encerrar", QUINTA_SEGUINTE), ("apagar", QUINTA_SEGUINTE)]

    def test_o_job_que_falha_nao_derruba_o_scheduler(self, monkeypatch):
        from app.cron import scheduler

        def _explode(*_a):
            raise RuntimeError("banco fora do ar")

        monkeypatch.setattr(scheduler, "_supabase", lambda: "banco")
        monkeypatch.setattr(assinatura_da_ata, "encerrar_atas", _explode)
        monkeypatch.setattr(assinatura_da_ata, "apagar_transcricoes", _explode)

        scheduler.encerrar_atas_do_nucleo()
        scheduler.apagar_transcricoes_do_nucleo()


# ═══════════════════════════════════════════════════════════════════════════
# O PDF que vai para assinatura
# ═══════════════════════════════════════════════════════════════════════════


class TestPdf:
    def test_o_pdf_da_ata_tem_os_dez_blocos_e_nao_tem_travessao(self):
        from app.services.pdf_generator import env

        banco = _validada()
        reuniao = _reuniao_gravada(banco)

        html = env.get_template("nsp_ata_do_nucleo.html").render(reuniao=reuniao, ata=reuniao["json_ata"])

        for bloco in reuniao["json_ata"]["blocos"]:
            assert bloco["titulo"] in html
        assert "Revisar a sinalização dos leitos de risco de queda" in html
        assert "—" not in html
        assert "–" not in html
        assert _GERAR_PDF(reuniao, reuniao["json_ata"]).startswith(b"%PDF")


# ═══════════════════════════════════════════════════════════════════════════
# 6. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    def test_o_kit_de_conhecimento_diz_o_comportamento_novo(self):
        caminho = os.path.join(os.path.dirname(__file__), "..", "app", "conhecimento", "seguranca-do-paciente.md")
        with open(caminho, encoding="utf-8") as arquivo:
            texto = " ".join(arquivo.read().split())

        assert "a ata validada vai por e-mail para a assinatura eletrônica de quem estava presente, e só deles" in texto
        assert "5 dias úteis depois do envio, contando os feriados cadastrados" in texto
        assert "quem estava presente e não assinou fica registrado no bloco Assinaturas" in texto
        assert "entra em Documentos como ata, com o número seguinte" in texto
        assert "Baixar a ata assinada" in texto
        assert "a transcrição importada é apagada 30 dias corridos depois da ata assinada" in texto
        assert "A assinatura dos presentes chega numa próxima entrega" not in texto
        assert "—" not in texto
        assert "–" not in texto
