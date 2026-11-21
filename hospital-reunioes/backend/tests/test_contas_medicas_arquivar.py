"""Arquivar por Competência e desarquivar em Contas médicas (issue #1958, PRD #1933, ADR 0105).

A conta concluída ganha um carimbo de quando e quem arquivou, e a situação
fica como está (decisão 7). As Concluídas aparecem agrupadas por
Competência, o mês do fim do período da conta (decisão 6), e a etapa
Arquivadas guarda as que saíram da Esteira. A faturista arquiva as dela; quem
tem "painel completo" arquiva qualquer uma e o mês inteiro (decisão 8).

O dublê do banco é o da rota da fila. Os rótulos de paciente e os nomes de
pessoa são inventados.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_contas_medicas_envio import (  # noqa: E402
    ROTA_FILA,
    _c,
    _cenario,
    _cliente,
    _reset_rate_limiter,  # noqa: F401 (fixture autouse do envio)
)

from app.services.contas_medicas.competencia import competencia  # noqa: E402

MIGRATION_176 = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "176_contas_medicas_arquivar_por_competencia.sql"
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. A migration
# ═══════════════════════════════════════════════════════════════════════════


class TestAMigration:
    def test_acrescenta_o_carimbo_com_a_pessoa_set_null_e_o_indice_parcial_e_so_acrescenta(self):
        sql = re.sub(r"--[^\n]*", "", MIGRATION_176.read_text(encoding="utf-8"))

        assert re.findall(r"ALTER TABLE cm_conta\s+ADD COLUMN IF NOT EXISTS (\w+) ([\w()]+)", sql) == [
            ("arquivada_em", "TIMESTAMPTZ"),
            ("arquivada_por", "VARCHAR(10)"),
        ]
        assert re.search(r"arquivada_por VARCHAR\(10\) REFERENCES participantes\(id\) ON DELETE SET NULL;", sql), (
            "a pessoa que arquivou sai com ON DELETE SET NULL"
        )
        assert re.search(
            r"CREATE INDEX IF NOT EXISTS \w+\s+ON cm_conta \([^)]*\)\s+WHERE arquivada_em IS NULL;", sql
        ), "falta o índice parcial das não arquivadas"
        # Só acrescenta: nada de DROP, DELETE, UPDATE, ALTER COLUMN nem CHECK novo na situação.
        sem_on_delete = sql.replace("ON DELETE SET NULL", "")
        assert not re.search(r"\b(DROP|DELETE|UPDATE|ALTER COLUMN|RENAME|TRUNCATE)\b", sem_on_delete, flags=re.I)
        assert "situacao_check" not in sql


# ═══════════════════════════════════════════════════════════════════════════
# 2. A Competência
# ═══════════════════════════════════════════════════════════════════════════


class TestACompetencia:
    def test_e_o_mes_do_fim_do_periodo_da_conta(self):
        conta = {
            "periodo_inicio": "2026-09-28",
            "periodo_fim": "2026-10-03",
            "concluida_em": "2026-11-04T13:00:00+00:00",
        }

        assert competencia(conta) == "2026-10"

    def test_sem_periodo_e_o_mes_da_conclusao_no_fuso_do_hospital_na_virada_do_mes(self):
        """Concluída às 22h de 31 de outubro em Bangu: no UTC já é 1º de novembro."""
        conta = {"periodo_inicio": None, "periodo_fim": None, "concluida_em": "2026-11-01T01:00:00+00:00"}

        assert competencia(conta) == "2026-10"

    def test_sem_periodo_nem_conclusao_nao_tem_competencia(self):
        assert competencia({"periodo_fim": None, "concluida_em": None}) is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. As Concluídas por Competência
# ═══════════════════════════════════════════════════════════════════════════

ARQUIVADA_EM = "2026-11-10T12:00:00+00:00"


def _id(nome: str) -> str:
    """A rota pede UUID no caminho: cada conta do teste tem um, tirado do nome."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, nome))


def _nome(conta: dict) -> str:
    return conta["numero_conta"].removeprefix("conta-")


def _nomes(contas: list[dict]) -> list[str]:
    return [_nome(c) for c in contas]


def _concluida(nome: str, ordem: int, fim: str | None, faturista="F1", situacao="CONCLUIDA", **campos) -> dict:
    conta = _c(
        nome,
        situacao,
        ordem,
        faturista=faturista,
        periodo_inicio=fim and fim[:8] + "01",
        periodo_fim=fim,
        concluida_em="2026-11-05T15:00:00+00:00",
        **campos,
    )
    return conta | {"id": _id(nome)}


