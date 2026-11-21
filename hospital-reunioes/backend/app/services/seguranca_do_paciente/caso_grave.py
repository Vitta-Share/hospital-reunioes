"""O alerta imediato de caso grave e a confirmação de recebimento (issue #1989, PRD #1979).

Na chegada de uma notificação, ainda dentro do envio e antes de qualquer
triagem (do agente ou de gente), saem do registro de e-mail do Núcleo
(`emails`):

- **o alerta de caso grave**, quando quem notificou marcou "grave ou houve
  morte": um e-mail nominal à Presidência, ao suplente vigente, a quem tem
  Acesso pleno e à Diretoria Executiva. É urgente: sai na hora, de madrugada e
  no fim de semana. Não depende de IA nem do agente, que pode estar desligado;
- **a confirmação de recebimento**, para quem se identificou com e-mail, com o
  protocolo: cumpre o prazo de 24 horas do Regimento, e por isso também é
  urgente. O anônimo e quem deixou só telefone não geram e-mail.

Nenhum dos dois leva o relato: só o protocolo, o setor e o link. O destinatário
da confirmação não é um cadastro: o registro fica sem `destinatario_id`, e o
endereço sai da própria notificação na hora do envio.

O registro acontece no envio; a entrega, logo depois da resposta, numa tarefa
de fundo. O que a tarefa não entregar fica na fila do job de 10 em 10 minutos.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from postgrest.exceptions import APIError

from app.config import settings
from app.dependencies import selecionar_participantes
from app.services.ouvidoria_contato import email_utilizavel
from app.services.ouvidoria_notificacoes import avisar_admins_tecnicos, ler_diretoria_executiva
from app.services.seguranca_do_paciente import emails
from app.services.seguranca_do_paciente.permissao import (
    PERFIL_ACESSO_PLENO,
    id_do_nucleo,
    participacoes_vigentes,
)
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

_FUSO = ZoneInfo("America/Sao_Paulo")
MODELO = "email_nsp_aviso.html"
MARCO_DO_ALERTA = "caso_grave"
MARCO_DA_CONFIRMACAO = "confirmacao_de_recebimento"
# Quantos casos graves o início do módulo destaca, no máximo.
TETO_DO_DESTAQUE = 20

_CAMPOS_DO_CASO = "id, protocolo, setor_id, grave_ou_morte, anonimo, notificante_nome, notificante_contato"


def _agora() -> datetime:
    return datetime.now(_FUSO)


def _caso(supabase, notificacao_id: str) -> dict | None:
    linhas = supabase.table("nsp_notificacoes").select(_CAMPOS_DO_CASO).eq("id", notificacao_id).limit(1).execute().data
    return linhas[0] if linhas else None


def _nome_do_setor(supabase, setor_id: str | None) -> str:
    """O setor ilegível sai como "não informado": o alerta não espera por ele."""
    if not setor_id:
        return "não informado"
    try:
        linhas = supabase.table("setores").select("id, nome").eq("id", setor_id).limit(1).execute().data
    except (APIError, httpx.HTTPError) as erro:
        logger.error("[Caso grave NSP] Setor ilegível; o alerta segue sem ele: %s", type(erro).__name__)
        return "não informado"
    return (linhas[0].get("nome") if linhas else None) or "não informado"


def _pessoas(supabase, ids: Iterable[str]) -> list[dict]:
    """Nome e e-mail de cada um. Ilegível, segue só o id: o envio lê o e-mail
    do cadastro na hora de entregar."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    try:
        resposta = selecionar_participantes(supabase, "id, nome_completo, email", lambda q: q.in_("id", ids))
    except (APIError, httpx.HTTPError) as erro:
        logger.error(
            "[Caso grave NSP] Nomes de quem recebe ilegíveis; o alerta segue sem eles: %s", type(erro).__name__
        )
        return [{"id": pid} for pid in ids]
    por_id = {p["id"]: p for p in (resposta.data or [])}
    return [por_id.get(pid, {"id": pid}) for pid in ids]


def _presidencia_e_suplente(supabase, hoje: date) -> list[str]:
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return []
    vigentes = (
        participacoes_vigentes(supabase, nucleo_id, hoje).in_("papel", ["presidencia", "suplente"]).execute().data
    ) or []
    return [linha["participante_id"] for linha in vigentes]


def _acesso_pleno(supabase, _hoje: date) -> list[str]:
    resposta = selecionar_participantes(
        supabase, "id", lambda q: q.eq("perfil_nsp", PERFIL_ACESSO_PLENO).eq("ativo", True)
    )
    return [p["id"] for p in (resposta.data or [])]


def _diretoria_executiva(supabase, _hoje: date) -> list[str] | None:
    """None quando a leitura falhou (`ler_diretoria_executiva` já a engole)."""
    diretoria = ler_diretoria_executiva(supabase)
    return None if diretoria is None else [d["id"] for d in diretoria]


