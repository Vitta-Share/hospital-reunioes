"""A migration 208, os prazos do caso e a tabela de prazos do Núcleo, num
Postgres de verdade (issue #1993).

Sobe um Postgres descartável, aplica a 208 duas vezes sobre o mínimo de antes
e prova no banco:

- a carga da tabela é a do art. 26 do Regimento, e nenhum marco legal cabe nela;
- alterar uma célula grava o histórico (quem, quando, de e para) no mesmo
  update, e o histórico só cresce;
- uma linha de notificação externa por caso, só com VigiMed ou NOTIVISA;
- as tabelas novas têm RLS ligada, nenhuma policy, e o anon e o authenticated
  não leem nada, mesmo com o GRANT padrão do Supabase.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.seguranca_do_paciente import prazos  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "208_nsp_prazos_do_caso.sql"

TABELAS_NOVAS = (
    "nsp_tabela_de_prazos",
    "nsp_tabela_de_prazos_historico",
    "nsp_prazos_do_caso",
    "nsp_notificacoes_externas",
)

# O mínimo de antes da 208: os papéis do Supabase, o recibo, quem altera e a
# notificação a que o prazo pertence.
ESQUEMA_ANTERIOR = """
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN NOSUPERUSER BYPASSRLS;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;

CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);
CREATE TABLE participantes (id VARCHAR(10) PRIMARY KEY, nome_completo TEXT);
INSERT INTO participantes (id, nome_completo) VALUES ('P1', 'Presidência de Teste');
CREATE TABLE nsp_notificacoes (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a tabela de prazos no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54208"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso(banco) -> str:
    return banco.ok("INSERT INTO nsp_notificacoes DEFAULT VALUES RETURNING id;").splitlines()[-1]


def test_a_migration_cria_as_quatro_tabelas():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql)) == sorted(TABELAS_NOVAS)
    assert "VALUES (208) ON CONFLICT" in sql


def test_a_carga_da_tabela_e_a_do_art_26(banco):
    linhas = banco.ok(
        "SELECT faixa || '|' || marco || '|' || coalesce(valor::text, '') || '|' || coalesce(unidade, '') "
        "FROM nsp_tabela_de_prazos ORDER BY faixa, marco;"
    ).splitlines()
    no_banco = {}
    for linha in linhas:
        faixa, marco, valor, unidade = linha.split("|")
        if valor:
            no_banco[(faixa, marco)] = (int(valor), unidade)
    assert len(linhas) == 30
    assert no_banco == {celula: (p.valor, p.unidade) for celula, p in prazos.ART_26.items()}
    # Três células conferidas contra o Regimento, não contra o código.
    assert no_banco[("A", "triagem")] == (4, "horas_uteis")
    assert no_banco[("A", "conclusao_da_investigacao")] == (45, "dias_corridos")
    assert ("C", "reuniao_de_analise") not in no_banco


@pytest.mark.parametrize("marco", prazos.MARCOS_LEGAIS)
def test_nenhum_marco_legal_cabe_na_tabela(banco, marco):
    r = banco.sql(
        "INSERT INTO nsp_tabela_de_prazos (faixa, marco, valor, unidade) "
        f"VALUES ('A', '{marco}', 96, 'horas_corridas');",
        papel="service_role",
    )
    assert "check" in r.stderr.lower()


def test_alterar_a_celula_grava_quem_quando_de_e_para(banco):
    banco.ok(
        "UPDATE nsp_tabela_de_prazos SET valor = 3, unidade = 'horas_uteis', atualizado_por = 'P1' "
        "WHERE faixa = 'A' AND marco = 'triagem';",
        papel="service_role",
    )
    registro = banco.ok(
        "SELECT de_valor || '|' || de_unidade || '|' || para_valor || '|' || para_unidade || '|' || alterado_por "
        "|| '|' || (alterado_em IS NOT NULL) FROM nsp_tabela_de_prazos_historico "
        "WHERE faixa = 'A' AND marco = 'triagem';"
    )
    assert registro == "4|horas_uteis|3|horas_uteis|P1|true"


def test_salvar_o_mesmo_valor_nao_grava_historico(banco):
    banco.ok(
        "UPDATE nsp_tabela_de_prazos SET atualizado_por = 'P1' WHERE faixa = 'B' AND marco = 'triagem';",
        papel="service_role",
    )
    assert banco.ok("SELECT count(*) FROM nsp_tabela_de_prazos_historico WHERE faixa = 'B';") == "0"


@pytest.mark.parametrize(
    "comando",
    ["UPDATE nsp_tabela_de_prazos_historico SET para_valor = 1;", "DELETE FROM nsp_tabela_de_prazos_historico;"],
    ids=["UPDATE", "DELETE"],
)
def test_o_historico_so_cresce(banco, comando):
    banco.ok(
        "UPDATE nsp_tabela_de_prazos SET valor = 6, unidade = 'dias_uteis', atualizado_por = 'P1' "
        "WHERE faixa = 'E' AND marco = 'triagem';",
        papel="service_role",
    )
    r = banco.sql(comando, papel="service_role")
    assert "só cresce" in r.stderr


def test_a_celula_da_tabela_nao_se_apaga(banco):
    r = banco.sql("DELETE FROM nsp_tabela_de_prazos WHERE faixa = 'D';", papel="service_role")
    assert "não se apaga" in r.stderr


def test_uma_linha_de_notificacao_externa_por_caso_e_so_vigimed_ou_notivisa(banco):
    caso = _caso(banco)
    linha = "INSERT INTO nsp_notificacoes_externas (notificacao_id, sistema, prazo_legal) VALUES ('{c}', '{s}', now());"
    banco.ok(linha.format(c=caso, s="vigimed"), papel="service_role")

    assert "duplicate key" in banco.sql(linha.format(c=caso, s="notivisa"), papel="service_role").stderr
    assert "check" in banco.sql(linha.format(c=_caso(banco), s="email"), papel="service_role").stderr.lower()
    assert banco.ok(f"SELECT estado FROM nsp_notificacoes_externas WHERE notificacao_id = '{caso}';") == "pendente"


def test_o_prazo_do_caso_e_um_por_marco(banco):
    caso = _caso(banco)
    linha = (
        "INSERT INTO nsp_prazos_do_caso (notificacao_id, marco, tipo, valor, unidade, contado_de, vence_em) "
        f"VALUES ('{caso}', 'notificacao_externa', 'legal', 72, 'horas_corridas', now(), now() + interval '72 hours');"
    )
    banco.ok(linha, papel="service_role")
    assert "duplicate key" in banco.sql(linha, papel="service_role").stderr


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_toda_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{tabela}';") == "0"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_o_anon_e_o_authenticated_nao_leem_a_tabela(banco, papel):
    assert banco.ok("SELECT count(*) FROM nsp_tabela_de_prazos;", papel=papel) == "0"
