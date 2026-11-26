"""As migrations da Mensagem pelo terminal e da observação do Validar (issues #1805 e #2013).

As rotas que gravavam nessas colunas saíram da ponte de automação na issue
#2281 (ADR 0113, decisões 7 e 10), e as colunas ficam no banco, sem migration
que apague. Os testes das rotas saíram com elas; o das migrations fica, para
nenhuma das duas mudar depois de aplicada.
"""

from __future__ import annotations

from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION_161 = MIGRATIONS / "161_tecnologia_origem_da_mensagem.sql"
MIGRATION_166 = MIGRATIONS / "166_tecnologia_observacao_da_validacao.sql"


def _sql_sem_comentario(migration: Path) -> str:
    linhas = migration.read_text(encoding="utf-8").splitlines()
    return "\n".join(linha for linha in linhas if not linha.lstrip().startswith("--")).strip()


class TestAMigration161:
    def test_a_origem_entra_com_app_como_padrao_e_so_os_dois_valores(self):
        sql = _sql_sem_comentario(MIGRATION_161)

        assert (
            "ALTER TABLE tecnologia_conversa_da_demanda ADD COLUMN IF NOT EXISTS origem TEXT NOT NULL DEFAULT 'app';"
            in sql
        )
        assert "CHECK (origem IN ('app', 'terminal'))" in sql

    def test_termina_com_o_recibo_do_proprio_numero(self):
        assert _sql_sem_comentario(MIGRATION_161).endswith(
            "INSERT INTO migracoes_aplicadas (numero) VALUES (161) ON CONFLICT (numero) DO NOTHING;"
        )


class TestAMigration166:
    def test_a_tabela_do_envio_ganha_a_origem_e_o_texto_original_com_o_recibo_166(self):
        sql = MIGRATION_166.read_text(encoding="utf-8")
        assert "ALTER TABLE tecnologia_envios_aos_desenvolvedores" in sql
        assert "ADD COLUMN IF NOT EXISTS origem" in sql
        assert "'conversa'" in sql and "'validacao'" in sql
        assert "ADD COLUMN IF NOT EXISTS texto_original" in sql
        assert "CREATE POLICY" not in sql.upper()
        assert sql.rstrip().endswith(
            "INSERT INTO migracoes_aplicadas (numero) VALUES (166) ON CONFLICT (numero) DO NOTHING;"
        )
