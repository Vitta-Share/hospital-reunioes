"""A migration 174: a Notificação de incidente do Núcleo (issue #1987, PRD #1979).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere, um
bloco por promessa da issue:

- o protocolo NSP-AAAA-NNNN sai do banco, numa sequência que recomeça a cada
  ano (ADR 0107, decisão 3);
- o banco aceita as origens e os estados que o serviço grava;
- a anônima guarda só o hash do código, e nenhuma coluna guarda IP ou
  identificador do aparelho;
- DELETE na notificação é recusado, e cada edição grava quem, quando, de e para
  numa trilha que só cresce;
- toda tabela nova nasce com RLS ligado.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.seguranca_do_paciente import notificacoes  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "174_nsp_notificacao_de_incidente.sql"


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _tabela(nome: str) -> str:
    bloco = re.search(rf"CREATE TABLE IF NOT EXISTS {nome} \((.*?)\n\);", _sql(), re.DOTALL)
    assert bloco, nome
    return bloco.group(1)


def _funcao(nome: str) -> str:
    bloco = re.search(rf"CREATE OR REPLACE FUNCTION {nome}\(\).*?\$\$(.*?)\$\$", _sql(), re.DOTALL)
    assert bloco, nome
    return bloco.group(1)


def _valores_do_check(coluna: str) -> set[str]:
    bloco = re.search(rf"\n\s+{coluna}\s[^\n]*CHECK \({coluna} IN \(([^)]*)\)\)", _tabela("nsp_notificacoes"))
    assert bloco, coluna
    return set(re.findall(r"'(\w+)'", bloco.group(1)))


# ═══════════════════════════════════════════════════════════════════════════
# Protocolo NSP-AAAA-NNNN, em sequência por ano
# ═══════════════════════════════════════════════════════════════════════════


def test_o_protocolo_sai_de_um_contador_por_ano_no_banco():
    contador = _tabela("nsp_protocolos")
    assert re.search(r"ano\s+SMALLINT PRIMARY KEY", contador)

    corpo = _funcao("nsp_notificacao_protocolo")
    # O ano é o de São Paulo: a notificação da virada às 22h do dia 31 é do ano velho.
    assert "now() AT TIME ZONE 'America/Sao_Paulo'" in corpo
    # Um único comando atômico: dois envios no mesmo segundo não pegam o mesmo número.
    assert re.search(
        r"INSERT INTO nsp_protocolos \(ano, ultimo\) VALUES \(v_ano, 1\)\s+"
        r"ON CONFLICT \(ano\) DO UPDATE SET ultimo = nsp_protocolos\.ultimo \+ 1\s+"
        r"RETURNING ultimo INTO v_numero",
        corpo,
    )
    # Quatro dígitos, sem cortar o 10.000º (o lpad sozinho corta).
    assert "'NSP-' || v_ano || '-' || lpad(v_numero::text, greatest(4, length(v_numero::text)), '0')" in corpo
    assert re.search(r"BEFORE INSERT ON nsp_notificacoes\s+FOR EACH ROW EXECUTE FUNCTION nsp_notificacao_protocolo\(\)", _sql())


def test_o_protocolo_e_unico_e_o_numero_nao_repete_no_ano():
    tabela = _tabela("nsp_notificacoes")
    assert re.search(r"protocolo\s+TEXT NOT NULL UNIQUE", tabela)
    assert "UNIQUE (ano, numero)" in tabela


# ═══════════════════════════════════════════════════════════════════════════
# Origem e estado
# ═══════════════════════════════════════════════════════════════════════════


def test_o_banco_aceita_as_origens_do_serviço_e_as_das_outras_portas():
    assert _valores_do_check("origem") == set(notificacoes.ORIGENS)
    # As três do formulário estão entre elas.
    assert {notificacoes.ORIGEM_QR, notificacoes.ORIGEM_ENDERECO, notificacoes.ORIGEM_MODULO} <= set(
        notificacoes.ORIGENS
    )


def test_o_banco_aceita_os_estados_e_nasce_recebida():
    assert _valores_do_check("estado") == set(notificacoes.ESTADO_PUBLICO)
    assert re.search(r"estado\s+TEXT NOT NULL DEFAULT 'recebida'", _tabela("nsp_notificacoes"))


# ═══════════════════════════════════════════════════════════════════════════
# Anonimato: só o hash, e nada do aparelho
# ═══════════════════════════════════════════════════════════════════════════


def test_a_anonima_guarda_so_o_hash_e_nenhuma_identidade():
    tabela = _tabela("nsp_notificacoes")
    assert re.search(
        r"CHECK \(NOT anonimo OR \(notificante_id IS NULL AND notificante_nome IS NULL "
        r"AND notificante_contato IS NULL AND codigo_acompanhamento_hash IS NOT NULL\)\)",
        tabela,
    )
    assert re.search(r"CHECK \(anonimo OR codigo_acompanhamento_hash IS NULL\)", tabela)


def test_nenhuma_coluna_guarda_ip_nem_aparelho():
    colunas = re.findall(r"^\s+([a-z_]+)\s", _tabela("nsp_notificacoes"), re.MULTILINE)
    assert colunas, "a tabela não foi lida"
    for proibida in ("ip", "endereco_ip", "user_agent", "aparelho", "dispositivo", "fingerprint"):
        assert not any(proibida in coluna for coluna in colunas), proibida


# ═══════════════════════════════════════════════════════════════════════════
# Sem DELETE, e a trilha de cada edição
# ═══════════════════════════════════════════════════════════════════════════


def test_delete_na_notificacao_e_recusado_pelo_banco():
    assert "RAISE EXCEPTION" in _funcao("nsp_notificacoes_sem_exclusao")
    assert re.search(
        r"BEFORE DELETE ON nsp_notificacoes\s+FOR EACH ROW EXECUTE FUNCTION nsp_notificacoes_sem_exclusao\(\)",
        _sql(),
    )


def test_cada_edicao_grava_quem_quando_de_e_para():
    trilha = _tabela("nsp_notificacoes_trilha")
    for coluna in ("notificacao_id", "campo", "de", "para", "autor_id", "papel_do_banco", "ocorrido_em"):
        assert re.search(rf"^\s+{coluna}\s", trilha, re.MULTILINE), coluna

    corpo = _funcao("nsp_notificacoes_editar")
    # Campo a campo: o que mudou entre a linha velha e a nova.
    assert "to_jsonb(OLD)" in corpo and "to_jsonb(NEW)" in corpo
    assert re.search(
        r"INSERT INTO nsp_notificacoes_trilha \(notificacao_id, campo, de, para, autor_id\)",
        corpo,
    )
    # Quem editou vem da própria edição, e é consumido: a edição seguinte que
    # não disser quem foi grava sem autor, e não com o autor da anterior.
    assert "NEW.editado_por := NULL" in corpo
    assert re.search(
        r"BEFORE UPDATE ON nsp_notificacoes\s+FOR EACH ROW EXECUTE FUNCTION nsp_notificacoes_editar\(\)", _sql()
    )


def test_o_protocolo_nao_muda_numa_edicao():
    corpo = _funcao("nsp_notificacoes_editar")
    assert re.search(r"NEW\.protocolo IS DISTINCT FROM OLD\.protocolo", corpo)
    assert "RAISE EXCEPTION" in corpo


def test_a_trilha_so_cresce():
    assert "RAISE EXCEPTION" in _funcao("nsp_notificacoes_trilha_imutavel")
    assert re.search(
        r"BEFORE UPDATE OR DELETE ON nsp_notificacoes_trilha\s+"
        r"FOR EACH ROW EXECUTE FUNCTION nsp_notificacoes_trilha_imutavel\(\)",
        _sql(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# RLS, e o e-mail de caso ganha a chave estrangeira
# ═══════════════════════════════════════════════════════════════════════════


def test_toda_tabela_nova_nasce_com_rls_ligado():
    novas = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", _sql())
    assert set(novas) == {"nsp_protocolos", "nsp_notificacoes", "nsp_notificacoes_trilha"}
    for tabela in novas:
        assert f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;" in _sql(), tabela
    assert "CREATE POLICY" not in _sql()


def test_o_email_de_caso_aponta_para_a_notificacao():
    assert re.search(
        r"FOREIGN KEY \(caso_id\) REFERENCES nsp_notificacoes\(id\)",
        _sql(),
    )


def test_o_recibo_e_o_da_174():
    assert "INSERT INTO migracoes_aplicadas (numero) VALUES (174)" in MIGRATION.read_text(encoding="utf-8")