def _esteira_com_arquivadas():
    """Concluídas de outubro e de novembro, de F1 e de F2. A "out-arquivada"
    já saiu da Esteira; a "sem-periodo" cai no mês da conclusão (novembro)."""
    contas = [
        _concluida("out-f1", 1, "2026-10-20"),
        _concluida("out-f2-pendencia", 2, "2026-10-28", faturista="F2", situacao="CONCLUIDA_COM_PENDENCIA"),
        _concluida("out-arquivada", 3, "2026-10-15", arquivada_em=ARQUIVADA_EM, arquivada_por="F1"),
        _concluida("nov-f1", 4, "2026-11-02"),
        _concluida("sem-periodo", 5, None, faturista="F2"),
        _c("em-correcao", "EM_CORRECAO", 6, faturista="F1"),
    ]
    atendimentos = [{"id": c["atendimento_id"], "numero_atendimento": f"40{n:03d}"} for n, c in enumerate(contas)]
    return _cenario(cm_conta=contas, cm_atendimento=atendimentos)


def _conta(banco, nome: str) -> dict:
    return next(c for c in banco.tabelas["cm_conta"] if _nome(c) == nome)


class TestAsConcluidasPorCompetencia:
    def test_vem_sem_as_arquivadas_cada_uma_com_a_competencia(self):
        corpo = _cliente("faturista", _esteira_com_arquivadas()).get(ROTA_FILA).json()

        assert [(_nome(c), c["competencia"]) for c in corpo["concluidas"]] == [
            ("sem-periodo", "2026-11"),
            ("nov-f1", "2026-11"),
            ("out-f2-pendencia", "2026-10"),
            ("out-f1", "2026-10"),
        ]

    def test_a_contagem_das_concluidas_nao_conta_as_arquivadas_e_a_das_arquivadas_conta(self):
        corpo = _cliente("faturista", _esteira_com_arquivadas()).get(ROTA_FILA).json()

        assert corpo["contagem"]["concluidas"] == 4
        assert corpo["contagem"]["arquivadas"] == 1
        assert corpo["contagem_minhas"]["concluidas"] == 2

    def test_sem_o_teto_das_100_mais_recentes_mesmo_com_o_max_rows_do_banco(self):
        banco = _esteira_com_arquivadas()
        banco.tabelas["cm_conta"] += [
            _concluida(f"muitas-{n}", 100 + n, "2026-09-10", faturista="F2") for n in range(150)
        ]
        banco.max_rows = 100

        corpo = _cliente("faturista", banco).get(ROTA_FILA).json()

        assert len(corpo["concluidas"]) == 154

    def test_a_lista_sem_teto_le_os_dados_de_cada_conta_em_lotes_que_cabem_na_url(self):
        """Centenas de UUIDs num `in_` estouram o header do proxy: sem o teto da
        lista, os atendimentos, as linhas e os prontuários vêm em lotes."""
        banco = _esteira_com_arquivadas()
        novas = [_concluida(f"muitas-{n}", 100 + n, "2026-09-10", faturista="F2") for n in range(250)]
        banco.tabelas["cm_conta"] += novas
        banco.tabelas["cm_atendimento"] += [
            {"id": c["atendimento_id"], "numero_atendimento": f"5{n:04d}"} for n, c in enumerate(novas)
        ]
        banco.teto_do_in = 100

        resposta = _cliente("faturista", banco).get(ROTA_FILA)

        assert resposta.status_code == 200, resposta.text
        numeros = {_nome(c): c["numero_atendimento"] for c in resposta.json()["concluidas"]}
        assert numeros["muitas-249"] == "50249"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Arquivar uma conta
# ═══════════════════════════════════════════════════════════════════════════


def _arquivar(quem: str, banco, nome: str):
    return _cliente(quem, banco).post(f"/api/contas-medicas/contas/{_id(nome)}/arquivar")


def _desarquivar(quem: str, banco, nome: str):
    return _cliente(quem, banco).post(f"/api/contas-medicas/contas/{_id(nome)}/desarquivar")


