"""A busca da tela de contas de Contas médicas (issue #1956, PRD #1933, ADR 0105).

A faturista digita parte do número do atendimento ou do rótulo do paciente e a
rota procura em todas as etapas da conta, de quem quer que esteja com ela,
dizendo a etapa e com quem está. O número da conta não entra na busca.

O dublê do banco é o da rota da fila, com o `ilike` do PostgREST: sem
diferenciar maiúscula, mas diferenciando acento, como o Postgres. Os rótulos
de paciente e os nomes de pessoa são inventados.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_contas_medicas_envio import (  # noqa: E402
    _Banco,
    _c,
    _cenario,
    _cliente,
    _Consulta,
    _reset_rate_limiter,  # noqa: F401 (fixture autouse do envio)
)

ROTA_BUSCA = "/api/contas-medicas/busca"


def _como_like(padrao: str) -> re.Pattern:
    """O `ilike` do Postgres: `%` é qualquer trecho, `_` é um caractere."""
    partes = ("." * (p == "_") or ".*" * (p == "%") or re.escape(p) for p in padrao)
    return re.compile("".join(partes), re.IGNORECASE | re.DOTALL)


class _ConsultaComIlike(_Consulta):
    def ilike(self, coluna, padrao):
        regex = _como_like(padrao)
        self._filtros.append(lambda linha: linha.get(coluna) is not None and regex.fullmatch(linha[coluna]))
        return self


class _BancoDaBusca(_Banco):
    def table(self, nome: str):
        return _ConsultaComIlike(self, nome)


def _banco(contas: list[dict], atendimentos: list[dict], **tabelas) -> _BancoDaBusca:
    base = _cenario(cm_conta=contas, cm_atendimento=atendimentos, **tabelas)
    return _BancoDaBusca(base.tabelas)


def _at(id_: str, numero: str, rotulo: str | None = None) -> dict:
    return {"id": id_, "numero_atendimento": numero, "paciente_rotulo": rotulo, "operadora_id": "op-1"}


def _semeado() -> _BancoDaBusca:
    """Uma conta em cada etapa. F1 é quem busca; a em análise e a concluída
    estão com F2; a em Envios foi enviada por F2 e ainda não ficou pronta."""
    contas = [
        _c("livre", "A_FAZER", 10, atendimento_id="at-livre", arquivo_id="arq-livre"),
        _c("da-outra", "EM_CORRECAO", 20, faturista="F2", atendimento_id="at-outra", arquivo_id="arq-outra"),
        _c("concluida", "CONCLUIDA", 5, faturista="F2", atendimento_id="at-concluida", arquivo_id="arq-concl"),
        _c("no-envio", "PROCESSANDO", 30, atendimento_id="at-envio", arquivo_id="arq-envio"),
        _c("minha", "EM_CORRECAO", 25, faturista="F1", atendimento_id="at-minha", arquivo_id="arq-minha"),
    ]
    atendimentos = [
        _at("at-livre", "27751", "Antônia F."),
        _at("at-outra", "27752", "Joana B."),
        _at("at-concluida", "27753", "Célia R."),
        _at("at-envio", "27754", "Ivone P."),
        _at("at-minha", "31999", "Marta L."),
    ]
    envios = [{"id": "env-F1", "usuario_id": "F1"}, {"id": "env-F2", "usuario_id": "F2"}]
    arquivos = [
        {"id": c["arquivo_id"], "envio_id": "env-F2", "tipo": "CONTA", "atendimento_id": c["atendimento_id"]}
        for c in contas
    ]
    return _banco(contas, atendimentos, cm_envio=envios, cm_arquivo=arquivos)


def _buscar(texto: str, banco=None, quem: str = "faturista"):
    return _cliente(quem, banco or _semeado()).get(ROTA_BUSCA, params={"q": texto})


def _ids(resposta) -> list[str]:
    assert resposta.status_code == 200, resposta.text
    return sorted(c["id"] for c in resposta.json()["contas"])


class TestBusca:
    def test_acha_pela_parte_do_numero_do_atendimento(self):
        assert _ids(_buscar("2775")) == ["concluida", "da-outra", "livre", "no-envio"]
        assert _ids(_buscar("753")) == ["concluida"]

    @pytest.mark.parametrize("texto", ["antonia", "ANTÔN", "tôni", "a f."])
    def test_acha_pela_parte_do_rotulo_sem_diferenciar_maiuscula_nem_acento(self, texto):
        assert _ids(_buscar(texto)) == ["livre"]

    def test_o_acento_digitado_acha_o_rotulo_gravado_sem_acento(self):
        banco = _semeado()
        banco.tabelas["cm_atendimento"][2]["paciente_rotulo"] = "Celia R."

        assert _ids(_buscar("célia", banco)) == ["concluida"]

    def test_o_curinga_do_banco_nao_vira_resultado(self):
        # "_" e "%" casam qualquer coisa no `ilike`: a conferência exata tira.
        assert _ids(_buscar("a_")) == []
        assert _ids(_buscar("2%5")) == []

    @pytest.mark.parametrize("quem", ["apoio", "credenciamento", "sem_eixo"])
    def test_sem_analisar_contas_recebe_403(self, quem):
        assert _buscar("2775", quem=quem).status_code == 403

    def test_tem_limite_de_120_buscas_por_minuto(self):
        cliente = _cliente("faturista", _semeado())

        respostas = [cliente.get(ROTA_BUSCA, params={"q": "2775"}).status_code for _ in range(121)]

        assert respostas[:120] == [200] * 120
        assert respostas[120] == 429

    def test_acha_a_livre_a_da_outra_a_concluida_e_a_de_envios_com_a_etapa_e_com_quem_esta(self):
        contas = {c["id"]: c for c in _buscar("2775").json()["contas"]}

        campos = ("numero_atendimento", "paciente_rotulo", "operadora", "periodo_inicio", "periodo_fim", "etapa", "com")
        assert {i: tuple(c[k] for k in campos) for i, c in contas.items()} == {
            "livre": ("27751", "Antônia F.", "ASSIM", "2026-10-01", "2026-10-05", "fila", None),
            "da-outra": ("27752", "Joana B.", "ASSIM", "2026-10-01", "2026-10-05", "em_analise", "Pessoa F2"),
            "concluida": ("27753", "Célia R.", "ASSIM", "2026-10-01", "2026-10-05", "concluidas", "Pessoa F2"),
            "no-envio": ("27754", "Ivone P.", "ASSIM", "2026-10-01", "2026-10-05", "envios", "Pessoa F2"),
        }

    def test_nao_procura_pelo_numero_da_conta(self):
        banco = _semeado()
        # O número da conta da livre bate com o texto; o do atendimento, não.
        banco.tabelas["cm_conta"][0]["numero_conta"] = "88123"

        assert _ids(_buscar("88123", banco)) == []
        assert _ids(_buscar("8812", banco)) == []

    @pytest.mark.parametrize(
        ("quem", "abre"),
        [
            ("faturista", {"livre": True, "da-outra": False, "concluida": False, "no-envio": False, "minha": True}),
            ("coordenadora", {"livre": True, "da-outra": True, "concluida": True, "no-envio": False, "minha": True}),
        ],
    )
    def test_ver_nao_e_abrir_a_faturista_abre_a_livre_e_as_suas_e_o_painel_completo_as_que_tem_guia(self, quem, abre):
        banco = _semeado()
        achadas = [c for q in ("2775", "31999") for c in _buscar(q, banco, quem).json()["contas"]]

        assert {c["id"]: c["pode_abrir"] for c in achadas} == abre
        assert {c["id"] for c in achadas if c["minha"]} == ({"minha"} if quem == "faturista" else set())


def _muitas(n: int) -> _BancoDaBusca:
    contas = [_c(f"c{i:03d}", "A_FAZER", i, atendimento_id=f"at-{i:03d}") for i in range(n)]
    atendimentos = [_at(f"at-{i:03d}", f"40{i:03d}") for i in range(n)]
    return _banco(contas, atendimentos)


class TestTetoDaBusca:
    def test_comeca_com_dois_caracteres(self):
        assert _buscar("4").status_code == 422
        assert _buscar("40", _muitas(3)).status_code == 200

    def test_devolve_no_maximo_50_e_avisa_que_ha_mais(self):
        corpo = _buscar("40", _muitas(51)).json()

        assert len(corpo["contas"]) == 50
        assert corpo["mais"] is True

    def test_com_50_ou_menos_nao_avisa(self):
        corpo = _buscar("40", _muitas(50)).json()

        assert len(corpo["contas"]) == 50
        assert corpo["mais"] is False

    def test_o_numero_igual_ao_digitado_vem_primeiro(self):
        banco = _muitas(30)
        # O "4001" exato é a conta mais antiga: pela ordem de envio, viria por último.
        banco.tabelas["cm_atendimento"][0]["numero_atendimento"] = "4001"

        corpo = _buscar("4001", banco).json()

        assert [c["numero_atendimento"] for c in corpo["contas"]][:3] == ["4001", "40019", "40018"]
