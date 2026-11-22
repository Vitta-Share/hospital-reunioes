"""A página de acompanhamento do Canal de Conduta e as Mensagens do caso
(issue #1845; especificação, P7 e 6.1).

Quem relatou entra com o protocolo e o código, vê a situação do caso em
linguagem simples e as mensagens do Comitê, e manda o complemento pela mesma
página. Do lado do Comitê, a coordenação pergunta, e o pedido sem resposta em
15 dias libera arquivar por falta de elementos; o caso arquivado reabre quando
a informação chega depois.

Tudo é exercitado pelas rotas (TestClient), com o limitador e o middleware de
log de produção. O banco é o dublê de `conduta_apoio`, e o texto é cifrado de
verdade, com uma chave gerada na hora.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import secrets
import sys
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.middleware.request_context import JsonFormatter, RequestContextMiddleware  # noqa: E402
from app.routers import conduta_acompanhamento, conduta_comite, conduta_mensagens, conduta_trilha  # noqa: E402
from app.services import ouvidoria_acompanhamento  # noqa: E402
from app.services.conduta import acompanhamento, casos, cifra  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402

ACOMPANHAR = "/api/conduta/acompanhamento"
COMPLEMENTO = "/api/conduta/acompanhamento/complemento"
IP_DE_QUEM_ACOMPANHA = "203.0.113.45"
APARELHO = "Mozilla/5.0 (Linux; Android 10; SM-A105M) Celular-de-Entrada/77"
RELATO = "O encarregado da manutenção ameaçou demitir quem reclamasse das horas extras."
PERGUNTA = "Em que dia e em que setor isso aconteceu?"
COMPLEMENTO_TEXTO = "Foi na oficina, numa terça de manhã, na frente de três técnicos."
RECUSA = {"detail": "Não encontramos um relato com esse protocolo e esse código. Confira os dois e tente de novo."}

HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}
COORDENACAO = "P1"
MEMBRO = "P2"
NOME_DA_COORDENACAO = "Marina Coordenadora Sigilosa"
NOME_DO_MEMBRO = "Otávio Membro Sigiloso"


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "conduta_canal_aberto", True)
    limiter._storage.reset()
    yield
    limiter._storage.reset()


def _pessoa(pid: str, nome: str) -> dict:
    return {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": nome,
        "email": f"{pid.lower()}@hsm.test",
        "role": None,
        "ativo": True,
        "is_super_admin": False,
        "access_profile": None,
    }


def _participacao(pid: str, papel: str) -> dict:
    return {
        "id": f"part-{pid}",
        "colegiado_id": COMITE["id"],
        "participante_id": pid,
        "papel": papel,
        "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=600)).isoformat(),
        "termo_assinado_em": "2026-10-01T12:00:00+00:00",
    }


class _Canal:
    """O banco, um caso recebido pela página pública e os dois lados: quem
    relatou, sem login, e o Comitê, logado."""

    def __init__(self):
        self.banco = Banco(
            {
                "participantes": [_pessoa(COORDENACAO, NOME_DA_COORDENACAO), _pessoa(MEMBRO, NOME_DO_MEMBRO)],
                "colegiados": [dict(COMITE)],
                "participacoes": [_participacao(COORDENACAO, "coordenacao"), _participacao(MEMBRO, "membro")],
            }
        )
        novo = casos.registrar_caso(self.banco, relato=RELATO, categoria="A")
        self.caso_id = novo["id"]
        self.protocolo = novo["protocolo"]
        self.codigo = novo["codigo"]

    @property
    def caso(self) -> dict:
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == self.caso_id)

    def mudar_caso(self, **campos) -> None:
        self.caso_mutavel().update(campos)

    def caso_mutavel(self) -> dict:
        return next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == self.caso_id)

    def publico(self, ip: str = IP_DE_QUEM_ACOMPANHA) -> TestClient:
        app = FastAPI()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(RequestContextMiddleware)
        app.include_router(conduta_acompanhamento.router, prefix="/api")
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app, client=(ip, 50123), raise_server_exceptions=False)

    def comite(self, pid: str = COORDENACAO) -> TestClient:
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(conduta_comite.router, prefix="/api")
        app.include_router(conduta_mensagens.router, prefix="/api")
        app.include_router(conduta_trilha.router, prefix="/api")

        async def _usuario() -> dict:
            return {"id": f"auth-{pid}", "email": f"{pid.lower()}@hsm.test", "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app, raise_server_exceptions=False)

    def acompanhar(self, protocolo: str | None = None, codigo: str | None = None, **kwargs):
        corpo = {"protocolo": protocolo or self.protocolo, "codigo": codigo or self.codigo}
        return self.publico(**kwargs).post(ACOMPANHAR, json=corpo, headers={"User-Agent": APARELHO})

    def complementar(self, texto: str = COMPLEMENTO_TEXTO):
        corpo = {"protocolo": self.protocolo, "codigo": self.codigo, "texto": texto}
        return self.publico().post(COMPLEMENTO, json=corpo, headers={"User-Agent": APARELHO})

    def perguntar(self, texto: str = PERGUNTA, pid: str = COORDENACAO):
        return self.comite(pid).post(f"/api/comite-de-conduta/casos/{self.caso_id}/mensagens", json={"texto": texto})

    def tela(self, pid: str = COORDENACAO) -> dict:
        resposta = self.comite(pid).get(f"/api/comite-de-conduta/casos/{self.caso_id}")
        assert resposta.status_code == 200, resposta.text
        return resposta.json()

    def recuar_mensagens(self, dias: int) -> None:
        """Faz as mensagens gravadas terem sido enviadas `dias` atrás."""
        for linha in self.banco.tabelas.get("conduta_mensagens", []):
            momento = datetime.fromisoformat(linha["enviada_em"]) - timedelta(days=dias)
            linha["enviada_em"] = momento.isoformat()


@pytest.fixture
def canal() -> _Canal:
    return _Canal()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Protocolo e código certos abrem; qualquer erro, a mesma resposta no mesmo tempo
# ═══════════════════════════════════════════════════════════════════════════


class TestEntrada:
    def test_protocolo_e_codigo_certos_abrem_a_situacao_e_as_mensagens(self, canal):
        resposta = canal.acompanhar()

        assert resposta.status_code == 200, resposta.text
        assert resposta.json() == {"protocolo": canal.protocolo, "situacao": "Recebido", "mensagens": []}

    def test_o_codigo_vale_com_minuscula_e_sem_o_hifen(self, canal):
        resposta = canal.acompanhar(protocolo=canal.protocolo.lower(), codigo=canal.codigo.replace("-", "").lower())

        assert resposta.status_code == 200

    @pytest.mark.parametrize("erro", ["codigo_errado", "protocolo_que_nao_existe", "protocolo_de_outro_caso"])
    def test_qualquer_erro_devolve_a_mesma_resposta(self, canal, erro):
        outro = casos.registrar_caso(canal.banco, relato=RELATO, categoria="A")
        protocolo, codigo = {
            "codigo_errado": (canal.protocolo, "ABCDE-23456"),
            "protocolo_que_nao_existe": ("CC-ZZZZ-9999", canal.codigo),
            "protocolo_de_outro_caso": (outro["protocolo"], canal.codigo),
        }[erro]

        resposta = canal.acompanhar(protocolo=protocolo, codigo=codigo)

        assert resposta.status_code == 404
        assert resposta.json() == RECUSA

    def test_envio_malformado_tambem_recebe_a_mesma_recusa(self, canal):
        resposta = canal.publico().post(ACOMPANHAR, json={"protocolo": canal.protocolo, "codigo": "x" * 500})

        assert resposta.status_code == 404
        assert resposta.json() == RECUSA
        assert "xxxx" not in resposta.text

    @pytest.mark.parametrize("erro", ["codigo_errado", "protocolo_que_nao_existe", "malformado"])
    def test_toda_recusa_gasta_uma_conferencia_lenta_como_o_acerto(self, canal, monkeypatch, erro):
        """O mesmo tempo: a recusa pelo protocolo que não existe faz a mesma
        derivação lenta do código que a recusa pelo código errado e que o
        acerto. Contar a derivação é o que não depende do relógio da máquina."""
        ouvidoria_acompanhamento._gastar_o_tempo_de_uma_conferencia("aquecer")
        derivacoes: list[int] = []
        original = ouvidoria_acompanhamento._derivar

        def _contar(codigo, sal, iteracoes):
            derivacoes.append(iteracoes)
            return original(codigo, sal, iteracoes)

        monkeypatch.setattr(ouvidoria_acompanhamento, "_derivar", _contar)
        protocolo, codigo = {
            "codigo_errado": (canal.protocolo, "ABCDE-23456"),
            "protocolo_que_nao_existe": ("CC-ZZZZ-9999", canal.codigo),
            "malformado": ("x" * 300, canal.codigo),
        }[erro]

        assert canal.acompanhar().status_code == 200
        acerto = list(derivacoes)
        derivacoes.clear()
        assert canal.acompanhar(protocolo=protocolo, codigo=codigo).status_code == 404

        assert acerto == [ouvidoria_acompanhamento._ITERACOES]
        assert derivacoes == acerto


# ═══════════════════════════════════════════════════════════════════════════
# 2. Nenhum dado interno: nome de membro, voto, medida nem etapa
# ═══════════════════════════════════════════════════════════════════════════

RESPOSTA_DO_RETORNO = "O Comitê apurou o seu relato e tomou as providências cabíveis. Obrigado por relatar."


class TestNadaInterno:
    def _caso_com_tudo_dentro(self, canal: _Canal, **campos) -> None:
        """Um caso que já passou pelo voto, com a medida decidida e o nome de
        cada membro no banco: tudo o que a página não pode mostrar."""
        assert canal.perguntar().status_code == 201
        canal.banco.tabelas["conduta_votos"] = [
            {
                "id": "v1",
                "caso_id": canal.caso_id,
                "rodada": 1,
                "participante_id": MEMBRO,
                "resultado": "procedente",
                "medida": "advertencia_escrita",
                "justificativa_cifrada": cifra.cifrar_texto("Voto do membro pela advertência escrita"),
            }
        ]
        canal.banco.tabelas["conduta_retornos"] = [
            {
                "id": "r1",
                "caso_id": canal.caso_id,
                "versao": 1,
                "denunciante_cifrado": cifra.cifrar_texto(RESPOSTA_DO_RETORNO),
                "acusado_cifrado": cifra.cifrar_texto("Comunicação da advertência escrita ao acusado"),
            }
        ]
        canal.mudar_caso(triagem_em="2026-11-02T12:00:00+00:00", rito="completo", resultado="procedente", **campos)

    @pytest.mark.parametrize("etapa", ["apuracao", "voto", "ata", "medida", "retorno"])
    def test_no_meio_do_rito_a_pagina_diz_so_em_apuracao(self, canal, etapa):
        self._caso_com_tudo_dentro(canal, etapa=etapa)
        canal.complementar()

        pagina = canal.acompanhar().json()

        assert pagina["situacao"] == "Em apuração"
        self._sem_nada_interno(pagina, etapa)

    def test_no_caso_concluido_a_resposta_final_nao_traz_medida_nem_nome(self, canal):
        self._caso_com_tudo_dentro(
            canal,
            etapa="encerrado",
            desfecho="concluido",
            retorno_aprovado_id="r1",
            retorno_aprovado_por=COORDENACAO,
        )
        canal.mudar_caso(encerrado_em=datetime.now(UTC).isoformat())

        pagina = canal.acompanhar().json()

        assert pagina["situacao"] == "Concluído"
        assert pagina["mensagens"][-1] == {
            "de": "comite",
            "tipo": "resposta_final",
            "texto": RESPOSTA_DO_RETORNO,
            "em": pagina["mensagens"][-1]["em"],
        }
        self._sem_nada_interno(pagina, "encerrado")

    def _sem_nada_interno(self, pagina: dict, etapa: str) -> None:
        assert set(pagina) == {"protocolo", "situacao", "mensagens"}
        for mensagem in pagina["mensagens"]:
            assert set(mensagem) == {"de", "tipo", "texto", "em"}
        texto = json.dumps(pagina, ensure_ascii=False).lower()
        for proibido in (
            NOME_DA_COORDENACAO,
            NOME_DO_MEMBRO,
            f'"{COORDENACAO}"',
            f'"{MEMBRO}"',
            "advert",
            "procedente",
            "voto",
            "medida",
            "completo",
            f'"{etapa}"',
        ):
            assert proibido.lower() not in texto, proibido


# ═══════════════════════════════════════════════════════════════════════════
# 3. A coordenação pergunta, e a pergunta aparece para quem relatou
# ═══════════════════════════════════════════════════════════════════════════


def _aberto(canal: _Canal, papel: str = "coordenacao"):
    from types import SimpleNamespace

    return SimpleNamespace(autor_id=COORDENACAO, pessoa=SimpleNamespace(papel=papel), caso=canal.caso, atribuicoes=[])


class TestPergunta:
    def test_a_pergunta_da_coordenacao_aparece_para_quem_relatou(self, canal):
        assert canal.perguntar().status_code == 201

        pagina = canal.acompanhar().json()

        assert pagina["situacao"] == "Aguardando sua resposta"
        assert [(m["de"], m["tipo"], m["texto"]) for m in pagina["mensagens"]] == [("comite", "pergunta", PERGUNTA)]

    def test_a_pergunta_fica_cifrada_e_na_trilha(self, canal):
        canal.perguntar()

        (linha,) = canal.banco.tabelas["conduta_mensagens"]
        assert linha["texto_cifrado"].startswith("v1:")
        assert PERGUNTA not in repr(canal.banco.tabelas)
        assert [t["acao"] for t in canal.banco.tabelas["conduta_trilha"]][-1] == "pergunta"

    def test_so_a_coordenacao_pergunta(self, canal):
        resposta = canal.perguntar(pid=MEMBRO)

        assert resposta.status_code == 403
        assert canal.banco.tabelas.get("conduta_mensagens", []) == []

    def test_a_tela_do_caso_oferece_as_perguntas_que_o_agente_sugeriu(self, canal):
        sugestao = {"perguntas_ao_denunciante": {"valor": ["Quando foi?", "Alguém mais viu?"], "justificativa": ""}}
        canal.banco.tabelas["conduta_sugestoes"] = [
            {
                "caso_id": canal.caso_id,
                "situacao": "sugerida",
                "sugestao_cifrada": cifra.cifrar_texto(json.dumps(sugestao)),
            }
        ]

        area = acompanhamento.para_a_tela(canal.banco, _aberto(canal), HOJE)["mensagens"]

        assert area["perguntas_sugeridas"] == ["Quando foi?", "Alguém mais viu?"]
        assert area["pode_perguntar"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 4. O complemento aparece no caso, cifrado, e muda a situação
# ═══════════════════════════════════════════════════════════════════════════


class TestComplemento:
    def test_o_complemento_aparece_no_caso_cifrado_e_muda_a_situacao(self, canal):
        canal.perguntar()
        assert canal.acompanhar().json()["situacao"] == "Aguardando sua resposta"

        resposta = canal.complementar()

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["situacao"] == "Recebido"
        (linha,) = [m for m in canal.banco.tabelas["conduta_mensagens"] if m["tipo"] == "complemento"]
        assert linha["texto_cifrado"].startswith("v1:")
        assert linha["autor_id"] is None
        assert COMPLEMENTO_TEXTO not in repr(canal.banco.tabelas)
        itens = canal.tela()["mensagens"]["itens"]
        assert [(m["de"], m["texto"]) for m in itens] == [("comite", PERGUNTA), ("relator", COMPLEMENTO_TEXTO)]

    def test_a_conversa_entra_no_dossie_do_caso(self, canal):
        canal.perguntar()
        canal.complementar()

        resposta = canal.comite().get(f"/api/comite-de-conduta/casos/{canal.caso_id}/dossie")

        assert resposta.status_code == 200, resposta.text
        with zipfile.ZipFile(io.BytesIO(resposta.content)) as pacote:
            mensagens = pacote.read("08-mensagens-com-o-denunciante.txt").decode("utf-8")
        assert mensagens.index(PERGUNTA) < mensagens.index(COMPLEMENTO_TEXTO)
        assert "Pergunta do Comitê" in mensagens
        assert "Complemento de quem relatou" in mensagens

    def test_o_complemento_marca_que_quem_relatou_informou_algo(self, canal):
        """A verificação de retaliação do caso anônimo depende desse aviso."""
        canal.complementar()

        assert canal.caso["denunciante_informou_em"]
        assert [t["acao"] for t in canal.banco.tabelas["conduta_trilha"]][-1] == "complemento"

    def test_complemento_vazio_e_recusado_sem_gravar(self, canal):
        resposta = canal.complementar(texto="   ")

        assert resposta.status_code == 422
        assert canal.banco.tabelas.get("conduta_mensagens", []) == []

    def test_complemento_com_codigo_errado_recebe_a_recusa_padrao(self, canal):
        corpo = {"protocolo": canal.protocolo, "codigo": "ABCDE-23456", "texto": COMPLEMENTO_TEXTO}

        resposta = canal.publico().post(COMPLEMENTO, json=corpo)

        assert resposta.status_code == 404
        assert resposta.json() == RECUSA
        assert canal.banco.tabelas.get("conduta_mensagens", []) == []


# ═══════════════════════════════════════════════════════════════════════════
# 5. 15 dias sem resposta liberam arquivar; o arquivado reabre
# ═══════════════════════════════════════════════════════════════════════════

ARQUIVAR = "/api/comite-de-conduta/casos/{}/arquivamento"
REABRIR = "/api/comite-de-conduta/casos/{}/reabertura"


def _depoimento(canal: _Canal, did: str, *, concluido_em: str | None) -> dict:
    return {
        "id": did,
        "caso_id": canal.caso_id,
        "nome_cifrado": cifra.cifrar_texto("Pessoa ouvida"),
        "cargo_cifrado": cifra.cifrar_texto("Técnico"),
        "papel": "testemunha",
        "criado_por": COORDENACAO,
        "criado_em": "2026-11-03T12:00:00+00:00",
        "concluido_em": concluido_em,
        "concluido_por": COORDENACAO if concluido_em else None,
    }


class TestArquivarEReabrir:
    def test_antes_de_15_dias_arquivar_nao_esta_disponivel(self, canal):
        canal.perguntar()
        canal.recuar_mensagens(14)

        area = canal.tela()["mensagens"]
        resposta = canal.comite().post(ARQUIVAR.format(canal.caso_id))

        assert area["pode_arquivar"] is False
        assert resposta.status_code == 409
        assert not canal.caso.get("encerrado_em")

    def test_depois_de_15_dias_sem_resposta_arquivar_fica_disponivel(self, canal):
        canal.mudar_caso(etapa="apuracao", triagem_em="2026-11-02T12:00:00+00:00")
        canal.perguntar()
        canal.recuar_mensagens(15)

        assert canal.tela()["mensagens"]["pode_arquivar"] is True
        resposta = canal.comite().post(ARQUIVAR.format(canal.caso_id))

        assert resposta.status_code == 200, resposta.text
        assert canal.caso["desfecho"] == "arquivado"
        assert canal.caso["encerrado_em"]
        assert canal.acompanhar().json()["situacao"] == "Concluído"

    def test_pergunta_respondida_nao_libera_arquivar(self, canal):
        canal.perguntar()
        canal.complementar()
        canal.recuar_mensagens(30)

        assert canal.tela()["mensagens"]["pode_arquivar"] is False
        assert canal.comite().post(ARQUIVAR.format(canal.caso_id)).status_code == 409

    def test_so_a_coordenacao_arquiva(self, canal):
        canal.perguntar()
        canal.recuar_mensagens(20)

        assert canal.comite(MEMBRO).post(ARQUIVAR.format(canal.caso_id)).status_code == 403

    def test_o_caso_arquivado_reabre_quando_a_informacao_chega_depois(self, canal):
        canal.mudar_caso(etapa="apuracao", triagem_em="2026-11-02T12:00:00+00:00")
        canal.perguntar()
        canal.recuar_mensagens(16)
        assert canal.comite().post(ARQUIVAR.format(canal.caso_id)).status_code == 200
        assert canal.tela()["mensagens"]["pode_reabrir"] is False
        assert canal.comite().post(REABRIR.format(canal.caso_id)).status_code == 409

        assert canal.complementar().status_code == 200
        assert canal.tela()["mensagens"]["pode_reabrir"] is True
        resposta = canal.comite().post(REABRIR.format(canal.caso_id))

        assert resposta.status_code == 200, resposta.text
        assert canal.caso["encerrado_em"] is None
        assert canal.caso["desfecho"] is None
        assert canal.caso["etapa"] == "apuracao"
        assert canal.acompanhar().json()["situacao"] == "Em apuração"
        acoes = [t["acao"] for t in canal.banco.tabelas["conduta_trilha"]]
        assert "arquivamento" in acoes
        assert acoes[-1] == "reabertura"

    def _arquivar_travado(self, canal) -> tuple[dict, object, list]:
        canal.perguntar()
        canal.recuar_mensagens(20)
        area = canal.tela()["mensagens"]
        trilha_antes = list(canal.banco.tabelas["conduta_trilha"])
        resposta = canal.comite().post(ARQUIVAR.format(canal.caso_id))
        return area, resposta, trilha_antes

    def test_na_apuracao_com_depoimento_em_aberto_nao_arquiva_nem_grava_na_trilha(self, canal):
        canal.mudar_caso(etapa="apuracao", triagem_em="2026-11-02T12:00:00+00:00")
        canal.banco.tabelas.setdefault("conduta_depoimentos", []).extend(
            [_depoimento(canal, "dep-1", concluido_em=None), _depoimento(canal, "dep-2", concluido_em="2026-11-04")]
        )

        area, resposta, trilha_antes = self._arquivar_travado(canal)

        assert area["pode_arquivar"] is False
        assert resposta.status_code == 409
        assert "depoimentos concluídos" in resposta.json()["detail"]
        assert canal.banco.tabelas["conduta_trilha"] == trilha_antes
        assert not canal.caso.get("encerrado_em")
        assert canal.caso["etapa"] == "apuracao"

    def test_na_apuracao_com_os_depoimentos_concluidos_arquiva(self, canal):
        canal.mudar_caso(etapa="apuracao", triagem_em="2026-11-02T12:00:00+00:00")
        canal.banco.tabelas.setdefault("conduta_depoimentos", []).append(
            _depoimento(canal, "dep-1", concluido_em="2026-11-04T12:00:00+00:00")
        )

        area, resposta, _ = self._arquivar_travado(canal)

        assert area["pode_arquivar"] is True
        assert resposta.status_code == 200, resposta.text
        assert canal.caso["desfecho"] == "arquivado"

    def test_na_medida_sem_a_decisao_da_direcao_nao_arquiva_nem_grava_na_trilha(self, canal):
        canal.mudar_caso(etapa="medida", triagem_em="2026-11-02T12:00:00+00:00")

        area, resposta, trilha_antes = self._arquivar_travado(canal)

        assert area["pode_arquivar"] is False
        assert resposta.status_code == 409
        assert "decisão da Direção" in resposta.json()["detail"]
        assert canal.banco.tabelas["conduta_trilha"] == trilha_antes
        assert not canal.caso.get("encerrado_em")
        assert canal.caso["etapa"] == "medida"

    def test_na_medida_com_a_decisao_da_direcao_arquiva(self, canal):
        canal.mudar_caso(etapa="medida", triagem_em="2026-11-02T12:00:00+00:00")
        canal.banco.tabelas.setdefault("conduta_decisoes_da_medida", []).append(
            {"id": "dec-1", "caso_id": canal.caso_id, "decisao": "aplicada"}
        )

        area, resposta, _ = self._arquivar_travado(canal)

        assert area["pode_arquivar"] is True
        assert resposta.status_code == 200, resposta.text
        assert canal.caso["desfecho"] == "arquivado"

    def test_quem_relatou_le_que_o_caso_foi_arquivado_e_como_reabrir(self, canal):
        canal.perguntar()
        canal.recuar_mensagens(15)
        canal.comite().post(ARQUIVAR.format(canal.caso_id))

        final = canal.acompanhar().json()["mensagens"][-1]

        assert final["tipo"] == "resposta_final"
        assert "arquivado por falta de elementos" in final["texto"]

    def test_a_caixa_o_que_fazer_agora_diz_que_o_caso_foi_arquivado(self, canal):
        canal.perguntar()
        canal.recuar_mensagens(15)
        canal.comite().post(ARQUIVAR.format(canal.caso_id))

        caixa = canal.tela()["o_que_fazer_agora"]

        assert "arquivado por falta de elementos" in caixa["frase"]
        assert "Encaminhado" not in caixa["frase"]


# ═══════════════════════════════════════════════════════════════════════════
# 6. Acompanhar não grava IP e tem limite de tentativas sem guardar endereço
# ═══════════════════════════════════════════════════════════════════════════


class _Captura(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.linhas: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.linhas.append(self.format(record))


@pytest.fixture
def log():
    captura = _Captura()
    raiz = logging.getLogger()
    nivel = raiz.level
    raiz.addHandler(captura)
    raiz.setLevel(logging.DEBUG)
    yield captura
    raiz.removeHandler(captura)
    raiz.setLevel(nivel)


def _tentativas_erradas(cliente: TestClient, canal: _Canal, quantas: int) -> list[int]:
    return [
        cliente.post(ACOMPANHAR, json={"protocolo": canal.protocolo, "codigo": f"ABCDE-2345{n + 2}"}).status_code
        for n in range(quantas)
    ]


class TestSemRastro:
    def test_acompanhar_e_complementar_nao_gravam_ip_aparelho_nem_localizacao(self, canal, log):
        cabecalhos = {"User-Agent": APARELHO, "X-Forwarded-For": "198.51.100.23", "Geolocation": "-22.87,-43.46"}
        corpo = {"protocolo": canal.protocolo, "codigo": canal.codigo}

        assert canal.publico().post(ACOMPANHAR, json=corpo, headers=cabecalhos).status_code == 200
        complemento = corpo | {"texto": "Mais um dado"}
        assert canal.publico().post(COMPLEMENTO, json=complemento, headers=cabecalhos).status_code == 200

        rastro = repr(canal.banco.tabelas) + "\n".join(log.linhas)
        assert log.linhas, "controle: o log da requisição tem que ter sido escrito"
        for marca in (IP_DE_QUEM_ACOMPANHA, "203.0.113", "198.51.100.23", "Android", "Celular-de-Entrada", "-22.87"):
            assert marca not in rastro

    def test_a_resposta_nao_fica_em_cache_nem_grava_cookie(self, canal):
        resposta = canal.acompanhar()

        assert resposta.headers["cache-control"] == "no-store"
        assert "set-cookie" not in resposta.headers

    def test_tentativas_demais_do_mesmo_aparelho_param_no_limite_sem_gravar_o_endereco(self, canal, log):
        respostas = _tentativas_erradas(canal.publico(), canal, 7)

        assert respostas == [404, 404, 404, 404, 404, 429, 429]
        assert IP_DE_QUEM_ACOMPANHA not in repr(canal.banco.tabelas) + "\n".join(log.linhas)

    def test_depois_da_rajada_nem_o_codigo_certo_passa(self, canal):
        cliente = canal.publico()
        _tentativas_erradas(cliente, canal, 5)

        assert cliente.post(ACOMPANHAR, json={"protocolo": canal.protocolo, "codigo": canal.codigo}).status_code == 429

    def test_outro_aparelho_ainda_acompanha(self, canal):
        _tentativas_erradas(canal.publico(), canal, 5)

        assert canal.acompanhar(ip="198.51.100.77").status_code == 200

    def test_com_o_canal_fechado_o_acompanhamento_responde_404(self, canal, monkeypatch):
        monkeypatch.setattr(settings, "conduta_canal_aberto", False)

        resposta = canal.acompanhar()

        assert resposta.status_code == 404
        assert resposta.json() == {"detail": "Not Found"}