class TestArquivarUmaConta:
    @pytest.mark.parametrize("nome", ["out-f1", "nov-f1"])
    def test_a_faturista_arquiva_a_conta_concluida_em_que_e_a_faturista(self, nome):
        banco = _esteira_com_arquivadas()

        resposta = _arquivar("faturista", banco, nome)

        assert resposta.status_code == 200, resposta.text
        conta = _conta(banco, nome)
        assert conta["arquivada_por"] == "F1"
        assert conta["arquivada_em"]
        # Arquivar é um carimbo, não uma situação (decisão 7).
        assert conta["situacao"] == "CONCLUIDA"

    def test_a_faturista_arquiva_a_concluida_com_pendencia_dela(self):
        banco = _esteira_com_arquivadas()
        _conta(banco, "out-f2-pendencia")["faturista_id"] = "F1"

        assert _arquivar("faturista", banco, "out-f2-pendencia").status_code == 200
        assert _conta(banco, "out-f2-pendencia")["situacao"] == "CONCLUIDA_COM_PENDENCIA"

    def test_a_faturista_nao_arquiva_a_conta_de_outra_faturista_e_a_recusa_vem_com_uma_frase(self):
        banco = _esteira_com_arquivadas()

        resposta = _arquivar("faturista", banco, "out-f2-pendencia")

        assert resposta.status_code == 403
        assert resposta.json()["detail"] == "Esta conta é de outra faturista. Só quem tem o painel completo arquiva."
        assert _conta(banco, "out-f2-pendencia").get("arquivada_em") is None

    def test_quem_tem_o_painel_completo_arquiva_a_conta_de_qualquer_faturista(self):
        banco = _esteira_com_arquivadas()

        assert _arquivar("coordenadora", banco, "out-f2-pendencia").status_code == 200
        assert _conta(banco, "out-f2-pendencia")["arquivada_por"] == "CO"

    @pytest.mark.parametrize("situacao", ["EM_CORRECAO", "RETORNO", "A_FAZER"])
    def test_so_a_conta_concluida_se_arquiva(self, situacao):
        banco = _esteira_com_arquivadas()
        _conta(banco, "out-f1")["situacao"] = situacao

        resposta = _arquivar("coordenadora", banco, "out-f1")

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "Só a conta concluída se arquiva."
        assert _conta(banco, "out-f1").get("arquivada_em") is None

    def test_a_conta_ja_arquivada_nao_se_arquiva_de_novo(self):
        banco = _esteira_com_arquivadas()

        resposta = _arquivar("faturista", banco, "out-arquivada")

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "Esta conta já está arquivada."
        assert _conta(banco, "out-arquivada")["arquivada_em"] == ARQUIVADA_EM

    def test_a_conta_que_nao_existe_da_404(self):
        assert _arquivar("faturista", _esteira_com_arquivadas(), "nao-existe").status_code == 404

    def test_a_arquivada_sai_das_concluidas_e_entra_na_contagem_das_arquivadas(self):
        banco = _esteira_com_arquivadas()
        _arquivar("faturista", banco, "out-f1")

        corpo = _cliente("faturista", banco).get(ROTA_FILA).json()

        assert "out-f1" not in _nomes(corpo["concluidas"])
        assert (corpo["contagem"]["concluidas"], corpo["contagem"]["arquivadas"]) == (3, 2)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Arquivar o mês
# ═══════════════════════════════════════════════════════════════════════════


def _arquivar_o_mes(quem: str, banco, mes: str):
    return _cliente(quem, banco).post(f"/api/contas-medicas/competencias/{mes}/arquivar")


def _arquivadas(banco) -> set[str]:
    return {_nome(c) for c in banco.tabelas["cm_conta"] if c.get("arquivada_em")}


class TestArquivarOMes:
    def test_a_faturista_arquiva_so_as_dela_daquela_competencia(self):
        banco = _esteira_com_arquivadas()
        _conta(banco, "out-f2-pendencia")["faturista_id"] = "F2"

        resposta = _arquivar_o_mes("faturista", banco, "2026-10")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {"arquivadas": 1, "com_pendencia": 0}
        assert _arquivadas(banco) == {"out-arquivada", "out-f1"}
        assert _conta(banco, "out-f1")["arquivada_por"] == "F1"

    def test_quem_tem_o_painel_completo_arquiva_a_competencia_inteira_com_as_de_pendencia(self):
        banco = _esteira_com_arquivadas()

        resposta = _arquivar_o_mes("coordenadora", banco, "2026-10")

        assert resposta.json() == {"arquivadas": 2, "com_pendencia": 1}
        assert _arquivadas(banco) == {"out-arquivada", "out-f1", "out-f2-pendencia"}
        # A situação fica: a de pendência segue Concluída com pendência.
        assert _conta(banco, "out-f2-pendencia")["situacao"] == "CONCLUIDA_COM_PENDENCIA"

    def test_a_conta_sem_periodo_entra_no_mes_da_conclusao(self):
        banco = _esteira_com_arquivadas()

        assert _arquivar_o_mes("coordenadora", banco, "2026-11").json() == {"arquivadas": 2, "com_pendencia": 0}
        assert _arquivadas(banco) == {"out-arquivada", "nov-f1", "sem-periodo"}

    def test_o_mes_sem_conta_arquiva_nenhuma(self):
        banco = _esteira_com_arquivadas()

        assert _arquivar_o_mes("faturista", banco, "2026-08").json() == {"arquivadas": 0, "com_pendencia": 0}
        assert _arquivadas(banco) == {"out-arquivada"}

    @pytest.mark.parametrize("mes", ["2026-13", "outubro", "2026-1"])
    def test_a_competencia_fora_do_formato_e_recusada(self, mes):
        assert _arquivar_o_mes("coordenadora", _esteira_com_arquivadas(), mes).status_code == 422

    def test_o_mes_com_centenas_de_contas_arquiva_em_lotes_que_cabem_na_url(self):
        banco = _esteira_com_arquivadas()
        banco.tabelas["cm_conta"] += [_concluida(f"setembro-{n}", 100 + n, "2026-09-10") for n in range(250)]
        banco.teto_do_in = 100

        resposta = _arquivar_o_mes("faturista", banco, "2026-09")

        assert resposta.json() == {"arquivadas": 250, "com_pendencia": 0}


