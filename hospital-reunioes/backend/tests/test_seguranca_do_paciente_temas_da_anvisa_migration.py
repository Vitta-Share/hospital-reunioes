"""A migration 162: os 17 temas mínimos de capacitação do Núcleo (issue #1782).

Lida como texto, do arquivo que o humano cola no Studio. A lista é a do caderno
nº 6 da ANVISA (3ª ed., 2025, item 2.5.2.3) que a Diretoria mandou em
18/11/2026. Rodar de novo, ou rodar depois de a Presidência já ter incluído um
tema com o mesmo nome, não duplica nada.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "162_nsp_temas_minimos_da_anvisa.sql"

TEMAS_DA_ANVISA = [
    "Qualidade e Segurança do Paciente",
    "Práticas de Segurança do Paciente",
    "Regulamentações sobre Qualidade e Segurança do Paciente",
    "Princípios Básicos em Segurança do Paciente",
    "Tipos de Eventos Adversos Relacionados à Assistência à Saúde",
    "Protocolos de Segurança do Paciente",
    "Indicadores de Segurança do Paciente",
    "Estratégias para a Melhoria da Qualidade e Segurança",
    "Cultura de Segurança do Paciente",
    "Núcleo de Segurança do Paciente",
    "Plano de Segurança do Paciente",
    "Gestão de Riscos",
    "Sistema de Notificação de Incidentes",
    "Investigação do Incidente",
    "Análise de Causa-Raiz",
    "Análise dos Modos de Falha (FMEA)",
    "Engajamento dos Pacientes e Familiares na Assistência Prestada",
]


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _insert_dos_temas() -> str:
    bloco = re.search(r"INSERT INTO nsp_temas_minimos \(nome\) VALUES(.*?);", _sql(), re.DOTALL)
    assert bloco, "a migration não carrega os temas"
    return bloco.group(0)


def test_carrega_os_17_temas_da_anvisa_na_ordem():
    """Mutante: tirar, trocar ou reescrever um tema."""
    assert re.findall(r"\('([^']+)'\)", _insert_dos_temas()) == TEMAS_DA_ANVISA


def test_tema_que_ja_existe_com_o_mesmo_nome_fica_como_esta():
    """Mutante: tirar o ON CONFLICT, e a migration quebra no índice único da 155."""
    assert re.search(r"ON CONFLICT \(\(lower\(btrim\(nome\)\)\)\) DO NOTHING;$", _insert_dos_temas())


def test_so_mexe_nos_temas():
    inserts = re.findall(r"INSERT INTO (\w+)", _sql())
    assert sorted(inserts) == ["migracoes_aplicadas", "nsp_temas_minimos"]
    assert re.search(r"\b(UPDATE|DELETE|DROP|ALTER|TRUNCATE)\b", _sql(), re.IGNORECASE) is None


def test_o_recibo_e_o_162():
    assert "INSERT INTO migracoes_aplicadas (numero) VALUES (162) ON CONFLICT (numero) DO NOTHING;" in _sql()
