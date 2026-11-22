"""A Rota Especial do Canal de Conduta (issue #1829; especificação, seção 10;
decisões 16, 19 e 28 do diretor no PRD #1786).

O relato que envolve a Direção, a Presidência ou a família proprietária é
apurado por um grupo sem nenhum diretor:

- o "Sim" no passo 3 nunca entra na fila comum: o caso nasce na Rota
  Especial (`registrar_caso` chama `entrar`);
- o "Não sei" e o sinal do agente entram na fila comum com o aviso, e qualquer
  membro da fila comum confirma o desvio (`confirmar_desvio`);
- na entrada, o grupo é montado uma vez e fica gravado nas atribuições do
  caso, com o Termo da época: uma troca no Comitê depois não o muda. O grupo
  é o membro não diretor do Comitê (fora a coordenação, que nem fica sabendo
  do caso) e um suplente não diretor. O membro eleito da CIPA entra por
  convite do grupo, dentro do caso (`convites`);
- na entrada, o relato é selado: gravado com data, hora e código de
  integridade, numa tabela que nenhum perfil altera nem apaga (migration 214);
- o prazo é de 60 dias, com avisos ao grupo em 15, 30 e 60 dias. Vencido sem
  parecer, fica o registro permanente "Caso não respondido no prazo";
- no encerramento, o grupo registra a quem entregou o parecer, fora do
  aplicativo, e em que data. O destinatário vai cifrado;
- para fora do grupo, só a contagem: recebidos, concluídos e em aberto.

Toda ação grava a sua linha na trilha antes de mudar o caso.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any

from app.services.conduta import avisos, cifra, membros, trilha
from app.services.conduta.acesso import PAPEIS_DA_FILA_COMUM, hoje_em_sao_paulo
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc, data_do_envio, prazo_do_rito
from app.services.conduta.triagem import AcaoRecusadaError, _mudar, registrar_vencidos

RESPOSTAS_SOBRE_A_DIRECAO = ("sim", "nao", "nao_sei")
GRUPO = "grupo_especial"
# Quem é do grupo no caso: os dois da entrada, o membro da CIPA convidado e o
# suplente que entra no lugar de um impedido. O apurador convidado não é.
DO_GRUPO = (GRUPO, "cipa", "suplente_convocado")
# As cadeiras de onde sai o membro do grupo. A coordenação fica de fora.
CADEIRAS_DO_GRUPO = ("membro", "segundo_leitor")

AVISO = (
    "Este relato pode envolver a Direção, a Presidência ou a família proprietária. "
    "Se envolver, confirme o desvio para a Rota Especial."
)
# Do mais adiantado para o primeiro: o primeiro que a contagem alcança é o do dia.
MARCOS = (("marco_60", 60), ("marco_30", 30), ("marco_15", 15))
_TAMANHO_DO_DESTINATARIO = 300


# ── O selo ──────────────────────────────────────────────────────────────────


def _codigo_do_selo(caso_id: str, relato: str, selado_em: str) -> str:
    momento = datetime.fromisoformat(selado_em).astimezone(UTC).isoformat(timespec="microseconds")
    conteudo = [str(caso_id), relato, momento]
    return hashlib.sha256(json.dumps(conteudo, ensure_ascii=False).encode("utf-8")).hexdigest()


def selo_confere(selo: dict[str, Any]) -> bool:
    """O relato selado ainda bate com o código gravado na entrada."""
    relato = cifra.decifrar_texto(selo["relato_cifrado"])
    return _codigo_do_selo(selo["caso_id"], relato, selo["selado_em"]) == selo["codigo"]


def _selar(supabase, caso_id: str, relato: str) -> None:
    selado_em = datetime.now(UTC).isoformat(timespec="microseconds")
    supabase.table("conduta_selos").insert(
        {
            "caso_id": caso_id,
            "relato_cifrado": cifra.cifrar_texto(relato),
            "selado_em": selado_em,
            "codigo": _codigo_do_selo(caso_id, relato, selado_em),
        }
    ).execute()


# ── O grupo ─────────────────────────────────────────────────────────────────


def grupo_da_entrada(supabase, hoje: date, fora: set[str] = frozenset()) -> list[dict]:
    """As Participações vigentes que formam o grupo hoje: os membros não
    diretores (fora a coordenação) e o suplente não diretor mais antigo, todos
    com o Termo assinado. `fora` são os Citados do caso."""
    comite_id = membros.id_do_comite(supabase)
    if not comite_id:
        return []
    aptas = sorted(
        (
            p
            for p in membros.participacoes(supabase, comite_id)
            if membros.vigente_em(p, hoje)
            and p.get("termo_assinado_em")
            and not p.get("e_diretor")
            and p["participante_id"] not in fora
        ),
        key=lambda p: (str(p["vigencia_inicio"]), p["participante_id"]),
    )
    do_comite = [p for p in aptas if p["papel"] in CADEIRAS_DO_GRUPO]
    suplente = next((p for p in aptas if p["papel"] == "suplente"), None)
    return do_comite + ([suplente] if suplente else [])


def _citados(supabase, caso_id: str) -> set[str]:
    linhas = supabase.table("conduta_citados").select("participante_id").eq("caso_id", caso_id).execute().data
    return {linha["participante_id"] for linha in linhas or [] if linha.get("participante_id")}


def entrar(supabase, caso_id: str, relato: str, autor_id: str | None, detalhe: str) -> None:
    """O caso entra na Rota Especial: a linha da trilha, o selo do relato e o
    grupo gravado nas atribuições do caso, com o Termo de cada um."""
    grupo = grupo_da_entrada(supabase, hoje_em_sao_paulo(), _citados(supabase, caso_id))
    trilha.registrar(supabase, caso_id, autor_id, "rota_especial", f"{detalhe}; grupo de {len(grupo)}, sem diretor")
    _selar(supabase, caso_id, relato)
    for p in grupo:
        supabase.table("conduta_atribuicoes").insert(
            {
                "caso_id": caso_id,
                "participante_id": p["participante_id"],
                "motivo": GRUPO,
                "termo_assinado_em": p["termo_assinado_em"],
            }
        ).execute()
    if not grupo:
        trilha.registrar(supabase, caso_id, None, "grupo_especial_vazio", "nenhum membro não diretor para o grupo")


def campos_da_entrada(recebido_em: str | datetime) -> dict[str, Any]:
    return {
        "rota": "especial",
        "rito": "especial",
        "etapa": "apuracao",
        "prazo_em": prazo_do_rito("especial", recebido_em).isoformat(),
    }


def no_grupo(aberto: CasoAberto) -> bool:
    return any(a.get("motivo") in DO_GRUPO and not a.get("revogada_em") for a in aberto.atribuicoes)


# ── O desvio pela fila comum ────────────────────────────────────────────────


def tem_aviso(caso: dict[str, Any]) -> bool:
    """O "Não sei" no passo 3 ou o sinal do agente, num caso ainda da fila comum."""
    return (
        caso.get("rota") == "comum"
        and not caso.get("encerrado_em")
        and (caso.get("direcao_envolvida") == "nao_sei" or bool(caso.get("sinal_especial")))
    )


def marcar_sinal_do_agente(supabase, caso_id: str) -> None:
    """O agente de triagem sugeriu a Rota Especial: o caso ganha o aviso na
    fila comum. Só o membro desvia."""
    supabase.table("conduta_casos").update({"sinal_especial": True}).eq("id", caso_id).execute()


def confirmar_desvio(supabase, aberto: CasoAberto) -> dict:
    caso = aberto.caso
    if aberto.pessoa.papel not in PAPEIS_DA_FILA_COMUM:
        raise AcaoRecusadaError(403, "Só um membro do Comitê confirma o desvio para a Rota Especial.")
    if not tem_aviso(caso):
        raise AcaoRecusadaError(409, "Este caso não tem o aviso de Rota Especial.")
    relato = cifra.decifrar_texto(caso["relato_cifrado"])
    # Quem a fila comum pôs no caso (o suplente convocado, que pode ser
    # diretor, o apurador e a CIPA convidados) sai: o caso Especial é só do
    # grupo. O impedimento fica, porque ele barra a pessoa.
    da_fila_comum = (
        supabase.table("conduta_atribuicoes")
        .select("id")
        .eq("caso_id", caso["id"])
        .is_("revogada_em", "null")
        .is_("impedido_em", "null")
        .execute()
        .data
        or []
    )
    detalhe = "confirmou o desvio para a Rota Especial"
    if da_fila_comum:
        detalhe += f"; {len(da_fila_comum)} atribuição(ões) da fila comum revogada(s)"
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "desvio_especial", detalhe)
    mudado = _mudar(
        supabase,
        caso,
        caso.get("etapa") or "triagem",
        {
            **campos_da_entrada(caso["recebido_em"]),
            "desviado_por": aberto.autor_id,
            "desviado_em": agora_utc().isoformat(),
        },
    )
    revogada_em = agora_utc().isoformat()
    for atribuicao in da_fila_comum:
        supabase.table("conduta_atribuicoes").update({"revogada_em": revogada_em}).eq("id", atribuicao["id"]).execute()
    entrar(supabase, caso["id"], relato, None, "entrou na Rota Especial pelo desvio")
    return mudado


# ── A entrega do parecer ────────────────────────────────────────────────────


def _entrega(supabase, caso_id: str) -> dict | None:
    linhas = supabase.table("conduta_entregas_do_parecer").select("*").eq("caso_id", caso_id).execute().data or []
    return linhas[0] if linhas else None


def registrar_entrega(supabase, aberto: CasoAberto, *, destinatario: str, entregue_em: date, hoje: date) -> dict:
    caso = aberto.caso
    if caso.get("rota") != "especial" or not no_grupo(aberto):
        raise AcaoRecusadaError(403, "Só o Grupo Especial registra a entrega do parecer.")
    if caso.get("encerrado_em"):
        raise AcaoRecusadaError(409, "A entrega do parecer já foi registrada.")
    destinatario = (destinatario or "").strip()
    if not destinatario:
        raise AcaoRecusadaError(422, "Diga a quem o parecer foi entregue.")
    if len(destinatario) > _TAMANHO_DO_DESTINATARIO:
        raise AcaoRecusadaError(422, "O destinatário passou do tamanho que cabe.")
    if entregue_em > hoje or entregue_em < data_do_envio(caso["recebido_em"]):
        raise AcaoRecusadaError(422, "A data da entrega fica entre a chegada do relato e hoje.")
    registrar_vencidos(supabase, [caso], hoje)
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "entrega_do_parecer",
        f"registrou a entrega do parecer em {entregue_em.strftime('%d/%m/%Y')}",
    )
    supabase.table("conduta_entregas_do_parecer").insert(
        {
            "caso_id": caso["id"],
            "destinatario_cifrado": cifra.cifrar_texto(destinatario),
            "entregue_em": entregue_em.isoformat(),
            "autor_id": aberto.autor_id,
        }
    ).execute()
    return _mudar(
        supabase,
        caso,
        caso.get("etapa") or "apuracao",
        {"encerrado_em": agora_utc().isoformat(), "desfecho": "parecer_entregue", "etapa": "encerrado"},
    )


# ── A tela do caso ──────────────────────────────────────────────────────────


def para_a_tela(supabase, aberto: CasoAberto) -> dict[str, Any]:
    caso = aberto.caso
    aviso = tem_aviso(caso)
    saida: dict[str, Any] = {
        "aviso_de_rota_especial": AVISO if aviso else None,
        "pode_desviar": aviso and aberto.pessoa.papel in PAPEIS_DA_FILA_COMUM,
        "rota_especial": None,
    }
    if caso.get("rota") != "especial":
        return saida
    selos = supabase.table("conduta_selos").select("*").eq("caso_id", caso["id"]).execute().data or []
    # Só o prazo da Rota Especial: o Rápido ou o Completo que venceu ainda na
    # fila comum, antes do desvio, não é "Caso não respondido no prazo".
    vencidos = (
        supabase.table("conduta_prazos_vencidos")
        .select("id")
        .eq("caso_id", caso["id"])
        .eq("prazo_em", str(caso.get("prazo_em"))[:10])
        .execute()
        .data
    )
    entrega = _entrega(supabase, caso["id"])
    saida["rota_especial"] = {
        "selo": {"selado_em": selos[0]["selado_em"], "codigo": selos[0]["codigo"], "confere": selo_confere(selos[0])}
        if selos
        else None,
        "nao_respondido_no_prazo": bool(vencidos),
        "entrega": {
            "destinatario": cifra.decifrar_texto(entrega["destinatario_cifrado"]),
            "entregue_em": entrega["entregue_em"],
        }
        if entrega
        else None,
        "pode_registrar_entrega": no_grupo(aberto) and not caso.get("encerrado_em"),
    }
    return saida


# ── Para fora do grupo, só a contagem ───────────────────────────────────────


def contagem(supabase) -> dict[str, int]:
    linhas = supabase.table("conduta_casos").select("encerrado_em").eq("rota", "especial").execute().data or []
    concluidos = sum(1 for linha in linhas if linha.get("encerrado_em"))
    return {"recebidos": len(linhas), "concluidos": concluidos, "em_aberto": len(linhas) - concluidos}


# ── A rodada do dia: os marcos e o prazo vencido ────────────────────────────


def _marco(dias: int) -> str | None:
    return next((marco for marco, n in MARCOS if dias >= n), None)


def rodada(supabase, hoje: date) -> int:
    """Grava o aviso do marco do dia (15, 30 ou 60 dias do envio) a quem abre
    cada caso aberto da Rota Especial, e o prazo vencido sem parecer. Devolve
    quantos avisos gravou."""
    abertos = (
        supabase.table("conduta_casos")
        .select("id, protocolo, rota, etapa, rito, recebido_em, prazo_em, encerrado_em")
        .eq("rota", "especial")
        .is_("encerrado_em", "null")
        .execute()
        .data
        or []
    )
    registrar_vencidos(supabase, abertos, hoje)
    gravados = 0
    for caso in abertos:
        envio = data_do_envio(caso["recebido_em"])
        marco = _marco((hoje - envio).days)
        if marco is None:
            continue
        ja = (
            supabase.table(avisos.TABELA).select("motivo").eq("caso_id", caso["id"]).eq("referencia", envio.isoformat())
        )
        ja_marcos = {linha["motivo"] for linha in ja.execute().data or []}
        # O job parado uns dias não manda o de 15 depois do de 30.
        posicao = [m for m, _ in MARCOS].index(marco)
        if any(m in ja_marcos for m, _ in MARCOS[: posicao + 1]):
            continue
        for pid in sorted(pid for pid, _, _ in avisos._quem_abre(supabase, caso, hoje)):
            gravados += avisos._gravar(supabase, caso, pid, marco, envio.isoformat())
    return gravados
