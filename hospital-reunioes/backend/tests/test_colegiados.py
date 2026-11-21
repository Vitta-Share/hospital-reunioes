"""O serviço de membros e de Termo recebe o Colegiado (issue #1819, ADR 0097 decisão 3).

O Núcleo de Segurança do Paciente e o Comitê de Conduta usam as mesmas tabelas
de Colegiado e Participação. Aqui o serviço roda com dois Colegiados no mesmo
banco: o Núcleo e um segundo, com as tabelas e a sigla dele. Os membros de um
não aparecem no outro, e o Termo de um não cai nas tabelas do outro.

O banco, o Storage e a assinatura eletrônica são dublês em memória. As pessoas
daqui são de teste.
"""

from __future__ import annotations

import ast
import os
import sys
import uuid
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.services import clicksign_service, colegiados  # noqa: E402
from app.services.seguranca_do_paciente import permissao, termo  # noqa: E402
from app.services.seguranca_do_paciente.permissao import NUCLEO  # noqa: E402

HOJE = date(2026, 11, 20)

# O segundo Colegiado: as mesmas tabelas de Participação, as dele para o Termo.
COMITE = replace(
    NUCLEO,
    slug="comite-de-teste",
    nome="Comitê",
    sigla="CT",
    termos_envios="comite_termos_envios",
    documentos="comite_documentos",
    documentos_envios="comite_documentos_envios",
    bucket_dos_documentos="supabase_storage_bucket_anexos_tecnologia",
    modelo_do_termo="comite_termo_adesao.html",
)


def _iso(delta: int) -> str:
    return (HOJE + timedelta(days=delta)).isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# Dublês
# ═══════════════════════════════════════════════════════════════════════════


class _Consulta:
    def __init__(self, banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._filtros: list = []
        self._teto: int | None = None
        self._ordem: tuple | None = None
        self._recorte: tuple[int, int] | None = None
        self._operacao = ("select", None)

    @property
    def _linhas(self) -> list[dict]:
        return self._banco.tabelas.setdefault(self._nome, [])

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        valores = list(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) <= str(valor))
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) >= str(valor))
        return self

    def order(self, coluna, desc=False):
        self._ordem = (coluna, desc)
        return self

    def limit(self, n):
        self._teto = n
        return self

    def range(self, inicio, fim):
        self._recorte = (inicio, fim)
        return self

    def insert(self, linha):
        self._operacao = ("insert", linha)
        return self

    def update(self, campos: dict):
        self._operacao = ("update", campos)
        return self

    def execute(self):
        operacao, carga = self._operacao
        if operacao == "insert":
            gravadas = []
            for linha in carga if isinstance(carga, list) else [carga]:
                nova = {"id": str(uuid.uuid4()), "created_at": f"{HOJE.isoformat()}T12:00:00+00:00", **linha}
                self._linhas.append(nova)
                gravadas.append(dict(nova))
            return SimpleNamespace(data=gravadas)
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if operacao == "update":
            for linha in casam:
                linha.update(carga)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        if self._ordem:
            coluna, desc = self._ordem
            casam.sort(key=lambda linha: str(linha.get(coluna) or ""), reverse=desc)
        if self._recorte:
            inicio, fim = self._recorte
            casam = casam[inicio : fim + 1]
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)


class _Balde:
    def __init__(self, arquivos: dict, nome: str):
        self._arquivos = arquivos
        self._nome = nome

    def upload(self, caminho, conteudo, _opcoes=None):
        self._arquivos[(self._nome, caminho)] = conteudo


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas
        self.arquivos: dict[tuple[str, str], bytes] = {}
        self.storage = SimpleNamespace(from_=lambda nome: _Balde(self.arquivos, nome))

    def table(self, nome: str):
        return _Consulta(self, nome)


class _Assinatura:
    def __init__(self):
        self.envelopes: list[str] = []
        self.arquivos: list[str] = []

    def create_envelope(self, nome):
        self.envelopes.append(nome)
        return f"env-{len(self.envelopes)}"

    def add_document(self, envelope_id, _pdf, nome_do_arquivo):
        self.arquivos.append(nome_do_arquivo)
        return f"doc-{envelope_id}"

    def add_signer(self, envelope_id, nome, email):
        return f"sig-{envelope_id}"

    def create_qualification_requirement(self, *_a):
        return "req-q"

    def create_auth_requirement(self, *_a):
        return "req-a"

    def activate_envelope(self, _envelope_id):
        return True

    def notify_signers(self, _envelope_id):
        return True

    def cancel_envelope(self, _envelope_id):
        return True

    def get_signed_document(self, _envelope_id):
        return b"%PDF-1.4 assinado"


