"""O papel original, a guarda, o congelamento e a eliminação do caso do Canal
de Conduta (issue #1838; especificação, seções 9.3 e 9.4 e Anexo E.2; ADR
0097).

Cada classe é um critério de aceite da issue. O banco e o Storage são os
dublês de `conduta_apoio`, a cifra é de verdade e o e-mail é dublado. A
função de eliminação do banco é dublada aqui pelo que ela faz (apaga o
conteúdo e marca o caso); as recusas dela (prazo, congelado) são provadas
num Postgres de verdade em `test_conduta_guarda_migration_banco`.
"""

from __future__ import annotations

import ast
import base64
import inspect
import os
import secrets
import sys
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from test_conduta_trilha_e_dossie import ComiteDaTrilha
from test_conduta_voto import BASE, COORDENACAO, HOJE, LEITOR, MEMBRO, NOMES

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.services.conduta import guarda  # noqa: E402
from app.services.conhecimento import CONHECIMENTO_DIR  # noqa: E402
from app.services.pdf_generator import env  # noqa: E402

FRASE = "Venceu a guarda de um envelope do Canal de Conduta."
# O conteúdo do caso que a eliminação leva (a migration 226 apaga essas e
# outras; aqui, as que o caso de teste tem).
CONTEUDO = ("conduta_depoimentos", "conduta_depoimento_arquivos", "conduta_votos")


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "frontend_url", "https://app.hsm.test")


def _anos_antes(dia: date, anos: int) -> date:
    try:
        return dia.replace(year=dia.year - anos)
    except ValueError:
        return dia.replace(year=dia.year - anos, day=28)


def _instante(dia: date) -> str:
    """Meio-dia em São Paulo do dia dado."""
    return f"{dia.isoformat()}T15:00:00+00:00"


class ComiteDaGuarda(ComiteDaTrilha):
    def __init__(self):
        super().__init__()
        self.eliminacoes: list[str] = []
        self.banco.rpc = self._rpc

    def _rpc(self, nome: str, parametros: dict):
        """O que a função `conduta_eliminar_conteudo_do_caso` faz no banco."""
        assert nome == "conduta_eliminar_conteudo_do_caso"
        caso_id = parametros["p_caso_id"]
        self.eliminacoes.append(caso_id)
        tabelas = self.banco.tabelas
        deps = {d["id"] for d in tabelas.get("conduta_depoimentos", []) if d["caso_id"] == caso_id}
        tabelas["conduta_depoimento_arquivos"] = [
            a for a in tabelas.get("conduta_depoimento_arquivos", []) if a["depoimento_id"] not in deps
        ]
        for tabela in ("conduta_depoimentos", "conduta_votos", "conduta_ciencias_do_codigo"):
            tabelas[tabela] = [x for x in tabelas.get(tabela, []) if x["caso_id"] != caso_id]
        self.linha_do_caso(caso_id).update({"relato_cifrado": None, "eliminado_em": datetime.now(UTC).isoformat()})
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.linha_do_caso(caso_id)["eliminado_em"]))

    def encerrado(self, *, dia: date, desfecho: str = "concluido", rito: str = "rapido") -> str:
        """Um caso com o acusado ouvido (termo, áudio e transcrição no
        bucket), encerrado no dia dado."""
        caso, _ = self.caso_com_depoimento()
        self.linha_do_caso(caso).update(
            {
                "etapa": "encerrado",
                "rito": rito,
                "encerrado_em": _instante(dia),
                "desfecho": desfecho,
                "recebido_em": _instante(dia - timedelta(days=20)),
            }
        )
        return caso

    def guarda(self, caso: str, pid: str = COORDENACAO) -> dict:
        return self.abrir(pid, caso)["guarda"]

    def conteudo(self, caso: str) -> dict[str, int]:
        tabelas = self.banco.tabelas
        deps = {d["id"] for d in tabelas.get("conduta_depoimentos", []) if d["caso_id"] == caso}
        return {
            "conduta_depoimentos": len(deps),
            "conduta_depoimento_arquivos": sum(
                1 for a in tabelas.get("conduta_depoimento_arquivos", []) if a["depoimento_id"] in deps
            ),
            "conduta_votos": sum(1 for v in tabelas.get("conduta_votos", []) if v["caso_id"] == caso),
        }

    def com_voto(self, caso: str) -> None:
        self.banco.tabelas.setdefault("conduta_votos", []).append(
            {"id": f"voto-{caso}", "caso_id": caso, "rodada": 1, "participante_id": MEMBRO, "voto_cifrado": "v1:x"}
        )

    def acoes(self, caso: str) -> list[str]:
        return [t["acao"] for t in self.banco.tabelas["conduta_trilha"] if t["caso_id"] == caso]


