"""A migration 205, o encaminhamento da triagem do Núcleo, num Postgres de
verdade (issue #1995).

Sobe um Postgres descartável, aplica a 205 duas vezes sobre o mínimo de antes
e prova no banco:

- o marco do e-mail ao ouvidor entra somado aos que a constraint já aceitava,
  inclusive um que outra migration da leva tenha somado antes;
- os destinos aceitos são os do app, fora de escopo vai sozinho e só ele tem a
  orientação a quem notificou;
- a tabela nova tem RLS ligada, nenhuma policy, e nem o anon nem o
  authenticated leem, mesmo com o GRANT padrão do Supabase.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

from app.services.seguranca_do_paciente import encaminhamento

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "205_nsp_encaminhamento.sql"
NOTIFICACAO = "00000000-0000-0000-0000-000000000001"

# O mínimo de antes: as tabelas que a 205 referencia e o registro de e-mail
# com a constraint de marcos da 182, mais um marco que outra migration da
# mesma leva teria somado antes desta.
ESQUEMA_ANTERIOR = """
DO $$ BEGIN
  CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE TABLE participantes (id VARCHAR(10) PRIMARY KEY);
CREATE TABLE nsp_notificacoes (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);
CREATE TABLE nsp_avisos (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), marco TEXT NOT NULL);
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check
  CHECK (marco IN ('documento_gerado', 'assinatura_3', 'assinatura_7', 'assinatura_14',
                   'vigencia_60', 'vigencia_30', 'fim_da_carencia', 'convocacao',
                   'caso_grave', 'confirmacao_de_recebimento', 'marco_de_uma_irma'));
INSERT INTO participantes VALUES ('P1');
INSERT INTO nsp_notificacoes (id) VALUES ('00000000-0000-0000-0000-000000000001');
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar o encaminhamento no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54205"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _aviso(banco, marco: str):
    return banco.sql(f"INSERT INTO nsp_avisos (marco) VALUES ('{marco}');", papel="service_role")


@pytest.mark.parametrize("marco", [encaminhamento.MARCO_DA_OUVIDORIA, "caso_grave", "marco_de_uma_irma"])
def test_o_marco_do_ouvidor_entra_somado_aos_que_ja_valiam(banco, marco):
    assert _aviso(banco, marco).returncode == 0, marco


def test_o_marco_inventado_continua_recusado(banco):
    assert "nsp_avisos_marco_check" in _aviso(banco, "marco_inventado").stderr


def _encaminhar(banco, destinos: list[str], orientacao: str | None = None):
    lista = ", ".join(f"'{d}'" for d in destinos)
    valor = f"'{orientacao}'" if orientacao else "NULL"
    return banco.sql(
        "INSERT INTO nsp_encaminhamentos (notificacao_id, destinos, motivo, orientacao, autor_id) "
        f"VALUES ('{NOTIFICACAO}', ARRAY[{lista}]::TEXT[], 'Motivo de teste.', {valor}, 'P1');",
        papel="service_role",
    )


@pytest.mark.parametrize(
    ("destinos", "orientacao"),
    [
        ([d for d in encaminhamento.DESTINOS if d != encaminhamento.FORA_DE_ESCOPO], None),
        ([encaminhamento.FORA_DE_ESCOPO], "Procure o Departamento Pessoal."),
    ],
    ids=["os outros três juntos", "fora de escopo com a orientação"],
)
def test_os_destinos_do_app_sao_aceitos(banco, destinos, orientacao):
    assert _encaminhar(banco, destinos, orientacao).returncode == 0


@pytest.mark.parametrize(
    ("destinos", "orientacao"),
    [
        ([], None),
        (["vigilancia"], None),
        ([encaminhamento.FORA_DE_ESCOPO], None),
        ([encaminhamento.FORA_DE_ESCOPO, encaminhamento.OUVIDORIA], "Procure o Departamento Pessoal."),
        ([encaminhamento.OUVIDORIA], "Orientação fora do fora de escopo."),
    ],
    ids=[
        "sem destino",
        "destino inventado",
        "fora de escopo sem orientação",
        "fora de escopo somado",
        "orientação sem fora de escopo",
    ],
)
def test_o_encaminhamento_fora_das_regras_e_recusado(banco, destinos, orientacao):
    assert "check" in _encaminhar(banco, destinos, orientacao).stderr.lower()


def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok("SELECT relrowsecurity FROM pg_class WHERE relname = 'nsp_encaminhamentos';") == "t"
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename = 'nsp_encaminhamentos';") == "0"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_o_anon_nao_le(banco, papel):
    assert "permission denied" in banco.sql("SELECT * FROM nsp_encaminhamentos;", papel=papel).stderr


def test_o_recibo_e_o_205(banco):
    assert banco.ok("SELECT numero FROM migracoes_aplicadas;") == "205"
