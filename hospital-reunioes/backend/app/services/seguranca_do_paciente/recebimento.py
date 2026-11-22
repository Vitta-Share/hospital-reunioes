"""O encaminhamento à Segurança do Trabalho e à queixa técnica, com o botão
"Recebido" (issue #1996, PRD #1979, ADR 0107 decisão 8).

A Presidência escolhe o destino e o setor da taxonomia que recebe (a queixa
técnica vai à Farmácia ou à Engenharia Clínica). O e-mail vai ao titular
vigente do cadastro de responsáveis da Ouvidoria, o mesmo de todo acionamento;
sem titular, vai ao gestor e a Presidência é avisada. Sem titular e sem gestor,
o encaminhamento é recusado em vez de mandar o caso para o vazio.

O link é de uso único e próprio do Núcleo: o token aleatório só existe dentro
do e-mail que saiu, e o banco guarda o hash (`nsp_recebimentos.token_hash`). O
token nasce na hora do envio, e não no registro, para o texto guardado na fila
não carregar o link em claro. Cada envio emite um token novo por cima do
anterior: vale o link do e-mail mais recente, até a validade.

Abrir o link não confirma nada (leitor de e-mail que abre link sozinho
gastaria o uso único): é o botão "Recebido" da tela que carimba
`recebido_em`, uma vez só. Depois dele, e depois da validade, o link recusa.

Sem o clique em `ESPERA_DO_REENVIO`, o e-mail sai de novo uma única vez, sem
degraus.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from app.config import settings
from app.services.feriados import carregar_feriados
from app.services.ouvidoria_prazos import DIAS_UTEIS, Prazo, calcular_vencimento, esta_vencido
from app.services.ouvidoria_responsaveis import TITULAR, escolher_destinatario
from app.services.seguranca_do_paciente import emails
from app.services.seguranca_do_paciente.permissao import id_do_nucleo, participacoes_vigentes
from app.services.seguranca_do_paciente.triagem import TriagemRecusadaError
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

SEGURANCA_DO_TRABALHO = "seguranca_do_trabalho"
QUEIXA_TECNICA = "queixa_tecnica"
DESTINOS = (SEGURANCA_DO_TRABALHO, QUEIXA_TECNICA)
ROTULOS = {SEGURANCA_DO_TRABALHO: "Segurança do Trabalho", QUEIXA_TECNICA: "Queixa técnica"}

TABELA = "nsp_recebimentos"
MARCO_DO_SETOR = emails.MARCO_DO_SETOR
MARCO_SEM_TITULAR = "encaminhamento_sem_titular"
MODELO = "email_nsp_aviso.html"
SUFIXO_DO_REENVIO = ":reenvio"

# Quanto o link vale depois de cada envio, e quanto o setor tem para clicar
# antes do reenvio único.
VALIDADE_DO_LINK = timedelta(days=30)
ESPERA_DO_REENVIO = Prazo(2, DIAS_UTEIS)

_CAMPOS = (
    "id, encaminhamento_id, notificacao_id, destino, setor, destinatario_nome, destinatario_email, papel, "
    "enviado_em, reenviado_em, recebido_em, expira_em"
)


class SetorSemResponsavelError(TriagemRecusadaError):
    pass


class LinkInvalidoError(Exception):
    """Token que não existe: link adulterado, de outro sistema ou substituído
    por um envio mais novo."""


class JaRecebidoError(Exception):
    """O setor já clicou em Recebido: o link não abre de novo."""


class LinkVencidoError(Exception):
    """Passou da validade do link."""


@dataclass(frozen=True)
class Envio:
    destino: str
    setor: str
    nome: str
    email: str
    papel: str


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _nome_do_setor(supabase, setor_id: str | None) -> str | None:
    if not setor_id:
        return None
    linhas = supabase.table("setores").select("id, nome").eq("id", setor_id).eq("ativo", True).limit(1).execute().data
    return linhas[0]["nome"] if linhas else None


def _responsaveis(supabase, setor: str) -> list[dict]:
    """O cadastro do setor, na mesma ordem do acionamento da Ouvidoria:
    vigência mais recente primeiro, `id` como desempate."""
    linhas = (
        supabase.table("ouvidoria_setor_responsaveis")
        .select("id, setor, papel, nome, email, vigencia_inicio, vigencia_fim")
        .eq("setor", setor)
        .execute()
        .data
    ) or []
    linhas = sorted(linhas, key=lambda r: str(r.get("id") or ""))
    return sorted(linhas, key=lambda r: str(r.get("vigencia_inicio") or ""), reverse=True)


def quem_recebe(supabase, destinos: list[str], setores: dict[str, str] | None, hoje: date) -> list[Envio]:
    """Para quem vai cada destino com Recebido. Recusa, sem gravar nada, o
    destino sem setor escolhido e o setor sem titular nem gestor vigente."""
    envios = []
    for destino in (d for d in destinos if d in DESTINOS):
        setor = _nome_do_setor(supabase, (setores or {}).get(destino))
        if setor is None:
            raise SetorSemResponsavelError(f"Escolha o setor que recebe ({ROTULOS[destino]}).")
        quem = escolher_destinatario(_responsaveis(supabase, setor), hoje)
        if quem is None:
            raise SetorSemResponsavelError(
                f"O setor {setor} não tem titular nem gestor vigente no cadastro de responsáveis."
            )
        envios.append(Envio(destino=destino, setor=setor, nome=quem.nome, email=quem.email, papel=quem.papel))
    return envios


def mensagem_ao_setor(envio: Envio, protocolo: str, motivo: str) -> tuple[str, str, dict]:
    """(assunto, texto, contexto) do e-mail ao setor, ainda sem o link: ele
    entra na hora do envio."""
    assunto = f"Caso do Núcleo encaminhado a {envio.setor}: protocolo {protocolo}"
    paragrafos = [
        f"O Núcleo de Segurança do Paciente encaminhou a {envio.setor} a notificação {protocolo}.",
        f"Motivo: {motivo}",
        'Abra o link para ver o resumo do caso e confirme no botão "Recebido". '
        f"O link vale uma vez e vence em {VALIDADE_DO_LINK.days} dias.",
    ]
    assunto, nome, paragrafos = sanitizar_estrutura([assunto, envio.nome, paragrafos])
    texto = f"Olá, {nome}.\n\n" + "\n\n".join(paragrafos)
    return assunto, texto, {"nome": nome, "paragrafos": paragrafos, "botao": "Abrir e confirmar o recebimento"}


def _presidencia(supabase, hoje: date) -> list[str]:
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return []
    linhas = participacoes_vigentes(supabase, nucleo_id, hoje).eq("papel", "presidencia").execute().data or []
    return [linha["participante_id"] for linha in linhas]


def _avisar_a_presidencia(supabase, notificacao: dict, recebimento: dict, envio: Envio, agora, feriados) -> None:
    """O setor sem titular vigente: o caso foi ao gestor, e a Presidência fica
    sabendo do buraco no cadastro."""
    link = f"{settings.frontend_url}/seguranca-do-paciente/notificacoes"
    assunto = f"Setor sem titular: o caso {notificacao['protocolo']} foi ao gestor de {envio.setor}"
    paragrafos = [
        f"O setor {envio.setor} não tem titular vigente no cadastro de responsáveis.",
        f"O encaminhamento da notificação {notificacao['protocolo']} foi ao gestor, {envio.nome}.",
        "Peça à Ouvidoria para cadastrar o titular do setor.",
    ]
    assunto, paragrafos = sanitizar_estrutura([assunto, paragrafos])
    for pessoa_id in _presidencia(supabase, agora.date()):
        emails.registrar(
            supabase,
            caso_id=notificacao["id"],
            marco=MARCO_SEM_TITULAR,
            referencia=recebimento["id"],
            destinatario_id=pessoa_id,
            assunto=assunto,
            texto="\n\n".join(paragrafos) + f"\n\nCasos do Núcleo: {link}\n",
            modelo=MODELO,
            contexto={"nome": "Presidência", "paragrafos": paragrafos, "link": link, "botao": "Abrir os casos"},
            agora=agora,
            feriados=feriados,
        )


def registrar_os_envios(
    supabase, notificacao: dict, encaminhamento_id: str, envios: list[Envio], motivo: str, agora: datetime
) -> None:
    """Uma linha de recebimento por destino e o e-mail na fila do Núcleo."""
    if not envios:
        return
    feriados = carregar_feriados(supabase)
    for envio in envios:
        recebimento = (
            supabase.table(TABELA)
            .insert(
                {
                    "encaminhamento_id": encaminhamento_id,
                    "notificacao_id": notificacao["id"],
                    "destino": envio.destino,
                    "setor": envio.setor,
                    "destinatario_nome": envio.nome,
                    "destinatario_email": envio.email,
                    "papel": envio.papel,
                    "enviado_em": agora.isoformat(),
                }
            )
            .execute()
            .data[0]
        )
        assunto, texto, contexto = mensagem_ao_setor(envio, notificacao["protocolo"], motivo)
        emails.registrar(
            supabase,
            caso_id=notificacao["id"],
            marco=MARCO_DO_SETOR,
            referencia=recebimento["id"],
            destinatario_id=None,
            assunto=assunto,
            texto=texto,
            modelo=MODELO,
            contexto=contexto,
            agora=agora,
            feriados=feriados,
        )
        if envio.papel != TITULAR:
            _avisar_a_presidencia(supabase, notificacao, recebimento, envio, agora, feriados)


def _linha(supabase, recebimento_id: str) -> dict | None:
    linhas = supabase.table(TABELA).select(_CAMPOS).eq("id", recebimento_id).limit(1).execute().data
    return linhas[0] if linhas else None


def com_o_link(supabase, registro: dict, agora: datetime) -> tuple[str | None, dict]:
    """O endereço e o registro com o link novo, na hora do envio. O token nasce
    aqui, e só o hash fica no banco. None no endereço quando o setor já
    confirmou: o e-mail não sai."""
    recebimento_id = str(registro["referencia"]).removesuffix(SUFIXO_DO_REENVIO)
    linha = _linha(supabase, recebimento_id)
    if linha is None or linha.get("recebido_em"):
        return None, registro
    token = secrets.token_urlsafe(32)
    supabase.table(TABELA).update({"token_hash": _hash(token), "expira_em": (agora + VALIDADE_DO_LINK).isoformat()}).eq(
        "id", recebimento_id
    ).is_("recebido_em", "null").execute()
    link = f"{settings.frontend_url}/notificar/recebido/{token}"
    pronto = {
        **registro,
        "texto": f"{registro['texto']}\n\nAbra o caso e confirme o recebimento: {link}\n",
        "contexto": {**(registro.get("contexto") or {}), "link": link},
    }
    return linha.get("destinatario_email") or "", pronto


def carregar_pelo_token(supabase, token: str, agora: datetime) -> dict:
    """O recebimento do link, ou a recusa: inválido, já recebido ou vencido."""
    linhas = supabase.table(TABELA).select(_CAMPOS).eq("token_hash", _hash(token)).limit(1).execute().data
    if not linhas:
        raise LinkInvalidoError()
    linha = linhas[0]
    if linha.get("recebido_em"):
        raise JaRecebidoError()
    expira_em = linha.get("expira_em")
    if not expira_em or datetime.fromisoformat(str(expira_em)) < agora:
        raise LinkVencidoError()
    return linha


def resumo(supabase, linha: dict) -> dict[str, Any]:
    """O que a tela do link mostra: o protocolo, onde e quando, o motivo. Sem o
    relato e sem quem notificou: o link abre sem senha."""
    caso = (
        supabase.table("nsp_notificacoes")
        .select("id, protocolo, setor_id, data_ocorrencia, turno")
        .eq("id", linha["notificacao_id"])
        .limit(1)
        .execute()
        .data
    ) or [{}]
    encaminhamento = (
        supabase.table("nsp_encaminhamentos")
        .select("id, motivo")
        .eq("id", linha["encaminhamento_id"])
        .limit(1)
        .execute()
        .data
    ) or [{}]
    caso = caso[0]
    setores = supabase.table("setores").select("id, nome").eq("id", caso.get("setor_id")).limit(1).execute().data
    return {
        "protocolo": caso.get("protocolo"),
        "destino": ROTULOS.get(linha.get("destino"), linha.get("destino")),
        "setor_que_recebe": linha.get("setor"),
        "destinatario_nome": linha.get("destinatario_nome"),
        "setor_do_incidente": setores[0]["nome"] if setores else None,
        "data_ocorrencia": caso.get("data_ocorrencia"),
        "turno": caso.get("turno"),
        "motivo": encaminhamento[0].get("motivo"),
        "expira_em": linha.get("expira_em"),
    }


def confirmar(supabase, linha: dict, agora: datetime) -> str | None:
    """O clique em Recebido: carimba uma vez só. None quando outro clique
    chegou antes."""
    carimbo = agora.isoformat()
    resposta = (
        supabase.table(TABELA)
        .update({"recebido_em": carimbo})
        .eq("id", linha["id"])
        .is_("recebido_em", "null")
        .execute()
    )
    return carimbo if resposta.data else None


def recebimentos_do_caso(supabase, notificacao_id: str) -> list[dict[str, Any]]:
    """Os envios com Recebido do caso, para a tela: a quem foi e quando o setor
    confirmou. Sem token nem hash."""
    linhas = (
        supabase.table(TABELA).select(_CAMPOS).eq("notificacao_id", notificacao_id).order("enviado_em").execute().data
    ) or []
    campos = ("encaminhamento_id", "destino", "setor", "destinatario_nome", "papel", "enviado_em", "reenviado_em")
    return [{**{c: linha.get(c) for c in campos}, "recebido_em": linha.get("recebido_em")} for linha in linhas]


def reenviar_os_esquecidos(supabase, agora: datetime, feriados: frozenset[date] | None = None) -> int:
    """O reenvio único: o setor que não clicou em `ESPERA_DO_REENVIO` recebe o
    mesmo e-mail de novo, com link novo. O carimbo `reenviado_em` entra antes,
    por update condicional, e só quem o grava registra: a segunda passada não
    reenvia. Sem degraus depois disso."""
    pendentes = (
        supabase.table(TABELA).select(_CAMPOS).is_("recebido_em", "null").is_("reenviado_em", "null").execute().data
    ) or []
    if not pendentes:
        return 0
    if feriados is None:
        feriados = carregar_feriados(supabase)
    reenviados = 0
    for linha in pendentes:
        limite = calcular_vencimento(datetime.fromisoformat(str(linha["enviado_em"])), ESPERA_DO_REENVIO, feriados)
        if not esta_vencido(limite, agora):
            continue
        carimbado = (
            supabase.table(TABELA)
            .update({"reenviado_em": agora.isoformat()})
            .eq("id", linha["id"])
            .is_("reenviado_em", "null")
            .is_("recebido_em", "null")
            .execute()
        )
        if not carimbado.data:
            continue
        originais = (
            supabase.table(emails.TABELA)
            .select("id, assunto, texto, contexto")
            .eq("marco", MARCO_DO_SETOR)
            .eq("referencia", linha["id"])
            .limit(1)
            .execute()
            .data
        )
        if not originais:
            logger.error("[Recebido NSP] O e-mail original do recebimento %s sumiu; sem reenvio.", linha["id"])
            continue
        original = originais[0]
        emails.registrar(
            supabase,
            caso_id=linha["notificacao_id"],
            marco=MARCO_DO_SETOR,
            referencia=f"{linha['id']}{SUFIXO_DO_REENVIO}",
            destinatario_id=None,
            assunto=f"Lembrete: {original['assunto']}"[:300],
            texto=original["texto"],
            modelo=MODELO,
            contexto=original.get("contexto") or {},
            agora=agora,
            feriados=feriados,
        )
        reenviados += 1
    return reenviados
