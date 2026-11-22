"""O período de sombra e a recalibração do agente do Núcleo (issue #2001,
PRD #1979, ADR 0107 decisão 10; Anexo F, seções 4, 5 e 7).

Um bloco por critério de aceite do backend:

1. a concordância entre a sugestão do agente e a decisão da Presidência, por
   eixo, na Configuração, com os casos em que a Presidência subiu o grau de
   dano sugerido listados à parte;
2. o job diário, sem IA e sem e-mail, cria a pendência "Recalibrar o agente do
   NSP" aos 30 e aos 60 dias da primeira notificação, uma vez cada, para quem
   tem Acesso pleno;
3. a tela dos itens do Anexo F calcula o que tem dado nesta fase e marca o
   resto como "sem dados nesta fase";
4. concluir a pendência exige uma das três decisões e grava quem decidiu e
   quando;
5. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória da tela de triagem. Nenhum dado de pessoa real.
"""

from __future__ import annotations

import inspect
import os
import sys
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_seguranca_do_paciente_notificacoes import (  # noqa: E402
    DIRETOR_EXECUTIVO,
    MEMBRO,
    NUCLEO,
    PRESIDENTE,
    SETOR,
    SETOR_DESATIVADO,
    SUPER_ADMIN,
    _participacao,
    _pessoa,
)
from test_seguranca_do_paciente_triagem import (  # noqa: E402
    GRAVE,
    MODERADO,
    OBITO,
    OUTRO_SETOR,
    QUASE_ERRO,
    _BancoDaTriagem,
    _ConsultaDaTriagem,
    _notificacao,
    _sugestao,
)

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_recalibracao as recalibracao_router  # noqa: E402
from app.services.seguranca_do_paciente import recalibracao  # noqa: E402

RECUSA = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}
CONCORDANCIA = "/api/nsp/configuracao/concordancia"
OUTRO_PLENO = _pessoa("P7", perfil_nsp="acesso_pleno")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


# ═══════════════════════════════════════════════════════════════════════════
# O dublê: a triagem, mais o `is_` e a função de ação da Pendência
# ═══════════════════════════════════════════════════════════════════════════


class _ConsultaDaRecalibracao(_ConsultaDaTriagem):
    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def _inserir(self) -> list[dict]:
        if self._nome == "nsp_recalibracoes":
            novas = self._valores if isinstance(self._valores, list) else [self._valores]
            for valores in novas:
                if any(r["marco"] == valores["marco"] for r in self._linhas):
                    raise APIError({"code": "23505", "message": "duplicate key value"})
                valores.setdefault("pendencias", [])
                valores.setdefault("decisao", None)
                valores.setdefault("decidido_por", None)
                valores.setdefault("decidido_em", None)
        return super()._inserir()


class _BancoDaRecalibracao(_BancoDaTriagem):
    def table(self, nome: str):
        return _ConsultaDaRecalibracao(self, nome)

    def rpc(self, nome: str, params: dict):
        """A função `registrar_acao_da_pendencia` (migration 169): confere o
        estado lido e muda a Pendência."""
        banco = self

        class _Exec:
            def execute(self_inner):  # noqa: N805
                assert nome == "registrar_acao_da_pendencia"
                pendencia = next(p for p in banco.tabelas["pendencias"] if p["id_acao"] == params["p_id_acao"])
                if pendencia["status"] != params["p_status_esperado"]:
                    raise APIError({"code": "PT409", "message": "A pendencia mudou."})
                pendencia["status"] = params["p_status_novo"]
                banco.tabelas.setdefault("pendencia_historico", []).append(dict(params))
                return type("R", (), {"data": None})()

        return _Exec()

    @property
    def recalibracoes(self) -> list[dict]:
        return self.tabelas.setdefault("nsp_recalibracoes", [])

    @property
    def pendencias(self) -> list[dict]:
        return self.tabelas.setdefault("pendencias", [])


