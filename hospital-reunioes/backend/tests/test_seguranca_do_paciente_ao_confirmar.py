"""O que acontece ao confirmar a triagem: a reunião de análise e os avisos
(issue #1994, PRD #1979, ADR 0107 decisão 1).

Um bloco por critério de aceite:

1. confirmar um caso A cria a reunião de análise Programada na data-limite,
   com o protocolo na pauta;
2. a lesão por pressão dos itens 8 a 10 sem óbito não cria reunião e entra na
   pauta da ordinária seguinte;
3. confirmar A ou B registra o aviso à Diretoria na hora; C, D e E não;
4. o identificado com e-mail recebe o aviso; o anônimo vê o estado novo na
   página de acompanhamento;
5. confirmar duas vezes o mesmo caso não cria segunda reunião nem segundo
   aviso;
6. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória dos testes da triagem e dos prazos, com o que a
migration 218 faz: uma reunião de análise por caso e um aviso por caso, marco
e destinatário. O e-mail é sempre dublado. As pessoas são de teste.

As datas são as dos testes de prazos: o caso chega na terça 10/11/2026 e a
triagem é confirmada na quinta 12/11 às 15h de São Paulo. A reunião de análise
da faixa A vence em 7 dias úteis da confirmação, na segunda 23/11.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import ANONIMO, DIRETOR, PUBLICO, _pessoa  # noqa: E402
from test_seguranca_do_paciente_prazos import (  # noqa: E402
    DO_CASO,
    LESAO_POR_PRESSAO,
    _BancoDoNucleo,
    _ConsultaDoNucleo,
)
from test_seguranca_do_paciente_prazos import _banco as _banco_dos_prazos  # noqa: E402
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    GRAVE,
    MODERADO,
    OBITO,
    PRESIDENTE,
    QUASE_ERRO,
    TODOS_OS_CAMPOS,
    _notificacao,
    _sugestao,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_notificacoes as notificacoes_router  # noqa: E402
from app.routers import seguranca_do_paciente_reunioes as reunioes_router  # noqa: E402
from app.routers import seguranca_do_paciente_triagem as triagem_router  # noqa: E402
from app.services.seguranca_do_paciente import ao_confirmar, emails  # noqa: E402

SP = ZoneInfo("America/Sao_Paulo")
DIRETORIA_EXECUTIVA = _pessoa("P8", perfil_ouvidoria="diretoria_executiva")
LEVE = {"natureza": "evento_adverso", "grau_de_dano": "leve", "faixa": "D"}
ANALISE_DE_EVENTO = "Análise de evento"
ORDINARIA = "Ordinária mensal"

# O que a migration 218 (e as anteriores) seguram no banco.
_UNICAS = {
    "reunioes": ("nsp_caso_id",),
    "nsp_pautas": ("id_reuniao",),
    "nsp_avisos": ("caso_id", "marco", "referencia", "destinatario_id"),
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def enviados(monkeypatch) -> list[dict[str, str]]:
    """O provedor de e-mail dublado: anota cada envio."""
    caixa: list[dict[str, str]] = []

    def _enviar(destino, assunto, html, texto, **_kw):
        caixa.append({"para": destino, "assunto": assunto, "html": html, "texto": texto})
        return True

    monkeypatch.setattr(emails, "_enviar_email", _enviar)
    return caixa


class _Consulta(_ConsultaDoNucleo):
    """O dublê dos prazos, com as chaves únicas do banco."""

    def _inserir(self) -> list[dict]:
        chave = _UNICAS.get(self._nome)
        if chave:
            novas = self._valores if isinstance(self._valores, list) else [self._valores]
            for valores in novas:
                if all(valores.get(c) is None for c in chave):
                    continue
                if any(all(linha.get(c) == valores.get(c) for c in chave) for linha in self._linhas):
                    raise APIError({"code": "23505", "message": "duplicate key value"})
        return super()._inserir()


class _Banco(_BancoDoNucleo):
    def table(self, nome: str):
        return _Consulta(self, nome)


def _banco(notificacoes: list[dict], triagens: list[dict]) -> _Banco:
    banco = _Banco(_banco_dos_prazos(notificacoes, triagens).tabelas)
    banco.tabelas["participantes"] += [dict(DIRETOR), dict(DIRETORIA_EXECUTIVA)]
    return banco


def _avisos(banco, marco: str) -> list[dict[str, Any]]:
    return [a for a in banco.tabelas.get("nsp_avisos", []) if a["marco"] == marco]


def _cliente(banco, pessoa: dict[str, Any] = PRESIDENTE) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(triagem_router.router, prefix="/api")
    app.include_router(notificacoes_router.router, prefix="/api")
    app.include_router(reunioes_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _confirmar(banco, caso) -> None:
    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})
    assert resposta.status_code == 201, resposta.text


def _caso_confirmado(sugestao: dict, numero: int = 1, **campos) -> tuple[_Banco, dict]:
    caso = _notificacao(numero, **{**DO_CASO, **campos})
    banco = _banco([caso], [_sugestao(caso, **sugestao)])
    _confirmar(banco, caso)
    return banco, caso


def _reunioes(banco, tipo: str = ANALISE_DE_EVENTO) -> list[dict]:
    return [r for r in banco.tabelas.get("reunioes", []) if r.get("tipo") == tipo]


def _textos_da_pauta(banco, id_reuniao: str) -> list[str]:
    resposta = _cliente(banco).get(f"/api/nsp/reunioes/{id_reuniao}/pauta")
    assert resposta.status_code == 200, resposta.text
    return [item["texto"] for bloco in resposta.json()["blocos"] for item in bloco["itens"]]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Faixa A: a reunião de análise nasce Programada na data-limite
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("sugestao", "data_limite"),
    [(OBITO, "2026-11-23"), (GRAVE, "2026-12-03")],
    ids=["faixa A, 7 dias úteis", "faixa B, 15 dias úteis"],
)
def test_confirmar_um_caso_a_cria_a_reuniao_de_analise_programada_na_data_limite_com_o_protocolo_na_pauta(
    sugestao, data_limite
):
    banco, caso = _caso_confirmado(sugestao)

    [reuniao] = _reunioes(banco)
    assert reuniao["status_ata"] == "PROGRAMADA"
    assert reuniao["data"] == data_limite
    assert reuniao["colegiado_id"] == "col-nsp"
    assert reuniao["nsp_caso_id"] == caso["id"]
    assert any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, reuniao["id_reuniao"]))


@pytest.mark.parametrize("sugestao", [MODERADO], ids=["faixa C"])
def test_o_caso_sem_prazo_de_reuniao_de_analise_nao_cria_reuniao(sugestao):
    banco, _ = _caso_confirmado(sugestao)

    assert banco.tabelas.get("reunioes", []) == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. A lesão por pressão sem óbito vai para a ordinária seguinte
# ═══════════════════════════════════════════════════════════════════════════

# A ordinária de novembro já passou quando a triagem é confirmada (12/11); a
# seguinte é a de dezembro, e a de janeiro vem depois dela.
ORDINARIAS = {"novembro": "2026-11-05", "dezembro": "2026-12-03", "janeiro": "2027-01-07"}
# Segunda 30/11, dentro dos 5 dias úteis antes da ordinária de dezembro.
DIA_DA_PAUTA = datetime(2026, 11, 30, 10, 0, tzinfo=SP)


def _ordinaria(mes: str) -> dict[str, Any]:
    return {
        "id_reuniao": f"RD_{mes}",
        "titulo": f"Reunião ordinária de {mes}",
        "data": ORDINARIAS[mes],
        "hora_inicio": "14:00:00",
        "hora_fim": None,
        "tipo": ORDINARIA,
        "objetivo": None,
        "status_ata": "PROGRAMADA",
        "colegiado_id": "col-nsp",
        "deleted_at": None,
    }


@pytest.fixture
def com_as_ordinarias(monkeypatch):
    monkeypatch.setattr(reunioes_router, "_agora", lambda: datetime(2027, 1, 4, 10, 0, tzinfo=SP))

    def _cenario(item: int = 9, **sugestao) -> tuple[_Banco, dict]:
        caso = _notificacao(3, **DO_CASO)
        banco = _banco([caso], [_sugestao(caso, **{**LESAO_POR_PRESSAO, "evento_item": item, **sugestao})])
        banco.tabelas["reunioes"] = [_ordinaria(mes) for mes in ORDINARIAS]
        return banco, caso

    return _cenario


@pytest.mark.parametrize("item", [8, 9, 10])
def test_a_lesao_por_pressao_sem_obito_nao_cria_reuniao_e_entra_na_pauta_da_ordinaria_seguinte(com_as_ordinarias, item):
    banco, caso = com_as_ordinarias(item)

    _confirmar(banco, caso)

    assert _reunioes(banco) == []
    assert any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, "RD_dezembro"))
    assert not any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, "RD_janeiro"))
    assert not any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, "RD_novembro"))


def test_a_lesao_por_pressao_entra_na_pauta_da_ordinaria_seguinte_ja_montada(com_as_ordinarias):
    banco, caso = com_as_ordinarias()
    assert not any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, "RD_dezembro"))

    _confirmar(banco, caso)

    assert any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, "RD_dezembro"))
    assert not any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, "RD_janeiro"))


def test_a_lesao_por_pressao_com_obito_tem_a_reuniao_de_analise(com_as_ordinarias):
    banco, caso = com_as_ordinarias(grau_de_dano="obito")

    _confirmar(banco, caso)

    [reuniao] = _reunioes(banco)
    assert reuniao["data"] == "2026-11-23"
    assert not any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, "RD_dezembro"))


# ═══════════════════════════════════════════════════════════════════════════
# 3. A comunicação à Direção, na hora, só nas faixas A e B
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("sugestao", [OBITO, GRAVE], ids=["faixa A", "faixa B"])
def test_confirmar_a_ou_b_registra_o_aviso_a_diretoria_na_hora(enviados, sugestao):
    banco, caso = _caso_confirmado(sugestao)

    avisos = _avisos(banco, ao_confirmar.MARCO_DA_DIRECAO)
    assert sorted(a["destinatario_id"] for a in avisos) == ["P6", "P8"]
    for aviso in avisos:
        assert aviso["caso_id"] == caso["id"]
        assert aviso["urgente"] is True
        assert aviso["situacao"] == emails.ENVIADO
    para_a_direcao = [e for e in enviados if e["para"] in ("p6@hsm.test", "p8@hsm.test")]
    assert len(para_a_direcao) == 2
    for email in para_a_direcao:
        assert caso["protocolo"] in email["assunto"]
        assert caso["relato"] not in email["texto"]
        assert caso["relato"] not in email["html"]


@pytest.mark.parametrize("sugestao", [MODERADO, LEVE, QUASE_ERRO], ids=["faixa C", "faixa D", "faixa E"])
def test_confirmar_c_d_ou_e_nao_registra_o_aviso_a_diretoria(enviados, sugestao):
    banco, _ = _caso_confirmado(sugestao)

    assert _avisos(banco, ao_confirmar.MARCO_DA_DIRECAO) == []
    assert not [e for e in enviados if e["para"] in ("p6@hsm.test", "p8@hsm.test")]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Quem notificou fica sabendo que o caso está em análise
# ═══════════════════════════════════════════════════════════════════════════


def test_o_identificado_com_email_recebe_o_aviso_de_que_o_caso_esta_em_analise(enviados):
    banco, caso = _caso_confirmado(MODERADO)

    [aviso] = _avisos(banco, ao_confirmar.MARCO_DO_EM_ANALISE)
    assert aviso["caso_id"] == caso["id"]
    assert aviso["destinatario_id"] is None
    assert "notificante@hsm.test" not in str(aviso)
    # O aviso não é urgente: se a confirmação foi fora do expediente, o job
    # de 10 em 10 minutos o leva quando ele abre.
    emails.despachar_pendentes(banco, datetime(2030, 1, 7, 10, 0, tzinfo=SP))
    [email] = [e for e in enviados if e["para"] == "notificante@hsm.test"]
    assert caso["protocolo"] in email["assunto"]
    assert "em análise" in email["texto"]
    assert caso["relato"] not in email["texto"]


@pytest.mark.parametrize(
    "campos",
    [
        {"anonimo": True, "notificante_nome": None, "notificante_contato": None},
        {"notificante_contato": "21 99999-0000"},
    ],
    ids=["anônimo", "só telefone"],
)
def test_quem_nao_deixou_email_nao_gera_o_aviso(campos):
    banco, _ = _caso_confirmado(MODERADO, **campos)

    assert _avisos(banco, ao_confirmar.MARCO_DO_EM_ANALISE) == []


def test_o_anonimo_ve_o_estado_novo_na_pagina_de_acompanhamento():
    banco = _banco([], [])
    recibo = _cliente(banco).post(PUBLICO, json={**ANONIMO, "origem": "qr"}).json()
    [caso] = banco.notificacoes
    banco.tabelas["nsp_triagens"].append(_sugestao({**caso, "numero": 1}, **MODERADO))
    acompanhar = {"protocolo": recibo["protocolo"], "codigo": recibo["codigo_acompanhamento"]}
    assert _cliente(banco).post("/api/nsp/publico/acompanhamento", json=acompanhar).json()["estado"] == "Recebida"

    _confirmar(banco, caso)

    resposta = _cliente(banco).post("/api/nsp/publico/acompanhamento", json=acompanhar)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estado"] == "Em análise"
    assert _avisos(banco, ao_confirmar.MARCO_DO_EM_ANALISE) == []


# ═══════════════════════════════════════════════════════════════════════════
# 5. Confirmar duas vezes não cria segunda reunião nem segundo aviso
# ═══════════════════════════════════════════════════════════════════════════


def _o_que_a_confirmacao_criou(banco) -> tuple[int, int, int]:
    return (
        len(_reunioes(banco)),
        len(_avisos(banco, ao_confirmar.MARCO_DA_DIRECAO)),
        len(_avisos(banco, ao_confirmar.MARCO_DO_EM_ANALISE)),
    )


def test_confirmar_de_novo_o_caso_ja_classificado_nao_cria_segunda_reuniao_nem_segundo_aviso(enviados):
    banco, caso = _caso_confirmado(OBITO)
    assert _o_que_a_confirmacao_criou(banco) == (1, 2, 1)
    saidos = len(enviados)

    resposta = _cliente(banco).post(f"/api/nsp/triagem/{caso['id']}", json={"conferidos": TODOS_OS_CAMPOS})

    assert resposta.status_code == 409
    assert _o_que_a_confirmacao_criou(banco) == (1, 2, 1)
    assert len(enviados) == saidos


def test_a_nova_tentativa_da_confirmacao_que_caiu_no_meio_nao_cria_segunda_reuniao_nem_segundo_aviso(enviados):
    """A confirmação caiu antes de mudar o estado: a nova tentativa conclui
    com a reunião, a pauta e os avisos que a primeira já gravou."""
    banco, caso = _caso_confirmado(OBITO)
    [reuniao] = _reunioes(banco)
    saidos = len(enviados)
    banco.notificacoes[0]["estado"] = "recebida"

    _confirmar(banco, caso)

    assert _o_que_a_confirmacao_criou(banco) == (1, 2, 1)
    assert len(enviados) == saidos
    textos = _textos_da_pauta(banco, reuniao["id_reuniao"])
    assert sum(caso["protocolo"] in texto for texto in textos) == 1


def test_a_confirmacao_que_chega_junto_com_outra_fica_com_a_reuniao_da_primeira(monkeypatch):
    """Duas tentativas ao mesmo tempo: a segunda esbarra na reunião única por
    caso do banco e segue com a reunião que a primeira criou."""
    caso = _notificacao(1, **DO_CASO)
    banco = _banco([caso], [_sugestao(caso, **OBITO)])
    inserir = _Consulta._inserir

    def _a_outra_criou_primeiro(self):
        if self._nome == "reunioes" and not banco.tabelas.get("reunioes"):
            inserir(self)
            raise APIError({"code": "23505", "message": "duplicate key value"})
        return inserir(self)

    monkeypatch.setattr(_Consulta, "_inserir", _a_outra_criou_primeiro)

    _confirmar(banco, caso)

    [reuniao] = _reunioes(banco)
    assert any(caso["protocolo"] in texto for texto in _textos_da_pauta(banco, reuniao["id_reuniao"]))


# ═══════════════════════════════════════════════════════════════════════════
# 6. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_diz_o_que_acontece_ao_confirmar():
    from test_seguranca_do_paciente_prazos import _secao_do_kit

    no_ar = _secao_do_kit("O que já está no ar")
    for termo in (
        "a reunião de análise de evento já nasce programada na data-limite",
        "o protocolo do caso no bloco Casos da pauta",
        "entra na pauta da ordinária seguinte",
        "comunicação à Direção",
        "está em análise",
        "Confirmar de novo não cria outra reunião nem outro aviso",
    ):
        assert termo in no_ar, termo
    assert "a reunião de análise e o chamado" not in _secao_do_kit("O que ele ainda não faz")
