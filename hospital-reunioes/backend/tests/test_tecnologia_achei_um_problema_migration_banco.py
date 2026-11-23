"""A migration 237 do Achei um problema num Postgres de verdade (issue #2210,
ADR 0111, decisão 9).

A Demanda ganha o Pedido de que o bug veio e a Demanda de origem; o Pedido
ganha a Demanda de bug que ele espera. Só o Pedido de implantação espera uma
Demanda de bug, a Demanda nunca é a própria origem, e o que é apontado precisa
existir. Sobe um Postgres descartável, aplica a 211, a 232, a 235, a 236 e a
237 (a 237 duas vezes) e prova no banco.

Sem `initdb` na máquina o teste pula; no CI ele falha.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres
from test_tecnologia_perguntas_migration_banco import ESQUEMA_ANTERIOR

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
ANTERIORES = [
    PASTA / "211_tecnologia_pergunta_da_vitta.sql",
    PASTA / "232_pedido_da_vitta_passo_a_passo.sql",
    PASTA / "235_pedido_de_implantacao.sql",
    PASTA / "236_pedido_espera_outro.sql",
]
MIGRATION = PASTA / "237_achei_um_problema.sql"

DEMANDAS = "tecnologia_demandas"
PEDIDOS = "tecnologia_perguntas"
ENTREGA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
NAO_EXISTE = "9c3d4e5f-6a7b-4c8d-8e9f-1a2b3c4d5e6f"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54237"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        for anterior in ANTERIORES:
            pg.ok(anterior.read_text(encoding="utf-8"))
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _id(resultado) -> str:
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout.strip().splitlines()[0].strip()


def _bug(banco, *, pedido="NULL", origem="NULL", id_="gen_random_uuid()"):
    return banco.sql(
        f"INSERT INTO {DEMANDAS} (id, titulo, pedido_origem_id, demanda_origem_id) VALUES ("
        f"{id_}, 'O relato saiu com o nome', {pedido}, {origem}) RETURNING id;",
        papel="service_role",
    )


def _pedido(banco, *, tipo="implantacao", espera_demanda="NULL"):
    return banco.sql(
        f"INSERT INTO {PEDIDOS} (demanda_id, assunto, texto, por_que_precisa, o_que_esta_parado,"
        " o_que_anda_depois, ganho, tipo, card_projeto, card_numero, passos, estado, espera_demanda_id) VALUES ("
        f"'{ENTREGA}', 'testar o Canal', 'Teste', 'a', 'b', 'c', 'd', '{tipo}', 'hospital', 1853,"
        f" '[\"passo 1\", \"passo 2\"]'::jsonb, 'aberta', {espera_demanda}) RETURNING id;",
        papel="service_role",
    )


def test_o_bug_grava_o_pedido_e_a_demanda_de_origem_e_o_pedido_espera_o_bug(banco):
    pedido = _id(_pedido(banco))
    bug = _id(_bug(banco, pedido=f"'{pedido}'", origem=f"'{ENTREGA}'"))

    resultado = banco.sql(
        f"UPDATE {PEDIDOS} SET espera_demanda_id = '{bug}' WHERE id = '{pedido}';", papel="service_role"
    )

    assert resultado.returncode == 0, resultado.stderr


def test_sem_origem_tudo_continua_valendo(banco):
    assert _bug(banco).returncode == 0
    assert _pedido(banco, tipo="passo_a_passo").returncode == 0


def test_so_o_pedido_de_implantacao_espera_uma_demanda_de_bug(banco):
    bug = _id(_bug(banco))
    assert _pedido(banco, tipo="passo_a_passo", espera_demanda=f"'{bug}'").returncode != 0


def test_a_demanda_nao_e_a_propria_origem(banco):
    propria = "'5d4e5f6a-7b8c-4d9e-8f0a-1b2c3d4e5f6a'"
    assert _bug(banco, id_=propria, origem=propria).returncode != 0


def test_o_que_e_apontado_precisa_existir(banco):
    assert _bug(banco, origem=f"'{NAO_EXISTE}'").returncode != 0
    assert _bug(banco, pedido=f"'{NAO_EXISTE}'").returncode != 0
    assert _pedido(banco, espera_demanda=f"'{NAO_EXISTE}'").returncode != 0


def test_o_recibo_e_o_237():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.rstrip().endswith(
        "INSERT INTO migracoes_aplicadas (numero) VALUES (237) ON CONFLICT (numero) DO NOTHING;"
    )
