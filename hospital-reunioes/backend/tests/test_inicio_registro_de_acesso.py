"""O Registro de acesso (issue #1941, PRD #1932, ADR 0104 decisão 10).

A marca de que a pessoa abriu o Início num dia: uma por pessoa por dia, sem
trilha de cliques, guardada por 90 dias. Gravada quando o Início é montado
para a própria pessoa; a falha ao gravar não derruba o Início. Nesta fatia
nenhuma rota devolve o registro de ninguém: quem lê é o bloco Quem responde a
você, em outra fatia.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.cron import scheduler as cron  # noqa: E402
from app.routers import inicio as inicio_router  # noqa: E402

BRT = ZoneInfo("America/Sao_Paulo")
# Quarta-feira, 18/11/2026, 10h em Brasília.
AGORA = datetime(2026, 11, 18, 10, 0, tzinfo=BRT)
AURORA = {"id": "P_AURORA", "nome_completo": "Aurora Lima", "access_profile": "regular"}

BACKEND = Path(__file__).resolve().parents[1]
MIGRATION = BACKEND.parent / "supabase" / "migrations" / "167_registro_de_acesso.sql"


# ─── O banco de mentira ───────────────────────────────────────────────────


@dataclass
class _Result:
    data: list


class _Consulta:
    """Só o que o Início e o job pedem. Tabela que não existe aqui devolve
    vazio: as fontes do Início não são o assunto deste arquivo."""

    def __init__(self, banco: _Banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._filtros: list = []
        self._gravar: dict | None = None
        self._apagar = False

    def __getattr__(self, _nome):
        return lambda *_a, **_kw: self

    def upsert(self, linha, on_conflict=None, ignore_duplicates=False, **_kw):
        self._gravar = {"linha": linha, "on_conflict": on_conflict, "ignore": ignore_duplicates}
        return self

    def delete(self, **_kw):
        self._apagar = True
        return self

    def lt(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) < str(valor))
        return self

    def execute(self):
        if self._nome != "registro_de_acesso":
            return _Result([])
        if self._banco.falhar:
            raise RuntimeError("PostgREST fora do ar")
        linhas = self._banco.registro_de_acesso
        if self._gravar is not None:
            linha = self._gravar["linha"]
            chave = tuple(self._gravar["on_conflict"].split(","))
            existe = any(all(r[c] == linha[c] for c in chave) for r in linhas)
            if existe and not self._gravar["ignore"]:
                raise RuntimeError("duplicate key value violates unique constraint")
            if not existe:
                linhas.append(dict(linha))
            return _Result([] if existe else [dict(linha)])
        if self._apagar:
            fora = [r for r in linhas if all(f(r) for f in self._filtros)]
            self._banco.registro_de_acesso = [r for r in linhas if r not in fora]
            return _Result(fora)
        return _Result([dict(r) for r in linhas if all(f(r) for f in self._filtros)])


@dataclass
class _Banco:
    registro_de_acesso: list = field(default_factory=list)
    falhar: bool = False

    def table(self, nome):
        return _Consulta(self, nome)


def _abrir_o_inicio(monkeypatch, banco: _Banco, agora: datetime = AGORA):
    async def _participante(_user, _sb):
        return AURORA

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: agora)
    return asyncio.run(inicio_router.get_inicio(current_user={"id": "u1"}, supabase=banco))


# ─── A migration ──────────────────────────────────────────────────────────


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


class TestMigration:
    def test_a_tabela_tem_uma_linha_por_pessoa_por_dia(self):
        corpo = re.search(r"CREATE TABLE IF NOT EXISTS registro_de_acesso\s*\((.*?)\n\);", _sql(), re.DOTALL)
        assert corpo
        colunas = re.findall(r"^\s*(\w+)\s+(?:VARCHAR|DATE|TEXT|UUID|TIMESTAMPTZ)", corpo.group(1), re.MULTILINE)
        # Sem trilha de cliques: a pessoa e o dia, nada além.
        assert colunas == ["participante_id", "dia"]
        assert "PRIMARY KEY (participante_id, dia)" in corpo.group(1)

    def test_a_tabela_nasce_com_rls_e_sem_politica(self):
        assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql()) == ["registro_de_acesso"]
        assert "ALTER TABLE registro_de_acesso ENABLE ROW LEVEL SECURITY;" in _sql()
        assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None

    def test_o_recibo_e_o_167(self):
        assert (
            _sql()
            .rstrip()
            .endswith("INSERT INTO migracoes_aplicadas (numero) VALUES (167) ON CONFLICT (numero) DO NOTHING;")
        )


# ─── A marca ao abrir o Início ────────────────────────────────────────────


class TestMarcaAoAbrirOInicio:
    def test_abrir_o_inicio_grava_o_dia_da_pessoa(self, monkeypatch):
        banco = _Banco()

        _abrir_o_inicio(monkeypatch, banco)

        assert banco.registro_de_acesso == [{"participante_id": "P_AURORA", "dia": "2026-11-18"}]

    def test_abrir_duas_vezes_no_mesmo_dia_grava_uma_linha_so(self, monkeypatch):
        banco = _Banco()

        _abrir_o_inicio(monkeypatch, banco)
        _abrir_o_inicio(monkeypatch, banco, agora=datetime(2026, 11, 18, 17, 30, tzinfo=BRT))

        assert banco.registro_de_acesso == [{"participante_id": "P_AURORA", "dia": "2026-11-18"}]

    def test_o_dia_e_o_de_brasilia(self, monkeypatch):
        banco = _Banco()

        # 23h30 de Brasília já é o dia seguinte em UTC.
        _abrir_o_inicio(monkeypatch, banco, agora=datetime(2026, 11, 18, 23, 30, tzinfo=BRT))

        assert [r["dia"] for r in banco.registro_de_acesso] == ["2026-11-18"]

    def test_a_falha_ao_gravar_a_marca_nao_derruba_o_inicio(self, monkeypatch):
        banco = _Banco(falhar=True)

        inicio = _abrir_o_inicio(monkeypatch, banco)

        assert inicio.hoje == date(2026, 11, 18)
        assert inicio.avisos == []


# ─── A retenção de 90 dias ────────────────────────────────────────────────


class TestRetencao:
    def test_o_job_das_seis_apaga_as_marcas_com_mais_de_90_dias(self, monkeypatch):
        banco = _Banco(
            registro_de_acesso=[
                {"participante_id": "P_AURORA", "dia": "2026-08-19"},
                {"participante_id": "P_AURORA", "dia": "2026-08-20"},
                {"participante_id": "P_BRUNO", "dia": "2026-11-17"},
            ]
        )
        monkeypatch.setattr(cron, "_supabase", lambda: banco)
        monkeypatch.setattr(cron, "_hoje", lambda: date(2026, 11, 18))

        cron.marcar_atrasadas()

        # 18/11 menos 90 dias é 20/08: o dia 20/08 ainda está dentro.
        assert banco.registro_de_acesso == [
            {"participante_id": "P_AURORA", "dia": "2026-08-20"},
            {"participante_id": "P_BRUNO", "dia": "2026-11-17"},
        ]

    def test_a_retencao_mora_num_job_que_ja_existe(self):
        try:
            cron.start_scheduler()
            job = cron.scheduler.get_job("marcar_atrasadas")
            assert job is not None
            assert job.func is cron.marcar_atrasadas
        finally:
            cron.stop_scheduler()

    def test_a_retencao_nao_chama_ia(self):
        fonte = (BACKEND / "app" / "services" / "inicio" / "registro_de_acesso.py").read_text(encoding="utf-8")
        assert re.search(r"anthropic|openrouter|openai|ai_processor|ia_cliente", fonte, re.IGNORECASE) is None


# ─── Ninguém lê o registro nesta fatia ────────────────────────────────────


class TestNenhumaRotaDevolveORegistro:
    def test_so_o_servico_do_registro_toca_na_tabela_e_ele_nao_le(self):
        quem_cita = sorted(
            str(arquivo.relative_to(BACKEND))
            for arquivo in (BACKEND / "app").rglob("*.py")
            if "registro_de_acesso" in arquivo.read_text(encoding="utf-8")
            and re.search(r"[\"']registro_de_acesso[\"']", arquivo.read_text(encoding="utf-8"))
        )
        assert quem_cita == ["app/services/inicio/registro_de_acesso.py"]
        fonte = (BACKEND / quem_cita[0]).read_text(encoding="utf-8")
        assert ".select(" not in fonte

    def test_o_inicio_nao_devolve_marca_de_acesso(self, monkeypatch):
        banco = _Banco(registro_de_acesso=[{"participante_id": "P_BRUNO", "dia": "2026-11-17"}])

        inicio = _abrir_o_inicio(monkeypatch, banco)

        assert "P_BRUNO" not in inicio.model_dump_json()
        assert "2026-11-17" not in inicio.model_dump_json()
