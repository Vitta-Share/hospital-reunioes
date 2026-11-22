"""A faixa "o que exige ação hoje" e o alerta de 72 horas (issue #2000, PRD #1979).

A faixa abre o início do módulo para quem abre os casos, com quatro grupos,
cada um com a contagem e o link para a tela onde ele se resolve:

- **casos A e B abertos:** a triagem confirmada nas faixas A ou B, e o caso
  ainda classificado. Cada caso leva à página dele;
- **triagens pendentes por idade:** a fila de triagem, em três idades. Leva à
  fila;
- **prazos legais a vencer:** a notificação externa ainda pendente, 72 horas
  ou 15º dia útil do mês seguinte, do vencimento mais perto ao mais longe. O
  que vence em menos de 24 horas vem em destaque. Cada um leva ao caso;
- **Termos pendentes:** a Participação aberta no Núcleo sem o Termo assinado.
  Leva a Membros.

Nenhum item leva nome de paciente ou de profissional: só protocolo, faixa,
sistema e data. Investigações e ações vencidas entram na Fase 3.

Cada grupo é lido por si: a leitura que falha marca só o grupo como ilegível,
e os outros aparecem.

O alerta de 72 horas é o job de hora em hora, sem IA: o caso A com a
notificação externa pendente e o prazo de 72 horas a menos de 24 horas do fim
registra o e-mail urgente à Presidência, ao suplente vigente e ao Acesso
pleno. Quem já tem o registro do caso não ganha outro, e a chave do registro
(caso, marco, protocolo, destinatário) segura a corrida entre duas rodadas:
cada pessoa recebe uma vez só.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from postgrest.exceptions import APIError

from app.config import settings
from app.services.paginacao import LeituraIncompletaError, ler_tudo
from app.services.seguranca_do_paciente import caso_grave, emails, triagem
from app.services.seguranca_do_paciente.membros import estado_do_membro
from app.services.seguranca_do_paciente.notificacoes import LOTE_DE_IDS
from app.services.seguranca_do_paciente.permissao import id_do_nucleo
from app.services.seguranca_do_paciente.prazos import (
    HORAS_CORRIDAS,
    NOTIFICACOES_EXTERNAS,
    PRAZOS_DO_CASO,
    SISTEMAS,
)
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

_FUSO = ZoneInfo("America/Sao_Paulo")

MARCO_DAS_72_HORAS = "prazo_de_72_horas"
MODELO = "email_nsp_aviso.html"
# A antecedência do destaque e do e-mail.
ANTECEDENCIA = timedelta(hours=24)
# Quantos itens cada grupo lista, no máximo. A contagem é a inteira.
TETO_DE_ITENS = 10

FAIXAS_DOS_CASOS_ABERTOS = ("A", "B")
CASO_ABERTO = "classificada"
NOTIFICACAO_EXTERNA = "notificacao_externa"
EXTERNA_PENDENTE = "pendente"

TELA_DO_CASO = "/seguranca-do-paciente/notificacoes/{id}"
TELA_DAS_NOTIFICACOES = "/seguranca-do-paciente/notificacoes"
TELA_DA_TRIAGEM = "/seguranca-do-paciente/notificacoes/triagem"
TELA_DE_MEMBROS = "/seguranca-do-paciente/membros"

# As idades da fila de triagem, da mais velha para a mais nova. A mais velha
# vem em destaque.
_IDADES = (("há mais de 3 dias", True), ("de 1 a 3 dias", False), ("há menos de 1 dia", False))

# Os estados da Participação com o Termo ainda por assinar.
_TERMOS = (
    ("cadastrado", "sem o Termo gerado"),
    ("documento_gerado", "com o Termo gerado e não enviado"),
    ("aguardando_assinatura", "esperando a assinatura"),
)

_FALHAS_DE_LEITURA = (APIError, httpx.HTTPError, LeituraIncompletaError)


def _agora() -> datetime:
    return datetime.now(_FUSO)


def _instante(bruto: Any) -> datetime:
    momento = datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def _data_e_hora(momento: datetime) -> str:
    local = momento.astimezone(_FUSO)
    return f"{local:%d/%m/%Y} às {local:%H:%M}"


def _em_lotes(consulta: Callable[[list[str]], Any], ids: Iterable[str]) -> list[dict[str, Any]]:
    """As linhas da consulta, em lotes de ids: `in_` sem teto estoura a URL."""
    lista = sorted(set(ids))
    linhas: list[dict[str, Any]] = []
    for inicio in range(0, len(lista), LOTE_DE_IDS):
        linhas += consulta(lista[inicio : inicio + LOTE_DE_IDS]).execute().data or []
    return linhas


def _protocolos(supabase, ids: Iterable[str], *, estado: str | None = None) -> dict[str, dict[str, Any]]:
    def consulta(lote: list[str]):
        q = supabase.table("nsp_notificacoes").select("id, protocolo, numero, estado").in_("id", lote)
        return q.eq("estado", estado) if estado else q

    return {linha["id"]: linha for linha in _em_lotes(consulta, ids)}


def _item(rotulo: str, link: str, urgente: bool = False) -> dict[str, Any]:
    return {"rotulo": rotulo, "link": link, "urgente": urgente}


# ═══════════════════════════════════════════════════════════════════════════
# Os quatro grupos
# ═══════════════════════════════════════════════════════════════════════════


def _casos_abertos(supabase, _momento: datetime) -> tuple[int, list[dict[str, Any]]]:
    decisoes = triagem._paginas(
        lambda: (
            supabase.table("nsp_triagens")
            .select("id, notificacao_id, faixa")
            .eq("autor_tipo", "pessoa")
            .in_("faixa", list(FAIXAS_DOS_CASOS_ABERTOS))
            .order("id")
        )
    )
    faixas = {d["notificacao_id"]: d["faixa"] for d in decisoes}
    abertos = _protocolos(supabase, faixas, estado=CASO_ABERTO)
    ordem = sorted(abertos.values(), key=lambda caso: (faixas[caso["id"]], caso.get("numero") or 0))
    itens = [
        _item(f"{caso['protocolo']}, faixa {faixas[caso['id']]}", TELA_DO_CASO.format(id=caso["id"]))
        for caso in ordem
    ]
    return len(itens), itens


def _triagens_pendentes(supabase, agora: datetime) -> tuple[int, list[dict[str, Any]]]:
    fila = triagem.fila(supabase)
    contagem = [0] * len(_IDADES)
    for caso in fila:
        idade = agora - _instante(caso["criado_em"])
        contagem[0 if idade > timedelta(days=3) else 1 if idade >= timedelta(days=1) else 2] += 1
    itens = [
        _item(f"{quantos} {rotulo}", TELA_DA_TRIAGEM, urgente)
        for quantos, (rotulo, urgente) in zip(contagem, _IDADES, strict=True)
        if quantos
    ]
    return len(fila), itens


def _prazos_legais(supabase, agora: datetime) -> tuple[int, list[dict[str, Any]]]:
    externas = triagem._paginas(
        lambda: (
            supabase.table(NOTIFICACOES_EXTERNAS)
            .select("id, notificacao_id, sistema, prazo_legal")
            .eq("estado", EXTERNA_PENDENTE)
            .order("prazo_legal")
        )
    )
    externas.sort(key=lambda linha: _instante(linha["prazo_legal"]))
    ids = [linha["notificacao_id"] for linha in externas]
    unidades = {
        linha["notificacao_id"]: linha["unidade"]
        for linha in _em_lotes(
            lambda lote: (
                supabase.table(PRAZOS_DO_CASO)
                .select("notificacao_id, unidade")
                .eq("marco", NOTIFICACAO_EXTERNA)
                .in_("notificacao_id", lote)
            ),
            ids,
        )
    }
    protocolos = _protocolos(supabase, ids[:TETO_DE_ITENS])
    itens = []
    for linha in externas[:TETO_DE_ITENS]:
        caso_id = linha["notificacao_id"]
        vence = _instante(linha["prazo_legal"])
        prazo = "em 72 horas" if unidades.get(caso_id) == HORAS_CORRIDAS else "até o 15º dia útil"
        verbo = "vence" if vence > agora else "venceu"
        protocolo = protocolos.get(caso_id, {}).get("protocolo") or "Caso sem protocolo"
        sistema = SISTEMAS.get(linha["sistema"], linha["sistema"])
        itens.append(
            _item(
                f"{protocolo}, {sistema} {prazo}: {verbo} em {_data_e_hora(vence)}",
                TELA_DO_CASO.format(id=caso_id),
                vence - agora < ANTECEDENCIA,
            )
        )
    return len(externas), itens


def _termos_pendentes(supabase, agora: datetime) -> tuple[int, list[dict[str, Any]]]:
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return 0, []
    participacoes = ler_tudo(
        lambda: (
            supabase.table("participacoes")
            .select(
                "id, vigencia_inicio, vigencia_fim, encerrada_em, termo_gerado_em, termo_enviado_em, termo_assinado_em"
            )
            .eq("colegiado_id", nucleo_id)
            .is_("encerrada_em", "null")
            .order("id")
        ),
        rotulo="Participações do Núcleo",
    )
    hoje = agora.astimezone(_FUSO).date()
    estados = [estado_do_membro(p, hoje) for p in participacoes]
    itens = [
        _item(f"{estados.count(estado)} {rotulo}", TELA_DE_MEMBROS)
        for estado, rotulo in _TERMOS
        if estados.count(estado)
    ]
    return sum(estados.count(estado) for estado, _ in _TERMOS), itens


_GRUPOS = (
    ("casos_abertos", "Casos A e B abertos", TELA_DAS_NOTIFICACOES, _casos_abertos),
    ("triagens_pendentes", "Triagens pendentes", TELA_DA_TRIAGEM, _triagens_pendentes),
    ("prazos_legais", "Prazos legais a vencer", TELA_DAS_NOTIFICACOES, _prazos_legais),
    ("termos_pendentes", "Termos pendentes", TELA_DE_MEMBROS, _termos_pendentes),
)


def faixa_de_hoje(supabase) -> dict[str, Any]:
    """Os quatro grupos da faixa, na ordem da tela."""
    agora = _agora()
    grupos = []
    for chave, titulo, link, ler in _GRUPOS:
        grupo: dict[str, Any] = {"chave": chave, "titulo": titulo, "link": link, "ilegivel": False}
        try:
            grupo["total"], grupo["itens"] = ler(supabase, agora)
        except _FALHAS_DE_LEITURA as erro:
            logger.error("[Ação de hoje NSP] Grupo %s ilegível: %s", chave, type(erro).__name__)
            grupo.update(total=None, itens=[], ilegivel=True)
        grupos.append(grupo)
    return {"grupos": grupos}


# ═══════════════════════════════════════════════════════════════════════════
# O alerta de 72 horas
# ═══════════════════════════════════════════════════════════════════════════


def mensagem_das_72_horas(nome: str, protocolo: str, caso_id: str, sistema: str, vence: datetime):
    """(assunto, texto, contexto do modelo). Sem o relato: protocolo, sistema,
    data e link. Tudo passa pelo sanitizador."""
    quando = _data_e_hora(vence)
    link = f"{settings.frontend_url}{TELA_DO_CASO.format(id=caso_id)}"
    assunto = f"[72 HORAS] Notificação {protocolo}: notificar a vigilância até {quando}"
    paragrafos = [
        f"O prazo legal de 72 horas para notificar à vigilância sanitária o caso {protocolo} "
        f"termina em {quando}. Faltam menos de 24 horas.",
        f"Sistema de destino: {sistema}.",
        "O relato não vai por e-mail. Abra o caso no módulo Segurança do Paciente.",
    ]
    assunto, nome, paragrafos = sanitizar_estrutura([assunto, nome, paragrafos])
    texto = f"Olá, {nome}.\n\n" + "\n\n".join(paragrafos) + f"\n\nAbrir o caso: {link}\n"
    return assunto, texto, {"nome": nome, "paragrafos": paragrafos, "link": link, "botao": "Abrir o caso"}


def _prazos_de_72_horas_perto_do_fim(supabase, agora: datetime) -> list[dict[str, Any]]:
    """A notificação externa pendente com o prazo de 72 horas entre agora e as
    próximas 24 horas."""
    perto = (
        supabase.table(PRAZOS_DO_CASO)
        .select("notificacao_id, vence_em")
        .eq("marco", NOTIFICACAO_EXTERNA)
        .eq("unidade", HORAS_CORRIDAS)
        .gte("vence_em", agora.astimezone(UTC).isoformat())
        .lte("vence_em", (agora + ANTECEDENCIA).astimezone(UTC).isoformat())
        .execute()
        .data
    ) or []
    vencimentos = {linha["notificacao_id"]: linha["vence_em"] for linha in perto}
    pendentes = _em_lotes(
        lambda lote: (
            supabase.table(NOTIFICACOES_EXTERNAS)
            .select("notificacao_id, sistema")
            .eq("estado", EXTERNA_PENDENTE)
            .in_("notificacao_id", lote)
        ),
        vencimentos,
    )
    protocolos = _protocolos(supabase, (linha["notificacao_id"] for linha in pendentes))
    return [
        {
            "caso_id": linha["notificacao_id"],
            "protocolo": protocolos[linha["notificacao_id"]]["protocolo"],
            "sistema": SISTEMAS.get(linha["sistema"], linha["sistema"]),
            "vence": _instante(vencimentos[linha["notificacao_id"]]),
        }
        for linha in pendentes
        if linha["notificacao_id"] in protocolos
    ]


def alertar_os_prazos_de_72_horas(supabase, agora: datetime) -> int:
    """O job: registra e entrega o e-mail urgente de cada caso perto do fim das
    72 horas, uma vez por pessoa. Devolve quantos registros nasceram agora."""
    casos = _prazos_de_72_horas_perto_do_fim(supabase, agora)
    if not casos:
        return 0
    destinatarios, ilegiveis = caso_grave.quem_recebe_o_alerta(
        supabase, agora.astimezone(_FUSO).date(), caso_grave.GRUPOS_DO_PRAZO_LEGAL
    )
    if ilegiveis:
        logger.error("[72 horas NSP] Sem %s nesta rodada; a próxima tenta de novo.", ", ".join(ilegiveis))
    ja_avisados = {
        (linha["caso_id"], linha["destinatario_id"])
        for linha in _em_lotes(
            lambda lote: (
                supabase.table(emails.TABELA)
                .select("id, caso_id, destinatario_id")
                .eq("marco", MARCO_DAS_72_HORAS)
                .in_("referencia", lote)
            ),
            (caso["protocolo"] for caso in casos),
        )
    }
    registros = []
    for caso in casos:
        for pessoa in destinatarios:
            if (caso["caso_id"], pessoa["id"]) in ja_avisados:
                continue
            try:
                assunto, texto, contexto = mensagem_das_72_horas(
                    pessoa.get("nome_completo") or "", caso["protocolo"], caso["caso_id"], caso["sistema"], caso["vence"]
                )
                registro = emails.registrar(
                    supabase,
                    caso_id=caso["caso_id"],
                    marco=MARCO_DAS_72_HORAS,
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
                    "[72 horas NSP] Alerta de %s para %s falhou: %s",
                    caso["protocolo"],
                    pessoa["id"],
                    type(falha).__name__,
                )
                continue
            if registro:
                registros.append(registro)
    for registro in registros:
        try:
            emails.despachar_se_puder(supabase, registro, agora)
        except Exception as falha:  # noqa: BLE001 (o job de 10 em 10 minutos leva o resto)
            logger.error("[72 horas NSP] Registro %s não saiu agora: %s", registro.get("id"), type(falha).__name__)
    return len(registros)
