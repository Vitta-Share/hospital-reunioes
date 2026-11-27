"""A migration 236 da espera do Pedido de implantação num Postgres de verdade
(issue #2208, ADR 0111, decisão 8).

O Pedido ganha a coluna `espera_pedido_id`, o Pedido que ele espera. Só o
Pedido de implantação espera, nunca a si mesmo, e o esperado precisa existir.
Sobe um Postgres descartável, aplica a 211, a 232, a 235 e a 236 (a 236 duas
vezes) e prova no banco.

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
]
MIGRATION = PASTA / "236_pedido_espera_outro.sql"

PEDIDOS = "tecnologia_perguntas"
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
NAO_EXISTE = "9c3d4e5f-6a7b-4c8d-8e9f-1a2b3c4d5e6f"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54236"
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


def _pedido(banco, *, tipo="implantacao", espera="NULL", id_="gen_random_uuid()"):
    return banco.sql(
        f"INSERT INTO {PEDIDOS} (id, demanda_id, assunto, texto, por_que_precisa, o_que_esta_parado,"
        " o_que_anda_depois, ganho, tipo, card_projeto, card_numero, passos, estado, espera_pedido_id) VALUES ("
        f"{id_}, '{DEMANDA}', 'abrir o Canal', 'Teste', 'a', 'b', 'c', 'd', '{tipo}', 'hospital', 1853,"
        f" '[\"passo 1\", \"passo 2\"]'::jsonb, 'aberta', {espera}) RETURNING id;",
        papel="service_role",
    )


def _id(resultado) -> str:
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout.strip().splitlines()[0].strip()


def test_o_pedido_de_implantacao_grava_o_pedido_que_ele_espera(banco):
    esperado = _id(_pedido(banco))
    assert _pedido(banco, espera=f"'{esperado}'").returncode == 0


def test_sem_espera_tudo_continua_valendo(banco):
    assert _pedido(banco).returncode == 0
    assert _pedido(banco, tipo="passo_a_passo").returncode == 0


def test_so_o_pedido_de_implantacao_espera(banco):
    esperado = _id(_pedido(banco))
    assert _pedido(banco, tipo="passo_a_passo", espera=f"'{esperado}'").returncode != 0


def test_o_pedido_nao_espera_a_si_mesmo(banco):
    proprio = "'5d4e5f6a-7b8c-4d9e-8f0a-1b2c3d4e5f6a'"
    assert _pedido(banco, id_=proprio, espera=proprio).returncode != 0


def test_o_esperado_precisa_existir(banco):
    assert _pedido(banco, espera=f"'{NAO_EXISTE}'").returncode != 0


def test_o_recibo_e_o_236():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.rstrip().endswith(
        "INSERT INTO migracoes_aplicadas (numero) VALUES (236) ON CONFLICT (numero) DO NOTHING;"
    )
