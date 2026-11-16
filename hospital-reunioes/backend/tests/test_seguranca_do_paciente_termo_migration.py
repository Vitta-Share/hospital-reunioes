"""A migration 151: o Termo de Adesão do Núcleo (issue #1768, ADR 0095).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere: a
Participação ganha os carimbos de gerado e enviado, o envio do Termo nasce com
RLS e sem política, um envelope aponta para um envio só, a trilha aceita a
liberação manual com motivo, o Termo assinado mora nos Documentos uma vez por
envio, o arquivo vai para bucket privado, e nenhuma pessoa entra por migration.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "151_nsp_termo_de_adesao.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def test_a_participacao_ganha_os_carimbos_de_gerado_e_enviado():
    for coluna in ("termo_gerado_em", "termo_enviado_em"):
        assert re.search(rf"ALTER TABLE participacoes\s+ADD COLUMN IF NOT EXISTS {coluna} TIMESTAMPTZ", _sql()), coluna


def test_o_envio_do_termo_nasce_com_rls_e_sem_politica():
    assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql()) == ["nsp_termos_envios"]
    assert "ALTER TABLE nsp_termos_envios ENABLE ROW LEVEL SECURITY;" in _sql()
    assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None


def test_um_envelope_aponta_para_um_envio_so():
    """O retorno da assinatura acha o envio pela chave do documento."""
    assert re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON nsp_termos_envios\s*\(documento_key\)", _sql())


def test_um_envio_aberto_por_participacao():
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON nsp_termos_envios\s*\(participacao_id\)\s+"
        r"WHERE situacao IN \('gerado', 'enviado'\)",
        _sql(),
    )


def test_a_trilha_aceita_a_liberacao_manual_com_motivo():
    assert re.search(r"ALTER TABLE participacoes_trilha\s+ADD COLUMN IF NOT EXISTS motivo TEXT", _sql())
    checagem = re.search(r"ADD CONSTRAINT participacoes_trilha_acao_check\s+CHECK \(acao IN \(([^)]*)\)\)", _sql())
    assert checagem
    for acao in ("cadastro", "encerramento", "termo_enviado", "termo_reenviado", "termo_assinado", "liberacao_manual"):
        assert f"'{acao}'" in checagem.group(1), acao


def test_o_termo_assinado_entra_nos_documentos_uma_vez_por_envio():
    assert re.search(
        r"ALTER TABLE nsp_documentos\s+ADD COLUMN IF NOT EXISTS termo_envio_id UUID UNIQUE "
        r"REFERENCES nsp_termos_envios",
        _sql(),
    )


def test_o_arquivo_do_termo_vai_para_bucket_privado():
    assert re.search(
        r"INSERT INTO storage\.buckets \(id, name, public\)\s+VALUES \('nsp-documentos', 'nsp-documentos', false\)",
        _sql(),
    )


def test_nenhuma_pessoa_na_migration():
    assert re.search(r"INSERT INTO (participacoes|participantes)\b", _sql(), re.IGNORECASE) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_sem_travessao_no_arquivo():
    texto = MIGRATION.read_text(encoding="utf-8")
    assert chr(0x2013) not in texto and chr(0x2014) not in texto


def test_o_recibo_e_o_151():
    assert (
        _sql()
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (151) ON CONFLICT (numero) DO NOTHING;")
    )