@pytest.fixture
def comite() -> ComiteDaGuarda:
    return ComiteDaGuarda()


@pytest.fixture
def emails(monkeypatch) -> list[dict]:
    enviados: list[dict] = []

    def _enviar(destinatario, assunto, html, texto, **kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(guarda, "_enviar_email", _enviar)
    return enviados


@pytest.fixture
def etiquetas(monkeypatch) -> list[dict]:
    """O PDF dublado: guarda os dados que iriam para a folha."""
    from app.services.seguranca_do_paciente import termo

    pedidas: list[dict] = []

    def _gerar(dados):
        pedidas.append(dados)
        return b"%PDF-1.7 etiqueta"

    monkeypatch.setattr(termo, "gerar_pdf_do_termo", _gerar)
    return pedidas


def _folha(dados: dict) -> str:
    return env.get_template(dados["modelo"]).render(**dados, logo_path=None, font_path=None)


VENCIDO_HA_CINCO_ANOS = _anos_antes(HOJE, 5) - timedelta(days=1)


# ═══════════════════════════════════════════════════════════════════════════
# 1. "IMPRIMIR ETIQUETA" gera a folha A4 com os campos do Anexo E.2, sem nome
#    de pessoa, setor nem assunto
# ═══════════════════════════════════════════════════════════════════════════


class TestEtiqueta:
    def test_a_etiqueta_sai_em_pdf_com_os_campos_do_anexo_e2(self, comite, etiquetas):
        caso = comite.encerrado(dia=date(2026, 11, 10))
        protocolo = comite.linha_do_caso(caso)["protocolo"]

        resposta = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso}/etiqueta")

        assert resposta.status_code == 200, resposta.text
        assert resposta.headers["content-type"] == "application/pdf"
        assert resposta.content.startswith(b"%PDF")
        folha = _folha(etiquetas[0])
        assert "Canal de Conduta: documentos originais" in folha
        assert "Sigiloso. Abrir somente por membro do Comitê de Conduta" in folha
        assert protocolo in folha
        assert "Rápido" in folha
        assert "Abertura: 21/10/2026" in folha
        assert "Encerramento: 10/11/2026" in folha
        assert "Termo de declaração: 1" in folha
        assert "10/11/2031" in folha  # guardar até: cinco anos
        assert "Assinatura sobre o lacre" in folha

    def test_o_encaminhado_guarda_um_ano(self, comite, etiquetas):
        caso = comite.encerrado(dia=date(2026, 11, 10), desfecho="encaminhado")

        comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso}/etiqueta")

        assert etiquetas[0]["guardar_ate"] == "10/11/2027"

    def test_a_etiqueta_nao_leva_nome_setor_nem_assunto(self, comite, etiquetas):
        caso = comite.encerrado(dia=date(2026, 11, 10))
        comite.linha_do_caso(caso)["categoria"] = "assedio_moral"
        comite.post(MEMBRO, f"/casos/{caso}/lacre", {"local": "Armário 2 da Diretoria"})

        comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso}/etiqueta")

        folha = _folha(etiquetas[0]).lower()
        proibidos = [*NOMES.values(), "Rogério", "Valente", "Supervisor", "almoxarifado", "assedio", "assédio"]
        assert [p for p in proibidos if p.lower() in folha] == []

    def test_o_detector_de_nome_pega_a_folha_com_o_nome(self, comite, etiquetas):
        """Piso do teste acima: o nome que entra na folha aparece nela."""
        caso = comite.encerrado(dia=date(2026, 11, 10))
        comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso}/etiqueta")

        folha = _folha({**etiquetas[0], "protocolo": "Rogério Valente"}).lower()

        assert "rogério" in folha

    def test_a_etiqueta_e_do_caso_encerrado(self, comite, etiquetas):
        caso, _ = comite.caso_com_depoimento()

        resposta = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso}/etiqueta")

        assert resposta.status_code == 409
        assert etiquetas == []

    def test_a_folha_vira_pdf_de_verdade(self, comite):
        caso = comite.encerrado(dia=date(2026, 11, 10))

        resposta = comite.cliente(MEMBRO).get(f"{BASE}/casos/{caso}/etiqueta")

        assert resposta.status_code == 200, resposta.text
        assert resposta.content.startswith(b"%PDF")
        assert len(resposta.content) > 1000


