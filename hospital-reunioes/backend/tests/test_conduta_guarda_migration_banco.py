"""A migration 226, o papel, a guarda, o congelamento e a eliminação, num
Postgres de verdade (issue #1838).

Sobe um Postgres descartável, aplica as migrations do Canal de que a 226
depende e a 226 duas vezes, e prova no banco:

- a função de eliminação apaga o conteúdo do caso vencido (cinco anos do
  encerramento; um ano para o encaminhado), marca a eliminação e deixa a
  trilha, as atribuições e os metadados;
- antes do prazo, com o caso aberto ou congelado, ela recusa;
- os gatilhos das tabelas do conteúdo voltam a valer depois dela;
- só a service_role executa a função;
- o lacre do envelope é do caso encerrado, vem inteiro e, gravado, não muda;
- caso congelado e eliminado ao mesmo tempo, o banco recusa.

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
    "186_conduta_configuracoes_com_versao.sql",
    "191_conduta_impedimento_e_citado.sql",
    "192_conduta_assinaturas.sql",
    "193_conduta_depoimentos.sql",
    "199_conduta_avisos_por_email.sql",
    "200_conduta_agente_de_triagem.sql",
    "203_conduta_nota_ao_nucleo.sql",
    "213_conduta_relatorio_de_apuracao.sql",
    "214_conduta_rota_especial.sql",
    "215_conduta_termo_de_declaracao.sql",
    "216_conduta_voto_e_trava_de_robustez.sql",
    "217_conduta_afastamento_cautelar.sql",
    "221_conduta_ata_de_deliberacao.sql",
    "223_conduta_recomendacao_medida_e_retorno.sql",
    "224_conduta_trilha_e_dossie.sql",
)
MIGRATION = PASTA / "226_conduta_papel_guarda_e_eliminacao.sql"
CODIGO = "c" * 64


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a guarda e a eliminação no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54226"
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


def _caso(banco, *, encerrado_ha: str | None = "5 years 2 days", desfecho: str = "concluido") -> str:
    """Um caso do rito Rápido com conteúdo em várias tabelas: depoimento com
    arquivo, voto, ata, retorno aprovado, Citado com e sem cadastro e uma
    linha na trilha. `encerrado_ha` é quanto tempo faz o encerramento."""
    protocolo = f"CC-{os.urandom(2).hex().upper()}-{os.urandom(2).hex().upper()}"
    encerrado = f"now() - interval '{encerrado_ha}'" if encerrado_ha else "NULL"
    desfecho_sql = f"'{desfecho}'" if encerrado_ha else "NULL"
    caso = banco.ok(
        "INSERT INTO conduta_casos (protocolo, codigo_hash, relato_cifrado, etapa, rito, encerrado_em, desfecho) "
        f"VALUES ('{protocolo}', 'hash', 'v1:RELATO', 'encerrado', 'rapido', {encerrado}, {desfecho_sql}) "
        "RETURNING id;"
    ).splitlines()[-1]
    # O conteúdo entra sem os gatilhos de etapa: aqui importa só o que fica.
    banco.ok(
        f"""
        SET session_replication_role = replica;
        WITH dep AS (
          INSERT INTO conduta_depoimentos (caso_id, nome_cifrado, cargo_cifrado, papel, criado_por)
          VALUES ('{caso}', 'v1:NOME', 'v1:CARGO', 'acusado', 'P1') RETURNING id
        )
        INSERT INTO conduta_depoimento_arquivos
          (depoimento_id, tipo, versao, storage_path, content_type, tamanho_bytes, enviado_por)
        SELECT id, 'termo_assinado', 1, 'depoimentos/' || gen_random_uuid(), 'application/pdf', 10, 'P1' FROM dep;
        INSERT INTO conduta_votos (caso_id, rodada, participante_id, voto_cifrado)
          VALUES ('{caso}', 1, 'P1', 'v1:VOTO');
        INSERT INTO conduta_atas (caso_id, versao, rodada, votantes, ata_cifrada, autor_id)
          VALUES ('{caso}', 1, 1, ARRAY['P1','P1','P1'], 'v1:ATA', 'P1');
        WITH r AS (
          INSERT INTO conduta_retornos (caso_id, versao, denunciante_cifrado, acusado_cifrado, origem, autor_id)
          VALUES ('{caso}', 1, 'v1:D', 'v1:A', 'coordenacao', 'P1') RETURNING id
        )
        UPDATE conduta_casos SET retorno_aprovado_id = (SELECT id FROM r) WHERE id = '{caso}';
        INSERT INTO conduta_citados (caso_id, participante_id, nome_cifrado) VALUES ('{caso}', 'P1', 'v1:CITADO');
        INSERT INTO conduta_citados (caso_id, nome_cifrado) VALUES ('{caso}', 'v1:SEM_CADASTRO');
        INSERT INTO conduta_atribuicoes (caso_id, participante_id, motivo) VALUES ('{caso}', 'P1', 'apurador');
        INSERT INTO conduta_trilha (caso_id, autor_id, acao, registrado_em, codigo)
          VALUES ('{caso}', 'P1', 'leitura', now(), md5(random()::text) || md5(random()::text));
        SET session_replication_role = origin;
        """
    )
    return caso


def _eliminar(banco, caso: str, papel: str = "service_role"):
    return banco.sql(f"SELECT conduta_eliminar_conteudo_do_caso('{caso}');", papel=papel)


def _conta(banco, tabela: str, caso: str) -> int:
    if tabela == "conduta_depoimento_arquivos":
        filtro = f"depoimento_id IN (SELECT id FROM conduta_depoimentos WHERE caso_id = '{caso}')"
    else:
        filtro = f"caso_id = '{caso}'"
    return int(banco.ok(f"SELECT count(*) FROM {tabela} WHERE {filtro};"))


CONTEUDO = (
    "conduta_depoimentos",
    "conduta_depoimento_arquivos",
    "conduta_votos",
    "conduta_atas",
    "conduta_retornos",
)


class TestEliminacao:
    def test_o_caso_encerrado_ha_mais_de_cinco_anos_perde_o_conteudo_e_guarda_a_trilha(self, banco):
        caso = _caso(banco, encerrado_ha="5 years 2 days")
        assert all(_conta(banco, t, caso) == 1 for t in CONTEUDO)

        r = _eliminar(banco, caso)

        assert r.returncode == 0, r.stderr
        assert all(_conta(banco, t, caso) == 0 for t in CONTEUDO)
        linha = banco.ok(
            "SELECT relato_cifrado IS NULL, eliminado_em IS NOT NULL, protocolo IS NOT NULL "
            f"FROM conduta_casos WHERE id = '{caso}';"
        )
        assert linha == "t|t|t"
        assert _conta(banco, "conduta_trilha", caso) == 1
        assert _conta(banco, "conduta_atribuicoes", caso) == 1

    def test_o_citado_ligado_fica_sem_o_nome_e_o_sem_cadastro_sai(self, banco):
        caso = _caso(banco)

        assert _eliminar(banco, caso).returncode == 0

        assert banco.ok(f"SELECT participante_id, nome_cifrado IS NULL FROM conduta_citados WHERE caso_id = '{caso}';") == "P1|t"

    def test_o_encaminhado_vence_em_um_ano(self, banco):
        caso = _caso(banco, encerrado_ha="1 year 2 days", desfecho="encaminhado")

        assert _eliminar(banco, caso).returncode == 0
        assert _conta(banco, "conduta_votos", caso) == 0

    def test_o_concluido_ha_dois_anos_ainda_esta_na_guarda(self, banco):
        caso = _caso(banco, encerrado_ha="2 years")

        r = _eliminar(banco, caso)

        assert r.returncode != 0
        assert "A guarda do caso vai até" in r.stderr
        assert _conta(banco, "conduta_votos", caso) == 1

    def test_o_caso_aberto_nao_e_eliminado(self, banco):
        caso = _caso(banco, encerrado_ha=None)

        r = _eliminar(banco, caso)

        assert r.returncode != 0
        assert "Só o caso encerrado é eliminado" in r.stderr

    def test_o_caso_congelado_nao_e_eliminado(self, banco):
        caso = _caso(banco)
        banco.ok(f"UPDATE conduta_casos SET congelado_em = now(), congelado_por = 'P1' WHERE id = '{caso}';")

        r = _eliminar(banco, caso)

        assert r.returncode != 0
        assert "Caso congelado não é eliminado" in r.stderr
        assert _conta(banco, "conduta_votos", caso) == 1

    def test_eliminar_de_novo_nao_muda_nada(self, banco):
        caso = _caso(banco)
        assert _eliminar(banco, caso).returncode == 0
        antes = banco.ok(f"SELECT eliminado_em FROM conduta_casos WHERE id = '{caso}';")

        assert _eliminar(banco, caso).returncode == 0

        assert banco.ok(f"SELECT eliminado_em FROM conduta_casos WHERE id = '{caso}';") == antes

    def test_os_gatilhos_do_conteudo_voltam_a_valer_depois(self, banco):
        vencido = _caso(banco)
        assert _eliminar(banco, vencido).returncode == 0
        outro = _caso(banco, encerrado_ha="1 year")

        r = banco.sql(f"DELETE FROM conduta_votos WHERE caso_id = '{outro}';", papel="service_role")

        assert r.returncode != 0
        assert _conta(banco, "conduta_votos", outro) == 1

    @pytest.mark.parametrize("papel", ["anon", "authenticated"])
    def test_so_a_service_role_executa(self, banco, papel):
        caso = _caso(banco)

        r = _eliminar(banco, caso, papel=papel)

        assert r.returncode != 0
        assert "permission denied" in r.stderr
        assert _conta(banco, "conduta_votos", caso) == 1


class TestLacreECongelamento:
    def test_o_lacre_e_do_caso_encerrado(self, banco):
        caso = _caso(banco, encerrado_ha=None)

        r = banco.sql(
            "UPDATE conduta_casos SET papel_lacrado_em = current_date, papel_lacrado_por = 'P1', "
            f"papel_local = 'Armário da Diretoria' WHERE id = '{caso}';",
            papel="service_role",
        )

        assert r.returncode != 0
        assert "conduta_casos_lacre_check" in r.stderr

    def test_o_lacre_vem_com_o_local(self, banco):
        caso = _caso(banco, encerrado_ha="1 day")

        r = banco.sql(
            "UPDATE conduta_casos SET papel_lacrado_em = current_date, papel_lacrado_por = 'P1', "
            f"papel_local = '  ' WHERE id = '{caso}';",
            papel="service_role",
        )

        assert r.returncode != 0
        assert "conduta_casos_lacre_check" in r.stderr

    def test_o_lacre_gravado_nao_muda(self, banco):
        caso = _caso(banco, encerrado_ha="1 day")
        banco.ok(
            "UPDATE conduta_casos SET papel_lacrado_em = current_date, papel_lacrado_por = 'P1', "
            f"papel_local = 'Armário da Diretoria' WHERE id = '{caso}';",
            papel="service_role",
        )

        r = banco.sql(f"UPDATE conduta_casos SET papel_local = 'Outro lugar' WHERE id = '{caso}';", papel="service_role")

        assert r.returncode != 0
        assert "não muda" in r.stderr

    def test_congelado_e_eliminado_juntos_o_banco_recusa(self, banco):
        caso = _caso(banco)
        assert _eliminar(banco, caso).returncode == 0

        r = banco.sql(
            f"UPDATE conduta_casos SET congelado_em = now(), congelado_por = 'P1' WHERE id = '{caso}';",
            papel="service_role",
        )

        assert r.returncode != 0
        assert "conduta_casos_congelado_check" in r.stderr

    def test_a_migration_nao_cria_tabela_nem_policy(self):
        sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
        assert "CREATE TABLE" not in sql
        assert "CREATE POLICY" not in sql
