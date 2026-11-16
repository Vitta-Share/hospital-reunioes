"""A migration 154: a reunião rápida de segurança (issue #1777, PRD #1764).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere é o
que a issue promete: o registro fica numa tabela própria, longe de `reunioes`
e do pipeline da ata, o banco também recusa mais de três linhas, e a tabela
nova tem RLS ligado e nenhuma política.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "154_nsp_reunioes_rapidas.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


class TestReuniaoRapidaNoBanco:
    def test_cria_so_a_tabela_da_reuniao_rapida(self):
        assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql()) == ["nsp_reunioes_rapidas"]

    def test_nao_mexe_na_tabela_de_reunioes(self):
        """A rápida não entra no pipeline da ata: `reunioes` fica como está."""
        assert re.search(r"\breunioes\b(?!_rapidas)", _sql()) is None

    def test_o_banco_recusa_mais_de_tres_linhas(self):
        """Mutante: trocar o teto de três linhas por quatro."""
        assert re.search(r"cardinality\(string_to_array\(texto, E'\\n'\)\) <= 3", _sql())

    def test_rls_ligado_e_nenhuma_politica(self):
        assert re.search(r"ALTER TABLE nsp_reunioes_rapidas ENABLE ROW LEVEL SECURITY;", _sql())
        assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None

    def test_o_recibo_e_o_154(self):
        assert "INSERT INTO migracoes_aplicadas (numero) VALUES (154)" in _sql()