# ═══════════════════════════════════════════════════════════════════════════
# 6. A etapa Arquivadas e o desarquivar
# ═══════════════════════════════════════════════════════════════════════════

ROTA_ARQUIVADAS = "/api/contas-medicas/arquivadas"


class TestArquivadas:
    def test_a_lista_traz_as_arquivadas_de_todas_com_a_competencia_e_com_quem_esta(self):
        banco = _esteira_com_arquivadas()
        _arquivar("coordenadora", banco, "out-f2-pendencia")

        corpo = _cliente("faturista", banco).get(ROTA_ARQUIVADAS).json()

        assert [(_nome(c), c["competencia"], c["com"], c["minha"]) for c in corpo["arquivadas"]] == [
            ("out-arquivada", "2026-10", "Pessoa F1", True),
            ("out-f2-pendencia", "2026-10", "Pessoa F2", False),
        ]
        assert corpo["todas"] is False

    def test_a_faturista_desarquiva_a_dela_e_a_conta_volta_para_as_concluidas(self):
        banco = _esteira_com_arquivadas()

        resposta = _desarquivar("faturista", banco, "out-arquivada")

        assert resposta.status_code == 200, resposta.text
        conta = _conta(banco, "out-arquivada")
        assert (conta["arquivada_em"], conta["arquivada_por"], conta["situacao"]) == (None, None, "CONCLUIDA")
        assert "out-arquivada" in _nomes(_cliente("faturista", banco).get(ROTA_FILA).json()["concluidas"])

    def test_a_faturista_nao_desarquiva_a_de_outra(self):
        banco = _esteira_com_arquivadas()
        _conta(banco, "out-arquivada")["faturista_id"] = "F2"

        resposta = _desarquivar("faturista", banco, "out-arquivada")

        assert resposta.status_code == 403
        assert resposta.json()["detail"] == "Esta conta é de outra faturista. Só quem tem o painel completo desarquiva."
        assert _conta(banco, "out-arquivada")["arquivada_em"] == ARQUIVADA_EM

    def test_quem_tem_o_painel_completo_desarquiva_qualquer_uma(self):
        banco = _esteira_com_arquivadas()
        _conta(banco, "out-arquivada")["faturista_id"] = "F2"

        assert _desarquivar("coordenadora", banco, "out-arquivada").status_code == 200
        assert _conta(banco, "out-arquivada")["arquivada_em"] is None

    def test_a_conta_que_nao_esta_arquivada_nao_se_desarquiva(self):
        resposta = _desarquivar("faturista", _esteira_com_arquivadas(), "out-f1")

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "Esta conta não está arquivada."

    @pytest.mark.parametrize("quem", ["credenciamento", "sem_eixo"])
    def test_sem_analisar_contas_as_rotas_do_arquivar_dao_403(self, quem):
        banco = _esteira_com_arquivadas()
        cliente = _cliente(quem, banco)

        assert cliente.get(ROTA_ARQUIVADAS).status_code == 403
        assert cliente.post(f"/api/contas-medicas/contas/{_id('out-f1')}/arquivar").status_code == 403
        assert cliente.post("/api/contas-medicas/competencias/2026-10/arquivar").status_code == 403
        assert _arquivadas(banco) == {"out-arquivada"}


# ═══════════════════════════════════════════════════════════════════════════
# 7. O kit de conhecimento
# ═══════════════════════════════════════════════════════════════════════════

KIT = Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "contas-medicas.md"


class TestOKitDizOArquivar:
    def test_diz_a_competencia_quem_arquiva_o_desarquivar_e_o_retorno(self):
        secao = KIT.read_text(encoding="utf-8").split("## O envio e a fila", 1)[1].split("\n## ", 1)[0]
        paragrafo = next(p for p in secao.split("\n\n") if p.startswith("Arquivar tira a conta"))

        for trecho in (
            "já foi tratada no MV",
            '"Arquivar o mês"',
            "quantas têm pendência",
            "Painel completo arquiva qualquer uma",
            "**Arquivadas**",
            '"Desarquivar"',
            "Retorno da Validação volta sozinha",
            "A busca também acha a conta arquivada",
        ):
            assert trecho in paragrafo, trecho
        assert "fim do período da conta" in secao
        # O teto das 100 mais recentes saiu (issue #1958).
        assert "100 que a lista mostra" not in secao
