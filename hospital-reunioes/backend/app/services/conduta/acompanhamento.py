"""A página de acompanhamento do Canal de Conduta e as Mensagens do caso
(issue #1845; especificação, P7 e 6.1, passo 4).

Quem relatou entra com o protocolo e o código, sem login. A página mostra a
situação em linguagem simples, as mensagens do Comitê (as perguntas e a
resposta final) e recebe o complemento. Nada interno sai daqui: o que a página
recebe é montado em `pagina_publica`, campo a campo, sem nome de membro, voto,
medida nem etapa.

Toda recusa é a mesma recusa, no mesmo tempo: protocolo que não existe,
código errado e envio malformado devolvem `None`, e cada um gasta uma
derivação lenta do código, como o acerto (`ouvidoria_acompanhamento`).

Do lado do Comitê, a coordenação pergunta a quem relatou (o agente sugere as
perguntas na triagem). Pedido sem resposta há 15 dias libera arquivar por
falta de elementos; o caso arquivado reabre quando o complemento chega
depois do arquivamento. As mensagens ficam cifradas, e o banco não deixa
alterar nem apagar nenhuma (migration 234).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from app.services import ouvidoria_acompanhamento
from app.services.conduta import cifra, retorno, trilha
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import FUSO, agora_utc

TABELA = "conduta_mensagens"
TAMANHO_DA_PERGUNTA = 2000
TAMANHO_DO_COMPLEMENTO = 5000
DIAS_PARA_ARQUIVAR = 15

PERGUNTA = "pergunta"
COMPLEMENTO = "complemento"
ARQUIVADO = "arquivado"

# As seis situações da especificação (P7), na língua de quem relatou.
RECEBIDO = "Recebido"
EM_ANALISE = "Em análise"
EM_APURACAO = "Em apuração"
AGUARDANDO = "Aguardando sua resposta"
CONCLUIDO = "Concluído"
ENCAMINHADO = "Encaminhado"

_ETAPAS_DA_APURACAO = ("apuracao", "voto", "ata", "medida", "retorno")

FRASE_DO_ARQUIVAMENTO = (
    "O caso foi arquivado por falta de elementos. Se você tiver a informação pedida, escreva no complemento: "
    "o Comitê pode reabrir o caso."
)

# O que a consulta lê do caso. Tupla fechada: o que não está aqui não tem como
# chegar à página.
_CAMPOS_DO_CASO = (
    "id, protocolo, codigo_hash, rota, etapa, triagem_em, encerrado_em, desfecho, orientacao_cifrada, "
    "retorno_aprovado_id"
)


class MensagemRecusadaError(Exception):
    """A ação não pode acontecer agora. `status` vai para a resposta, e a
    mensagem diz o motivo numa linha."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ── A entrada de quem relatou ───────────────────────────────────────────────


def conferir(supabase, protocolo: Any, codigo: Any) -> dict | None:
    """O caso, se o protocolo existe e o código confere; `None` para toda
    recusa. Cada recusa gasta uma derivação lenta, como o acerto."""
    codigo_texto = codigo if isinstance(codigo, str) else ""
    valido = (
        isinstance(protocolo, str)
        and isinstance(codigo, str)
        and 0 < len(protocolo.strip()) <= 20
        and 0 < len(codigo.strip()) <= 40
    )
    linhas = []
    if valido:
        linhas = (
            supabase.table("conduta_casos")
            .select(_CAMPOS_DO_CASO)
            .eq("protocolo", protocolo.strip().upper())
            .limit(1)
            .execute()
            .data
        ) or []
    if not linhas:
        ouvidoria_acompanhamento._gastar_o_tempo_de_uma_conferencia(codigo_texto)
        return None
    if not ouvidoria_acompanhamento.codigo_confere(codigo_texto, linhas[0].get("codigo_hash")):
        return None
    return linhas[0]


# ── As mensagens e a situação ───────────────────────────────────────────────


