"""A marca de Responsável técnico no cadastro de usuários (issue #2248, PRD
#2247, ADR 0112).

Pela área administrativa (`/admin/usuarios`): a lista e o detalhe devolvem a
marca, e gravar passa pela função de troca do banco (migration 241), que
desmarca quem estava. A troca entra no registro de auditoria da pessoa marcada
e da que perdeu a marca.

O banco fingido aqui imita a função `trocar_responsavel_tecnico`; o SQL dela é
conferido no teste da migration 241. Pessoas de teste, sem nome ou e-mail real.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_admin_usuarios import (  # noqa: E402
    _build_supabase,
    _FakeRequest,
    _ParticipantesQuery,
    _Result,
    _super_admin,
)

from app.models.admin_schemas import AdminUsuarioResponse, AdminUsuarioUpdate  # noqa: E402
from app.routers.admin import usuarios as usuarios_router  # noqa: E402


def _pessoa(pid: str, *, marcada: bool = False) -> dict:
    return {
        "id": pid,
        "nome_completo": f"Pessoa {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "cargo": "Médico",
        "role": "coordenador",
        "ativo": True,
        "is_externo": False,
        "is_super_admin": False,
        "responsavel_tecnico": marcada,
    }


class _ParticipantesComColunas(_ParticipantesQuery):
    """Devolve só as colunas pedidas no select, como o PostgREST: a marca que
    a rota não pede não chega à tela."""

    def select(self, campos="*", *_args, **_kwargs):
        self._campos = [c.strip() for c in campos.split(",")]
        return super().select()

    def execute(self):
        resultado = super().execute()
        campos = getattr(self, "_campos", None)
        if self._op == "select" and campos and campos != ["*"]:
            return _Result(data=[{c: r.get(c) for c in campos} for r in resultado.data])
        return resultado


def _banco(*pessoas: dict):
    sb = _build_supabase(participantes=list(pessoas))
    sb.trocas = []
    sb.updates = []

    def _table(nome):
        if nome == "participantes":
            consulta = _ParticipantesComColunas(sb.participantes)
            update_original = consulta.update

            def _update(payload):
                sb.updates.append(dict(payload))
                return update_original(payload)

            consulta.update = _update
            return consulta
        return type(sb).table(sb, nome)

    def _rpc(funcao, params):
        assert funcao == "trocar_responsavel_tecnico"
        sb.trocas.append(params)
        anterior = None
        if params["p_marcar"]:
            for p in sb.participantes:
                if p.get("responsavel_tecnico") and p["id"] != params["p_participante_id"]:
                    p["responsavel_tecnico"] = False
                    anterior = p["id"]
        for p in sb.participantes:
            if p["id"] == params["p_participante_id"]:
                p["responsavel_tecnico"] = params["p_marcar"]

        chamada = MagicMock()
        chamada.execute.return_value = _Result(data=anterior)
        return chamada

    sb.table = _table
    sb.rpc = _rpc
    return sb


async def _editar(sb, pid: str, body: AdminUsuarioUpdate) -> dict:
    return await usuarios_router.update_usuario(
        participante_id=pid, body=body, request=_FakeRequest(), actor=_super_admin(), supabase=sb
    )


def _marcados(sb) -> list[str]:
    return [p["id"] for p in sb.participantes if p.get("responsavel_tecnico")]


class TestLeitura:
    @pytest.mark.asyncio
    async def test_a_lista_devolve_quem_e_o_responsavel_tecnico(self):
        sb = _banco(_pessoa("P010", marcada=True), _pessoa("P011"))

        lista = await usuarios_router.list_usuarios(
            q=None,
            setor=None,
            ativo=None,
            is_super_admin_filter=None,
            is_externo_filter=None,
            access_profile_filter=None,
            limit=50,
            offset=0,
            _actor=_super_admin(),
            supabase=sb,
        )

        marcas = {u["id"]: AdminUsuarioResponse(**u).responsavel_tecnico for u in lista}
        assert marcas == {"P010": True, "P011": False}

    @pytest.mark.asyncio
    async def test_o_detalhe_devolve_a_marca(self):
        sb = _banco(_pessoa("P010", marcada=True))

        detalhe = await usuarios_router.get_usuario(participante_id="P010", _actor=_super_admin(), supabase=sb)

        assert detalhe.usuario.responsavel_tecnico is True


class TestTroca:
    @pytest.mark.asyncio
    async def test_marcar_uma_pessoa_desmarca_a_anterior(self):
        sb = _banco(_pessoa("P010", marcada=True), _pessoa("P011"))

        resultado = await _editar(sb, "P011", AdminUsuarioUpdate(responsavel_tecnico=True, reason="troca da RT"))

        assert resultado["responsavel_tecnico"] is True
        assert _marcados(sb) == ["P011"]
        assert sb.trocas == [{"p_participante_id": "P011", "p_marcar": True}]
        trilha = {(r["target_id"], r["action"]): r for r in sb.audit_rows}
        assert trilha[("P011", "EDIT_USUARIO")]["metadata"]["changes"]["responsavel_tecnico"] == {
            "antes": False,
            "depois": True,
        }
        assert trilha[("P010", "EDIT_USUARIO")]["metadata"]["changes"]["responsavel_tecnico"] == {
            "antes": True,
            "depois": False,
        }
        assert trilha[("P010", "EDIT_USUARIO")]["metadata"]["substituido_por"] == "P011"

    @pytest.mark.asyncio
    async def test_desmarcar_sem_marcar_outra_deixa_ninguem_marcado(self):
        sb = _banco(_pessoa("P010", marcada=True), _pessoa("P011"))

        resultado = await _editar(sb, "P010", AdminUsuarioUpdate(responsavel_tecnico=False))

        assert resultado["responsavel_tecnico"] is False
        assert _marcados(sb) == []
        assert [(r["target_id"], r["metadata"]["changes"]) for r in sb.audit_rows] == [
            ("P010", {"responsavel_tecnico": {"antes": True, "depois": False}})
        ]

    @pytest.mark.asyncio
    async def test_a_marca_nunca_vai_pelo_update_da_tabela(self):
        """Mutante: deixar a marca no payload do update. A tabela seria gravada
        sem desmarcar a anterior, e o índice único recusaria."""
        sb = _banco(_pessoa("P010", marcada=True), _pessoa("P011"))

        await _editar(sb, "P011", AdminUsuarioUpdate(responsavel_tecnico=True, area="Diretoria"))

        assert sb.updates == [{"area": "Diretoria"}]
        assert sb.trocas == [{"p_participante_id": "P011", "p_marcar": True}]
        assert _marcados(sb) == ["P011"]

    @pytest.mark.asyncio
    async def test_marca_igual_a_atual_nao_chama_a_troca(self):
        sb = _banco(_pessoa("P010", marcada=True))

        await _editar(sb, "P010", AdminUsuarioUpdate(responsavel_tecnico=True))

        assert sb.trocas == []
        assert sb.audit_rows == []


def test_o_kit_diz_onde_se_marca_o_responsavel_tecnico():
    """O Assistente responde "onde marco o Responsável técnico?" pelo kit.
    Mutante: apagar a linha do Responsável técnico da fundação do módulo."""
    from test_kit_conhecimento import _secao, _texto

    no_ar = _secao(_texto("seguranca-do-paciente.md"), "O que já está no ar")
    for termo in (
        "Responsável técnico",
        "cadastro de usuários",
        "ao lado do Acesso pleno ao NSP",
        "marcar outra desmarca a anterior",
        "histórico da pessoa",
    ):
        assert termo in no_ar, termo
