"""O afastamento cautelar do Canal de Conduta (issue #1836; especificação,
seção 6.5; decisões 20 a 23, 35 e 36 do diretor no PRD #1786).

Disponível em qualquer etapa, enquanto o caso está aberto, para um Citado do
caso e nunca para quem relatou:

- no caso comum, quem decide é o Comitê, pelo coordenador: ele registra a
  decisão de afastar, e o aplicativo gera o pedido ao DP e ao Jurídico. O DP
  faz as notificações formais, e o parecer do Jurídico é consultivo;
- na Rota Especial, o grupo pede o afastamento à coordenação, que vê só o
  pedido e nada mais do caso (`portao.portao_do_afastamento`). A coordenação
  pede o parecer ao Jurídico com urgência e o anexa, com ciência dos membros
  do grupo, e é o parecer que define se haverá afastamento.

O pedido leva só quem afastar e o motivo: nem relato, nem protocolo, nem
quem relatou. Ele é entregue fora do aplicativo, e a coordenação registra a
entrega ao DP e ao Jurídico. O parecer entra cifrado no bucket do Canal e só
sai pela rota que confere o acesso.

Toda ação grava a sua linha na trilha antes de mudar qualquer coisa.
"""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from datetime import date
from typing import Any

from postgrest.exceptions import APIError

from app.services import storage
from app.services.conduta import cifra, impedimento, membros, trilha
from app.services.conduta.acesso import coordenacao_abre_o_pedido, pessoa_no_comite
from app.services.conduta.portao import CasoAberto, PedidoAberto
from app.services.conduta.ritos import agora_utc, data_do_envio
from app.services.conduta.rota_especial import DO_GRUPO, no_grupo
from app.services.conduta.triagem import AcaoRecusadaError

logger = logging.getLogger(__name__)

TABELA = "conduta_afastamentos"
BUCKET = "conduta-arquivos"
AVISO = "O afastamento cautelar é remunerado e não é punição."
RESULTADOS = {"afastar": "afastar", "nao_afastar": "não afastar"}
DESTINOS = {"dp": "ao DP", "juridico": "ao Jurídico"}
TAMANHO_DO_MOTIVO = 1000
LIMITE_DO_PARECER = 20 * 1024 * 1024
_PROTOCOLO = re.compile(r"CC-[A-Z0-9]{4}-[A-Z0-9]{4}", re.IGNORECASE)


# ── Quem relatou ────────────────────────────────────────────────────────────


def _normal(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.casefold().split())


def _nomes_de_quem_relatou(supabase, caso: dict) -> set[str]:
    """Quem relatou, quando o caso sabe: o denunciante identificado ouvido na
    Apuração e, no caso que a Ouvidoria sinalizou, o nome da manifestação."""
    nomes = {
        cifra.decifrar_texto(d["nome_cifrado"])
        for d in supabase.table("conduta_depoimentos").select("*").eq("caso_id", caso["id"]).execute().data or []
        if d.get("papel") == "denunciante"
    }
    if caso.get("manifestacao_id"):
        manifestacao = (
            supabase.table("ouvidoria_protocolos")
            .select("manifestante_nome")
            .eq("id", caso["manifestacao_id"])
            .limit(1)
            .execute()
            .data
            or []
        )
        nomes |= {m.get("manifestante_nome") or "" for m in manifestacao}
    return {_normal(n) for n in nomes if _normal(n)}


# ── O registro ──────────────────────────────────────────────────────────────


def _do_caso(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(TABELA).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda x: str(x.get("registrado_em") or ""))


def pode_registrar(aberto: CasoAberto) -> bool:
    caso = aberto.caso
    if caso.get("encerrado_em"):
        return False
    if caso.get("rota") == "especial":
        return no_grupo(aberto)
    return aberto.pessoa.papel == "coordenacao"


