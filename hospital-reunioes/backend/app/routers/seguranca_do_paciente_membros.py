"""Segurança do Paciente: os membros do Núcleo (issue #1766, PRD #1764, ADR 0095).

Uma linha por Participação no Núcleo, com papel, área, registro profissional,
vigência, estado e situação do Termo. A Presidência e o Acesso pleno cadastram,
editam, renovam e encerram (`gerir_nucleo`); quem tem o recurso `membros` lê.

Nada se apaga: encerrar termina a vigência no dia e a linha fica, para a
composição de qualquer data passada. Toda mudança grava a trilha (autor,
campo, valor anterior e novo). Não existe rota DELETE, e o banco recusa apagar
Participação (migration 150).

O estado do membro sai da função pura de `membros`. Cadastrar gera o Termo de
Adesão e o envia para assinatura (issue #1768, serviço `termo`); renovar a
vigência e mudar o papel geram novo Termo (issue #1769). Sem Regimento vigente
ou com a assinatura eletrônica fora, a mudança fica de pé e a resposta traz o
aviso em `aviso_termo`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from supabase import Client

from app.dependencies import get_supabase_client, require_recurso_nsp, selecionar_participantes
from app.limiter import limiter
from app.services import colegiados
from app.services.seguranca_do_paciente import termo
from app.services.seguranca_do_paciente.membros import estado_do_membro, vigente_em
from app.services.seguranca_do_paciente.permissao import NUCLEO, PAPEIS_DO_NUCLEO, hoje_em_sao_paulo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nsp/membros", tags=["seguranca-do-paciente"])

Papel = Literal["presidencia", "suplente", "membro"]

# O registro profissional mora no cadastro da pessoa (migration 146); a tela
# dos membros o edita junto, com a mesma trilha.
CAMPOS_DO_REGISTRO = ("conselho_profissional", "registro_profissional", "registro_uf")
CAMPOS_DA_PARTICIPACAO = ("papel", "area", "vigencia_inicio", "vigencia_fim")


def _texto_opcional(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpo = valor.strip()
    return limpo or None


class _Registro(BaseModel):
    conselho_profissional: str | None = Field(default=None, max_length=20)
    registro_profissional: str | None = Field(default=None, max_length=30)
    registro_uf: str | None = None

    @field_validator("conselho_profissional", "registro_profissional")
    @classmethod
    def _limpar(cls, valor: str | None) -> str | None:
        return _texto_opcional(valor)

    @field_validator("registro_uf")
    @classmethod
    def _uf(cls, valor: str | None) -> str | None:
        valor = _texto_opcional(valor)
        if valor is None:
            return None
        valor = valor.upper()
        if len(valor) != 2 or not valor.isalpha() or not valor.isascii():
            raise ValueError("A UF do registro tem duas letras")
        return valor


class MembroNovo(_Registro):
    participante_id: str = Field(min_length=1, max_length=10)
    papel: Papel
    area: str | None = Field(default=None, max_length=120)
    vigencia_inicio: date
    vigencia_fim: date

    @field_validator("area")
    @classmethod
    def _area(cls, valor: str | None) -> str | None:
        return _texto_opcional(valor)


class MembroEdicao(_Registro):
    papel: Papel | None = None
    area: str | None = Field(default=None, max_length=120)
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None

    @field_validator("area")
    @classmethod
    def _area(cls, valor: str | None) -> str | None:
        return _texto_opcional(valor)


class Renovacao(BaseModel):
    vigencia_fim: date


class Encerramento(BaseModel):
    # Sem data, encerra hoje.
    data: date | None = None


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def _nucleo_id(supabase) -> str:
    nucleo_id = colegiados.id_do_colegiado(supabase, NUCLEO)
    if not nucleo_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O Núcleo ainda não foi criado")
    return nucleo_id


def _pessoas(supabase, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    linhas = (
        selecionar_participantes(
            supabase,
            "id, nome_completo, " + ", ".join(CAMPOS_DO_REGISTRO),
            lambda q: q.in_("id", sorted(set(ids))),
        ).data
        or []
    )
    return {linha["id"]: linha for linha in linhas}


def _linha(participacao: dict, pessoa: dict | None, hoje: date, revisao_material_em: str | None) -> dict[str, Any]:
    """O que a tela mostra de um membro. Sem e-mail nem telefone."""
    pessoa = pessoa or {}
    return {
        "id": participacao["id"],
        "participante_id": participacao["participante_id"],
        "nome": pessoa.get("nome_completo"),
        "papel": participacao["papel"],
        "area": participacao.get("area"),
        **{campo: pessoa.get(campo) for campo in CAMPOS_DO_REGISTRO},
        "vigencia_inicio": participacao["vigencia_inicio"],
        "vigencia_fim": participacao["vigencia_fim"],
        "encerrada_em": participacao.get("encerrada_em"),
        "termo_gerado_em": participacao.get("termo_gerado_em"),
        "termo_enviado_em": participacao.get("termo_enviado_em"),
        "termo_assinado_em": participacao.get("termo_assinado_em"),
        "estado": estado_do_membro(participacao, hoje),
        "termo_pendente": termo.novo_termo_pendente(participacao, revisao_material_em, hoje),
    }


_ORDEM_DO_PAPEL = {papel: i for i, papel in enumerate(PAPEIS_DO_NUCLEO)}


def _linhas(supabase, participacoes: list[dict]) -> list[dict]:
    hoje = hoje_em_sao_paulo()
    pessoas = _pessoas(supabase, [p["participante_id"] for p in participacoes])
    revisao = termo.revisao_material_em(supabase)
    linhas = [_linha(p, pessoas.get(p["participante_id"]), hoje, revisao) for p in participacoes]
    return sorted(
        linhas,
        key=lambda linha: (
            linha["estado"] == "encerrado",
            _ORDEM_DO_PAPEL.get(linha["papel"], 99),
            (linha["nome"] or "").lower(),
        ),
    )


def _participacao(supabase, nucleo_id: str, participacao_id: str) -> dict:
    participacao = colegiados.participacao_do_colegiado(supabase, nucleo_id, participacao_id)
    if not participacao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participação não encontrada")
    return participacao


@router.get("")
@limiter.limit("60/minute")
async def listar_membros(
    request: Request,
    data: date | None = Query(default=None, description="Sem data, todas; com data, quem valia naquele dia."),
    _: dict = Depends(require_recurso_nsp("membros")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Todas as Participações do Núcleo, encerradas inclusive, com o estado de
    hoje. Com `data`, a composição daquele dia: quem tinha a vigência valendo,
    encerrado depois ou não."""
    participacoes = colegiados.participacoes_do_colegiado(supabase, _nucleo_id(supabase))
    if data is not None:
        participacoes = [p for p in participacoes if vigente_em(p, data)]
    return {"data": data.isoformat() if data else None, "membros": _linhas(supabase, participacoes)}


