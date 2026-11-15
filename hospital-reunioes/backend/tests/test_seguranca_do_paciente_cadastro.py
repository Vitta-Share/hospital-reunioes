"""O cadastro de pessoas com o registro profissional e o Acesso pleno ao NSP
(issue #1765, ADR 0095, decisões 3 e 4).

Pela área administrativa (`/admin/usuarios`), a mesma tela que já edita o
cadastro: conselho, número de registro e UF, e o perfil do módulo Segurança do
Paciente. Toda mudança entra no registro de auditoria, como as outras.

Pessoas de teste, sem nome, registro ou e-mail real.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_admin_usuarios import _build_supabase, _FakeRequest, _super_admin  # noqa: E402

from app.models.admin_schemas import AdminUsuarioCreate, AdminUsuarioResponse, AdminUsuarioUpdate  # noqa: E402
from app.routers.admin import usuarios as usuarios_router  # noqa: E402


def _pessoa() -> dict:
    return {
        "id": "P010",
        "nome_completo": "Pessoa de Teste",
        "email": "pessoa@hsm.test",
        "cargo": "Enfermeira",
        "area": None,
        "setor": None,
        "role": "coordenador",
        "ativo": True,
        "is_externo": False,
        "is_super_admin": False,
        "conselho_profissional": None,
        "registro_profissional": None,
        "registro_uf": None,
        "perfil_nsp": None,
    }


async def _editar(sb, body: AdminUsuarioUpdate, actor: dict | None = None) -> dict:
    return await usuarios_router.update_usuario(
        participante_id="P010", body=body, request=_FakeRequest(), actor=actor or _super_admin(), supabase=sb
    )


class TestRegistroProfissional:
    @pytest.mark.asyncio
    async def test_o_cadastro_aceita_conselho_numero_e_uf(self):
        sb = _build_supabase(participantes=[_pessoa()])

        resultado = await _editar(
            sb,
            AdminUsuarioUpdate(conselho_profissional="COREN", registro_profissional="000000", registro_uf="rj"),
        )

        assert resultado["conselho_profissional"] == "COREN"
        assert resultado["registro_profissional"] == "000000"
        assert resultado["registro_uf"] == "RJ"
        mudancas = sb.audit_rows[0]["metadata"]["changes"]
        assert mudancas["registro_uf"] == {"antes": None, "depois": "RJ"}

    def test_a_resposta_do_admin_devolve_o_registro(self):
        resposta = AdminUsuarioResponse(**{**_pessoa(), "registro_uf": "SP", "conselho_profissional": "CRM"})

        assert resposta.registro_uf == "SP"
        assert resposta.conselho_profissional == "CRM"

    @pytest.mark.parametrize("uf", ["R", "RJX", "R1", "--"])
    def test_uf_que_nao_e_duas_letras_e_recusada(self, uf):
        with pytest.raises(ValidationError):
            AdminUsuarioUpdate(registro_uf=uf)

    def test_a_criacao_tambem_aceita_o_registro(self):
        corpo = AdminUsuarioCreate(
            nome_completo="Pessoa Nova",
            email="nova@exemplo.com.br",
            conselho_profissional="CRF",
            registro_profissional="000001",
            registro_uf="mg",
        )

        assert (corpo.conselho_profissional, corpo.registro_profissional, corpo.registro_uf) == ("CRF", "000001", "MG")


class TestAcessoPleno:
    @pytest.mark.asyncio
    async def test_o_admin_concede_o_acesso_pleno_a_outra_pessoa(self):
        sb = _build_supabase(participantes=[_pessoa()])

        resultado = await _editar(sb, AdminUsuarioUpdate(perfil_nsp="acesso_pleno", reason="designação"))

        assert resultado["perfil_nsp"] == "acesso_pleno"
        assert sb.audit_rows[0]["metadata"]["changes"]["perfil_nsp"] == {"antes": None, "depois": "acesso_pleno"}

    @pytest.mark.asyncio
    async def test_o_super_admin_nao_concede_o_acesso_pleno_a_si_mesmo(self):
        """ADR 0095, decisão 4: o super admin não passa por cima do conteúdo, e
        conceder o Acesso pleno a si mesmo seria passar.

        Mutante: tirar a trava do próprio cadastro."""
        eu = {**_pessoa(), "id": "P001", "is_super_admin": True, "access_profile": "super_admin"}
        sb = _build_supabase(participantes=[eu])

        with pytest.raises(HTTPException) as recusa:
            await usuarios_router.update_usuario(
                participante_id="P001",
                body=AdminUsuarioUpdate(perfil_nsp="acesso_pleno"),
                request=_FakeRequest(),
                actor=_super_admin(),
                supabase=sb,
            )

        assert recusa.value.status_code == 403
        assert recusa.value.detail == "O Acesso pleno à Segurança do Paciente não pode ser dado a si mesmo"
        assert sb.participantes[0]["perfil_nsp"] is None
        assert sb.audit_rows == []

    def test_perfil_desconhecido_e_recusado(self):
        with pytest.raises(ValidationError):
            AdminUsuarioUpdate(perfil_nsp="super_admin")
