"""A Recomendação do Comitê, a decisão da medida e o retorno do Canal de
Conduta (issue #1835; especificação, 6.8, 6.9 e 6.10; ADR 0097).

Cada classe é um critério de aceite da issue. O banco e o Storage são os
dublês de `conduta_apoio`, a cifra é de verdade, e o modelo é um dublê que
guarda o que recebeu e devolve o texto pedido.
"""

from __future__ import annotations

import base64
import json
import re
import secrets
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_conduta_voto import (
    BASE,
    COORDENACAO,
    HOJE,
    LEITOR,
    MEMBRO,
    NOMES,
    Comite,
    Modelo,
)

from app.config import settings
from app.routers import conduta_depoimentos, conduta_direcao, conduta_retorno
from app.services.conduta import assinaturas, cifra, retorno
from app.services.conhecimento import CONHECIMENTO_DIR

PRESIDENTE, DIRETORIA, CADASTRO = "PRES", "DIREX", "CADM"
DIRECAO = f"{BASE}/direcao"
RELATORIO = "Rogério Valente, supervisor, ameaçou cortar as horas da equipe. Duas testemunhas confirmam."
PDF_DA_ATA = b"%PDF-ata-assinada"


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")


def _pessoa(pid: str, nome: str, perfil: str | None) -> dict[str, Any]:
    return {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": nome,
        "email": f"{pid.lower()}@hsm.test",
        "role": None,
        "ativo": True,
        "is_super_admin": pid == CADASTRO,
        "access_profile": None,
        "perfil_conduta": perfil,
    }


class ComiteEDirecao(Comite):
    """O Comitê dos testes do voto, o Presidente, a diretoria executiva e um
    super admin com o perfil de cadastro."""

    def __init__(self):
        super().__init__()
        self.banco.tabelas["participantes"] += [
            _pessoa(PRESIDENTE, "Paulo Presidente", "presidente"),
            _pessoa(DIRETORIA, "Diana Diretora", "diretoria_executiva"),
            _pessoa(CADASTRO, "Sara Super", "cadastro_de_membros"),
        ]

    def cliente(self, pid: str) -> TestClient:
        cliente = super().cliente(pid)
        for router in (conduta_direcao, conduta_retorno, conduta_depoimentos):
            cliente.app.include_router(router.router, prefix="/api")
        return cliente

    def concluido(self, resultado: str = "procedente", medida: str | None = "advertencia_escrita") -> str:
        """Um caso com a votação concluída e a ata assinada pelos três."""
        caso = self.caso()
        self.linha_do_caso(caso).update(
            {
                "etapa": "ata",
                "resultado": resultado,
                "medida_cifrada": cifra.cifrar_texto(json.dumps({"medida": medida, "dias_de_suspensao": None}))
                if medida
                else None,
                "votacao_concluida_em": "2026-11-15T12:00:00+00:00",
                "votacao_concluida_por": COORDENACAO,
            }
        )
        self.banco.tabelas.setdefault("conduta_relatorios", []).append(
            {
                "id": f"rel-{caso}",
                "caso_id": caso,
                "tipo": "relatorio",
                "versao": 1,
                "texto_cifrado": cifra.cifrar_texto(RELATORIO),
                "origem": "agente",
                "autor_id": COORDENACAO,
                "criado_em": "2026-11-10T12:00:00+00:00",
            }
        )
        for pid in (COORDENACAO, MEMBRO, LEITOR):
            self.banco.tabelas.setdefault("conduta_votos", []).append(
                {
                    "id": f"voto-{caso}-{pid}",
                    "caso_id": caso,
                    "rodada": 1,
                    "participante_id": pid,
                    "voto_cifrado": cifra.cifrar_texto(
                        json.dumps({"resultado": resultado, "medida": medida, "justificativa": "Voto secreto."})
                    ),
                    "votado_em": "2026-11-14T12:00:00+00:00",
                }
            )
        self.banco.tabelas.setdefault("conduta_atas", []).append(
            {
                "id": f"ata-{caso}",
                "caso_id": caso,
                "versao": 1,
                "rodada": 1,
                "votantes": sorted((COORDENACAO, MEMBRO, LEITOR)),
                "ata_cifrada": cifra.cifrar_texto(json.dumps({"resumo": "Resumo da ata."})),
                "criado_em": "2026-11-14T13:00:00+00:00",
            }
        )
        caminho = f"assinados/ata-{caso}"
        self.banco.storage.objetos[(assinaturas.BUCKET, caminho)] = cifra.cifrar_arquivo(PDF_DA_ATA)
        self.banco.tabelas.setdefault("conduta_assinaturas", []).append(
            {
                "id": f"assinatura-{caso}",
                "tipo": "ata_de_deliberacao",
                "caso_id": caso,
                "ata_id": f"ata-{caso}",
                "signatarios": [COORDENACAO, MEMBRO, LEITOR],
                "situacao": "assinado",
                "arquivo_assinado_path": caminho,
                "created_at": "2026-11-14T14:00:00+00:00",
            }
        )
        return caso

    def enviado(self, resultado: str = "procedente") -> str:
        caso = self.concluido(resultado)
        resposta = self.post(COORDENACAO, f"/casos/{caso}/direcao")
        assert resposta.status_code == 200, resposta.text
        return caso

    def direcao_get(self, pid: str, caminho: str):
        return self.cliente(pid).get(f"{DIRECAO}{caminho}")

    def direcao_post(self, pid: str, caminho: str, json: dict | None = None):
        return self.cliente(pid).post(f"{DIRECAO}{caminho}", json=json or {})

    def decidir(self, caso: str, decisao: str = "aplicada", justificativa: str = "", pid: str = DIRETORIA):
        return self.direcao_post(
            pid,
            f"/recomendacoes/{caso}/decisao",
            {"decisao": decisao, "justificativa": justificativa, "decidida_em": HOJE.isoformat()},
        )

    def trilha(self, caso: str) -> list[dict]:
        return [t for t in self.banco.tabelas.get("conduta_trilha", []) if t["caso_id"] == caso]


