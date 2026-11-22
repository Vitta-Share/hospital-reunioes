"""A migration 220, o Recebido do setor no encaminhamento do Núcleo, num
Postgres de verdade (issue #1996).

Sobe um Postgres descartável, aplica a 209 e a 220 (duas vezes) sobre o
mínimo de antes e prova no banco:

- os destinos novos entram no encaminhamento, e os da 209 continuam;
- os marcos do e-mail ao setor e do aviso à Presidência entram somados aos
  que a constraint já aceitava, inclusive um que outra migration da leva
  tenha somado;
- o e-mail ao setor sai sem `destinatario_id`, e a regra antiga continua;
- a tabela nova guarda o hash do token, tem RLS ligada, nenhuma policy, e
  nem o anon nem o authenticated leem.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from test_pendencia_historico_banco import _bin_do_postgres, _Postgres

from app.services.seguranca_do_paciente import encaminhamento, recebimento

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
NOTIFICACAO = "00000000-0000-0000-0000-000000000001"
HASH = "a" * 64

ESQUEMA_ANTERIOR = """
DO $$ BEGIN
  CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE TABLE participantes (id VARCHAR(10) PRIMARY KEY);
CREATE TABLE nsp_notificacoes (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);
CREATE TABLE nsp_avisos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  marco TEXT NOT NULL,
  destinatario_id VARCHAR(10),
  caso_id UUID
);
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_marco_check
  CHECK (marco IN ('documento_gerado', 'assinatura_3', 'assinatura_7', 'assinatura_14',
                   'vigencia_60', 'vigencia_30', 'fim_da_carencia', 'convocacao',
                   'caso_grave', 'confirmacao_de_recebimento', 'marco_de_uma_irma'));
ALTER TABLE nsp_avisos ADD CONSTRAINT nsp_avisos_destinatario_check
  CHECK (destinatario_id IS NOT NULL OR (marco = 'confirmacao_de_recebimento' AND caso_id IS NOT NULL));
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
            pytest.fail("O CI precisa do initdb para provar o Recebido do setor no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.porta = "54220"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok((PASTA / "209_nsp_encaminhamento.sql").read_text(encoding="utf-8"))
        migration = (PASTA / "220_nsp_recebido_do_setor.sql").read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


def _encaminhar(banco, destinos: list[str]):
    lista = ", ".join(f"'{d}'" for d in destinos)
    return banco.sql(
        "INSERT INTO nsp_encaminhamentos (notificacao_id, destinos, motivo, autor_id) "
        f"VALUES ('{NOTIFICACAO}', ARRAY[{lista}]::TEXT[], 'Motivo de teste.', 'P1') RETURNING id;",
        papel="service_role",
    )


def test_os_destinos_do_app_sao_aceitos(banco):
    destinos = [d for d in encaminhamento.DESTINOS if d != encaminhamento.FORA_DE_ESCOPO]
    assert _encaminhar(banco, destinos).returncode == 0


def test_o_destino_inventado_continua_recusado(banco):
    assert "check" in _encaminhar(banco, ["vigilancia"]).stderr.lower()


def _aviso(banco, marco: str, destinatario: str | None, caso: str | None):
    d = f"'{destinatario}'" if destinatario else "NULL"
    c = f"'{caso}'" if caso else "NULL"
    return banco.sql(
        f"INSERT INTO nsp_avisos (marco, destinatario_id, caso_id) VALUES ('{marco}', {d}, {c});",
        papel="service_role",
    )


@pytest.mark.parametrize(
    "marco",
    [recebimento.MARCO_DO_SETOR, recebimento.MARCO_SEM_TITULAR, encaminhamento.MARCO_DA_OUVIDORIA, "marco_de_uma_irma"],
)
def test_os_marcos_novos_entram_somados_aos_que_ja_valiam(banco, marco):
    assert _aviso(banco, marco, "P1", None).returncode == 0, marco


def test_o_email_ao_setor_sai_sem_destinatario_id(banco):
    assert _aviso(banco, recebimento.MARCO_DO_SETOR, None, NOTIFICACAO).returncode == 0


@pytest.mark.parametrize(
    ("marco", "caso"),
    [(recebimento.MARCO_SEM_TITULAR, NOTIFICACAO), (recebimento.MARCO_DO_SETOR, None)],
    ids=["aviso à Presidência sem destinatário", "e-mail ao setor sem caso"],
)
def test_sem_destinatario_continua_recusado_fora_da_regra(banco, marco, caso):
    assert "nsp_avisos_destinatario_check" in _aviso(banco, marco, None, caso).stderr


def test_a_confirmacao_de_recebimento_continua_sem_destinatario(banco):
    assert _aviso(banco, "confirmacao_de_recebimento", None, NOTIFICACAO).returncode == 0


def _recebimento(banco, token_hash: str = HASH, destino: str = "seguranca_do_trabalho"):
    encaminhamento_id = banco.ok(
        "INSERT INTO nsp_encaminhamentos (notificacao_id, destinos, motivo, autor_id) "
        f"VALUES ('{NOTIFICACAO}', ARRAY['{destino}']::TEXT[], 'Motivo.', 'P1') RETURNING id;",
        papel="service_role",
    ).splitlines()[0]
    return banco.sql(
        "INSERT INTO nsp_recebimentos (encaminhamento_id, notificacao_id, destino, setor, destinatario_nome, "
        f"destinatario_email, papel, token_hash) VALUES ('{encaminhamento_id}', '{NOTIFICACAO}', '{destino}', "
        f"'Segurança do Trabalho', 'Responsável', 'r1@hsm.test', 'titular', '{token_hash}');",
        papel="service_role",
    )


def test_o_recebimento_guarda_o_hash_do_token(banco):
    assert _recebimento(banco, "b" * 64).returncode == 0


def test_o_token_em_claro_e_recusado_no_lugar_do_hash(banco):
    assert "check" in _recebimento(banco, "kzN7Vv2r0QhTf3lXqB9dJm4sPcW8yAeR1uGhOiZbNxE").stderr.lower()


def test_a_tabela_nova_tem_rls_ligada_e_nenhuma_policy(banco):
    assert banco.ok("SELECT relrowsecurity FROM pg_class WHERE relname = 'nsp_recebimentos';") == "t"
    assert banco.ok("SELECT count(*) FROM pg_policies WHERE tablename = 'nsp_recebimentos';") == "0"


@pytest.mark.parametrize("papel", ["anon", "authenticated"])
def test_o_anon_nao_le(banco, papel):
    assert "permission denied" in banco.sql("SELECT * FROM nsp_recebimentos;", papel=papel).stderr


def test_o_recibo_e_o_220(banco):
    assert "220" in banco.ok("SELECT numero FROM migracoes_aplicadas ORDER BY numero;").split()
