"""A fonte do Núcleo no Início, Fase 1 (issue #1939, ADR 0104, decisão 5).

O que o Núcleo de Segurança do Paciente espera da pessoa: o Termo de Adesão
pendente, o documento do Núcleo esperando a assinatura dela e a capacitação em
que falta confirmar a presença. Nenhum dos três tem prazo no módulo, e todos
entram no grupo Sem prazo.

O acesso segue a ADR 0095: a fonte só devolve o que a tela dona mostraria à
pessoa (`recursos_nsp_da_pessoa`). O super admin sem acesso ao Núcleo só
alcança a configuração técnica e não recebe item nenhum daqui.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.dependencies import recursos_nsp_da_pessoa
from app.services.seguranca_do_paciente.assinatura_dos_documentos import ROTULO_DO_TIPO
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo, id_do_nucleo, participacoes_vigentes

ROTULO = "o que o Núcleo espera de você"

AREA = "Segurança do Paciente"


def _data(valor: Any) -> date | None:
    return date.fromisoformat(str(valor)[:10]) if valor else None


def _termo_pendente(supabase, me: dict) -> list[dict]:
    """A mesma regra da faixa das telas bloqueadas (`/nsp/meu-termo`): há
    Participação vigente e nenhuma delas tem o Termo assinado."""
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return []
    linhas = participacoes_vigentes(supabase, nucleo_id, hoje_em_sao_paulo()).eq("participante_id", me["id"]).execute()
    linhas = linhas.data or []
    if not linhas or any(linha.get("termo_assinado_em") for linha in linhas):
        return []
    participacao = linhas[0]
    envios = (
        supabase.table("nsp_termos_envios")
        .select("situacao, enviado_em, created_at")
        .eq("participacao_id", participacao["id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    ) or []
    envio = envios[0] if envios else {}
    return [
        {
            "tipo": "termo_de_adesao",
            "id": participacao["id"],
            "titulo": "Assinar o Termo de Adesão ao Núcleo",
            "origem": "Núcleo de Segurança do Paciente. Sem o Termo, as telas do Núcleo ficam fechadas.",
            "chegou_em": _data(envio.get("enviado_em") or envio.get("created_at")),
            "sem_prazo_no_modulo": True,
            "area": AREA,
            # A tela de Documentos, fechada para quem não assinou, mostra a
            # faixa com o botão que abre o documento pendente (issue #1768).
            "acao": "Abrir o Termo de Adesão",
            "destino": "/seguranca-do-paciente/documentos",
        }
    ]


def _documentos_a_assinar(supabase, me: dict) -> list[dict]:
    """A versão enviada para assinatura em que a pessoa é signatária e ainda
    não assinou. Envio cancelado (pelo reenvio ou por versão mais nova) ou
    ainda não enviado não tem o que assinar."""
    minhas = (
        supabase.table("nsp_documentos_signatarios")
        .select("envio_id")
        .eq("participante_id", me["id"])
        .is_("assinado_em", "null")
        .execute()
        .data
    ) or []
    if not minhas:
        return []
    envios = (
        supabase.table("nsp_documentos_envios")
        .select("id, documento_id, situacao, enviado_em")
        .in_("id", sorted({linha["envio_id"] for linha in minhas}))
        .eq("situacao", "enviado")
        .execute()
        .data
    ) or []
    if not envios:
        return []
    documentos = {
        linha["id"]: linha
        for linha in (
            supabase.table("nsp_documentos")
            .select("id, tipo, titulo, versao")
            .in_("id", sorted({envio["documento_id"] for envio in envios}))
            .execute()
            .data
        )
        or []
    }
    saida: list[dict] = []
    for envio in envios:
        documento = documentos.get(envio["documento_id"], {})
        nome = ROTULO_DO_TIPO.get(documento.get("tipo"), documento.get("titulo") or "documento do Núcleo")
        versao = documento.get("versao")
        saida.append(
            {
                "tipo": "documento_do_nucleo",
                "id": envio["id"],
                "titulo": f"Assinar o {nome}, versão {versao}" if versao else f"Assinar o {nome}",
                "origem": "Documento do Núcleo esperando a sua assinatura. O link foi para o seu e-mail.",
                "chegou_em": _data(envio.get("enviado_em")),
                "sem_prazo_no_modulo": True,
                "area": AREA,
                "acao": "Abrir os Documentos",
                "destino": "/seguranca-do-paciente/documentos",
            }
        )
    return saida


def itens(supabase, me: dict) -> list[dict]:
    """Os itens da fonte, no formato comum do Início."""
    recursos = recursos_nsp_da_pessoa(supabase, me)
    if "ver_modulo" not in recursos:
        return []
    saida = _termo_pendente(supabase, me)
    if "documentos" in recursos:
        saida += _documentos_a_assinar(supabase, me)
    return saida
