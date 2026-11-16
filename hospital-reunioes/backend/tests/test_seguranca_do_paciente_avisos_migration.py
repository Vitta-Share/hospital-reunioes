"""A migration 158: os avisos do Termo e da vigência (issue #1770).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere: os
marcos que o serviço grava são os que o banco aceita, a chave única que
impede o mesmo aviso duas vezes, RLS e nenhuma política, e nenhuma pessoa
entra por migration (decisão 12).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.seguranca_do_paciente import avisos  # noqa: E402

PASTA = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MIGRATION = PASTA / "158_nsp_avisos.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _corpo() -> str:
    corpo = re.search(r"CREATE TABLE IF NOT EXISTS nsp_avisos\s*\((.*?)\n\);", _sql(), re.DOTALL)
    assert corpo
    return corpo.group(1)


def test_o_banco_aceita_exatamente_os_marcos_que_o_servico_grava():
    bloco = re.search(r"CHECK \(marco IN \((.*?)\)\)", _corpo(), re.DOTALL)
    assert bloco

    assert set(re.findall(r"'(\w+)'", bloco.group(1))) == set(avisos.DESTINATARIOS)


def test_o_mesmo_aviso_nao_entra_duas_vezes():
    assert "UNIQUE (participacao_id, marco, referencia, destinatario_id)" in _corpo()


def test_a_falha_fica_na_linha():
    assert set(re.findall(r"'(\w+)'", re.search(r"situacao.*?\)\)", _corpo(), re.DOTALL).group(0))) == {
        "pendente",
        "enviado",
        "falhou",
    }
    assert re.search(r"^\s*erro\s+TEXT", _corpo(), re.MULTILINE)


def test_a_tabela_nasce_com_rls_e_sem_politica():
    assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql()) == ["nsp_avisos"]
    assert "ALTER TABLE nsp_avisos ENABLE ROW LEVEL SECURITY;" in _sql()
    assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None


def test_nenhuma_pessoa_na_migration():
    assert re.search(r"INSERT INTO (participacoes|participantes|nsp_avisos)\b", _sql(), re.IGNORECASE) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_o_recibo_e_o_158():
    assert (
        _sql()
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (158) ON CONFLICT (numero) DO NOTHING;")
    )
