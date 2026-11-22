"""A migration 232 do Pedido da Vitta num Postgres de verdade (issue #2176,
ADR 0110).

A tabela da Pergunta da Vitta (migration 211) vira a do Pedido, com o tipo
(Pergunta ou Passo a passo), o card do Passo a passo, os passos, o estado
`concluida`, quem concluiu e como, e o fechamento no GitHub. Nasce a tabela
dos checks, que só cresce. Sobe um Postgres descartável, aplica a 211 e a 232
(a 232 duas vezes) e prova no banco:

- as linhas que já existem ficam Pergunta;
- o Passo a passo sem card ou com passos fora de 2 a 15 é recusado;
- a Pergunta não vira `concluida`, e o Passo a passo não vira `respondida`;
- as duas tabelas com RLS ligada e nenhuma policy;
- o histórico dos checks recusa UPDATE e DELETE, mas some com o Pedido.

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
MIGRATION = PASTA / "232_pedido_da_vitta_passo_a_passo.sql"

PEDIDOS = "tecnologia_perguntas"
CHECKS = "tecnologia_checks_do_pedido"
DEMANDA = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"

COLUNAS_NOVAS = {
    "tipo",
    "card_projeto",
    "card_numero",
    "passos",
    "concluida_por",
    "concluida_em_nome_de",
    "concluida_em",
    "concluida_como",
    "fechamento_github",
    "fechamento_motivo",
}


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54232"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_211.read_text(encoding="utf-8"))
        # A Pergunta de antes da 232: tem que ficar Pergunta.
        pg.ok(
            f"INSERT INTO {PEDIDOS} (id, demanda_id, assunto, texto, por_que_precisa, o_que_esta_parado,"
            " o_que_anda_depois, ganho) VALUES ('11111111-1111-4111-8111-111111111111',"
            f" '{DEMANDA}', 'a', 'b', 'c', 'd', 'e', 'f');"
        )
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _pedido(banco, *, tipo="passo_a_passo", estado="aberta", passos=2, card="1961"):
    lista = ", ".join(f'"passo {i}"' for i in range(passos))
    return banco.sql(
        f"INSERT INTO {PEDIDOS} (demanda_id, assunto, texto, por_que_precisa, o_que_esta_parado,"
        " o_que_anda_depois, ganho, tipo, card_projeto, card_numero, passos, estado) VALUES ("
        f"'{DEMANDA}', 'publicar o Regimento', 'Publique', 'a', 'b', 'c', 'd', '{tipo}', 'hospital', {card},"
        f" '[{lista}]'::jsonb, '{estado}') RETURNING id;",
        papel="service_role",
    )


def test_a_pergunta_que_ja_existia_fica_pergunta(banco):
    assert banco.ok(f"SELECT tipo FROM {PEDIDOS} WHERE id = '11111111-1111-4111-8111-111111111111';") == "pergunta"


def test_a_tabela_do_pedido_ganha_as_colunas_do_passo_a_passo(banco):
    colunas = banco.ok(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{PEDIDOS}';")
    assert COLUNAS_NOVAS <= set(colunas.splitlines())


def test_o_passo_a_passo_com_card_e_passos_entra(banco):
    r = _pedido(banco)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize(
    "campos",
    [{"card": "NULL"}, {"passos": 1}, {"passos": 16}],
    ids=["sem-card", "um-passo-so", "dezesseis-passos"],
)
def test_o_passo_a_passo_sem_card_ou_com_passos_fora_de_2_a_15_e_recusado(banco, campos):
    assert _pedido(banco, **campos).returncode != 0


def test_a_pergunta_nao_conclui_e_o_passo_a_passo_nao_e_respondido(banco):
    assert _pedido(banco, tipo="pergunta", estado="concluida").returncode != 0
    assert _pedido(banco, estado="respondida").returncode != 0
    assert _pedido(banco, estado="concluida").returncode == 0


@pytest.mark.parametrize("tabela", [PEDIDOS, CHECKS])
def test_as_duas_tabelas_tem_rls_ligada_e_nenhuma_policy(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{tabela}';") == "0"


def test_o_historico_dos_checks_so_cresce(banco):
    pedido = _pedido(banco).stdout.strip().splitlines()[0]
    inserir = f"INSERT INTO {CHECKS} (pedido_id, passo, marcado, por) VALUES ('{pedido}', 0, true, 'P004');"
    assert banco.sql(inserir, papel="service_role").returncode == 0

    mudar = banco.sql(f"UPDATE {CHECKS} SET marcado = false WHERE pedido_id = '{pedido}';", papel="service_role")
    apagar = banco.sql(f"DELETE FROM {CHECKS} WHERE pedido_id = '{pedido}';", papel="service_role")

    assert mudar.returncode != 0
    assert apagar.returncode != 0
    assert banco.ok(f"SELECT marcado FROM {CHECKS} WHERE pedido_id = '{pedido}';") == "t"


def test_o_historico_some_com_o_pedido(banco):
    pedido = _pedido(banco).stdout.strip().splitlines()[0]
    banco.ok(f"INSERT INTO {CHECKS} (pedido_id, passo, marcado) VALUES ('{pedido}', 1, true);")

    r = banco.sql(f"DELETE FROM {PEDIDOS} WHERE id = '{pedido}';", papel="service_role")

    assert r.returncode == 0, r.stderr
    assert banco.ok(f"SELECT count(*) FROM {CHECKS} WHERE pedido_id = '{pedido}';") == "0"


def test_o_recibo_e_o_232():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.rstrip().endswith(
        "INSERT INTO migracoes_aplicadas (numero) VALUES (232) ON CONFLICT (numero) DO NOTHING;"
    )
