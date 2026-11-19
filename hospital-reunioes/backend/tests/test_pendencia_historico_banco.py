"""O Histórico da Pendência e a migration 169 num Postgres de verdade (issue #1862).

Um teste lê o SQL do trigger; os outros sobem um Postgres descartável (o
`initdb` da máquina, que o runner do GitHub já traz em
`/usr/lib/postgresql/*/bin`), montam o mínimo das tabelas de antes, aplicam a
migration duas vezes e provam no banco que:

- UPDATE, DELETE e TRUNCATE no histórico são recusados, inclusive para a
  `service_role` (a chave do backend, ADR 0002) e para o superusuário;
- a migration restaura o prazo das Pendências antigas atrasadas e "a
  repactuar" pelo quadro da Ata e grava o evento "migração" onde usou a data
  da última mudança;
- a função de gravação atualiza a Pendência e insere o evento juntos.

Sem `initdb` na máquina o teste pula; no CI ele falha, para não ficar verde
sobre nada.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "169_ciclo_de_vida_da_pendencia.sql"

# O mínimo das tabelas de antes da 169 (migrations 001, 002, 003, 014, 030, 057).
ESQUEMA_ANTERIOR = """
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN NOSUPERUSER BYPASSRLS;

CREATE TABLE migracoes_aplicadas (numero INT PRIMARY KEY);

CREATE FUNCTION update_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TABLE participantes (id VARCHAR(10) PRIMARY KEY, nome_completo TEXT);

CREATE TABLE reunioes (
  id_reuniao VARCHAR(20) PRIMARY KEY,
  json_ata JSONB,
  acoes_concluidas INTEGER DEFAULT 0,
  deleted_at TIMESTAMPTZ
);

CREATE TABLE pendencias (
  id_acao VARCHAR(10) PRIMARY KEY,
  id_reuniao VARCHAR(20) REFERENCES reunioes(id_reuniao) ON DELETE CASCADE,
  descricao_acao TEXT NOT NULL,
  responsavel_id VARCHAR(10) REFERENCES participantes(id),
  prazo DATE,
  status TEXT DEFAULT 'PENDENTE' CHECK (status IN (
    'PENDENTE', 'EM_PROGRESSO', 'CONCLUIDO', 'ATRASADO', 'CANCELADO', 'REPACTUADA'
  )),
  quadro_pos INTEGER,
  co_responsavel_id VARCHAR(10),
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE TRIGGER trigger_pendencias_updated_at BEFORE UPDATE ON pendencias
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
"""

# Pendências de antes, com a data da última mudança congelada.
CARGA_ANTIGA = """
INSERT INTO reunioes (id_reuniao, json_ata) VALUES
  ('R1', '{"quadro_atribuicoes": [
      {"acao": "Comprar luvas", "prazo": "2026-10-05"},
      {"acao": "Treinar equipe", "prazo": "12/10/2026"},
      {"acao": "Revisar escala", "prazo": "a definir"}
  ]}'),
  ('R2', '{"atribuicoes": [{"acao": "Pintar sala", "prazo": "2026-09-30"}]}');

INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, prazo, status, quadro_pos) VALUES
  ('A001', 'R1', 'Comprar luvas',   NULL,         'REPACTUADA', 0),
  ('A002', 'R1', 'Treinar equipe',  NULL,         'REPACTUADA', 1),
  ('A003', 'R1', 'Revisar escala',  NULL,         'REPACTUADA', 2),
  ('A004', 'R1', 'Comprar luvas',   '2026-10-05', 'ATRASADO',   0),
  ('A005', 'R2', 'Pintar sala',     NULL,         'REPACTUADA', NULL),
  ('A006', 'R1', 'Comprar luvas',   '2026-12-01', 'EM_PROGRESSO', 0),
  ('A007', 'R1', 'Algo concluído',  '2026-10-01', 'CONCLUIDO',  NULL);