def _banco(notificacoes: list[dict] | None = None, triagens: list[dict] | None = None, **tabelas):
    return _BancoDaRecalibracao(
        {
            "participantes": [dict(p) for p in (PRESIDENTE, MEMBRO, SUPER_ADMIN, DIRETOR_EXECUTIVO)],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [_participacao("P1", "presidencia"), _participacao("P2", "membro")],
            "setores": [dict(SETOR)],
            "nsp_notificacoes": [dict(n) for n in (notificacoes or [])],
            "nsp_triagens": [dict(t) for t in (triagens or [])],
            "pendencias": [],
            **tabelas,
        }
    )


def _cliente(banco: _BancoDaRecalibracao, pessoa: dict[str, Any] = PRESIDENTE) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(recalibracao_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _decisao(notificacao: dict, divergencias: list[str] | None, **campos) -> dict[str, Any]:
    """A linha da pessoa: a triagem confirmada, com as divergências."""
    return {
        **_sugestao(notificacao, versao=9, **campos),
        "id": f"dec-{notificacao['numero']}",
        "autor_tipo": "pessoa",
        "autor_id": "P1",
        "divergencias": divergencias,
        "criado_em": notificacao["criado_em"].replace("T10:", "T12:"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. A concordância por eixo, na Configuração
# ═══════════════════════════════════════════════════════════════════════════


def _cenario_da_concordancia() -> _BancoDaRecalibracao:
    acatada, subiu, categoria, manual, canal = (_notificacao(n, estado="classificada") for n in range(1, 6))
    return _banco(
        [acatada, subiu, categoria, manual, canal],
        [
            _sugestao(acatada),
            _decisao(acatada, []),
            _sugestao(subiu, **MODERADO),
            _decisao(subiu, ["grau_de_dano", "faixa"], **GRAVE),
            _sugestao(categoria),
            _decisao(categoria, ["categoria"], categoria="MED"),
            # Classificar manualmente: não havia sugestão, não entra na conta.
            _decisao(manual, None),
            _sugestao(canal),
            _decisao(canal, ["canais", "iras"], canais=["NSP", "SST"], iras=True),
        ],
    )


def test_a_configuracao_mostra_a_concordancia_por_eixo_so_dos_casos_com_sugestao():
    resposta = _cliente(_cenario_da_concordancia()).get(CONCORDANCIA)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["casos"] == 4
    assert [(e["rotulo"], e["acatadas"], e["total"], e["percentual"]) for e in corpo["eixos"]] == [
        ("Natureza", 4, 4, 100),
        ("Grau de dano", 3, 4, 75),
        ("Categoria", 3, 4, 75),
        ("Faixa", 3, 4, 75),
        ("Canal", 3, 4, 75),
        ("Marcadores", 3, 4, 75),
    ]


def test_os_casos_em_que_a_presidencia_subiu_o_grau_aparecem_a_parte():
    corpo = _cliente(_cenario_da_concordancia()).get(CONCORDANCIA).json()

    assert corpo["erros_para_baixo"] == [
        {
            "notificacao_id": "00000000-0000-0000-0000-000000000002",
            "protocolo": "NSP-2026-0002",
            "sugerido": "moderado",
            "decidido": "grave",
            "grave_ou_obito": True,
        }
    ]


FORA_DO_NSP = {"natureza": "nao_e_do_nsp", "grau_de_dano": "nao_se_aplica", "faixa": "nao_se_aplica"}


def _cenario_do_fora_do_nsp() -> _BancoDaRecalibracao:
    """O agente nem tratou como incidente; a Presidência decidiu óbito."""
    caso = _notificacao(1, estado="classificada", criado_em="2026-11-29T13:00:00+00:00")
    return _banco([caso], [_sugestao(caso, **FORA_DO_NSP), _decisao(caso, ["natureza", "grau_de_dano"], **OBITO)])


def test_o_obito_que_o_agente_nem_tratou_como_incidente_e_erro_para_baixo():
    corpo = _cliente(_cenario_do_fora_do_nsp()).get(CONCORDANCIA).json()

    assert corpo["erros_para_baixo"] == [
        {
            "notificacao_id": "00000000-0000-0000-0000-000000000001",
            "protocolo": "NSP-2026-0001",
            "sugerido": "nao_se_aplica",
            "decidido": "obito",
            "grave_ou_obito": True,
        }
    ]


def test_o_obito_que_o_agente_nem_tratou_como_incidente_acende_o_item_3():
    tela = recalibracao.tela(_cenario_do_fora_do_nsp(), date(2026, 11, 30))
    item = next(i for i in tela["itens"] if i["numero"] == 3)

    assert item["linhas"] == [
        "1 caso com o grau de dano subido pela Presidência.",
        "NSP-2026-0001: sugerido não se aplica, decidido óbito",
    ]
    assert item["alerta"] is True


def test_a_configuracao_diz_as_versoes_do_prompt_e_da_base_em_uso():
    corpo = _cliente(_banco()).get(CONCORDANCIA).json()

    assert corpo["versoes"] == {"prompt": "1.0.2", "base": "1.1"}
    assert corpo["casos"] == 0
    assert all(e["percentual"] is None for e in corpo["eixos"])


@pytest.mark.parametrize("pessoa", [MEMBRO, SUPER_ADMIN])
def test_quem_nao_confirma_triagem_nao_ve_a_concordancia(pessoa):
    resposta = _cliente(_cenario_da_concordancia(), pessoa).get(CONCORDANCIA)

    assert resposta.status_code == 403
    assert resposta.json() == RECUSA


# ═══════════════════════════════════════════════════════════════════════════
# 2. A pendência aos 30 e aos 60 dias, uma vez cada, sem e-mail
# ═══════════════════════════════════════════════════════════════════════════

# A primeira notificação registrada chega em 01/10/2026, às 22h de Brasília
# (01h de 02/10 em UTC): o dia que conta é o de Brasília.
PRIMEIRA = _notificacao(1, criado_em="2026-10-02T01:00:00+00:00")
DEPOIS = _notificacao(2, criado_em="2026-10-20T10:00:00+00:00")
TRINTA_DIAS = date(2026, 10, 31)
SESSENTA_DIAS = date(2026, 11, 30)


def _cenario_do_lembrete(*pessoas: dict) -> _BancoDaRecalibracao:
    banco = _banco([DEPOIS, PRIMEIRA])
    banco.tabelas["participantes"].extend(dict(p) for p in pessoas)
    return banco


def _recalibrar(banco: _BancoDaRecalibracao) -> list[dict]:
    return [p for p in banco.pendencias if p["descricao_acao"].startswith("Recalibrar o agente do NSP")]


def test_aos_30_dias_nasce_a_pendencia_para_cada_pessoa_com_acesso_pleno():
    banco = _cenario_do_lembrete(OUTRO_PLENO)

    criadas = recalibracao.lembrar(banco, TRINTA_DIAS)

    assert criadas == 2
    pendencias = _recalibrar(banco)
    assert sorted(p["responsavel_id"] for p in pendencias) == ["P5", "P7"]
    assert all(p["descricao_acao"] == "Recalibrar o agente do NSP (30 dias)" for p in pendencias)
    assert all(p.get("id_reuniao") is None and p["status"] == "PENDENTE" for p in pendencias)
    assert banco.recalibracoes[0]["marco"] == 30
    assert sorted(banco.recalibracoes[0]["pendencias"]) == sorted(p["id_acao"] for p in pendencias)


def test_antes_dos_30_dias_nada_nasce():
    banco = _cenario_do_lembrete()

    assert recalibracao.lembrar(banco, TRINTA_DIAS - timedelta(days=1)) == 0
    assert _recalibrar(banco) == []
    assert banco.recalibracoes == []


def test_cada_marco_nasce_uma_vez_so():
    banco = _cenario_do_lembrete()

    recalibracao.lembrar(banco, TRINTA_DIAS)
    assert recalibracao.lembrar(banco, TRINTA_DIAS) == 0
    assert recalibracao.lembrar(banco, TRINTA_DIAS + timedelta(days=5)) == 0
    assert recalibracao.lembrar(banco, SESSENTA_DIAS) == 1
    assert recalibracao.lembrar(banco, SESSENTA_DIAS + timedelta(days=1)) == 0

    assert [p["descricao_acao"] for p in _recalibrar(banco)] == [
        "Recalibrar o agente do NSP (30 dias)",
        "Recalibrar o agente do NSP (60 dias)",
    ]


def test_a_rodada_que_caiu_no_meio_nao_repete_a_pendencia_na_seguinte(monkeypatch):
    """O marco gravou, a primeira pendência nasceu e a segunda falhou."""
    banco = _cenario_do_lembrete(OUTRO_PLENO)
    criar = recalibracao.criar_pendencia_sem_reuniao
    chamadas = []

    def _cai_na_segunda(supabase, item):
        chamadas.append(item)
        if len(chamadas) == 2:
            raise APIError({"code": "57014", "message": "statement timeout"})
        return criar(supabase, item)

    monkeypatch.setattr(recalibracao, "criar_pendencia_sem_reuniao", _cai_na_segunda)
    with pytest.raises(APIError):
        recalibracao.lembrar(banco, TRINTA_DIAS)
    monkeypatch.setattr(recalibracao, "criar_pendencia_sem_reuniao", criar)

    assert recalibracao.lembrar(banco, TRINTA_DIAS + timedelta(days=1)) == 1

    pendencias = _recalibrar(banco)
    assert sorted(p["responsavel_id"] for p in pendencias) == ["P5", "P7"]
    assert sorted(banco.recalibracoes[0]["pendencias"]) == sorted(p["id_acao"] for p in pendencias)


def test_a_rodada_que_nao_gravou_a_lista_nao_cria_de_novo():
    """Todas nasceram e o update da lista no marco falhou."""
    banco = _cenario_do_lembrete(OUTRO_PLENO)
    recalibracao.lembrar(banco, TRINTA_DIAS)
    banco.recalibracoes[0]["pendencias"] = []

    assert recalibracao.lembrar(banco, TRINTA_DIAS + timedelta(days=1)) == 0

    pendencias = _recalibrar(banco)
    assert len(pendencias) == 2
    assert sorted(banco.recalibracoes[0]["pendencias"]) == sorted(p["id_acao"] for p in pendencias)


def test_a_pendencia_nao_vai_para_quem_nao_tem_acesso_pleno_nem_para_o_desligado():
    banco = _cenario_do_lembrete(_pessoa("P8", perfil_nsp="acesso_pleno", ativo=False))

    recalibracao.lembrar(banco, TRINTA_DIAS)

    assert [p["responsavel_id"] for p in _recalibrar(banco)] == ["P5"]


def test_sem_notificacao_nenhuma_nada_nasce():
    banco = _banco()

    assert recalibracao.lembrar(banco, SESSENTA_DIAS) == 0
    assert banco.recalibracoes == []


def test_o_marco_sem_ninguem_com_acesso_pleno_nasce_quando_alguem_chega():
    banco = _banco([PRIMEIRA])
    banco.tabelas["participantes"] = [dict(PRESIDENTE)]

    assert recalibracao.lembrar(banco, TRINTA_DIAS) == 0
    banco.tabelas["participantes"].append(dict(DIRETOR_EXECUTIVO))
    assert recalibracao.lembrar(banco, TRINTA_DIAS + timedelta(days=1)) == 1
    assert [p["responsavel_id"] for p in _recalibrar(banco)] == ["P5"]


# O que denuncia IA ou e-mail no código: os módulos do app que falam com
# provedor de modelo ou de e-mail e os SDKs.
_MARCAS_DE_IA_E_EMAIL = ("ai_processor", "anthropic", "openai", "openrouter", "email", "resend", "smtp")


def _marcas(codigo: str) -> list[str]:
    return [marca for marca in _MARCAS_DE_IA_E_EMAIL if marca in codigo.lower()]


def test_o_detector_reconhece_um_modulo_que_chama_ia_e_email():
    """Piso do detector: o agente de triagem e o serviço de e-mail têm marca."""
    from app.services import email_service
    from app.services.seguranca_do_paciente import agente_de_triagem

    assert _marcas(inspect.getsource(agente_de_triagem))
    assert _marcas(inspect.getsource(email_service))


def test_o_job_nao_fala_com_ia_nem_com_email():
    from app.cron import scheduler

    assert _marcas(inspect.getsource(recalibracao.lembrar)) == []
    assert _marcas(inspect.getsource(scheduler.lembrar_recalibracao_do_agente)) == []
    assert "recalibracao.lembrar(" in inspect.getsource(scheduler.lembrar_recalibracao_do_agente)
    assert 'lembrar_recalibracao_do_agente,\n        "cron"' in inspect.getsource(scheduler.start_scheduler)


# ═══════════════════════════════════════════════════════════════════════════
# 3. A tela dos itens do Anexo F
# ═══════════════════════════════════════════════════════════════════════════

TELA = "/api/nsp/recalibracao"
HOJE_DA_AUDITORIA = date(2026, 11, 30)
# Os itens que dependem das Fases 3 e 4 (investigação, plano de ação,
# notificação externa, dossiê) e do encaminhamento, que ainda não chegaram, e
# a carga que a coordenadora estima.
SEM_DADOS = {5, 7, 9, 14, 15, 17, 18, 19}


def _decidida(notificacao: dict, divergencias: list[str], em: str, **campos) -> dict[str, Any]:
    return {**_decisao(notificacao, divergencias, **campos), "criado_em": em}


def _cenario_da_auditoria() -> _BancoDaRecalibracao:
    """Quatro casos decididos e um esperando, em 30/11/2026."""
    obito = _notificacao(1, estado="classificada", criado_em="2026-11-29T13:00:00+00:00")
    subiu = _notificacao(2, estado="classificada", criado_em="2026-11-20T10:00:00+00:00", anonimo=True)
    leve = _notificacao(3, estado="classificada", criado_em="2026-11-10T10:00:00+00:00", setor_id=OUTRO_SETOR["id"])
    antigo = _notificacao(4, estado="em_analise_agregada", criado_em="2026-10-15T10:00:00+00:00")
    esperando = _notificacao(5, criado_em="2026-11-25T10:00:00+00:00")
    nucleo, outro = NUCLEO["id"], "col-outro"
    return _banco(
        [obito, subiu, leve, antigo, esperando],
        [
            _sugestao(obito, **OBITO),
            _decidida(obito, [], "2026-11-29T18:00:00+00:00", **OBITO),
            _sugestao(subiu, **MODERADO),
            _decidida(subiu, ["grau_de_dano", "faixa"], "2026-11-20T12:00:00+00:00", **GRAVE),
            _sugestao(leve, perguntas_ao_notificante=["Quando foi?"]),
            _decidida(leve, [], "2026-11-10T11:00:00+00:00"),
            _sugestao(antigo, **QUASE_ERRO),
            _decidida(antigo, ["categoria"], "2026-10-15T10:30:00+00:00", categoria="MED", **QUASE_ERRO),
            # Quem notificou respondeu uma das duas perguntas, e o agente, de
            # novo, mudou a faixa de E para D.
            _sugestao(esperando, perguntas_ao_notificante=["Houve dano?", "Qual equipamento?"], **QUASE_ERRO),
            _sugestao(esperando, versao=2),
        ],
        nsp_esclarecimentos=[
            {
                "id": "esc-1",
                "notificacao_id": esperando["id"],
                "triagem_id": "tri-5-1",
                "pergunta": "Houve dano?",
                "resposta": "Não houve.",
                "criado_em": "2026-11-25T11:00:00+00:00",
            }
        ],
        setores=[dict(SETOR), dict(OUTRO_SETOR)],
        reunioes=[
            {
                "id_reuniao": "R1",
                "colegiado_id": nucleo,
                "tipo": "Ordinária mensal",
                "data": "2026-11-12",
                "status_ata": "ASSINADA",
                "deleted_at": None,
            },
            {
                "id_reuniao": "R2",
                "colegiado_id": nucleo,
                "tipo": "Análise de evento",
                "data": "2026-10-20",
                "status_ata": "PROCESSANDO",
                "deleted_at": None,
            },
            {
                "id_reuniao": "R3",
                "colegiado_id": nucleo,
                "tipo": "Ordinária mensal",
                "data": "2026-08-10",
                "status_ata": "ASSINADA",
                "deleted_at": None,
            },
            {
                "id_reuniao": "R4",
                "colegiado_id": outro,
                "tipo": "Ordinária mensal",
                "data": "2026-11-12",
                "status_ata": "ASSINADA",
                "deleted_at": None,
            },
            {
                "id_reuniao": "R5",
                "colegiado_id": None,
                "tipo": "Mensal",
                "data": "2026-11-12",
                "status_ata": "ASSINADA",
                "deleted_at": None,
            },
        ],
    )


def _itens() -> dict[int, dict]:
    tela = recalibracao.tela(_cenario_da_auditoria(), HOJE_DA_AUDITORIA)
    return {item["numero"]: item for item in tela["itens"]}


def test_a_tela_traz_os_19_itens_e_marca_os_que_nao_tem_dados_nesta_fase():
    itens = _itens()

    assert sorted(itens) == list(range(1, 20))
    assert {n for n, item in itens.items() if item["secao"] == 4} == set(range(1, 12))
    assert {n for n, item in itens.items() if not item["com_dados"]} == SEM_DADOS
    assert all(item["linhas"] == [] and not item["alerta"] for n, item in itens.items() if n in SEM_DADOS)
    assert itens[2]["titulo"] == "Concordância agente e coordenação"
    assert itens[2]["sinal"] == "Abaixo de 85% em grau de dano"


def test_volume_anonimas_e_tendencia_contam_os_ultimos_30_dias():
    itens = _itens()

    assert itens[1]["linhas"] == ["4 notificações nos últimos 30 dias.", "UTI Adulto: 3", "Centro Cirúrgico: 1"]
    assert itens[10]["linhas"] == ["1 de 4 notificações sem identificação nos últimos 30 dias (25%)."]
    assert itens[10]["alerta"] is False
    assert itens[12]["linhas"] == ["Últimos 30 dias: 4. Os 30 dias anteriores: 1."]
    assert itens[12]["alerta"] is False


def test_o_setor_sem_notificacao_nos_ultimos_30_dias_aparece_e_acende_o_item_1():
    banco = _cenario_da_auditoria()
    banco.tabelas["setores"] += [
        {"id": "55555555-5555-5555-5555-555555555555", "nome": "Pronto-socorro", "ativo": True},
        {"id": "66666666-6666-6666-6666-666666666666", "nome": "Farmácia", "ativo": True},
        dict(SETOR_DESATIVADO),
    ]

    item = next(i for i in recalibracao.tela(banco, HOJE_DA_AUDITORIA)["itens"] if i["numero"] == 1)

    assert item["linhas"] == [
        "4 notificações nos últimos 30 dias.",
        "UTI Adulto: 3",
        "Centro Cirúrgico: 1",
        "Setores sem notificação nos últimos 30 dias: Farmácia, Pronto-socorro.",
    ]
    assert item["alerta"] is True


def test_com_todo_setor_notificando_o_item_1_fica_apagado():
    assert _itens()[1]["alerta"] is False


def test_concordancia_e_erros_para_baixo_acendem_o_sinal_de_alerta():
    itens = _itens()

    assert "Grau de dano: 75% (3 de 4)" in itens[2]["linhas"]
    assert itens[2]["alerta"] is True
    assert itens[3]["linhas"] == [
        "1 caso com o grau de dano subido pela Presidência.",
        "NSP-2026-0002: sugerido moderado, decidido grave",
    ]
    assert itens[3]["alerta"] is True


def test_lista_anvisa_tempo_de_triagem_e_amostra():
    itens = _itens()

    assert itens[4]["linhas"] == [
        "Marcados pelo agente como evento que nunca deveria ocorrer: 0 sim e 0 possível.",
        "Graves ou com óbito sem marcação na decisão: 2.",
        "Marcados pela Presidência e não reconhecidos pelo agente: 0.",
    ]
    assert itens[6]["linhas"] == [
        "Faixa A: 5,0 horas corridas em média (1 caso)",
        "Faixa B: 2,0 horas corridas em média (1 caso)",
        "Faixa D: 1,0 hora corrida em média (1 caso)",
        "Faixa E: 0,5 hora corrida em média (1 caso)",
    ]
    assert itens[6]["alerta"] is True
    assert itens[11]["linhas"] == ["NSP-2026-0001", "NSP-2026-0002", "NSP-2026-0003", "NSP-2026-0004"]


def test_aprovacao_em_lote_mede_os_casos_leves_das_ultimas_4_semanas():
    itens = _itens()

    assert itens[13]["linhas"] == [
        "Casos leves (faixas D e E) confirmados nas últimas 4 semanas: 1 de 1 sem ajuste (100%)."
    ]
    assert itens[13]["alerta"] is False


def test_perguntas_de_esclarecimento_respondidas_e_as_que_mudaram_a_classificacao():
    itens = _itens()

    assert itens[8]["linhas"] == [
        "1 de 3 perguntas respondidas (33%).",
        "1 de 1 caso com resposta com a classificação do agente mudada depois dela (100%).",
    ]
    assert itens[8]["alerta"] is False


def test_reunioes_do_nucleo_nos_ultimos_60_dias():
    itens = _itens()

    assert itens[16]["linhas"] == [
        "2 reuniões do Núcleo nos últimos 60 dias, 1 com ata assinada.",
        "Ordinárias mensais nos últimos 30 dias: 1.",
    ]
    assert itens[16]["alerta"] is False


@pytest.mark.parametrize("status", ["PROGRAMADA", "CANCELADA", "NAO_INSTALADA"])
def test_a_ordinaria_que_nao_aconteceu_nao_conta_e_acende_o_item_16(status):
    """O calendário anual cria as 12 ordinárias de antemão como PROGRAMADA."""
    banco = _cenario_da_auditoria()
    ordinaria = next(r for r in banco.tabelas["reunioes"] if r["id_reuniao"] == "R1")
    ordinaria["status_ata"] = status

    item = next(i for i in recalibracao.tela(banco, HOJE_DA_AUDITORIA)["itens"] if i["numero"] == 16)

    assert item["linhas"] == [
        "1 reunião do Núcleo nos últimos 60 dias, 0 com ata assinada.",
        "Ordinárias mensais nos últimos 30 dias: 0.",
    ]
    assert item["alerta"] is True


def test_a_tela_abre_pela_rota_com_os_itens():
    banco = _cenario_da_auditoria()

    corpo = _cliente(banco, DIRETOR_EXECUTIVO).get(TELA).json()

    assert len(corpo["itens"]) == 19
    assert [d["valor"] for d in corpo["decisoes"]] == ["manter", "ajustar", "ligar_lote"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Concluir exige uma das três decisões e grava quem decidiu e quando
# ═══════════════════════════════════════════════════════════════════════════

AGORA = datetime(2026, 11, 2, 13, 0, tzinfo=UTC)


def _decidir(marco: int) -> str:
    return f"/api/nsp/recalibracao/{marco}"


def _com_o_marco_de_30() -> _BancoDaRecalibracao:
    banco = _cenario_do_lembrete(OUTRO_PLENO)
    recalibracao.lembrar(banco, TRINTA_DIAS)
    return banco


# "ligar_lote" pede 90% de concordância nos casos leves: o teste dele está em
# test_seguranca_do_paciente_aprovacao_em_lote.py (issue #2002).
@pytest.mark.parametrize("decisao", ["manter", "ajustar"])
def test_concluir_grava_a_decisao_quem_decidiu_e_quando_e_fecha_as_pendencias(decisao, monkeypatch):
    banco = _com_o_marco_de_30()
    monkeypatch.setattr(recalibracao_router, "agora_utc", lambda: AGORA)

    resposta = _cliente(banco, DIRETOR_EXECUTIVO).post(_decidir(30), json={"decisao": decisao})

    assert resposta.status_code == 200, resposta.text
    linha = banco.recalibracoes[0]
    assert (linha["decisao"], linha["decidido_por"], linha["decidido_em"]) == (
        decisao,
        "P5",
        "2026-11-02T13:00:00+00:00",
    )
    assert [p["status"] for p in _recalibrar(banco)] == ["CONCLUIDO", "CONCLUIDO"]
    marco = next(r for r in resposta.json()["recalibracoes"] if r["marco"] == 30)
    assert marco["decidido_por"] == "Pessoa de Teste P5"


@pytest.mark.parametrize("corpo", [{}, {"decisao": ""}, {"decisao": "desligar"}, {"decisao": None}])
def test_concluir_sem_uma_das_tres_decisoes_e_recusado(corpo):
    banco = _com_o_marco_de_30()

    resposta = _cliente(banco, DIRETOR_EXECUTIVO).post(_decidir(30), json=corpo)

    assert resposta.status_code == 422
    assert banco.recalibracoes[0]["decisao"] is None
    assert [p["status"] for p in _recalibrar(banco)] == ["PENDENTE", "PENDENTE"]


def test_a_decisao_gravada_nao_muda_depois():
    banco = _com_o_marco_de_30()
    _cliente(banco, DIRETOR_EXECUTIVO).post(_decidir(30), json={"decisao": "manter"})

    resposta = _cliente(banco, OUTRO_PLENO).post(_decidir(30), json={"decisao": "ligar_lote"})

    assert resposta.status_code == 409
    assert (banco.recalibracoes[0]["decisao"], banco.recalibracoes[0]["decidido_por"]) == ("manter", "P5")


def test_o_marco_que_ainda_nao_chegou_nao_se_decide():
    banco = _com_o_marco_de_30()

    assert _cliente(banco, DIRETOR_EXECUTIVO).post(_decidir(60), json={"decisao": "manter"}).status_code == 404


def test_a_presidencia_le_a_tela_mas_so_o_acesso_pleno_decide():
    banco = _com_o_marco_de_30()

    tela = _cliente(banco, PRESIDENTE).get(TELA)
    resposta = _cliente(banco, PRESIDENTE).post(_decidir(30), json={"decisao": "manter"})

    assert tela.status_code == 200, tela.text
    assert tela.json()["pode_decidir"] is False
    assert _cliente(banco, DIRETOR_EXECUTIVO).get(TELA).json()["pode_decidir"] is True
    assert resposta.status_code == 403
    assert banco.recalibracoes[0]["decisao"] is None


@pytest.mark.parametrize("pessoa", [MEMBRO, SUPER_ADMIN])
def test_quem_nao_confirma_triagem_nao_abre_a_recalibracao(pessoa):
    banco = _com_o_marco_de_30()

    assert _cliente(banco, pessoa).get(TELA).json() == RECUSA
    assert _cliente(banco, pessoa).post(_decidir(30), json={"decisao": "manter"}).status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 5. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def test_o_kit_diz_a_concordancia_a_pendencia_a_tela_e_as_tres_decisoes():
    """O Assistente responde "quando o agente é recalibrado?" e "quem decide?"
    pelo kit. Mutante: apagar o bloco da recalibração."""
    from test_kit_conhecimento import _secao, _texto

    no_ar = _secao(_texto("seguranca-do-paciente.md"), "O que já está no ar")
    for termo in (
        "Concordância do agente",
        "subiu o grau de dano sugerido",
        "aos 30 e aos 60 dias da primeira notificação registrada",
        '"Recalibrar o agente do NSP", uma vez cada, sem e-mail',
        "Sem dados nesta fase",
        "manter o agente como está, ajustar o prompt e a base, ou ligar a aprovação em lote",
        "gravada com o nome de quem decidiu e o dia",
    ):
        assert termo in no_ar, termo