@pytest.fixture
def comite() -> ComiteEDirecao:
    return ComiteEDirecao()


# ═══════════════════════════════════════════════════════════════════════════
# ENVIAR À DIREÇÃO libera a Recomendação do Comitê
# ═══════════════════════════════════════════════════════════════════════════


class TestEnviarADirecao:
    def test_a_coordenacao_envia_e_o_caso_vai_a_etapa_medida(self, comite):
        caso = comite.concluido()

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/direcao")

        assert resposta.status_code == 200, resposta.text
        assert comite.linha_do_caso(caso)["etapa"] == "medida"
        assert [t["acao"] for t in comite.trilha(caso)][-1] == "enviou_a_direcao"

    def test_so_a_coordenacao_envia(self, comite):
        caso = comite.concluido()

        assert comite.post(MEMBRO, f"/casos/{caso}/direcao").status_code == 403
        assert comite.linha_do_caso(caso)["etapa"] == "ata"

    def test_a_caixa_da_etapa_ata_pede_o_envio_so_no_procedente(self, comite):
        procedente = comite.concluido()
        improcedente = comite.concluido("improcedente", medida=None)

        assert comite.abrir(COORDENACAO, procedente)["o_que_fazer_agora"]["botao"] == "ENVIAR À DIREÇÃO"
        assert comite.abrir(COORDENACAO, improcedente)["o_que_fazer_agora"]["botao"] == "GERAR RETORNO"

    def test_antes_do_envio_a_direcao_nao_le(self, comite):
        caso = comite.concluido()

        assert comite.direcao_get(PRESIDENTE, f"/recomendacoes/{caso}").status_code == 403
        assert comite.direcao_get(PRESIDENTE, "/recomendacoes").json()["recomendacoes"] == []


# ═══════════════════════════════════════════════════════════════════════════
# O Presidente lê a página de conclusão e a ata, não registra nada, e cada
# leitura entra na trilha
# ═══════════════════════════════════════════════════════════════════════════


