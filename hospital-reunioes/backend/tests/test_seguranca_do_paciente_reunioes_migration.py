"""A migration 148: as reuniões do Núcleo (issue #1772, PRD #1764, ADR 0095).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere é o
que a issue promete ao banco: a reunião ganha o vínculo com o Colegiado, o
tipo aceita os quatro tipos do Núcleo, e um tipo do Núcleo não existe sem o
Colegiado. Nenhum dado de pessoa.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "148_nsp_reunioes_do_nucleo.sql"

TIPOS_DE_ANTES = ["Diretoria", "Gerencial", "Coordenação", "Mensal", "Extraordinária"]
TIPOS_DO_NUCLEO = [
    "Ordinária mensal",
    "Análise de evento",
    "Apresentação à Diretoria",
    "Reunião rápida de segurança",
]


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _tipos_do_check(nome: str) -> list[str]:
    bloco = re.search(rf"CONSTRAINT {nome}\s+CHECK\s*\((.*?)\);", _sql(), re.DOTALL)
    assert bloco, nome
    return re.findall(r"'([^']+)'", bloco.group(1))


def test_a_reuniao_ganha_o_vinculo_com_o_colegiado():
    assert re.search(
        r"ALTER TABLE reunioes\s+ADD COLUMN IF NOT EXISTS colegiado_id UUID REFERENCES colegiados\(id\)", _sql()
    )


def test_o_tipo_aceita_os_de_antes_e_os_quatro_do_nucleo():
    """Mutante: esquecer um dos tipos de antes ao recriar o CHECK."""
    assert _tipos_do_check("reunioes_tipo_check") == TIPOS_DE_ANTES + TIPOS_DO_NUCLEO


def test_tipo_do_nucleo_so_existe_com_o_colegiado():
    assert _tipos_do_check("reunioes_tipo_do_nucleo_check") == TIPOS_DO_NUCLEO
    assert "colegiado_id IS NOT NULL" in re.search(
        r"CONSTRAINT reunioes_tipo_do_nucleo_check\s+CHECK\s*\((.*?)\);", _sql(), re.DOTALL
    ).group(1)


def test_o_check_antigo_cai_antes_de_voltar():
    sql = _sql()
    assert sql.index("DROP CONSTRAINT IF EXISTS reunioes_tipo_check") < sql.index("ADD CONSTRAINT reunioes_tipo_check")


def test_nenhum_dado_de_pessoa():
    sql = _sql()
    assert re.search(r"INSERT INTO (participantes|participacoes|reunioes)\b", sql, re.IGNORECASE) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_o_recibo_e_o_148():
    assert "INSERT INTO migracoes_aplicadas (numero) VALUES (148)" in _sql()
