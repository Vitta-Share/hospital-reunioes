"""A migration 223, a Recomendação do Comitê, a decisão da medida e o retorno,
num Postgres de verdade (issue #1835).

Sobe um Postgres descartável, aplica a 175, a 185, a 192, a 199, a 214, a
216, a 221 e a 223 (a 223 duas vezes) sobre o mínimo de antes e prova no
banco:

- só o caso procedente da fila comum, na etapa Ata, vai à Direção, e o envio
  não muda;
- a decisão da medida é da etapa Medida, uma por caso, e "com ajuste" e "não
  aplicada" levam justificativa; a etapa Medida só termina com ela;
- a comunicação da medida vem depois de uma decisão que aplica a medida;
- o retorno é da etapa Retorno (ou da Ata, no improcedente), só a última
  versão é aprovada, a aprovada não muda e, no procedente, vem depois da
  decisão e de uma correção de processo escolhida;
- a correção de processo é só do procedente;
- os perfis do Presidente e da diretoria executiva;
- as tabelas novas não se alteram, têm RLS ligada, nenhuma policy, e o anon
  não lê.

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
)
MIGRATION = PASTA / "223_conduta_recomendacao_medida_e_retorno.sql"
TABELAS_NOVAS = (
    "conduta_retornos",
    "conduta_decisoes_da_medida",
    "conduta_comunicacoes_da_medida",
    "conduta_correcoes_sugeridas",
    "conduta_correcoes",
)


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a medida e o retorno no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54222"
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


def _caso(banco, resultado: str = "procedente", etapa: str = "ata", rota: str = "comum") -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa, rito, rota, resultado) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', '{etapa}', 'rapido', '{rota}', '{resultado}') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


def _sql(banco, comando: str):
    return banco.sql(comando, papel="service_role")


def _enviar_a_direcao(banco, caso: str):
    return _sql(
        banco,
        f"UPDATE conduta_casos SET enviado_a_direcao_em = now(), enviado_a_direcao_por = 'P1', etapa = 'medida' "
        f"WHERE id = '{caso}';",
    )


def _decidir(banco, caso: str, decisao: str = "aplicada", justificativa: str | None = None):
    valor = f"'{justificativa}'" if justificativa else "NULL"
    return _sql(
        banco,
        "INSERT INTO conduta_decisoes_da_medida (caso_id, decisao, justificativa_cifrada, decidida_em, registrada_por) "
        f"VALUES ('{caso}', '{decisao}', {valor}, current_date, 'P1');",
    )


def _ir_ao_retorno(banco, caso: str):
    return _sql(banco, f"UPDATE conduta_casos SET etapa = 'retorno' WHERE id = '{caso}';")


def _retorno(banco, caso: str, versao: int = 1):
    return _sql(
        banco,
        "INSERT INTO conduta_retornos (caso_id, versao, denunciante_cifrado, acusado_cifrado, origem, autor_id) "
        f"VALUES ('{caso}', {versao}, 'v1:R', 'v1:A', 'agente', 'P1') RETURNING id;",
    )


def _id(resultado) -> str:
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout.strip().splitlines()[0]


def _aprovar(banco, caso: str, retorno_id: str):
    return _sql(
        banco,
        f"UPDATE conduta_casos SET retorno_aprovado_id = '{retorno_id}', retorno_aprovado_em = now(), "
        f"retorno_aprovado_por = 'P1' WHERE id = '{caso}';",
    )


def _correcao(banco, caso: str):
    return _sql(
        banco,
        "INSERT INTO conduta_correcoes (caso_id, texto_cifrado, responsavel_cifrado, prazo_em, escolhida_por) "
        f"VALUES ('{caso}', 'v1:T', 'v1:R', current_date + 30, 'P1');",
    )


def _na_etapa_retorno(banco) -> str:
    caso = _caso(banco)
    assert _enviar_a_direcao(banco, caso).returncode == 0
    assert _decidir(banco, caso).returncode == 0
    assert _ir_ao_retorno(banco, caso).returncode == 0
    return caso


def test_a_migration_nao_esvazia_tabela():
    assert not re.search(r"\b(DROP\s+TABLE|DELETE\s+FROM)\b", MIGRATION.read_text(encoding="utf-8"), re.IGNORECASE)


@pytest.mark.parametrize("perfil", ["presidente", "diretoria_executiva", "cadastro_de_membros"])
def test_os_perfis_da_direcao_entram_no_cadastro(banco, perfil):
    assert _sql(banco, f"UPDATE participantes SET perfil_conduta = '{perfil}' WHERE id = 'P1';").returncode == 0
    assert _sql(banco, "UPDATE participantes SET perfil_conduta = NULL WHERE id = 'P1';").returncode == 0


def test_perfil_fora_da_lista_e_recusado(banco):
    assert (
        "perfil_conduta" in _sql(banco, "UPDATE participantes SET perfil_conduta = 'diretor' WHERE id = 'P1';").stderr
    )


@pytest.mark.parametrize("resultado", ["improcedente", "inconclusivo"])
def test_improcedente_e_inconclusivo_nao_vao_a_direcao(banco, resultado):
    caso = _caso(banco, resultado=resultado)

    assert "procedente da fila comum" in _enviar_a_direcao(banco, caso).stderr


def test_o_caso_da_rota_especial_nao_vai_a_direcao(banco):
    caso = _caso(banco, rota="especial")

    assert "procedente da fila comum" in _enviar_a_direcao(banco, caso).stderr


def test_fora_da_etapa_ata_nao_vai_a_direcao(banco):
    caso = _caso(banco, etapa="voto")

    assert "procedente da fila comum" in _enviar_a_direcao(banco, caso).stderr


@pytest.mark.parametrize("resultado", ["procedente", "parcialmente_procedente"])
def test_o_procedente_vai_a_direcao_e_o_envio_nao_muda(banco, resultado):
    caso = _caso(banco, resultado=resultado)

    assert _enviar_a_direcao(banco, caso).returncode == 0
    assert (
        "não muda" in _sql(banco, f"UPDATE conduta_casos SET enviado_a_direcao_em = NULL WHERE id = '{caso}';").stderr
    )


def test_a_etapa_medida_comeca_com_o_envio(banco):
    caso = _caso(banco)

    assert "Medida começa" in _sql(banco, f"UPDATE conduta_casos SET etapa = 'medida' WHERE id = '{caso}';").stderr


def test_a_decisao_e_da_etapa_medida(banco):
    caso = _caso(banco)

    assert "etapa Medida" in _decidir(banco, caso).stderr


@pytest.mark.parametrize("decisao", ["aplicada_com_ajuste", "nao_aplicada"])
def test_com_ajuste_e_nao_aplicada_pedem_justificativa(banco, decisao):
    caso = _caso(banco)
    assert _enviar_a_direcao(banco, caso).returncode == 0

    assert "justificativa" in _decidir(banco, caso, decisao).stderr
    assert _decidir(banco, caso, decisao, "v1:JUST").returncode == 0


def test_a_decisao_e_uma_por_caso_e_nao_muda(banco):
    caso = _caso(banco)
    assert _enviar_a_direcao(banco, caso).returncode == 0
    assert _decidir(banco, caso).returncode == 0

    assert "duplicate key" in _decidir(banco, caso).stderr
    assert (
        "guardado"
        in _sql(
            banco, f"UPDATE conduta_decisoes_da_medida SET decisao = 'nao_aplicada' WHERE caso_id = '{caso}';"
        ).stderr
    )
    assert "guardado" in _sql(banco, f"DELETE FROM conduta_decisoes_da_medida WHERE caso_id = '{caso}';").stderr


def test_a_etapa_medida_so_termina_com_a_decisao(banco):
    caso = _caso(banco)
    assert _enviar_a_direcao(banco, caso).returncode == 0

    assert "decisão registrada" in _ir_ao_retorno(banco, caso).stderr
    assert _decidir(banco, caso).returncode == 0
    assert _ir_ao_retorno(banco, caso).returncode == 0


def _comunicacao(banco, caso: str):
    return _sql(
        banco,
        "INSERT INTO conduta_comunicacoes_da_medida (caso_id, versao, storage_path, content_type, tamanho_bytes, "
        f"enviado_por) VALUES ('{caso}', 1, 'medida/x', 'application/pdf', 10, 'P1');",
    )


def test_a_comunicacao_da_medida_vem_depois_da_decisao_que_aplica(banco):
    nao_aplicada = _caso(banco)
    assert _enviar_a_direcao(banco, nao_aplicada).returncode == 0
    assert _decidir(banco, nao_aplicada, "nao_aplicada", "v1:J").returncode == 0
    aplicada = _caso(banco)
    assert _enviar_a_direcao(banco, aplicada).returncode == 0

    assert "decisão que aplica" in _comunicacao(banco, aplicada).stderr
    assert "decisão que aplica" in _comunicacao(banco, nao_aplicada).stderr
    assert _decidir(banco, aplicada).returncode == 0
    assert _comunicacao(banco, aplicada).returncode == 0


def test_o_retorno_e_da_etapa_retorno(banco):
    caso = _caso(banco)

    assert "etapa Retorno" in _retorno(banco, caso).stderr


@pytest.mark.parametrize("resultado", ["improcedente", "inconclusivo"])
def test_no_improcedente_o_retorno_sai_da_etapa_ata(banco, resultado):
    caso = _caso(banco, resultado=resultado)

    retorno = _id(_retorno(banco, caso))
    assert _aprovar(banco, caso, retorno).returncode == 0


def test_so_a_ultima_versao_do_retorno_e_aprovada_e_a_aprovada_nao_muda(banco):
    caso = _caso(banco, resultado="improcedente")
    primeira = _id(_retorno(banco, caso, 1))
    segunda = _id(_retorno(banco, caso, 2))

    assert "última versão" in _aprovar(banco, caso, primeira).stderr
    assert _aprovar(banco, caso, segunda).returncode == 0
    assert "não muda" in _aprovar(banco, caso, primeira).stderr
    assert "etapa Retorno" in _retorno(banco, caso, 3).stderr


def test_no_procedente_o_retorno_aprovado_pede_a_correcao_de_processo(banco):
    caso = _na_etapa_retorno(banco)
    retorno = _id(_retorno(banco, caso))

    assert "correção de processo" in _aprovar(banco, caso, retorno).stderr
    assert _correcao(banco, caso).returncode == 0
    assert _aprovar(banco, caso, retorno).returncode == 0


@pytest.mark.parametrize("resultado", ["improcedente", "inconclusivo"])
def test_a_correcao_de_processo_e_so_do_procedente(banco, resultado):
    caso = _caso(banco, resultado=resultado)

    assert "procedente" in _correcao(banco, caso).stderr


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_a_tabela_nova_nao_se_altera(banco, tabela):
    caso = _na_etapa_retorno(banco)
    _id(_retorno(banco, caso))
    _correcao(banco, caso)
    _comunicacao(banco, caso)
    _sql(
        banco,
        "INSERT INTO conduta_correcoes_sugeridas (caso_id, versao, itens_cifrado, autor_id) "
        f"VALUES ('{caso}', 1, 'v1:I', 'P1');",
    )

    assert banco.ok(f"SELECT count(*) FROM {tabela} WHERE caso_id = '{caso}';") == "1"
    assert "guardado" in _sql(banco, f"UPDATE {tabela} SET caso_id = caso_id WHERE caso_id = '{caso}';").stderr
    assert "guardado" in _sql(banco, f"DELETE FROM {tabela} WHERE caso_id = '{caso}';").stderr


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{tabela}';") == "0"


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_o_anon_nao_le(banco, tabela, papel):
    assert "permission denied" in banco.sql(f"SELECT * FROM {tabela};", papel=papel).stderr
