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

    def test_a_de_90_e_a_de_180_aparecem_cada_uma_no_seu_dia(self, comite):
        caso = comite.encerrado(ha_dias=30)
        assert comite.verificar(caso, 30).status_code == 200
        assert comite.da_verificacao(caso) == []

        comite.recuar(caso, 89)
        assert comite.da_verificacao(caso) == []
        comite.recuar(caso, 90)
        assert [i["acao"] for i in comite.da_verificacao(caso)] == [f"{ACAO} (90 dias)"]
        assert comite.verificar(caso, 90).status_code == 200

        comite.recuar(caso, 179)
        assert comite.da_verificacao(caso) == []
        comite.recuar(caso, 180)
        assert [i["acao"] for i in comite.da_verificacao(caso)] == [f"{ACAO} (180 dias)"]
        assert comite.verificar(caso, 180).status_code == 200
        comite.recuar(caso, 400)
        assert comite.da_verificacao(caso) == []

    def test_a_verificacao_atrasada_continua_na_lista_com_o_prazo_vencido_contado(self, comite):
        caso = comite.encerrado(ha_dias=95)

        (item,) = comite.da_verificacao(caso)

        assert item["acao"] == f"{ACAO} (30 dias)"
        assert item["faltam_dias"] == -65

    def test_so_a_coordenacao_tem_a_tarefa(self, comite):
        caso = comite.encerrado(ha_dias=30)

        assert comite.da_verificacao(caso, MEMBRO) == []
        caixa = comite.abrir(MEMBRO, caso)["o_que_fazer_agora"]
        assert caixa["botao"] == "REGISTRAR VERIFICAÇÃO"
        assert caixa["bloqueio"] == "Só a coordenação registra a verificação."

    def test_a_caixa_do_caso_pede_a_verificacao_no_dia(self, comite):
        caso = comite.encerrado(ha_dias=30)

        caixa = comite.abrir(COORDENACAO, caso)["o_que_fazer_agora"]

        assert caixa["frase"] == "Verifique se houve mudança desfavorável para quem relatou."
        assert caixa["botao"] == "REGISTRAR VERIFICAÇÃO"
        assert caixa["bloqueio"] is None


