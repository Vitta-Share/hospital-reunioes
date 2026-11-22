"""A migration 221, a ata de deliberação e a reunião do Comitê, num Postgres
de verdade (issue #1834).

Sobe um Postgres descartável, aplica a 175, a 185, a 192, a 199, a 214, a 216
e a 221 (a 221 duas vezes) sobre o mínimo de antes e prova no banco:

- a versão da ata não se altera nem se apaga, nasce só na etapa Voto, e a ata
  assinada não ganha versão nova;
- a ata sai dos três votos da rodada aberta, e impedimento ou Citado depois
  dos votos tiram a ata de valer (a votação não conclui com ela, e a versão
  nova entra);
- a ata que está na ClickSign, e vale, não ganha versão nova, e só a última
  versão que vale vai à assinatura;
- a assinatura da ata aponta para a versão;
- a transcrição da reunião só entra no rito Completo, nunca como áudio, não
  se altera e só é eliminada depois de concluída a reunião;
- "CONCLUIR REUNIÃO" só com os quatro itens;
- o item dos votos da trava só se confirma com a ata assinada, e a votação só
  conclui com a ata assinada e, no Completo, com a reunião concluída;
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
    "192_conduta_assinaturas.sql",
    "199_conduta_avisos_por_email.sql",
    "214_conduta_rota_especial.sql",
    "216_conduta_voto_e_trava_de_robustez.sql",
)
MIGRATION = PASTA / "221_conduta_ata_de_deliberacao.sql"
TABELAS_NOVAS = ("conduta_atas", "conduta_reuniao_conferencia", "conduta_reuniao_transcricoes")


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a ata e a reunião no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54221"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(MIGRATION_175.read_text(encoding="utf-8"))
        for nome in ANTERIORES:
            pg.ok((PASTA / nome).read_text(encoding="utf-8"))
        pg.ok("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;")
        pg.ok(
            "INSERT INTO participantes (id, nome_completo) "
            "VALUES ('P2', 'Segunda'), ('P3', 'Terceira'), ('P4', 'Suplente');"
        )
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _caso(banco, rito: str = "rapido", etapa: str = "voto") -> str:
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    return banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa, rito) "
        f"VALUES ('{protocolo}', 'hash', 'v1:AAAA', '{etapa}', '{rito}') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


VOTANTES = ("P1", "P2", "P3")


def _votar(banco, caso: str, votantes: tuple[str, ...] = VOTANTES):
    """Os votos da rodada 1. No caso fora da etapa Voto o banco recusa, e a
    recusa que o teste quer ver é a da ata."""
    linhas = ", ".join(f"('{caso}', 1, '{pid}', 'v1:VOTO')" for pid in votantes)
    return banco.sql(
        f"INSERT INTO conduta_votos (caso_id, rodada, participante_id, voto_cifrado) VALUES {linhas} "
        "ON CONFLICT DO NOTHING;",
        papel="service_role",
    )


def _ata(banco, caso: str, versao: int = 1, votantes: tuple[str, ...] = VOTANTES, votar: bool = True):
    if votar:
        _votar(banco, caso, votantes)
    lista = ", ".join(f"'{pid}'" for pid in votantes)
    return banco.sql(
        "INSERT INTO conduta_atas (caso_id, versao, rodada, votantes, ata_cifrada, autor_id) "
        f"VALUES ('{caso}', {versao}, 1, ARRAY[{lista}]::varchar[], 'v1:ATA', 'P1') RETURNING id;",
        papel="service_role",
    )


def _enviar(banco, caso: str, situacao: str = "assinado"):
    ata = banco.ok(f"SELECT id FROM conduta_atas WHERE caso_id = '{caso}' ORDER BY versao DESC LIMIT 1;").splitlines()[
        -1
    ]
    return banco.sql(
        "INSERT INTO conduta_assinaturas (tipo, caso_id, ata_id, signatarios, situacao) "
        f"VALUES ('ata_de_deliberacao', '{caso}', '{ata}', ARRAY['P1'], '{situacao}');",
        papel="service_role",
    )


def _assinar(banco, caso: str) -> None:
    r = _enviar(banco, caso)
    assert r.returncode == 0, r.stderr


def _impedir(banco, caso: str, pid: str = "P3") -> None:
    banco.ok(
        "INSERT INTO conduta_atribuicoes (caso_id, participante_id, motivo, impedido_em) "
        f"VALUES ('{caso}', '{pid}', 'membro_do_comite', now());",
        papel="service_role",
    )


def _ata_assinada(banco, caso: str) -> None:
    assert _ata(banco, caso).returncode == 0
    _assinar(banco, caso)


def _transcricao(banco, caso: str, content_type: str = "text/plain; charset=utf-8", versao: int = 1):
    return banco.sql(
        "INSERT INTO conduta_reuniao_transcricoes (caso_id, versao, storage_path, content_type, tamanho_bytes, "
        f"enviado_por) VALUES ('{caso}', {versao}, 'reuniao/x', '{content_type}', 10, 'P1');",
        papel="service_role",
    )


def _declarar(banco, caso: str, item: str):
    return banco.sql(
        f"INSERT INTO conduta_reuniao_conferencia (caso_id, item, marcado_por) VALUES ('{caso}', '{item}', 'P1');",
        papel="service_role",
    )


def _concluir_reuniao(banco, caso: str):
    return banco.sql(
        f"UPDATE conduta_casos SET reuniao_concluida_em = now(), reuniao_concluida_por = 'P1' WHERE id = '{caso}';",
        papel="service_role",
    )


def _concluir_votacao(banco, caso: str, resultado: str = "improcedente"):
    return banco.sql(
        f"UPDATE conduta_casos SET resultado = '{resultado}', etapa = 'ata' WHERE id = '{caso}';",
        papel="service_role",
    )


def test_a_migration_cria_as_tres_tabelas():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql)) == sorted(TABELAS_NOVAS)


def test_a_versao_da_ata_nao_se_altera_nem_se_apaga(banco):
    caso = _caso(banco)
    assert _ata(banco, caso).returncode == 0

    troca = banco.sql(
        f"UPDATE conduta_atas SET ata_cifrada = 'v1:OUTRA' WHERE caso_id = '{caso}';", papel="service_role"
    )
    apaga = banco.sql(f"DELETE FROM conduta_atas WHERE caso_id = '{caso}';", papel="service_role")

    assert "fica guardado" in troca.stderr
    assert "fica guardado" in apaga.stderr


def test_a_ata_so_nasce_na_etapa_voto(banco):
    assert "etapa Voto" in _ata(banco, _caso(banco, etapa="apuracao")).stderr


def test_a_ata_assinada_nao_ganha_versao_nova(banco):
    caso = _caso(banco)
    _ata_assinada(banco, caso)

    assert "não ganha versão nova" in _ata(banco, caso, versao=2).stderr


def test_a_ata_sai_dos_tres_votos_da_rodada(banco):
    caso = _caso(banco)
    _votar(banco, caso, ("P1", "P2"))

    sem_o_terceiro = _ata(banco, caso, votantes=VOTANTES, votar=False)
    dois = _ata(banco, caso, votantes=("P1", "P2"), votar=False)

    assert "três votos da rodada aberta" in sem_o_terceiro.stderr
    assert "três votos da rodada aberta" in dois.stderr


@pytest.mark.parametrize("como", ["impedimento", "citado"])
def test_o_votante_que_sai_depois_da_ata_assinada_tira_a_ata_de_valer(banco, como):
    caso = _caso(banco)
    _ata_assinada(banco, caso)
    if como == "impedimento":
        _impedir(banco, caso)
    else:
        banco.ok(
            f"INSERT INTO conduta_citados (caso_id, participante_id) VALUES ('{caso}', 'P3');", papel="service_role"
        )

    assert banco.ok(f"SELECT conduta_ata_assinada('{caso}');") == "f"
    assert "ata assinada" in _concluir_votacao(banco, caso).stderr
    assert "três votos da rodada aberta" in _ata(banco, caso, versao=2).stderr
    nova = _ata(banco, caso, versao=2, votantes=("P1", "P2", "P4"))
    assert nova.returncode == 0, nova.stderr
    _assinar(banco, caso)
    assert _concluir_votacao(banco, caso).returncode == 0


def test_a_rodada_nova_tira_a_ata_de_valer(banco):
    caso = _caso(banco)
    _ata_assinada(banco, caso)
    banco.ok(f"UPDATE conduta_casos SET rodada_do_voto = 2 WHERE id = '{caso}';", papel="service_role")

    assert banco.ok(f"SELECT conduta_ata_assinada('{caso}');") == "f"


def test_a_ata_na_clicksign_nao_ganha_versao_nova(banco):
    caso = _caso(banco)
    assert _ata(banco, caso).returncode == 0
    assert _enviar(banco, caso, situacao="enviado").returncode == 0

    assert "está na ClickSign" in _ata(banco, caso, versao=2).stderr
    _impedir(banco, caso)
    assert _ata(banco, caso, versao=2, votantes=("P1", "P2", "P4")).returncode == 0


def test_a_ata_de_votos_que_nao_valem_nao_vai_a_assinatura(banco):
    caso = _caso(banco)
    assert _ata(banco, caso).returncode == 0
    _impedir(banco, caso)

    assert "vai à assinatura" in _enviar(banco, caso, situacao="gerado").stderr


def test_a_assinatura_da_ata_aponta_para_a_versao(banco):
    caso = _caso(banco)
    r = banco.sql(
        "INSERT INTO conduta_assinaturas (tipo, caso_id, signatarios) "
        f"VALUES ('ata_de_deliberacao', '{caso}', ARRAY['P1']);",
        papel="service_role",
    )
    assert "conduta_assinaturas_ata_da_versao" in r.stderr


def test_a_transcricao_da_reuniao_so_entra_no_rito_completo(banco):
    assert "rito Completo" in _transcricao(banco, _caso(banco, rito="rapido")).stderr
    assert _transcricao(banco, _caso(banco, rito="completo")).returncode == 0


def test_o_audio_da_reuniao_nao_entra(banco):
    r = _transcricao(banco, _caso(banco, rito="completo"), content_type="audio/mpeg")
    assert "content_type_check" in r.stderr


def test_a_transcricao_so_e_eliminada_depois_de_concluida_a_reuniao(banco):
    caso = _caso(banco, rito="completo")
    assert _transcricao(banco, caso).returncode == 0

    troca = banco.sql(
        f"UPDATE conduta_reuniao_transcricoes SET storage_path = 'outro' WHERE caso_id = '{caso}';",
        papel="service_role",
    )
    antes = banco.sql(f"DELETE FROM conduta_reuniao_transcricoes WHERE caso_id = '{caso}';", papel="service_role")
    assert "não se altera" in troca.stderr
    assert "depois de concluída" in antes.stderr

    _ata_assinada(banco, caso)
    _declarar(banco, caso, "gravacao_apagada")
    _declarar(banco, caso, "arquivos_apagados")
    assert _concluir_reuniao(banco, caso).returncode == 0
    depois = banco.sql(f"DELETE FROM conduta_reuniao_transcricoes WHERE caso_id = '{caso}';", papel="service_role")

    assert depois.returncode == 0, depois.stderr
    assert banco.ok(f"SELECT count(*) FROM conduta_reuniao_transcricoes WHERE caso_id = '{caso}';") == "0"


@pytest.mark.parametrize("falta", ["transcricao", "ata", "gravacao_apagada", "arquivos_apagados"])
def test_concluir_reuniao_so_com_os_quatro_itens(banco, falta):
    caso = _caso(banco, rito="completo")
    if falta != "transcricao":
        _transcricao(banco, caso)
    if falta != "ata":
        _ata_assinada(banco, caso)
    for item in ("gravacao_apagada", "arquivos_apagados"):
        if item != falta:
            assert _declarar(banco, caso, item).returncode == 0

    assert "só conclui" in _concluir_reuniao(banco, caso).stderr


def test_a_declaracao_da_reuniao_nao_se_desfaz(banco):
    caso = _caso(banco, rito="completo")
    assert _declarar(banco, caso, "gravacao_apagada").returncode == 0

    apaga = banco.sql(f"DELETE FROM conduta_reuniao_conferencia WHERE caso_id = '{caso}';", papel="service_role")
    assert "fica guardado" in apaga.stderr


def test_o_item_dos_votos_so_se_confirma_com_a_ata_assinada(banco):
    caso = _caso(banco)
    confirmar = (
        f"INSERT INTO conduta_trava_confirmacoes (caso_id, item, participante_id) VALUES ('{caso}', 'votos', 'P1');"
    )

    assert "ata assinada" in banco.sql(confirmar, papel="service_role").stderr
    _ata_assinada(banco, caso)
    assert banco.sql(confirmar, papel="service_role").returncode == 0


def test_a_votacao_so_conclui_com_a_ata_assinada(banco):
    caso = _caso(banco)
    assert _ata(banco, caso).returncode == 0

    assert "ata assinada" in _concluir_votacao(banco, caso).stderr
    _assinar(banco, caso)
    assert _concluir_votacao(banco, caso).returncode == 0


def test_no_rito_completo_a_votacao_so_conclui_com_a_reuniao_concluida(banco):
    caso = _caso(banco, rito="completo")
    _transcricao(banco, caso)
    _ata_assinada(banco, caso)

    assert "reunião concluída" in _concluir_votacao(banco, caso).stderr
    _declarar(banco, caso, "gravacao_apagada")
    _declarar(banco, caso, "arquivos_apagados")
    assert _concluir_reuniao(banco, caso).returncode == 0
    assert _concluir_votacao(banco, caso).returncode == 0


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{tabela}';") == "0"


@pytest.mark.parametrize("tabela", TABELAS_NOVAS)
@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_o_anon_nao_le(banco, tabela, papel):
    assert "permission denied" in banco.sql(f"SELECT * FROM {tabela};", papel=papel).stderr
