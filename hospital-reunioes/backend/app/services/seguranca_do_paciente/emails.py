"""O registro de e-mail do Núcleo, com retentativa (issue #1985, ADR 0107 decisão 8).

Todo e-mail do Núcleo nasce como linha de `nsp_avisos` antes de sair: o
registro dos avisos da Fase 1 virou o registro único do módulo. A linha guarda
o assunto, o texto, o modelo do HTML e o que o modelo precisa; o HTML é
montado na hora do envio.

As regras de tempo são as da Ouvidoria, pelas mesmas funções puras:

- **Janela comercial:** o registro urgente sai na hora; os demais esperam a
  próxima abertura do expediente (`inicio_da_contagem`).
- **Retentativa:** a falha do provedor devolve a linha à fila com espera
  crescente (`proxima_tentativa`). Na terceira falha a linha vira falhou e o
  admin técnico é avisado, por fora da fila.

- **Reconferência:** o aviso do Termo e da vigência que esperou na fila só
  sai se ainda é o marco do dia da Participação (`avisos.ainda_devidos`).

O envio reivindica a linha antes de chamar o provedor (`pendente` para
`enviando`, condicional): a rodada do job que cruza com outra não manda o
mesmo e-mail duas vezes.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from typing import Any

from postgrest.exceptions import APIError

from app.dependencies import selecionar_participantes
from app.services.email_constants import get_logo_data_uri
from app.services.email_service import _enviar_email, jinja_env
from app.services.ouvidoria_notificacoes import avisar_admins_tecnicos, proxima_tentativa
from app.services.ouvidoria_prazos import inicio_da_contagem
from app.services.paginacao import ler_tudo

logger = logging.getLogger(__name__)

TABELA = "nsp_avisos"

PENDENTE = "pendente"
ENVIANDO = "enviando"
ENVIADO = "enviado"
FALHOU = "falhou"

SEM_EMAIL = "A pessoa não tem e-mail no cadastro."
FALHA_DO_ENVIO = "O provedor de e-mail não aceitou o envio."
MARCO_MUDOU = "A Participação mudou antes do envio; aviso não enviado."

# Só os modelos do Núcleo: o nome vem do banco e vira um template carregado.
_MODELO = re.compile(r"^email_nsp_[a-z_]+\.html$")

_CAMPOS = (
    "id, participacao_id, caso_id, marco, referencia, destinatario_id, situacao, tentativas, "
    "enviar_a_partir_de, urgente, assunto, texto, modelo, contexto"
)


def _utc(momento: datetime) -> str:
    return momento.astimezone(UTC).isoformat()


def quando_enviar(agora: datetime, urgente: bool, feriados: frozenset[date]) -> datetime:
    """O urgente sai agora; o resto espera o expediente abrir."""
    return agora if urgente else inicio_da_contagem(agora, feriados)


def registrar(
    supabase,
    *,
    marco: str,
    referencia: str,
    destinatario_id: str,
    assunto: str,
    texto: str,
    modelo: str,
    contexto: dict[str, Any],
    agora: datetime,
    feriados: frozenset[date] = frozenset(),
    urgente: bool = False,
    participacao_id: str | None = None,
    caso_id: str | None = None,
) -> dict | None:
    """Grava o e-mail na fila, antes de qualquer envio. None quando a mesma
    linha (Participação, marco, referência, destinatário) já existe."""
    if not _MODELO.match(modelo):
        raise ValueError(f"Modelo de e-mail fora do Núcleo: {modelo}")
    try:
        return (
            supabase.table(TABELA)
            .insert(
                {
                    "participacao_id": participacao_id,
                    "caso_id": caso_id,
                    "marco": marco,
                    "referencia": referencia,
                    "destinatario_id": destinatario_id,
                    "situacao": PENDENTE,
                    "tentativas": 0,
                    "urgente": urgente,
                    "enviar_a_partir_de": _utc(quando_enviar(agora, urgente, feriados)),
                    "assunto": assunto,
                    "texto": texto,
                    "modelo": modelo,
                    "contexto": contexto,
                }
            )
            .execute()
            .data[0]
        )
    except APIError as erro:
        if getattr(erro, "code", None) != "23505":
            raise
        return None


def _reivindicar(supabase, registro_id: str) -> bool:
    resposta = (
        supabase.table(TABELA).update({"situacao": ENVIANDO}).eq("id", registro_id).eq("situacao", PENDENTE).execute()
    )
    return bool(resposta.data)


def _email_de(supabase, pessoa_id: str) -> str:
    resposta = selecionar_participantes(supabase, "id, email", lambda q: q.eq("id", pessoa_id))
    pessoas = resposta.data or []
    return ((pessoas[0].get("email") if pessoas else None) or "").strip()


def _alertar_admin_tecnico(supabase, registro: dict, erro: str | None) -> None:
    """Sem nada do conteúdo do e-mail: só o que o admin precisa para achar a linha."""
    avisar_admins_tecnicos(
        supabase,
        f"Núcleo de Segurança do Paciente: falha no envio do e-mail {registro.get('marco')}",
        (
            "O e-mail abaixo falhou nas tres tentativas e nao foi entregue:\n\n"
            f"- Registro: {registro.get('id')}\n"
            f"- Marco: {registro.get('marco')}\n"
            f"- Destinatario (cadastro): {registro.get('destinatario_id')}\n"
            f"- Ultimo erro: {erro}\n\n"
            "Confira o provedor de e-mail.\n"
        ),
    )


def despachar(supabase, registro: dict, agora: datetime) -> str | None:
    """Tenta entregar um registro da fila: ENVIADO, FALHOU (a tentativa não deu
    certo) ou None (outra rodada já o levou)."""
    if not _reivindicar(supabase, registro["id"]):
        return None
    tentativas = (registro.get("tentativas") or 0) + 1
    try:
        email = _email_de(supabase, registro["destinatario_id"])
        if not email:
            supabase.table(TABELA).update({"situacao": FALHOU, "erro": SEM_EMAIL, "tentativas": tentativas}).eq(
                "id", registro["id"]
            ).execute()
            logger.warning("[E-mails NSP] Registro %s sem e-mail no cadastro.", registro["id"])
            return FALHOU
        html = jinja_env.get_template(registro["modelo"]).render(
            **(registro.get("contexto") or {}), logo_base64=get_logo_data_uri()
        )
        erro = None if _enviar_email(email, registro["assunto"], html, registro["texto"]) else FALHA_DO_ENVIO
    except Exception as falha:  # noqa: BLE001 (a falha devolve a linha à fila)
        erro = f"Falha no envio: {type(falha).__name__}"

    if erro is None:
        supabase.table(TABELA).update({"situacao": ENVIADO, "enviado_em": _utc(agora), "tentativas": tentativas}).eq(
            "id", registro["id"]
        ).execute()
        return ENVIADO

    proxima = proxima_tentativa(agora, tentativas)
    mudanca: dict[str, Any] = {
        "tentativas": tentativas,
        "erro": erro,
        "situacao": FALHOU if proxima is None else PENDENTE,
    }
    if proxima is not None:
        mudanca["enviar_a_partir_de"] = _utc(proxima)
    supabase.table(TABELA).update(mudanca).eq("id", registro["id"]).execute()
    logger.warning("[E-mails NSP] Registro %s (%s) não saiu: %s", registro["id"], registro.get("marco"), erro)
    if proxima is None:
        _alertar_admin_tecnico(supabase, registro, erro)
    return FALHOU


def despachar_se_puder(supabase, registro: dict | None, agora: datetime) -> str | None:
    """Entrega já, quando a hora do registro chegou: o desfecho de `despachar`.
    Fora dela, None, e o job leva."""
    if not registro:
        return None
    quando = registro.get("enviar_a_partir_de")
    if quando and datetime.fromisoformat(str(quando)) > agora:
        return None
    return despachar(supabase, registro, agora)


def _so_o_que_ainda_vale(supabase, linhas: list[dict], agora: datetime) -> list[dict]:
    """O aviso do Termo e da vigência que esperou na fila reconfere a
    Participação antes de sair, como a cobrança da Ouvidoria retida pela
    janela: o que deixou de ser o marco do dia vira falhou, sem alerta."""
    from app.services.seguranca_do_paciente import avisos  # avisos importa este módulo

    dos_avisos = [
        linha for linha in linhas if linha.get("participacao_id") and linha.get("marco") in avisos.DESTINATARIOS
    ]
    if not dos_avisos:
        return linhas
    valem = avisos.ainda_devidos(supabase, (linha["participacao_id"] for linha in dos_avisos), agora)
    velhos = {
        linha["id"]
        for linha in dos_avisos
        if (linha["participacao_id"], linha["marco"], linha["referencia"]) not in valem
    }
    for registro_id in velhos:
        supabase.table(TABELA).update({"situacao": FALHOU, "erro": MARCO_MUDOU}).eq("id", registro_id).eq(
            "situacao", PENDENTE
        ).execute()
        logger.info("[E-mails NSP] Registro %s não saiu: a Participação mudou antes do envio.", registro_id)
    return [linha for linha in linhas if linha["id"] not in velhos]


def despachar_pendentes(supabase, agora: datetime) -> dict[str, int]:
    """O job de 10 em 10 minutos: entrega o que já pode sair."""
    linhas = ler_tudo(
        lambda: (
            supabase.table(TABELA)
            .select(_CAMPOS)
            .eq("situacao", PENDENTE)
            .lte("enviar_a_partir_de", _utc(agora))
            .order("id")
        ),
        rotulo="fila de e-mails do Núcleo",
    )
    linhas = _so_o_que_ainda_vale(supabase, linhas, agora)
    resultado = {"enviados": 0, "falhas": 0}
    for linha in linhas:
        try:
            desfecho = despachar(supabase, linha, agora)
        except Exception as falha:  # noqa: BLE001 (uma linha que falha não para as outras)
            logger.error("[E-mails NSP] Registro %s falhou no despacho: %s", linha.get("id"), type(falha).__name__)
            desfecho = FALHOU
        if desfecho == ENVIADO:
            resultado["enviados"] += 1
        elif desfecho == FALHOU:
            resultado["falhas"] += 1
    return resultado
