"""A limpeza dos testes da Ouvidoria (issue #1962, PRD #1913, ADR 0102).

O script de `scripts/oneshot/limpeza_testes_ouvidoria.py` confere a janela,
lista o que sai, tira os arquivos do bucket e gera o SQL avulso que uma pessoa
roda à mão. A escolha do que sai é uma função pura; o resto passa por um
cliente falso do PostgREST e um bucket falso. Nada aqui fala com banco de
verdade.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.oneshot import limpeza_testes_ouvidoria as limpeza  # noqa: E402
from scripts.oneshot.limpeza_testes_ouvidoria import Avaliacao, Caso, escolher  # noqa: E402

# Os dois limites da janela, escritos à mão a partir da issue: 19/10/2026 à 0h
# de Brasília e 17/11/2026 às 18h31min43s de Brasília (21:31:43 UTC).
INICIO = datetime(2026, 10, 19, 3, 0, 0, tzinfo=UTC)
FIM = datetime(2026, 11, 17, 21, 31, 43, tzinfo=UTC)
MEIO = datetime(2026, 11, 1, 15, 0, 0, tzinfo=UTC)
UM_MICRO = timedelta(microseconds=1)


def _avaliacoes(n: int, quando: datetime = MEIO) -> list[Avaliacao]:
    return [Avaliacao(id=f"av-{i}", criada_em=quando) for i in range(n)]


def _caso(protocolo: str = "2026-0101", **campos) -> Caso:
    base = {
        "id": f"id-{protocolo}",
        "protocolo": protocolo,
        "canal": "qr",
        "t0": MEIO,
        "estado": "em_classificacao",
        "anonimo": False,
    }
    base.update(campos)
    return Caso(**base)


class TestJanela:
    def test_avaliacao_no_primeiro_instante_da_janela_entra_e_a_de_um_instante_antes_fica(self):
        escolha = escolher(
            [Avaliacao("dentro", INICIO), Avaliacao("antes", INICIO - UM_MICRO)],
            [],
        )
        assert [a.id for a in escolha.avaliacoes] == ["dentro"]

    def test_avaliacao_no_ultimo_segundo_da_janela_entra_e_a_do_segundo_seguinte_fica(self):
        escolha = escolher(
            [
                Avaliacao("no_fim", FIM),
                Avaliacao("fim_do_segundo", FIM + timedelta(microseconds=999_999)),
                Avaliacao("depois", FIM + timedelta(seconds=1)),
            ],
            [],
        )
        assert [a.id for a in escolha.avaliacoes] == ["no_fim", "fim_do_segundo"]

    def test_caso_conta_pelo_t0_nos_dois_limites(self):
        casos = [
            _caso("2026-0001", t0=INICIO - UM_MICRO),
            _caso("2026-0002", t0=INICIO),
            _caso("2026-0003", t0=FIM),
            _caso("2026-0004", t0=FIM + timedelta(seconds=1)),
        ]
        escolha = escolher(_avaliacoes(5), casos)
        assert [c.protocolo for c in escolha.saem] == ["2026-0002", "2026-0003"]


class TestTravaDosCinco:
    def test_cinco_avaliacoes_na_janela_deixam_seguir(self):
        escolha = escolher(_avaliacoes(5), [_caso()])
        assert escolha.pode_seguir
        assert not escolha.trava_dos_cinco

    @pytest.mark.parametrize("quantas", [0, 4, 6])
    def test_numero_de_avaliacoes_diferente_de_cinco_trava(self, quantas):
        escolha = escolher(_avaliacoes(quantas), [_caso()])
        assert escolha.trava_dos_cinco
        assert not escolha.pode_seguir

    def test_avaliacao_fora_da_janela_nao_conta_para_os_cinco(self):
        fora = _avaliacoes(1, quando=FIM + timedelta(days=1))
        escolha = escolher(_avaliacoes(4) + fora, [])
        assert escolha.trava_dos_cinco

    def test_zero_avaliacoes_e_zero_casos_e_limpeza_ja_feita_e_nao_trava(self):
        fora = [_caso(t0=FIM + timedelta(days=2))]
        escolha = escolher(_avaliacoes(2, quando=INICIO - timedelta(days=1)), fora)
        assert escolha.ja_feita
        assert not escolha.trava_dos_cinco
        assert not escolha.pode_seguir


class TestForaDoPadrao:
    @pytest.mark.parametrize("canal", ["qr", "site"])
    def test_caso_do_qr_ou_do_site_sem_nada_ligado_sai_sem_pergunta(self, canal):
        escolha = escolher(_avaliacoes(5), [_caso(canal=canal)])
        assert escolha.pendentes == []
        assert [c.protocolo for c in escolha.saem] == ["2026-0101"]

    @pytest.mark.parametrize(
        ("campos", "trecho"),
        [
            ({"canal": "telefone"}, "não veio do QR nem do site"),
            ({"emails": ("email-1",)}, "e-mail recebido"),
            ({"acionamentos": 1}, "acionamento"),
            ({"links_de_setor": 2}, "link de setor"),
            ({"no_nucleo": True}, "Núcleo de Segurança do Paciente"),
            ({"no_canal_de_conduta": True}, "Canal de Conduta"),
        ],
    )
    def test_cada_motivo_de_fora_do_padrao_segura_o_caso_ate_a_decisao(self, campos, trecho):
        escolha = escolher(_avaliacoes(5), [_caso("2026-0200", **campos), _caso("2026-0201")])
        assert [p.protocolo for p in escolha.pendentes] == ["2026-0200"]
        assert any(trecho in motivo for motivo in escolha.pendentes[0].motivos)
        assert not escolha.pode_seguir

    def test_caso_com_dois_motivos_mostra_os_dois(self):
        escolha = escolher(_avaliacoes(5), [_caso("2026-0200", canal="email", emails=("e1",))])
        assert len(escolha.pendentes[0].motivos) == 2

    def test_liberar_leva_o_caso_fora_do_padrao_junto(self):
        caso = _caso("2026-0200", canal="whatsapp", emails=("email-1",))
        escolha = escolher(_avaliacoes(5), [caso, _caso("2026-0201")], liberar=["2026-0200"])
        assert escolha.pode_seguir
        assert [c.protocolo for c in escolha.saem] == ["2026-0200", "2026-0201"]

    def test_manter_deixa_o_caso_fora_do_padrao_no_banco(self):
        caso = _caso("2026-0200", acionamentos=1)
        escolha = escolher(_avaliacoes(5), [caso, _caso("2026-0201")], manter=["2026-0200"])
        assert escolha.pode_seguir
        assert [c.protocolo for c in escolha.saem] == ["2026-0201"]
        assert [c.protocolo for c in escolha.ficam] == ["2026-0200"]

    @pytest.mark.parametrize("campos", [{"no_nucleo": True}, {"no_canal_de_conduta": True}])
    def test_caso_ligado_a_outro_modulo_nao_aceita_liberar(self, campos):
        """A notificação do Núcleo e o caso do Canal de Conduta têm trilha e
        filhas próprias, e esta limpeza não alcança outro módulo: o caso só
        pode ficar."""
        escolha = escolher(_avaliacoes(5), [_caso("2026-0200", **campos)], liberar=["2026-0200"])
        assert not escolha.pode_seguir
        assert any("2026-0200" in erro for erro in escolha.erros)

    def test_protocolo_que_nao_esta_na_janela_e_erro_de_digitacao(self):
        escolha = escolher(_avaliacoes(5), [_caso("2026-0201")], manter=["2026-9999"])
        assert not escolha.pode_seguir
        assert any("2026-9999" in erro for erro in escolha.erros)

    def test_mesmo_protocolo_em_liberar_e_manter_e_erro(self):
        caso = _caso("2026-0200", canal="telefone")
        escolha = escolher(_avaliacoes(5), [caso], liberar=["2026-0200"], manter=["2026-0200"])
        assert not escolha.pode_seguir
        assert any("2026-0200" in erro for erro in escolha.erros)


CASO_A = "11111111-1111-1111-1111-111111111111"
CASO_B = "22222222-2222-2222-2222-222222222222"
EMAIL_A = "33333333-3333-3333-3333-333333333333"
AVALIACAO_A = "44444444-4444-4444-4444-444444444444"


def _plano() -> limpeza.Plano:
    esperado = {tabela: 1 for tabela, _ in limpeza.TABELAS_APAGADAS}
    esperado["ouvidoria_protocolos"] = 2
    esperado["ouvidoria_avaliacoes"] = 1
    return limpeza.Plano(
        casos=(CASO_A, CASO_B),
        emails=(EMAIL_A,),
        avaliacoes=(AVALIACAO_A,),
        esperado=esperado,
    )


class TestSqlGerado:
    def test_sql_mira_os_ids_conferidos_e_nao_as_datas_da_janela(self):
        sql = limpeza.gerar_sql(_plano())
        for id_ in (CASO_A, CASO_B, EMAIL_A, AVALIACAO_A):
            assert id_ in sql
        for data in ("2026-10-19", "2026-11-17", "contato_em", "criada_em"):
            assert data not in sql

    def test_sql_roda_numa_transacao_e_religa_os_gatilhos_antes_do_fim(self):
        sql = limpeza.gerar_sql(_plano())
        begin = sql.index("BEGIN;")
        commit = sql.index("COMMIT;")
        for gatilho in ("trg_ouvidoria_movimentos_sem_delete", "trg_ouvidoria_acessos_sem_delete"):
            desliga = sql.index(f"DISABLE TRIGGER {gatilho}")
            religa = sql.index(f"ENABLE TRIGGER {gatilho}")
            assert begin < desliga < sql.index("DELETE FROM") < religa < commit
        # Termina mostrando, depois do COMMIT, que os dois gatilhos estão ligados.
        assert sql.index("FROM pg_trigger") > commit

    def test_sql_apaga_filhas_depois_casos_depois_avaliacoes(self):
        sql = limpeza.gerar_sql(_plano())
        filhas = max(sql.index(f"DELETE FROM {t} ") for t, _ in limpeza.TABELAS_APAGADAS)
        casos = sql.index("DELETE FROM ouvidoria_protocolos ")
        avaliacoes = sql.index("DELETE FROM ouvidoria_avaliacoes ")
        assert filhas < casos < avaliacoes

    def test_sql_confere_cada_contagem_e_levanta_erro_se_nao_bater(self):
        plano = _plano()
        plano.esperado["ouvidoria_movimentos"] = 7
        sql = limpeza.gerar_sql(plano)
        trecho = sql[sql.index("DELETE FROM ouvidoria_movimentos ") :]
        trecho = trecho[: trecho.index("END IF;")]
        assert "GET DIAGNOSTICS" in trecho
        assert "<> 7" in trecho
        assert "RAISE EXCEPTION" in trecho

    def test_sql_nao_toca_na_sequence_dos_protocolos(self):
        sql = limpeza.gerar_sql(_plano()).lower()
        for proibido in ("numero_seq", "setval", "sequence", "truncate"):
            assert proibido not in sql
