"""A migration 149: a Agenda regulatória do Núcleo (issue #1779, PRD #1764).

Lida como texto, do arquivo que o humano cola no Studio. O que se confere é o
que a issue promete: a lista nasce com os eventos da seção 6.4 da
especificação (obrigações do Núcleo, e não dados de pessoas), as tabelas novas
têm RLS ligado e nenhuma política, e cada ocorrência só existe uma vez.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "149_nsp_agenda_regulatoria.sql"

TABELAS_NOVAS = ("nsp_agenda_regulatoria", "nsp_agenda_ocorrencias")

# A seção 6.4 da especificação do Núcleo, evento e periodicidade.
EVENTOS_DA_ESPECIFICACAO = {
    "Notificação externa do mês": "mensal",
    "Fechamento mensal e relatório": "mensal",
    "Reunião ordinária": "mensal",
    "Avaliação Nacional das Práticas de Segurança do Paciente": "anual",
    "Avaliação da cultura de segurança (E-Questionário da ANVISA)": "bienal",
    "Revisão do PSP e do Regimento": "anual",
    "Vencimento de vigência dos membros": "avulsa",
    "Recalibração do agente": "avulsa",
}


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _eventos_semeados() -> dict[str, str]:
    bloco = re.search(r"INSERT INTO nsp_agenda_regulatoria\s*\(([^)]*)\)\s*SELECT(.*?);", _sql(), re.DOTALL)
    assert bloco, "a carga inicial sumiu"
    linhas = re.findall(r"\(\s*'([^']+)'\s*,\s*'(\w+)'", bloco.group(2))
    return dict(linhas)


class TestCargaInicial:
    def test_a_lista_nasce_com_os_eventos_da_especificacao(self):
        """Mutante: tirar um evento da carga."""
        assert _eventos_semeados() == EVENTOS_DA_ESPECIFICACAO

    def test_a_carga_so_entra_com_a_lista_vazia(self):
        """Rodar duas vezes não duplica, e a lista que a Presidência já editou
        não volta ao que era."""
        assert re.search(r"WHERE NOT EXISTS\s*\(\s*SELECT 1 FROM nsp_agenda_regulatoria\s*\)", _sql())

    def test_nenhuma_pessoa_nem_email(self):
        assert re.search(r"INSERT INTO (participantes|participacoes|pendencias)", _sql(), re.IGNORECASE) is None
        assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None


class TestTabelas:
    def test_cria_a_agenda_e_as_ocorrencias(self):
        assert sorted(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql())) == sorted(TABELAS_NOVAS)

    @pytest.mark.parametrize("tabela", TABELAS_NOVAS)
    def test_toda_tabela_nova_tem_rls_ligado(self, tabela):
        assert re.search(rf"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;", _sql())

    def test_nenhuma_politica(self):
        assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None

    def test_a_periodicidade_tem_check(self):
        bloco = re.search(r"periodicidade\s+TEXT NOT NULL CHECK \(periodicidade IN \((.*?)\)\)", _sql())
        assert bloco
        assert sorted(re.findall(r"'(\w+)'", bloco.group(1))) == ["anual", "avulsa", "bienal", "mensal"]

    def test_o_link_so_aceita_http(self):
        """Link com `javascript:` viraria script na tela."""
        assert re.search(r"link\s*~\s*'\^https\?://", _sql())

    def test_uma_ocorrencia_por_data(self):
        """O lembrete sai uma vez por ocorrência: a guarda é do banco."""
        assert re.search(r"UNIQUE\s*\(\s*item_id\s*,\s*data_prevista\s*\)", _sql())

    def test_o_recibo_e_o_149(self):
        assert "INSERT INTO migracoes_aplicadas (numero) VALUES (149)" in _sql()
