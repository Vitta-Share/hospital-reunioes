"""A migration 159: a assinatura dos documentos do Núcleo (issue #1771, ADR 0095).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere: o
envio e os signatários nascem com RLS e sem política, um envelope aponta para
um envio só, uma versão tem um envio aberto por vez, a versão para assinatura
nasce fora da vigência, a troca da vigente na assinatura não passa por cima de
versão mais nova, as duas funções são só do backend, e nenhuma pessoa entra
por migration.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "159_nsp_assinatura_dos_documentos.sql"
)

FUNCOES = ("nsp_versao_para_assinatura", "nsp_tornar_vigente")


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _corpo(funcao: str) -> str:
    achado = re.search(rf"FUNCTION {funcao}\(.*?\$\$(.*?)\$\$;", _sql(), re.DOTALL)
    assert achado, funcao
    return achado.group(1)


def test_o_envio_e_os_signatarios_nascem_com_rls_e_sem_politica():
    assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql()) == [
        "nsp_documentos_envios",
        "nsp_documentos_signatarios",
    ]
    for tabela in ("nsp_documentos_envios", "nsp_documentos_signatarios"):
        assert f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;" in _sql(), tabela
    assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None


def test_um_envelope_aponta_para_um_envio_so():
    assert re.search(r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON nsp_documentos_envios\s*\(documento_key\)", _sql())


def test_um_envio_aberto_por_versao():
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON nsp_documentos_envios\s*\(documento_id\)\s+"
        r"WHERE situacao IN \('gerado', 'enviado'\)",
        _sql(),
    )


def test_o_ultimo_envio_da_versao_tem_indice():
    assert re.search(
        r"CREATE INDEX IF NOT EXISTS \w+\s+ON nsp_documentos_envios\s*\(documento_id, created_at DESC\)\s*;", _sql()
    )


def test_um_signatario_por_pessoa_em_cada_envio():
    assert re.search(r"UNIQUE \(envio_id, participante_id\)", _sql())
    qualidade = re.search(r"qualidade\s+TEXT NOT NULL\s+CHECK \(qualidade IN \(([^)]*)\)\)", _sql())
    assert qualidade
    assert qualidade.group(1) == "'diretoria_executiva', 'presidencia'"


def test_a_versao_para_assinatura_nasce_fora_da_vigencia():
    """Mutante: inserir a versão com vigente = true. A anterior deixaria de
    valer antes das assinaturas."""
    corpo = _corpo("nsp_versao_para_assinatura")
    insercao = re.search(r"INSERT INTO nsp_documentos\s*\(([^)]*)\)\s*VALUES\s*\(([^)]*)\)", corpo)
    assert insercao
    colunas = [c.strip() for c in insercao.group(1).split(",")]
    valores = [v.strip() for v in insercao.group(2).split(",")]
    assert dict(zip(colunas, valores, strict=True))["vigente"] == "false"
    assert "UPDATE nsp_documentos" not in corpo
    assert re.search(r"pg_advisory_xact_lock\(hashtext\('nsp_documentos:' \|\| p_tipo\)\)", corpo)


def test_a_troca_da_vigente_nao_passa_por_cima_de_versao_mais_nova():
    corpo = _corpo("nsp_tornar_vigente")
    assert re.search(r"pg_advisory_xact_lock\(hashtext\('nsp_documentos:' \|\| v_doc\.tipo\)\)", corpo)
    assert re.search(r"tipo = v_doc\.tipo AND vigente AND versao > v_doc\.versao", corpo)
    assert re.search(r"UPDATE nsp_documentos SET vigente = false WHERE tipo = v_doc\.tipo AND vigente", corpo)


def test_as_funcoes_sao_so_do_backend():
    for funcao in FUNCOES:
        assert re.search(
            rf"REVOKE EXECUTE ON FUNCTION {funcao}\([^)]*\)\s+FROM PUBLIC, anon, authenticated;", _sql()
        ), funcao
        assert re.search(rf"GRANT EXECUTE ON FUNCTION {funcao}\([^)]*\) TO service_role;", _sql()), funcao
        assert re.search(rf"FUNCTION {funcao}\([^)]*\)[^$]*SET search_path = public", _sql(), re.DOTALL), funcao


def test_nenhuma_pessoa_na_migration():
    assert re.search(r"INSERT INTO (participacoes|participantes)\b", _sql(), re.IGNORECASE) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_sem_travessao_no_arquivo():
    texto = MIGRATION.read_text(encoding="utf-8")
    assert chr(0x2013) not in texto and chr(0x2014) not in texto


def test_o_recibo_e_o_159():
    assert (
        _sql()
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (159) ON CONFLICT (numero) DO NOTHING;")
    )