class TestPresidenteSoLe:
    def test_o_presidente_le_a_pagina_de_conclusao(self, comite):
        caso = comite.enviado()

        resposta = comite.direcao_get(PRESIDENTE, f"/recomendacoes/{caso}")

        assert resposta.status_code == 200, resposta.text
        pagina = resposta.json()
        assert pagina["resultado"] == "Procedente"
        assert pagina["medida_recomendada"] == "Advertência escrita"
        assert pagina["relatorio"] == RELATORIO
        assert pagina["pode_registrar"] is False

    def test_o_presidente_abre_a_ata_assinada(self, comite):
        caso = comite.enviado()

        resposta = comite.direcao_get(PRESIDENTE, f"/recomendacoes/{caso}/ata")

        assert resposta.status_code == 200
        assert resposta.content == PDF_DA_ATA

    def test_cada_leitura_do_presidente_entra_na_trilha(self, comite):
        caso = comite.enviado()
        antes = len(comite.trilha(caso))

        comite.direcao_get(PRESIDENTE, f"/recomendacoes/{caso}")
        comite.direcao_get(PRESIDENTE, f"/recomendacoes/{caso}")
        comite.direcao_get(PRESIDENTE, f"/recomendacoes/{caso}/ata")

        novas = comite.trilha(caso)[antes:]
        assert [(t["autor_id"], t["acao"]) for t in novas] == [(PRESIDENTE, "leitura")] * 3
        assert "ata assinada" in novas[-1]["detalhe"]

    def test_o_presidente_nao_registra_a_decisao(self, comite):
        caso = comite.enviado()

        resposta = comite.decidir(caso, pid=PRESIDENTE)

        assert resposta.status_code == 403
        assert comite.banco.tabelas.get("conduta_decisoes_da_medida", []) == []

    def test_o_presidente_ve_o_caso_na_lista_das_recomendacoes(self, comite):
        caso = comite.enviado()

        (item,) = comite.direcao_get(PRESIDENTE, "/recomendacoes").json()["recomendacoes"]

        assert item["id"] == caso
        assert item["decisao"] is None

    def test_quem_nao_e_da_direcao_nao_le_a_recomendacao(self, comite):
        caso = comite.enviado()

        for pid in (CADASTRO, MEMBRO):
            assert comite.direcao_get(pid, f"/recomendacoes/{caso}").status_code == 403
            assert comite.direcao_get(pid, "/recomendacoes").status_code == 403

    def test_o_presidente_citado_no_caso_nao_le(self, comite):
        caso = comite.enviado()
        comite.banco.tabelas.setdefault("conduta_citados", []).append(
            {"id": "cit-pres", "caso_id": caso, "participante_id": PRESIDENTE}
        )

        assert comite.direcao_get(PRESIDENTE, f"/recomendacoes/{caso}").status_code == 403
        assert comite.direcao_get(PRESIDENTE, "/recomendacoes").json()["recomendacoes"] == []


# ═══════════════════════════════════════════════════════════════════════════
# A diretoria executiva registra a decisão, e "com ajuste" e "não aplicada"
# exigem justificativa
# ═══════════════════════════════════════════════════════════════════════════


