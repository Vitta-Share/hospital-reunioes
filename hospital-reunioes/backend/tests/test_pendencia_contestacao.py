"""A Contestação do item da Ata na assinatura (issue #1870, PRD #1757).

Decisões 1, 2, 12, 17, 22, 32, 38 e 51 do diretor: só o responsável pelo item
contesta, e só enquanto a Ata está em assinatura; contestar não impede assinar
a Ata; o item contestado segue cobrado; a Contestação aparece na hora na Minha
Fila do Facilitador; o Facilitador (ou o Super admin) ajusta ou recusa, sempre
com anotação, e a Ata não volta para assinatura.

Os valores esperados saem da issue, não do código.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

from app.services.pendencia_ciclo import AcaoRecusada, Comando, Papel, acoes_disponiveis, decidir

# O banco de mentira e o cliente da API são os de `test_pendencia_acoes.py`.
sys.path.insert(0, os.path.dirname(__file__))

from test_pendencia_acoes import _banco, cliente  # noqa: E402, F401

HOJE = date(2026, 11, 19)
ONTEM = date(2026, 11, 18)
AMANHA = date(2026, 11, 20)
DAQUI_A_UMA_SEMANA = date(2026, 11, 26)

PAPEIS = {
    "responsavel": {Papel.RESPONSAVEL},
    "co_responsavel": {Papel.CO_RESPONSAVEL},
    "facilitador": {Papel.FACILITADOR},
    "super_admin": {Papel.SUPER_ADMIN},
    "outro": set(),
}


def _decidir(
    comando, papeis, *, status="PENDENTE", prazo=AMANHA, prazo_novo=None, anotacao="o prazo está errado", **ctx
):
    return decidir(
        comando, papeis, status=status, prazo=prazo, hoje=HOJE, anotacao=anotacao, prazo_novo=prazo_novo, **ctx
    )


# ── Só o responsável contesta, e só com a Ata em assinatura ─────────────────


@pytest.mark.parametrize(
    "papel,pode",
    [
        ("responsavel", True),
        ("co_responsavel", False),
        ("facilitador", False),
        ("super_admin", False),
        ("outro", False),
    ],
)
def test_so_o_responsavel_pelo_item_contesta(papel, pode):
    if pode:
        mudanca = _decidir(Comando.CONTESTAR, PAPEIS[papel], ata_em_assinatura=True)
        assert mudanca.status == "PENDENTE"
    else:
        with pytest.raises(AcaoRecusada) as erro:
            _decidir(Comando.CONTESTAR, PAPEIS[papel], ata_em_assinatura=True)
        assert erro.value.tipo == "permissao"


def test_contestar_fora_da_assinatura_e_recusado():
    with pytest.raises(AcaoRecusada) as erro:
        _decidir(Comando.CONTESTAR, PAPEIS["responsavel"], ata_em_assinatura=False)
    assert erro.value.tipo == "transicao"


@pytest.mark.parametrize("status", ["CONCLUIDO", "CANCELADO"])
def test_item_fechado_nao_se_contesta(status):
    with pytest.raises(AcaoRecusada) as erro:
        _decidir(Comando.CONTESTAR, PAPEIS["responsavel"], status=status, ata_em_assinatura=True)
    assert erro.value.tipo == "transicao"


def test_item_ja_contestado_nao_se_contesta_de_novo_ate_o_facilitador_responder():
    with pytest.raises(AcaoRecusada) as erro:
        _decidir(Comando.CONTESTAR, PAPEIS["responsavel"], ata_em_assinatura=True, contestada=True)
    assert erro.value.tipo == "transicao"


def test_o_botao_contestar_so_aparece_ao_responsavel_com_a_ata_em_assinatura():
    resp = PAPEIS["responsavel"]
    assert Comando.CONTESTAR in acoes_disponiveis(resp, "PENDENTE", ata_em_assinatura=True)
    assert Comando.CONTESTAR not in acoes_disponiveis(resp, "PENDENTE", ata_em_assinatura=False)
    assert Comando.CONTESTAR not in acoes_disponiveis(PAPEIS["co_responsavel"], "PENDENTE", ata_em_assinatura=True)


# ── O item contestado segue cobrado ─────────────────────────────────────────


def test_contestar_nao_muda_estado_nem_prazo_e_nao_conta_atraso():
    mudanca = _decidir(
        Comando.CONTESTAR, PAPEIS["responsavel"], status="EM_PROGRESSO", prazo=ONTEM, ata_em_assinatura=True
    )
    assert (mudanca.status, mudanca.prazo, mudanca.concluida, mudanca.conta_atraso) == (
        "EM_PROGRESSO",
        ONTEM,
        None,
        False,
    )


# ── Ajustar e recusar: Facilitador e Super admin, com anotação ──────────────


@pytest.mark.parametrize("comando", [Comando.AJUSTAR, Comando.RECUSAR])
@pytest.mark.parametrize(
    "papel,pode",
    [
        ("facilitador", True),
        ("super_admin", True),
        ("responsavel", False),
        ("co_responsavel", False),
        ("outro", False),
    ],
)
def test_ajustar_e_recusar_sao_do_facilitador_e_do_super_admin(comando, papel, pode):
    if pode:
        assert _decidir(comando, PAPEIS[papel], contestada=True) is not None
    else:
        with pytest.raises(AcaoRecusada) as erro:
            _decidir(comando, PAPEIS[papel], contestada=True)
        assert erro.value.tipo == "permissao"


@pytest.mark.parametrize("comando", [Comando.AJUSTAR, Comando.RECUSAR])
@pytest.mark.parametrize("anotacao", ["", "   ", None])
def test_ajustar_e_recusar_exigem_anotacao(comando, anotacao):
    with pytest.raises(AcaoRecusada) as erro:
        _decidir(comando, PAPEIS["facilitador"], contestada=True, anotacao=anotacao)
    assert erro.value.tipo == "dados"


@pytest.mark.parametrize("comando", [Comando.AJUSTAR, Comando.RECUSAR])
def test_ajustar_e_recusar_so_respondem_a_uma_contestacao_aberta(comando):
    with pytest.raises(AcaoRecusada) as erro:
        _decidir(comando, PAPEIS["facilitador"], contestada=False)
    assert erro.value.tipo == "transicao"
    assert comando not in acoes_disponiveis(PAPEIS["facilitador"], "PENDENTE", contestada=False)
    assert comando in acoes_disponiveis(PAPEIS["facilitador"], "PENDENTE", contestada=True)


def test_ajustar_muda_o_prazo_na_pendencia_sem_contar_atraso():
    mudanca = _decidir(
        Comando.AJUSTAR, PAPEIS["facilitador"], prazo=ONTEM, prazo_novo=DAQUI_A_UMA_SEMANA, contestada=True
    )
    assert (mudanca.status, mudanca.prazo, mudanca.conta_atraso) == ("PENDENTE", DAQUI_A_UMA_SEMANA, False)


def test_ajustar_sem_prazo_novo_mantem_o_prazo():
    mudanca = _decidir(Comando.AJUSTAR, PAPEIS["facilitador"], contestada=True)
    assert mudanca.prazo == AMANHA


def test_ajustar_para_um_prazo_no_passado_e_recusado():
    with pytest.raises(AcaoRecusada) as erro:
        _decidir(Comando.AJUSTAR, PAPEIS["facilitador"], prazo_novo=ONTEM, contestada=True)
    assert erro.value.tipo == "dados"


def test_recusar_mantem_a_pendencia_como_esta():
    mudanca = _decidir(Comando.RECUSAR, PAPEIS["facilitador"], contestada=True)
    assert (mudanca.status, mudanca.prazo, mudanca.concluida, mudanca.conta_atraso) == ("PENDENTE", AMANHA, None, False)
    with pytest.raises(AcaoRecusada) as erro:
        _decidir(Comando.RECUSAR, PAPEIS["facilitador"], prazo_novo=DAQUI_A_UMA_SEMANA, contestada=True)
    assert erro.value.tipo == "dados"


# ── Pela API: `POST /pendencias/{id}/acoes` ─────────────────────────────────


def _em_assinatura(estado, status_ata="AGUARDANDO_ASSINATURA"):
    estado["banco"].reunioes[0]["status_ata"] = status_ata
    return estado


def _evento(id_evento=10, comando="contestar", criado_em="2026-11-19T09:00:00+00:00"):
    return {
        "id": id_evento,
        "id_acao": "A001",
        "comando": comando,
        "anotacao": "o prazo combinado era outro",
        "autor_nome": "Rita Responsável",
        "criado_em": criado_em,
        "conta_atraso": False,
    }


@pytest.mark.parametrize(
    "quem,status_ata,esperado",
    [
        ("resp", "AGUARDANDO_ASSINATURA", 200),
        ("resp", "ASSINADA", 409),
        ("resp", "AGUARDANDO_VALIDACAO", 409),
        ("coresp", "AGUARDANDO_ASSINATURA", 403),
        ("facil", "AGUARDANDO_ASSINATURA", 403),
        ("admin", "AGUARDANDO_ASSINATURA", 403),
        ("outro", "AGUARDANDO_ASSINATURA", 404),
    ],
)
def test_contestar_pela_api_por_papel_e_por_estado_da_ata(cliente, quem, status_ata, esperado):  # noqa: F811
    client, estado = cliente
    _em_assinatura(estado, status_ata)
    estado["quem"] = quem
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "contestar", "anotacao": "prazo errado"})
    assert r.status_code == esperado, r.text
    if esperado != 200:
        assert estado["banco"].chamadas == []


def test_contestar_grava_o_evento_e_o_item_segue_cobrado(cliente):  # noqa: F811
    client, estado = cliente
    estado["banco"] = _banco(prazo=ONTEM)
    _em_assinatura(estado)
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "contestar", "anotacao": "o prazo era março"})

    assert r.status_code == 200, r.text
    corpo = r.json()
    # Segue na cobrança e no cálculo de atraso, com o prazo de antes.
    assert (corpo["status"], corpo["prazo"], corpo["atrasada"]) == ("PENDENTE", ONTEM.isoformat(), True)
    params = estado["banco"].chamadas[0][1]
    assert (params["p_comando"], params["p_anotacao"], params["p_prazo_novo"]) == (
        "contestar",
        "o prazo era março",
        None,
    )


def test_contestar_nao_impede_assinar_a_ata(cliente):  # noqa: F811
    """A Contestação é do item; a assinatura é a ciência da Ata inteira
    (decisão 32). Quem já assinou ainda contesta, e contestar não mexe na
    Reunião: a Ata segue em assinatura, e a única gravação é o evento."""
    client, estado = cliente
    _em_assinatura(estado)
    estado["banco"].reuniao_aceites = [{"id_reuniao": "R1", "participante_id": "P_RESP"}]
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "contestar", "anotacao": "responsável errado"})

    assert r.status_code == 200, r.text
    assert estado["banco"].reunioes[0]["status_ata"] == "AGUARDANDO_ASSINATURA"
    assert [nome for nome, _ in estado["banco"].chamadas] == ["registrar_acao_da_pendencia"]


def test_item_ja_contestado_nao_se_contesta_de_novo_pela_api(cliente):  # noqa: F811
    client, estado = cliente
    _em_assinatura(estado)
    estado["banco"].pendencia_historico = [_evento()]
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "contestar", "anotacao": "de novo"})
    assert r.status_code == 409


@pytest.mark.parametrize("comando", ["ajustar", "recusar"])
def test_ajustar_e_recusar_exigem_anotacao_pela_api(cliente, comando):  # noqa: F811
    client, estado = cliente
    estado["quem"] = "facil"
    estado["banco"].pendencia_historico = [_evento()]
    r = client.post("/api/pendencias/A001/acoes", json={"comando": comando, "anotacao": "  "})
    assert r.status_code == 422
    assert estado["banco"].chamadas == []


def test_facilitador_ajusta_o_prazo_e_o_evento_vai_para_o_historico(cliente):  # noqa: F811
    client, estado = cliente
    estado["quem"] = "facil"
    # A Ata já foi assinada: o ajuste vale depois, e ela não volta a assinar.
    _em_assinatura(estado, "ASSINADA")
    estado["banco"].pendencia_historico = [_evento()]
    novo = DAQUI_A_UMA_SEMANA.isoformat()
    r = client.post(
        "/api/pendencias/A001/acoes", json={"comando": "ajustar", "anotacao": "combinado em março", "prazo": novo}
    )

    assert r.status_code == 200, r.text
    assert r.json()["prazo"] == novo
    params = estado["banco"].chamadas[0][1]
    assert (params["p_comando"], params["p_anotacao"], params["p_prazo_novo"]) == (
        "ajustar",
        "combinado em março",
        novo,
    )
    assert estado["banco"].reunioes[0]["status_ata"] == "ASSINADA"


def test_facilitador_recusa_e_a_pendencia_fica_como_esta(cliente):  # noqa: F811
    client, estado = cliente
    estado["quem"] = "facil"
    estado["banco"].pendencia_historico = [_evento()]
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "recusar", "anotacao": "o prazo foi esse mesmo"})

    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["prazo"]) == ("PENDENTE", AMANHA.isoformat())
    assert estado["banco"].chamadas[0][1]["p_comando"] == "recusar"


def test_depois_da_resposta_a_contestacao_esta_fechada(cliente):  # noqa: F811
    client, estado = cliente
    estado["quem"] = "facil"
    # O id e a hora contam a ordem, não a posição na lista.
    estado["banco"].pendencia_historico = [
        _evento(11, "recusar", "2026-11-19T11:00:00+00:00"),
        _evento(),
    ]
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "ajustar", "anotacao": "mudei de ideia"})
    assert r.status_code == 409


def test_historico_mostra_ao_facilitador_ajustar_e_recusar_so_com_contestacao_aberta(cliente):  # noqa: F811
    client, estado = cliente
    estado["quem"] = "facil"
    assert client.get("/api/pendencias/A001/historico").json()["acoes_permitidas"] == ["repactuar", "cancelar"]
    estado["banco"].pendencia_historico = [_evento()]
    assert client.get("/api/pendencias/A001/historico").json()["acoes_permitidas"] == [
        "repactuar",
        "cancelar",
        "ajustar",
        "recusar",
    ]


def test_historico_mostra_ao_responsavel_contestar_com_a_ata_em_assinatura(cliente):  # noqa: F811
    client, estado = cliente
    assert "contestar" not in client.get("/api/pendencias/A001/historico").json()["acoes_permitidas"]
    _em_assinatura(estado)
    assert "contestar" in client.get("/api/pendencias/A001/historico").json()["acoes_permitidas"]
