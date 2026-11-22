"""A migration 216, o voto e a trava de robustez, num Postgres de verdade
(issue #1833).

Sobe um Postgres descartável, aplica a 175, a 185, a 199, a 214 e a 216 (a 216
duas vezes) sobre o mínimo de antes e prova no banco:

- o voto registrado, a confirmação da trava, o preenchimento do agente e a
  ciência do Código não se alteram nem se apagam, nem pela `service_role`;
- um voto por pessoa e rodada, cifrado, e só com o caso na etapa Voto;
- procedente e parcialmente procedente só com os sete itens confirmados, e
  improcedente sem a trava; o resultado gravado não muda;
- o aviso da reunião curta é um motivo aceito;
- as tabelas novas têm RLS ligada, nenhuma policy, e o anon não lê.

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
    "199_conduta_avisos_por_email.sql",
    "214_conduta_rota_especial.sql",
)
MIGRATION = PASTA / "216_conduta_voto_e_trava_de_robustez.sql"
TABELAS_NOVAS = (
    "conduta_ciencias_do_codigo",
    "conduta_trava_confirmacoes",
    "conduta_trava_preenchimentos",
    "conduta_votos",
)
ITENS = ("fato", "prova", "defesa", "regra", "ciencia", "medida", "votos")


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar o voto e a trava no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54216"
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


def _caso(banco, etapa: str = "voto") -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', '{etapa}') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _votar(banco, caso: str, rodada: int = 1, voto: str = "v1:VOTO"):
    return banco.sql(
        "INSERT INTO conduta_votos (caso_id, rodada, participante_id, voto_cifrado) "
        f"VALUES ('{caso}', {rodada}, 'P1', '{voto}');",
        papel="service_role",
    )


def _confirmar(banco, caso: str, item: str):
    return banco.sql(
        f"INSERT INTO conduta_trava_confirmacoes (caso_id, item, participante_id) VALUES ('{caso}', '{item}', 'P1');",
        papel="service_role",
    )


def _concluir(banco, caso: str, resultado: str):
    return banco.sql(
        f"UPDATE conduta_casos SET resultado = '{resultado}', etapa = 'ata' WHERE id = '{caso}';",
        papel="service_role",
    )


def test_a_migration_cria_as_quatro_tabelas():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql)) == sorted(TABELAS_NOVAS)


def test_o_voto_registrado_nao_se_altera_nem_se_apaga(banco):
    caso = _caso(banco)
    assert _votar(banco, caso).returncode == 0

    troca = banco.sql(
        f"UPDATE conduta_votos SET voto_cifrado = 'v1:OUTRO' WHERE caso_id = '{caso}';", papel="service_role"
    )
    apaga = banco.sql(f"DELETE FROM conduta_votos WHERE caso_id = '{caso}';", papel="service_role")

    assert "fica guardado" in troca.stderr
    assert "fica guardado" in apaga.stderr
    assert banco.ok(f"SELECT count(*) FROM conduta_votos WHERE caso_id = '{caso}';") == "1"


def test_um_voto_por_pessoa_e_rodada(banco):
    caso = _caso(banco)
    _votar(banco, caso)

    assert "duplicate key" in _votar(banco, caso).stderr
    assert _votar(banco, caso, rodada=2).returncode == 0


def test_o_voto_entra_cifrado_e_so_na_etapa_voto(banco):
    assert "check" in _votar(banco, _caso(banco), voto="procedente").stderr.lower()
    assert "etapa Voto" in _votar(banco, _caso(banco, etapa="apuracao")).stderr


def test_a_confirmacao_da_trava_nao_se_desfaz(banco):
    caso = _caso(banco)
    _confirmar(banco, caso, "fato")

    apaga = banco.sql(f"DELETE FROM conduta_trava_confirmacoes WHERE caso_id = '{caso}';", papel="service_role")

    assert "fica guardado" in apaga.stderr


@pytest.mark.parametrize("tabela", ["conduta_trava_preenchimentos", "conduta_ciencias_do_codigo"])
def test_o_preenchimento_e_a_ciencia_nao_se_apagam(banco, tabela):
    caso = _caso(banco)
    if tabela == "conduta_trava_preenchimentos":
        valores = "(caso_id, versao, itens_cifrado, autor_id) VALUES ('{c}', 1, 'v1:ITENS', 'P1')"
    else:
        valores = (
            "(caso_id, versao, storage_path, content_type, tamanho_bytes, enviado_por) "
            "VALUES ('{c}', 1, 'ciencias/x', 'application/pdf', 10, 'P1')"
        )
    banco.ok(f"INSERT INTO {tabela} {valores.format(c=caso)};", papel="service_role")

    assert "fica guardado" in banco.sql(f"DELETE FROM {tabela} WHERE caso_id = '{caso}';", papel="service_role").stderr


@pytest.mark.parametrize("resultado", ["procedente", "parcialmente_procedente"])
def test_procedente_so_com_os_sete_itens_confirmados(banco, resultado):
    caso = _caso(banco)
    for item in ITENS[:-1]:
        _confirmar(banco, caso, item)

    assert "trava de robustez" in _concluir(banco, caso, resultado).stderr
    _confirmar(banco, caso, ITENS[-1])
    assert _concluir(banco, caso, resultado).returncode == 0


def test_improcedente_conclui_sem_a_trava_e_o_resultado_nao_muda(banco):
    caso = _caso(banco)

    assert _concluir(banco, caso, "improcedente").returncode == 0
    assert "não muda" in _concluir(banco, caso, "inconclusivo").stderr


def test_o_resultado_so_sai_da_etapa_voto(banco):
    caso = _caso(banco, etapa="apuracao")

    assert "etapa Voto" in _concluir(banco, caso, "improcedente").stderr


def test_o_aviso_da_reuniao_curta_e_aceito(banco):
    assert "reuniao_curta" in banco.ok(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'conduta_avisos_motivo_check';"
    )


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{tabela}';") == "0"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_o_anon_nao_le(banco, tabela, papel):
    assert "permission denied" in banco.sql(f"SELECT * FROM {tabela};", papel=papel).stderr