# ═══════════════════════════════════════════════════════════════════════════
# 2. O lacre registra quem lacrou, a data e o local de guarda
# ═══════════════════════════════════════════════════════════════════════════


class TestLacre:
    def test_o_lacre_registra_quem_lacrou_a_data_e_o_local(self, comite):
        caso = comite.encerrado(dia=date(2026, 11, 10))

        resposta = comite.post(
            MEMBRO, f"/casos/{caso}/lacre", {"data": "2026-11-12", "local": "Armário 2 da Diretoria"}
        )

        assert resposta.status_code == 200, resposta.text
        assert comite.guarda(caso)["lacre"] == {
            "por": NOMES[MEMBRO],
            "em": "2026-11-12",
            "local": "Armário 2 da Diretoria",
        }
        assert "lacrou_o_papel" in comite.acoes(caso)

    def test_a_tela_lista_os_originais_esperados_e_traz_o_local_das_configuracoes(self, comite):
        caso = comite.encerrado(dia=date(2026, 11, 10))
        comite.post(COORDENACAO, "/configuracoes/local_guarda_envelopes", {"texto": "Cofre da Diretoria"})

        tela = comite.guarda(caso, MEMBRO)

        assert tela["local_padrao"] == "Cofre da Diretoria"
        assert tela["originais"] == [
            {"rotulo": "Termo de declaração, Acusado 1", "situacao": "Assinado"},
            {"rotulo": "Ciência do Código pelo acusado", "situacao": "Aguardando"},
        ]
        assert tela["pode_lacrar"] is True

    def test_sem_data_vale_o_dia_de_hoje(self, comite):
        caso = comite.encerrado(dia=date(2026, 11, 10))

        comite.post(MEMBRO, f"/casos/{caso}/lacre", {"local": "Cofre"})

        assert comite.guarda(caso)["lacre"]["em"] == HOJE.isoformat()

    def test_o_lacre_e_registrado_uma_vez_so(self, comite):
        caso = comite.encerrado(dia=date(2026, 11, 10))
        comite.post(MEMBRO, f"/casos/{caso}/lacre", {"local": "Cofre"})

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/lacre", {"local": "Outro lugar"})

        assert resposta.status_code == 409
        assert comite.guarda(caso)["lacre"]["local"] == "Cofre"

    def test_sem_local_ou_com_data_futura_o_lacre_e_recusado(self, comite):
        caso = comite.encerrado(dia=date(2026, 11, 10))
        amanha = (HOJE + timedelta(days=1)).isoformat()

        assert comite.post(MEMBRO, f"/casos/{caso}/lacre", {"local": "  "}).status_code == 422
        assert comite.post(MEMBRO, f"/casos/{caso}/lacre", {"local": "Cofre", "data": amanha}).status_code == 422
        assert comite.guarda(caso)["lacre"] is None

    def test_o_lacre_e_depois_do_encerramento(self, comite):
        caso, _ = comite.caso_com_depoimento()

        resposta = comite.post(MEMBRO, f"/casos/{caso}/lacre", {"local": "Cofre"})

        assert resposta.status_code == 409
        assert comite.linha_do_caso(caso).get("papel_lacrado_em") is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. O job elimina caso encerrado há mais de cinco anos e caso encaminhado há
