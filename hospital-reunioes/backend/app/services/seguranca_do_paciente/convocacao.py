"""A convocação das reuniões do Núcleo (issue #1773, PRD #1764).

Um clique da Presidência manda o e-mail nominal a cada membro que conta para
quórum (Ativo, A vencer e Em carência, pela função pura de `membros`), com a
data e a hora absolutas, e grava quem foi convocado. O e-mail só traz a data,
a hora, o tipo e o link: o conteúdo do Núcleo fica na tela.

A gravação vem antes do envio: a chave (reunião, pessoa) do banco faz o
segundo clique bater na guarda, em vez de mandar o e-mail duas vezes.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any

from postgrest.exceptions import APIError

from app.config import settings
from app.dependencies import selecionar_participantes
from app.services.email_constants import get_logo_data_uri
from app.services.email_service import _enviar_email, jinja_env
from app.services.seguranca_do_paciente.membros import estado_do_membro

logger = logging.getLogger(__name__)

TABELA = "nsp_convocados"

ESTADOS_DE_QUORUM = ("ativo", "a_vencer", "em_carencia")

_DIAS_DA_SEMANA = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


class JaConvocadaError(RuntimeError):
    def __init__(self, convocada_em: str | None):
        super().__init__(convocada_em)
        self.convocada_em = convocada_em


class NinguemParaConvocarError(RuntimeError):
    pass


def quando(dia: date, hora: time) -> str:
    """'segunda-feira, 15/03/2027, às 09:00': a data e a hora sem 'amanhã'."""
    return f"{_DIAS_DA_SEMANA[dia.weekday()]}, {dia.strftime('%d/%m/%Y')}, às {hora.strftime('%H:%M')}"


def quem_convocar(supabase, nucleo_id: str, hoje: date) -> list[dict[str, Any]]:
    """As pessoas que contam para quórum hoje, uma vez cada, com nome, e-mail e
    estado. Participação que ainda não começou fica de fora."""
    participacoes = (
        supabase.table("participacoes")
        .select("participante_id, vigencia_inicio, vigencia_fim, encerrada_em, termo_assinado_em")
        .eq("colegiado_id", nucleo_id)
        .lte("vigencia_inicio", hoje.isoformat())
        .execute()
        .data
        or []
    )
    estados: dict[str, str] = {}
    for p in participacoes:
        estado = estado_do_membro(p, hoje)
        if estado in ESTADOS_DE_QUORUM and p["participante_id"] not in estados:
            estados[p["participante_id"]] = estado
    if not estados:
        return []
    pessoas = (
        selecionar_participantes(supabase, "id, nome_completo, email", lambda q: q.in_("id", sorted(estados))).data
        or []
    )
    return [
        {"participante_id": p["id"], "nome": p.get("nome_completo"), "email": p.get("email"), "estado": estados[p["id"]]}
        for p in sorted(pessoas, key=lambda p: (p.get("nome_completo") or "").lower())
    ]


def convocados(supabase, id_reuniao: str) -> list[dict[str, Any]]:
    """Quem foi convocado para a reunião, com o nome de hoje do cadastro."""
    linhas = (
        supabase.table(TABELA)
        .select("participante_id, estado, email_enviado, convocado_em")
        .eq("id_reuniao", id_reuniao)
        .execute()
        .data
        or []
    )
    if not linhas:
        return []
    nomes = {
        p["id"]: p.get("nome_completo")
        for p in (
            selecionar_participantes(
                supabase, "id, nome_completo", lambda q: q.in_("id", sorted({x["participante_id"] for x in linhas}))
            ).data
            or []
        )
    }
    return sorted(
        ({**linha, "nome": nomes.get(linha["participante_id"])} for linha in linhas),
        key=lambda linha: (linha["nome"] or "").lower(),
    )


def _mensagem(pessoa: dict, reuniao: dict, dia: date, hora: time) -> tuple[str, str, str]:
    momento = quando(dia, hora)
    link = f"{settings.frontend_url}/seguranca-do-paciente/reunioes"
    assunto = f"Convocação: {reuniao['tipo']} do Núcleo de Segurança do Paciente, {dia.strftime('%d/%m/%Y')}"
    texto = (
        f"Olá, {pessoa['nome']}.\n\n"
        "Você está convocado para a reunião do Núcleo de Segurança do Paciente:\n"
        f"- {reuniao.get('titulo') or reuniao['tipo']}\n"
        f"- Tipo: {reuniao['tipo']}\n"
        f"- Quando: {momento} (horário de Brasília)\n\n"
        f"A pauta está no app, em Segurança do Paciente, Reuniões: {link}\n"
    )
    html = jinja_env.get_template("email_nsp_convocacao.html").render(
        nome=pessoa["nome"],
        titulo=reuniao.get("titulo") or reuniao["tipo"],
        tipo=reuniao["tipo"],
        quando=momento,
        link=link,
        logo_base64=get_logo_data_uri(),
    )
    return assunto, html, texto


def convocar(supabase, reuniao: dict, *, nucleo_id: str, autor_id: str, agora: datetime) -> list[dict[str, Any]]:
    """Grava os convocados e manda o e-mail a cada um. Devolve quem foi
    convocado, com o resultado do envio."""
    ja = (
        supabase.table(TABELA)
        .select("convocado_em")
        .eq("id_reuniao", reuniao["id_reuniao"])
        .limit(1)
        .execute()
        .data
        or []
    )
    if ja:
        raise JaConvocadaError(ja[0].get("convocado_em"))
    pessoas = quem_convocar(supabase, nucleo_id, agora.date())
    if not pessoas:
        raise NinguemParaConvocarError(reuniao["id_reuniao"])
    try:
        supabase.table(TABELA).insert(
            [
                {
                    "id_reuniao": reuniao["id_reuniao"],
                    "participante_id": p["participante_id"],
                    "estado": p["estado"],
                    "email_enviado": False,
                    "convocado_em": agora.isoformat(),
                    "convocado_por": autor_id,
                }
                for p in pessoas
            ]
        ).execute()
    except APIError as erro:
        if getattr(erro, "code", None) != "23505":
            raise
        raise JaConvocadaError(None) from erro

    dia = date.fromisoformat(str(reuniao["data"])[:10])
    hora = time.fromisoformat(str(reuniao["hora_inicio"])[:8])
    for pessoa in pessoas:
        enviado = False
        if pessoa.get("email"):
            assunto, html, texto = _mensagem(pessoa, reuniao, dia, hora)
            enviado = bool(_enviar_email(pessoa["email"], assunto, html, texto))
        pessoa["email_enviado"] = enviado
        if enviado:
            supabase.table(TABELA).update({"email_enviado": True}).eq("id_reuniao", reuniao["id_reuniao"]).eq(
                "participante_id", pessoa["participante_id"]
            ).execute()
        else:
            logger.warning(
                "Convocação da reunião %s sem e-mail para %s", reuniao["id_reuniao"], pessoa["participante_id"]
            )
    return [{k: v for k, v in p.items() if k != "email"} for p in pessoas]