def registrar(supabase, aberto: CasoAberto, *, citado_id: str, motivo: str) -> dict:
    """No caso comum, a decisão do coordenador; na Rota Especial, o pedido do
    grupo à coordenação."""
    caso = aberto.caso
    especial = caso.get("rota") == "especial"
    if caso.get("encerrado_em"):
        raise AcaoRecusadaError(409, "O caso está encerrado.")
    if not pode_registrar(aberto):
        quem = "o Grupo Especial pede" if especial else "o coordenador do Comitê registra"
        raise AcaoRecusadaError(403, f"Só {quem} o afastamento cautelar.")
    citado = next((c for c in impedimento.citados_para_a_tela(supabase, caso["id"]) if c["id"] == citado_id), None)
    if citado is None:
        raise AcaoRecusadaError(422, "Escolha quem afastar entre os Citados do caso.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise AcaoRecusadaError(422, "Diga o motivo do afastamento.")
    if len(motivo) > TAMANHO_DO_MOTIVO:
        raise AcaoRecusadaError(422, "O motivo passou do tamanho que cabe.")
    if _PROTOCOLO.search(motivo):
        raise AcaoRecusadaError(422, "O motivo não leva protocolo de caso.")
    if _normal(citado["nome"] or "") in _nomes_de_quem_relatou(supabase, caso):
        raise AcaoRecusadaError(422, "Nenhuma medida cautelar recai sobre quem relatou.")
    if any(a["citado_id"] == citado_id for a in _do_caso(supabase, caso["id"])):
        raise AcaoRecusadaError(409, "Já há afastamento registrado para esta pessoa neste caso.")
    acao, detalhe = (
        ("afastamento_pedido", "o Grupo Especial pediu o afastamento cautelar à coordenação")
        if especial
        else ("afastamento_decidido", "o coordenador decidiu o afastamento cautelar")
    )
    trilha.registrar(supabase, caso["id"], aberto.autor_id, acao, detalhe)
    supabase.table(TABELA).insert(
        {
            "caso_id": caso["id"],
            "citado_id": citado_id,
            "rota": "especial" if especial else "comum",
            "quem_cifrado": cifra.cifrar_texto(citado["nome"] or ""),
            "motivo_cifrado": cifra.cifrar_texto(motivo),
            "registrado_por": aberto.autor_id,
            "registrado_em": agora_utc().isoformat(),
        }
    ).execute()
    return caso


# ── O que se vê ─────────────────────────────────────────────────────────────


def resultado(afastamento: dict) -> str | None:
    """No caso comum, a decisão do coordenador é afastar. Na Rota Especial,
    quem define é o parecer: sem ele, ainda não há resultado."""
    if afastamento["rota"] == "comum":
        return "afastar"
    return afastamento.get("parecer_resultado")


def _vista(supabase, afastamento: dict, coordena: bool) -> dict[str, Any]:
    parecer = None
    if afastamento.get("parecer_anexado_em"):
        ciencia = afastamento.get("ciencia_de")
        nomes = membros.nomes(supabase, list(ciencia or []))
        parecer = {
            "anexado_em": afastamento["parecer_anexado_em"],
            "ciencia_de": [nomes.get(pid) or "" for pid in ciencia] if ciencia is not None else None,
        }
    return {
        "id": afastamento["id"],
        "rota": afastamento["rota"],
        "quem": cifra.decifrar_texto(afastamento["quem_cifrado"]),
        "motivo": cifra.decifrar_texto(afastamento["motivo_cifrado"]),
        "registrado_em": afastamento["registrado_em"],
        "resultado": resultado(afastamento),
        "entregas": {
            "dp": afastamento.get("entregue_ao_dp_em"),
            "juridico": afastamento.get("entregue_ao_juridico_em"),
        },
        "parecer": parecer,
        "pode_registrar_entrega": coordena,
        "pode_anexar_parecer": coordena and not afastamento.get("parecer_anexado_em"),
    }


def _coordena(aberto: PedidoAberto) -> bool:
    """Quem registra a entrega e anexa o parecer: a coordenação do caso comum
    e, na Rota Especial, a coordenação pelo pedido."""
    if aberto.afastamento["rota"] == "especial":
        return aberto.so_o_pedido
    return aberto.pessoa.papel == "coordenacao"


def texto_do_pedido(quem: str, motivo: str) -> str:
    return (
        "Pedido de afastamento cautelar\n"
        "Comitê de Conduta do Hospital São Matheus\n\n"
        f"Quem afastar: {quem}\n"
        f"Motivo: {motivo}\n\n"
        f"{AVISO}"
    )


def abrir_pedido(supabase, aberto: PedidoAberto) -> dict[str, Any]:
    """O pedido ao DP e ao Jurídico e em que pé ele está. Só quem afastar e o
    motivo: nada do caso vai junto. A leitura entra na trilha."""
    trilha.registrar(supabase, aberto.caso["id"], aberto.autor_id, "leitura", "abriu o pedido de afastamento")
    vista = _vista(supabase, aberto.afastamento, _coordena(aberto))
    return {
        "pedido": {
            "quem": vista["quem"],
            "motivo": vista["motivo"],
            "texto": texto_do_pedido(vista["quem"], vista["motivo"]),
        },
        **{campo: vista[campo] for campo in ("id", "rota", "registrado_em", "resultado", "entregas", "parecer")},
        "pode_registrar_entrega": vista["pode_registrar_entrega"],
        "pode_anexar_parecer": vista["pode_anexar_parecer"],
        "aviso": AVISO,
    }


def _exigir_coordenacao(aberto: PedidoAberto, o_que: str) -> None:
    if not _coordena(aberto):
        raise AcaoRecusadaError(403, f"Só a coordenação do Comitê {o_que}.")


def registrar_entrega(supabase, aberto: PedidoAberto, *, destino: str, entregue_em: date, hoje: date) -> dict:
    """O pedido foi entregue fora do aplicativo, ao DP ou ao Jurídico, nesta
    data. Cada entrega se registra uma vez."""
    _exigir_coordenacao(aberto, "registra a entrega do pedido")
    if destino not in DESTINOS:
        raise AcaoRecusadaError(422, "Diga se o pedido foi entregue ao DP ou ao Jurídico.")
    afastamento = aberto.afastamento
    coluna = f"entregue_ao_{destino}_em"
    if afastamento.get(coluna):
        raise AcaoRecusadaError(409, f"A entrega {DESTINOS[destino]} já foi registrada.")
    if entregue_em > hoje or entregue_em < data_do_envio(afastamento["registrado_em"]):
        raise AcaoRecusadaError(422, "A data da entrega fica entre o registro do afastamento e hoje.")
    trilha.registrar(
        supabase,
        aberto.caso["id"],
        aberto.autor_id,
        "afastamento_entregue",
        f"registrou a entrega do pedido de afastamento {DESTINOS[destino]} em {entregue_em.strftime('%d/%m/%Y')}",
    )
    marcada = (
        supabase.table(TABELA)
        .update({coluna: entregue_em.isoformat(), f"entregue_ao_{destino}_por": aberto.autor_id})
        .eq("id", afastamento["id"])
        .is_(coluna, "null")
        .execute()
        .data
    )
    if not marcada:
        raise AcaoRecusadaError(409, "O afastamento mudou enquanto você agia. Abra de novo.")
    return marcada[0]


def _ciencia_do_grupo(supabase, caso_id: str) -> list[str]:
    """Os membros do grupo da Rota Especial no caso, hoje: os que analisaram o
    caso e têm ciência do parecer."""
    linhas = supabase.table("conduta_atribuicoes").select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(
        {
            a["participante_id"]
            for a in linhas
            if a.get("motivo") in DO_GRUPO and not a.get("revogada_em") and not a.get("impedido_em")
        }
    )


def anexar_parecer(supabase, aberto: PedidoAberto, *, conteudo: bytes, resultado_do_parecer: str | None) -> dict:
    """A coordenação anexa o parecer do Jurídico, em PDF, uma vez. No caso
    comum ele é consultivo. Na Rota Especial ele define o resultado e fica com
    a ciência dos membros do grupo."""
    _exigir_coordenacao(aberto, "anexa o parecer do Jurídico")
    afastamento = aberto.afastamento
    especial = afastamento["rota"] == "especial"
    if afastamento.get("parecer_anexado_em"):
        raise AcaoRecusadaError(409, "O parecer do Jurídico já foi anexado.")
    if especial and resultado_do_parecer not in RESULTADOS:
        raise AcaoRecusadaError(422, "Diga o que o parecer definiu: afastar ou não afastar.")
    if not especial and resultado_do_parecer:
        raise AcaoRecusadaError(422, "No caso comum, quem decide é o coordenador: o parecer é consultivo.")
    if not conteudo.startswith(b"%PDF"):
        raise AcaoRecusadaError(422, "Envie o parecer do Jurídico em PDF.")
    if len(conteudo) > LIMITE_DO_PARECER:
        raise AcaoRecusadaError(422, "O parecer passou de 20 MB.")
    cifrado = cifra.cifrar_arquivo(conteudo)
    ciencia = _ciencia_do_grupo(supabase, aberto.caso["id"]) if especial else None
    detalhe = "anexou o parecer do Jurídico"
    if especial:
        detalhe += f": {RESULTADOS[resultado_do_parecer]}; com ciência de {len(ciencia)} membro(s) do grupo"
    trilha.registrar(supabase, aberto.caso["id"], aberto.autor_id, "parecer_do_juridico_anexado", detalhe)
    caminho = f"afastamentos/{afastamento['id']}/{uuid.uuid4()}"
    if not storage.upload_private(supabase, BUCKET, caminho, cifrado, "application/octet-stream"):
        raise AcaoRecusadaError(503, "O parecer não foi guardado. Tente de novo.")
    campos = {
        "parecer_storage_path": caminho,
        "parecer_tamanho_bytes": len(conteudo),
        "parecer_codigo_integridade": trilha.codigo_de_integridade(conteudo),
        "parecer_anexado_por": aberto.autor_id,
        "parecer_anexado_em": agora_utc().isoformat(),
    }
    if especial:
        campos |= {"parecer_resultado": resultado_do_parecer, "ciencia_de": ciencia}
    try:
        marcada = (
            supabase.table(TABELA)
            .update(campos)
            .eq("id", afastamento["id"])
            .is_("parecer_storage_path", "null")
            .execute()
            .data
        )
    except APIError:
        marcada = []
    if not marcada:
        if not storage.delete_file(supabase, BUCKET, caminho):
            logger.error("Parecer de afastamento órfão no bucket do Canal: %s", caminho)
        raise AcaoRecusadaError(409, "O parecer do Jurídico já foi anexado.")
    return marcada[0]


def abrir_parecer(supabase, aberto: PedidoAberto) -> bytes:
    """O parecer decifrado. A abertura entra na trilha antes de ele sair."""
    caminho = aberto.afastamento.get("parecer_storage_path")
    if not caminho:
        raise AcaoRecusadaError(404, "O parecer do Jurídico ainda não foi anexado.")
    trilha.registrar(supabase, aberto.caso["id"], aberto.autor_id, "leitura", "abriu o parecer do Jurídico")
    cifrado = storage.download_file(supabase, BUCKET, caminho)
    if cifrado is None:
        raise AcaoRecusadaError(503, "O parecer não pôde ser lido agora. Tente de novo.")
    return cifra.decifrar_arquivo(cifrado)


def pedidos_da_rota_especial(supabase, coordenacao_id: str) -> list[dict[str, Any]]:
    """Os pedidos da Rota Especial que a coordenação abre, do mais novo ao mais
    antigo, sem nada do caso: nem protocolo, nem quem afastar. O pedido se abre
    pelo portão do afastamento, que grava a leitura."""
    pessoa = pessoa_no_comite(supabase, coordenacao_id)
    linhas = supabase.table(TABELA).select("*").eq("rota", "especial").execute().data or []
    return [
        {
            "id": a["id"],
            "caso_id": a["caso_id"],
            "registrado_em": a["registrado_em"],
            "resultado": resultado(a),
            "parecer_anexado": bool(a.get("parecer_anexado_em")),
        }
        for a in sorted(linhas, key=lambda x: str(x.get("registrado_em") or ""), reverse=True)
        if coordenacao_abre_o_pedido(supabase, pessoa, a["caso_id"]) is not None
    ]


def para_a_tela(supabase, aberto: CasoAberto) -> dict[str, Any]:
    """O que a tela do caso mostra a quem abre o caso inteiro."""
    coordena = aberto.caso.get("rota") == "comum" and aberto.pessoa.papel == "coordenacao"
    return {
        "aviso_do_afastamento": AVISO,
        "afastamentos": [_vista(supabase, a, coordena) for a in _do_caso(supabase, aberto.caso["id"])],
        "pode_registrar_afastamento": pode_registrar(aberto),
    }
