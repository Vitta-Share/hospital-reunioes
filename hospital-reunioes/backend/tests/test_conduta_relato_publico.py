"""O relato em passos do Canal de Conduta, pela rota pública (issue #1843).

Sem login. Quem relata passa pelos passos P1 a P5 e o envio chega aqui de uma
vez: a ciência do passo 1, a identificação, o "sobre o quê" e o "o que
aconteceu". A resposta traz o protocolo e o código, uma vez só, e a data para
voltar. Tudo é exercitado pela rota (TestClient), com o limitador, o
middleware de log e o tratamento do 429 de produção.
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
import sys
from datetime import UTC, date, datetime

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import JsonFormatter, RequestContextMiddleware  # noqa: E402
from app.routers import conduta_publico  # noqa: E402
from app.services.conduta import agente_de_triagem, cifra, relato_publico  # noqa: E402
from app.services.ouvidoria_acompanhamento import codigo_confere  # noqa: E402

RELATOS = "/api/conduta/relatos"
CONFIANCA = "/api/conduta/relatos/confianca"
IP_DE_QUEM_RELATA = "203.0.113.45"
APARELHO = "Mozilla/5.0 (Linux; Android 10; SM-A105M) Celular-de-Entrada/77"
TEXTO = "A supervisora do almoxarifado gritou com a equipe e ameaçou cortar o turno de quem reclamasse."
NOME = "Joana Prudente"

CIENCIA = {"ciente": True, "versoes": {"aviso_p1_anonimato": 1, "aviso_p1_protocolo": None, "aviso_p1_boa_fe": 2}}


def envio(**mudar) -> dict:
    base = {
        "ciencia": CIENCIA,
        "identificacao": "anonimo",
        "nome": None,
        "assunto": "A",
        "direcao": "nao",
        "posicao": "presenciou",
        "relato": TEXTO,
        "quando": "Semana passada",
        "ainda_acontece": True,
        "onde": "Almoxarifado",
        "quem": "A supervisora do turno da tarde",
        "testemunhas": "Dois auxiliares",
        "lideranca_sabe": "sim",
        "o_que_foi_feito": "Nada até agora",
        "evidencias": "Mensagens no grupo do setor",
    }
    return base | mudar


def _versoes(chave: str, quantas: int) -> list[dict]:
    return [
        {"id": f"{chave}-{n}", "chave": chave, "versao": n, "texto": f"texto {n}", "autor_id": "P1", "criado_em": "x"}
        for n in range(1, quantas + 1)
    ]


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "conduta_canal_aberto", True)
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture
def triagens(monkeypatch):
    """O agente de triagem é chamado depois da resposta; aqui só se anota."""
    chamadas: list[str] = []
    monkeypatch.setattr(agente_de_triagem, "agendar_triagem_do_caso", lambda _t, _s, caso_id: chamadas.append(caso_id))
    return chamadas


@pytest.fixture
def banco():
    return Banco(
        {
            "conduta_configuracoes": _versoes("aviso_p1_anonimato", 1) + _versoes("aviso_p1_boa_fe", 2),
        }
    )


@pytest.fixture
def cliente(banco, triagens):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(conduta_publico.router, prefix="/api")
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app, client=(IP_DE_QUEM_RELATA, 50123), raise_server_exceptions=False)


def _relatar(cliente, corpo=None, **cabecalhos):
    return cliente.post(
        RELATOS, json=corpo if corpo is not None else envio(), headers={"User-Agent": APARELHO, **cabecalhos}
    )


def _o_caso(banco) -> dict:
    (caso,) = banco.tabelas["conduta_casos"]
    return caso


class TestEnvio:
    def test_o_relato_enviado_devolve_protocolo_e_codigo_e_fica_cifrado(self, cliente, banco):
        resposta = _relatar(cliente)

        assert resposta.status_code == 201
        corpo = resposta.json()
        caso = _o_caso(banco)
        assert corpo["protocolo"] == caso["protocolo"]
        assert codigo_confere(corpo["codigo"], caso["codigo_hash"])
        assert TEXTO not in repr(banco.tabelas)
        assert TEXTO in cifra.decifrar_texto(caso["relato_cifrado"])

    def test_os_campos_do_passo_4_entram_no_relato_embaixo_do_texto(self, cliente, banco):
        _relatar(cliente)

        assert cifra.decifrar_texto(_o_caso(banco)["relato_cifrado"]) == (
            f"{TEXTO}\n"
            "\n"
            "Quem relata: presenciou\n"
            "Quando: Semana passada (ainda está acontecendo)\n"
            "Onde: Almoxarifado\n"
            "Quem: A supervisora do turno da tarde\n"
            "Testemunhas: Dois auxiliares\n"
            "Alguma liderança já sabe: Sim. O que foi feito: Nada até agora\n"
            "Evidências: Mensagens no grupo do setor"
        )

    def test_so_o_obrigatorio_basta(self, cliente, banco):
        minimo = {"ciencia": CIENCIA, "identificacao": "anonimo", "direcao": "nao_sei", "relato": TEXTO}

        resposta = _relatar(cliente, minimo)

        assert resposta.status_code == 201
        caso = _o_caso(banco)
        assert cifra.decifrar_texto(caso["relato_cifrado"]) == TEXTO
        assert caso["categoria"] is None
        assert caso["direcao_envolvida"] == "nao_sei"

    def test_o_assunto_vira_a_categoria_do_caso(self, cliente, banco):
        _relatar(cliente, envio(assunto="C"))

        assert _o_caso(banco)["categoria"] == "C"

    def test_o_agente_de_triagem_le_o_caso_depois_da_resposta(self, cliente, banco, triagens):
        _relatar(cliente)

        assert triagens == [_o_caso(banco)["id"]]

    def test_a_data_para_voltar_e_o_fim_dos_5_dias_uteis_de_leitura(self, cliente, monkeypatch):
        # Sexta, 20/11/2026, 22h em São Paulo (já sábado em UTC): conta da sexta.
        monkeypatch.setattr(relato_publico, "agora_utc", lambda: datetime(2026, 11, 21, 1, 0, tzinfo=UTC))

        resposta = _relatar(cliente)

        assert resposta.json()["voltar_a_partir_de"] == date(2026, 11, 27).isoformat()


class TestCiencia:
    def test_a_ciencia_grava_o_momento_e_a_versao_de_cada_aviso_sem_identidade(self, cliente, banco):
        _relatar(cliente)

        caso = _o_caso(banco)
        assert caso["ciencia_em"]
        assert caso["ciencia_versoes"] == {"aviso_p1_anonimato": 1, "aviso_p1_protocolo": None, "aviso_p1_boa_fe": 2}

    def test_sem_marcar_a_caixa_nada_e_gravado(self, cliente, banco):
        resposta = _relatar(cliente, envio(ciencia={**CIENCIA, "ciente": False}))

        assert resposta.status_code == 422
        assert banco.tabelas.get("conduta_casos", []) == []

    def test_versao_de_aviso_que_nunca_existiu_e_recusada(self, cliente, banco):
        forjada = {**CIENCIA, "versoes": {**CIENCIA["versoes"], "aviso_p1_boa_fe": 3}}

        resposta = _relatar(cliente, envio(ciencia=forjada))

        assert resposta.status_code == 422
        assert banco.tabelas.get("conduta_casos", []) == []


class TestIdentificacao:
    def test_o_nome_fica_cifrado_e_fora_do_relato(self, cliente, banco):
        _relatar(cliente, envio(identificacao="identificado", nome=NOME))

        caso = _o_caso(banco)
        assert NOME not in repr(banco.tabelas)
        assert cifra.decifrar_texto(caso["relator_nome_cifrado"]) == NOME
        assert NOME not in cifra.decifrar_texto(caso["relato_cifrado"])

    def test_o_relato_anonimo_nao_guarda_nome(self, cliente, banco):
        _relatar(cliente, envio(nome=NOME))

        assert "relator_nome_cifrado" not in _o_caso(banco)
        assert NOME not in repr(banco.tabelas)

    def test_com_identificacao_o_nome_e_obrigatorio(self, cliente, banco):
        resposta = _relatar(cliente, envio(identificacao="identificado", nome="  "))

        assert resposta.status_code == 422
        assert banco.tabelas.get("conduta_casos", []) == []


class _Captura(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.linhas: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.linhas.append(self.format(record))


@pytest.fixture
def log():
    """Tudo o que o app escreve no log, já como sai no stdout do container."""
    captura = _Captura()
    raiz = logging.getLogger()
    nivel = raiz.level
    raiz.addHandler(captura)
    raiz.setLevel(logging.DEBUG)
    yield captura
    raiz.removeHandler(captura)
    raiz.setLevel(nivel)


class TestSemRastro:
    def test_depois_do_relato_nem_o_banco_nem_o_log_guardam_ip_aparelho_ou_localizacao(self, cliente, banco, log):
        resposta = _relatar(cliente, **{"X-Forwarded-For": "198.51.100.23", "Geolocation": "-22.87,-43.46"})

        assert resposta.status_code == 201
        rastro = repr(banco.tabelas) + "\n".join(log.linhas)
        assert log.linhas, "controle: o log da requisição tem que ter sido escrito"
        for marca in (IP_DE_QUEM_RELATA, "203.0.113", "198.51.100.23", "Android", "Celular-de-Entrada", "-22.87"):
            assert marca not in rastro

    def test_a_resposta_nao_grava_cookie_nem_fica_em_cache(self, cliente):
        resposta = _relatar(cliente)

        assert "set-cookie" not in resposta.headers
        assert resposta.headers["cache-control"] == "no-store"

    def test_o_token_de_login_que_vier_e_ignorado(self, cliente, banco):
        """Sem login: a rota nem lê o cabeçalho de sessão."""
        resposta = _relatar(cliente, Authorization="Bearer token-de-quem-esqueceu-logado")

        assert resposta.status_code == 201
        assert "token-de-quem" not in repr(banco.tabelas)


class TestNadaSensivelNoErro:
    @pytest.mark.parametrize(
        "mudar",
        [
            {"relato": TEXTO + " " + "x" * 10_000},
            {"identificacao": "identificado", "nome": NOME * 20},
            {"direcao": TEXTO},
            {"quem": NOME + " " + "y" * 600},
        ],
        ids=["relato-longo", "nome-longo", "direcao-invalida", "quem-longo"],
    )
    def test_a_recusa_nao_devolve_trecho_de_relato_nem_nome(self, cliente, banco, log, mudar):
        resposta = _relatar(cliente, envio(**mudar))

        assert resposta.status_code == 422
        saida = resposta.text + "\n".join(log.linhas)
        assert "supervisora" not in saida
        assert "Joana" not in saida
        assert "almoxarifado" not in saida.lower()

    def test_a_recusa_diz_quais_campos_conferir(self, cliente):
        resposta = _relatar(cliente, envio(relato="x" * 10_001))

        assert resposta.json() == {"detail": "Confira os campos: relato."}

    def test_sem_a_chave_da_cifra_a_falha_nao_traz_o_relato(self, cliente, banco, log, monkeypatch):
        monkeypatch.setattr(settings, "conduta_chave_cifra", "")

        resposta = _relatar(cliente)

        assert resposta.status_code == 503
        assert "supervisora" not in resposta.text + "\n".join(log.linhas)
        assert banco.tabelas.get("conduta_casos", []) == []


class TestRajada:
    def test_a_rajada_do_mesmo_aparelho_para_no_limite_sem_gravar_o_endereco(self, cliente, banco, log):
        respostas = [_relatar(cliente).status_code for _ in range(5)]

        assert respostas == [201, 201, 201, 429, 429]
        assert len(banco.tabelas["conduta_casos"]) == 3
        assert IP_DE_QUEM_RELATA not in repr(banco.tabelas) + "\n".join(log.linhas)

    def test_outro_aparelho_ainda_relata(self, cliente, banco):
        for _ in range(3):
            _relatar(cliente)
        outro = TestClient(cliente.app, client=("198.51.100.77", 40000), raise_server_exceptions=False)

        assert outro.post(RELATOS, json=envio()).status_code == 201


class TestCanalFechado:
    def test_com_a_chave_de_abertura_desligada_o_envio_responde_404(self, cliente, banco, monkeypatch):
        monkeypatch.setattr(settings, "conduta_canal_aberto", False)

        resposta = _relatar(cliente)

        assert resposta.status_code == 404
        assert banco.tabelas.get("conduta_casos", []) == []


class TestConfianca:
    def _relatado(self, cliente) -> dict:
        return _relatar(cliente).json()

    def test_a_nota_de_confianca_fica_no_caso(self, cliente, banco):
        novo = self._relatado(cliente)

        resposta = cliente.post(CONFIANCA, json={"protocolo": novo["protocolo"], "codigo": novo["codigo"], "nota": 4})

        assert resposta.status_code == 204
        assert _o_caso(banco)["confianca"] == 4

    def test_a_nota_vale_uma_vez_so(self, cliente, banco):
        novo = self._relatado(cliente)
        chave = {"protocolo": novo["protocolo"], "codigo": novo["codigo"]}
        cliente.post(CONFIANCA, json={**chave, "nota": 2})

        cliente.post(CONFIANCA, json={**chave, "nota": 5})

        assert _o_caso(banco)["confianca"] == 2

    def test_codigo_errado_nao_grava_e_nao_diz_por_que(self, cliente, banco):
        novo = self._relatado(cliente)

        resposta = cliente.post(CONFIANCA, json={"protocolo": novo["protocolo"], "codigo": "AAAAAAAAAA", "nota": 1})

        assert resposta.status_code == 404
        assert novo["protocolo"] not in resposta.text
        assert _o_caso(banco).get("confianca") is None

    @pytest.mark.parametrize("nota", [0, 6])
    def test_a_nota_vai_de_1_a_5(self, cliente, banco, nota):
        novo = self._relatado(cliente)

        resposta = cliente.post(
            CONFIANCA, json={"protocolo": novo["protocolo"], "codigo": novo["codigo"], "nota": nota}
        )

        assert resposta.status_code == 422
        assert novo["protocolo"] not in resposta.text
        assert novo["codigo"] not in resposta.text
        assert _o_caso(banco).get("confianca") is None


class TestOComiteLe:
    """O que a pessoa enviou chega à tela do caso, para o Comitê, e só a ele."""

    def _aberto(self, corpo: dict) -> dict:
        # Sem avisos salvos nas Configurações: a tela mostrou o texto padrão.
        corpo = corpo | {"ciencia": {"ciente": True, "versoes": dict.fromkeys(relato_publico.AVISOS_DO_PASSO_1)}}
        from test_conduta_portao import _Cenario, _participacao, _pessoa, _rota_do_caso

        cenario = _Cenario(_pessoa(), [_participacao(papel="membro")])
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(conduta_publico.router, prefix="/api")
        app.dependency_overrides[get_supabase_client] = lambda: cenario.banco
        assert TestClient(app).post(RELATOS, json=corpo).status_code == 201
        (caso,) = cenario.banco.tabelas["conduta_casos"]
        return cenario.cliente().get(_rota_do_caso(caso)).json()

    def test_com_identificacao_o_comite_ve_o_nome(self, triagens):
        aberto = self._aberto(envio(identificacao="identificado", nome=NOME))

        assert aberto["relator_nome"] == NOME
        assert aberto["relato"].startswith(TEXTO)

    def test_no_relato_anonimo_nao_ha_nome(self, triagens):
        aberto = self._aberto(envio(nome=NOME))

        assert aberto["relator_nome"] is None
