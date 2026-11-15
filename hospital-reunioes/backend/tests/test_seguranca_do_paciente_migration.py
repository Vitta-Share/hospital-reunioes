"""A migration 146: a fundação de Segurança do Paciente (issue #1765, ADR 0095).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere é o
que a issue promete: tabelas novas com RLS ligado e sem política, o Núcleo
criado sem nenhuma pessoa, o perfil e o registro profissional no cadastro, e o
Produto na aba Tecnologia.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "146_nsp_fundacao.sql"

TABELAS_NOVAS = ("colegiados", "participacoes")


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _tabelas_criadas() -> list[str]:
    return re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql())


class TestTabelasNovas:
    def test_cria_o_colegiado_e_a_participacao(self):
        assert sorted(_tabelas_criadas()) == sorted(TABELAS_NOVAS)

    @pytest.mark.parametrize("tabela", TABELAS_NOVAS)
    def test_toda_tabela_nova_tem_rls_ligado(self, tabela):
        """Mutante: tirar o ENABLE ROW LEVEL SECURITY de uma tabela."""
        assert re.search(rf"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;", _sql())

    def test_nenhuma_politica(self):
        """RLS sem política: só o backend, com a service role, lê e grava."""
        assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None

    def test_a_participacao_tem_papel_e_vigencia(self):
        corpo = re.search(r"CREATE TABLE IF NOT EXISTS participacoes\s*\((.*?)\n\);", _sql(), re.DOTALL)
        assert corpo
        for coluna in ("colegiado_id", "participante_id", "papel", "vigencia_inicio", "vigencia_fim"):
            assert re.search(rf"^\s*{coluna}\s", corpo.group(1), re.MULTILINE), coluna
        assert "vigencia_fim >= vigencia_inicio" in corpo.group(1)

    def test_o_papel_tem_check_com_os_tres_papeis(self):
        bloco = re.search(r"papel\s+TEXT NOT NULL CHECK \(papel IN \((.*?)\)\)", _sql())
        assert bloco
        assert sorted(re.findall(r"'(\w+)'", bloco.group(1))) == ["membro", "presidencia", "suplente"]


class TestNenhumDadoDePessoa:
    def test_o_nucleo_nasce_como_colegiado(self):
        assert re.search(r"INSERT INTO colegiados\s*\(slug, nome.*?\)\s*VALUES\s*\(\s*'nsp'", _sql(), re.DOTALL)

    def test_nenhuma_participacao_na_migration(self):
        """Mutante: semear a Presidência por migration."""
        assert re.search(r"INSERT INTO participacoes", _sql(), re.IGNORECASE) is None

    def test_nenhuma_pessoa_na_migration(self):
        assert re.search(r"INSERT INTO participantes", _sql(), re.IGNORECASE) is None
        assert re.search(r"UPDATE participantes", _sql(), re.IGNORECASE) is None

    def test_nenhum_email_na_migration(self):
        assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


class TestCadastroDaPessoa:
    def test_o_perfil_do_modulo_so_aceita_acesso_pleno(self):
        bloco = re.search(r"participantes_perfil_nsp_check\s+CHECK\s*\((.*?)\);", _sql(), re.DOTALL)
        assert bloco
        assert re.findall(r"'(\w+)'", bloco.group(1)) == ["acesso_pleno"]

    @pytest.mark.parametrize("coluna", ["conselho_profissional", "registro_profissional", "registro_uf"])
    def test_o_cadastro_ganha_o_registro_profissional(self, coluna):
        assert re.search(rf"ADD COLUMN IF NOT EXISTS {coluna}\b", _sql())

    def test_a_uf_tem_duas_letras(self):
        assert re.search(r"registro_uf\s*~\s*'\^\[A-Z\]\{2\}\$'", _sql())


class TestProdutoERecibo:
    def test_o_produto_entra_na_aba_tecnologia(self):
        assert re.search(
            r"INSERT INTO tecnologia_produtos\s*\(nome, ordem\)\s*VALUES\s*\(\s*'Segurança do Paciente'", _sql()
        )

    def test_o_recibo_e_o_146(self):
        assert "INSERT INTO migracoes_aplicadas (numero) VALUES (146)" in _sql()