@pytest.fixture(autouse=True)
def assinatura(monkeypatch) -> _Assinatura:
    dubla = _Assinatura()
    for nome in (
        "create_envelope",
        "add_document",
        "add_signer",
        "create_qualification_requirement",
        "create_auth_requirement",
        "activate_envelope",
        "notify_signers",
        "cancel_envelope",
        "get_signed_document",
    ):
        monkeypatch.setattr(clicksign_service, nome, getattr(dubla, nome))
    return dubla


@pytest.fixture(autouse=True)
def modelos(monkeypatch) -> list[str]:
    """O PDF não é gerado aqui: anota de qual modelo ele sairia."""
    usados: list[str] = []

    def _pdf(dados):
        usados.append(dados["modelo"])
        return b"%PDF-1.4 termo"

    monkeypatch.setattr(termo, "gerar_pdf_do_termo", _pdf)
    monkeypatch.setattr(permissao, "hoje_em_sao_paulo", lambda: HOJE)
    return usados


def _pessoa(pid: str) -> dict:
    return {
        "id": pid,
        "nome_completo": f"Pessoa de Teste {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "cargo": "Cargo de teste",
        "setor": "Setor de teste",
        "conselho_profissional": None,
        "registro_profissional": None,
        "registro_uf": None,
    }


def _participacao(pid: str, colegiado_id: str, *, papel="membro", termo_assinado=True) -> dict:
    return {
        "id": f"part-{colegiado_id}-{pid}",
        "colegiado_id": colegiado_id,
        "participante_id": pid,
        "papel": papel,
        "area": "Área de teste",
        "vigencia_inicio": _iso(-30),
        "vigencia_fim": _iso(300),
        "encerrada_em": None,
        "termo_gerado_em": None,
        "termo_enviado_em": None,
        "termo_assinado_em": "2026-01-10T12:00:00+00:00" if termo_assinado else None,
    }


def _regimento(colegiado: str) -> dict:
    return {
        "id": f"regimento-{colegiado}",
        "tipo": "regimento",
        "versao": 1,
        "titulo": f"Regimento de teste do {colegiado}",
        "texto": "Art. 1º Texto de teste.",
        "natureza_revisao": "material",
        "vigente": True,
        "publicado_em": "2026-06-01T12:00:00+00:00",
    }


def _banco() -> _Banco:
    """P1 e P2 são do Núcleo; P3 e P4, do segundo Colegiado."""
    return _Banco(
        {
            "colegiados": [{"id": "col-nsp", "slug": NUCLEO.slug}, {"id": "col-comite", "slug": COMITE.slug}],
            "participantes": [_pessoa(pid) for pid in ("P1", "P2", "P3", "P4")],
            "participacoes": [
                _participacao("P1", "col-nsp", papel="presidencia"),
                _participacao("P2", "col-nsp"),
                _participacao("P3", "col-comite", papel="presidencia"),
                _participacao("P4", "col-comite"),
            ],
            "participacoes_trilha": [],
            NUCLEO.documentos: [_regimento("nucleo")],
            NUCLEO.termos_envios: [],
            NUCLEO.documentos_envios: [],
            COMITE.documentos: [_regimento("comite")],
            COMITE.termos_envios: [],
            COMITE.documentos_envios: [],
        }
    )


def _pessoas(linhas: list[dict]) -> set[str]:
    return {linha["participante_id"] for linha in linhas}


# ═══════════════════════════════════════════════════════════════════════════
# Membros e Participações vigentes
# ═══════════════════════════════════════════════════════════════════════════


