"""A migration 224, o código de integridade por arquivo, num Postgres de
verdade (issue #1837).

Sobe um Postgres descartável, aplica as migrations do Canal de que a 224
depende e a 224 duas vezes, e prova no banco:

- o código de integridade só entra como SHA-256 em hexadecimal, nas quatro
  tabelas de arquivo do caso;
- o código da cópia assinada e o do parecer do Jurídico, uma vez gravados,
  não mudam, nem pela `service_role`;
- o arquivo do depoimento continua sem UPDATE, com código e tudo;
- a migration não cria tabela nem policy.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import hashlib
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
    "193_conduta_depoimentos.sql",
    "199_conduta_avisos_por_email.sql",
    "214_conduta_rota_especial.sql",
    "216_conduta_voto_e_trava_de_robustez.sql",
    "217_conduta_afastamento_cautelar.sql",
)
MIGRATION = PASTA / "224_conduta_trilha_e_dossie.sql"
CODIGO = hashlib.sha256(b"arquivo").hexdigest()
OUTRO = hashlib.sha256(b"outro").hexdigest()


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar o código de integridade no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54223"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        for nome in ANTERIORES:
            pg.ok((PASTA / nome).read_text(encoding="utf-8"))
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso(banco, etapa: str = "voto") -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa, rito) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', '{etapa}', 'rapido') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _assinatura(banco) -> str:
    return banco.ok(
        "INSERT INTO conduta_assinaturas (tipo, caso_id, signatarios, situacao) "
        f"VALUES ('relatorio_de_apuracao', '{_caso(banco)}', ARRAY['P1'], 'assinado') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _afastamento(banco) -> str:
    caso = _caso(banco)
    citado = banco.ok(
        f"INSERT INTO conduta_citados (caso_id, nome_cifrado) VALUES ('{caso}', 'v1:NOME') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]
    return banco.ok(
        "INSERT INTO conduta_afastamentos (caso_id, citado_id, rota, quem_cifrado, motivo_cifrado, registrado_por) "
        f"VALUES ('{caso}', '{citado}', 'comum', 'v1:QUEM', 'v1:MOTIVO', 'P1') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _depoimento(banco) -> str:
    return banco.ok(
        "INSERT INTO conduta_depoimentos (caso_id, nome_cifrado, cargo_cifrado, papel, criado_por) "
        f"VALUES ('{_caso(banco, 'apuracao')}', 'v1:NOME', 'v1:CARGO', 'acusado', 'P1') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def test_a_migration_nao_cria_tabela_nem_policy():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert "CREATE TABLE" not in sql
    assert "CREATE POLICY" not in sql


@pytest.mark.parametrize("codigo", ["abc", CODIGO.upper(), CODIGO + "0"])
def test_o_codigo_do_arquivo_do_depoimento_so_entra_como_sha256(banco, codigo):
    r = banco.sql(
        "INSERT INTO conduta_depoimento_arquivos "
        "(depoimento_id, tipo, versao, storage_path, content_type, tamanho_bytes, enviado_por, codigo_integridade) "
        f"VALUES ('{_depoimento(banco)}', 'audio', 1, 'depoimentos/{os.urandom(4).hex()}', 'audio/mpeg', 10, 'P1', "
        f"'{codigo}');",
        papel="service_role",
    )
    assert r.returncode != 0


def test_o_arquivo_do_depoimento_entra_com_o_codigo_e_nao_muda(banco):
    banco.ok(
        "INSERT INTO conduta_depoimento_arquivos "
        "(depoimento_id, tipo, versao, storage_path, content_type, tamanho_bytes, enviado_por, codigo_integridade) "
        f"VALUES ('{_depoimento(banco)}', 'audio', 1, 'depoimentos/fixo', 'audio/mpeg', 10, 'P1', '{CODIGO}');",
        papel="service_role",
    )
    r = banco.sql(
        f"UPDATE conduta_depoimento_arquivos SET codigo_integridade = '{OUTRO}' "
        "WHERE storage_path = 'depoimentos/fixo';",
        papel="service_role",
    )
    assert r.returncode != 0


def test_a_ciencia_do_codigo_recusa_codigo_torto(banco):
    r = banco.sql(
        "INSERT INTO conduta_ciencias_do_codigo "
        "(caso_id, versao, storage_path, content_type, tamanho_bytes, enviado_por, codigo_integridade) "
        f"VALUES ('{_caso(banco)}', 1, 'ciencias/x', 'application/pdf', 10, 'P1', 'nao-e-sha');",
        papel="service_role",
    )
    assert r.returncode != 0


def test_o_codigo_da_copia_assinada_entra_uma_vez_e_nao_muda(banco):
    assinatura = _assinatura(banco)
    banco.ok(
        f"UPDATE conduta_assinaturas SET arquivo_assinado_path = 'assinaturas/x', codigo_integridade = '{CODIGO}' "
        f"WHERE id = '{assinatura}';",
        papel="service_role",
    )

    trocar = banco.sql(
        f"UPDATE conduta_assinaturas SET codigo_integridade = '{OUTRO}' WHERE id = '{assinatura}';",
        papel="service_role",
    )
    apagar = banco.sql(
        f"UPDATE conduta_assinaturas SET codigo_integridade = NULL WHERE id = '{assinatura}';",
        papel="service_role",
    )

    assert trocar.returncode != 0
    assert apagar.returncode != 0
    assert banco.ok(f"SELECT codigo_integridade FROM conduta_assinaturas WHERE id = '{assinatura}';") == CODIGO


def test_a_assinatura_com_codigo_ainda_muda_o_resto(banco):
    assinatura = _assinatura(banco)
    banco.ok(
        f"UPDATE conduta_assinaturas SET codigo_integridade = '{CODIGO}' WHERE id = '{assinatura}';",
        papel="service_role",
    )
    r = banco.sql(
        f"UPDATE conduta_assinaturas SET erro = 'reconsulta' WHERE id = '{assinatura}';",
        papel="service_role",
    )
    assert r.returncode == 0, r.stderr


def test_o_codigo_do_parecer_entra_uma_vez_e_nao_muda(banco):
    afastamento = _afastamento(banco)
    banco.ok(
        "UPDATE conduta_afastamentos SET parecer_storage_path = 'afastamentos/x', parecer_anexado_por = 'P1', "
        f"parecer_anexado_em = now(), parecer_codigo_integridade = '{CODIGO}' WHERE id = '{afastamento}';",
        papel="service_role",
    )
    r = banco.sql(
        f"UPDATE conduta_afastamentos SET parecer_codigo_integridade = '{OUTRO}' WHERE id = '{afastamento}';",
        papel="service_role",
    )
    assert r.returncode != 0
