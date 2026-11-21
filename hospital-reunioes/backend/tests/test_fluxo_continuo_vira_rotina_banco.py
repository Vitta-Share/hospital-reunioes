"""O fluxo contínuo antigo vira Rotina, num Postgres de verdade (issue #1877, migration 190).

Usa o Postgres descartável de `test_pendencia_historico_banco.py`: monta as
tabelas de antes, aplica a 169 (Histórico) e a 177 (Rotina), carrega
Pendências antigas e aplica a 190 duas vezes. Prova no banco que:

- a Pendência aberta e sem prazo cuja linha no quadro da Ata diz "Fluxo
  contínuo" vira Rotina sem frequência, e a Pendência é encerrada;
- cada Pendência convertida ganha um evento no Histórico apontando para a
  Rotina;
- rodar de novo não cria Rotina duplicada nem evento a mais;
- a sem prazo que não casa com o quadro continua Pendência aberta.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from test_pendencia_historico_banco import ESQUEMA_ANTERIOR, _bin_do_postgres, _Postgres  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION_190 = MIGRATIONS / "190_fluxo_continuo_vira_rotina.sql"

CARGA = """
ALTER TABLE pendencias ADD COLUMN responsavel_nome TEXT;
INSERT INTO participantes (id, nome_completo) VALUES ('P2', 'Ana Lima');

INSERT INTO reunioes (id_reuniao, json_ata) VALUES
  ('R1', '{"quadro_atribuicoes": [
      {"acao": "Revisar escala", "prazo": "Fluxo contínuo"},
      {"acao": "Comprar luvas", "prazo": "a definir"},
      {"acao": "Conferir estoque", "prazo": "fluxo continuo"},
      {"acao": "Pintar sala", "prazo": "2026-12-01"}
  ]}'),
  ('R2', '{"atribuicoes": [{"acao": "Lavar o carro", "prazo": "Fluxo Contínuo"}]}'),
  ('R3', '{"quadro_atribuicoes": [{"acao": "Ronda", "prazo": "Fluxo contínuo"}]}');

-- A Rotina que já nasceu do envio da Ata na mesma posição.
INSERT INTO rotinas (id, id_reuniao, quadro_pos, descricao, responsavel_nome, frequencia, comeca_em)
  VALUES ('00000000-0000-0000-0000-000000000003', 'R3', 0, 'Ronda', '', 'SEMANAL', '2026-11-23');

INSERT INTO pendencias
  (id_acao, id_reuniao, descricao_acao, responsavel_id, responsavel_nome, prazo, status, quadro_pos) VALUES
  ('A101', 'R1', 'Revisar escala',   'P2', 'Ana Lima', NULL,         'PENDENTE',     0),
  ('A102', 'R1', 'Comprar luvas',    'P2', 'Ana Lima', NULL,         'PENDENTE',     1),
  ('A103', 'R1', 'Conferir estoque', NULL, 'Bruno',    NULL,         'EM_PROGRESSO', 2),
  ('A104', 'R1', 'Revisar escala',   'P2', 'Ana Lima', NULL,         'CONCLUIDO',    0),
  ('A105', 'R1', 'Pintar sala',      'P2', 'Ana Lima', NULL,         'PENDENTE',     3),
  ('A106', 'R2', 'Lavar o carro',    'P2', 'Ana Lima', NULL,         'PENDENTE',     NULL),
  ('A107', 'R1', 'Conferir estoque', 'P2', 'Ana Lima', '2026-12-10', 'PENDENTE',     2),
  ('A108', 'R3', 'Ronda',            'P2', 'Ana Lima', NULL,         'PENDENTE',     0);
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a conversão no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54190"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok((MIGRATIONS / "169_ciclo_de_vida_da_pendencia.sql").read_text(encoding="utf-8"))
        pg.ok((MIGRATIONS / "177_rotina_e_verificacao.sql").read_text(encoding="utf-8"))
        pg.ok(CARGA)
        sql = MIGRATION_190.read_text(encoding="utf-8")
        pg.ok(sql)
        pg.ok(sql)  # rodar de novo não duplica nada
        yield pg
    finally:
        pg.descer()


def _status(banco, id_acao: str) -> str:
    return banco.ok(f"SELECT status FROM pendencias WHERE id_acao = '{id_acao}';")


def test_fluxo_continuo_aberto_e_sem_prazo_vira_rotina_sem_frequencia(banco):
    linha = banco.ok(
        "SELECT descricao, responsavel_id, responsavel_nome, coalesce(frequencia, '-'), "
        "coalesce(comeca_em::text, '-'), status FROM rotinas WHERE id_reuniao = 'R1' AND quadro_pos = 0;"
    )

    assert linha == "Revisar escala|P2|Ana Lima|-|-|ATIVA"
    assert _status(banco, "A101") == "CANCELADO"


def test_a_pendencia_em_progresso_e_a_sem_posicao_no_quadro_tambem_viram_rotina(banco):
    assert banco.ok("SELECT responsavel_nome FROM rotinas WHERE id_reuniao = 'R1' AND quadro_pos = 2;") == "Bruno"
    # A Pendência de antes do `quadro_pos` casa pelo texto da ação.
    assert banco.ok("SELECT descricao FROM rotinas WHERE id_reuniao = 'R2' AND quadro_pos = 0;") == "Lavar o carro"
    assert _status(banco, "A103") == "CANCELADO"
    assert _status(banco, "A106") == "CANCELADO"


def test_a_conversao_e_idempotente(banco):
    # A 190 rodou duas vezes na fixture.
    assert banco.ok("SELECT count(*) FROM rotinas;") == "4"
    assert banco.ok("SELECT count(*) FROM rotinas WHERE id_reuniao = 'R3';") == "1"
    assert banco.ok("SELECT count(*) FROM pendencia_historico WHERE comando = 'migracao';") == "4"


@pytest.mark.parametrize(
    ("id_acao", "id_reuniao", "posicao"),
    [("A101", "R1", 0), ("A103", "R1", 2), ("A106", "R2", 0), ("A108", "R3", 0)],
)
def test_cada_pendencia_convertida_ganha_um_evento_apontando_para_a_rotina(banco, id_acao, id_reuniao, posicao):
    evento = banco.ok(
        "SELECT h.comando, h.status_depois, h.autor_nome, h.rotina_id = r.id "
        "FROM pendencia_historico h JOIN rotinas r ON r.id_reuniao = '" + id_reuniao + "' "
        f"AND r.quadro_pos = {posicao} WHERE h.id_acao = '{id_acao}';"
    )

    assert evento == "migracao|CANCELADO|Sistema|t"
    anotacao = banco.ok(f"SELECT anotacao FROM pendencia_historico WHERE id_acao = '{id_acao}';")
    assert "Rotina" in anotacao


@pytest.mark.parametrize(
    "id_acao",
    [
        "A102",  # sem prazo, mas a linha do quadro diz "a definir"
        "A105",  # sem prazo, e a linha do quadro tem data
        "A104",  # fluxo contínuo, mas já concluída
        "A107",  # fluxo contínuo, mas com prazo
    ],
)
def test_o_que_nao_casa_continua_pendencia_sem_evento(banco, id_acao):
    assert _status(banco, id_acao) != "CANCELADO"
    assert banco.ok(f"SELECT count(*) FROM pendencia_historico WHERE id_acao = '{id_acao}';") == "0"
