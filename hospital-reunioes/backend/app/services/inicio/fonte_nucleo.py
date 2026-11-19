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

from datetime import date, datetime
from typing import Any

from app.dependencies import recursos_nsp_da_pessoa
from app.services.inicio.regras import FUSO
from app.services.seguranca_do_paciente import capacitacoes, termo
from app.services.seguranca_do_paciente.assinatura_dos_documentos import ROTULO_DO_TIPO
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo, id_do_nucleo, participacoes_vigentes

ROTULO = "o que o Núcleo espera de você"

AREA = "Segurança do Paciente"


def _data(valor: Any) -> date | None:
    return date.fromisoformat(str(valor)[:10]) if valor else None


def _dia_em_brasilia(valor: Any) -> date | None:
    """O dia de um `TIMESTAMPTZ`, que chega em UTC, contado em Brasília como o
    resto do Início: o envio às 22h não chega no dia seguinte."""
    if not valor:
        return None
    momento = datetime.fromisoformat(str(valor))
    return momento.astimezone(FUSO).date() if momento.tzinfo else momento.date()


def _depois(instante: Any, de: Any) -> bool:
    return bool(instante) and datetime.fromisoformat(str(instante)) > datetime.fromisoformat(str(de))


def _termo_pendente(supabase, me: dict) -> list[dict]:
    """A mesma regra do "Termo pendente" da ficha do membro
    (`termo.novo_termo_pendente`, issue #1769): quem nunca assinou e também
    quem assinou antes da renovação, da mudança de papel ou da revisão
    material do Regimento. Quem já assinou alguma vez tem o acesso liberado
    e não vê a faixa das telas bloqueadas: o link dele foi pelo e-mail."""
    nucleo_id = id_do_nucleo(supabase)
    if not nucleo_id:
        return []
    hoje = hoje_em_sao_paulo()
    linhas = participacoes_vigentes(supabase, nucleo_id, hoje).eq("participante_id", me["id"]).execute()
    linhas = linhas.data or []
    if not linhas:
        return []
    revisao = termo.revisao_material_em(supabase)
    pendentes = [linha for linha in linhas if termo.novo_termo_pendente(linha, revisao, hoje)]
    if not pendentes:
        return []
    participacao = pendentes[0]
    assinado = participacao.get("termo_assinado_em")
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
    enviado = envio.get("enviado_em") or envio.get("created_at")
    if assinado and not _depois(enviado, assinado):
        # O envio é o do Termo já assinado: o novo ainda não saiu (a geração
        # falhou, ou a revisão material não gerou), e a espera conta do pedido.
        pedidos = (participacao.get("termo_gerado_em"), revisao)
        chegou_em = max((_dia_em_brasilia(p) for p in pedidos if _depois(p, assinado)), default=None)
    else:
        chegou_em = _dia_em_brasilia(enviado)
    if not any(linha.get("termo_assinado_em") for linha in linhas):
        # A tela de Documentos, fechada para quem não assinou, mostra a
        # faixa com o botão que abre o documento pendente (issue #1768).
        origem = "Núcleo de Segurança do Paciente. Sem o Termo, as telas do Núcleo ficam fechadas."
        acao, destino = "Abrir o Termo de Adesão", "/seguranca-do-paciente/documentos"
    else:
        origem = "Termo de Adesão novo esperando a sua assinatura. O link foi para o seu e-mail."
        acao, destino = "Abrir o Núcleo", "/seguranca-do-paciente"
    return [
        {
            "tipo": "termo_de_adesao",
            "id": participacao["id"],
            "titulo": "Assinar o Termo de Adesão ao Núcleo",
            "origem": origem,
            "chegou_em": chegou_em,
            "sem_prazo_no_modulo": True,
            "area": AREA,
            "acao": acao,
            "destino": destino,
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
                "chegou_em": _dia_em_brasilia(envio.get("enviado_em")),
                "sem_prazo_no_modulo": True,
                "area": AREA,
                "acao": "Abrir os Documentos",
                "destino": "/seguranca-do-paciente/documentos",
            }
        )
    return saida


def _presencas_a_confirmar(supabase, me: dict) -> list[dict]:
    """A capacitação em cuja lista a pessoa está e ainda não confirmou. Só a
    partir do dia dela, como a rota de presença: antes, não há o que confirmar."""
    minhas = (
        supabase.table(capacitacoes.TABELA_PARTICIPANTES)
        .select("capacitacao_id")
        .eq("participante_id", me["id"])
        .is_("presenca_confirmada_em", "null")
        .execute()
        .data
    ) or []
    if not minhas:
        return []
    linhas = (
        supabase.table(capacitacoes.TABELA)
        .select("id, titulo, data")
        .in_("id", sorted({linha["capacitacao_id"] for linha in minhas}))
        .lte("data", hoje_em_sao_paulo().isoformat())
        .execute()
        .data
    ) or []
    saida: list[dict] = []
    for linha in linhas:
        quando = _data(linha.get("data"))
        saida.append(
            {
                "tipo": "capacitacao",
                "id": linha["id"],
                "titulo": f"Confirmar a presença na capacitação {(linha.get('titulo') or '').strip()}".strip(),
                "origem": f"Capacitação do Núcleo de {quando.strftime('%d/%m/%Y')}."
                if quando
                else "Capacitação do Núcleo.",
                "chegou_em": quando,
                "sem_prazo_no_modulo": True,
                "area": AREA,
                "acao": "Abrir as Capacitações",
                "destino": "/seguranca-do-paciente/capacitacoes",
                # Um clique sem Anotação (ADR 0104, decisão 3): a presença se
                # confirma no próprio Início, pela mesma rota da tela.
                "acao_de_um_clique": {
                    "rotulo": "Confirmar presença",
                    "endpoint": f"/api/nsp/capacitacoes/{linha['id']}/presenca",
                },
            }
        )
    return saida


def itens(supabase, me: dict) -> list[dict]:
    """Os itens da fonte, no formato comum do Início. Cada um só entra para
    quem alcança o recurso da tela que o mostra: o super admin, que só alcança
    a configuração, não recebe nenhum."""
    recursos = recursos_nsp_da_pessoa(supabase, me)
    saida: list[dict] = []
    if "ver_modulo" in recursos:
        saida += _termo_pendente(supabase, me)
    if "documentos" in recursos:
        saida += _documentos_a_assinar(supabase, me)
    if "capacitacoes" in recursos:
        saida += _presencas_a_confirmar(supabase, me)
    return saida