#    mais de um, e registra a eliminação
# ═══════════════════════════════════════════════════════════════════════════


class TestEliminacao:
    def test_o_caso_encerrado_ha_mais_de_cinco_anos_e_eliminado_e_registrado(self, comite, emails):
        caso = comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)
        comite.com_voto(caso)
        arquivos = [a["storage_path"] for a in comite.banco.tabelas["conduta_depoimento_arquivos"]]
        assert len(arquivos) == 3

        resultado = guarda.rodada(comite.banco, HOJE)

        assert resultado["eliminados"] == 1
        assert comite.conteudo(caso) == dict.fromkeys(CONTEUDO, 0)
        assert [c for c in arquivos if ("conduta-arquivos", c) in comite.banco.storage.objetos] == []
        assert "eliminou_o_conteudo" in comite.acoes(caso)

    def test_no_ultimo_dia_da_guarda_o_caso_fica(self, comite, emails):
        caso = comite.encerrado(dia=_anos_antes(HOJE, 5))
        comite.com_voto(caso)

        assert guarda.rodada(comite.banco, HOJE)["eliminados"] == 0

        assert comite.conteudo(caso)["conduta_votos"] == 1
        assert comite.eliminacoes == []

    def test_o_encaminhado_ha_mais_de_um_ano_e_eliminado(self, comite, emails):
        caso = comite.encerrado(dia=_anos_antes(HOJE, 1) - timedelta(days=1), desfecho="encaminhado")

        guarda.rodada(comite.banco, HOJE)

        assert comite.eliminacoes == [caso]
        assert "eliminou_o_conteudo" in comite.acoes(caso)

    def test_o_concluido_ha_mais_de_um_ano_ainda_esta_na_guarda(self, comite, emails):
        comite.encerrado(dia=_anos_antes(HOJE, 1) - timedelta(days=1))

        guarda.rodada(comite.banco, HOJE)

        assert comite.eliminacoes == []

    def test_o_caso_aberto_nao_entra(self, comite, emails):
        caso, _ = comite.caso_com_depoimento()
        comite.linha_do_caso(caso)["recebido_em"] = _instante(VENCIDO_HA_CINCO_ANOS)

        guarda.rodada(comite.banco, HOJE)

        assert comite.eliminacoes == []

    def test_o_arquivo_que_o_bucket_nao_solta_deixa_o_caso_inteiro(self, comite, emails, monkeypatch):
        caso = comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)
        monkeypatch.setattr(guarda.storage, "delete_file", lambda *_a: False)

        resultado = guarda.rodada(comite.banco, HOJE)

        assert resultado == {"eliminados": 0, "avisados": 0, "falhas": 1}
        assert comite.eliminacoes == []
        assert comite.conteudo(caso)["conduta_depoimentos"] == 1

    def test_o_caso_eliminado_abre_so_com_os_metadados_e_a_trilha(self, comite, emails):
        caso = comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)
        guarda.rodada(comite.banco, HOJE)

        tela = comite.abrir(COORDENACAO, caso)

        assert tela["relato"] is None
        assert tela["guarda"]["eliminado_em"]
        assert tela["trilha"]["pode_baixar_dossie"] is False
        assert comite.baixar(COORDENACAO, caso).status_code == 409

    def test_a_segunda_rodada_nao_elimina_de_novo(self, comite, emails):
        comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)
        guarda.rodada(comite.banco, HOJE)

        assert guarda.rodada(comite.banco, HOJE)["eliminados"] == 0
        assert len(comite.eliminacoes) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. Caso congelado não é eliminado, e só a coordenação congela e descongela