class TestDiretoriaRegistraADecisao:
    def test_a_diretoria_registra_a_decisao_aplicada_com_a_data(self, comite):
        caso = comite.enviado()

        resposta = comite.decidir(caso, "aplicada")

        assert resposta.status_code == 200, resposta.text
        (decisao,) = comite.banco.tabelas["conduta_decisoes_da_medida"]
        assert decisao["decisao"] == "aplicada"
        assert decisao["decidida_em"] == HOJE.isoformat()
        assert decisao["registrada_por"] == DIRETORIA
        assert comite.linha_do_caso(caso)["etapa"] == "retorno"
        pagina = comite.direcao_get(PRESIDENTE, f"/recomendacoes/{caso}").json()
        assert pagina["decisao"]["decisao"] == "Aplicada"

    @pytest.mark.parametrize("decisao", ["aplicada_com_ajuste", "nao_aplicada"])
    def test_com_ajuste_e_nao_aplicada_exigem_justificativa(self, comite, decisao):
        caso = comite.enviado()

        sem = comite.decidir(caso, decisao, "   ")

        assert sem.status_code == 422
        assert "justificativa" in sem.json()["detail"].lower()
        assert comite.banco.tabelas.get("conduta_decisoes_da_medida", []) == []
        com = comite.decidir(caso, decisao, "A suspensão virou advertência pelo histórico.")
        assert com.status_code == 200, com.text
        (linha,) = comite.banco.tabelas["conduta_decisoes_da_medida"]
        assert cifra.decifrar_texto(linha["justificativa_cifrada"]) == "A suspensão virou advertência pelo histórico."

    def test_a_decisao_nao_se_registra_duas_vezes(self, comite):
        caso = comite.enviado()
        assert comite.decidir(caso).status_code == 200

        assert comite.decidir(caso, "nao_aplicada", "Mudou de ideia.").status_code == 409

    def test_a_decisao_entra_na_trilha(self, comite):
        caso = comite.enviado()

        comite.decidir(caso, "aplicada")

        assert ("registrou_decisao_da_medida", DIRETORIA) in [(t["acao"], t["autor_id"]) for t in comite.trilha(caso)]

    def test_a_diretoria_anexa_a_copia_da_comunicacao_da_medida_a_trilha(self, comite):
        caso = comite.enviado()
        comite.decidir(caso, "aplicada")

        resposta = comite.cliente(DIRETORIA).post(
            f"{DIRECAO}/recomendacoes/{caso}/comunicacao",
            files={"arquivo": ("comunicacao.pdf", b"%PDF-comunicacao", "application/pdf")},
        )

        assert resposta.status_code == 200, resposta.text
        assert "anexou_arquivo" in [t["acao"] for t in comite.trilha(caso)]
        aberta = comite.cliente(COORDENACAO).get(f"{BASE}/casos/{caso}/medida/comunicacao")
        assert aberta.content == b"%PDF-comunicacao"

    def test_o_comite_ve_a_decisao_na_tela_do_caso(self, comite):
        caso = comite.enviado()
        comite.decidir(caso, "nao_aplicada", "Sem histórico.")

        tela = comite.abrir(COORDENACAO, caso)["medida_e_retorno"]

        assert tela["decisao"]["decisao"] == "Não aplicada"
        assert tela["decisao"]["justificativa"] == "Sem histórico."


# ═══════════════════════════════════════════════════════════════════════════
# Presidente e diretoria executiva recebem 403 no relato, nos depoimentos, nos
# votos individuais e no Dossiê do caso
# ═══════════════════════════════════════════════════════════════════════════


class TestDirecaoNaoAbreOCaso:
    @pytest.mark.parametrize("pid", [PRESIDENTE, DIRETORIA])
    @pytest.mark.parametrize(
        "caminho",
        [
            "/casos/{caso}",  # o relato e os votos da tela do caso
            "/casos/{caso}/depoimentos/00000000-0000-4000-8000-000000000002/termo/pdf",  # o termo de um depoimento
            "/casos/{caso}/depoimentos/00000000-0000-4000-8000-000000000002/arquivos/00000000-0000-4000-8000-000000000001",
            "/casos/{caso}/trava/ciencia",
        ],
    )
    def test_a_direcao_recebe_403_no_conteudo_do_caso(self, comite, pid, caminho):
        caso = comite.enviado()

        resposta = comite.cliente(pid).get(f"{BASE}{caminho.format(caso=caso)}")

        assert resposta.status_code == 403

    @pytest.mark.parametrize("pid", [PRESIDENTE, DIRETORIA])
    def test_a_pagina_de_conclusao_nao_leva_relato_votos_nem_depoimentos(self, comite, pid):
        caso = comite.enviado()

        texto = comite.direcao_get(pid, f"/recomendacoes/{caso}").text

        assert "ameaçou cortar as horas da equipe do almoxarifado" not in texto  # o relato
        assert "Voto secreto." not in texto  # a justificativa de um voto
        assert "nega a ameaça" not in texto  # o depoimento do acusado

    @pytest.mark.parametrize("pid", [PRESIDENTE, DIRETORIA])
    def test_a_direcao_nao_entra_na_lista_do_comite(self, comite, pid):
        comite.enviado()

        assert comite.cliente(pid).get(f"{BASE}/casos").status_code == 403


RESPOSTA = "O Comitê concluiu a apuração do seu relato. Obrigado por relatar. Retaliação é proibida."
COMUNICACAO = "O Comitê apurou os fatos de outubro sobre [PESSOA_1] e concluiu o caso."
_ACUSADO_NA_IDA = re.compile(r"O acusado é (\[PESSOA_\d+\])")


