"""Notificar um incidente (issue #1987, PRD #1979, ADR 0107).

Três portas para o mesmo formulário, e a origem vem da porta:

- `POST /nsp/publico/notificacoes`, sem login, para o QR (`/notificar/qr`) e o
  endereço (`/notificar`). Só aceita essas duas origens;
- `POST /nsp/notificacoes`, com login, para o botão "Notificar incidente" do
  módulo, que todo usuário logado vê. A identificação vem da sessão.

As rotas de envio e a de acompanhamento usam o limite sem IP (ADR 0107,
decisão 6): a conta é pelo endereço, com chave embaralhada, e a linha do log
sai sem endereço. Nada aqui lê IP ou identificador do aparelho para gravar.
O botão do módulo conta também por pessoa (`LIMITE_POR_PESSOA`).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field, field_validator, model_validator
from supabase import Client

from app.dependencies import (
    barrar_desligado,
    get_current_user,
    get_participante_for_user,
    get_supabase_client,
    require_recurso_nsp,
)
from app.limiter import limiter
from app.services import limite_sem_ip
from app.services.seguranca_do_paciente import notificacoes
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp", tags=["seguranca-do-paciente"])

# A conta do limite sem IP é por endereço, e o endereço é o da rede: os
# computadores e o Wi-Fi do hospital saem por um só, como os celulares de uma
# mesma operadora. O teto da rede precisa caber no hospital inteiro, senão
# quem esgota a conta fecha o canal para todos. Cada rota tem a sua conta:
# esgotar as portas sem login não fecha o botão do módulo.
LIMITE_DA_REDE = "30/minute;300/hour"
# O botão do módulo sabe quem está logado e conta por pessoa.
LIMITE_POR_PESSOA = "5/minute;20/hour"

SETOR_INVALIDO = "Escolha o setor na lista."
FALHA_AO_REGISTRAR = "Não foi possível registrar a notificação agora. Tente de novo em instantes."


class RelatoDoIncidente(BaseModel):
    """As quatro telas do formulário, menos a origem, que vem da porta."""

    relato: str = Field(..., min_length=1, max_length=10000)
    leito_ou_atendimento: str | None = Field(default=None, max_length=60)
    setor_id: UUID
    data_ocorrencia: date
    turno: Literal["manha", "tarde", "noite"]
    hora_aproximada: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    chegou_ao_paciente: Literal["nao", "sem_dano", "com_dano", "nao_sei"]
    grave_ou_morte: bool | None = None
    percebido_ou_reclamacao: Literal["sim", "nao", "nao_sei"] | None = None
    anonimo: bool

    @field_validator("relato", "leito_ou_atendimento")
    @classmethod
    def _sem_espaco_sobrando(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return valor.strip() or None

    @field_validator("data_ocorrencia")
    @classmethod
    def _nao_e_futura(cls, valor: date) -> date:
        if valor > hoje_em_sao_paulo():
            raise ValueError("A data do incidente não pode ser depois de hoje.")
        return valor

    @model_validator(mode="after")
    def _gravidade_quando_houve_dano_ou_nao_sei(self):
        if not self.relato:
            raise ValueError("Conte o que aconteceu.")
        if self.chegou_ao_paciente in ("com_dano", "nao_sei"):
            if self.grave_ou_morte is None:
                raise ValueError("Diga se foi grave ou se houve morte.")
        else:
            self.grave_ou_morte = None
        return self


class EnvioPublico(RelatoDoIncidente):
    origem: Literal["qr", "endereco"]
    nome: str | None = Field(default=None, max_length=200)
    contato: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _identificado_deixa_nome_e_contato(self):
        self.nome = (self.nome or "").strip() or None
        self.contato = (self.contato or "").strip() or None
        if self.anonimo:
            self.nome = self.contato = None
        elif not self.nome or not self.contato:
            raise ValueError("Para notificar com o seu nome, deixe o nome e um e-mail ou telefone.")
        return self


def _setor_ativo(supabase, setor_id: str) -> bool:
    linhas = supabase.table("setores").select("id").eq("id", setor_id).eq("ativo", True).limit(1).execute().data
    return bool(linhas)


def _gravar_notificacao(supabase, envio: RelatoDoIncidente, **identificacao) -> dict:
    try:
        if not _setor_ativo(supabase, str(envio.setor_id)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=SETOR_INVALIDO)
        relato = envio.model_dump(mode="json")
        return notificacoes.registrar(supabase, relato, anonimo=envio.anonimo, **identificacao)
    except (APIError, httpx.HTTPError) as erro:
        # Detalhe do banco não vai para um canal aberto; quem notifica vê que
        # não deu e tenta de novo, com o relato ainda na tela.
        logger.error("Falha ao registrar a notificação de incidente: %s", type(erro).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=FALHA_AO_REGISTRAR) from erro


@router.post("/publico/notificacoes", status_code=status.HTTP_201_CREATED)
@limite_sem_ip.limitar(LIMITE_DA_REDE)
async def notificar_sem_login(
    request: Request,
    envio: EnvioPublico,
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O formulário público, pelo QR ou pelo endereço."""
    return _gravar_notificacao(supabase, envio, origem=envio.origem, nome=envio.nome, contato=envio.contato)


