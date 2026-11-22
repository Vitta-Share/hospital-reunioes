"""A migration 218, a reunião de análise e os avisos da confirmação, num
Postgres de verdade (issue #1994).

Sobe um Postgres descartável, aplica a 218 duas vezes sobre o mínimo de antes
e prova no banco:

- os marcos da comunicação à Direção e do aviso de caso em análise entram
  somados aos que a constraint já aceitava, inclusive um que outra migration
  da leva tenha somado antes;
- o aviso de caso em análise vai a quem notificou sem cadastro, como a
  confirmação de recebimento, um por caso; o resto continua com destinatário;
- a reunião de análise é uma por caso.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

from app.services.seguranca_do_paciente import ao_confirmar

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "218_nsp_reuniao_de_analise_e_avisos_da_confirmacao.sql"
)
CASO = "00000000-0000-0000-0000-000000000001"

# O mínimo de antes: o registro de e-mail com as constraints da 182 e um marco
# que outra migration da leva teria somado antes desta, e a tabela de reuniões.
ESQUEMA_ANTERIOR = """
DO $$ BEGIN
  CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE TABLE participantes (id VARCHAR(10) PRIMARY KEY);
CREATE TABLE nsp_notificacoes (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);
CREATE TABLE reunioes (id_reuniao VARCHAR(20) PRIMARY KEY);
CREATE TABLE nsp_avisos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participacao_id UUID,
  caso_id UUID,
  marco TEXT NOT NULL,
  referencia TEXT NOT NULL DEFAULT 'NSP-2026-0001',
  destinatario_id VARCHAR(10) REFERENCES participantes(id)
);
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check
  CHECK (marco IN ('documento_gerado', 'assinatura_3', 'assinatura_7', 'assinatura_14',
                   'vigencia_60', 'vigencia_30', 'fim_da_carencia', 'convocacao',
                   'caso_grave', 'confirmacao_de_recebimento', 'marco_de_uma_irma'));
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_destinatario_check
  CHECK (destinatario_id IS NOT NULL OR (marco = 'confirmacao_de_recebimento' AND caso_id IS NOT NULL));
CREATE UNIQUE INDEX uq_nsp_avisos_confirmacao ON nsp_avisos (caso_id, marco, referencia)
  WHERE destinatario_id IS NULL;
INSERT INTO participantes VALUES ('P1');
INSERT INTO nsp_notificacoes (id) VALUES ('00000000-0000-0000-0000-000000000001');
INSERT INTO nsp_notificacoes (id) VALUES ('00000000-0000-0000-0000-000000000002');
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration da confirmação no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54218"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _aviso(banco, marco: str, destinatario: str | None = "'P1'", caso: str = CASO):
    return banco.sql(
        "INSERT INTO nsp_avisos (caso_id, marco, destinatario_id) "
        f"VALUES ('{caso}', '{marco}', {destinatario or 'NULL'});",
        papel="service_role",
    )


@pytest.mark.parametrize(
    "marco", [*ao_confirmar.MARCOS, "caso_grave", "marco_de_uma_irma"], ids=lambda m: m.replace("_", " ")
)
def test_os_marcos_da_confirmacao_entram_somados_aos_que_ja_valiam(banco, marco):
    assert _aviso(banco, marco).returncode == 0, marco


def test_o_marco_inventado_continua_recusado(banco):
    assert "nsp_avisos_marco_check" in _aviso(banco, "marco_inventado").stderr


def test_o_aviso_de_caso_em_analise_vai_a_quem_notificou_sem_cadastro_uma_vez_por_caso(banco):
    outro = "00000000-0000-0000-0000-000000000002"
    assert _aviso(banco, ao_confirmar.MARCO_DO_EM_ANALISE, None, outro).returncode == 0
    assert "uq_nsp_avisos_confirmacao" in _aviso(banco, ao_confirmar.MARCO_DO_EM_ANALISE, None, outro).stderr


@pytest.mark.parametrize("marco", [ao_confirmar.MARCO_DA_DIRECAO, "caso_grave"])
def test_o_resto_continua_com_destinatario(banco, marco):
    assert "nsp_avisos_destinatario_check" in _aviso(banco, marco, None).stderr


def test_a_reuniao_de_analise_e_uma_por_caso(banco):
    assert (
        banco.sql(
            f"INSERT INTO reunioes (id_reuniao, nsp_caso_id) VALUES ('RD_1', '{CASO}');", papel="service_role"
        ).returncode
        == 0
    )
    assert banco.sql("INSERT INTO reunioes (id_reuniao) VALUES ('RD_2');", papel="service_role").returncode == 0
    assert banco.sql("INSERT INTO reunioes (id_reuniao) VALUES ('RD_3');", papel="service_role").returncode == 0
    repetida = banco.sql(
        f"INSERT INTO reunioes (id_reuniao, nsp_caso_id) VALUES ('RD_4', '{CASO}');", papel="service_role"
    )
    assert "uq_reunioes_nsp_caso" in repetida.stderr


def test_o_recibo_e_o_218(banco):
    assert banco.ok("SELECT numero FROM migracoes_aplicadas;") == "218"
