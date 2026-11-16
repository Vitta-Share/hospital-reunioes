"""O papel de quem está logado na Ouvidoria (issue #1884, ADR 0099).

Função pura: o participante, as linhas do cadastro de responsáveis e o dia
entram; sai um papel só. O papel maior vence: Perfil da Ouvidoria, depois o
índice geral (Secretária ou Super admin), depois o responsável vigente.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.ouvidoria_papel import (  # noqa: E402
    INDICE_GERAL,
    NENHUM,
    PERFIL_OUVIDORIA,
    RESPONSAVEL,
    papel_na_ouvidoria,
)

HOJE = dt.date(2026, 11, 16)
ONTEM = "2026-11-15"

OUVIDOR = {"email": "ouvidor@hsm.test", "access_profile": "regular", "perfil_ouvidoria": "ouvidor"}
DIRETORIA = {"email": "dir@hsm.test", "access_profile": None, "perfil_ouvidoria": "diretoria_executiva"}
SECRETARIA = {"email": "sec@hsm.test", "access_profile": "secretaria", "perfil_ouvidoria": None}
SUPER_ADMIN = {"email": "admin@hsm.test", "access_profile": "super_admin", "perfil_ouvidoria": None}
MEDICO = {"email": "medico@hsm.test", "access_profile": "regular", "perfil_ouvidoria": None}
SEM_REUNIOES = {"email": "medico@hsm.test", "access_profile": None, "perfil_ouvidoria": None}


def _linha(setor: str, papel: str, email: str = "medico@hsm.test", inicio="2026-01-01", fim=None) -> dict:
    return {"setor": setor, "papel": papel, "email": email, "vigencia_inicio": inicio, "vigencia_fim": fim}


CADASTRO = [
    _linha("Recepção", "titular", email="outra@hsm.test"),
    _linha("UTI", "titular", email="sec@hsm.test"),
]


@pytest.mark.parametrize(
    ("caso", "participante", "linhas", "papel", "setores"),
    [
        ("ouvidor", OUVIDOR, CADASTRO, PERFIL_OUVIDORIA, set()),
        ("diretoria", DIRETORIA, CADASTRO, PERFIL_OUVIDORIA, set()),
        ("secretária", SECRETARIA, [], INDICE_GERAL, set()),
        ("super admin", SUPER_ADMIN, [], INDICE_GERAL, set()),
        ("titular", MEDICO, [_linha("Recepção", "titular")], RESPONSAVEL, {"Recepção"}),
        ("substituto", MEDICO, [_linha("Recepção", "substituto")], RESPONSAVEL, {"Recepção"}),
        ("gestor", SEM_REUNIOES, [_linha("Recepção", "gestor")], RESPONSAVEL, {"Recepção"}),
        ("vigência encerrada ontem", MEDICO, [_linha("Recepção", "titular", fim=ONTEM)], NENHUM, set()),
        (
            "vigência que acaba hoje",
            MEDICO,
            [_linha("Recepção", "titular", fim="2026-11-16")],
            RESPONSAVEL,
            {"Recepção"},
        ),
        (
            "e-mail com maiúscula e espaço",
            MEDICO,
            [_linha("Recepção", "titular", email="  Medico@HSM.test ")],
            RESPONSAVEL,
            {"Recepção"},
        ),
        (
            "responsável de dois setores",
            MEDICO,
            [_linha("Recepção", "titular"), _linha("UTI", "gestor"), _linha("Farmácia", "titular", email="x@hsm.test")],
            RESPONSAVEL,
            {"Recepção", "UTI"},
        ),
        ("responsável que é Secretária", SECRETARIA, CADASTRO, INDICE_GERAL, set()),
        ("ninguém", MEDICO, CADASTRO, NENHUM, set()),
        ("sem participante", None, CADASTRO, NENHUM, set()),
    ],
)
def test_o_papel_de_quem_entra_na_ouvidoria(caso, participante, linhas, papel, setores):
    resultado = papel_na_ouvidoria(participante, linhas, HOJE)

    assert resultado.papel == papel, caso
    assert set(resultado.setores) == setores, caso