def _do_agente(resposta: str = RESPOSTA, comunicacao: str = COMUNICACAO) -> str:
    return json.dumps({"resposta_ao_denunciante": resposta, "comunicacao_ao_acusado": comunicacao})


class ModeloDoRetorno(Modelo):
    """Escreve `[PESSOA_1]` do molde com o marcador que o acusado recebeu, e
    `[OUTRO]` com o primeiro marcador que não é o dele, como o agente de
    verdade faria."""

    molde = _do_agente()

    def _create(self, **kwargs):
        mensagem = kwargs["messages"][0]["content"]
        achado = _ACUSADO_NA_IDA.search(mensagem)
        acusado = achado.group(1) if achado else "[PESSOA_1]"
        outros = [m for m in re.findall(r"\[PESSOA_\d+\]", mensagem) if m != acusado]
        self.texto = self.molde.replace("[PESSOA_1]", acusado).replace("[OUTRO]", outros[0] if outros else "")
        return super()._create(**kwargs)


@pytest.fixture
def modelo(monkeypatch) -> ModeloDoRetorno:
    falso = ModeloDoRetorno()
    monkeypatch.setattr(retorno, "_cliente_do_agente_do_retorno", lambda: falso)
    monkeypatch.setattr(retorno, "_cliente_do_agente_da_correcao", lambda: falso)
    return falso


def _no_retorno(comite: ComiteEDirecao, resultado: str = "procedente") -> str:
    """Um caso procedente com a decisão registrada, ou um sem medida na Ata."""
    if resultado in ("improcedente", "inconclusivo"):
        return comite.concluido(resultado, medida=None)
    caso = comite.enviado(resultado)
    assert comite.decidir(caso).status_code == 200
    return caso


def _correcao(comite, caso: str, pid: str = MEMBRO, **trocas):
    corpo = {
        "texto": "Revisar a escala do almoxarifado.",
        "responsavel": "Gerência de Logística",
        "prazo_em": (HOJE + timedelta(days=30)).isoformat(),
        **trocas,
    }
    return comite.post(pid, f"/casos/{caso}/correcoes", corpo)


def _retorno_na_tela(comite, caso: str, pid: str = COORDENACAO) -> dict:
    return comite.abrir(pid, caso)["medida_e_retorno"]["retorno"]


def _editar(comite, caso: str, denunciante: str = RESPOSTA, acusado: str = "O caso foi encerrado."):
    return comite.post(COORDENACAO, f"/casos/{caso}/retorno/versoes", {"denunciante": denunciante, "acusado": acusado})


# ═══════════════════════════════════════════════════════════════════════════
# A resposta ao denunciante e a comunicação ao acusado só saem depois da
# aprovação da coordenação
# ═══════════════════════════════════════════════════════════════════════════


