"""Presença, quórum e reunião não instalada (issue #1774, PRD #1764, ADR 0095).

A Presidência registra, para cada pessoa, presente, ausente, ausente
justificado ou convidado. O app apura o quórum sobre quem contava para quórum no
dia da reunião (Ativo, A vencer, Em carência). Sem quórum, a reunião vira não
instalada, não aceita transcrição e a Presidência reagenda numa data nova, com
a reunião nova ligada à original.

O super admin sem Acesso pleno não passa por nenhuma das rotas: a recusa é o
403 com o corpo do módulo (ADR 0095, decisão 4).

O banco é o dublê em memória dos testes das reuniões do Núcleo. Nenhum nome,
registro ou e-mail de pessoa real. Nada aqui chama IA nem assinatura: a rota
de transcrição recusa antes de chegar no pipeline, que fica dublado mesmo assim.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_seguranca_do_paciente_reunioes import (  # noqa: E402
    DE_FORA,
    HOJE,
    MEMBRO,
    MEMBRO_SEM_TERMO,
    NUCLEO,
    PRESIDENCIA,
    R_COMUM,
    SUPER_ADMIN,
    SUPER_ADMIN_PLENO,
    _assert_recusado,
    _Banco,
    _banco,
    _cliente,
    _participacao,
    _pessoa,
    _reuniao,
)

R_PROG = "RD_NUCLEO_PROG"

SUPLENTE = _pessoa("SUPL1")
MEMBRO_3 = _pessoa("MEMB3")
MEMBRO_4 = _pessoa("MEMB4")
VENCIDO = _pessoa("VENC1")


def _cenario() -> _Banco:
    """Contam para quórum: PRES1, SUPL1, MEMB1, MEMB3 e MEMB4 (cinco). MEMB2
    está vigente sem Termo e VENC1 venceu há meses: os dois não contam."""
    banco = _banco()
    banco.tabelas["participantes"] += [dict(p) for p in (SUPLENTE, MEMBRO_3, MEMBRO_4, VENCIDO)]
    vencida = {
        **_participacao("VENC1"),
        "vigencia_inicio": (HOJE - timedelta(days=500)).isoformat(),
        "vigencia_fim": (HOJE - timedelta(days=120)).isoformat(),
    }
    banco.tabelas["participacoes"] += [
        _participacao("SUPL1", papel="suplente"),
        _participacao("MEMB3"),
        _participacao("MEMB4"),
        vencida,
    ]
    reuniao = _reuniao(R_PROG, titulo="Ordinária de dezembro", tipo="Ordinária mensal", colegiado=NUCLEO["id"])
    banco.tabelas["reunioes"].append({**reuniao, "status_ata": "PROGRAMADA", "json_ata": None})
    banco.tabelas["reuniao_presencas"] = []
    return banco


def _rota(sufixo: str = "presenca", rid: str = R_PROG) -> str:
    return f"/api/nsp/reunioes/{rid}/{sufixo}"


def _registrar(cliente, presenca: dict[str, str], rid: str = R_PROG):
    corpo = {"presencas": [{"participante_id": pid, "situacao": s} for pid, s in presenca.items()]}
    return cliente.put(_rota(rid=rid), json=corpo)


def _nova_data(dias: int = 14) -> dict[str, Any]:
    return {"data": (HOJE + timedelta(days=dias)).isoformat(), "hora_inicio": "10:00"}


def _reuniao_do_banco(banco: _Banco, rid: str) -> dict[str, Any]:
    return next(r for r in banco.tabelas["reunioes"] if r["id_reuniao"] == rid)


SEM_QUORUM = {"PRES1": "presente", "MEMB1": "presente", "SUPL1": "ausente_justificado", "MEMB3": "ausente"}
COM_QUORUM = {"PRES1": "presente", "MEMB1": "presente", "MEMB3": "presente", "MEMB4": "ausente"}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quem passa pelas rotas da presença
# ═══════════════════════════════════════════════════════════════════════════

ROTAS = [
    pytest.param("get", "presenca", None, id="ler_presenca"),
    pytest.param("put", "presenca", {"presencas": []}, id="registrar_presenca"),
    pytest.param("post", "nao-instalada", _nova_data(), id="nao_instalada"),
]


class TestAcesso:
    @pytest.mark.parametrize(("metodo", "sufixo", "corpo"), ROTAS)
    def test_super_admin_sem_acesso_pleno_recebe_recusa(self, metodo, sufixo, corpo):
        banco = _cenario()
        cliente = _cliente(SUPER_ADMIN, banco)
        kwargs = {"json": corpo} if corpo is not None else {}

        resposta = getattr(cliente, metodo)(_rota(sufixo), **kwargs)

        _assert_recusado(resposta)
        assert "dezembro" not in resposta.text
        assert banco.tabelas["reuniao_presencas"] == []
        assert _reuniao_do_banco(banco, R_PROG)["status_ata"] == "PROGRAMADA"

    @pytest.mark.parametrize("pessoa", [DE_FORA, MEMBRO_SEM_TERMO], ids=["de_fora", "sem_termo"])
    def test_quem_nao_abre_a_ata_nao_le_a_presenca(self, pessoa):
        _assert_recusado(_cliente(pessoa, _cenario()).get(_rota()))

    def test_super_admin_com_acesso_pleno_le_a_presenca(self):
        resposta = _cliente(SUPER_ADMIN_PLENO, _cenario()).get(_rota())

        assert resposta.status_code == 200, resposta.text

    def test_membro_le_a_presenca_e_nao_registra(self):
        banco = _cenario()
        cliente = _cliente(MEMBRO, banco)

        leitura = cliente.get(_rota())

        assert leitura.status_code == 200, leitura.text
        assert leitura.json()["pode_registrar"] is False
        _assert_recusado(_registrar(cliente, {"MEMB1": "presente"}))
        _assert_recusado(cliente.post(_rota("nao-instalada"), json=_nova_data()))
        assert banco.tabelas["reuniao_presencas"] == []

    def test_reuniao_comum_nao_passa_pela_rota_do_nucleo(self):
        resposta = _cliente(PRESIDENCIA, _cenario()).get(_rota(rid=R_COMUM))

        assert resposta.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 2. O registro de presença, pessoa a pessoa
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistro:
    def test_presidencia_registra_as_quatro_situacoes_e_le_de_volta(self):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        presenca = {"PRES1": "presente", "MEMB1": "ausente", "SUPL1": "ausente_justificado", "FORA1": "convidado"}

        gravada = _registrar(cliente, presenca)

        assert gravada.status_code == 200, gravada.text
        lida = cliente.get(_rota()).json()
        por_pessoa = {p["participante_id"]: p for p in lida["pessoas"]}
        assert {pid: por_pessoa[pid]["situacao"] for pid in presenca} == presenca
        assert por_pessoa["FORA1"]["nome"] == "Pessoa de Teste FORA1"
        assert por_pessoa["FORA1"]["conta_para_quorum"] is False
        assert lida["pode_registrar"] is True
        assert {(r["participante_id"], r["registrada_por"]) for r in banco.tabelas["reuniao_presencas"]} == {
            (pid, "PRES1") for pid in presenca
        }

    def test_registrar_de_novo_substitui_a_presenca_anterior(self):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        _registrar(cliente, {"PRES1": "presente", "MEMB1": "presente"})

        _registrar(cliente, {"PRES1": "presente", "MEMB1": "ausente_justificado"})

        situacoes = {r["participante_id"]: r["situacao"] for r in banco.tabelas["reuniao_presencas"]}
        assert situacoes == {"PRES1": "presente", "MEMB1": "ausente_justificado"}

    def test_a_lista_traz_quem_compunha_o_nucleo_no_dia_e_diz_quem_conta(self):
        lida = _cliente(PRESIDENCIA, _cenario()).get(_rota()).json()

        conta = {p["participante_id"]: p["conta_para_quorum"] for p in lida["pessoas"]}
        assert conta == {
            "PRES1": True,
            "SUPL1": True,
            "MEMB1": True,
            "MEMB3": True,
            "MEMB4": True,
            "MEMB2": False,
        }

    def test_situacao_fora_das_quatro_e_recusada(self):
        resposta = _registrar(_cliente(PRESIDENCIA, _cenario()), {"MEMB1": "atrasado"})

        assert resposta.status_code == 422

    def test_pessoa_que_nao_existe_e_recusada(self):
        banco = _cenario()
        resposta = _registrar(_cliente(PRESIDENCIA, banco), {"NINGUEM": "convidado"})

        assert resposta.status_code == 422
        assert banco.tabelas["reuniao_presencas"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. O quórum que a tela mostra
# ═══════════════════════════════════════════════════════════════════════════


class TestQuorumNaTela:
    def test_metade_arredondada_para_cima_com_a_presidencia_instala(self):
        """Cinco contam: três presentes com a Presidência instalam."""
        cliente = _cliente(PRESIDENCIA, _cenario())

        quorum = _registrar(cliente, COM_QUORUM).json()["quorum"]

        assert quorum == {
            "total": 5,
            "presentes": 3,
            "minimo": 3,
            "presidencia_ou_suplente": True,
            "instalada": True,
        }

    def test_dois_de_cinco_nao_instalam(self):
        quorum = _registrar(_cliente(PRESIDENCIA, _cenario()), SEM_QUORUM).json()["quorum"]

        assert (quorum["presentes"], quorum["instalada"]) == (2, False)

    def test_sem_termo_e_vencido_presentes_nao_somam(self):
        presenca = {"PRES1": "presente", "MEMB1": "presente", "MEMB2": "presente", "VENC1": "presente"}

        quorum = _registrar(_cliente(PRESIDENCIA, _cenario()), presenca).json()["quorum"]

        assert (quorum["total"], quorum["presentes"], quorum["instalada"]) == (5, 2, False)


# ═══════════════════════════════════════════════════════════════════════════
# 4. A reunião não instalada
# ═══════════════════════════════════════════════════════════════════════════


class TestNaoInstalada:
    def test_sem_quorum_fica_nao_instalada_e_nasce_a_reagendada_ligada_a_original(self):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        _registrar(cliente, SEM_QUORUM)

        resposta = cliente.post(_rota("nao-instalada"), json=_nova_data(14))

        assert resposta.status_code == 201, resposta.text
        assert _reuniao_do_banco(banco, R_PROG)["status_ata"] == "NAO_INSTALADA"
        nova = _reuniao_do_banco(banco, resposta.json()["reagendada"]["id_reuniao"])
        assert nova["reagendada_de"] == R_PROG
        assert nova["status_ata"] == "PROGRAMADA"
        assert nova["data"] == (HOJE + timedelta(days=14)).isoformat()
        assert (nova["tipo"], nova["titulo"], nova["colegiado_id"]) == (
            "Ordinária mensal",
            "Ordinária de dezembro",
            NUCLEO["id"],
        )
        lista = cliente.get("/api/nsp/reunioes").json()["reunioes"]
        assert {r["id_reuniao"]: r["status_ata"] for r in lista}[R_PROG] == "NAO_INSTALADA"

    def test_com_quorum_a_reuniao_nao_vira_nao_instalada(self):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        _registrar(cliente, COM_QUORUM)

        resposta = cliente.post(_rota("nao-instalada"), json=_nova_data())

        assert resposta.status_code == 409
        assert _reuniao_do_banco(banco, R_PROG)["status_ata"] == "PROGRAMADA"
        assert len(banco.tabelas["reunioes"]) == 3

    def test_presidencia_e_suplente_ausentes_nao_instala_mesmo_com_maioria(self):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        presenca = {"PRES1": "ausente", "SUPL1": "ausente", "MEMB1": "presente", "MEMB3": "presente"}
        presenca["MEMB4"] = "presente"

        quorum = _registrar(cliente, presenca).json()["quorum"]
        resposta = cliente.post(_rota("nao-instalada"), json=_nova_data())

        assert (quorum["presentes"], quorum["instalada"]) == (3, False)
        assert resposta.status_code == 201, resposta.text

    def test_a_nova_data_tem_que_ser_depois_da_original(self):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        _registrar(cliente, SEM_QUORUM)

        resposta = cliente.post(_rota("nao-instalada"), json=_nova_data(0))

        assert resposta.status_code == 422
        assert _reuniao_do_banco(banco, R_PROG)["status_ata"] == "PROGRAMADA"

    def test_reuniao_nao_instalada_nao_aceita_transcricao(self, monkeypatch):
        from app.pipeline import orchestrator

        chamadas: list = []
        monkeypatch.setattr(orchestrator, "run_pipeline", lambda *a, **kw: chamadas.append(a))
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        _registrar(cliente, SEM_QUORUM)
        cliente.post(_rota("nao-instalada"), json=_nova_data())

        resposta = cliente.post(
            f"/api/reunioes/{R_PROG}/anexar-transcricao",
            files={"file": ("reuniao.txt", "Fala de teste da reunião.".encode(), "text/plain")},
        )

        assert resposta.status_code == 400, resposta.text
        assert _reuniao_do_banco(banco, R_PROG)["status_ata"] == "NAO_INSTALADA"
        assert chamadas == []

    def test_a_lista_geral_de_reunioes_mostra_a_nao_instalada_a_quem_e_do_nucleo(self):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        _registrar(cliente, SEM_QUORUM)
        cliente.post(_rota("nao-instalada"), json=_nova_data())

        resposta = _cliente(MEMBRO, banco).get("/api/reunioes")

        assert resposta.status_code == 200, resposta.text
        assert {r["id_reuniao"]: r["status_ata"] for r in resposta.json()}[R_PROG] == "NAO_INSTALADA"

    def test_o_kit_de_conhecimento_diz_o_comportamento_novo(self):
        caminho = os.path.join(os.path.dirname(__file__), "..", "app", "conhecimento", "seguranca-do-paciente.md")
        with open(caminho, encoding="utf-8") as arquivo:
            texto = " ".join(arquivo.read().split())

        assert "presente, ausente, ausente justificado ou convidado" in texto
        assert "metade de quem conta para quórum no dia da reunião, arredondada para cima" in texto
        assert "com a Presidência ou o suplente presente" in texto
        assert "fica como não instalada, não aceita transcrição nem ata" in texto
        assert "a reunião reagendada nasce ligada à original" in texto

    def test_reuniao_nao_instalada_nao_aceita_nova_presenca_nem_segundo_reagendamento(self):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        _registrar(cliente, SEM_QUORUM)
        cliente.post(_rota("nao-instalada"), json=_nova_data())

        assert _registrar(cliente, COM_QUORUM).status_code == 409
        assert cliente.post(_rota("nao-instalada"), json=_nova_data(20)).status_code == 409
        assert cliente.get(_rota()).json()["pode_registrar"] is False
        assert len(banco.tabelas["reunioes"]) == 4
