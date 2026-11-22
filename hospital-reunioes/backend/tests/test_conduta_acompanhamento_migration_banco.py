"""A migration 234, as mensagens do caso e o arquivamento por falta de
elementos, num Postgres de verdade (issue #1845).

Sobe um Postgres descartável, aplica a 175 e as do Canal até a 229, e a 234
duas vezes, sobre o mínimo de antes, e prova no banco:

- a mensagem guarda só texto cifrado, a pergunta tem autor e o complemento
  não tem; gravada, ela não muda nem se apaga;
- o desfecho `arquivado` existe e guarda a etapa para reabrir, e a
  reabertura limpa os dois;
- a tabela nova tem RLS ligada, nenhuma policy, e o anon não lê.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os

import pytest
from test_conduta_migration_banco import ESQUEMA_ANTERIOR
from test_conduta_migration_banco import MIGRATION as MIGRATION_175
from test_conduta_retaliacao_migration_banco import ANTERIORES as ANTERIORES_DA_229
from test_conduta_retaliacao_migration_banco import MIGRATION as MIGRATION_229
from test_conduta_retaliacao_migration_banco import PASTA
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

MIGRATION = PASTA / "234_conduta_acompanhamento_e_mensagens.sql"
TABELA = "conduta_mensagens"


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar as mensagens do caso no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54234"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        for nome in ANTERIORES_DA_229:
            pg.ok((PASTA / nome).read_text(encoding="utf-8"))
        pg.ok(MIGRATION_229.read_text(encoding="utf-8"))
        pg.ok("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;")
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _sql(banco, comando: str):
    return banco.sql(comando, papel="service_role")


def _caso(banco) -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa, rota) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', 'apuracao', 'comum') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _mensagem(banco, caso: str, tipo: str = "pergunta", autor: str | None = "'P1'", texto: str = "v1:T"):
    return _sql(
        banco,
        f"INSERT INTO {TABELA} (caso_id, tipo, autor_id, texto_cifrado) "
        f"VALUES ('{caso}', '{tipo}', {autor or 'NULL'}, '{texto}');",
    )


def test_a_pergunta_tem_autor_e_o_complemento_nao(banco):
    caso = _caso(banco)

    assert _mensagem(banco, caso).returncode == 0
    assert _mensagem(banco, caso, "complemento", autor=None).returncode == 0
    assert "autor_check" in _mensagem(banco, caso, "complemento").stderr
    assert "autor_check" in _mensagem(banco, caso, autor=None).stderr


def test_o_texto_da_mensagem_e_cifrado(banco):
    assert "texto_cifrado" in _mensagem(banco, _caso(banco), texto="texto em claro").stderr


def test_a_mensagem_gravada_nao_muda_nem_se_apaga(banco):
    caso = _caso(banco)
    assert _mensagem(banco, caso).returncode == 0

    assert (
        "como foi enviada"
        in _sql(banco, f"UPDATE {TABELA} SET texto_cifrado = 'v1:X' WHERE caso_id = '{caso}';").stderr
    )
    assert "como foi enviada" in _sql(banco, f"DELETE FROM {TABELA} WHERE caso_id = '{caso}';").stderr


def test_o_arquivado_guarda_a_etapa_e_a_reabertura_limpa(banco):
    caso = _caso(banco)
    sem_etapa = f"UPDATE conduta_casos SET desfecho = 'arquivado', encerrado_em = now() WHERE id = '{caso}';"
    arquivar = (
        "UPDATE conduta_casos SET desfecho = 'arquivado', encerrado_em = now(), etapa = 'encerrado', "
        f"etapa_ao_arquivar = 'apuracao' WHERE id = '{caso}';"
    )
    reabrir = (
        "UPDATE conduta_casos SET desfecho = NULL, encerrado_em = NULL, etapa = etapa_ao_arquivar, "
        f"etapa_ao_arquivar = NULL WHERE id = '{caso}';"
    )

    assert "arquivado_check" in _sql(banco, sem_etapa).stderr
    assert _sql(banco, arquivar).returncode == 0
    assert _sql(banco, reabrir).returncode == 0
    assert banco.ok(f"SELECT etapa FROM conduta_casos WHERE id = '{caso}';", papel="service_role") == "apuracao"


def test_os_desfechos_de_antes_continuam_valendo(banco):
    caso = _caso(banco)

    concluir = f"UPDATE conduta_casos SET desfecho = 'concluido', encerrado_em = now() WHERE id = '{caso}';"
    assert _sql(banco, concluir).returncode == 0
    assert "desfecho_check" in _sql(banco, f"UPDATE conduta_casos SET desfecho = 'sumido' WHERE id = '{caso}';").stderr


def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{TABELA}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{TABELA}';") == "0"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_o_anon_nao_le(banco, papel):
    assert "permission denied" in banco.sql(f"SELECT * FROM {TABELA};", papel=papel).stderr
