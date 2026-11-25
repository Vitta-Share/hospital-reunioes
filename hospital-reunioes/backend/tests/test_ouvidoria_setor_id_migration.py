"""A migration 238 (era a 172) num Postgres de verdade (issue #1983).

Sobe um Postgres descartável pelo mesmo arnês do teste da migration 169, monta
o mínimo de `setores` e `ouvidoria_protocolos`, aplica a migration duas vezes e
prova no banco que os casos antigos ganham o id pelo nome, sem diferença de
maiúscula, e que o nome que não casa fica com o id vazio e aparece no
relatório da migration, sem quebrar.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from test_pendencia_historico_banco import _bin_do_postgres, _Postgres  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "238_ouvidoria_setor_id.sql"

S_RECEPCAO = "00000000-0000-0000-0000-000000000001"
S_FARMACIA = "00000000-0000-0000-0000-000000000002"
S_INATIVO = "00000000-0000-0000-0000-000000000003"

# O mínimo das tabelas de antes da 172 (migrations 027 e 063).
ESQUEMA_ANTERIOR = f"""
CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);

CREATE TABLE setores (
  id UUID PRIMARY KEY,
  nome TEXT NOT NULL,
  ativo BOOLEAN NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX setores_nome_lower ON setores (lower(nome));

CREATE TABLE ouvidoria_protocolos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  protocolo TEXT,
  setor TEXT NOT NULL CHECK (btrim(setor) <> '')
);

INSERT INTO setores (id, nome, ativo) VALUES
  ('{S_RECEPCAO}', 'Recepção', true),
  ('{S_FARMACIA}', 'Farmácia', true),
  ('{S_INATIVO}', 'Almoxarifado', false);

INSERT INTO ouvidoria_protocolos (protocolo, setor) VALUES
  ('2026-0001', 'Recepção'),
  ('2026-0002', 'RECEPÇÃO'),
  ('2026-0003', ' farmácia '),
  ('2026-0004', 'almoxarifado'),
  ('2026-0005', 'Setor Inventado'),
  ('2026-0006', 'Setor Inventado'),
  ('2026-0007', 'A definir');
"""


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar a migration no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    # Porta própria: com o pytest-xdist, o banco da 169 pode estar de pé ao lado.
    pg.porta = "54172"
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        migration = MIGRATION.read_text(encoding="utf-8")
        primeira = pg.sql(migration)
        assert primeira.returncode == 0, primeira.stderr
        segunda = pg.sql(migration)  # rodar duas vezes é inofensivo
        assert segunda.returncode == 0, segunda.stderr
        pg.relatorio = primeira.stderr
        yield pg
    finally:
        pg.descer()


def _setor_id(banco, protocolo: str) -> str:
    return banco.ok(f"SELECT coalesce(setor_id::text, '') FROM ouvidoria_protocolos WHERE protocolo = '{protocolo}';")


class TestPreenchimentoPeloNome:
    """Critério 1: os casos existentes ganham o id pelo nome."""

    @pytest.mark.parametrize(
        ("protocolo", "esperado"),
        [("2026-0001", S_RECEPCAO), ("2026-0002", S_RECEPCAO), ("2026-0003", S_FARMACIA)],
        ids=["mesma-grafia", "maiuscula", "espaco-e-minuscula"],
    )
    def test_o_caso_antigo_ganha_o_id_do_setor_de_mesmo_nome(self, banco, protocolo, esperado):
        assert _setor_id(banco, protocolo) == esperado

    def test_o_setor_desativado_continua_sendo_o_setor_do_caso_antigo(self, banco):
        assert _setor_id(banco, "2026-0004") == S_INATIVO

    def test_o_texto_do_setor_fica_como_estava(self, banco):
        assert banco.ok("SELECT setor FROM ouvidoria_protocolos WHERE protocolo = '2026-0002';") == "RECEPÇÃO"

    def test_a_coluna_aponta_para_a_tabela_de_setores(self, banco):
        r = banco.sql(
            "INSERT INTO ouvidoria_protocolos (protocolo, setor, setor_id) "
            "VALUES ('2026-0099', 'X', '00000000-0000-0000-0000-000000000099');"
        )
        assert r.returncode != 0
        assert "foreign key" in r.stderr


class TestNomeQueNaoCasa:
    """Critério 2: o nome que não casa fica sem id e vai para o relatório."""

    def test_o_caso_que_nao_casa_fica_com_o_id_vazio(self, banco):
        assert _setor_id(banco, "2026-0005") == ""
        assert _setor_id(banco, "2026-0006") == ""

    def test_o_relatorio_lista_o_nome_e_os_protocolos(self, banco):
        assert 'setor "Setor Inventado" não casa com nenhum setor: 2026-0005, 2026-0006' in banco.relatorio

    def test_o_relatorio_conta_os_orfaos_e_os_pendentes_a_parte(self, banco):
        assert "2 caso(s) sem setor do cadastro, 1 caso(s) ainda A definir" in banco.relatorio
        assert '"A definir"' not in banco.relatorio, "o caso sem área é fila de triagem, não erro"

    def test_o_recibo_e_gravado(self, banco):
        assert banco.ok("SELECT numero FROM migracoes_aplicadas;") == "238"
