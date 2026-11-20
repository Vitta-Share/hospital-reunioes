"""O setor da manifestação aponta para o cadastro por id (issue #1983, ADR 0095
decisão 2).

O Núcleo de Segurança do Paciente conta por setor do Admin, e a Ouvidoria só
guardava o nome. A manifestação ganha `setor_id` (migration 172), preenchido
pelo nome nos casos antigos, e toda porta que grava o `setor` passa a gravar o
id junto. O texto continua como está.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_ana_ouvidoria_protocolos import CHAVE_CORRETA, _BancoOuvidoriaFake, _make_app, _payload_valido  # noqa: E402
from test_ouvidoria_aba_avaliacoes import OUVIDOR as OUVIDOR_DAS_AVALIACOES  # noqa: E402
from test_ouvidoria_aba_avaliacoes import _cliente as _client_avaliacoes  # noqa: E402
from test_ouvidoria_aba_avaliacoes import _uma_marcada  # noqa: E402
from test_ouvidoria_formulario_publico import CARTAZ, _BancoFake, _payload  # noqa: E402
from test_ouvidoria_formulario_publico import _make_app as _make_app_publico  # noqa: E402
from test_ouvidoria_registro_manual import REGISTRO  # noqa: E402
from test_ouvidoria_registro_manual import _client as _client_registro  # noqa: E402
from test_ouvidoria_validacao_acionamento import OUVIDOR  # noqa: E402

from app.config import settings  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.services import ouvidoria_agente_triagem, ouvidoria_notificacoes  # noqa: E402
from app.services.ouvidoria_taxonomia import SETOR_PENDENTE  # noqa: E402

TAXONOMIA = [
    {"id": "s1", "nome": "Recepção", "ativo": True},
    {"id": "s2", "nome": "Farmácia", "ativo": True},
]


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _nunca_envia_email_de_verdade(monkeypatch):
    """O pytest do backend carrega o .env real (Resend de produção)."""
    monkeypatch.setattr(ouvidoria_notificacoes, "_enviar_email", lambda *_a, **_kw: True)


@pytest.fixture(autouse=True)
def _sem_agente(monkeypatch):
    """O agente de triagem não sai para a internet daqui."""
    monkeypatch.setattr(ouvidoria_agente_triagem, "agendar_caso", lambda *_a, **_kw: None)


# ─── Critério 3: toda porta grava o id junto com o texto ─────────────────────


class TestRegistroManual:
    def test_o_registro_manual_grava_o_id_do_setor_escolhido(self, monkeypatch):
        client, supabase = _client_registro(monkeypatch, OUVIDOR)
        supabase.tabelas["setores"] = [dict(s) for s in TAXONOMIA]

        r = client.post("/api/ouvidoria/manifestacoes", json={**REGISTRO, "setor": "farmacia"})

        assert r.status_code == 201, r.text
        [caso] = supabase.tabelas["ouvidoria_protocolos"]
        assert (caso["setor"], caso["setor_id"]) == ("Farmácia", "s2")


class TestAna:
    def _registrar(self, monkeypatch, setor: str) -> dict:
        monkeypatch.setattr(settings, "ana_api_key", CHAVE_CORRETA)
        banco = _BancoOuvidoriaFake()
        r = _make_app(banco).post(
            "/api/ana/ouvidoria/protocolos", json=_payload_valido(setor=setor), headers={"X-API-Key": CHAVE_CORRETA}
        )
        assert r.status_code == 201, r.text
        return banco.rows[0]

    def test_a_area_que_a_ana_escreveu_entra_com_o_id_do_cadastro(self, monkeypatch):
        caso = self._registrar(monkeypatch, "enfermagem")

        assert (caso["setor"], caso["setor_id"]) == ("Enfermagem", "id-enfermagem")

    def test_a_area_que_nao_casa_entra_pendente_e_sem_id(self, monkeypatch):
        caso = self._registrar(monkeypatch, "Setor que a IA inventou")

        assert (caso["setor"], caso["setor_id"]) == (SETOR_PENDENTE, None)


class TestCanalAberto:
    def test_o_cartaz_lido_nao_vira_o_id_da_area(self):
        """O setor do cartaz é de onde a pessoa leu, não contra quem ela
        reclama: o caso entra pendente, e o id junto fica vazio."""
        client, banco = _make_app_publico(_BancoFake(setores=["Recepção"], pontos=[dict(CARTAZ)]))

        r = client.post("/api/ouvidoria/publico/manifestacoes", json=_payload(p=CARTAZ["codigo"]))

        assert r.status_code == 201, r.text
        caso = banco.inserts[0]
        assert (caso["setor"], caso["setor_id"]) == (SETOR_PENDENTE, None)


class TestConversaoDeAvaliacao:
    def test_o_caso_da_avaliacao_entra_pendente_e_sem_id(self, monkeypatch):
        banco = _uma_marcada()
        client = _client_avaliacoes(monkeypatch, OUVIDOR_DAS_AVALIACOES, banco)

        r = client.post("/api/ouvidoria/avaliacoes/av-1/conversao")

        assert r.status_code == 201, r.text
        [caso] = banco.casos
        assert (caso["setor"], caso["setor_id"]) == (SETOR_PENDENTE, None)