# ═══════════════════════════════════════════════════════════════════════════
# A verificação é registrada com um clique e observação opcional
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistroComUmClique:
    def test_um_clique_sem_observacao_registra(self, comite):
        caso = comite.encerrado(ha_dias=30)

        resposta = comite.verificar(caso, 30, houve=False)

        assert resposta.status_code == 200, resposta.text
        (linha,) = comite.banco.tabelas[TABELA]
        assert (linha["caso_id"], linha["marco"], linha["houve"]) == (caso, 30, False)
        assert linha["observacao_cifrada"] is None
        assert linha["verificada_por"] == COORDENACAO
        assert comite.trilha(caso)[-1]["acao"] == "verificou_retaliacao"

    def test_a_observacao_fica_cifrada_e_aparece_na_tela(self, comite):
        caso = comite.encerrado(ha_dias=30)
        observacao = "Consultei o DP: mesma escala e mesmo setor."

        assert comite.verificar(caso, 30, observacao=observacao).status_code == 200

        (linha,) = comite.banco.tabelas[TABELA]
        assert observacao not in str(linha)
        assert cifra.decifrar_texto(linha["observacao_cifrada"]) == observacao
        marcos = comite.abrir(COORDENACAO, caso)["verificacao_de_retaliacao"]["marcos"]
        assert [(m["marco"], m["situacao"], m["houve"], m["observacao"]) for m in marcos] == [
            (30, "verificada", False, observacao),
            (90, "aguardando", None, None),
            (180, "aguardando", None, None),
        ]
        assert marcos[0]["verificada_por"] == "Ana Coordenadora"

    def test_so_a_coordenacao_registra(self, comite):
        caso = comite.encerrado(ha_dias=30)

        assert comite.verificar(caso, 30, pid=MEMBRO).status_code == 403
        assert comite.banco.tabelas.get(TABELA, []) == []

    def test_antes_do_dia_e_depois_de_registrada_e_recusada(self, comite):
        caso = comite.encerrado(ha_dias=30)

        assert comite.verificar(caso, 90).status_code == 409
        assert comite.verificar(caso, 30).status_code == 200
        assert comite.verificar(caso, 30, houve=True).status_code == 409
        assert len(comite.banco.tabelas[TABELA]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Caso anônimo sem aviso do denunciante não gera tarefa
# ═══════════════════════════════════════════════════════════════════════════


class TestCasoAnonimoSemAviso:
    def test_o_caso_anonimo_sem_aviso_nao_gera_tarefa(self, comite):
        caso = comite.encerrado(identificado=False, ha_dias=30)

        assert comite.da_verificacao(caso) == []
        assert comite.abrir(COORDENACAO, caso)["verificacao_de_retaliacao"] is None
        assert comite.abrir(COORDENACAO, caso)["o_que_fazer_agora"]["botao"] is None
        assert comite.verificar(caso, 30).status_code == 409

    def test_o_caso_anonimo_em_que_o_denunciante_avisou_gera_tarefa(self, comite):
        caso = comite.encerrado(identificado=False, ha_dias=30)

        comite.linha_do_caso(caso)["denunciante_informou_em"] = "2026-11-20T12:00:00+00:00"

        assert [i["acao"] for i in comite.da_verificacao(caso)] == [f"{ACAO} (30 dias)"]

    def test_o_caso_sinalizado_pela_ouvidoria_com_nome_gera_tarefa(self, comite):
        caso = comite.encerrado(identificado=False, ha_dias=30)
        comite.linha_do_caso(caso).update({"origem": "ouvidoria", "manifestacao_id": "manif-1"})
        comite.banco.tabelas["ouvidoria_protocolos"] = [{"id": "manif-1", "manifestante_nome": "Marta Relatora"}]

        assert [i["acao"] for i in comite.da_verificacao(caso)] == [f"{ACAO} (30 dias)"]

    def test_o_caso_encaminhado_nao_gera_tarefa(self, comite):
        caso = comite.caso()
        _denunciante_ouvido(comite, caso)
        comite.linha_do_caso(caso).update(
            {"etapa": "encerrado", "desfecho": "encaminhado", "encerrado_em": "2026-01-01T12:00:00+00:00"}
        )

        assert comite.da_verificacao(caso) == []


# ═══════════════════════════════════════════════════════════════════════════
# A resposta "houve" oferece abrir um caso novo de retaliação
# ═══════════════════════════════════════════════════════════════════════════


def _abrir_caso_novo(comite, caso: str, marco: int = 30, pid: str = COORDENACAO):
    return comite.post(pid, f"/casos/{caso}/verificacoes-de-retaliacao/caso-novo", {"marco": marco})


class TestHouveAbreCasoNovo:
    def test_houve_oferece_abrir_o_caso_novo(self, comite):
        caso = comite.encerrado(ha_dias=30)

        comite.verificar(caso, 30, houve=True, observacao="Ela foi trocada de escala na semana seguinte.")

        (marco_30, *_) = comite.abrir(COORDENACAO, caso)["verificacao_de_retaliacao"]["marcos"]
        assert marco_30["houve"] is True
        assert marco_30["pode_abrir_caso_novo"] is True

    def test_nao_houve_nao_oferece(self, comite):
        caso = comite.encerrado(ha_dias=30)

        comite.verificar(caso, 30, houve=False)

        (marco_30, *_) = comite.abrir(COORDENACAO, caso)["verificacao_de_retaliacao"]["marcos"]
        assert marco_30["pode_abrir_caso_novo"] is False
        assert _abrir_caso_novo(comite, caso).status_code == 409

    def test_o_caso_novo_entra_na_triagem_ligado_a_verificacao(self, comite):
        caso = comite.encerrado(ha_dias=30)
        comite.verificar(caso, 30, houve=True, observacao="Ela foi trocada de escala na semana seguinte.")

        resposta = _abrir_caso_novo(comite, caso)

        assert resposta.status_code == 200, resposta.text
        novo = comite.linha_do_caso(resposta.json()["id"])
        assert novo["protocolo"] == resposta.json()["protocolo"] != comite.linha_do_caso(caso)["protocolo"]
        assert (novo["etapa"], novo["categoria"], novo["rota"]) == ("triagem", "A", "comum")
        relato = cifra.decifrar_texto(novo["relato_cifrado"])
        assert "retaliação" in relato
        assert comite.linha_do_caso(caso)["protocolo"] in relato
        assert "Ela foi trocada de escala na semana seguinte." in relato
        (marco_30, *_) = comite.abrir(COORDENACAO, caso)["verificacao_de_retaliacao"]["marcos"]
        assert marco_30["caso_novo"] == {"id": novo["id"], "protocolo": novo["protocolo"]}
        assert marco_30["pode_abrir_caso_novo"] is False
        assert "abriu_caso_de_retaliacao" in [t["acao"] for t in comite.trilha(caso)]

    def test_o_caso_novo_abre_uma_vez_e_so_pela_coordenacao(self, comite):
        caso = comite.encerrado(ha_dias=30)
        comite.verificar(caso, 30, houve=True)

        assert _abrir_caso_novo(comite, caso, pid=MEMBRO).status_code == 403
        assert _abrir_caso_novo(comite, caso).status_code == 200
        assert _abrir_caso_novo(comite, caso).status_code == 409
        assert len(comite.banco.tabelas["conduta_casos"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# O texto do Produto Canal de Conduta no kit de conhecimento diz o
# comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    @pytest.mark.parametrize(
        "trecho",
        [
            "30, 90 e 180 dias",
            "REGISTRAR VERIFICAÇÃO",
            "caso novo de retaliação",
            "Caso anônimo sem aviso de quem relatou não gera verificação",
        ],
    )
    def test_o_kit_diz_o_comportamento_novo(self, trecho):
        assert trecho in (CONHECIMENTO_DIR / "canal-de-conduta.md").read_text(encoding="utf-8")