def _mensagens(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(TABELA).select("*").eq("caso_id", caso_id).order("enviada_em").execute().data or []
    return sorted(linhas, key=lambda m: _momento(m["enviada_em"]))


def _momento(valor: str | datetime) -> datetime:
    return datetime.fromisoformat(valor) if isinstance(valor, str) else valor


def _dia(valor: str | datetime) -> date:
    return _momento(valor).astimezone(FUSO).date()


def perguntas_sem_resposta(mensagens: list[dict]) -> list[dict]:
    """As perguntas do Comitê enviadas depois do último complemento."""
    abertas: list[dict] = []
    for mensagem in mensagens:
        if mensagem["tipo"] == COMPLEMENTO:
            abertas = []
        elif mensagem["tipo"] == PERGUNTA:
            abertas.append(mensagem)
    return abertas


def situacao_publica(caso: dict, mensagens: list[dict]) -> str:
    if caso.get("encerrado_em"):
        return ENCAMINHADO if caso.get("desfecho") == "encaminhado" else CONCLUIDO
    if perguntas_sem_resposta(mensagens):
        return AGUARDANDO
    if caso.get("rota") == "especial" or caso.get("etapa") in _ETAPAS_DA_APURACAO:
        return EM_APURACAO
    if caso.get("triagem_em"):
        return EM_ANALISE
    return RECEBIDO


def _resposta_final(supabase, caso: dict) -> str | None:
    """O que o Comitê disse a quem relatou no encerramento: a orientação do
    Encaminhamento, a resposta do retorno aprovado ou a frase do arquivamento."""
    if not caso.get("encerrado_em"):
        return None
    desfecho = caso.get("desfecho")
    if desfecho == "encaminhado" and caso.get("orientacao_cifrada"):
        return cifra.decifrar_texto(caso["orientacao_cifrada"])
    if desfecho == "concluido":
        return retorno.resposta_ao_denunciante(supabase, caso)
    if desfecho == ARQUIVADO:
        return FRASE_DO_ARQUIVAMENTO
    return None


def pagina_publica(supabase, caso: dict) -> dict:
    """Tudo o que a página de acompanhamento recebe."""
    mensagens = _mensagens(supabase, caso["id"])
    itens = [
        {
            "de": "comite" if m["tipo"] == PERGUNTA else "voce",
            "tipo": m["tipo"],
            "texto": cifra.decifrar_texto(m["texto_cifrado"]),
            "em": _momento(m["enviada_em"]).isoformat(),
        }
        for m in mensagens
    ]
    final = _resposta_final(supabase, caso)
    if final:
        itens.append(
            {"de": "comite", "tipo": "resposta_final", "texto": final, "em": _momento(caso["encerrado_em"]).isoformat()}
        )
        itens.sort(key=lambda item: _momento(item["em"]))
    return {"protocolo": caso["protocolo"], "situacao": situacao_publica(caso, mensagens), "mensagens": itens}


def complementar(supabase, caso: dict, texto: Any) -> None:
    """Grava o complemento de quem relatou, cifrado, e o aviso no caso
    (`denunciante_informou_em`, que a verificação de retaliação lê)."""
    texto = texto.strip() if isinstance(texto, str) else ""
    if not texto:
        raise MensagemRecusadaError(422, "Escreva o complemento.")
    if len(texto) > TAMANHO_DO_COMPLEMENTO:
        raise MensagemRecusadaError(422, f"O complemento cabe em {TAMANHO_DO_COMPLEMENTO} caracteres.")
    agora = agora_utc().isoformat()
    trilha.registrar(supabase, caso["id"], None, "complemento", "quem relatou enviou um complemento")
    supabase.table(TABELA).insert(
        {
            "caso_id": caso["id"],
            "tipo": COMPLEMENTO,
            "autor_id": None,
            "texto_cifrado": cifra.cifrar_texto(texto),
            "enviada_em": agora,
        }
    ).execute()
    supabase.table("conduta_casos").update({"denunciante_informou_em": agora}).eq("id", caso["id"]).execute()


# ── O lado do Comitê ────────────────────────────────────────────────────────


def _coordena(aberto: CasoAberto) -> bool:
    return aberto.pessoa.papel == "coordenacao"


def _arquivavel_a_partir_de(mensagens: list[dict]) -> date | None:
    abertas = perguntas_sem_resposta(mensagens)
    return _dia(abertas[0]["enviada_em"]) + timedelta(days=DIAS_PARA_ARQUIVAR) if abertas else None


def _complemento_depois_do_arquivamento(caso: dict, mensagens: list[dict]) -> bool:
    if caso.get("desfecho") != ARQUIVADO or not caso.get("encerrado_em"):
        return False
    arquivado = _momento(caso["encerrado_em"])
    return any(m["tipo"] == COMPLEMENTO and _momento(m["enviada_em"]) > arquivado for m in mensagens)


def _perguntas_sugeridas(supabase, caso_id: str) -> list[str]:
    linhas = (
        supabase.table("conduta_sugestoes")
        .select("situacao, sugestao_cifrada")
        .eq("caso_id", caso_id)
        .limit(1)
        .execute()
        .data
    ) or []
    if not linhas or linhas[0].get("situacao") != "sugerida" or not linhas[0].get("sugestao_cifrada"):
        return []
    sugestao = json.loads(cifra.decifrar_texto(linhas[0]["sugestao_cifrada"]))
    valor = (sugestao.get("perguntas_ao_denunciante") or {}).get("valor") or []
    return [str(p) for p in valor if str(p).strip()]


def para_a_tela(supabase, aberto: CasoAberto, hoje: date) -> dict[str, Any]:
    """A área Mensagens da tela do caso."""
    caso = aberto.caso
    mensagens = _mensagens(supabase, caso["id"])
    encerrado = bool(caso.get("encerrado_em"))
    coordena = _coordena(aberto)
    a_partir_de = None if encerrado else _arquivavel_a_partir_de(mensagens)
    return {
        "mensagens": {
            "itens": [
                {
                    "id": m["id"],
                    "tipo": m["tipo"],
                    "de": "comite" if m["tipo"] == PERGUNTA else "relator",
                    "texto": cifra.decifrar_texto(m["texto_cifrado"]),
                    "enviada_em": _momento(m["enviada_em"]).isoformat(),
                }
                for m in mensagens
            ],
            "aguardando_resposta": a_partir_de is not None,
            "pode_perguntar": coordena and not encerrado,
            "perguntas_sugeridas": _perguntas_sugeridas(supabase, caso["id"]) if coordena and not encerrado else [],
            "arquivar_a_partir_de": a_partir_de.isoformat() if a_partir_de else None,
            "pode_arquivar": coordena and a_partir_de is not None and a_partir_de <= hoje,
            "arquivado": caso.get("desfecho") == ARQUIVADO,
            "pode_reabrir": coordena and _complemento_depois_do_arquivamento(caso, mensagens),
        }
    }


def perguntar(supabase, aberto: CasoAberto, *, texto: str) -> dict:
    """A coordenação envia uma pergunta a quem relatou."""
    if not _coordena(aberto):
        raise MensagemRecusadaError(403, "Só a coordenação envia perguntas a quem relatou.")
    caso = aberto.caso
    if caso.get("encerrado_em"):
        raise MensagemRecusadaError(409, "O caso está encerrado.")
    texto = (texto or "").strip()
    if not texto:
        raise MensagemRecusadaError(422, "Escreva a pergunta.")
    if len(texto) > TAMANHO_DA_PERGUNTA:
        raise MensagemRecusadaError(422, f"A pergunta cabe em {TAMANHO_DA_PERGUNTA} caracteres.")
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "pergunta", "enviou uma pergunta a quem relatou")
    return (
        supabase.table(TABELA)
        .insert(
            {
                "caso_id": caso["id"],
                "tipo": PERGUNTA,
                "autor_id": aberto.autor_id,
                "texto_cifrado": cifra.cifrar_texto(texto),
                "enviada_em": agora_utc().isoformat(),
            }
        )
        .execute()
        .data[0]
    )


