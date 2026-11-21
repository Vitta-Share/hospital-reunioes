"""O agente de triagem do Canal de Conduta (issue #1827, PRD #1786, ADR 0097
decisões 6, 7 e 15).

Cada classe é um critério de aceite da issue. O banco é o dublê de
`conduta_apoio`, com a função da cota; o modelo é um dublê que guarda o que
recebeu. Nenhum teste chama a IA de verdade.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from conduta_apoio import Banco
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.routers import conduta_comite  # noqa: E402
from app.services.conduta import agente_de_triagem as agente  # noqa: E402
from app.services.conduta import casos, cifra  # noqa: E402
from app.services.conduta.acesso import hoje_em_sao_paulo  # noqa: E402

BASE = "/api/comite-de-conduta"
HOJE = hoje_em_sao_paulo()
COMITE = {"id": "col-conduta", "slug": "conduta", "nome": "Comitê de Conduta"}
COORDENACAO, MEMBRO = "COORD", "MEMB"
NOMES = {COORDENACAO: "Beatriz Albuquerque Mendes", MEMBRO: "Rogério Tavares Lins"}

RELATO = "Minha coordenadora grita comigo na frente da equipe toda semana e me chama de incompetente."


def _item(valor, justificativa="Sustentado pelo relato.", trecho="grita comigo", **extra) -> dict:
    return {"valor": valor, "justificativa": justificativa, "trecho": trecho, **extra}


def resposta_valida(**troca) -> dict:
    saida = {
        "escopo": _item("DENTRO", "Relato de assédio moral pela chefia.", destino=""),
        "categoria": _item("A", "Conduta e relações: humilhação repetida."),
        "rito": _item("RAPIDO", "Não há fato que leve a demissão por justa causa."),
        "especial": _item("NAO", "Ninguém da Direção é citado.", citados=""),
        "risco_imediato": _item("NAO", "Sem ameaça à integridade."),
        "assunto_para_lista": _item("Humilhação pela chefia na frente da equipe"),
        "resumo": _item("A pessoa relata gritos e ofensas semanais da coordenação."),
        "lacunas": _item(["setor", "testemunhas"], "Faltam o setor e quem presenciou."),
        "perguntas_ao_denunciante": _item(["Em que setor isso acontece?"], "O setor muda quem apura."),
        "casos_parecidos": _item([], "Nenhum caso anterior parecido.", trecho=""),
        "relatos_repetidos_improcedentes": _item("NAO", "Sem casos anteriores com o mesmo cargo.", trecho=""),
        "sinalizar_nsp": _item("NAO", "Não descreve evento com paciente.", trecho=""),
        "confianca": _item("ALTA", "Relato claro.", trecho=""),
    }
    saida.update(troca)
    return saida


class Modelo:
    """O dublê do cliente da Anthropic: guarda cada mensagem e devolve a
    resposta combinada, ou levanta quando `falha` é uma exceção."""

    def __init__(self, resposta: dict | str | None = None, falha: Exception | None = None):
        self.resposta = resposta if resposta is not None else resposta_valida()
        self.falha = falha
        self.chamadas: list[dict] = []
        self.messages = self

    def create(self, **argumentos):
        self.chamadas.append(argumentos)
        if self.falha:
            raise self.falha
        texto = self.resposta if isinstance(self.resposta, str) else json.dumps(self.resposta, ensure_ascii=False)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=texto)])

    def texto_enviado(self) -> str:
        return "\n".join(m["content"] for chamada in self.chamadas for m in chamada["messages"])


class BancoComCota(Banco):
    """O dublê com a função da cota da migration 195 e a chave única do caso
    em `conduta_sugestoes`."""

    def __init__(self, tabelas=None, *, teto_atingido: bool = False):
        super().__init__(tabelas)
        self.teto_atingido = teto_atingido
        self.reservas = 0

    def rpc(self, nome, parametros):
        assert nome == agente.FUNCAO_DA_COTA
        assert parametros == {"p_teto": 100}
        self.reservas += 1
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[{"reservada": not self.teto_atingido}]))

    def gravar(self, nome, linha):
        unicas = {"conduta_sugestoes": ("caso_id",), "conduta_sugestao_respostas": ("caso_id", "item")}
        chave = unicas.get(nome)
        if chave and any(all(x.get(c) == linha.get(c) for c in chave) for x in self.tabelas.get(nome, [])):
            raise APIError({"code": "23505", "message": f"duplicate key value violates unique constraint ({nome})"})
        return super().gravar(nome, linha)


class Tarefas:
    """O `BackgroundTasks` do FastAPI, sem rodar nada sozinho."""

    def __init__(self):
        self.agendadas: list[tuple] = []

    def add_task(self, funcao, *argumentos):
        self.agendadas.append((funcao, argumentos))


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "conduta_chave_cifra", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setattr(settings, "conduta_agente_ligado", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "chave-de-teste")


def _pessoa(pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": NOMES[pid],
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


class Comite:
    def __init__(self, *, teto_atingido: bool = False, modelo: Modelo | None = None):
        self.banco = BancoComCota(
            {
                "participantes": [_pessoa(COORDENACAO), _pessoa(MEMBRO)],
                "colegiados": [dict(COMITE)],
                "participacoes": [_participacao(COORDENACAO, "coordenacao"), _participacao(MEMBRO, "membro")],
            },
            teto_atingido=teto_atingido,
        )
        self.modelo = modelo or Modelo()

    def novo_caso(self, relato: str = RELATO) -> str:
        tarefas = Tarefas()
        caso = casos.registrar_caso(self.banco, relato=relato, categoria=None, tarefas=tarefas)
        for funcao, argumentos in tarefas.agendadas:
            assert funcao is agente.triar_caso_fora_do_loop
            agente.triar_caso(*argumentos, cliente=self.modelo)
        return caso["id"]

    def cliente(self, pid: str) -> TestClient:
        app = FastAPI()
        app.include_router(conduta_comite.router, prefix="/api")
        pessoa = next(p for p in self.banco.tabelas["participantes"] if p["id"] == pid)

        async def _usuario() -> dict[str, Any]:
            return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

        app.dependency_overrides[get_current_user] = _usuario
        app.dependency_overrides[get_supabase_client] = lambda: self.banco
        return TestClient(app)

    def abrir(self, pid: str, caso_id: str) -> dict:
        resposta = self.cliente(pid).get(f"{BASE}/casos/{caso_id}")
        assert resposta.status_code == 200, resposta.text
        return resposta.json()

    def trilha(self, caso_id: str) -> list[tuple[str, str]]:
        return [(x["acao"], x["detalhe"]) for x in self.banco.tabelas["conduta_trilha"] if x["caso_id"] == caso_id]

    def sugestoes(self, caso_id: str) -> list[dict]:
        return [x for x in self.banco.tabelas.get("conduta_sugestoes", []) if x["caso_id"] == caso_id]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Um caso novo recebe a sugestão do agente sem clique de ninguém, uma única vez
# ═══════════════════════════════════════════════════════════════════════════


class TestSugestaoNaEntrada:
    def test_caso_novo_recebe_a_sugestao_sem_clique_de_ninguem(self):
        comite = Comite()
        caso_id = comite.novo_caso()

        assert len(comite.modelo.chamadas) == 1
        [linha] = comite.sugestoes(caso_id)
        assert linha["situacao"] == "sugerida"
        assert linha["modelo"] == "claude-sonnet-5-5"
        sugestao = json.loads(cifra.decifrar_texto(linha["sugestao_cifrada"]))
        assert sugestao["rito"]["valor"] == "RAPIDO"
        assert ("sugestao_do_agente", "o agente sugeriu a triagem") in comite.trilha(caso_id)

    def test_o_agente_le_o_caso_uma_unica_vez(self):
        comite = Comite()
        caso_id = comite.novo_caso()

        agente.triar_caso(comite.banco, caso_id, cliente=comite.modelo)

        assert len(comite.modelo.chamadas) == 1
        assert len(comite.sugestoes(caso_id)) == 1
        assert [a for a, _ in comite.trilha(caso_id)].count("sugestao_do_agente") == 1
