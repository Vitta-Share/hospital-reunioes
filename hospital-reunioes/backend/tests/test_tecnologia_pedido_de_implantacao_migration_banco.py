"""A migration 235 do Pedido de implantação num Postgres de verdade (issue
#2207, ADR 0111).

O tipo `implantacao` passa a valer na coluna do tipo do Pedido da Vitta, com
as mesmas regras do Passo a passo: o card e de 2 a 15 passos, e os estados
aberta, concluida e cancelada. Sobe um Postgres descartável, aplica a 211, a
232 e a 235 (a 235 duas vezes) e prova no banco.

Sem `initdb` na máquina o teste pula; no CI ele falha.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres
from test_tecnologia_perguntas_migration_banco import ESQUEMA_ANTERIOR

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION_211 = PASTA / "211_tecnologia_pergunta_da_vitta.sql"
MIGRATION_232 = PASTA / "232_pedido_da_vitta_passo_a_passo.sql"
MIGRATION = PASTA / "235_pedido_de_implantacao.sql"

PEDIDOS = "tecnologia_perguntas"
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54235"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_211.read_text(encoding="utf-8"))
        pg.ok(MIGRATION_232.read_text(encoding="utf-8"))
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _pedido(banco, *, tipo="implantacao", estado="aberta", passos=2, card="1853"):
    lista = ", ".join(f'"passo {i}"' for i in range(passos))
    return banco.sql(
        f"INSERT INTO {PEDIDOS} (demanda_id, assunto, texto, por_que_precisa, o_que_esta_parado,"
        " o_que_anda_depois, ganho, tipo, card_projeto, card_numero, passos, estado) VALUES ("
        f"'{DEMANDA}', 'testar o Canal', 'Teste', 'a', 'b', 'c', 'd', '{tipo}', 'hospital', {card},"
        f" '[{lista}]'::jsonb, '{estado}') RETURNING id;",
        papel="service_role",
    )


@pytest.mark.parametrize("estado", ["aberta", "concluida", "cancelada"])
def test_o_pedido_de_implantacao_entra_nos_estados_do_passo_a_passo(banco, estado):
    r = _pedido(banco, estado=estado)
    assert r.returncode == 0, r.stderr


def test_o_pedido_de_implantacao_nao_e_respondido(banco):
    assert _pedido(banco, estado="respondida").returncode != 0


@pytest.mark.parametrize(
    "campos",
    [{"card": "NULL"}, {"passos": 1}, {"passos": 16}],
    ids=["sem-card", "um-passo-so", "dezesseis-passos"],
)
def test_o_pedido_de_implantacao_sem_card_ou_com_passos_fora_de_2_a_15_e_recusado(banco, campos):
    assert _pedido(banco, **campos).returncode != 0


def test_os_dois_tipos_de_antes_continuam_valendo_e_outro_tipo_nao(banco):
    assert _pedido(banco, tipo="passo_a_passo").returncode == 0
    assert _pedido(banco, tipo="pergunta", passos=0, estado="respondida").returncode == 0
    assert _pedido(banco, tipo="tarefa").returncode != 0


def test_o_recibo_e_o_235():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.rstrip().endswith(
        "INSERT INTO migracoes_aplicadas (numero) VALUES (235) ON CONFLICT (numero) DO NOTHING;"
    )