# ═══════════════════════════════════════════════════════════════════════════


class TestCongelar:
    def test_o_caso_congelado_nao_e_eliminado(self, comite, emails):
        caso = comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)

        assert comite.post(COORDENACAO, f"/casos/{caso}/congelamento").status_code == 200
        guarda.rodada(comite.banco, HOJE)

        assert comite.eliminacoes == []
        assert comite.conteudo(caso)["conduta_depoimentos"] == 1
        assert comite.guarda(caso)["congelado_em"]
        assert "congelou_o_caso" in comite.acoes(caso)

    def test_descongelado_a_guarda_volta_a_valer(self, comite, emails):
        caso = comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)
        comite.post(COORDENACAO, f"/casos/{caso}/congelamento")

        assert comite.post(COORDENACAO, f"/casos/{caso}/descongelamento").status_code == 200
        guarda.rodada(comite.banco, HOJE)

        assert comite.eliminacoes == [caso]
        assert "descongelou_o_caso" in comite.acoes(caso)

    @pytest.mark.parametrize("pid", [MEMBRO, LEITOR])
    def test_so_a_coordenacao_congela(self, comite, pid):
        caso = comite.encerrado(dia=date(2026, 11, 10))

        resposta = comite.post(pid, f"/casos/{caso}/congelamento")

        assert resposta.status_code == 403
        assert comite.linha_do_caso(caso).get("congelado_em") is None
        assert comite.guarda(caso, pid)["pode_congelar"] is False

    @pytest.mark.parametrize("pid", [MEMBRO, LEITOR])
    def test_so_a_coordenacao_descongela(self, comite, pid):
        caso = comite.encerrado(dia=date(2026, 11, 10))
        comite.post(COORDENACAO, f"/casos/{caso}/congelamento")

        resposta = comite.post(pid, f"/casos/{caso}/descongelamento")

        assert resposta.status_code == 403
        assert comite.linha_do_caso(caso)["congelado_em"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. O aviso de vencimento do papel chega à coordenação e não sai para caso
#    congelado
# ═══════════════════════════════════════════════════════════════════════════


class TestAvisoDoPapel:
    def test_o_aviso_chega_a_coordenacao_e_so_a_ela(self, comite, emails):
        caso = comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)
        protocolo = comite.linha_do_caso(caso)["protocolo"]

        resultado = guarda.rodada(comite.banco, HOJE)

        assert resultado["avisados"] == 1
        assert [e["para"] for e in emails] == ["coord@hsm.test"]
        assert emails[0]["assunto"] == FRASE
        assert "https://app.hsm.test/comite-de-conduta/casos" in emails[0]["texto"]
        assert protocolo not in emails[0]["html"] + emails[0]["texto"]

    def test_o_aviso_sai_uma_vez_so(self, comite, emails):
        comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)
        guarda.rodada(comite.banco, HOJE)

        guarda.rodada(comite.banco, HOJE)

        assert len(emails) == 1

    def test_o_caso_congelado_nao_avisa(self, comite, emails):
        caso = comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)
        comite.post(COORDENACAO, f"/casos/{caso}/congelamento")

        guarda.rodada(comite.banco, HOJE)

        assert emails == []

    def test_o_caso_na_guarda_nao_avisa(self, comite, emails):
        comite.encerrado(dia=_anos_antes(HOJE, 5))

        guarda.rodada(comite.banco, HOJE)

        assert emails == []


# ═══════════════════════════════════════════════════════════════════════════
# 6. O job não chama IA
# ═══════════════════════════════════════════════════════════════════════════