_GRUPOS_DO_ALERTA = (
    ("a Presidência e o suplente", _presidencia_e_suplente),
    ("o Acesso pleno", _acesso_pleno),
    ("a Diretoria Executiva", _diretoria_executiva),
)


def quem_recebe_o_alerta(supabase, hoje: date) -> tuple[list[dict], list[str]]:
    """A Presidência e o suplente vigentes, o Acesso pleno e a Diretoria
    Executiva, cada pessoa uma vez só, e os grupos que não deu para ler.

    Cada grupo é lido por si: um timeout em um não tira o alerta dos outros."""
    ids: list[str] = []
    ilegiveis: list[str] = []
    for grupo, ler in _GRUPOS_DO_ALERTA:
        try:
            lidos = ler(supabase, hoje)
        except (APIError, httpx.HTTPError) as erro:
            logger.error("[Caso grave NSP] %s ilegível: %s", grupo, type(erro).__name__)
            lidos = None
        if lidos is None:
            logger.error("[Caso grave NSP] Sem %s; o alerta segue para os demais.", grupo)
            ilegiveis.append(grupo)
            continue
        ids += lidos
    return _pessoas(supabase, ids), ilegiveis


def _avisar_o_admin_dos_grupos_ilegiveis(supabase, protocolo: str, ilegiveis: list[str]) -> None:
    """Quem ficou de fora do alerta só fica sabendo por aqui. Sem o relato."""
    try:
        avisar_admins_tecnicos(
            supabase,
            "Núcleo de Segurança do Paciente: alerta de caso grave incompleto",
            (
                f"O alerta do caso grave {protocolo} saiu sem chegar a: {', '.join(ilegiveis)}.\n"
                "A leitura de quem recebe falhou no banco. Avise essas pessoas e confira o banco.\n"
            ),
        )
    except Exception as falha:  # noqa: BLE001 (o aviso ao admin não segura o alerta já gravado)
        logger.error("[Caso grave NSP] Aviso ao admin técnico de %s falhou: %s", protocolo, type(falha).__name__)


def _quando(agora: datetime) -> tuple[str, str]:
    local = agora.astimezone(_FUSO)
    return local.strftime("%d/%m/%Y"), local.strftime("%H:%M")


def mensagem_do_alerta(nome: str, protocolo: str, setor: str, agora: datetime) -> tuple[str, str, dict]:
    """(assunto, texto, contexto do modelo) do alerta. Sem o relato: só o
    protocolo, o setor e o link. Tudo passa pelo sanitizador."""
    data, hora = _quando(agora)
    link = f"{settings.frontend_url}/seguranca-do-paciente/notificacoes"
    assunto = f"Caso grave ou com morte: abra a notificação {protocolo}, recebida em {data} às {hora}"
    paragrafos = [
        f"Chegou ao Núcleo de Segurança do Paciente, em {data} às {hora}, uma notificação de incidente "
        "marcada por quem notificou como grave ou com morte.",
        f"Protocolo: {protocolo}. Setor: {setor}.",
        "O relato não vai por e-mail. Abra o caso em Notificações, no módulo Segurança do Paciente.",
    ]
    assunto, nome, paragrafos = sanitizar_estrutura([assunto, nome, paragrafos])
    texto = f"Olá, {nome}.\n\n" + "\n\n".join(paragrafos) + f"\n\nSegurança do Paciente, Notificações: {link}\n"
    return assunto, texto, {"nome": nome, "paragrafos": paragrafos, "link": link, "botao": "Abrir Notificações"}


def _alertar_quem_decide(supabase, caso: dict, setor: str, agora: datetime) -> list[dict]:
    destinatarios, ilegiveis = quem_recebe_o_alerta(supabase, agora.astimezone(_FUSO).date())
    if ilegiveis:
        _avisar_o_admin_dos_grupos_ilegiveis(supabase, caso["protocolo"], ilegiveis)
    if not destinatarios:
        logger.error("[Caso grave NSP] Caso %s sem ninguém para alertar.", caso["protocolo"])
    registros = []
    for pessoa in destinatarios:
        try:
            assunto, texto, contexto = mensagem_do_alerta(
                pessoa.get("nome_completo") or "", caso["protocolo"], setor, agora
            )
            registro = emails.registrar(
                supabase,
                caso_id=caso["id"],
                marco=MARCO_DO_ALERTA,
                referencia=caso["protocolo"],
                destinatario_id=pessoa["id"],
                assunto=assunto,
                texto=texto,
                modelo=MODELO,
                contexto=contexto,
                agora=agora,
                urgente=True,
            )
        except Exception as falha:  # noqa: BLE001 (um alerta que falha não segura os outros)
            logger.error(
                "[Caso grave NSP] Alerta de %s para %s falhou: %s",
                caso["protocolo"],
                pessoa["id"],
                type(falha).__name__,
            )
            continue
        if registro:
            registros.append(registro)
    return registros


