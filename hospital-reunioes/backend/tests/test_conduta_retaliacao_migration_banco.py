"""A migration 227, a verificação de retaliação em 30, 90 e 180 dias, num
Postgres de verdade (issue #1839).

Sobe um Postgres descartável, aplica a 175, a 185, a 192, a 199, a 214, a
216, a 221, a 223 e a 227 (a 227 duas vezes) sobre o mínimo de antes e prova
no banco:

- a verificação é do caso concluído, uma por marco, e só a partir do dia
  dela, contado do encerramento no fuso de São Paulo;
- registrada, ela não muda nem se apaga; a única mudança é ligar, uma vez, o
  caso novo de retaliação, e só quando houve;
- a tabela nova tem RLS ligada, nenhuma policy, e o anon não lê.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from test_conduta_migration_banco import ESQUEMA_ANTERIOR
from test_conduta_migration_banco import MIGRATION as MIGRATION_175
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
ANTERIORES = (
    "185_conduta_triagem_e_ritos.sql",
    "192_conduta_assinaturas.sql",
    "199_conduta_avisos_por_email.sql",
    "214_conduta_rota_especial.sql",
    "216_conduta_voto_e_trava_de_robustez.sql",
    "221_conduta_ata_de_deliberacao.sql",
    "223_conduta_recomendacao_medida_e_retorno.sql",
)
MIGRATION = PASTA / "227_conduta_verificacao_de_retaliacao.sql"
TABELA = "conduta_verificacoes_de_retaliacao"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a verificação de retaliação no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54227"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        for nome in ANTERIORES:
            pg.ok((PASTA / nome).read_text(encoding="utf-8"))
        pg.ok("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;")
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _sql(banco, comando: str):
    return banco.sql(comando, papel="service_role")


def _caso(banco, *, ha_dias: int = 30, desfecho: str | None = "concluido") -> str:
    """Um caso encerrado há `ha_dias` dias, no fuso de São Paulo, ao meio-dia
    de lá: longe da virada do dia em UTC."""
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    desfecho_sql = f"'{desfecho}'" if desfecho else "NULL"
    encerrado = (
        f"(((now() AT TIME ZONE 'America/Sao_Paulo')::date - {ha_dias}) + time '12:00') "
        "AT TIME ZONE 'America/Sao_Paulo'"
    )
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa, rito, rota, desfecho, encerrado_em) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', 'encerrado', 'rapido', 'comum', {desfecho_sql}, {encerrado}) "
        "RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _verificar(banco, caso: str, marco: int = 30, houve: bool = False):
    return _sql(
        banco,
        f"INSERT INTO {TABELA} (caso_id, marco, houve, observacao_cifrada, verificada_por) "
        f"VALUES ('{caso}', {marco}, {str(houve).lower()}, 'v1:O', 'P1');",
    )


def test_a_migration_nao_esvazia_tabela():
    assert not re.search(r"\b(DROP\s+TABLE|DELETE\s+FROM)\b", MIGRATION.read_text(encoding="utf-8"), re.IGNORECASE)


def test_a_verificacao_e_do_caso_concluido_a_partir_do_dia_dela(banco):
    caso = _caso(banco, ha_dias=30)

    assert "a partir do dia dela" in _verificar(banco, caso, 90).stderr
    assert _verificar(banco, caso, 30).returncode == 0


def test_um_dia_antes_a_verificacao_e_recusada(banco):
    caso = _caso(banco, ha_dias=29)

    assert "a partir do dia dela" in _verificar(banco, caso, 30).stderr


@pytest.mark.parametrize("desfecho", [None, "encaminhado", "parecer_entregue"])
def test_o_caso_nao_concluido_nao_tem_verificacao(banco, desfecho):
    caso = _caso(banco, ha_dias=200, desfecho=desfecho)

    assert "caso concluído" in _verificar(banco, caso, 30).stderr


def test_uma_verificacao_por_marco(banco):
    caso = _caso(banco, ha_dias=200)

    assert _verificar(banco, caso, 30).returncode == 0
    assert "duplicate key" in _verificar(banco, caso, 30, houve=True).stderr
    assert "marco" in _verificar(banco, caso, 60).stderr


def test_a_verificacao_registrada_nao_muda_nem_se_apaga(banco):
    caso = _caso(banco, ha_dias=30)
    assert _verificar(banco, caso, 30, houve=True).returncode == 0

    assert "guardada" in _sql(banco, f"UPDATE {TABELA} SET houve = false WHERE caso_id = '{caso}';").stderr
    assert "guardada" in _sql(banco, f"DELETE FROM {TABELA} WHERE caso_id = '{caso}';").stderr


def test_o_caso_novo_liga_uma_vez_e_so_quando_houve(banco):
    caso, outro, terceiro = _caso(banco, ha_dias=30), _caso(banco, ha_dias=30), _caso(banco, ha_dias=30)
    assert _verificar(banco, caso, 30, houve=True).returncode == 0
    assert _verificar(banco, terceiro, 30, houve=False).returncode == 0

    ligar = f"UPDATE {TABELA} SET caso_novo_id = '{outro}' WHERE caso_id = '{{caso}}';"
    assert "caso_novo" in _sql(banco, ligar.format(caso=terceiro)).stderr
    assert _sql(banco, ligar.format(caso=caso)).returncode == 0
    assert "guardada" in _sql(banco, ligar.format(caso=caso)).stderr
    assert "guardada" in _sql(banco, f"UPDATE {TABELA} SET caso_novo_id = NULL WHERE caso_id = '{caso}';").stderr


def test_a_observacao_e_cifrada(banco):
    caso = _caso(banco, ha_dias=30)

    resultado = _sql(
        banco,
        f"INSERT INTO {TABELA} (caso_id, marco, houve, observacao_cifrada, verificada_por) "
        f"VALUES ('{caso}', 30, true, 'texto em claro', 'P1');",
    )

    assert "observacao_cifrada" in resultado.stderr


def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{TABELA}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{TABELA}';") == "0"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_o_anon_nao_le(banco, papel):
    assert "permission denied" in banco.sql(f"SELECT * FROM {TABELA};", papel=papel).stderr
