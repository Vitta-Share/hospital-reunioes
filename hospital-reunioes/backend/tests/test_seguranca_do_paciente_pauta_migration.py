"""A migration 152: a pauta e os convocados das reuniões do Núcleo (issue #1773).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere é o
que a issue promete: uma pauta por reunião, cada pessoa convocada uma vez por
reunião, só estados que contam para quórum, RLS ligado sem política e nenhum
dado de pessoa.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "152_nsp_pauta_e_convocacao.sql"

TABELAS_NOVAS = ("nsp_pautas", "nsp_convocados")


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _tabela(nome: str) -> str:
    bloco = re.search(rf"CREATE TABLE IF NOT EXISTS {nome}\s*\((.*?)\n\);", _sql(), re.DOTALL)
    assert bloco, f"a tabela {nome} sumiu"
    return bloco.group(1)


class TestTabelas:
    def test_cria_a_pauta_e_os_convocados(self):
        assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql())) == sorted(TABELAS_NOVAS)

    @pytest.mark.parametrize("tabela", TABELAS_NOVAS)
    def test_toda_tabela_nova_tem_rls_ligado(self, tabela):
        assert re.search(rf"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;", _sql())

    def test_nenhuma_politica(self):
        assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None

    def test_uma_pauta_por_reuniao(self):
        assert re.search(r"id_reuniao\s+VARCHAR\(20\) PRIMARY KEY REFERENCES reunioes", _tabela("nsp_pautas"))

    def test_cada_pessoa_convocada_uma_vez_por_reuniao(self):
        """O segundo clique bate na guarda do banco, não manda outro e-mail."""
        assert re.search(r"UNIQUE\s*\(\s*id_reuniao\s*,\s*participante_id\s*\)", _tabela("nsp_convocados"))

    def test_so_estado_que_conta_para_quorum_e_gravado(self):
        bloco = re.search(r"estado\s+TEXT NOT NULL CHECK \(estado IN \((.*?)\)\)", _tabela("nsp_convocados"))
        assert bloco
        assert sorted(re.findall(r"'(\w+)'", bloco.group(1))) == ["a_vencer", "ativo", "em_carencia"]

    def test_nenhuma_pessoa_nem_email(self):
        assert re.search(r"INSERT INTO (participantes|participacoes|nsp_convocados)", _sql(), re.IGNORECASE) is None
        assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None

    def test_o_recibo_e_o_152(self):
        assert "INSERT INTO migracoes_aplicadas (numero) VALUES (152)" in _sql()