_MARCAS_DE_IA = ("ai_processor", "anthropic", "openai", "openrouter", "agente", "ia_chaves")


def _marcas(codigo: str) -> list[str]:
    """As marcas de IA nos imports do módulo."""
    nomes = []
    for no in ast.walk(ast.parse(codigo)):
        if isinstance(no, ast.Import):
            nomes += [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            nomes += [no.module or "", *(a.name for a in no.names)]
    return [marca for marca in _MARCAS_DE_IA if any(marca in nome.lower() for nome in nomes)]


class TestSemIa:
    def test_o_detector_reconhece_um_modulo_que_chama_ia(self):
        from app.services.conduta import trava

        assert _marcas(inspect.getsource(trava))

    def test_o_servico_da_guarda_nao_importa_ia(self):
        assert _marcas(inspect.getsource(guarda)) == []

    def test_o_job_so_chama_o_servico_e_esta_registrado_uma_vez_por_dia(self):
        from app.cron import scheduler

        assert "guarda.rodada(" in inspect.getsource(scheduler.guarda_conduta)
        assert _marcas(inspect.getsource(scheduler.guarda_conduta)) == []
        assert 'guarda_conduta,\n        "cron",\n        hour=7,' in inspect.getsource(scheduler.start_scheduler)

    def test_a_rodada_sai_com_o_provedor_de_ia_fora_do_ar(self, comite, emails, monkeypatch):
        import anthropic

        def _explode(*_a, **_kw):
            raise AssertionError("o job da guarda chamou IA")

        monkeypatch.setattr(anthropic, "Anthropic", _explode)
        monkeypatch.setattr(anthropic, "AsyncAnthropic", _explode)
        comite.encerrado(dia=VENCIDO_HA_CINCO_ANOS)

        assert guarda.rodada(comite.banco, HOJE) == {"eliminados": 1, "avisados": 1, "falhas": 0}

    def test_o_job_le_o_dia_em_sao_paulo_e_nao_derruba_o_scheduler(self, monkeypatch):
        from app.cron import scheduler

        chamadas: list = []
        monkeypatch.setattr(scheduler, "_supabase", lambda: "banco")
        monkeypatch.setattr(scheduler, "_hoje_em_sao_paulo", lambda: date(2031, 1, 2))
        monkeypatch.setattr(guarda, "rodada", lambda b, h: chamadas.append((b, h)) or {})
        scheduler.guarda_conduta()
        assert chamadas == [("banco", date(2031, 1, 2))]

        def _explode(*_a, **_kw):
            raise RuntimeError("banco fora do ar")

        monkeypatch.setattr(guarda, "rodada", _explode)
        scheduler.guarda_conduta()


# ═══════════════════════════════════════════════════════════════════════════
# 7. O texto do Produto no kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def _secao_do_kit(titulo: str) -> str:
    texto = (CONHECIMENTO_DIR / "canal-de-conduta.md").read_text(encoding="utf-8")
    partes = texto.split(f"## {titulo}\n", 1)
    assert len(partes) == 2, f"a seção {titulo!r} sumiu do kit"
    return partes[1].split("\n## ", 1)[0]


class TestKitDeConhecimento:
    def test_o_kit_conta_o_papel_a_guarda_o_congelamento_e_a_eliminacao(self):
        secao = _secao_do_kit("O papel original e a guarda")
        for trecho in (
            "ARQUIVAR PAPEL",
            "IMPRIMIR ETIQUETA",
            "não leva nome de pessoa, setor nem assunto",
            "quem lacrou, a data e o local de guarda",
            "cinco anos depois do encerramento",
            "um ano",
            "Congelar caso",
            "só a coordenação",
            "não é eliminado",
            "a trilha do caso continua",
            FRASE,
            "não chama IA",
        ):
            assert trecho in secao, trecho
