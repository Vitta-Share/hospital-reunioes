"""Rotina e Verificação por ciclo de calendário (ADR 0098, decisão 9; issue #1874).

A Rotina nasce do envio da Ata (linha do tipo Rotina), com responsável e
frequência, e começa no primeiro ciclo inteiro depois do envio. A Verificação
não é criada por job: o ciclo vem da data e a linha só é gravada quando alguém
marca. O responsável marca; o Facilitador marca por ele. Não realizada pede
anotação, a marcação depois do ciclo fica atrasada, e encerrar pede anotação e
para os ciclos seguintes. A Verificação em aberto aparece na Minha Fila do
responsável.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# O `make_client` importado registra a fábrica de TestClient do envio aqui.
from test_pendencia_nasce_no_envio import _sb, make_client  # noqa: E402, F401

from app.services import rotina_service  # noqa: E402

D = date.fromisoformat


@pytest.fixture
def hoje(monkeypatch):
    """O dia do servidor, em Brasília, controlado pelo teste."""
    dia = {"valor": D("2026-11-19")}  # uma quinta-feira
    monkeypatch.setattr(rotina_service, "hoje_em_brasilia", lambda: dia["valor"])
    return dia


@pytest.fixture
def cliente(request):
    return request.getfixturevalue("make_client")


def _sem_clicksign(monkeypatch):
    from app.services import clicksign_service

    monkeypatch.setattr(clicksign_service, "start_signature_flow", lambda *_a, **_kw: None)


QUADRO = [
    {"acao": "Comprar insumos", "responsavel": "Pedro Rezende", "prazo": "2026-12-10", "tipo": "ACAO"},
    {"acao": "Reunir a equipe", "responsavel": "Ana Lima", "tipo": "ROTINA", "frequencia": "SEMANAL"},
    {
        "acao": "Conferir o carrinho de parada",
        "responsavel": "Pedro Rezende",
        "tipo": "ROTINA",
        "frequencia": "QUINZENAL",
    },
    {"acao": "Toda alta passa pelo checklist", "responsavel": None, "tipo": "PROCESSO"},
]


def _sb_com_quadro():
    sb = _sb()
    sb.reunioes[0]["json_ata"] = {"quadro_atribuicoes": [dict(a) for a in QUADRO]}
    return sb


# ─── 1. A Rotina nasce do envio da Ata ───────────────────────────────────────


@pytest.mark.parametrize("rota", ["aprovar", "aprovar-sem-assinatura"])
def test_enviar_a_ata_cria_a_rotina_com_responsavel_frequencia_e_primeiro_ciclo(cliente, monkeypatch, hoje, rota):
    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro()

    r = cliente(sb).post(f"/api/reunioes/R1/{rota}")

    assert r.status_code == 200, r.text
    rotinas = sorted(sb.rotinas, key=lambda x: x["quadro_pos"])
    assert [
        (x["quadro_pos"], x["descricao"], x["responsavel_id"], x["frequencia"], x["comeca_em"], x["status"])
        for x in rotinas
    ] == [
        # Enviada numa quinta: a semana pela metade não conta.
        (1, "Reunir a equipe", "P2", "SEMANAL", "2026-11-23", "ATIVA"),
        (2, "Conferir o carrinho de parada", "P1", "QUINZENAL", "2026-12-01", "ATIVA"),
    ]
    # A Rotina não é Pendência.
    assert sorted(p["quadro_pos"] for p in sb.pendencias) == [0]


def test_reenviar_nao_cria_a_rotina_duas_vezes(cliente, monkeypatch, hoje):
    from app.services.pendencia_service import liberar_pendencias

    _sem_clicksign(monkeypatch)
    sb = _sb_com_quadro()
    assert cliente(sb).post("/api/reunioes/R1/aprovar").status_code == 200

    liberar_pendencias(sb, "R1", origem="RECONCILIACAO")

    assert len(sb.rotinas) == 2


# ─── 2. Marcar a Verificação e encerrar a Rotina ─────────────────────────────

ANA = {"id": "P2", "nome_completo": "Ana Lima", "access_profile": "regular", "email": "ana@hsm.com"}
PEDRO = {"id": "P1", "nome_completo": "Pedro Rezende", "access_profile": "regular", "email": "pedro@hsm.com"}
OUTRO = {"id": "P3", "nome_completo": "Bruno Souza", "access_profile": "regular", "email": "bruno@hsm.com"}
ADMIN = {"id": "P9", "nome_completo": "Diretor", "access_profile": "super_admin", "email": "dir@hsm.com"}


def _sb_com_rotina(**rotina):
    """Reunião R1 facilitada por P1, com a Rotina semanal de Ana (P2) que
    começou na semana de 23/11/2026."""
    sb = _sb()
    sb.rotinas.append(
        {
            "id": "RT1",
            "id_reuniao": "R1",
            "quadro_pos": 1,
            "descricao": "Reunir a equipe",
            "responsavel_id": "P2",
            "responsavel_nome": "Ana Lima",
            "frequencia": "SEMANAL",
            "comeca_em": "2026-11-23",
            "status": "ATIVA",
            "encerrada_em": None,
            "anotacao_encerramento": None,
            **rotina,
        }
    )
    return sb


@pytest.fixture
def cliente_das_rotinas(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.dependencies import get_current_user, get_supabase_client, require_acesso_reunioes
    from app.routers import rotinas as rotinas_router

    def _factory(sb, quem: dict, ocultas: list[str] | None = None) -> TestClient:
        app = FastAPI()
        app.include_router(rotinas_router.router, prefix="/api")
        app.dependency_overrides[get_current_user] = lambda: {"id": "auth", "email": quem["email"]}
        app.dependency_overrides[get_supabase_client] = lambda: sb
        app.dependency_overrides[require_acesso_reunioes] = lambda: None

        async def _me(*_a, **_kw):
            return dict(quem)

        monkeypatch.setattr(rotinas_router, "get_participante_for_user", _me)
        monkeypatch.setattr(rotinas_router, "reunioes_ocultas", lambda *_a, **_kw: list(ocultas or []))
        return TestClient(app)

    return _factory


def test_realizada_e_um_clique_do_responsavel(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, ANA).post("/api/rotinas/RT1/ciclos/2026-11-23/realizada")

    assert r.status_code == 201, r.text
    [v] = sb.rotina_verificacoes
    assert (v["rotina_id"], v["ciclo_inicio"], v["ciclo_fim"], v["resultado"], v["atrasada"]) == (
        "RT1",
        "2026-11-23",
        "2026-11-29",
        "REALIZADA",
        False,
    )
    assert (v["marcada_por_id"], v["marcada_por_nome"]) == ("P2", "Ana Lima")


@pytest.mark.parametrize("corpo", [{}, {"anotacao": ""}, {"anotacao": "   "}])
def test_nao_realizada_sem_anotacao_e_recusada(cliente_das_rotinas, hoje, corpo):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, ANA).post("/api/rotinas/RT1/ciclos/2026-11-23/nao-realizada", json=corpo)

    assert r.status_code == 422, r.text
    assert sb.rotina_verificacoes == []


def test_nao_realizada_com_anotacao_e_gravada(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, ANA).post(
        "/api/rotinas/RT1/ciclos/2026-11-23/nao-realizada", json={"anotacao": "A equipe estava de plantão."}
    )

    assert r.status_code == 201, r.text
    [v] = sb.rotina_verificacoes
    assert (v["resultado"], v["anotacao"]) == ("NAO_REALIZADA", "A equipe estava de plantão.")


def test_marcada_depois_do_ciclo_fica_registrada_como_atrasada(cliente_das_rotinas, hoje):
    # O ciclo de 23/11 a 29/11 fechou; marcar em 02/12 ainda vale, com atraso.
    hoje["valor"] = D("2026-12-02")
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, ANA).post("/api/rotinas/RT1/ciclos/2026-11-23/realizada")

    assert r.status_code == 201, r.text
    assert sb.rotina_verificacoes[0]["atrasada"] is True


def test_o_facilitador_marca_pelo_responsavel(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, PEDRO).post("/api/rotinas/RT1/ciclos/2026-11-23/realizada")

    assert r.status_code == 201, r.text
    assert sb.rotina_verificacoes[0]["marcada_por_id"] == "P1"


def test_quem_nao_e_responsavel_nem_facilitador_nao_marca(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, OUTRO).post("/api/rotinas/RT1/ciclos/2026-11-23/realizada")

    assert r.status_code == 404, r.text
    assert sb.rotina_verificacoes == []


@pytest.mark.parametrize(
    "inicio",
    [
        "2026-11-16",  # antes do primeiro ciclo
        "2026-11-30",  # ciclo que ainda não começou
        "2026-11-24",  # não é o primeiro dia de um ciclo
    ],
)
def test_ciclo_que_nao_existe_pela_data_e_recusado(cliente_das_rotinas, hoje, inicio):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, ANA).post(f"/api/rotinas/RT1/ciclos/{inicio}/realizada")

    assert r.status_code == 422, r.text
    assert sb.rotina_verificacoes == []


def test_o_mesmo_ciclo_nao_se_marca_duas_vezes(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()
    client = cliente_das_rotinas(sb, ANA)
    assert client.post("/api/rotinas/RT1/ciclos/2026-11-23/realizada").status_code == 201

    r = client.post("/api/rotinas/RT1/ciclos/2026-11-23/nao-realizada", json={"anotacao": "mudei"})

    assert r.status_code == 409, r.text
    assert len(sb.rotina_verificacoes) == 1


@pytest.mark.parametrize("corpo", [{}, {"anotacao": "  "}])
def test_encerrar_sem_anotacao_e_recusado(cliente_das_rotinas, hoje, corpo):
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, PEDRO).post("/api/rotinas/RT1/encerrar", json=corpo)

    assert r.status_code == 422, r.text
    assert sb.rotinas[0]["status"] == "ATIVA"


def test_encerrar_para_os_ciclos_seguintes(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-12-10")
    sb = _sb_com_rotina()
    client = cliente_das_rotinas(sb, PEDRO)

    r = client.post("/api/rotinas/RT1/encerrar", json={"anotacao": "A equipe passou a se reunir no plantão."})

    assert r.status_code == 200, r.text
    rotina = sb.rotinas[0]
    assert (rotina["status"], rotina["encerrada_em"], rotina["anotacao_encerramento"]) == (
        "ENCERRADA",
        "2026-12-10",
        "A equipe passou a se reunir no plantão.",
    )
    assert rotina["encerrada_por_id"] == "P1"
    # O ciclo em curso (07/12 a 13/12) e os seguintes saem; os que já
    # fecharam continuam devidos e ainda podem ser marcados, com atraso.
    hoje["valor"] = D("2026-12-20")
    assert client.post("/api/rotinas/RT1/ciclos/2026-12-07/realizada").status_code == 422
    assert client.post("/api/rotinas/RT1/ciclos/2026-12-14/realizada").status_code == 422
    assert client.post("/api/rotinas/RT1/ciclos/2026-11-30/realizada").status_code == 201


def test_encerrar_duas_vezes_e_recusado(cliente_das_rotinas, hoje):
    sb = _sb_com_rotina()
    client = cliente_das_rotinas(sb, PEDRO)
    assert client.post("/api/rotinas/RT1/encerrar", json={"anotacao": "Acabou."}).status_code == 200

    assert client.post("/api/rotinas/RT1/encerrar", json={"anotacao": "De novo."}).status_code == 409
    assert sb.rotinas[0]["anotacao_encerramento"] == "Acabou."


def test_o_responsavel_nao_encerra_a_rotina(cliente_das_rotinas, hoje):
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, ANA).post("/api/rotinas/RT1/encerrar", json={"anotacao": "Não quero mais."})

    assert r.status_code == 403, r.text
    assert sb.rotinas[0]["status"] == "ATIVA"


def test_o_super_admin_encerra_a_rotina(cliente_das_rotinas, hoje):
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, ADMIN).post("/api/rotinas/RT1/encerrar", json={"anotacao": "Repetida."})

    assert r.status_code == 200, r.text
    assert sb.rotinas[0]["status"] == "ENCERRADA"


def test_rotina_de_reuniao_do_nucleo_oculta_nao_se_marca(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()

    r = cliente_das_rotinas(sb, ADMIN, ocultas=["R1"]).post("/api/rotinas/RT1/ciclos/2026-11-23/realizada")

    assert r.status_code == 404, r.text


def test_a_lista_traz_os_ciclos_em_aberto_e_o_que_cada_um_pode_fazer(cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-12-09")
    sb = _sb_com_rotina()
    client = cliente_das_rotinas(sb, PEDRO)
    assert client.post("/api/rotinas/RT1/ciclos/2026-11-23/realizada").status_code == 201

    r = client.get("/api/rotinas")

    assert r.status_code == 200, r.text
    [rotina] = r.json()
    assert rotina["id"] == "RT1"
    assert rotina["pode_encerrar"] is True
    assert [(c["inicio"], c["fim"], c["atrasado"]) for c in rotina["ciclos_em_aberto"]] == [
        ("2026-11-30", "2026-12-06", True),
        ("2026-12-07", "2026-12-13", False),
    ]
    assert [(v["ciclo_inicio"], v["resultado"]) for v in rotina["verificacoes"]] == [("2026-11-23", "REALIZADA")]
    # O responsável vê, mas não encerra; quem não tem vínculo não vê.
    [da_ana] = cliente_das_rotinas(sb, ANA).get("/api/rotinas").json()
    assert da_ana["pode_encerrar"] is False
    assert cliente_das_rotinas(sb, OUTRO).get("/api/rotinas").json() == []


# ─── 3. A Verificação na Minha Fila do responsável ───────────────────────────


@pytest.fixture
def fila(monkeypatch):
    """O Início só com a fonte das Rotinas, pelo nome dela em `FONTES`."""
    from datetime import datetime

    from app.services import inicio
    from app.services.inicio import fonte_rotinas
    from app.services.inicio.regras import FUSO

    estado = {"ocultas": []}
    monkeypatch.setattr(fonte_rotinas, "reunioes_ocultas", lambda _sb, _me: list(estado["ocultas"]))

    def _montar(sb, quem: dict, dia: str):
        agora = datetime.fromisoformat(f"{dia}T10:00:00").replace(tzinfo=FUSO)
        fontes = tuple(f for f in inicio.FONTES if f.nome == "rotinas")
        assert fontes, "a fonte das Rotinas não está no Início"
        return inicio.montar_inicio(sb, quem, agora, fontes=fontes, filas_do_papel=())

    _montar.estado = estado
    return _montar


def _verificacoes(resposta) -> list[tuple]:
    return [
        (i.titulo, i.prazo.isoformat(), i.grupo, i.acao_de_um_clique.endpoint if i.acao_de_um_clique else None)
        for i in resposta.itens
        if i.tipo == "verificacao_da_rotina"
    ]


def test_a_verificacao_do_ciclo_aparece_na_minha_fila_do_responsavel(fila):
    sb = _sb_com_rotina()

    resposta = fila(sb, ANA, "2026-11-25")

    # O trilho lê tabelas que este banco de mentira não tem; a fonte das
    # Rotinas não pode falhar.
    assert [a for a in resposta.avisos if a.fonte == "rotinas"] == []
    assert _verificacoes(resposta) == [
        ("Reunir a equipe", "2026-11-29", "proximos_7_dias", "/api/rotinas/RT1/ciclos/2026-11-23/realizada"),
    ]
    [item] = resposta.itens
    assert item.acao_de_um_clique.rotulo == "Realizada"
    assert item.destino == "/rotinas"
    assert "Rotina semanal" in item.origem


def test_o_ciclo_que_fechou_sem_marcacao_fica_atrasado_na_fila(fila):
    sb = _sb_com_rotina()

    resposta = fila(sb, ANA, "2026-12-02")

    assert [(t, p, g) for t, p, g, _e in _verificacoes(resposta)] == [
        ("Reunir a equipe", "2026-11-29", "passou_do_prazo"),
        ("Reunir a equipe", "2026-12-06", "proximos_7_dias"),
    ]


def test_o_ciclo_marcado_sai_da_fila(fila, cliente_das_rotinas, hoje):
    hoje["valor"] = D("2026-11-25")
    sb = _sb_com_rotina()
    assert cliente_das_rotinas(sb, ANA).post("/api/rotinas/RT1/ciclos/2026-11-23/realizada").status_code == 201

    assert _verificacoes(fila(sb, ANA, "2026-11-25")) == []


def test_a_verificacao_nao_aparece_na_fila_de_quem_nao_e_o_responsavel(fila):
    sb = _sb_com_rotina()

    assert _verificacoes(fila(sb, PEDRO, "2026-11-25")) == []


def test_rotina_encerrada_nao_cobra_o_ciclo_em_curso_na_fila(fila):
    sb = _sb_com_rotina(status="ENCERRADA", encerrada_em="2026-11-25", anotacao_encerramento="Acabou.")

    assert _verificacoes(fila(sb, ANA, "2026-11-25")) == []


def test_rotina_de_reuniao_do_nucleo_oculta_nao_aparece_na_fila(fila):
    sb = _sb_com_rotina()
    fila.estado["ocultas"] = ["R1"]

    assert _verificacoes(fila(sb, ANA, "2026-11-25")) == []
