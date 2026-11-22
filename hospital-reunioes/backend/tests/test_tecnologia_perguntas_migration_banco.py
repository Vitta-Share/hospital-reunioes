"""A migration 211 da Pergunta da Vitta num Postgres de verdade (issue #2116,
PRD #2112, ADR 0109).

Uma migration só para o PRD inteiro, porque cada migration espera o Pedro
aplicar: a tabela da Pergunta já com as colunas da resposta, da resolução, das
datas de cada passagem e do lembrete, e a tabela da conversa particular do Me
explique (por Pergunta e por pessoa). Sobe um Postgres descartável (o apoio da
migration 169), monta o mínimo das tabelas de antes, aplica a migration duas
vezes e prova no banco:

- as duas tabelas novas, com RLS ligada e nenhuma policy;
- toda coluna do PRD existe na tabela da Pergunta;
- a linha que o serviço grava entra, e o estado fora dos quatro é recusado;
- o Me explique tem uma conversa por Pergunta e por pessoa.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "211_tecnologia_pergunta_da_vitta.sql"

PERGUNTAS = "tecnologia_perguntas"
ME_EXPLIQUE = "tecnologia_conversas_do_me_explique"

# Toda coluna que o PRD #2112 pede na Pergunta: o registro (decisões 1 e 3),
# as opções com a recomendada (4), a resposta com quem respondeu e em nome de
# quem (5), a resolução com o que foi decidido e o que destravou (6), as datas
# de cada passagem e o lembrete único (7).
COLUNAS_DA_PERGUNTA = {
    "id",
    "demanda_id",
    "mensagem_id",
    "autor_id",
    "destinatario_id",
    "assunto",
    "texto",
    "por_que_precisa",
    "o_que_esta_parado",
    "o_que_anda_depois",
    "ganho",
    "opcoes",
    "recomendada",
    "porque_da_recomendada",
    "estado",
    "resposta_opcao",
    "resposta_texto",
    "respondida_por",
    "respondida_em_nome_de",
    "respondida_em",
    "resolucao_decidido",
    "resolucao_destravou",
    "resolvida_em",
    "cancelada_em",
    "lembrete_enviado_em",
    "criado_em",
}

# O mínimo de antes da 211 (migrations 001, 102, 129, 161 e 165).
ESQUEMA_ANTERIOR = """
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN NOSUPERUSER BYPASSRLS;

CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);
CREATE TABLE participantes (id VARCHAR(10) PRIMARY KEY, nome_completo TEXT);
CREATE TABLE tecnologia_demandas (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), titulo TEXT);
CREATE TABLE tecnologia_conversa_da_demanda (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demanda_id  UUID NOT NULL REFERENCES tecnologia_demandas(id) ON DELETE CASCADE,
  autor_id    VARCHAR(10) REFERENCES participantes(id) ON DELETE SET NULL,
  texto       TEXT NOT NULL,
  origem      TEXT NOT NULL DEFAULT 'app' CHECK (origem IN ('app', 'terminal', 'sistema')),
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO participantes (id, nome_completo) VALUES ('P001', 'Pedro'), ('P004', 'Diretora');
INSERT INTO tecnologia_demandas (id, titulo) VALUES ('7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d', 'A Ata');
INSERT INTO tecnologia_conversa_da_demanda (id, demanda_id, autor_id, texto, origem)
VALUES (
  '0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e', '7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d', 'P001', 'Quem assina?', 'terminal'
);

GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54211"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _pergunta(banco, *, estado: str = "aberta", mensagem: str = "0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e"):
    """A linha que `tecnologia_perguntas.criar` grava."""
    return banco.sql(
        f"INSERT INTO {PERGUNTAS} (demanda_id, mensagem_id, autor_id, destinatario_id, assunto, texto,"
        " por_que_precisa, o_que_esta_parado, o_que_anda_depois, ganho, opcoes, recomendada,"
        " porque_da_recomendada, estado) VALUES ("
        "'7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d', "
        f"'{mensagem}', 'P001', 'P004', 'quem assina', 'Quem assina?', 'a', 'b', 'c', 'd', "
        """'[{"letra": "A", "texto": "Um"}, {"letra": "B", "texto": "Outro"}]'::jsonb, 'B', 'porque', """
        f"'{estado}') RETURNING id;",
        papel="service_role",
    )


def test_a_migration_cria_as_duas_tabelas_do_prd():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", sql)) == sorted([PERGUNTAS, ME_EXPLIQUE])


@pytest.mark.parametrize("tabela", [PERGUNTAS, ME_EXPLIQUE])
def test_toda_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco, tabela):
    assert banco.ok(f"SELECT relrowsecurity FROM pg_class WHERE relname = '{tabela}';") == "t"
    assert banco.ok(f"SELECT count(*) FROM pg_policies WHERE tablename = '{tabela}';") == "0"


def test_a_pergunta_tem_todas_as_colunas_do_prd(banco):
    colunas = banco.ok(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{PERGUNTAS}';")
    assert set(colunas.splitlines()) == COLUNAS_DA_PERGUNTA


def test_a_linha_que_o_servico_grava_entra_aberta(banco):
    r = _pergunta(banco)
    assert r.returncode == 0, r.stderr
    pergunta = r.stdout.strip().splitlines()[0]
    assert banco.ok(f"SELECT estado, opcoes->1->>'texto' FROM {PERGUNTAS} WHERE id = '{pergunta}';") == "aberta|Outro"


def test_estado_fora_dos_quatro_e_recusado(banco):
    r = _pergunta(banco, estado="pendente")
    assert r.returncode != 0
    assert "estado" in r.stderr


def test_o_me_explique_tem_uma_conversa_por_pergunta_e_por_pessoa(banco):
    pergunta = banco.ok(f"SELECT id FROM {PERGUNTAS} LIMIT 1;")
    inserir = f"INSERT INTO {ME_EXPLIQUE} (pergunta_id, participante_id) VALUES ('{pergunta}', 'P004');"
    assert banco.sql(inserir, papel="service_role").returncode == 0
    repetida = banco.sql(inserir, papel="service_role")
    assert repetida.returncode != 0
    assert "duplicate" in repetida.stderr or "duplicada" in repetida.stderr
    assert banco.ok(f"SELECT jsonb_typeof(mensagens) FROM {ME_EXPLIQUE};") == "array"


def test_o_recibo_e_o_211():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert sql.rstrip().endswith(
        "INSERT INTO migracoes_aplicadas (numero) VALUES (211) ON CONFLICT (numero) DO NOTHING;"
    )
