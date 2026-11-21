"""O caso do Canal de Conduta gravado (issue #1820, ADR 0097, decisões 1 e 8).

Quem lê a tabela direto no banco vê o relato cifrado, o protocolo aleatório e o
código de acompanhamento só como hash. Sem a chave, nada é gravado.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
import sys

import pytest
from conduta_apoio import Banco

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.services.conduta import casos, cifra  # noqa: E402
from app.services.ouvidoria_acompanhamento import codigo_confere  # noqa: E402

RELATO = "A chefe da farmácia humilhou o técnico na frente da equipe toda semana."


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())


class TestConteudoCifrado:
    def test_lendo_a_tabela_direto_o_relato_nao_aparece_em_claro(self):
        banco = Banco()
        casos.registrar_caso(banco, relato=RELATO, categoria="assedio_moral")

        (linha,) = banco.tabelas["conduta_casos"]
        tudo_que_o_banco_guarda = repr(banco.tabelas)
        assert "farmácia" not in tudo_que_o_banco_guarda
        assert "humilhou" not in tudo_que_o_banco_guarda
        assert cifra.decifrar_texto(linha["relato_cifrado"]) == RELATO

    def test_os_metadados_de_lista_e_prazo_ficam_em_claro(self):
        banco = Banco()
        casos.registrar_caso(banco, relato=RELATO, categoria="assedio_moral")

        (linha,) = banco.tabelas["conduta_casos"]
        assert linha["categoria"] == "assedio_moral"
        assert linha["rota"] == "comum"
        assert linha["etapa"] == "triagem"

    def test_sem_a_chave_nada_e_gravado(self, monkeypatch):
        monkeypatch.setattr(settings, "conduta_chave_cifra", "")
        banco = Banco()

        with pytest.raises(cifra.CifraIndisponivel):
            casos.registrar_caso(banco, relato=RELATO, categoria="assedio_moral")

        assert banco.tabelas.get("conduta_casos", []) == []
        assert banco.tabelas.get("conduta_trilha", []) == []

    def test_o_codigo_de_acompanhamento_fica_so_como_hash(self):
        banco = Banco()
        novo = casos.registrar_caso(banco, relato=RELATO, categoria="assedio_moral")

        (linha,) = banco.tabelas["conduta_casos"]
        assert novo["codigo"] not in repr(banco.tabelas)
        assert codigo_confere(novo["codigo"], linha["codigo_hash"])

    def test_o_recebimento_entra_na_trilha_sem_autor(self):
        banco = Banco()
        novo = casos.registrar_caso(banco, relato=RELATO, categoria="assedio_moral")

        (linha,) = banco.tabelas["conduta_trilha"]
        assert linha["caso_id"] == novo["id"]
        assert linha["autor_id"] is None
        assert linha["acao"] == "recebimento"


class TestProtocolo:
    def test_o_protocolo_tem_o_formato_do_canal(self):
        assert re.fullmatch(r"CC-[A-Z0-9]{4}-[A-Z0-9]{4}", casos.novo_protocolo())

    def test_o_protocolo_e_aleatorio_e_sem_sequencia(self):
        """Mutante: trocar o sorteio por um contador. Protocolos seguidos sairiam
        em ordem e contariam os casos."""
        protocolos = [casos.novo_protocolo() for _ in range(50)]

        assert len(set(protocolos)) == 50
        assert protocolos != sorted(protocolos)

    def test_o_caso_gravado_leva_o_protocolo_devolvido(self):
        banco = Banco()
        novo = casos.registrar_caso(banco, relato=RELATO, categoria="assedio_moral")

        assert banco.tabelas["conduta_casos"][0]["protocolo"] == novo["protocolo"]
        assert "numero" not in banco.tabelas["conduta_casos"][0]
