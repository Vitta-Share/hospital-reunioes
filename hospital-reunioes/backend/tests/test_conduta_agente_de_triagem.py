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
from datetime import UTC, datetime, timedelta
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
from app.services.prompt_loader import load_prompt  # noqa: E402

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
    """O dublê com a função da cota da migration 200 e a chave única do caso
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
        # O DEFAULT now() da migration 175.
        linha = next(c for c in self.banco.tabelas["conduta_casos"] if c["id"] == caso["id"])
        linha["recebido_em"] = datetime.now(UTC).isoformat()
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


# ═══════════════════════════════════════════════════════════════════════════
# 2. O texto enviado ao modelo não contém nome, CPF, telefone nem e-mail
# ═══════════════════════════════════════════════════════════════════════════

RELATO_COM_DADOS = (
    "Eu, Juliana Prado, CPF 529.982.247-25, telefone (21) 98765-4321, email juliana.prado@gmail.com, "
    "relato que a supervisora Marcia Coelho grita comigo. O caso foi visto por rogério tavares lins."
)


class TestTextoSemNome:
    def test_o_modelo_recebe_marcadores_no_lugar_de_nome_cpf_telefone_e_email(self):
        comite = Comite()
        comite.novo_caso(RELATO_COM_DADOS)

        enviado = comite.modelo.texto_enviado()
        for marcador in ("[NOME]", "[CPF]", "[TELEFONE]", "[EMAIL]"):
            assert marcador in enviado
        for dado in ("Juliana", "Prado", "529.982.247-25", "98765-4321", "juliana.prado", "Marcia", "Coelho"):
            assert dado not in enviado

    def test_o_nome_de_um_membro_do_comite_sai_mesmo_em_minusculas(self):
        comite = Comite()
        comite.novo_caso(RELATO_COM_DADOS)

        enviado = comite.modelo.texto_enviado().lower()
        assert "rogério" not in enviado and "tavares" not in enviado
        assert "visto por [nome]" in enviado

    def test_so_o_relato_a_categoria_e_os_casos_anteriores_vao_ao_modelo(self):
        comite = Comite()
        primeiro = comite.novo_caso()
        linha = next(c for c in comite.banco.tabelas["conduta_casos"] if c["id"] == primeiro)
        linha["recebido_em"] = "2026-11-01T10:00:00+00:00"
        comite.novo_caso("Estão sumindo ampolas do carrinho do centro cirúrgico.")

        segunda = comite.modelo.chamadas[1]["messages"][0]["content"]
        assert linha["protocolo"] in segunda
        assert "Humilhação pela chefia na frente da equipe" in segunda
        assert "codigo_hash" not in segunda and linha["codigo_hash"] not in segunda


# ═══════════════════════════════════════════════════════════════════════════
# 5. Passado o teto diário ou com falha do modelo, o caso entra na fila sem
#    sugestão, e a trilha diz por quê
# ═══════════════════════════════════════════════════════════════════════════


class TestSemSugestao:
    def test_passado_o_teto_o_modelo_nao_e_chamado_e_a_trilha_diz_por_que(self):
        comite = Comite(teto_atingido=True)
        caso_id = comite.novo_caso()

        assert comite.modelo.chamadas == []
        assert comite.banco.reservas == 1
        [linha] = comite.sugestoes(caso_id)
        assert linha["situacao"] == "manual" and linha["motivo_manual"] == "teto"
        assert (
            "triagem_manual",
            "sem sugestão do agente: o teto diário de leituras do agente foi atingido",
        ) in comite.trilha(caso_id)
        assert comite.abrir(COORDENACAO, caso_id)["etapa"] == "triagem"

    def test_com_o_modelo_fora_do_ar_o_caso_fica_para_triagem_manual(self):
        comite = Comite(modelo=Modelo(falha=TimeoutError("sem resposta")))
        caso_id = comite.novo_caso()

        assert len(comite.modelo.chamadas) == 1
        assert comite.sugestoes(caso_id)[0]["motivo_manual"] == "agente_fora"
        assert ("triagem_manual", "sem sugestão do agente: o agente está fora do ar") in comite.trilha(caso_id)

    def test_resposta_fora_do_formato_nao_vira_sugestao(self):
        comite = Comite(modelo=Modelo(resposta=resposta_valida(rito=_item("ENCAMINHAMENTO"))))
        caso_id = comite.novo_caso()

        assert comite.sugestoes(caso_id)[0]["motivo_manual"] == "validacao"
        assert (
            "triagem_manual",
            "sem sugestão do agente: a resposta do agente veio fora do formato",
        ) in comite.trilha(caso_id)

    def test_cada_quebra_de_coerencia_e_recusada(self):
        assert agente.validar_saida(resposta_valida()) == []
        fora_sem_destino = resposta_valida(
            escopo=_item("FORA", destino=""), categoria=_item(""), rito=_item("ENCAMINHAMENTO")
        )
        assert "destino" in agente.validar_saida(fora_sem_destino)
        especial_sem_rito = resposta_valida(especial=_item("SIM", citados="diretora"))
        assert "especial" in agente.validar_saida(especial_sem_rito)
        quatro = resposta_valida(perguntas_ao_denunciante=_item(["a?", "b?", "c?", "d?"]))
        assert "perguntas" in agente.validar_saida(quatro)
        sem_justificativa = resposta_valida(resumo=_item("Resumo.", justificativa=""))
        assert "formato:resumo" in agente.validar_saida(sem_justificativa)

    def test_assunto_de_mais_de_oito_palavras_leva_o_caso_a_triagem_manual(self):
        # Equivalente à resposta da rodada 1 do caso 7 do Anexo B, recusada no
        # assunto: a de oito palavras é a da rodada 3, que passou.
        oito = "Possível retaliação: horas extras cortadas após recusar convite"
        dez = "Possível retaliação: horas extras cortadas após recusar convite do chefe"
        assert agente.validar_saida(resposta_valida(assunto_para_lista=_item(oito))) == []
        comite = Comite(modelo=Modelo(resposta=resposta_valida(assunto_para_lista=_item(dez))))
        caso_id = comite.novo_caso()

        assert comite.sugestoes(caso_id)[0]["motivo_manual"] == "validacao"
        assert agente.validar_saida(resposta_valida(assunto_para_lista=_item(dez))) == ["assunto"]

    def test_o_prompt_diz_o_limite_do_assunto_entre_as_regras_que_o_sistema_confere(self):
        # O "até 8 palavras" só no molde do JSON não avisava o modelo de que a
        # nona palavra derruba a resposta inteira (caso 7, rodada 1, do Anexo B).
        prompt = load_prompt(agente.PROMPT)
        regras = prompt.split("Regras de coerência, que o sistema confere:")[1].split("\n\n")[0]
        [linha] = [linha for linha in regras.splitlines() if "`assunto_para_lista`" in linha]
        assert "no máximo 8 palavras" in linha
        assert "recusada" in linha


# ═══════════════════════════════════════════════════════════════════════════
# 3. Cada item sugerido aparece marcado como "Sugestão", com a justificativa
#    visível sem clique
# ═══════════════════════════════════════════════════════════════════════════


class TestSugestaoNaTela:
    def test_cada_item_vem_como_sugestao_com_a_justificativa(self):
        comite = Comite()
        caso_id = comite.novo_caso()

        sugestao = comite.abrir(MEMBRO, caso_id)["sugestao_do_agente"]

        assert sugestao["situacao"] == "sugerida"
        assert [i["item"] for i in sugestao["itens"]] == list(agente.ITENS)
        assert all(i["rotulo"] == "Sugestão" and i["justificativa"] for i in sugestao["itens"])
        rito = next(i for i in sugestao["itens"] if i["item"] == "rito")
        assert rito["valor"] == "Rápido"
        assert rito["justificativa"] == "Não há fato que leve a demissão por justa causa."
        assert rito["trecho"] == "grita comigo"
        lacunas = next(i for i in sugestao["itens"] if i["item"] == "lacunas")
        assert lacunas["valor"] == "setor\ntestemunhas"

    def test_sem_sugestao_a_tela_diz_por_que(self):
        comite = Comite(teto_atingido=True)
        caso_id = comite.novo_caso()

        sugestao = comite.abrir(COORDENACAO, caso_id)["sugestao_do_agente"]

        assert sugestao["situacao"] == "manual"
        assert sugestao["itens"] == []
        assert sugestao["motivo"] == "Sem sugestão do agente: o teto diário de leituras do agente foi atingido."


# ═══════════════════════════════════════════════════════════════════════════
# 4. Discordar de um item exige o motivo e grava a discordância
# ═══════════════════════════════════════════════════════════════════════════


def _responder(comite: Comite, pid: str, caso_id: str, **corpo):
    return comite.cliente(pid).post(f"{BASE}/casos/{caso_id}/sugestao", json=corpo)


class TestDiscordancia:
    def test_discordar_sem_motivo_e_recusado(self):
        comite = Comite()
        caso_id = comite.novo_caso()

        resposta = _responder(comite, COORDENACAO, caso_id, item="rito", resposta="discordo", motivo="  ")

        assert resposta.status_code == 422
        assert resposta.json()["detail"] == "Escreva o motivo da discordância em uma linha."
        assert comite.banco.tabelas.get("conduta_sugestao_respostas", []) == []

    def test_discordar_com_motivo_grava_a_discordancia_cifrada_e_a_trilha(self):
        comite = Comite()
        caso_id = comite.novo_caso()

        resposta = _responder(
            comite, COORDENACAO, caso_id, item="rito", resposta="discordo", motivo="Há ameaça de demissão."
        )

        assert resposta.status_code == 200, resposta.text
        [linha] = comite.banco.tabelas["conduta_sugestao_respostas"]
        assert linha["item"] == "rito" and linha["resposta"] == "discordo" and linha["autor_id"] == COORDENACAO
        assert cifra.decifrar_texto(linha["motivo_cifrado"]) == "Há ameaça de demissão."
        assert ("sugestao_discordada", "discordou da sugestão do agente: Rito") in comite.trilha(caso_id)
        itens = comite.abrir(COORDENACAO, caso_id)["sugestao_do_agente"]["itens"]
        rito = next(i for i in itens if i["item"] == "rito")
        assert rito["resposta"] == "discordo" and rito["motivo"] == "Há ameaça de demissão."

    def test_confirmar_nao_pede_motivo(self):
        comite = Comite()
        caso_id = comite.novo_caso()

        resposta = _responder(comite, COORDENACAO, caso_id, item="categoria", resposta="confirmo", motivo="")

        assert resposta.status_code == 200, resposta.text
        assert ("sugestao_confirmada", "confirmou a sugestão do agente: Categoria") in comite.trilha(caso_id)

    def test_so_a_coordenacao_responde_e_uma_vez_por_item(self):
        comite = Comite()
        caso_id = comite.novo_caso()

        assert _responder(comite, MEMBRO, caso_id, item="rito", resposta="confirmo").status_code == 403
        assert _responder(comite, COORDENACAO, caso_id, item="rito", resposta="confirmo").status_code == 200
        segunda = _responder(comite, COORDENACAO, caso_id, item="rito", resposta="discordo", motivo="x")
        assert segunda.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════
# 6. O possível impedimento por nome é calculado no app, sem chamada de IA
# ═══════════════════════════════════════════════════════════════════════════


class TestImpedimentoPorNome:
    def test_membro_citado_pelo_nome_aparece_como_possivel_impedimento_sem_ia(self):
        comite = Comite(modelo=Modelo(falha=AssertionError("o impedimento não chama a IA")))
        caso_id = comite.novo_caso("Quem grita com a equipe é a beatriz mendes, da coordenação.")
        chamadas_da_entrada = len(comite.modelo.chamadas)

        sugestao = comite.abrir(MEMBRO, caso_id)["sugestao_do_agente"]

        assert sugestao["possivel_impedimento"] == [
            {"membro": "Beatriz Albuquerque Mendes", "motivo": "O nome aparece no relato."}
        ]
        assert len(comite.modelo.chamadas) == chamadas_da_entrada

    def test_relato_sem_nome_de_membro_nao_aponta_impedimento(self):
        comite = Comite()
        caso_id = comite.novo_caso()

        assert comite.abrir(MEMBRO, caso_id)["sugestao_do_agente"]["possivel_impedimento"] == []