def mensagem_da_confirmacao(nome: str, protocolo: str, agora: datetime) -> tuple[str, str, dict]:
    """(assunto, texto, contexto do modelo) da confirmação de recebimento, com
    o protocolo e sem o relato."""
    data, hora = _quando(agora)
    link = f"{settings.frontend_url}/notificar/acompanhar"
    assunto = f"Recebemos a sua notificação de incidente: protocolo {protocolo}"
    paragrafos = [
        f"A sua notificação de incidente chegou ao Núcleo de Segurança do Paciente em {data} às {hora}, "
        f"com o protocolo {protocolo}.",
        "Obrigado por notificar. Notificar não gera punição: serve para tornar o cuidado mais seguro.",
        "Para acompanhar, abra a página de acompanhamento e informe o protocolo e o e-mail que você deixou.",
    ]
    assunto, nome, paragrafos = sanitizar_estrutura([assunto, nome, paragrafos])
    texto = f"Olá, {nome}.\n\n" + "\n\n".join(paragrafos) + f"\n\nAcompanhar a notificação: {link}\n"
    return assunto, texto, {"nome": nome, "paragrafos": paragrafos, "link": link, "botao": "Acompanhar a notificação"}


def _confirmar_a_quem_notificou(supabase, caso: dict, agora: datetime) -> list[dict]:
    """O endereço não vai para o registro: o envio o lê da notificação."""
    if caso.get("anonimo") or not email_utilizavel(caso.get("notificante_contato")):
        return []
    assunto, texto, contexto = mensagem_da_confirmacao(caso.get("notificante_nome") or "", caso["protocolo"], agora)
    registro = emails.registrar(
        supabase,
        caso_id=caso["id"],
        marco=MARCO_DA_CONFIRMACAO,
        referencia=caso["protocolo"],
        destinatario_id=None,
        assunto=assunto,
        texto=texto,
        modelo=MODELO,
        contexto=contexto,
        agora=agora,
        urgente=True,
    )
    return [registro] if registro else []


def avisar_a_chegada(supabase, notificacao_id: str) -> tuple[list[dict], datetime]:
    """Registra, no envio, os e-mails que a chegada pede, e devolve os
    registros para `entregar_os_avisos_da_chegada` e o instante do registro."""
    agora = _agora()
    caso = _caso(supabase, notificacao_id)
    if not caso:
        return [], agora
    registros: list[dict[str, Any]] = []
    if caso.get("grave_ou_morte"):
        try:
            registros += _alertar_quem_decide(supabase, caso, _nome_do_setor(supabase, caso.get("setor_id")), agora)
        except Exception as falha:  # noqa: BLE001 (a confirmação a quem notificou não espera o alerta)
            logger.error("[Caso grave NSP] Alerta de %s falhou: %s", caso["protocolo"], type(falha).__name__)
    try:
        registros += _confirmar_a_quem_notificou(supabase, caso, agora)
    except Exception as falha:  # noqa: BLE001 (o alerta já registrado segue para a entrega)
        logger.error("[Caso grave NSP] Confirmação de %s falhou: %s", caso["protocolo"], type(falha).__name__)
    return registros, agora


def casos_graves_em_espera(supabase) -> list[dict]:
    """O destaque do início do módulo: os casos graves ou com morte que ainda
    esperam a triagem, do mais novo ao mais velho. Sem o relato.

    A falha de leitura devolve a lista vazia: o início do módulo é a porta de
    entrada (o gate da área pergunta a ele), e o destaque não pode fechá-la."""
    try:
        linhas = (
            supabase.table("nsp_notificacoes")
            .select("id, protocolo, setor_id, criado_em")
            .eq("grave_ou_morte", True)
            .eq("estado", "recebida")
            .order("criado_em", desc=True)
            .limit(TETO_DO_DESTAQUE)
            .execute()
            .data
        ) or []
        setor_ids = sorted({linha["setor_id"] for linha in linhas if linha.get("setor_id")})
        setores = (
            {
                s["id"]: s["nome"]
                for s in supabase.table("setores").select("id, nome").in_("id", setor_ids).execute().data
            }
            if setor_ids
            else {}
        )
    except (APIError, httpx.HTTPError) as erro:
        logger.error("[Caso grave NSP] Destaque do início ilegível: %s", type(erro).__name__)
        return []
    return [
        {"protocolo": linha["protocolo"], "setor": setores.get(linha.get("setor_id")), "criado_em": linha["criado_em"]}
        for linha in linhas
    ]


def entregar_os_avisos_da_chegada(supabase, registros: list[dict], agora: datetime) -> None:
    """A tarefa de fundo do envio: entrega cada registro. O que falhar fica na
    fila do registro, com retentativa."""
    for registro in registros:
        try:
            emails.despachar_se_puder(supabase, registro, agora)
        except Exception as falha:  # noqa: BLE001 (o job de 10 em 10 minutos leva o resto)
            logger.error("[Caso grave NSP] Registro %s não saiu agora: %s", registro.get("id"), type(falha).__name__)
