"""Os avisos do Termo sem assinatura e do fim da vigência (issue #1770, PRD #1764).

Um job diário, sem IA, olha cada Participação aberta do Núcleo e vê qual marco
ela alcançou hoje:

- assinatura (do envio aberto do Termo, contado do dia em que foi gerado):
  documento gerado e 3 e 7 dias sem assinatura avisam o membro; 14 dias
  avisam o membro e a Presidência;
- vigência: 60 e 30 dias antes do fim avisam o membro e a Presidência;
- fim da carência sem renovação: avisa a Presidência e a Diretoria Executiva.

De cada família sai só o marco mais adiantado: o job que ficou fora do ar por
uns dias não manda o de 3 e o de 7 juntos.

Cada aviso é nominal (um e-mail por pessoa) e nasce como linha de
`nsp_avisos` antes de sair. A chave (Participação, marco, referência,
destinatário) do banco faz a segunda rodada bater na guarda em vez de mandar
de novo. A referência é o envio do Termo nos marcos de assinatura (o reenvio
recomeça a contagem) e o fim da vigência nos outros (a renovação recomeça os
avisos). A falha de um envio fica gravada na linha e não para os demais.

O e-mail diz a ação pedida no assunto, com data absoluta, e não traz nada do
conteúdo do Núcleo: só o nome do membro e as datas da vigência ou do Termo.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from postgrest.exceptions import APIError

from app.config import settings
from app.dependencies import selecionar_participantes
from app.services.email_constants import get_logo_data_uri
from app.services.email_service import _enviar_email, jinja_env
from app.services.ouvidoria_notificacoes import ler_diretoria_executiva
from app.services.paginacao import ler_tudo
from app.services.seguranca_do_paciente.agenda import presidencia_vigente
from app.services.seguranca_do_paciente.membros import DIAS_DE_CARENCIA, estado_do_membro
from app.services.seguranca_do_paciente.permissao import id_do_nucleo
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

TABELA = "nsp_avisos"
LOTE_DE_IDS = 100
_FUSO = ZoneInfo("America/Sao_Paulo")

MEMBRO = "membro"
PRESIDENCIA = "presidencia"
DIRETORIA_EXECUTIVA = "diretoria_executiva"

# Do mais adiantado para o primeiro: o primeiro que a contagem alcança é o do dia.
MARCOS_DA_ASSINATURA = (("assinatura_14", 14), ("assinatura_7", 7), ("assinatura_3", 3), ("documento_gerado", 0))
MARCOS_DA_VIGENCIA = (("vigencia_30", 30), ("vigencia_60", 60))
FIM_DA_CARENCIA = "fim_da_carencia"

DESTINATARIOS = {
    "documento_gerado": (MEMBRO,),
    "assinatura_3": (MEMBRO,),
    "assinatura_7": (MEMBRO,),
    "assinatura_14": (MEMBRO, PRESIDENCIA),
    "vigencia_60": (MEMBRO, PRESIDENCIA),
    "vigencia_30": (MEMBRO, PRESIDENCIA),
    FIM_DA_CARENCIA: (PRESIDENCIA, DIRETORIA_EXECUTIVA),
}

_SEM_EMAIL = "A pessoa não tem e-mail no cadastro."
_FALHA_DO_ENVIO = "O provedor de e-mail não aceitou o envio."


def _data(valor: Any) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def _dia_em_sao_paulo(carimbo: Any) -> date:
    texto = str(carimbo).replace("Z", "+00:00")
    momento = datetime.fromisoformat(texto)
    return momento.astimezone(_FUSO).date() if momento.tzinfo else momento.date()


def marcos_do_dia(participacao: dict, envio: dict | None, hoje: date) -> list[tuple[str, str, date]]:
    """Os marcos que a Participação alcançou hoje, um por família, como
    (marco, referência, data que o e-mail mostra). `envio` é o envio do Termo
    que espera a assinatura, se houver. Função pura.

    Os marcos de assinatura valem só enquanto o membro está Aguardando
    assinatura: assinado ou liberado à mão, eles param."""
    if participacao.get("encerrada_em"):
        return []
    marcos: list[tuple[str, str, date]] = []
    if envio and estado_do_membro(participacao, hoje) == "aguardando_assinatura":
        gerado = _dia_em_sao_paulo(envio["created_at"])
        dias = (hoje - gerado).days
        marco = next((nome for nome, limiar in MARCOS_DA_ASSINATURA if dias >= limiar), None)
        if marco:
            marcos.append((marco, envio["id"], gerado))
    fim = _data(participacao["vigencia_fim"])
    faltam = (fim - hoje).days
    marco = next((nome for nome, limiar in MARCOS_DA_VIGENCIA if 0 <= faltam <= limiar), None)
    if marco:
        marcos.append((marco, fim.isoformat(), fim))
    fim_da_carencia = fim + timedelta(days=DIAS_DE_CARENCIA)
    if hoje > fim_da_carencia:
        marcos.append((FIM_DA_CARENCIA, fim.isoformat(), fim_da_carencia))
    return marcos


# ---------------------------------------------------------------------------
# As mensagens
# ---------------------------------------------------------------------------


def _texto_do_aviso(marco: str, papel: str, membro: str, data: str) -> tuple[str, list[str]]:
    """(assunto, parágrafos) de cada marco, para o membro ou para quem cobra."""
    nucleo = "Núcleo de Segurança do Paciente"
    if marco == "documento_gerado":
        return (
            f"Assine o Termo de Adesão ao {nucleo}, gerado em {data}",
            [
                f"O seu Termo de Adesão ao {nucleo} foi gerado em {data} e enviado para a assinatura eletrônica.",
                "Procure na sua caixa de entrada o e-mail da assinatura eletrônica e assine para liberar o seu "
                "acesso ao módulo.",
            ],
        )
    if marco.startswith("assinatura_") and papel == MEMBRO:
        return (
            f"Assine o Termo de Adesão ao {nucleo}, pendente desde {data}",
            [
                f"O seu Termo de Adesão ao {nucleo}, gerado em {data}, ainda está sem assinatura.",
                "Sem a assinatura, o seu acesso ao módulo fica limitado ao painel, ao calendário e à agenda.",
            ],
        )
    if marco.startswith("assinatura_"):
        return (
            f"Cobre a assinatura do Termo de Adesão de {membro}, pendente desde {data}",
            [
                f"O Termo de Adesão de {membro} ao {nucleo}, gerado em {data}, ainda está sem assinatura.",
                "Na tela Membros, a seção do membro tem Reconsultar status da assinatura e Reenviar o Termo.",
            ],
        )
    if marco.startswith("vigencia_") and papel == MEMBRO:
        return (
            f"Renove a sua participação no {nucleo}: a vigência termina em {data}",
            [
                f"A sua participação no {nucleo} termina em {data}.",
                "Fale com a Presidência do Núcleo para renovar a vigência a tempo.",
            ],
        )
    if marco.startswith("vigencia_"):
        return (
            f"Renove a participação de {membro} no {nucleo}: a vigência termina em {data}",
            [
                f"A participação de {membro} no {nucleo} termina em {data}.",
                "Na tela Membros, a seção do membro tem Renovar a vigência.",
            ],
        )
    return (
        f"Recomponha o {nucleo}: a carência de {membro} terminou em {data} sem renovação",
        [
            f"A carência da participação de {membro} no {nucleo} terminou em {data}, e a vigência não foi renovada.",
            "O membro não conta mais para quórum. Na tela Membros, a Presidência renova ou encerra a participação.",
        ],
    )


def montar_email(marco: str, papel: str, destinatario: str, membro: str, data: date) -> tuple[str, str, str]:
    """(assunto, html, texto) do aviso. Tudo passa pelo sanitizador: os nomes
    vêm de quem digitou, e o e-mail não sai com travessão."""
    assunto, paragrafos = _texto_do_aviso(marco, papel, membro, data.strftime("%d/%m/%Y"))
    link = f"{settings.frontend_url}/seguranca-do-paciente/membros"
    assunto, destinatario, paragrafos = sanitizar_estrutura([assunto, destinatario, paragrafos])
    texto = f"Olá, {destinatario}.\n\n" + "\n\n".join(paragrafos) + f"\n\nSegurança do Paciente, Membros: {link}\n"
    html = jinja_env.get_template("email_nsp_aviso.html").render(
        nome=destinatario, paragrafos=paragrafos, link=link, logo_base64=get_logo_data_uri()
    )
    return assunto, html, texto


# ---------------------------------------------------------------------------
# O job
# ---------------------------------------------------------------------------


def _em_lotes(supabase, tabela: str, campos: str, coluna: str, ids: Iterable[str], rotulo: str, montar=None) -> list:
    ids = list(dict.fromkeys(ids))
    montar = montar or (lambda q: q)
    linhas: list[dict] = []
    for i in range(0, len(ids), LOTE_DE_IDS):
        lote = ids[i : i + LOTE_DE_IDS]
        linhas += ler_tudo(
            lambda lote=lote: montar(supabase.table(tabela).select(campos).in_(coluna, lote)).order("id"),
            rotulo=rotulo,
        )
    return linhas


def _pessoas(supabase, ids: Iterable[str]) -> dict[str, dict]:
    ids = sorted(set(ids))
    pessoas: dict[str, dict] = {}
    for i in range(0, len(ids), LOTE_DE_IDS):
        lote = ids[i : i + LOTE_DE_IDS]
        resposta = selecionar_participantes(
            supabase, "id, nome_completo, email", lambda q, lote=lote: q.in_("id", lote)
        )
        pessoas.update({p["id"]: p for p in (resposta.data or [])})
    return pessoas


def _gravar(supabase, linha: dict) -> dict | None:
    """A linha do aviso, antes do envio. None quando outra rodada já a gravou."""
    try:
        return supabase.table(TABELA).insert({**linha, "situacao": "pendente"}).execute().data[0]
    except APIError as erro:
        if getattr(erro, "code", None) != "23505":
            raise
        return None


def _enviar(supabase, aviso: dict, pessoa: dict, mensagem: tuple[str, str, str]) -> bool:
    erro = None
    if not (pessoa.get("email") or "").strip():
        erro = _SEM_EMAIL
    else:
        try:
            if not _enviar_email(pessoa["email"], *mensagem):
                erro = _FALHA_DO_ENVIO
        except Exception as falha:  # noqa: BLE001 (um aviso que falha não para os outros)
            erro = f"Falha no envio: {type(falha).__name__}"
    campos = (
        {"situacao": "enviado", "enviado_em": datetime.now(tz=_FUSO).isoformat()}
        if erro is None
        else {"situacao": "falhou", "erro": erro}
    )
    supabase.table(TABELA).update(campos).eq("id", aviso["id"]).execute()
    if erro:
        logger.warning("[Avisos NSP] Aviso %s (%s) não saiu: %s", aviso["id"], aviso["marco"], erro)
    return erro is None


def avisar(supabase, hoje: date) -> dict[str, int]:
    """O job diário. Devolve quantos avisos saíram e quantos falharam."""
    resultado = {"enviados": 0, "falhas": 0}
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return resultado
    participacoes = ler_tudo(
        lambda: (
            supabase.table("participacoes")
            .select(
                "id, participante_id, vigencia_inicio, vigencia_fim, encerrada_em, termo_gerado_em, "
                "termo_enviado_em, termo_assinado_em"
            )
            .eq("colegiado_id", nucleo_id)
            .is_("encerrada_em", "null")
            .order("id")
        ),
        rotulo="Participações do Núcleo",
    )
    # O envio que espera a assinatura (um aberto por Participação, pelo banco).
    envios = {
        e["participacao_id"]: e
        for e in _em_lotes(
            supabase,
            "nsp_termos_envios",
            "id, participacao_id, situacao, created_at",
            "participacao_id",
            (p["id"] for p in participacoes),
            "envios do Termo",
            lambda q: q.eq("situacao", "enviado"),
        )
    }
    devidos = [
        (p, marco, referencia, data)
        for p in participacoes
        for marco, referencia, data in marcos_do_dia(p, envios.get(p["id"]), hoje)
    ]
    if not devidos:
        return resultado

    ja = {
        (a["participacao_id"], a["marco"], a["referencia"], a["destinatario_id"])
        for a in _em_lotes(
            supabase,
            TABELA,
            "id, participacao_id, marco, referencia, destinatario_id",
            "participacao_id",
            (p["id"] for p, *_ in devidos),
            "avisos do Núcleo",
        )
    }
    presidencia = presidencia_vigente(supabase, hoje)
    diretoria = ler_diretoria_executiva(supabase) or []
    pessoas = _pessoas(
        supabase,
        [p["participante_id"] for p, *_ in devidos]
        + ([presidencia["id"]] if presidencia else [])
        + [d["id"] for d in diretoria],
    )

    def quem(papel: str, participacao: dict) -> list[str]:
        if papel == MEMBRO:
            return [participacao["participante_id"]]
        if papel == PRESIDENCIA:
            return [presidencia["id"]] if presidencia else []
        return [d["id"] for d in diretoria]

    for participacao, marco, referencia, data in devidos:
        membro = pessoas.get(participacao["participante_id"], {}).get("nome_completo") or "membro sem nome"
        vistos: set[str] = set()
        for papel in DESTINATARIOS[marco]:
            destinatarios = quem(papel, participacao)
            if not destinatarios:
                logger.warning("[Avisos NSP] Marco %s sem %s para avisar.", marco, papel)
            for pid in destinatarios:
                if pid in vistos or (participacao["id"], marco, referencia, pid) in ja:
                    continue
                vistos.add(pid)
                try:
                    aviso = _gravar(
                        supabase,
                        {
                            "participacao_id": participacao["id"],
                            "marco": marco,
                            "referencia": referencia,
                            "destinatario_id": pid,
                        },
                    )
                    if aviso is None:
                        continue
                    pessoa = pessoas.get(pid, {"id": pid})
                    papel_da_mensagem = MEMBRO if pid == participacao["participante_id"] else papel
                    mensagem = montar_email(marco, papel_da_mensagem, pessoa.get("nome_completo") or "", membro, data)
                    saiu = _enviar(supabase, aviso, pessoa, mensagem)
                except Exception as falha:  # noqa: BLE001 (um aviso que falha não para os outros)
                    logger.error("[Avisos NSP] Aviso %s para %s falhou: %s", marco, pid, type(falha).__name__)
                    saiu = False
                resultado["enviados" if saiu else "falhas"] += 1
    return resultado
