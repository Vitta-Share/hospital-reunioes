"""A migration 155: as Capacitações do Núcleo (issue #1778, PRD #1764).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere é o
que a issue promete: a lista de temas mínimos nasce vazia (a Diretoria ainda
vai mandar os temas), as tabelas novas têm RLS ligado e nenhuma política, a
presença é uma por pessoa em cada capacitação e o público só tem os dois
valores da tela.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "155_nsp_capacitacoes.sql"

TABELAS_NOVAS = ("nsp_temas_minimos", "nsp_capacitacoes", "nsp_capacitacao_participantes")


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


class TestTabelas:
    def test_cria_os_temas_as_capacitacoes_e_os_participantes(self):
        assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql())) == sorted(TABELAS_NOVAS)

    @pytest.mark.parametrize("tabela", TABELAS_NOVAS)
    def test_toda_tabela_nova_tem_rls_ligado(self, tabela):
        assert re.search(rf"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;", _sql())

    def test_nenhuma_politica(self):
        assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None

    def test_o_publico_tem_check(self):
        bloco = re.search(r"publico\s+TEXT NOT NULL CHECK \(publico IN \((.*?)\)\)", _sql())
        assert bloco
        assert sorted(re.findall(r"'(\w+)'", bloco.group(1))) == ["membros", "profissionais"]

    def test_uma_presenca_por_pessoa_em_cada_capacitacao(self):
        assert re.search(r"UNIQUE\s*\(\s*capacitacao_id\s*,\s*participante_id\s*\)", _sql())

    def test_a_carga_horaria_e_positiva(self):
        assert re.search(r"carga_horaria\s+NUMERIC\(5,\s*1\)\s+NOT NULL CHECK \(carga_horaria > 0\)", _sql())


class TestTemasMinimos:
    def test_a_lista_nasce_vazia(self):
        """Mutante: semear um tema."""
        assert re.search(r"INSERT INTO nsp_temas_minimos", _sql(), re.IGNORECASE) is None

    def test_nenhuma_pessoa_nem_email(self):
        assert re.search(r"INSERT INTO (participantes|participacoes|nsp_capacitac\w+)", _sql(), re.IGNORECASE) is None
        assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None

    def test_o_recibo_e_o_155(self):
        assert "INSERT INTO migracoes_aplicadas (numero) VALUES (155)" in _sql()