class TestMembrosPorColegiado:
    def test_os_membros_de_um_colegiado_nao_aparecem_no_outro(self):
        banco = _banco()
        nucleo_id = colegiados.id_do_colegiado(banco, NUCLEO)
        comite_id = colegiados.id_do_colegiado(banco, COMITE)

        assert (nucleo_id, comite_id) == ("col-nsp", "col-comite")
        assert _pessoas(colegiados.participacoes_do_colegiado(banco, nucleo_id)) == {"P1", "P2"}
        assert _pessoas(colegiados.participacoes_do_colegiado(banco, comite_id)) == {"P3", "P4"}
        assert _pessoas(colegiados.participacoes_vigentes(banco, comite_id, HOJE).execute().data) == {"P3", "P4"}
        assert colegiados.participacao_do_colegiado(banco, comite_id, "part-col-nsp-P2") is None
        assert colegiados.participacao_do_colegiado(banco, comite_id, "part-col-comite-P4")["participante_id"] == "P4"

    def test_o_vinculo_vigente_e_so_o_do_colegiado_pedido(self):
        banco = _banco()

        assert colegiados.vinculo_vigente(banco, COMITE, "P3", HOJE) == ("presidencia", True)
        assert colegiados.vinculo_vigente(banco, COMITE, "P1", HOJE) == (None, False)
        assert colegiados.vinculo_vigente(banco, NUCLEO, "P1", HOJE) == ("presidencia", True)


# ═══════════════════════════════════════════════════════════════════════════
# O Termo de Adesão
# ═══════════════════════════════════════════════════════════════════════════


def _participacao_do_comite(banco, pid: str) -> dict:
    return colegiados.participacao_do_colegiado(banco, "col-comite", f"part-col-comite-{pid}")


class TestTermoPorColegiado:
    def test_o_termo_do_segundo_colegiado_vai_para_as_tabelas_dele(self, assinatura, modelos):
        banco = _banco()

        envio = termo.novo_termo(banco, _participacao_do_comite(banco, "P4"), autor_id="P3", colegiado=COMITE)

        assert envio["situacao"] == "enviado"
        assert [e["id"] for e in banco.tabelas[COMITE.termos_envios]] == [envio["id"]]
        assert banco.tabelas[NUCLEO.termos_envios] == []
        assert envio["regimento_id"] == "regimento-comite"
        assert assinatura.envelopes == [f"Termo de Adesão CT - {envio['id']}"]
        assert assinatura.arquivos == [f"Termo_de_Adesao_CT_{envio['id']}.pdf"]
        assert modelos == ["comite_termo_adesao.html"]
        assert (settings.supabase_storage_bucket_anexos_tecnologia, f"termos/{envio['id']}.pdf") in banco.arquivos

    def test_a_assinatura_do_termo_do_segundo_colegiado_fica_nos_documentos_dele(self):
        banco = _banco()
        participacao = _participacao_do_comite(banco, "P4")
        envio = termo.novo_termo(banco, participacao, autor_id="P3", colegiado=COMITE)

        termo.processar_evento(banco, envio, "sign", colegiado=COMITE)

        assert banco.tabelas[COMITE.termos_envios][0]["situacao"] == "assinado"
        termos = [d["termo_envio_id"] for d in banco.tabelas[COMITE.documentos] if d["tipo"] == "termo"]
        assert termos == [envio["id"]]
        assert [d["tipo"] for d in banco.tabelas[NUCLEO.documentos]] == ["regimento"]
        assert termo.ultimo_envio(banco, participacao["id"], colegiado=COMITE)["id"] == envio["id"]
        assert termo.ultimo_envio(banco, participacao["id"], colegiado=NUCLEO) is None

    def test_a_revisao_material_do_segundo_colegiado_so_alcanca_os_membros_dele(self):
        banco = _banco()

        termo.termos_da_revisao_material(banco, autor_id="P3", colegiado=COMITE)

        alcancados = {e["participacao_id"] for e in banco.tabelas[COMITE.termos_envios]}
        assert alcancados == {"part-col-comite-P3", "part-col-comite-P4"}
        assert banco.tabelas[NUCLEO.termos_envios] == []

    def test_a_revisao_material_e_lida_dos_documentos_do_colegiado(self):
        banco = _banco()
        banco.tabelas[COMITE.documentos][0]["publicado_em"] = "2026-09-01T12:00:00+00:00"

        assert termo.revisao_material_em(banco, colegiado=COMITE) == "2026-09-01T12:00:00+00:00"
        assert termo.revisao_material_em(banco, colegiado=NUCLEO) == "2026-06-01T12:00:00+00:00"
