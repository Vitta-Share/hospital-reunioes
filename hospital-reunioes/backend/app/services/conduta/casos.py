"""O caso do Canal de Conduta (ADR 0097, decisões 1 e 8).

O relato entra cifrado; rota, etapa, categoria e datas ficam em claro, para a
lista e o prazo. O protocolo é sorteado, sem ordem e sem contagem: número em
sequência contaria os casos para quem relata e deixaria um buraco na fila
comum a cada caso da Rota Especial. A numeração da Ouvidoria não é tocada.

O código de acompanhamento é o mesmo da Ouvidoria (curto, legível, hash com
sal e derivação lenta), devolvido uma vez só a quem relatou.
"""

from __future__ import annotations

import secrets
from typing import Any

from postgrest.exceptions import APIError

from app.services.conduta import agente_de_triagem, avisos, cifra, rota_especial, trilha
from app.services.ouvidoria_acompanhamento import ALFABETO, gerar_codigo, hash_do_codigo

_VIOLACAO_DE_UNICIDADE = "23505"
_TENTATIVAS_DO_PROTOCOLO = 3

# De onde o caso veio (migration 202): a página pública ou a sinalização do
# ouvidor.
ORIGEM_OUVIDORIA = "ouvidoria"


def novo_protocolo() -> str:
    simbolos = "".join(secrets.choice(ALFABETO) for _ in range(8))
    return f"CC-{simbolos[:4]}-{simbolos[4:]}"


def registrar_caso(
    supabase,
    *,
    relato: str,
    categoria: str | None,
    rota: str = "comum",
    manifestacao_id: str | None = None,
    tarefas=None,
    direcao_envolvida: str | None = None,
) -> dict[str, Any]:
    """Grava o caso e a linha de recebimento na trilha. Devolve o id, o
    protocolo e o código de acompanhamento, que não fica guardado.

    Com `manifestacao_id`, o caso é o que a Ouvidoria sinalizou (issue #1849,
    ADR 0097 decisão 14): origem `ouvidoria`, ligado à manifestação. Ninguém
    acompanha esse caso pelo código, que é descartado.

    Com `tarefas` (o `BackgroundTasks` da rota que recebe o relato), o agente
    de triagem lê o caso depois da resposta, sem clique de ninguém (issue
    #1827, ADR 0097, decisão 6).

    `direcao_envolvida` é a resposta do passo 3 sobre a Direção (issue #1829):
    com "sim", o caso nunca entra na fila comum e nasce na Rota Especial, com
    o relato selado; "nao_sei" fica na fila comum com o aviso.

    Sem a chave de cifra levanta `CifraIndisponivelError` antes de gravar qualquer
    coisa."""
    if direcao_envolvida is not None and direcao_envolvida not in rota_especial.RESPOSTAS_SOBRE_A_DIRECAO:
        raise ValueError("Resposta sobre a Direção fora das três do passo 3")
    especial = direcao_envolvida == "sim"
    relato_cifrado = cifra.cifrar_texto(relato)
    codigo = gerar_codigo()
    linha = {
        "codigo_hash": hash_do_codigo(codigo),
        "rota": rota,
        "etapa": "triagem",
        "categoria": categoria,
        "relato_cifrado": relato_cifrado,
    }
    if manifestacao_id is not None:
        linha |= {"origem": ORIGEM_OUVIDORIA, "manifestacao_id": manifestacao_id}
    if direcao_envolvida is not None:
        linha["direcao_envolvida"] = direcao_envolvida
    if especial:
        linha |= rota_especial.campos_da_entrada(rota_especial.agora_utc())
    for tentativa in range(1, _TENTATIVAS_DO_PROTOCOLO + 1):
        try:
            caso = supabase.table("conduta_casos").insert({**linha, "protocolo": novo_protocolo()}).execute().data[0]
            break
        except APIError as erro:
            if tentativa == _TENTATIVAS_DO_PROTOCOLO or getattr(erro, "code", None) != _VIOLACAO_DE_UNICIDADE:
                raise
    detalhe = "caso sinalizado pela Ouvidoria" if manifestacao_id is not None else "caso recebido"
    trilha.registrar(supabase, caso["id"], None, "recebimento", detalhe)
    if especial:
        rota_especial.entrar(supabase, caso["id"], relato, None, "nasceu na Rota Especial pelo Sim no passo 3")
    avisos.avisar_tarefas_novas(supabase, caso["id"], {})
    if tarefas is not None:
        agente_de_triagem.agendar_triagem_do_caso(tarefas, supabase, caso["id"])
    return {"id": caso["id"], "protocolo": caso["protocolo"], "codigo": codigo}