@router.get("/pessoas")
@limiter.limit("60/minute")
async def pessoas_para_o_cadastro(
    request: Request,
    _: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """As pessoas ativas do cadastro, só id e nome, para escolher no cadastro."""
    linhas = (
        supabase.table("participantes")
        .select("id, nome_completo")
        .eq("ativo", True)
        .order("nome_completo")
        .execute()
        .data
    ) or []
    return {"pessoas": [{"id": linha["id"], "nome": linha["nome_completo"]} for linha in linhas]}


@router.get("/{participacao_id}/trilha")
@limiter.limit("60/minute")
async def trilha_do_membro(
    request: Request,
    participacao_id: str,
    _: dict = Depends(require_recurso_nsp("membros")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    _participacao(supabase, _nucleo_id(supabase), participacao_id)
    linhas = (
        supabase.table("participacoes_trilha")
        .select("acao, campo, valor_anterior, valor_novo, motivo, autor_id, created_at")
        .eq("participacao_id", participacao_id)
        .order("created_at", desc=True)
        .execute()
        .data
    ) or []
    autores = _pessoas(supabase, [linha["autor_id"] for linha in linhas])
    return {
        "trilha": [
            {
                "acao": linha["acao"],
                "campo": linha["campo"],
                "valor_anterior": linha["valor_anterior"],
                "valor_novo": linha["valor_novo"],
                "motivo": linha.get("motivo"),
                "autor": (autores.get(linha["autor_id"]) or {}).get("nome_completo"),
                "created_at": linha["created_at"],
            }
            for linha in linhas
        ]
    }


# ---------------------------------------------------------------------------
# Escrita: sempre com trilha
# ---------------------------------------------------------------------------


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    return valor.isoformat() if isinstance(valor, date) else str(valor)


def _gravar_trilha(supabase, participacao_id: str, autor_id: str, acao: str, mudancas: list[tuple]) -> None:
    """Uma linha por campo mudado: (campo, anterior, novo)."""
    if not mudancas:
        return
    supabase.table("participacoes_trilha").insert(
        [
            {
                "participacao_id": participacao_id,
                "autor_id": autor_id,
                "acao": acao,
                "campo": campo,
                "valor_anterior": _texto(anterior),
                "valor_novo": _texto(novo),
            }
            for campo, anterior, novo in mudancas
        ]
    ).execute()


def _mudancas(atual: dict, pedido: dict) -> list[tuple]:
    return [
        (campo, atual.get(campo), valor) for campo, valor in pedido.items() if _texto(valor) != _texto(atual.get(campo))
    ]


def _atualizar_registro(supabase, participante_id: str, pessoa: dict, pedido: dict) -> list[tuple]:
    """Grava no cadastro da pessoa o que mudou do registro profissional."""
    mudancas = _mudancas(pessoa, pedido)
    if mudancas:
        supabase.table("participantes").update({campo: novo for campo, _, novo in mudancas}).eq(
            "id", participante_id
        ).execute()
    return mudancas


def _vigencia_valida(inicio: date, fim: date) -> None:
    if fim < inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O fim da vigência não pode ser antes do início",
        )


def _aberta(participacao: dict) -> None:
    if participacao.get("encerrada_em"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta participação foi encerrada. Para a pessoa voltar, cadastre de novo.",
        )


def _responder(supabase, participacao_id: str, nucleo_id: str) -> dict:
    participacao = _participacao(supabase, nucleo_id, participacao_id)
    return _linhas(supabase, [participacao])[0]


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def cadastrar_membro(
    request: Request,
    body: MembroNovo,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    nucleo_id = _nucleo_id(supabase)
    _vigencia_valida(body.vigencia_inicio, body.vigencia_fim)
    pessoa = _pessoas(supabase, [body.participante_id]).get(body.participante_id)
    if not pessoa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pessoa não encontrada no cadastro")
    abertas = (
        supabase.table("participacoes")
        .select("id")
        .eq("colegiado_id", nucleo_id)
        .eq("participante_id", body.participante_id)
        .is_("encerrada_em", "null")
        .execute()
        .data
    ) or []
    if abertas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta pessoa já tem uma participação aberta no Núcleo. Renove ou encerre a atual.",
        )
    nova = (
        supabase.table("participacoes")
        .insert(
            {
                "colegiado_id": nucleo_id,
                "participante_id": body.participante_id,
                "papel": body.papel,
                "area": body.area,
                "vigencia_inicio": body.vigencia_inicio.isoformat(),
                "vigencia_fim": body.vigencia_fim.isoformat(),
            }
        )
        .execute()
        .data
    )[0]
    _gravar_trilha(
        supabase,
        nova["id"],
        me["id"],
        "cadastro",
        [
            ("papel", None, body.papel),
            ("vigencia_inicio", None, body.vigencia_inicio),
            ("vigencia_fim", None, body.vigencia_fim),
        ]
        + ([("area", None, body.area)] if body.area else []),
    )
    registro = {campo: getattr(body, campo) for campo in CAMPOS_DO_REGISTRO if getattr(body, campo) is not None}
    _gravar_trilha(
        supabase, nova["id"], me["id"], "edicao", _atualizar_registro(supabase, body.participante_id, pessoa, registro)
    )
    aviso = await run_in_threadpool(_gerar_termo, supabase, nova, me["id"])
    return {**_responder(supabase, nova["id"], nucleo_id), "aviso_termo": aviso}


def _gerar_termo(supabase, participacao: dict, autor_id: str) -> str | None:
    """Gera e envia o Termo: no cadastro, na renovação e na mudança de papel
    (issue #1769). A mudança já está gravada: falha aqui vira aviso na
    resposta, e a ficha tem o reenvio."""
    try:
        return termo.novo_termo(supabase, participacao, autor_id=autor_id).get("erro")
    except termo.TermoNaoGeradoError as erro:
        return str(erro)
    except Exception:  # noqa: BLE001 (o cadastro não se desfaz por falha do Termo)
        logger.exception("Termo de Adesão da Participação %s não gerado", participacao.get("id"))
        return "O Termo de Adesão não foi gerado agora. Use Reenviar o Termo na ficha do membro."


@router.patch("/{participacao_id}")
@limiter.limit("30/minute")
async def editar_membro(
    request: Request,
    participacao_id: str,
    body: MembroEdicao,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    nucleo_id = _nucleo_id(supabase)
    atual = _participacao(supabase, nucleo_id, participacao_id)
    _aberta(atual)
    pedido = body.model_dump(exclude_unset=True)
    da_participacao = {campo: pedido[campo] for campo in CAMPOS_DA_PARTICIPACAO if campo in pedido}
    if any(da_participacao.get(campo, "") is None for campo in ("papel", "vigencia_inicio", "vigencia_fim")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Papel e vigência não ficam em branco"
        )
    mudancas = _mudancas(atual, da_participacao)
    inicio = date.fromisoformat(_texto(da_participacao.get("vigencia_inicio", atual["vigencia_inicio"]))[:10])
    fim = date.fromisoformat(_texto(da_participacao.get("vigencia_fim", atual["vigencia_fim"]))[:10])
    _vigencia_valida(inicio, fim)
    muda_o_papel = any(campo == "papel" for campo, _, _ in mudancas)
    if mudancas:
        # O Termo novo fica pendente junto com a mudança (issue #1769).
        marca = termo.marca_do_novo_termo(atual) if muda_o_papel else {}
        supabase.table("participacoes").update({**{campo: _texto(novo) for campo, _, novo in mudancas}, **marca}).eq(
            "id", participacao_id
        ).execute()
        _gravar_trilha(
            supabase, participacao_id, me["id"], "mudanca_de_papel", [m for m in mudancas if m[0] == "papel"]
        )
        _gravar_trilha(supabase, participacao_id, me["id"], "edicao", [m for m in mudancas if m[0] != "papel"])
    registro = {campo: pedido[campo] for campo in CAMPOS_DO_REGISTRO if campo in pedido}
    if registro:
        pessoa = _pessoas(supabase, [atual["participante_id"]]).get(atual["participante_id"]) or {}
        _gravar_trilha(
            supabase,
            participacao_id,
            me["id"],
            "edicao",
            _atualizar_registro(supabase, atual["participante_id"], pessoa, registro),
        )
    aviso = None
    if muda_o_papel:
        editada = _participacao(supabase, nucleo_id, participacao_id)
        aviso = await run_in_threadpool(_gerar_termo, supabase, editada, me["id"])
    return {**_responder(supabase, participacao_id, nucleo_id), "aviso_termo": aviso}


@router.post("/{participacao_id}/renovar")
@limiter.limit("30/minute")
async def renovar_membro(
    request: Request,
    participacao_id: str,
    body: Renovacao,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Estende o fim da vigência. A mesma Participação segue, com a trilha
    guardando o fim anterior."""
    nucleo_id = _nucleo_id(supabase)
    atual = _participacao(supabase, nucleo_id, participacao_id)
    _aberta(atual)
    if body.vigencia_fim.isoformat() <= str(atual["vigencia_fim"])[:10]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A renovação tem de levar o fim da vigência para depois do fim atual",
        )
    supabase.table("participacoes").update(
        {"vigencia_fim": body.vigencia_fim.isoformat(), **termo.marca_do_novo_termo(atual)}
    ).eq("id", participacao_id).execute()
    _gravar_trilha(
        supabase, participacao_id, me["id"], "renovacao", [("vigencia_fim", atual["vigencia_fim"], body.vigencia_fim)]
    )
    renovada = _participacao(supabase, nucleo_id, participacao_id)
    aviso = await run_in_threadpool(_gerar_termo, supabase, renovada, me["id"])
    return {**_responder(supabase, participacao_id, nucleo_id), "aviso_termo": aviso}


@router.post("/{participacao_id}/encerrar")
@limiter.limit("30/minute")
async def encerrar_membro(
    request: Request,
    participacao_id: str,
    body: Encerramento,
    me: dict = Depends(require_recurso_nsp("gerir_nucleo")),
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Encerra sem apagar: a vigência termina no dia (inclusive) e a linha
    fica para o histórico e para a composição das datas em que valia."""
    nucleo_id = _nucleo_id(supabase)
    atual = _participacao(supabase, nucleo_id, participacao_id)
    _aberta(atual)
    dia = body.data or hoje_em_sao_paulo()
    if dia.isoformat() < str(atual["vigencia_inicio"])[:10]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O encerramento não pode ser antes do início da vigência",
        )
    novo_fim = min(dia.isoformat(), str(atual["vigencia_fim"])[:10])
    supabase.table("participacoes").update({"encerrada_em": dia.isoformat(), "vigencia_fim": novo_fim}).eq(
        "id", participacao_id
    ).execute()
    _gravar_trilha(
        supabase,
        participacao_id,
        me["id"],
        "encerramento",
        _mudancas(atual, {"encerrada_em": dia.isoformat(), "vigencia_fim": novo_fim}),
    )
    return _responder(supabase, participacao_id, nucleo_id)
