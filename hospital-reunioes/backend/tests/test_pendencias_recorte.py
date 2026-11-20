"""Quem vê qual Pendência, papel por papel (ADR 0098, decisão 7; issue #1863).

A função de recorte é pura: recebe quem é a pessoa (id, se é Super admin, as
Reuniões que ela facilita e o que o Núcleo libera) e responde se uma Pendência
está no recorte dela, e qual filtro a consulta do banco aplica. As rotas e o
Conector só carregam esses dados e perguntam a ela.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.pendencias_recorte import recorte_das_pendencias  # noqa: E402


def pendencia(responsavel_id: str | None, *, co_responsavel_id: str | None = None, id_reuniao: str = "R1") -> dict:
    return {
        "id_acao": "A1",
        "responsavel_id": responsavel_id,
        "co_responsavel_id": co_responsavel_id,
        "id_reuniao": id_reuniao,
    }


def recorte(
    participante_id: str | None,
    *,
    super_admin: bool = False,
    facilitadas: list[str] = (),
    do_nucleo: list[str] = (),
    ocultas: list[str] = (),
):
    return recorte_das_pendencias(
        participante_id,
        super_admin=super_admin,
        facilitadas=list(facilitadas),
        do_nucleo=list(do_nucleo),
        ocultas=list(ocultas),
    )


class TestQuemVe:
    def test_responsavel_ve_a_propria_pendencia(self):
        assert recorte("ana").ve(pendencia("ana")) is True

    def test_co_responsavel_ve_a_pendencia_que_divide(self):
        assert recorte("carla").ve(pendencia("externo", co_responsavel_id="carla")) is True

    def test_participante_sem_vinculo_nao_ve_a_pendencia_de_outra_pessoa(self):
        assert recorte("bruno").ve(pendencia("ana")) is False

    def test_facilitador_ve_todas_as_pendencias_da_reuniao_que_facilitou(self):
        facilitador = recorte("fabio", facilitadas=["R1"])

        assert facilitador.ve(pendencia("ana", id_reuniao="R1")) is True
        assert facilitador.ve(pendencia("bruno", id_reuniao="R1")) is True
        assert facilitador.ve(pendencia("ana", id_reuniao="R2")) is False

    def test_super_admin_ve_todas(self):
        assert recorte("admin", super_admin=True).ve(pendencia("ana", id_reuniao="R9")) is True

    def test_super_admin_nao_ve_a_pendencia_do_nucleo_que_o_nucleo_esconde(self):
        admin = recorte("admin", super_admin=True, do_nucleo=["N1"], ocultas=["N1"])

        assert admin.ve(pendencia("ana", id_reuniao="N1")) is False
        assert admin.ve(pendencia("ana", id_reuniao="R1")) is True

    def test_responsavel_de_fora_do_nucleo_nao_ve_a_pendencia_do_nucleo(self):
        assert recorte("ana", do_nucleo=["N1"], ocultas=["N1"]).ve(pendencia("ana", id_reuniao="N1")) is False

    def test_quem_o_nucleo_libera_ve_as_pendencias_das_reunioes_do_nucleo(self):
        membro = recorte("nina", do_nucleo=["N1"], ocultas=[])

        assert membro.ve(pendencia("ana", id_reuniao="N1")) is True
        assert membro.ve(pendencia("ana", id_reuniao="R1")) is False

    def test_sem_participante_nao_ve_nem_a_pendencia_sem_responsavel(self):
        """Token órfão: id None não pode casar com responsável None."""
        assert recorte(None).ve(pendencia(None)) is False


class TestFiltroDaConsulta:
    def test_super_admin_nao_tem_filtro(self):
        assert recorte("admin", super_admin=True).filtro() is None

    def test_regular_filtra_por_responsavel_co_responsavel_e_reunioes_facilitadas(self):
        assert recorte("fabio", facilitadas=["R1", "R2"]).filtro() == (
            "responsavel_id.eq.fabio,co_responsavel_id.eq.fabio,id_reuniao.in.(R1,R2)"
        )

    def test_sem_reuniao_facilitada_fica_so_o_vinculo_da_pessoa(self):
        assert recorte("ana").filtro() == "responsavel_id.eq.ana,co_responsavel_id.eq.ana"

    def test_sem_participante_o_filtro_e_vazio_e_nada_aparece(self):
        assert recorte(None).filtro() == ""
