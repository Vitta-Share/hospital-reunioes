"""A migration 208 do Canal de Conduta num Postgres de verdade (issue #1831).

Sobe um Postgres descartável, aplica a 175, a 192, a 193 e a 208 (a 208 duas
vezes) sobre o mínimo de antes e prova no banco:

- a versão do termo só entra cifrada, e uma correção não apaga a anterior: a
  versão guardada não se altera nem se apaga, nem pela `service_role`;
- depoimento concluído não recebe versão nova;
- o roteiro só entra cifrado;
- a certidão de recusa exige o depoimento e o caso;
- a tabela nova tem RLS ligada e nenhuma policy.

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
MIGRATION = PASTA / "208_conduta_termo_de_declaracao.sql"
ANTERIORES = (PASTA / "192_conduta_assinaturas.sql", PASTA / "193_conduta_depoimentos.sql")


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar as travas do termo no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54208"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        for anterior in ANTERIORES:
            pg.ok(anterior.read_text(encoding="utf-8"))
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _depoimento(banco) -> tuple[str, str]:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    caso = banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', 'apuracao') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]
    depoimento = banco.ok(
        "INSERT INTO conduta_depoimentos (caso_id, nome_cifrado, cargo_cifrado, papel, criado_por) "
        f"VALUES ('{caso}', 'v1:NOME', 'v1:CARGO', 'testemunha', 'P1') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]
    return caso, depoimento


def _versao(banco, depoimento: str, versao: int = 1, termo: str = "v1:TERMO"):
    return banco.sql(
        "INSERT INTO conduta_depoimento_termos (depoimento_id, versao, origem, termo_cifrado, criado_por) "
        f"VALUES ('{depoimento}', {versao}, 'agente', '{termo}', 'P1');",
        papel="service_role",
    )


def test_a_migration_cria_so_a_tabela_das_versoes():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql) == ["conduta_depoimento_termos"]


def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok("SELECT relrowsecurity FROM pg_class WHERE relname = 'conduta_depoimento_termos';") == "t"
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename LIKE 'conduta_%';") == "0"


def test_a_versao_so_entra_cifrada(banco):
    _, depoimento = _depoimento(banco)

    assert _versao(banco, depoimento, termo="O declarante afirmou").returncode != 0
    assert _versao(banco, depoimento).returncode == 0


def test_a_correcao_e_versao_nova_e_a_anterior_nao_muda_nem_some(banco):
    _, depoimento = _depoimento(banco)
    assert _versao(banco, depoimento, 1).returncode == 0
    assert _versao(banco, depoimento, 2).returncode == 0

    alterar = banco.sql(
        f"UPDATE conduta_depoimento_termos SET termo_cifrado = 'v1:OUTRO' WHERE depoimento_id = '{depoimento}';",
        papel="service_role",
    )
    apagar = banco.sql(
        f"DELETE FROM conduta_depoimento_termos WHERE depoimento_id = '{depoimento}';", papel="service_role"
    )

    esvaziar = banco.sql("TRUNCATE conduta_depoimento_termos;", papel="service_role")

    assert alterar.returncode != 0 and apagar.returncode != 0 and esvaziar.returncode != 0
    assert banco.ok(f"SELECT count(*) FROM conduta_depoimento_termos WHERE depoimento_id = '{depoimento}';") == "2"
    assert _versao(banco, depoimento, 2).returncode != 0  # a mesma versão não entra duas vezes


def test_depoimento_concluido_nao_recebe_versao(banco):
    _, depoimento = _depoimento(banco)
    banco.ok(
        f"UPDATE conduta_depoimentos SET concluido_em = now(), concluido_por = 'P1' WHERE id = '{depoimento}';",
        papel="service_role",
    )

    r = _versao(banco, depoimento)

    assert r.returncode != 0
    assert "concluído" in r.stderr


def test_o_roteiro_so_entra_cifrado(banco):
    _, depoimento = _depoimento(banco)

    def roteiro(valor: str):
        return banco.sql(
            f"UPDATE conduta_depoimentos SET roteiro_cifrado = '{valor}', roteiro_em = now() "
            f"WHERE id = '{depoimento}';",
            papel="service_role",
        )

    em_claro, cifrado = roteiro("Onde estava?"), roteiro("v1:ROTEIRO")

    assert em_claro.returncode != 0
    assert cifrado.returncode == 0


def test_a_certidao_de_recusa_exige_o_depoimento(banco):
    caso, depoimento = _depoimento(banco)

    def certidao(depoimento_id: str):
        return banco.sql(
            "INSERT INTO conduta_assinaturas (tipo, caso_id, depoimento_id, signatarios) "
            f"VALUES ('certidao_de_recusa', '{caso}', {depoimento_id}, ARRAY['P1', 'P1']);",
            papel="service_role",
        )

    assert certidao("NULL").returncode != 0
    assert certidao(f"'{depoimento}'").returncode == 0


def test_o_recibo_e_o_208(banco):
    assert banco.ok("SELECT max(numero) FROM migracoes_aplicadas;") == "208"