-- O trigger de updated_at vale no UPDATE; aqui ele grava a data de antes.
ALTER TABLE pendencias DISABLE TRIGGER trigger_pendencias_updated_at;
UPDATE pendencias SET updated_at = '2026-10-20 15:00:00-03';
ALTER TABLE pendencias ENABLE TRIGGER trigger_pendencias_updated_at;
"""


def _bin_do_postgres() -> Path | None:
    initdb = shutil.which("initdb")
    if initdb:
        return Path(initdb).parent
    candidatos = sorted(glob.glob("/usr/lib/postgresql/*/bin/initdb"))
    return Path(candidatos[-1]).parent if candidatos else None


# O postmaster do macOS recusa subir sem locale válido no ambiente.
_AMBIENTE = {**os.environ, "LC_ALL": "C", "LANG": "C"}


class _Postgres:
    def __init__(self, bindir: Path):
        self.bindir = bindir
        self.dados = Path(tempfile.mkdtemp(prefix="pg169-"))
        # Caminho curto: o socket Unix tem teto de ~100 caracteres no macOS.
        self.socket = Path(tempfile.mkdtemp(prefix="pg", dir="/tmp"))
        self.porta = "54169"

    def subir(self):
        subprocess.run(
            [str(self.bindir / "initdb"), "-D", str(self.dados / "d"), "-U", "postgres", "-A", "trust", "-E", "UTF8"],
            check=True,
            capture_output=True,
            env=_AMBIENTE,
        )
        subprocess.run(
            [
                str(self.bindir / "pg_ctl"),
                "-D",
                str(self.dados / "d"),
                "-l",
                str(self.dados / "log"),
                "-o",
                f"-k {self.socket} -c listen_addresses='' -p {self.porta}",
                "-w",
                "start",
            ],
            check=True,
            capture_output=True,
            env=_AMBIENTE,
        )

    def descer(self):
        subprocess.run(
            [str(self.bindir / "pg_ctl"), "-D", str(self.dados / "d"), "-m", "immediate", "stop"],
            capture_output=True,
        )
        shutil.rmtree(self.dados, ignore_errors=True)
        shutil.rmtree(self.socket, ignore_errors=True)

    def sql(self, comando: str, *, papel: str | None = None) -> subprocess.CompletedProcess:
        if papel:
            comando = f"SET ROLE {papel};\n{comando}"
        psql = self.bindir / "psql"
        return subprocess.run(
            [
                str(psql if psql.exists() else shutil.which("psql")),
                "-h",
                str(self.socket),
                "-p",
                self.porta,
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-X",
                "-q",
                "-A",
                "-t",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input=comando,
            capture_output=True,
            text=True,
            env=_AMBIENTE,
        )

    def ok(self, comando: str, *, papel: str | None = None) -> str:
        r = self.sql(comando, papel=papel)
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()


@pytest.fixture(scope="module")
def banco():
    bindir = _bin_do_postgres()
    if bindir is None:
        if os.environ.get("CI"):
            pytest.fail("O CI precisa do initdb para provar o trigger no banco.")
        pytest.skip("Sem initdb nesta máquina.")
    pg = _Postgres(bindir)
    pg.subir()
    try:
        pg.ok(ESQUEMA_ANTERIOR)
        pg.ok(CARGA_ANTIGA)
        migration = MIGRATION.read_text(encoding="utf-8")
        pg.ok(migration)
        pg.ok(migration)  # rodar duas vezes é inofensivo
        yield pg
    finally:
        pg.descer()


# ── O SQL do trigger ────────────────────────────────────────────────────────


def test_o_sql_do_trigger_recusa_update_delete_e_truncate_no_historico():
    ddl = MIGRATION.read_text(encoding="utf-8")
    for operacao in ("UPDATE", "DELETE", "TRUNCATE"):
        assert f"BEFORE {operacao} ON pendencia_historico" in ddl, operacao
    corpo = ddl.split("FUNCTION recusar_mudanca_no_historico_da_pendencia()")[1].split("$$")[1]
    assert "RAISE EXCEPTION" in corpo
    assert "RETURN" not in corpo, "a função do trigger não pode deixar passar"
    assert "ALTER TABLE pendencia_historico ENABLE ROW LEVEL SECURITY" in ddl


# ── O banco recusa mexer no passado ─────────────────────────────────────────


def _um_evento(banco) -> str:
    return banco.ok(
        "INSERT INTO pendencia_historico (id_acao, comando, anotacao, autor_nome, status_depois) "
        "VALUES ('A006', 'anotar', 'andando', 'Ana', 'EM_PROGRESSO') RETURNING id;",
        papel="service_role",
    ).splitlines()[-1]


@pytest.mark.parametrize("papel", ["service_role", None])
def test_update_no_historico_e_recusado_inclusive_com_a_chave_de_servico(banco, papel):
    evento = _um_evento(banco)
    r = banco.sql(f"UPDATE pendencia_historico SET anotacao = 'reescrito' WHERE id = {evento};", papel=papel)
    assert r.returncode != 0
    assert "so aceita insercao" in r.stderr
    assert banco.ok(f"SELECT anotacao FROM pendencia_historico WHERE id = {evento};") == "andando"


@pytest.mark.parametrize("papel", ["service_role", None])
def test_delete_no_historico_e_recusado_inclusive_com_a_chave_de_servico(banco, papel):
    evento = _um_evento(banco)
    r = banco.sql(f"DELETE FROM pendencia_historico WHERE id = {evento};", papel=papel)
    assert r.returncode != 0
    assert "so aceita insercao" in r.stderr
    assert banco.ok(f"SELECT count(*) FROM pendencia_historico WHERE id = {evento};") == "1"


def test_truncate_no_historico_e_recusado(banco):
    _um_evento(banco)
    r = banco.sql("TRUNCATE pendencia_historico;")
    assert r.returncode != 0
    assert "so aceita insercao" in r.stderr


def test_historico_recusa_anotacao_vazia(banco):
    r = banco.sql(
        "INSERT INTO pendencia_historico (id_acao, comando, anotacao, autor_nome, status_depois) "
        "VALUES ('A006', 'anotar', '   ', 'Ana', 'EM_PROGRESSO');",
        papel="service_role",
    )
    assert r.returncode != 0


# ── A migration das Pendências antigas ─────────────────────────────────────


def _pendencia(banco, id_acao: str) -> tuple[str, str]:
    status, prazo = banco.ok(f"SELECT status, prazo FROM pendencias WHERE id_acao = '{id_acao}';").split("|")
    return status, prazo


def _eventos_de_migracao(banco, id_acao: str) -> list[str]:
    saida = banco.ok(
        f"SELECT prazo_depois FROM pendencia_historico WHERE id_acao = '{id_acao}' AND comando = 'migracao';"
    )
    return saida.splitlines() if saida else []


def test_a_repactuar_recupera_o_prazo_do_quadro_da_ata(banco):
    assert _pendencia(banco, "A001") == ("PENDENTE", "2026-10-05")
    assert _pendencia(banco, "A002") == ("PENDENTE", "2026-10-12")  # DD/MM/AAAA
    assert _eventos_de_migracao(banco, "A001") == []
    assert _eventos_de_migracao(banco, "A002") == []


def test_pendencia_sem_posicao_casa_a_linha_do_quadro_pelo_texto(banco):
    assert _pendencia(banco, "A005") == ("PENDENTE", "2026-09-30")
    assert _eventos_de_migracao(banco, "A005") == []


def test_sem_prazo_no_quadro_vale_a_ultima_mudanca_com_evento_migracao(banco):
    assert _pendencia(banco, "A003") == ("PENDENTE", "2026-10-20")
    assert _eventos_de_migracao(banco, "A003") == ["2026-10-20"]


def test_atrasada_antiga_volta_a_pendente_com_o_mesmo_prazo(banco):
    assert _pendencia(banco, "A004") == ("PENDENTE", "2026-10-05")
    assert _eventos_de_migracao(banco, "A004") == []


def test_quem_nao_era_atrasada_nem_a_repactuar_fica_como_estava(banco):
    assert _pendencia(banco, "A006") == ("EM_PROGRESSO", "2026-12-01")
    assert _pendencia(banco, "A007") == ("CONCLUIDO", "2026-10-01")


def test_o_banco_so_aceita_os_quatro_estados(banco):
    assert banco.ok("SELECT count(*) FROM pendencias WHERE status IN ('ATRASADO', 'REPACTUADA');") == "0"
    r = banco.sql("UPDATE pendencias SET status = 'ATRASADO' WHERE id_acao = 'A004';")
    assert r.returncode != 0
    assert "pendencias_status_check" in r.stderr


# ── A gravação de uma ação ──────────────────────────────────────────────────


def _registrar(banco, id_acao, comando, status_esperado, status_novo, *, prazo_novo="NULL", concluida="NULL"):
    return banco.sql(
        "SELECT registrar_acao_da_pendencia("
        f"'{id_acao}', '{comando}', 'feito com cuidado', 'P01', 'Ana', "
        f"'{status_esperado}', '{status_novo}', {prazo_novo}, {concluida}, false);",
        papel="service_role",
    )


def test_concluir_atualiza_a_pendencia_e_grava_o_evento_na_mesma_chamada(banco):
    banco.ok(
        "INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, prazo, status) "
        "VALUES ('A100', 'R1', 'Teste', '2026-12-10', 'EM_PROGRESSO');"
    )
    antes = int(banco.ok("SELECT acoes_concluidas FROM reunioes WHERE id_reuniao = 'R1';"))

    r = _registrar(banco, "A100", "concluir", "EM_PROGRESSO", "CONCLUIDO", concluida="true")
    assert r.returncode == 0, r.stderr

    status, concluida = banco.ok(
        "SELECT status, concluida_em IS NOT NULL FROM pendencias WHERE id_acao = 'A100';"
    ).split("|")
    assert (status, concluida) == ("CONCLUIDO", "t")
    evento = banco.ok(
        "SELECT comando, anotacao, autor_id, status_antes, status_depois "
        "FROM pendencia_historico WHERE id_acao = 'A100';"
    )
    assert evento == "concluir|feito com cuidado|P01|EM_PROGRESSO|CONCLUIDO"
    assert int(banco.ok("SELECT acoes_concluidas FROM reunioes WHERE id_reuniao = 'R1';")) == antes + 1


def test_repactuar_troca_o_prazo_na_hora_e_guarda_o_de_antes(banco):
    banco.ok(
        "INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, prazo, status) "
        "VALUES ('A101', 'R1', 'Teste', '2026-11-01', 'PENDENTE');"
    )

    r = _registrar(banco, "A101", "repactuar", "PENDENTE", "PENDENTE", prazo_novo="'2026-12-15'")
    assert r.returncode == 0, r.stderr

    assert _pendencia(banco, "A101") == ("PENDENTE", "2026-12-15")
    assert banco.ok("SELECT prazo_antes, prazo_depois FROM pendencia_historico WHERE id_acao = 'A101';") == (
        "2026-11-01|2026-12-15"
    )


def test_estado_que_mudou_no_meio_e_recusado_sem_gravar_nada(banco):
    banco.ok(
        "INSERT INTO pendencias (id_acao, id_reuniao, descricao_acao, prazo, status) "
        "VALUES ('A102', 'R1', 'Teste', '2026-12-01', 'CANCELADO');"
    )

    r = _registrar(banco, "A102", "concluir", "EM_PROGRESSO", "CONCLUIDO", concluida="true")

    assert r.returncode != 0
    assert "PT409" in r.stderr or "mudou enquanto" in r.stderr
    assert _pendencia(banco, "A102")[0] == "CANCELADO"
    assert banco.ok("SELECT count(*) FROM pendencia_historico WHERE id_acao = 'A102';") == "0"


def test_a_funcao_de_gravacao_nao_abre_para_anon(banco):
    r = banco.sql(
        "SELECT registrar_acao_da_pendencia('A006', 'anotar', 'x', NULL, 'x', 'EM_PROGRESSO', "
        "'EM_PROGRESSO', NULL, NULL, false);",
        papel="anon",
    )
    assert r.returncode != 0
    assert "permission denied" in r.stderr