class TestRetornoSoSaiAprovado:
    def test_o_agente_redige_o_retorno_no_clique_da_coordenacao(self, comite, modelo):
        caso = _no_retorno(comite)

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/retorno")

        assert resposta.status_code == 200, resposta.text
        (versao,) = _retorno_na_tela(comite, caso)["versoes"]
        assert versao["denunciante"] == RESPOSTA
        assert versao["acusado"] == "O Comitê apurou os fatos de outubro sobre Rogério Valente e concluiu o caso."
        assert "Rogério" not in modelo.tudo_que_saiu()

    def test_sem_o_clique_o_agente_nao_roda(self, comite, modelo):
        caso = _no_retorno(comite)
        comite.abrir(COORDENACAO, caso)

        assert modelo.pedidos == []

    def test_antes_da_aprovacao_nada_sai(self, comite, modelo):
        caso = _no_retorno(comite)
        comite.post(COORDENACAO, f"/casos/{caso}/retorno")

        assert retorno.resposta_ao_denunciante(comite.banco, comite.linha_do_caso(caso)) is None
        comunicacao = comite.cliente(COORDENACAO).get(f"{BASE}/casos/{caso}/retorno/comunicacao-ao-acusado")
        assert comunicacao.status_code == 409

    def test_aprovado_a_resposta_vai_ao_acompanhamento_e_a_comunicacao_abre(self, comite, modelo):
        caso = _no_retorno(comite)
        comite.post(COORDENACAO, f"/casos/{caso}/retorno")
        assert _correcao(comite, caso).status_code == 200

        aprovacao = comite.post(COORDENACAO, f"/casos/{caso}/retorno/aprovacao")

        assert aprovacao.status_code == 200, aprovacao.text
        assert retorno.resposta_ao_denunciante(comite.banco, comite.linha_do_caso(caso)) == RESPOSTA
        comunicacao = comite.cliente(COORDENACAO).get(f"{BASE}/casos/{caso}/retorno/comunicacao-ao-acusado")
        assert comunicacao.json()["texto"].startswith("O Comitê apurou os fatos de outubro sobre Rogério Valente")
        linha = comite.linha_do_caso(caso)
        assert linha["encerrado_em"] and linha["desfecho"] == "concluido"
        assert "aprovou_retorno" in [t["acao"] for t in comite.trilha(caso)]

    def test_so_a_coordenacao_aprova(self, comite, modelo):
        caso = _no_retorno(comite)
        comite.post(COORDENACAO, f"/casos/{caso}/retorno")
        _correcao(comite, caso)

        assert comite.post(MEMBRO, f"/casos/{caso}/retorno/aprovacao").status_code == 403
        assert retorno.resposta_ao_denunciante(comite.banco, comite.linha_do_caso(caso)) is None

    def test_a_edicao_da_coordenacao_e_versao_nova_e_e_a_que_sai(self, comite, modelo):
        caso = _no_retorno(comite, "improcedente")
        comite.post(COORDENACAO, f"/casos/{caso}/retorno")

        editada = _editar(comite, caso, "Seu relato foi apurado e o caso foi encerrado.")
        comite.post(COORDENACAO, f"/casos/{caso}/retorno/aprovacao")

        assert editada.status_code == 200, editada.text
        assert [v["versao"] for v in _retorno_na_tela(comite, caso)["versoes"]] == [2, 1]
        assert retorno.resposta_ao_denunciante(comite.banco, comite.linha_do_caso(caso)) == (
            "Seu relato foi apurado e o caso foi encerrado."
        )

    def test_no_procedente_o_retorno_espera_a_decisao_da_direcao(self, comite, modelo):
        caso = comite.enviado()

        assert comite.post(COORDENACAO, f"/casos/{caso}/retorno").status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# A resposta ao denunciante não cita medida nem nome, e a comunicação ao
# acusado não cita quem relatou
# ═══════════════════════════════════════════════════════════════════════════


def _denunciante_ouvido(comite, caso: str, nome: str = "Marta Relatora") -> None:
    comite.banco.tabelas.setdefault("conduta_depoimentos", []).append(
        {
            "id": f"dep-den-{caso}",
            "caso_id": caso,
            "nome_cifrado": cifra.cifrar_texto(nome),
            "cargo_cifrado": cifra.cifrar_texto("Auxiliar"),
            "papel": "denunciante",
            "criado_em": "2026-11-09T11:00:00+00:00",
        }
    )


