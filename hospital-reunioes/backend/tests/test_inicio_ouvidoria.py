"""O caso da Ouvidoria do setor e a fila do ouvidor no Início (issue #1937,
PRD #1932, ADR 0099 e ADR 0104, decisão 6).

Titular, substituto e gestor vigentes veem na Minha Fila o caso acionado para o
setor deles que ainda espera a área, com o prazo do setor, e o botão abre a
Tela do responsável pela porta do login. O item não carrega relato nem
identificação: o título é o Assunto, ou o protocolo no caso sem Assunto e no
sigiloso. Quem tem Perfil da Ouvidoria vê uma linha de resumo da fila, fora da
frase e dos contadores.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers import inicio as inicio_router  # noqa: E402

BRT = ZoneInfo("America/Sao_Paulo")
# Quarta-feira, 18/11/2026, 10h em Brasília.
AGORA = datetime(2026, 11, 18, 10, 0, tzinfo=BRT)


# ─── O banco de mentira ───────────────────────────────────────────────────


@dataclass
class _Result:
    data: list


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []
        self._negar = False

    @property
    def not_(self):
        self._negar = True
        return self

    def _filtro(self, f):
        if self._negar:
            self._negar = False
            self._filtros.append(lambda linha: not f(linha))
        else:
            self._filtros.append(f)
        return self

    def select(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def range(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        return self._filtro(lambda linha: linha.get(coluna) == valor)

    def in_(self, coluna, valores):
        valores = set(valores)
        return self._filtro(lambda linha: linha.get(coluna) in valores)

    def is_(self, coluna, valor):
        assert valor == "null"
        return self._filtro(lambda linha: linha.get(coluna) is None)

    def ilike(self, coluna, padrao):
        assert "%" not in padrao and "_" not in padrao.replace("\\_", "")
        alvo = padrao.replace("\\", "").lower()
        return self._filtro(lambda linha: (linha.get(coluna) or "").lower() == alvo)

    def execute(self):
        return _Result([dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)])


@dataclass
class _Banco:
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    ouvidoria_setor_responsaveis: list = field(default_factory=list)
    ouvidoria_protocolos: list = field(default_factory=list)
    ouvidoria_prorrogacoes: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


def _responsavel(email: str, setor: str = "Recepção", papel: str = "titular", **campos) -> dict:
    base = {
        "setor": setor,
        "papel": papel,
        "email": email,
        "vigencia_inicio": "2026-01-01",
        "vigencia_fim": None,
    }
    return {**base, **campos}


def _caso(id_: str, setor: str = "Recepção", **campos) -> dict:
    base = {
        "id": id_,
        "numero": int(id_.strip("C") or 0),
        "protocolo": f"OUV-2026-{id_}",
        "setor": setor,
        "status": "aguardando_area",
        "validada_em": "2026-11-10T13:00:00+00:00",
        "prazo_area_em": "2026-11-19T20:00:00+00:00",
        "prazo_resposta": "2026-11-25",
        "assunto": f"Demora no atendimento {id_}",
        "resumo": "Resumo literal do relato",
        "relato_integral": "Relato integral de quem manifestou",
        "manifestante_nome": "Maria Manifestante",
        "sigilo_reforcado": False,
        "anonimo": False,
        "tipo_manifestacao": "reclamacao",
        "arquivada_em": None,
    }
    return {**base, **campos}


TITULAR = {"id": "P_TIT", "nome_completo": "Tânia Titular", "email": "tania@hsm.com.br", "access_profile": None}


def _rota(monkeypatch, me: dict | None, banco: _Banco, agora: datetime = AGORA):
    async def _participante(_user, _sb, fields=None):
        return me

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: agora)

    import asyncio

    return asyncio.run(inicio_router.get_inicio(current_user={"id": "u1"}, supabase=banco))


def _da_ouvidoria(resposta) -> list:
    return [item for item in resposta.itens if item.tipo == "caso_da_ouvidoria"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. O caso acionado para o setor de quem é responsável vigente
# ═══════════════════════════════════════════════════════════════════════════


class TestCasoDoSetor:
    def test_titular_ve_o_caso_do_setor_com_o_prazo_e_o_botao_da_tela_do_responsavel(self, monkeypatch):
        banco = _Banco(
            ouvidoria_setor_responsaveis=[_responsavel("Tania@HSM.com.br")],
            ouvidoria_protocolos=[_caso("C1")],
        )

        resposta = _rota(monkeypatch, TITULAR, banco)

        [item] = _da_ouvidoria(resposta)
        assert item.id == "C1"
        assert item.prazo == date(2026, 11, 19)
        assert item.grupo == "ate_48_horas"
        assert item.area == "Ouvidoria"
        assert item.destino == "/ouvidoria/responder/C1"
        assert item.acao == "Responder"

    def test_substituto_ve_o_caso_do_setor(self, monkeypatch):
        substituto = {**TITULAR, "id": "P_SUB", "email": "sergio@hsm.com.br"}
        banco = _Banco(
            ouvidoria_setor_responsaveis=[_responsavel("sergio@hsm.com.br", papel="substituto")],
            ouvidoria_protocolos=[_caso("C2")],
        )

        assert [item.id for item in _da_ouvidoria(_rota(monkeypatch, substituto, banco))] == ["C2"]

    def test_gestor_ve_o_caso_do_setor(self, monkeypatch):
        gestor = {**TITULAR, "id": "P_GES", "email": "gilda@hsm.com.br"}
        banco = _Banco(
            ouvidoria_setor_responsaveis=[_responsavel("gilda@hsm.com.br", papel="gestor")],
            ouvidoria_protocolos=[_caso("C3")],
        )

        assert [item.id for item in _da_ouvidoria(_rota(monkeypatch, gestor, banco))] == ["C3"]

    def test_responsavel_de_outro_setor_nao_ve_o_caso(self, monkeypatch):
        banco = _Banco(
            ouvidoria_setor_responsaveis=[_responsavel("tania@hsm.com.br", setor="Recepção")],
            ouvidoria_protocolos=[_caso("C4", setor="Recepção"), _caso("C5", setor="Farmácia")],
        )

        assert [item.id for item in _da_ouvidoria(_rota(monkeypatch, TITULAR, banco))] == ["C4"]

    def test_quem_teve_a_vigencia_encerrada_deixa_de_ver(self, monkeypatch):
        banco = _Banco(
            ouvidoria_setor_responsaveis=[_responsavel("tania@hsm.com.br", vigencia_fim="2026-11-17")],
            ouvidoria_protocolos=[_caso("C6")],
        )

        resposta = _rota(monkeypatch, TITULAR, banco)

        assert _da_ouvidoria(resposta) == []
        assert resposta.avisos == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. O item mostra o Assunto e nada de quem manifestou
# ═══════════════════════════════════════════════════════════════════════════


class TestSigiloDoItem:
    def _item(self, monkeypatch, caso: dict):
        banco = _Banco(ouvidoria_setor_responsaveis=[_responsavel("tania@hsm.com.br")], ouvidoria_protocolos=[caso])
        [item] = _da_ouvidoria(_rota(monkeypatch, TITULAR, banco))
        return item

    def test_o_titulo_e_o_assunto_e_o_item_nao_leva_relato_resumo_nem_manifestante(self, monkeypatch):
        item = self._item(monkeypatch, _caso("C10", assunto="Demora na recepção do pronto-socorro"))

        assert item.titulo == "Demora na recepção do pronto-socorro"
        texto = item.model_dump_json()
        assert "Resumo literal" not in texto
        assert "Relato integral" not in texto
        assert "Maria Manifestante" not in texto

    def test_caso_sem_assunto_mostra_o_protocolo(self, monkeypatch):
        item = self._item(monkeypatch, _caso("C11", assunto=None))

        assert item.titulo == "Manifestação OUV-2026-C11"

    def test_caso_sigiloso_mostra_o_protocolo_e_nao_o_assunto(self, monkeypatch):
        item = self._item(monkeypatch, _caso("C12", assunto="Denúncia sobre a chefia", sigilo_reforcado=True))

        assert item.titulo == "Manifestação OUV-2026-C12"
        assert "Denúncia" not in item.model_dump_json()


# ═══════════════════════════════════════════════════════════════════════════
# 3. O caso que já não espera a área sai da fila
# ═══════════════════════════════════════════════════════════════════════════


class TestSaiDaFila:
    def _ids(self, monkeypatch, casos: list[dict], prorrogacoes: list[dict] | None = None) -> list[str]:
        banco = _Banco(
            ouvidoria_setor_responsaveis=[_responsavel("tania@hsm.com.br")],
            ouvidoria_protocolos=casos,
            ouvidoria_prorrogacoes=prorrogacoes or [],
        )
        return sorted(item.id for item in _da_ouvidoria(_rota(monkeypatch, TITULAR, banco)))

    def test_caso_respondido_sai_da_fila(self, monkeypatch):
        assert self._ids(monkeypatch, [_caso("C20"), _caso("C21", status="respondido")]) == ["C20"]

    def test_caso_devolvido_a_ouvidoria_sai_da_fila(self, monkeypatch):
        assert self._ids(monkeypatch, [_caso("C22"), _caso("C23", status="em_classificacao")]) == ["C22"]

    def test_caso_com_prorrogacao_pedida_sai_da_fila(self, monkeypatch):
        prorrogacoes = [
            {"manifestacao_id": "C25", "status": "pendente"},
            {"manifestacao_id": "C26", "status": "aprovada"},
        ]

        assert self._ids(monkeypatch, [_caso("C24"), _caso("C25"), _caso("C26")], prorrogacoes) == ["C24", "C26"]

    def test_caso_ainda_nao_acionado_nao_entra(self, monkeypatch):
        assert self._ids(monkeypatch, [_caso("C27"), _caso("C28", validada_em=None)]) == ["C27"]
