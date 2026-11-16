"""Os documentos do Núcleo de Segurança do Paciente (issue #1767, ADR 0095).

Cada tipo (ato de designação, Regimento, Plano de Segurança do Paciente,
Termo, ata, outro) tem versões e uma única vigente. Publicar uma versão nova
troca a vigente e guarda a anterior, numa só transação: a função
`nsp_publicar_documento` da migration 147.

Não existe rota de exclusão nem de edição: a correção é uma versão nova, e a
trilha (quem publicou, quando, as versões anteriores) fica toda na lista.

Ler é do recurso `documentos` (membro com Termo válido, Presidência, Acesso
pleno); publicar é do `gerir_nucleo` (Presidência, Acesso pleno). Nesta fatia
a publicação ainda não dispara assinatura nem novo Termo.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field, model_validator
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp/documentos", tags=["seguranca-do-paciente"])

TipoDeDocumento = Literal["ato_designacao", "regimento", "plano_seguranca_paciente", "termo", "ata", "outro"]
NaturezaDaRevisao = Literal["material", "redacao"]

_CAMPOS_DA_LISTA = (
    "id, tipo, versao, titulo, texto, natureza_revisao, vigente, arquivo_assinado_path, publicado_por, publicado_em"
)

_INDISPONIVEL = "Os documentos do Núcleo estão indisponíveis agora. Tente de novo em instantes."


class PublicarDocumento(BaseModel):
    tipo: TipoDeDocumento
    titulo: str = Field(min_length=1, max_length=200)
    texto: str | None = Field(default=None, max_length=200_000)
    natureza_revisao: NaturezaDaRevisao | None = None

    @model_validator(mode="after")
    def _regimento_completo(self) -> PublicarDocumento:
        self.titulo = self.titulo.strip()
        if not self.titulo:
            raise ValueError("Dê um título ao documento.")
        self.texto = (self.texto or "").strip() or None
        if self.tipo == "regimento":
            if self.natureza_revisao is None:
                raise ValueError("Diga se a revisão do Regimento é material ou só de redação.")
            if self.texto is None:
                raise ValueError("O texto do Regimento é obrigatório.")
        return self


def _nomes(supabase, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    linhas = supabase.table("participantes").select("id, nome_completo").in_("id", sorted(ids)).execute().data or []
    return {linha["id"]: linha.get("nome_completo") for linha in linhas}


def _para_a_tela(linha: dict, nomes: dict[str, str]) -> dict:
    """A linha da lista: sem o texto (que vem na leitura) e com quem publicou."""
    return {
        "id": linha["id"],
        "tipo": linha["tipo"],
        "versao": linha["versao"],
        "titulo": linha["titulo"],
        "natureza_revisao": linha.get("natureza_revisao"),
        "vigente": bool(linha.get("vigente")),
        "tem_texto": bool(linha.get("texto")),
        "tem_arquivo_assinado": bool(linha.get("arquivo_assinado_path")),
        "publicado_em": linha.get("publicado_em"),
        "publicado_por": nomes.get(linha.get("publicado_por")),
    }


@router.get("")
@limiter.limit("60/minute")
async def listar_documentos(
    request: Request,
    _: dict = Depends(require_recurso_nsp("documentos")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Todas as versões de todos os tipos, a mais nova primeiro em cada tipo."""
    try:
        linhas = (
            supabase.table("nsp_documentos")
            .select(_CAMPOS_DA_LISTA)
            .order("tipo")
            .order("versao", desc=True)
            .execute()
            .data
            or []
        )
        nomes = _nomes(supabase, {linha["publicado_por"] for linha in linhas if linha.get("publicado_por")})
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Documentos do Núcleo ilegíveis: %s", erro)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_INDISPONIVEL) from erro
    return {"documentos": [_para_a_tela(linha, nomes) for linha in linhas]}


@router.get("/{documento_id}")
@limiter.limit("60/minute")
async def ler_documento(
    request: Request,
    documento_id: str,
    _: dict = Depends(require_recurso_nsp("documentos")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Uma versão inteira, com o texto (o Regimento e o Plano lidos na tela)."""
    try:
        linhas = (
            supabase.table("nsp_documentos").select(_CAMPOS_DA_LISTA).eq("id", documento_id).limit(1).execute().data
            or []
        )
        nomes = _nomes(supabase, {linhas[0]["publicado_por"]} if linhas and linhas[0].get("publicado_por") else set())
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Documento do Núcleo ilegível: %s", erro)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_INDISPONIVEL) from erro
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")
    return {**_para_a_tela(linhas[0], nomes), "texto": linhas[0].get("texto")}


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def publicar_documento(
    request: Request,
    corpo: PublicarDocumento,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Publica a versão seguinte do tipo, que passa a ser a vigente."""
    try:
        novo = (
            supabase.rpc(
                "nsp_publicar_documento",
                {
                    "p_tipo": corpo.tipo,
                    "p_titulo": corpo.titulo,
                    "p_texto": corpo.texto,
                    "p_natureza_revisao": corpo.natureza_revisao,
                    "p_publicado_por": me["id"],
                },
            )
            .execute()
            .data
        )
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Publicação de documento do Núcleo falhou: %s", erro)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_INDISPONIVEL) from erro
    linha = novo[0] if isinstance(novo, list) else novo
    return _para_a_tela(linha, {me["id"]: me.get("nome_completo")})