async def _quem_esta_logado(
    request: Request,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Todo usuário logado notifica pelo módulo, mesmo sem nenhum outro acesso
    ao Núcleo (Ajuste do plano #2045). Só o desligado fica de fora."""
    me = await get_participante_for_user(current_user, supabase)
    barrar_desligado(me)
    if not me:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cadastro não encontrado.")
    # O limitador roda depois das dependências e conta por esta pessoa.
    request.state.nsp_notificante_id = str(me["id"])
    return me


def _chave_da_pessoa(request: Request) -> str:
    """A conta do botão do módulo: quem está logado, e não a rede."""
    return "nsp-pessoa:" + request.state.nsp_notificante_id


@router.post("/notificacoes", status_code=status.HTTP_201_CREATED)
@limite_sem_ip.limitar(LIMITE_DA_REDE)
@limiter.limit(LIMITE_POR_PESSOA, key_func=_chave_da_pessoa)
async def notificar_pelo_modulo(
    request: Request,
    envio: RelatoDoIncidente,
    me: dict = Depends(_quem_esta_logado),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """O botão "Notificar incidente" do módulo: a identificação vem da sessão,
    e não do que a tela mandar."""
    return _gravar_notificacao(
        supabase,
        envio,
        origem=notificacoes.ORIGEM_MODULO,
        nome=me.get("nome_completo"),
        contato=me.get("email"),
        notificante_id=me["id"],
    )


@router.get("/publico/setores")
@limite_sem_ip.limitar("60/minute")
async def setores_do_formulario(request: Request, supabase: Client = Depends(get_supabase_client)) -> dict:
    """A lista de "Onde" do formulário: os setores ativos, pelo id."""
    linhas = supabase.table("setores").select("id, nome").eq("ativo", True).order("nome").execute().data or []
    return {"setores": [{"id": linha["id"], "nome": linha["nome"]} for linha in linhas]}


class ConsultaDeAcompanhamento(BaseModel):
    """O protocolo e uma das duas chaves: o código (anônima) ou o e-mail ou
    telefone (identificada). POST, para o código não ficar na URL."""

    protocolo: str = Field(..., min_length=1, max_length=20)
    codigo: str | None = Field(default=None, max_length=40)
    contato: str | None = Field(default=None, max_length=200)


NAO_ENCONTRADA = (
    "Não encontramos uma notificação com esses dados. Confira o protocolo e o código, "
    "ou o e-mail ou telefone que você deixou."
)


@router.post("/publico/acompanhamento")
@limite_sem_ip.limitar(LIMITE_DA_REDE)
async def acompanhar_notificacao(
    request: Request,
    consulta: ConsultaDeAcompanhamento,
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """A página de acompanhamento: só o estado, em palavras simples. O limite
    da rede segura quem tenta adivinhar o código (dez símbolos)."""
    try:
        situacao = notificacoes.consultar(supabase, consulta.protocolo, consulta.codigo, consulta.contato)
    except (APIError, httpx.HTTPError) as erro:
        logger.error("Falha ao consultar o acompanhamento da notificação: %s", type(erro).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível consultar agora. Tente novamente em instantes.",
        ) from erro
    if situacao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NAO_ENCONTRADA)
    return situacao


@router.get("/notificacoes")
@limite_sem_ip.limitar("60/minute")
async def lista_de_casos(
    request: Request,
    me: dict = Depends(require_recurso_nsp("casos")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Notificações: todos os casos, para quem tem o recurso de casos. Quem
    notificou só para a Presidência e o Acesso pleno."""
    com_identidade = "identidade_notificante" in me["recursos_nsp"]
    return {"notificacoes": notificacoes.listar(supabase, com_identidade=com_identidade)}