class TestOQueORetornoNaoCita:
    @pytest.mark.parametrize(
        "resposta",
        [
            "O Comitê concluiu o caso e aplicou advertência escrita.",
            "O caso terminou em suspensão.",
            "A medida foi decidida pela Direção.",
        ],
    )
    def test_a_resposta_que_cita_a_medida_e_recusada(self, comite, resposta):
        caso = _no_retorno(comite)

        editada = _editar(comite, caso, resposta)

        assert editada.status_code == 422
        assert "medida" in editada.json()["detail"]

    @pytest.mark.parametrize(
        "resposta", ["Rogério Valente foi ouvido e o caso concluiu.", "O supervisor Valente foi ouvido."]
    )
    def test_a_resposta_que_cita_nome_e_recusada(self, comite, resposta):
        caso = _no_retorno(comite)

        editada = _editar(comite, caso, resposta)

        assert editada.status_code == 422
        assert "nome" in editada.json()["detail"]

    def test_a_comunicacao_que_cita_quem_relatou_e_recusada(self, comite):
        caso = _no_retorno(comite)
        _denunciante_ouvido(comite, caso)

        editada = _editar(comite, caso, acusado="O relato de Marta foi apurado e o caso concluiu.")

        assert editada.status_code == 422
        assert "quem relatou" in editada.json()["detail"]

    @pytest.mark.parametrize("quem_relatou", ["Maria Valente", "Rogério Valente Souza"])
    def test_o_nome_do_acusado_passa_mesmo_com_palavra_em_comum_com_quem_relatou(self, comite, modelo, quem_relatou):
        """O sobrenome ou prenome que os dois dividem é do acusado também: a
        comunicação com o nome dele grava, a do agente e a editada."""
        caso = _no_retorno(comite, "improcedente")
        _denunciante_ouvido(comite, caso, quem_relatou)

        assert comite.post(COORDENACAO, f"/casos/{caso}/retorno").status_code == 200
        editada = _editar(comite, caso, acusado="Prezado Rogério Valente, o caso concluiu.")
        assert editada.status_code == 200
        assert comite.post(COORDENACAO, f"/casos/{caso}/retorno/aprovacao").status_code == 200

    def test_a_palavra_so_de_quem_relatou_continua_recusada(self, comite):
        caso = _no_retorno(comite)
        _denunciante_ouvido(comite, caso, "Maria Valente")

        editada = _editar(comite, caso, acusado="Rogério Valente, o relato de Maria foi apurado.")

        assert editada.status_code == 422
        assert "quem relatou" in editada.json()["detail"]

    def test_o_agente_que_escreve_a_medida_nao_grava_versao(self, comite, modelo):
        caso = _no_retorno(comite)
        modelo.molde = _do_agente(resposta="O caso concluiu com suspensão de cinco dias.")

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/retorno")

        assert resposta.status_code == 502
        assert comite.banco.tabelas.get("conduta_retornos", []) == []

    def test_na_comunicacao_so_o_nome_do_acusado_volta(self, comite, modelo):
        """O agente cita quem relatou pelo marcador: na volta ele vira "uma
        pessoa", e o nome nem vai nem volta."""
        caso = _no_retorno(comite)
        _denunciante_ouvido(comite, caso)
        relatorio = next(r for r in comite.banco.tabelas["conduta_relatorios"] if r["caso_id"] == caso)
        relatorio["texto_cifrado"] = cifra.cifrar_texto("Marta Relatora contou que Rogério Valente ameaçou a equipe.")
        modelo.molde = _do_agente(comunicacao="[OUTRO] relatou os fatos sobre [PESSOA_1].")

        assert comite.post(COORDENACAO, f"/casos/{caso}/retorno").status_code == 200
        (versao,) = _retorno_na_tela(comite, caso)["versoes"]
        assert versao["acusado"] == "uma pessoa relatou os fatos sobre Rogério Valente."
        assert "Marta" not in modelo.tudo_que_saiu()


# ═══════════════════════════════════════════════════════════════════════════
# Caso improcedente ou inconclusivo não aparece para ninguém fora do Comitê
# ═══════════════════════════════════════════════════════════════════════════


class TestImprocedenteFicaNoComite:
    @pytest.mark.parametrize("resultado", ["improcedente", "inconclusivo"])
    def test_o_caso_sem_medida_nao_vai_a_direcao(self, comite, resultado):
        caso = comite.concluido(resultado, medida=None)

        resposta = comite.post(COORDENACAO, f"/casos/{caso}/direcao")

        assert resposta.status_code == 409
        assert comite.linha_do_caso(caso).get("enviado_a_direcao_em") is None

    @pytest.mark.parametrize("resultado", ["improcedente", "inconclusivo"])
    @pytest.mark.parametrize("pid", [PRESIDENTE, DIRETORIA])
    def test_mesmo_marcado_como_enviado_a_direcao_nao_le(self, comite, resultado, pid):
        """O portão da Direção confere o resultado por conta própria."""
        caso = comite.concluido(resultado, medida=None)
        comite.linha_do_caso(caso)["enviado_a_direcao_em"] = "2026-11-16T12:00:00+00:00"

        assert comite.direcao_get(pid, f"/recomendacoes/{caso}").status_code == 403
        assert comite.direcao_get(pid, f"/recomendacoes/{caso}/ata").status_code == 403
        assert comite.direcao_get(pid, "/recomendacoes").json()["recomendacoes"] == []

    def test_o_improcedente_vai_da_ata_ao_retorno(self, comite, modelo):
        caso = _no_retorno(comite, "improcedente")

        assert comite.post(COORDENACAO, f"/casos/{caso}/retorno").status_code == 200
        assert comite.post(COORDENACAO, f"/casos/{caso}/retorno/aprovacao").status_code == 200
        assert comite.linha_do_caso(caso)["desfecho"] == "concluido"


