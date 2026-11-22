"""A verificação de retaliação do Canal de Conduta (issue #1839; especificação,
6.11 e 18; ADR 0097).

Cada classe é um critério de aceite da issue. O banco é o dublê de
`conduta_apoio`, a cifra é de verdade, e o caso chega ao fim pelo caminho de
verdade: o retorno editado e aprovado pela coordenação. A data do
encerramento é então recuada no dublê, no fuso de São Paulo, para o teste
olhar o dia 29, 30, 90 e 180 sem esperar.
"""

from __future__ import annotations

import base64
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conduta_apoio import UNICAS
from fastapi.testclient import TestClient
from test_conduta_medida_e_retorno import (
    BASE,
    COORDENACAO,
    MEMBRO,
    ComiteEDirecao,
    _denunciante_ouvido,
    _editar,
)

from app.config import settings
from app.routers import conduta_retaliacao
from app.services.conduta import cifra
from app.services.conhecimento import CONHECIMENTO_DIR

FUSO = ZoneInfo("America/Sao_Paulo")
TABELA = "conduta_verificacoes_de_retaliacao"
ACAO = "Verificar se houve retaliação"


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())


@pytest.fixture(autouse=True)
def _unica(monkeypatch):
    # A chave única da migration 227: uma verificação por marco do caso.
    monkeypatch.setitem(UNICAS, TABELA, ("caso_id", "marco"))


class ComiteDaVerificacao(ComiteEDirecao):
    def cliente(self, pid: str) -> TestClient:
        cliente = super().cliente(pid)
        cliente.app.include_router(conduta_retaliacao.router, prefix="/api")
        return cliente

    def encerrado(self, *, identificado: bool = True, ha_dias: int = 0) -> str:
        """Um caso improcedente concluído pelo retorno aprovado, encerrado há
        `ha_dias` dias (no fuso de São Paulo)."""
        caso = self.concluido("improcedente", medida=None)
        if identificado:
            _denunciante_ouvido(self, caso)
        assert _editar(self, caso).status_code == 200
        assert self.post(COORDENACAO, f"/casos/{caso}/retorno/aprovacao").status_code == 200
        self.recuar(caso, ha_dias)
        return caso

    def recuar(self, caso: str, ha_dias: int) -> None:
        self.linha_do_caso(caso)["encerrado_em"] = (datetime.now(FUSO) - timedelta(days=ha_dias)).isoformat()

    def minha_vez(self, pid: str = COORDENACAO) -> list[dict]:
        resposta = self.cliente(pid).get(f"{BASE}/minha-vez")
        assert resposta.status_code == 200, resposta.text
        return resposta.json()["itens"]

    def da_verificacao(self, caso: str, pid: str = COORDENACAO) -> list[dict]:
        return [i for i in self.minha_vez(pid) if i["id"] == caso and i["acao"].startswith(ACAO)]

    def verificar(self, caso: str, marco: int, houve: bool = False, observacao: str = "", pid: str = COORDENACAO):
        return self.post(
            pid, f"/casos/{caso}/verificacoes-de-retaliacao", {"marco": marco, "houve": houve, "observacao": observacao}
        )


@pytest.fixture
def comite() -> ComiteDaVerificacao:
    return ComiteDaVerificacao()


# ═══════════════════════════════════════════════════════════════════════════
# As três tarefas aparecem em MINHA VEZ da coordenação nas datas certas
# ═══════════════════════════════════════════════════════════════════════════


class TestTarefasNasDatasCertas:
    def test_a_primeira_aparece_no_dia_30_e_nao_antes(self, comite):
        caso = comite.encerrado(ha_dias=29)
        assert comite.da_verificacao(caso) == []

        comite.recuar(caso, 30)

        (item,) = comite.da_verificacao(caso)
        assert item["acao"] == f"{ACAO} (30 dias)"
        assert item["etapa"] == "acompanhamento"
        assert item["faltam_dias"] == 0
        assert item["prazo_vencido"] is False
