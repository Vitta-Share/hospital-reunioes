"""A limpeza dos testes da Ouvidoria (issue #1962, PRD #1913, ADR 0102).

O script de `scripts/oneshot/limpeza_testes_ouvidoria.py` confere a janela,
lista o que sai, tira os arquivos do bucket e gera o SQL avulso que uma pessoa
roda à mão. A escolha do que sai é uma função pura; o resto passa por um
cliente falso do PostgREST e um bucket falso. Nada aqui fala com banco de
verdade.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.oneshot import limpeza_testes_ouvidoria as limpeza  # noqa: E402
from scripts.oneshot.limpeza_testes_ouvidoria import Avaliacao, Caso, escolher  # noqa: E402

# Os dois limites da janela, escritos à mão a partir da issue: 19/10/2026 à 0h
# de Brasília e 17/11/2026 às 18h31min43s de Brasília (21:31:43 UTC).
INICIO = datetime(2026, 10, 19, 3, 0, 0, tzinfo=UTC)
FIM = datetime(2026, 11, 17, 21, 31, 43, tzinfo=UTC)
MEIO = datetime(2026, 11, 1, 15, 0, 0, tzinfo=UTC)
UM_MICRO = timedelta(microseconds=1)


def _avaliacoes(n: int, quando: datetime = MEIO) -> list[Avaliacao]:
    return [Avaliacao(id=f"av-{i}", criada_em=quando) for i in range(n)]


def _caso(protocolo: str = "2026-0101", **campos) -> Caso:
    base = {
        "id": f"id-{protocolo}",
        "protocolo": protocolo,
        "canal": "qr",
        "t0": MEIO,
        "estado": "em_classificacao",
        "anonimo": False,
    }
    base.update(campos)
    return Caso(**base)


class TestJanela:
    def test_avaliacao_no_primeiro_instante_da_janela_entra_e_a_de_um_instante_antes_fica(self):
        escolha = escolher(
            [Avaliacao("dentro", INICIO), Avaliacao("antes", INICIO - UM_MICRO)],
            [],
        )
        assert [a.id for a in escolha.avaliacoes] == ["dentro"]

    def test_avaliacao_no_ultimo_segundo_da_janela_entra_e_a_do_segundo_seguinte_fica(self):
        escolha = escolher(
            [
                Avaliacao("no_fim", FIM),
                Avaliacao("fim_do_segundo", FIM + timedelta(microseconds=999_999)),
                Avaliacao("depois", FIM + timedelta(seconds=1)),
            ],
            [],
        )
        assert [a.id for a in escolha.avaliacoes] == ["no_fim", "fim_do_segundo"]

    def test_caso_conta_pelo_t0_nos_dois_limites(self):
        casos = [
            _caso("2026-0001", t0=INICIO - UM_MICRO),
            _caso("2026-0002", t0=INICIO),
            _caso("2026-0003", t0=FIM),
            _caso("2026-0004", t0=FIM + timedelta(seconds=1)),
        ]
        escolha = escolher(_avaliacoes(5), casos)
        assert [c.protocolo for c in escolha.saem] == ["2026-0002", "2026-0003"]


class TestTravaDosCinco:
    def test_cinco_avaliacoes_na_janela_deixam_seguir(self):
        escolha = escolher(_avaliacoes(5), [_caso()])
        assert escolha.pode_seguir
        assert not escolha.trava_dos_cinco

    @pytest.mark.parametrize("quantas", [0, 4, 6])
    def test_numero_de_avaliacoes_diferente_de_cinco_trava(self, quantas):
        escolha = escolher(_avaliacoes(quantas), [_caso()])
        assert escolha.trava_dos_cinco
        assert not escolha.pode_seguir

    def test_avaliacao_fora_da_janela_nao_conta_para_os_cinco(self):
        fora = _avaliacoes(1, quando=FIM + timedelta(days=1))
        escolha = escolher(_avaliacoes(4) + fora, [])
        assert escolha.trava_dos_cinco

    def test_zero_avaliacoes_e_zero_casos_e_limpeza_ja_feita_e_nao_trava(self):
        fora = [_caso(t0=FIM + timedelta(days=2))]
        escolha = escolher(_avaliacoes(2, quando=INICIO - timedelta(days=1)), fora)
        assert escolha.ja_feita
        assert not escolha.trava_dos_cinco
        assert not escolha.pode_seguir


class TestForaDoPadrao:
    @pytest.mark.parametrize("canal", ["qr", "site"])
    def test_caso_do_qr_ou_do_site_sem_nada_ligado_sai_sem_pergunta(self, canal):
        escolha = escolher(_avaliacoes(5), [_caso(canal=canal)])
        assert escolha.pendentes == []
        assert [c.protocolo for c in escolha.saem] == ["2026-0101"]

    @pytest.mark.parametrize(
        ("campos", "trecho"),
        [
            ({"canal": "telefone"}, "não veio do QR nem do site"),
            ({"emails": ("email-1",)}, "e-mail recebido"),
            ({"acionamentos": 1}, "acionamento"),
            ({"links_de_setor": 2}, "link de setor"),
            ({"no_nucleo": True}, "Núcleo de Segurança do Paciente"),
            ({"no_canal_de_conduta": True}, "Canal de Conduta"),
        ],
    )
    def test_cada_motivo_de_fora_do_padrao_segura_o_caso_ate_a_decisao(self, campos, trecho):
        escolha = escolher(_avaliacoes(5), [_caso("2026-0200", **campos), _caso("2026-0201")])
        assert [p.protocolo for p in escolha.pendentes] == ["2026-0200"]
        assert any(trecho in motivo for motivo in escolha.pendentes[0].motivos)
        assert not escolha.pode_seguir

    def test_caso_com_dois_motivos_mostra_os_dois(self):
        escolha = escolher(_avaliacoes(5), [_caso("2026-0200", canal="email", emails=("e1",))])
        assert len(escolha.pendentes[0].motivos) == 2

    def test_liberar_leva_o_caso_fora_do_padrao_junto(self):
        caso = _caso("2026-0200", canal="whatsapp", emails=("email-1",))
        escolha = escolher(_avaliacoes(5), [caso, _caso("2026-0201")], liberar=["2026-0200"])
        assert escolha.pode_seguir
        assert [c.protocolo for c in escolha.saem] == ["2026-0200", "2026-0201"]

    def test_manter_deixa_o_caso_fora_do_padrao_no_banco(self):
        caso = _caso("2026-0200", acionamentos=1)
        escolha = escolher(_avaliacoes(5), [caso, _caso("2026-0201")], manter=["2026-0200"])
        assert escolha.pode_seguir
        assert [c.protocolo for c in escolha.saem] == ["2026-0201"]
        assert [c.protocolo for c in escolha.ficam] == ["2026-0200"]

    @pytest.mark.parametrize("campos", [{"no_nucleo": True}, {"no_canal_de_conduta": True}])
    def test_caso_ligado_a_outro_modulo_nao_aceita_liberar(self, campos):
        """A notificação do Núcleo e o caso do Canal de Conduta têm trilha e
        filhas próprias, e esta limpeza não alcança outro módulo: o caso só
        pode ficar."""
        escolha = escolher(_avaliacoes(5), [_caso("2026-0200", **campos)], liberar=["2026-0200"])
        assert not escolha.pode_seguir
        assert any("2026-0200" in erro for erro in escolha.erros)

    def test_protocolo_que_nao_esta_na_janela_e_erro_de_digitacao(self):
        escolha = escolher(_avaliacoes(5), [_caso("2026-0201")], manter=["2026-9999"])
        assert not escolha.pode_seguir
        assert any("2026-9999" in erro for erro in escolha.erros)

    def test_mesmo_protocolo_em_liberar_e_manter_e_erro(self):
        caso = _caso("2026-0200", canal="telefone")
        escolha = escolher(_avaliacoes(5), [caso], liberar=["2026-0200"], manter=["2026-0200"])
        assert not escolha.pode_seguir
        assert any("2026-0200" in erro for erro in escolha.erros)


CASO_A = "11111111-1111-1111-1111-111111111111"
CASO_B = "22222222-2222-2222-2222-222222222222"
EMAIL_A = "33333333-3333-3333-3333-333333333333"
AVALIACAO_A = "44444444-4444-4444-4444-444444444444"


def _plano() -> limpeza.Plano:
    esperado = {tabela: 1 for tabela, _ in limpeza.TABELAS_APAGADAS}
    esperado["ouvidoria_protocolos"] = 2
    esperado["ouvidoria_avaliacoes"] = 1
    return limpeza.Plano(
        casos=(CASO_A, CASO_B),
        emails=(EMAIL_A,),
        avaliacoes=(AVALIACAO_A,),
        esperado=esperado,
    )


class TestSqlGerado:
    def test_sql_mira_os_ids_conferidos_e_nao_as_datas_da_janela(self):
        sql = limpeza.gerar_sql(_plano())
        for id_ in (CASO_A, CASO_B, EMAIL_A, AVALIACAO_A):
            assert id_ in sql
        for data in ("2026-10-19", "2026-11-17", "contato_em", "criada_em"):
            assert data not in sql

    def test_sql_roda_numa_transacao_e_religa_os_gatilhos_antes_do_fim(self):
        sql = limpeza.gerar_sql(_plano())
        begin = sql.index("BEGIN;")
        commit = sql.index("COMMIT;")
        for gatilho in ("trg_ouvidoria_movimentos_sem_delete", "trg_ouvidoria_acessos_sem_delete"):
            desliga = sql.index(f"DISABLE TRIGGER {gatilho}")
            religa = sql.index(f"ENABLE TRIGGER {gatilho}")
            assert begin < desliga < sql.index("DELETE FROM") < religa < commit
        # Termina mostrando, depois do COMMIT, que os dois gatilhos estão ligados.
        assert sql.index("FROM pg_trigger") > commit

    def test_sql_apaga_filhas_depois_casos_depois_avaliacoes(self):
        sql = limpeza.gerar_sql(_plano())
        filhas = max(sql.index(f"DELETE FROM {t} ") for t, _ in limpeza.TABELAS_APAGADAS)
        casos = sql.index("DELETE FROM ouvidoria_protocolos ")
        avaliacoes = sql.index("DELETE FROM ouvidoria_avaliacoes ")
        assert filhas < casos < avaliacoes

    def test_sql_confere_cada_contagem_e_levanta_erro_se_nao_bater(self):
        plano = _plano()
        plano.esperado["ouvidoria_movimentos"] = 7
        sql = limpeza.gerar_sql(plano)
        trecho = sql[sql.index("DELETE FROM ouvidoria_movimentos ") :]
        trecho = trecho[: trecho.index("END IF;")]
        assert "GET DIAGNOSTICS" in trecho
        assert "<> 7" in trecho
        assert "RAISE EXCEPTION" in trecho

    def test_sql_nao_toca_na_sequence_dos_protocolos(self):
        sql = limpeza.gerar_sql(_plano()).lower()
        for proibido in ("numero_seq", "setval", "sequence", "truncate"):
            assert proibido not in sql


# ---------------------------------------------------------------------------
# As migrations contra o SQL: toda filha da Manifestação precisa sair
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"

_COMENTARIO = re.compile(r"--[^\n]*")
_CABECALHO = re.compile(
    r"\b(?:CREATE\s+TABLE|ALTER\s+TABLE)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:ONLY\s+)?(?:public\.)?\"?(\w+)", re.I
)


def _filhas(pai: str, pasta: Path) -> set[str]:
    """Tabelas com chave estrangeira para `pai`, lidas das migrations. A dona de
    cada REFERENCES é o último CREATE TABLE ou ALTER TABLE antes dele, o que
    cobre coluna nova, constraint nomeada e bloco DO."""
    referencia = re.compile(rf"\bREFERENCES\s+(?:public\.)?\"?{pai}\"?\s*\(", re.I)
    filhas: set[str] = set()
    for arquivo in sorted(pasta.glob("*.sql")):
        texto = _COMENTARIO.sub("", arquivo.read_text(encoding="utf-8"))
        for achado in referencia.finditer(texto):
            donos = list(_CABECALHO.finditer(texto, 0, achado.start()))
            assert donos, f"{arquivo.name}: REFERENCES {pai} sem tabela dona"
            filhas.add(donos[-1].group(1).lower())
    return filhas - {pai}


def _filhas_fora_do_sql(pasta: Path) -> set[str]:
    """As filhas da Manifestação (e do e-mail recebido, que sai junto com o caso
    liberado) que o SQL gerado nem apaga nem confere."""
    sql = limpeza.gerar_sql(_plano())
    filhas = _filhas("ouvidoria_protocolos", pasta) | _filhas("ouvidoria_emails_recebidos", pasta)
    cobertas = {t for t in filhas if f"DELETE FROM {t} WHERE" in sql}
    barram = {
        t for t in filhas if f"FROM {t} WHERE manifestacao_id = ANY(casos)" in sql and t in limpeza.TABELAS_QUE_BARRAM
    }
    return filhas - cobertas - barram


class TestMigrationsContraOSql:
    def test_o_leitor_de_migrations_acha_as_filhas_que_ja_existem(self):
        filhas = _filhas("ouvidoria_protocolos", MIGRATIONS_DIR)
        # As nove do Refino do PRD #1913 e as duas que vieram depois.
        assert {
            "ouvidoria_movimentos",
            "ouvidoria_acessos",
            "ouvidoria_anexos",
            "ouvidoria_notificacoes",
            "ouvidoria_setor_tokens",
            "ouvidoria_prorrogacoes",
            "ouvidoria_tentativas_contato",
            "ouvidoria_emails_recebidos",
            "ouvidoria_acionamentos",
            "nsp_notificacoes",
            "conduta_casos",
        } <= filhas

    def test_toda_tabela_filha_da_manifestacao_sai_no_sql(self):
        assert _filhas_fora_do_sql(MIGRATIONS_DIR) == set()

    def test_filha_nova_numa_migration_futura_faz_o_teste_falhar(self, tmp_path):
        for arquivo in MIGRATIONS_DIR.glob("*.sql"):
            (tmp_path / arquivo.name).write_text(arquivo.read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "999_ouvidoria_filha_nova.sql").write_text(
            "CREATE TABLE IF NOT EXISTS ouvidoria_filha_nova (\n"
            "  id UUID PRIMARY KEY,\n"
            "  -- REFERENCES comentado não conta\n"
            "  manifestacao_id UUID NOT NULL REFERENCES ouvidoria_protocolos(id) ON DELETE RESTRICT\n"
            ");\n"
            "ALTER TABLE outra_tabela\n"
            "  ADD COLUMN IF NOT EXISTS caso UUID REFERENCES public.ouvidoria_protocolos (id);\n",
            encoding="utf-8",
        )
        assert _filhas_fora_do_sql(tmp_path) == {"ouvidoria_filha_nova", "outra_tabela"}


# ---------------------------------------------------------------------------
# O script inteiro, contra um PostgREST e um bucket falsos
# ---------------------------------------------------------------------------


class _Consulta:
    """O pedaço do cliente do PostgREST que o script usa. Devolve só as colunas
    pedidas no select, como o banco de verdade."""

    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._colunas: list[str] = []
        self._filtros: list = []
        self._faixa: tuple[int, int] | None = None

    def select(self, colunas: str):
        self._colunas = [c.strip() for c in colunas.split(",")]
        return self

    def gte(self, coluna, valor):
        limite = datetime.fromisoformat(valor)
        self._filtros.append(lambda linha: datetime.fromisoformat(linha[coluna]) >= limite)
        return self

    def lt(self, coluna, valor):
        limite = datetime.fromisoformat(valor)
        self._filtros.append(lambda linha: datetime.fromisoformat(linha[coluna]) < limite)
        return self

    def in_(self, coluna, valores):
        valores = set(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
        return self

    def order(self, _coluna):
        return self

    def range(self, inicio, fim):
        self._faixa = (inicio, fim)
        return self

    def execute(self):
        achadas = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._faixa:
            achadas = achadas[self._faixa[0] : self._faixa[1] + 1]
        dados = [{c: linha.get(c) for c in self._colunas} for linha in achadas]
        return type("Resposta", (), {"data": dados})()


class _BancoFalso:
    def __init__(self):
        self.tabelas: dict[str, list[dict]] = {}

    def table(self, nome: str):
        return _Consulta(self.tabelas.setdefault(nome, []))

    def inserir(self, tabela: str, **linha):
        ordem = len(self.tabelas.setdefault(tabela, [])) + 1
        linha.setdefault("id", str(uuid.uuid5(uuid.NAMESPACE_URL, f"{tabela}-{ordem}")))
        self.tabelas[tabela].append(linha)
        return linha["id"]


class _BucketFalso:
    def __init__(self, arquivos: set[str], teimosos: set[str] = frozenset()):
        self.arquivos = set(arquivos)
        self.teimosos = set(teimosos)  # o Storage não confirma a remoção
        self.removidos: list[str] = []

    def remover(self, caminho: str) -> bool:
        if caminho in self.teimosos or caminho not in self.arquivos:
            return False
        self.arquivos.discard(caminho)
        self.removidos.append(caminho)
        return True

    def existe(self, caminho: str) -> bool:
        return caminho in self.arquivos


URL_LOCAL = "http://127.0.0.1:54351"
DOSSIE = ("RELATO-SIGILOSO", "Fulana de Tal", "fulana@exemplo.com", "Paciente Beltrano", "COMENTARIO-DA-NOTA")


def _iso(instante: datetime) -> str:
    return instante.isoformat()


def _banco(avaliacoes: int = 5, canal: str = "qr") -> _BancoFalso:
    """Cinco Avaliações na janela, um caso de teste com dois anexos, um caso e
    uma Avaliação fora da janela. Todas as linhas carregam dado do Dossiê."""
    banco = _BancoFalso()
    relato, nome, contato, paciente, comentario = DOSSIE
    for i in range(avaliacoes):
        banco.inserir(
            "ouvidoria_avaliacoes", criada_em=_iso(MEIO + timedelta(minutes=i)), comentario=comentario, nota=1
        )
    banco.inserir("ouvidoria_avaliacoes", id="av-fora", criada_em=_iso(FIM + timedelta(hours=1)), comentario=comentario)
    dossie = {
        "relato_integral": relato,
        "manifestante_nome": nome,
        "manifestante_contato": contato,
        "paciente_nome": paciente,
        "status": "em_classificacao",
        "anonimo": False,
    }
    banco.inserir(
        "ouvidoria_protocolos", id=CASO_A, protocolo="2026-0101", canal=canal, contato_em=_iso(MEIO), **dossie
    )
    banco.inserir(
        "ouvidoria_protocolos",
        id=CASO_B,
        protocolo="2026-0300",
        canal="qr",
        contato_em=_iso(FIM + timedelta(days=1)),
        **dossie,
    )
    for caminho in ("caso-a/1.jpg", "caso-a/2.pdf"):
        banco.inserir("ouvidoria_anexos", manifestacao_id=CASO_A, storage_path=caminho, filename=f"{nome}.jpg")
    banco.inserir("ouvidoria_anexos", manifestacao_id=CASO_B, storage_path="caso-b/1.jpg", filename="x.jpg")
    banco.inserir("ouvidoria_movimentos", manifestacao_id=CASO_A, observacao=relato)
    banco.inserir("ouvidoria_movimentos", manifestacao_id=CASO_A, observacao=relato)
    banco.inserir("ouvidoria_acessos", manifestacao_id=CASO_A, ator_nome=nome)
    return banco


def _rodar(banco, bucket, destino, *argv):
    return limpeza.executar(banco, bucket, URL_LOCAL, list(argv), destino)


class TestConferencia:
    def test_conferencia_mostra_o_banco_alvo_na_primeira_linha_e_nenhum_dado_do_dossie(self, capsys, tmp_path):
        codigo = _rodar(_banco(), _BucketFalso({"caso-a/1.jpg"}), tmp_path / "limpeza.sql")
        saida = capsys.readouterr().out
        assert codigo == 0
        assert saida.splitlines()[0] == f"Banco alvo: {URL_LOCAL}"
        assert "2026-0101" in saida
        for sigilo in DOSSIE:
            assert sigilo not in saida

    def test_conferencia_mostra_protocolo_canal_t0_estado_anonimo_e_anexos(self, capsys, tmp_path):
        _rodar(_banco(), _BucketFalso(set()), tmp_path / "limpeza.sql")
        linha = next(t for t in capsys.readouterr().out.splitlines() if "2026-0101" in t)
        # T0 na hora de Brasília: 15:00 UTC são 12:00 em Brasília.
        for trecho in ("canal qr", "T0 01/11/2026 12:00:00", "em_classificacao", "anônimo: não", "anexos: 2"):
            assert trecho in linha

    def test_conferencia_nao_grava_sql_nem_toca_no_bucket(self, tmp_path):
        bucket = _BucketFalso({"caso-a/1.jpg", "caso-a/2.pdf"})
        _rodar(_banco(), bucket, tmp_path / "limpeza.sql")
        assert bucket.removidos == []
        assert not (tmp_path / "limpeza.sql").exists()

    @pytest.mark.parametrize("quantas", [4, 6])
    def test_avaliacoes_diferente_de_cinco_param_sem_sql_e_sem_bucket(self, capsys, tmp_path, quantas):
        bucket = _BucketFalso({"caso-a/1.jpg", "caso-a/2.pdf"})
        codigo = _rodar(_banco(avaliacoes=quantas), bucket, tmp_path / "limpeza.sql", "--aplicar")
        assert codigo != 0
        assert bucket.removidos == []
        assert not (tmp_path / "limpeza.sql").exists()
        assert f"{quantas} Avaliações" in capsys.readouterr().out

    def test_caso_fora_do_padrao_sem_decisao_para_com_protocolo_e_motivo(self, capsys, tmp_path):
        bucket = _BucketFalso({"caso-a/1.jpg", "caso-a/2.pdf"})
        codigo = _rodar(_banco(canal="telefone"), bucket, tmp_path / "limpeza.sql", "--aplicar")
        saida = capsys.readouterr().out
        assert codigo != 0
        linha = next(t for t in saida.splitlines() if "2026-0101" in t and "QR" in t)
        assert "não veio do QR nem do site" in linha
        assert bucket.removidos == []
        assert not (tmp_path / "limpeza.sql").exists()

    def test_limpeza_ja_feita_sai_com_zero(self, capsys, tmp_path):
        banco = _BancoFalso()
        banco.inserir("ouvidoria_avaliacoes", criada_em=_iso(FIM + timedelta(days=3)))
        codigo = _rodar(banco, _BucketFalso(set()), tmp_path / "limpeza.sql", "--aplicar")
        assert codigo == 0
        assert "já foi feita" in capsys.readouterr().out
        assert not (tmp_path / "limpeza.sql").exists()


class TestAplicar:
    def test_aplicar_tira_os_arquivos_e_grava_o_sql_com_os_ids_e_as_contagens(self, capsys, tmp_path):
        bucket = _BucketFalso({"caso-a/1.jpg", "caso-a/2.pdf", "caso-b/1.jpg"})
        destino = tmp_path / "limpeza.sql"
        codigo = _rodar(_banco(), bucket, destino, "--aplicar")
        saida = capsys.readouterr().out
        assert codigo == 0
        assert bucket.arquivos == {"caso-b/1.jpg"}
        sql = destino.read_text(encoding="utf-8")
        assert CASO_A in sql and CASO_B not in sql
        assert "ouvidoria_anexos: esperava apagar 2 " in sql
        assert "ouvidoria_movimentos: esperava apagar 2 " in sql
        assert "ouvidoria_acessos: esperava apagar 1 " in sql
        assert "ouvidoria_protocolos: esperava apagar 1 " in sql
        assert "ouvidoria_avaliacoes: esperava apagar 5 " in sql
        assert "Lista da limpeza" in saida
        assert "2026-0101" in saida[saida.index("Lista da limpeza") :]

    def test_rodar_aplicar_duas_vezes_nao_falha_nem_apaga_nada_a_mais(self, tmp_path):
        bucket = _BucketFalso({"caso-a/1.jpg", "caso-a/2.pdf", "caso-b/1.jpg"})
        destino = tmp_path / "limpeza.sql"
        assert _rodar(_banco(), bucket, destino, "--aplicar") == 0
        primeiro = destino.read_text(encoding="utf-8")
        assert _rodar(_banco(), bucket, destino, "--aplicar") == 0
        assert destino.read_text(encoding="utf-8") == primeiro
        assert bucket.arquivos == {"caso-b/1.jpg"}
        assert sorted(bucket.removidos) == ["caso-a/1.jpg", "caso-a/2.pdf"]

    def test_arquivo_que_o_storage_nao_confirma_para_antes_do_sql(self, capsys, tmp_path):
        bucket = _BucketFalso({"caso-a/1.jpg", "caso-a/2.pdf"}, teimosos={"caso-a/2.pdf"})
        destino = tmp_path / "limpeza.sql"
        assert _rodar(_banco(), bucket, destino, "--aplicar") != 0
        assert not destino.exists()
        assert "caso-a/2.pdf" in capsys.readouterr().out

    def test_caso_liberado_com_email_leva_o_email_e_os_anexos_dele(self, tmp_path):
        banco = _banco()
        email = "55555555-5555-5555-5555-555555555555"
        banco.inserir("ouvidoria_emails_recebidos", id=email, manifestacao_id=CASO_A, corpo_texto="RELATO-SIGILOSO")
        banco.inserir("ouvidoria_emails_recebidos_anexos", email_recebido_id=email, storage_path="email/1.pdf")
        banco.inserir("ouvidoria_emails_recebidos_anexos", email_recebido_id=email, storage_path=None)
        banco.inserir("ouvidoria_acessos", email_recebido_id=email, ator_nome="x")
        bucket = _BucketFalso({"caso-a/1.jpg", "caso-a/2.pdf", "email/1.pdf"})
        destino = tmp_path / "limpeza.sql"
        assert _rodar(banco, bucket, destino, "--aplicar") != 0  # e-mail ligado: espera o diretor
        assert _rodar(banco, bucket, destino, "--aplicar", "--liberar", "2026-0101") == 0
        sql = destino.read_text(encoding="utf-8")
        assert email in sql
        assert "ouvidoria_emails_recebidos: esperava apagar 1 " in sql
        assert "ouvidoria_emails_recebidos_anexos: esperava apagar 2 " in sql
        assert "ouvidoria_acessos: esperava apagar 2 " in sql
        assert bucket.arquivos == set()


class TestOScriptEmSi:
    def test_o_script_nao_aceita_parametro_de_data(self):
        opcoes = {o for acao in limpeza.criar_parser()._actions for o in acao.option_strings}
        assert opcoes == {"-h", "--help", "--aplicar", "--liberar", "--manter"}

    def test_a_janela_e_constante_no_codigo(self):
        assert limpeza.INICIO_DA_JANELA == INICIO
        assert limpeza.FIM_DA_JANELA == FIM

    def test_o_sql_vai_para_local_fora_do_git(self):
        raiz = Path(__file__).resolve().parents[3]
        assert limpeza.DESTINO_SQL == raiz / "local" / "limpeza-1913.sql"
        assert "/local/" in (raiz / ".gitignore").read_text(encoding="utf-8").splitlines()

    def test_o_cabecalho_traz_os_comandos_na_ordem_de_producao(self):
        doc = limpeza.__doc__
        conferencia = doc.index("uv run python -m scripts.oneshot.limpeza_testes_ouvidoria\n")
        aplicar = doc.index("uv run python -m scripts.oneshot.limpeza_testes_ouvidoria --aplicar")
        sql = doc.index("local/limpeza-1913.sql", aplicar)
        assert conferencia < aplicar < sql