# ═══════════════════════════════════════════════════════════════════════════
# A correção de processo escolhida fica com responsável e prazo
# ═══════════════════════════════════════════════════════════════════════════


class TestCorrecaoDeProcesso:
    def test_o_agente_sugere_de_uma_a_tres_correcoes(self, comite, modelo):
        caso = _no_retorno(comite)
        modelo.molde = json.dumps(
            {"correcoes": ["Revisar a escala.", "Treinar a chefia.", "Criar rodízio.", "Uma quarta."]}
        )

        resposta = comite.post(MEMBRO, f"/casos/{caso}/correcoes/sugestao")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["correcoes"] == ["Revisar a escala.", "Treinar a chefia.", "Criar rodízio."]
        tela = comite.abrir(MEMBRO, caso)["medida_e_retorno"]["correcoes"]
        assert tela["sugeridas"] == ["Revisar a escala.", "Treinar a chefia.", "Criar rodízio."]

    def test_a_correcao_escolhida_fica_com_responsavel_e_prazo(self, comite):
        caso = _no_retorno(comite)
        prazo = (HOJE + timedelta(days=45)).isoformat()

        resposta = _correcao(comite, caso, prazo_em=prazo)

        assert resposta.status_code == 200, resposta.text
        (escolhida,) = comite.abrir(COORDENACAO, caso)["medida_e_retorno"]["correcoes"]["escolhidas"]
        assert escolhida["texto"] == "Revisar a escala do almoxarifado."
        assert escolhida["responsavel"] == "Gerência de Logística"
        assert escolhida["prazo_em"] == prazo
        assert escolhida["escolhida_por"] == NOMES[MEMBRO]
        assert "escolheu_correcao" in [t["acao"] for t in comite.trilha(caso)]

    @pytest.mark.parametrize(
        ("trocas", "trecho"),
        [({"responsavel": "  "}, "responsável"), ({"prazo_em": (HOJE - timedelta(days=1)).isoformat()}, "prazo")],
    )
    def test_sem_responsavel_ou_com_prazo_vencido_e_recusada(self, comite, trocas, trecho):
        caso = _no_retorno(comite)

        resposta = _correcao(comite, caso, **trocas)

        assert resposta.status_code == 422
        assert trecho in resposta.json()["detail"]
        assert comite.banco.tabelas.get("conduta_correcoes", []) == []

    def test_no_procedente_o_retorno_so_aprova_com_a_correcao_escolhida(self, comite, modelo):
        caso = _no_retorno(comite)
        comite.post(COORDENACAO, f"/casos/{caso}/retorno")

        sem = comite.post(COORDENACAO, f"/casos/{caso}/retorno/aprovacao")

        assert sem.status_code == 409
        assert "correção de processo" in sem.json()["detail"]
        _correcao(comite, caso)
        assert comite.post(COORDENACAO, f"/casos/{caso}/retorno/aprovacao").status_code == 200

    def test_o_caso_improcedente_nao_tem_correcao(self, comite):
        caso = _no_retorno(comite, "improcedente")

        assert _correcao(comite, caso).status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# O texto do Produto Canal de Conduta no kit de conhecimento diz o
# comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    @pytest.mark.parametrize(
        "trecho",
        [
            "ENVIAR À DIREÇÃO",
            "O Presidente só lê",
            "Aplicada com ajuste",
            "GERAR RETORNO",
            "não cita a medida nem nome",
            "não cita quem relatou",
            "Improcedente e inconclusivo não saem do Comitê",
            "responsável e prazo",
        ],
    )
    def test_o_kit_diz_o_comportamento_novo(self, trecho):
        assert trecho in (CONHECIMENTO_DIR / "canal-de-conduta.md").read_text(encoding="utf-8")
