"""A migration 241: a marca de Responsável técnico no cadastro (issue #2248,
PRD #2247, ADR 0112).

Lida como texto, do arquivo que o humano cola no Studio, no padrão do teste da
migration 159. O que se confere: `participantes` ganha a marca, falsa por
padrão; o banco garante uma pessoa marcada só; a troca desmarca a anterior e
marca a nova numa só transação, só pelo backend; o CHECK da qualidade de quem
assina aceita o Responsável técnico sem perder as qualidades antigas; e
nenhuma pessoa entra por migration.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "241_nsp_responsavel_tecnico.sql"

FUNCAO = "trocar_responsavel_tecnico"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _corpo() -> str:
    achado = re.search(rf"FUNCTION {FUNCAO}\(.*?\$\$(.*?)\$\$;", _sql(), re.DOTALL)
    assert achado, FUNCAO
    return achado.group(1)


def test_participantes_ganha_a_marca_falsa_por_padrao():
    assert re.search(
        r"ALTER TABLE participantes\s+ADD COLUMN IF NOT EXISTS responsavel_tecnico BOOLEAN NOT NULL DEFAULT false;",
        _sql(),
    )


def test_o_banco_garante_uma_pessoa_marcada_so():
    """Mutante: tirar o WHERE do índice. Sem ele, o índice único deixaria uma
    pessoa só como NÃO marcada, e o cadastro inteiro quebraria."""
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON participantes\s*\(responsavel_tecnico\)\s+"
        r"WHERE responsavel_tecnico\s*;",
        _sql(),
    )


def test_a_troca_desmarca_a_anterior_e_marca_a_nova_numa_transacao():
    """Mutante: tirar o UPDATE que desmarca a anterior. Marcar a segunda
    pessoa bateria no índice único em vez de trocar."""
    corpo = _corpo()
    assert re.search(r"pg_advisory_xact_lock\(hashtext\('responsavel_tecnico'\)\)", corpo)
    desmarca = re.search(
        r"UPDATE participantes SET responsavel_tecnico = false\s+"
        r"WHERE responsavel_tecnico AND id <> p_participante_id",
        corpo,
    )
    marca = re.search(r"UPDATE participantes SET responsavel_tecnico = p_marcar\s+WHERE id = p_participante_id", corpo)
    assert desmarca and marca
    assert desmarca.start() < marca.start()
    # Desmarcar a própria pessoa não mexe em mais ninguém.
    assert re.search(r"IF p_marcar THEN", corpo)


def test_a_troca_e_so_do_backend():
    assert re.search(rf"REVOKE EXECUTE ON FUNCTION {FUNCAO}\([^)]*\)\s+FROM PUBLIC, anon, authenticated;", _sql())
    assert re.search(rf"GRANT EXECUTE ON FUNCTION {FUNCAO}\([^)]*\) TO service_role;", _sql())
    assert re.search(rf"FUNCTION {FUNCAO}\([^)]*\)[^$]*SET search_path = public", _sql(), re.DOTALL)


def test_o_check_da_qualidade_aceita_o_responsavel_tecnico_e_mantem_as_antigas():
    assert re.search(
        r"ALTER TABLE nsp_documentos_signatarios\s+"
        r"DROP CONSTRAINT IF EXISTS nsp_documentos_signatarios_qualidade_check;",
        _sql(),
    )
    check = re.search(
        r"ADD CONSTRAINT nsp_documentos_signatarios_qualidade_check\s+CHECK \(qualidade IN \(([^)]*)\)\)", _sql()
    )
    assert check
    assert {q.strip() for q in check.group(1).split(",")} == {
        "'diretoria_executiva'",
        "'presidencia'",
        "'responsavel_tecnico'",
    }


def test_nenhuma_pessoa_na_migration():
    assert re.search(r"INSERT INTO (participacoes|participantes)\b", _sql(), re.IGNORECASE) is None
    assert re.search(r"UPDATE participantes SET", _sql().replace(_corpo(), "")) is None
    assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


def test_sem_travessao_no_arquivo():
    texto = MIGRATION.read_text(encoding="utf-8")
    assert chr(0x2013) not in texto and chr(0x2014) not in texto


def test_o_recibo_e_o_241():
    assert (
        _sql()
        .rstrip()
        .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (241) ON CONFLICT (numero) DO NOTHING;")
    )
