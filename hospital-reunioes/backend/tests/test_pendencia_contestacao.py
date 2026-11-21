"""A Contestação do item da Ata na assinatura (issue #1870, PRD #1757).

Decisões 1, 2, 12, 17, 22, 32, 38 e 51 do diretor: só o responsável pelo item
contesta, e só enquanto a Ata está em assinatura; contestar não impede assinar
a Ata; o item contestado segue cobrado; a Contestação aparece na hora na Minha
Fila do Facilitador; o Facilitador (ou o Super admin) ajusta ou recusa, sempre
com anotação, e a Ata não volta para assinatura.

Os valores esperados saem da issue, não do código.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.pendencia_ciclo import AcaoRecusada, Comando, Papel, acoes_disponiveis, decidir

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
