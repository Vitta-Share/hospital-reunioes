"""A varredura das rotas de Segurança do Paciente (issue #1999, ADR 0107, decisões 4 e 5).

Toda rota do módulo passa pelo gate de recurso (`require_recurso_nsp`), menos
as exceções escritas aqui, uma a uma: o formulário e o acompanhamento
públicos, o botão "Notificar incidente" que todo logado vê e a confirmação da
própria presença em capacitação. Rota nova sem o gate fica vermelha aqui até
ganhar o gate ou entrar, de propósito, na lista. O link de uso único do Núcleo
(ADR 0107, decisão 8) entra na lista quando a rota dele nascer.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
import sys

from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.routers as pacote_dos_routers  # noqa: E402
from app.config import settings  # noqa: E402
from app.dependencies import get_current_user, require_recurso_nsp  # noqa: E402

# As rotas do módulo que não pedem recurso, cada uma com o motivo.
EXCECOES = {
    # O formulário público: o QR e o endereço, sem login.
    "POST /nsp/publico/notificacoes",
    "GET /nsp/publico/setores",
    # O botão "Notificar incidente", que todo usuário logado vê.
    "POST /nsp/notificacoes",
    # O acompanhamento público, pelo protocolo e pelo código ou contato.
    "POST /nsp/publico/acompanhamento",
    "POST /nsp/publico/perguntas",
    "POST /nsp/publico/respostas",
    # A presença em capacitação: quem está na lista confirma a própria.
    "POST /nsp/capacitacoes/{capacitacao_id}/presenca",
}

# As rotas com "nsp" no caminho que moram noutro módulo, com o gate dele: a
# Ouvidoria manda o caso ao Núcleo, e o Comitê de Conduta manda a nota.
DE_OUTROS_MODULOS = {
    "/api/ouvidoria/manifestacoes/{manifestacao_id}/nsp",
    "/api/ouvidoria-setor/nsp/{token}",
    "/api/ouvidoria-setor/nsp/{token}/recebido",
    "/api/comite-de-conduta/casos/{caso_id}/nota-ao-nsp",
    "/api/comite-de-conduta/casos/{caso_id}/nota-ao-nsp/envio",
}


def _chamadas(dependente) -> set:
    """Todas as funções de que a rota depende, em qualquer profundidade."""
    achadas = set()
    for sub in dependente.dependencies:
        achadas.add(sub.call)
        achadas |= _chamadas(sub)
    return achadas


def _tem_o_gate(rota: APIRoute) -> bool:
    return any(getattr(chamada, "recursos_do_gate", None) for chamada in _chamadas(rota.dependant))


def _routers_do_modulo() -> list[APIRouter]:
    nomes = [
        m.name for m in pkgutil.iter_modules(pacote_dos_routers.__path__) if m.name.startswith("seguranca_do_paciente")
    ]
    return [importlib.import_module(f"app.routers.{nome}").router for nome in sorted(nomes)]


def _rotas(routers: list[APIRouter]) -> list[APIRoute]:
    return [rota for router in routers for rota in router.routes if isinstance(rota, APIRoute)]


def _chave(rota: APIRoute) -> list[str]:
    return [f"{metodo} {rota.path}" for metodo in sorted(rota.methods)]


def rotas_sem_gate(routers: list[APIRouter], excecoes: set[str] = EXCECOES) -> list[str]:
    """As rotas do módulo sem o gate de recurso que não estão na lista."""
    return [chave for rota in _rotas(routers) if not _tem_o_gate(rota) for chave in _chave(rota) if chave not in excecoes]


def test_a_varredura_enxerga_as_rotas_do_modulo():
    """Controle: varredura vazia satisfaria "toda rota tem o gate"."""
    chaves = {chave for rota in _rotas(_routers_do_modulo()) for chave in _chave(rota)}
    assert {
        "GET /nsp/notificacoes",
        "GET /nsp/notificacoes/{caso_id}",
        "POST /nsp/triagem/{notificacao_id}",
        "POST /nsp/membros/{participacao_id}/ausencia-da-presidencia",
        "GET /nsp/membros",
        "GET /nsp/reunioes",
        "GET /nsp/configuracao",
    } <= chaves


def test_toda_rota_do_modulo_passa_pelo_gate_ou_esta_na_lista_de_excecoes():
    assert rotas_sem_gate(_routers_do_modulo()) == []


def test_a_varredura_reprova_rota_nova_do_modulo_sem_gate():
    """O detector também é código: uma rota que só pede login aparece."""
    router = APIRouter(prefix="/nsp")

    @router.get("/notificacoes/{caso_id}/investigacao")
    async def _sem_gate(me: dict = Depends(get_current_user)):
        return {}

    @router.get("/notificacoes/{caso_id}/plano")
    async def _com_gate(me: dict = Depends(require_recurso_nsp("casos"))):
        return {}

    assert rotas_sem_gate([router]) == ["GET /nsp/notificacoes/{caso_id}/investigacao"]


def test_a_varredura_enxerga_o_gate_dentro_de_outra_dependencia():
    """O registro rápido pede o gate por dentro de uma dependência própria."""
    router = APIRouter(prefix="/nsp")
    gate = require_recurso_nsp("casos")

    async def _por_dentro(me: dict = Depends(gate)) -> dict:
        return me

    @router.post("/notificacoes/outra-porta")
    async def _rota(me: dict = Depends(_por_dentro)):
        return {}

    assert rotas_sem_gate([router]) == []


def test_cada_excecao_existe_e_continua_sem_gate():
    """A lista não apodrece: a exceção que sumiu ou ganhou o gate sai dela."""
    sem_gate = {chave for rota in _rotas(_routers_do_modulo()) if not _tem_o_gate(rota) for chave in _chave(rota)}
    assert sem_gate == EXCECOES


def test_toda_rota_com_nsp_no_app_e_de_um_router_do_modulo():
    """Uma rota do módulo escrita noutro router escaparia da varredura."""
    from app.main import app

    do_app = {caminho for caminho in app.openapi()["paths"] if "nsp" in caminho} - DE_OUTROS_MODULOS
    do_modulo = {f"{settings.api_prefix}{rota.path}" for rota in _rotas(_routers_do_modulo())}

    assert do_app == do_modulo