def arquivar(supabase, aberto: CasoAberto, *, hoje: date) -> dict:
    """Arquiva por falta de elementos: só com um pedido de complemento sem
    resposta há 15 dias."""
    if not _coordena(aberto):
        raise MensagemRecusadaError(403, "Só a coordenação arquiva o caso.")
    caso = aberto.caso
    if caso.get("encerrado_em"):
        raise MensagemRecusadaError(409, "O caso já está encerrado.")
    a_partir_de = _arquivavel_a_partir_de(_mensagens(supabase, caso["id"]))
    if a_partir_de is None:
        raise MensagemRecusadaError(409, "Só se arquiva por falta de elementos com um pedido de complemento sem resposta.")
    if a_partir_de > hoje:
        raise MensagemRecusadaError(409, f"O arquivamento fica disponível em {a_partir_de.strftime('%d/%m/%Y')}.")
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "arquivamento", "arquivou o caso por falta de elementos")
    linhas = (
        supabase.table("conduta_casos")
        .update(
            {
                "encerrado_em": agora_utc().isoformat(),
                "desfecho": ARQUIVADO,
                "etapa": "encerrado",
                "etapa_ao_arquivar": caso.get("etapa") or "triagem",
            }
        )
        .eq("id", caso["id"])
        .is_("encerrado_em", "null")
        .execute()
        .data
    ) or []
    if not linhas:
        raise MensagemRecusadaError(409, "O caso mudou enquanto você agia. Abra de novo.")
    return linhas[0]


def reabrir(supabase, aberto: CasoAberto) -> dict:
    """Reabre o caso arquivado por falta de elementos, na etapa em que ele
    estava, quando o complemento chegou depois do arquivamento."""
    if not _coordena(aberto):
        raise MensagemRecusadaError(403, "Só a coordenação reabre o caso.")
    caso = aberto.caso
    if caso.get("desfecho") != ARQUIVADO:
        raise MensagemRecusadaError(409, "Só reabre o caso arquivado por falta de elementos.")
    if not _complemento_depois_do_arquivamento(caso, _mensagens(supabase, caso["id"])):
        raise MensagemRecusadaError(409, "O caso reabre quando quem relatou mandar a informação depois do arquivamento.")
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "reabertura", "reabriu o caso com o complemento recebido")
    linhas = (
        supabase.table("conduta_casos")
        .update(
            {
                "encerrado_em": None,
                "desfecho": None,
                "etapa": caso.get("etapa_ao_arquivar") or "triagem",
                "etapa_ao_arquivar": None,
            }
        )
        .eq("id", caso["id"])
        .eq("desfecho", ARQUIVADO)
        .execute()
        .data
    ) or []
    if not linhas:
        raise MensagemRecusadaError(409, "O caso mudou enquanto você agia. Abra de novo.")
    return linhas[0]
