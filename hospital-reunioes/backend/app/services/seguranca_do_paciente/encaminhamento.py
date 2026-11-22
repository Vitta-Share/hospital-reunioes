"""Encaminhar da tela de triagem (issue #1995, PRD #1979, ADR 0095 decisão 11
e ADR 0107 decisão 8).

A Presidência manda o caso a um ou mais destinos, com o motivo em uma frase,
e o protocolo do Núcleo fica como está:

- **Núcleo**: o caso continua na triagem do Núcleo, junto do outro destino;
- **Ouvidoria**: um e-mail ao ouvidor, pelo registro de e-mail do Núcleo, com
  o protocolo, o motivo e o relato. A criação automática da manifestação é da
  Fase 4;
- **Canal de Conduta**: só a orientação na tela. Nada é enviado e nada do
  caso é gravado fora do Núcleo, nem link (ADR 0095, decisão 11);
- **Fora de escopo**: encerra o caso com a orientação de uma frase, que quem
  notificou vê na página de acompanhamento. Não se soma a outro destino.

Sem o Núcleo entre os destinos, o caso sai da fila: vai a Encaminhada, ou a
Fora de escopo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.config import settings
from app.dependencies import selecionar_participantes
from app.services.feriados import carregar_feriados
from app.services.seguranca_do_paciente import emails
from app.services.seguranca_do_paciente.triagem import (
    ESTADOS_DA_FILA,
    CasoNaoEncontradoError,
    JaConfirmadaError,
    TriagemRecusadaError,
)
from app.utils.text_sanitizer import sanitizar_estrutura

NUCLEO = "nucleo"
OUVIDORIA = "ouvidoria"
CANAL_DE_CONDUTA = "canal_de_conduta"
FORA_DE_ESCOPO = "fora_de_escopo"
DESTINOS = (NUCLEO, OUVIDORIA, CANAL_DE_CONDUTA, FORA_DE_ESCOPO)

ENCAMINHADA = "encaminhada"
ESTADO_FORA_DE_ESCOPO = "fora_de_escopo"

TABELA = "nsp_encaminhamentos"
TAMANHO_DA_FRASE = 300

# O que a tela mostra quando o destino é o Canal de Conduta: só a orientação,
# sem link e sem nada do caso (ADR 0095, decisão 11).
ORIENTACAO_DO_CANAL_DE_CONDUTA = (
    "Nada deste caso foi enviado ao Canal de Conduta. Oriente quem notificou a "
    "relatar o fato diretamente ao Canal de Conduta do hospital."
)

MARCO_DA_OUVIDORIA = "encaminhamento_ouvidoria"
MODELO = "email_nsp_aviso.html"
# O texto puro do registro cabe em 10 mil caracteres (migration 173); o
# relato inteiro vai no HTML, e o texto puro corta o que passar.
_TETO_DO_TEXTO = 10000
_FUSO = ZoneInfo("America/Sao_Paulo")


class EncaminhamentoInvalidoError(TriagemRecusadaError):
    pass


def _frase(valor: str | None, recusa: str) -> str:
    texto = " ".join((valor or "").split())
    if not texto:
        raise EncaminhamentoInvalidoError(recusa)
    if len(texto) > TAMANHO_DA_FRASE:
        raise EncaminhamentoInvalidoError(f"Escreva em uma frase, até {TAMANHO_DA_FRASE} caracteres.")
    return texto


def _destinos(destinos: list[str]) -> list[str]:
    escolhidos = list(dict.fromkeys(destinos or []))
    if not escolhidos:
        raise EncaminhamentoInvalidoError("Escolha ao menos um destino.")
    if any(destino not in DESTINOS for destino in escolhidos):
        raise EncaminhamentoInvalidoError("Escolha o destino na lista.")
    if FORA_DE_ESCOPO in escolhidos and len(escolhidos) > 1:
        raise EncaminhamentoInvalidoError("Fora de escopo encerra o caso: não se soma a outro destino.")
    return escolhidos


def estado_depois_do_encaminhamento(destinos: list[str]) -> str | None:
    """None quando o Núcleo fica com o caso: ele continua na triagem."""
    if NUCLEO in destinos:
        return None
    return ESTADO_FORA_DE_ESCOPO if FORA_DE_ESCOPO in destinos else ENCAMINHADA


def _agora() -> datetime:
    return datetime.now(_FUSO)


def _ouvidores(supabase) -> list[dict[str, Any]]:
    """Quem tem o perfil de ouvidor e está ativo. A Diretoria Executiva da
    Ouvidoria não recebe: o e-mail leva o relato."""
    resposta = selecionar_participantes(
        supabase, "id, nome_completo", lambda q: q.eq("perfil_ouvidoria", "ouvidor").eq("ativo", True)
    )
    return resposta.data or []


def mensagem_a_ouvidoria(nome: str, protocolo: str, motivo: str, relato: str) -> tuple[str, str, dict]:
    """(assunto, texto, contexto do modelo) do e-mail ao ouvidor, com o
    protocolo, o motivo e o relato."""
    link = f"{settings.frontend_url}/ouvidoria"
    assunto = f"Caso do Núcleo encaminhado à Ouvidoria: protocolo {protocolo}"
    paragrafos = [
        f"O Núcleo de Segurança do Paciente encaminhou à Ouvidoria a notificação {protocolo}.",
        f"Motivo: {motivo}",
        f"Relato: {relato}",
        "Abra a manifestação na Ouvidoria, se for o caso. O protocolo do Núcleo continua o mesmo.",
    ]
    assunto, nome, paragrafos = sanitizar_estrutura([assunto, nome, paragrafos])
    cabeca = f"Olá, {nome}.\n\n"
    rodape = f"\n\nOuvidoria: {link}\n"
    texto = cabeca + "\n\n".join(paragrafos) + rodape
    if len(texto) > _TETO_DO_TEXTO:
        sobra = len(texto) - _TETO_DO_TEXTO + len(" [...]")
        cortado = [*paragrafos[:2], paragrafos[2][:-sobra] + " [...]", paragrafos[3]]
        texto = cabeca + "\n\n".join(cortado) + rodape
    return assunto, texto, {"nome": nome, "paragrafos": paragrafos, "link": link, "botao": "Abrir a Ouvidoria"}


def _registrar_o_email_a_ouvidoria(
    supabase, notificacao: dict, ouvidores: list[dict], motivo: str, agora: datetime
) -> None:
    """Um registro por ouvidor, na fila do registro de e-mail: não é urgente, e
    o job de 10 em 10 minutos entrega no expediente."""
    feriados = carregar_feriados(supabase)
    for ouvidor in ouvidores:
        assunto, texto, contexto = mensagem_a_ouvidoria(
            ouvidor.get("nome_completo") or "", notificacao["protocolo"], motivo, notificacao.get("relato") or ""
        )
        emails.registrar(
            supabase,
            caso_id=notificacao["id"],
            marco=MARCO_DA_OUVIDORIA,
            referencia=notificacao["protocolo"],
            destinatario_id=ouvidor["id"],
            assunto=assunto,
            texto=texto,
            modelo=MODELO,
            contexto=contexto,
            agora=agora,
            feriados=feriados,
        )


def _notificacao(supabase, notificacao_id: str) -> dict[str, Any] | None:
    linhas = (
        supabase.table("nsp_notificacoes")
        .select("id, protocolo, estado, relato")
        .eq("id", notificacao_id)
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


def encaminhar_da_triagem(
    supabase,
    notificacao_id: str,
    *,
    autor_id: str,
    destinos: list[str],
    motivo: str | None,
    orientacao: str | None = None,
) -> dict[str, Any]:
    """Grava o encaminhamento e leva o caso ao estado que os destinos pedem.
    Devolve o estado do caso, o encaminhamento gravado e, com o Canal de
    Conduta entre os destinos, a orientação para a tela."""
    escolhidos = _destinos(destinos)
    motivo = _frase(motivo, "Escreva o motivo do encaminhamento em uma frase.")
    if FORA_DE_ESCOPO in escolhidos:
        orientacao = _frase(orientacao, "Escreva, em uma frase, a orientação para quem notificou.")
    else:
        orientacao = None
    notificacao = _notificacao(supabase, notificacao_id)
    if notificacao is None:
        raise CasoNaoEncontradoError("Caso não encontrado.")
    if notificacao.get("estado") not in ESTADOS_DA_FILA:
        raise JaConfirmadaError("Este caso já saiu da triagem.")
    ouvidores = _ouvidores(supabase) if OUVIDORIA in escolhidos else []
    if OUVIDORIA in escolhidos and not ouvidores:
        raise EncaminhamentoInvalidoError("Não há ouvidor ativo no cadastro para receber o caso.")
    gravado = (
        supabase.table(TABELA)
        .insert(
            {
                "notificacao_id": notificacao_id,
                "destinos": escolhidos,
                "motivo": motivo,
                "orientacao": orientacao,
                "autor_id": autor_id,
            }
        )
        .execute()
        .data[0]
    )
    if ouvidores:
        _registrar_o_email_a_ouvidoria(supabase, notificacao, ouvidores, motivo, _agora())
    estado = estado_depois_do_encaminhamento(escolhidos)
    if estado is not None:
        supabase.table("nsp_notificacoes").update({"estado": estado, "editado_por": autor_id}).eq(
            "id", notificacao_id
        ).in_("estado", list(ESTADOS_DA_FILA)).execute()
    resposta: dict[str, Any] = {"estado": estado or notificacao["estado"], "encaminhamento": _apresentar(gravado)}
    if CANAL_DE_CONDUTA in escolhidos:
        resposta["orientacao_do_canal_de_conduta"] = ORIENTACAO_DO_CANAL_DE_CONDUTA
    return resposta


def _apresentar(linha: dict[str, Any]) -> dict[str, Any]:
    return {campo: linha.get(campo) for campo in ("destinos", "motivo", "orientacao", "autor_id", "criado_em")}


def encaminhamentos_do_caso(supabase, notificacao_id: str) -> list[dict[str, Any]]:
    """Os encaminhamentos do caso, do mais antigo para o mais novo."""
    linhas = supabase.table(TABELA).select("*").eq("notificacao_id", notificacao_id).order("criado_em").execute().data
    return [_apresentar(linha) for linha in linhas or []]


def orientacao_ao_notificante(supabase, notificacao_id: str) -> str | None:
    """A orientação do caso fora de escopo, a que quem notificou vê no
    acompanhamento. Só ela: o motivo é do Núcleo."""
    linhas = (
        supabase.table(TABELA)
        .select("orientacao, criado_em")
        .eq("notificacao_id", notificacao_id)
        .order("criado_em", desc=True)
        .execute()
        .data
    )
    return next((linha["orientacao"] for linha in linhas or [] if linha.get("orientacao")), None)
