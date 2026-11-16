"""A ata do Núcleo em dez blocos (issue #1775, PRD #1764, ADR 0095, decisão 10).

A ata do Núcleo é um tipo próprio, nos dez blocos do art. 20 do Regimento. A
minuta sai de um agente com prompt próprio (`prompts/nsp_ata_do_nucleo.md`), e
roda uma vez por clique: quando a Presidência importa a transcrição. Nenhum
job chama esta IA.

O que é do sistema e o que é do agente:

- identificação, presenças e quórum, pendências da reunião anterior e
  indicadores são montados aqui, do banco, e substituem o que o agente
  escrever sobre eles. Casos e indicadores ficam vazios nesta fase. As
  assinaturas também saem do sistema: são os presentes;
- deliberações, plano de ação, alertas sanitários e próxima reunião vêm do
  agente, passam pelo sanitizador (sem travessão) e pela checagem de nomes: a
  minuta que traz nome de membro fora do bloco de presenças é recusada e
  refeita uma vez. Recusada de novo, a ata fica com os blocos do agente em
  branco e um aviso, e a Presidência redige.

Quem conduz a ata (revisa e valida) é a Presidência, o Acesso pleno ou o
suplente em exercício, que é o suplente presente numa reunião sem a
Presidência presente. A ata validada vira pendência por deliberação.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from app.services import ai_processor
from app.services.paginacao import ler_tudo
from app.services.prompt_loader import load_prompt
from app.services.seguranca_do_paciente import pauta
from app.services.seguranca_do_paciente.permissao import id_do_nucleo, situacao_da_pessoa
from app.services.seguranca_do_paciente.quorum import apurar_quorum
from app.services.seguranca_do_paciente.reunioes import TipoReuniaoNsp
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

MODELO_DA_ATA = "nsp_dez_blocos"
# Todos os agentes do Núcleo usam o mesmo modelo (ADR 0095, decisão 7).
MODELO_DE_IA = "claude-sonnet-5-5"

BLOCOS = (
    ("identificacao", "Identificação"),
    ("presencas_e_quorum", "Presenças e quórum"),
    ("pendencias_anteriores", "Situação das pendências da reunião anterior"),
    ("indicadores", "Indicadores"),
    ("casos_analisados", "Casos analisados"),
    ("deliberacoes", "Deliberações"),
    ("plano_de_acao", "Plano de ação"),
    ("alertas_sanitarios", "Alertas sanitários"),
    ("proxima_reuniao", "Próxima reunião"),
    ("assinaturas", "Assinaturas"),
)
# Os blocos de texto que o agente escreve. As deliberações também são do
# agente, mas vêm estruturadas (viram pendência).
BLOCOS_DO_AGENTE = ("plano_de_acao", "alertas_sanitarios", "proxima_reuniao")

SEM_DADOS = "Sem dados nesta fase."
A_DEFINIR = "a definir"

# A apresentação à Diretoria usa a versão resumida da mesma ata: cada bloco do
# agente com no máximo três itens.
ITENS_DA_RESUMIDA = 3

AVISO_NOMES = (
    "A IA escreveu nome de membro fora da lista de presença duas vezes, e a minuta foi descartada. "
    "Redija os blocos do Núcleo abaixo."
)
AVISO_SEM_IA = "A IA não conseguiu redigir a minuta. Redija os blocos do Núcleo abaixo."

_LOTE = 200

_ROTULO_DA_SITUACAO = (
    ("presente", "Presentes"),
    ("ausente", "Ausentes"),
    ("ausente_justificado", "Ausentes com justificativa"),
    ("convidado", "Convidados"),
)


class MinutaComNomeError(ValueError):
    """A minuta trouxe nome de membro fora do bloco de presenças."""


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def reuniao_do_nucleo(supabase, id_reuniao: str) -> dict | None:
    """A reunião, se for do Núcleo; None para a reunião comum. A reunião
    comum (sem colegiado) não chega a ler os colegiados."""
    linhas = (
        supabase.table("reunioes")
        .select("id_reuniao, data, hora_inicio, hora_fim, tipo, titulo, status_ata, colegiado_id, json_ata")
        .eq("id_reuniao", id_reuniao)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not linhas or not linhas[0].get("colegiado_id"):
        return None
    return linhas[0] if linhas[0]["colegiado_id"] == id_do_nucleo(supabase) else None


def _presenca(supabase, id_reuniao: str) -> dict[str, str]:
    linhas = ler_tudo(
        lambda: supabase.table("reuniao_presencas")
        .select("participante_id, situacao")
        .eq("id_reuniao", id_reuniao)
        .order("participante_id"),
        rotulo="presença da reunião do Núcleo",
    )
    return {linha["participante_id"]: linha["situacao"] for linha in linhas}


def _participacoes(supabase, colegiado_id: str) -> list[dict]:
    return ler_tudo(
        lambda: supabase.table("participacoes")
        .select("id, participante_id, papel, vigencia_inicio, vigencia_fim, encerrada_em, termo_assinado_em")
        .eq("colegiado_id", colegiado_id)
        .order("id"),
        rotulo="participações do Núcleo",
    )


def _nomes(supabase, ids: Iterable[str]) -> dict[str, str]:
    from app.dependencies import selecionar_participantes

    ids = sorted(set(ids))
    nomes: dict[str, str] = {}
    for inicio in range(0, len(ids), _LOTE):
        lote = ids[inicio : inicio + _LOTE]
        linhas = selecionar_participantes(supabase, "id, nome_completo", lambda q, lote=lote: q.in_("id", lote)).data
        nomes.update({linha["id"]: linha["nome_completo"] for linha in linhas or [] if linha.get("nome_completo")})
    return nomes


def _dia(reuniao: dict) -> date:
    return date.fromisoformat(str(reuniao["data"])[:10])


# ---------------------------------------------------------------------------
# Os blocos do sistema
# ---------------------------------------------------------------------------


def _hora(valor: Any) -> str | None:
    return str(valor)[:5] if valor else None


def _identificacao(reuniao: dict) -> list[str]:
    data = _dia(reuniao).strftime("%d/%m/%Y")
    inicio, fim = _hora(reuniao.get("hora_inicio")), _hora(reuniao.get("hora_fim"))
    if inicio and fim:
        quando = f"Data: {data}, das {inicio} às {fim}."
    elif inicio:
        quando = f"Data: {data}, às {inicio}."
    else:
        quando = f"Data: {data}."
    return [
        f"{reuniao.get('tipo')} do Núcleo de Segurança do Paciente: {reuniao.get('titulo') or 'sem título'}.",
        quando,
        f"Registro da reunião: {reuniao['id_reuniao']}.",
    ]


def _presencas(presenca: dict[str, str], nomes: dict[str, str], quorum) -> list[str]:
    itens = []
    for situacao, rotulo in _ROTULO_DA_SITUACAO:
        pessoas = sorted(nomes.get(pid, pid) for pid, s in presenca.items() if s == situacao)
        if pessoas:
            itens.append(f"{rotulo}: {', '.join(pessoas)}.")
    if not presenca:
        itens.append("A presença não foi registrada.")
    instalada = "Reunião instalada." if quorum.instalada else "Reunião sem quórum."
    itens.append(
        f"Quórum: {quorum.presentes} presentes de {quorum.total} que contam, mínimo de {quorum.minimo}. {instalada}"
    )
    return itens


def _pendencias_anteriores(supabase, reuniao: dict) -> list[str]:
    blocos = pauta.com_situacao_atual(supabase, [{"itens": pauta._itens_das_pendencias(supabase, reuniao)}])
    itens = [f"{item['id_acao']}: {item['texto']} Situação: {item['situacao']}." for item in blocos[0]["itens"]]
    return itens or ["Nenhuma pendência da reunião anterior."]


def _assinaturas(presenca: dict[str, str], nomes: dict[str, str]) -> list[str]:
    presentes = sorted(nomes.get(pid, pid) for pid, s in presenca.items() if s == "presente")
    return [f"Assinam os presentes: {', '.join(presentes)}."] if presentes else ["Sem presentes registrados."]


def _contexto(supabase, reuniao: dict) -> dict[str, Any]:
    """O que o sistema sabe da reunião: os blocos prontos e os nomes dos
    membros do Núcleo, para a checagem da minuta."""
    presenca = _presenca(supabase, reuniao["id_reuniao"])
    participacoes = _participacoes(supabase, reuniao["colegiado_id"])
    nomes = _nomes(supabase, set(presenca) | {p["participante_id"] for p in participacoes})
    quorum = apurar_quorum(participacoes, presenca, _dia(reuniao))
    membros = {nomes[p["participante_id"]] for p in participacoes if p["participante_id"] in nomes}
    return {
        "membros": sorted(membros),
        "blocos": {
            "identificacao": _identificacao(reuniao),
            "presencas_e_quorum": _presencas(presenca, nomes, quorum),
            "pendencias_anteriores": _pendencias_anteriores(supabase, reuniao),
            "indicadores": [SEM_DADOS],
            "casos_analisados": [SEM_DADOS],
            "assinaturas": _assinaturas(presenca, nomes),
        },
    }


# ---------------------------------------------------------------------------
# A saída do agente
# ---------------------------------------------------------------------------


def _textos(valor: Any) -> list[str]:
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list):
        return []
    return [str(v).strip() for v in valor if isinstance(v, str | int | float) and str(v).strip()]


def _campo(valor: Any) -> str:
    return str(valor).strip() if isinstance(valor, str | int | float) and str(valor).strip() else ""


def _deliberacoes(valor: Any) -> list[dict[str, Any]]:
    if not isinstance(valor, list):
        return []
    saida = []
    for item in valor:
        if not isinstance(item, dict) or not _campo(item.get("texto")):
            continue
        saida.append(
            {
                "texto": _campo(item.get("texto")),
                "responsavel": _campo(item.get("responsavel")) or A_DEFINIR,
                "prazo": _campo(item.get("prazo")) or A_DEFINIR,
                "notificacao": _campo(item.get("notificacao")) or None,
            }
        )
    return saida


def _do_agente(minuta: dict[str, Any], resumida: bool) -> dict[str, Any]:
    """Só o que é do agente, limpo e sem travessão."""
    blocos = minuta.get("blocos") if isinstance(minuta.get("blocos"), dict) else {}
    teto = ITENS_DA_RESUMIDA if resumida else None
    return sanitizar_estrutura(
        {
            "blocos": {chave: _textos(blocos.get(chave))[:teto] for chave in BLOCOS_DO_AGENTE},
            "deliberacoes": _deliberacoes(minuta.get("deliberacoes")),
            "trechos_a_conferir": _textos(minuta.get("trechos_a_conferir")),
        }
    )


def _normal(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " " + " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).split()) + " "


def _formas_do_nome(nome: str) -> set[str]:
    """O nome inteiro e o primeiro com o último, normalizados."""
    partes = _normal(nome).split()
    formas = {" ".join(partes)} if partes else set()
    if len(partes) > 2:
        formas.add(f"{partes[0]} {partes[-1]}")
    return {f" {forma} " for forma in formas}


def nomes_fora_das_presencas(do_agente: dict[str, Any], membros: Iterable[str]) -> list[str]:
    """Os membros cujo nome aparece no que o agente escreveu. O responsável
    da deliberação fica de fora: o Regimento deixa o nome ali."""
    textos = [item for chave in BLOCOS_DO_AGENTE for item in do_agente["blocos"][chave]]
    textos += [d["texto"] for d in do_agente["deliberacoes"]]
    textos += [d["notificacao"] for d in do_agente["deliberacoes"] if d.get("notificacao")]
    textos += do_agente["trechos_a_conferir"]
    corpo = _normal(" ".join(textos))
    return sorted(nome for nome in membros if any(forma in corpo for forma in _formas_do_nome(nome)))


def _prazo_legivel(prazo: str) -> str:
    try:
        return date.fromisoformat(prazo).strftime("%d/%m/%Y")
    except ValueError:
        return prazo


def _itens_das_deliberacoes(deliberacoes: list[dict[str, Any]]) -> list[str]:
    itens = []
    for d in deliberacoes:
        caso = f" Notificação {d['notificacao']}." if d.get("notificacao") else ""
        itens.append(
            f"{d['texto'].rstrip('.')}. Responsável: {d['responsavel']}; prazo: {_prazo_legivel(d['prazo'])}.{caso}"
        )
    return itens or ["Nenhuma deliberação."]


def montar_ata(do_sistema: dict[str, list[str]], do_agente: dict[str, Any], *, resumida: bool) -> dict[str, Any]:
    """A ata nos dez blocos, na ordem do Regimento. Bloco do sistema vem do
    sistema; o agente não tem como sobrescrevê-lo."""
    itens = {
        **{chave: do_agente["blocos"][chave] for chave in BLOCOS_DO_AGENTE},
        "deliberacoes": _itens_das_deliberacoes(do_agente["deliberacoes"]),
        **do_sistema,
    }
    return {
        "modelo": MODELO_DA_ATA,
        "resumida": resumida,
        "blocos": [
            {
                "chave": chave,
                "titulo": titulo,
                "origem": "agente" if chave in BLOCOS_DO_AGENTE or chave == "deliberacoes" else "sistema",
                "itens": itens[chave],
            }
            for chave, titulo in BLOCOS
        ],
        "deliberacoes": do_agente["deliberacoes"],
        "trechos_a_conferir": do_agente["trechos_a_conferir"],
    }


# ---------------------------------------------------------------------------
# A minuta (um clique, uma ou duas chamadas)
# ---------------------------------------------------------------------------


def e_resumida(reuniao: dict) -> bool:
    return reuniao.get("tipo") == TipoReuniaoNsp.APRESENTACAO_A_DIRETORIA.value


def _mensagem(reuniao: dict, do_sistema: dict[str, list[str]], transcricao: str, *, resumida: bool, refazer: bool) -> str:
    partes = [
        f"Reunião do Núcleo: {reuniao.get('tipo')}, {reuniao.get('titulo') or 'sem título'}.",
        f"Data da reunião: {_dia(reuniao).isoformat()}.",
    ]
    if resumida:
        partes.append(
            "Esta é a reunião de apresentação à Diretoria: escreva a versão resumida da ata, "
            f"com no máximo {ITENS_DA_RESUMIDA} frases curtas por bloco."
        )
    if refazer:
        partes.append(
            "A minuta anterior foi recusada porque trazia nome de membro do Núcleo fora do bloco de presenças. "
            "Refaça sem nenhum nome de pessoa: use a função."
        )
    for chave, titulo in BLOCOS:
        if chave in do_sistema:
            partes.append(f"{titulo} (do sistema, não reescreva):\n" + "\n".join(f"- {i}" for i in do_sistema[chave]))
    partes.append(f"Transcrição:\n{transcricao}")
    return "\n\n".join(partes)


def _pedir_minuta(usuario: str) -> dict[str, Any]:
    """Uma chamada ao agente da ata do Núcleo. Levanta em qualquer falha."""
    if ai_processor._llm_provider() == "mock":
        raise RuntimeError("IA sem chave configurada")
    client, _modelo_geral = ai_processor._get_llm()
    bruto = ai_processor._pedir_json(
        client, MODELO_DE_IA, system=load_prompt("nsp_ata_do_nucleo"), usuario=usuario, ata=True
    )
    minuta = json.loads(bruto)
    if not isinstance(minuta, dict):
        raise ValueError("a minuta não é um objeto")
    return minuta


def _minuta_conferida(reuniao: dict, contexto: dict[str, Any], transcricao: str, resumida: bool) -> dict[str, Any]:
    """A saída do agente que passou na checagem de nomes, na primeira ou na
    segunda tentativa. Levanta `MinutaComNomeError` se as duas falharem."""
    for refazer in (False, True):
        usuario = _mensagem(reuniao, contexto["blocos"], transcricao, resumida=resumida, refazer=refazer)
        do_agente = _do_agente(_pedir_minuta(usuario), resumida)
        nomes = nomes_fora_das_presencas(do_agente, contexto["membros"])
        if not nomes:
            return do_agente
        logger.warning(
            "Minuta da ata do Núcleo %s recusada: %d nome(s) de membro fora das presenças%s",
            reuniao["id_reuniao"],
            len(nomes),
            "" if refazer else ", refazendo",
        )
    raise MinutaComNomeError


def _vazio() -> dict[str, Any]:
    return {"blocos": {chave: [] for chave in BLOCOS_DO_AGENTE}, "deliberacoes": [], "trechos_a_conferir": []}


def redigir_minuta_do_nucleo(supabase, reuniao: dict, transcricao: str) -> dict[str, Any]:
    """Monta a ata do Núcleo a partir da transcrição importada e a deixa
    aguardando a validação. Chamada só pelo pipeline da importação."""
    resumida = e_resumida(reuniao)
    contexto = _contexto(supabase, reuniao)
    aviso = None
    try:
        do_agente = _minuta_conferida(reuniao, contexto, transcricao, resumida)
    except MinutaComNomeError:
        do_agente, aviso = _vazio(), AVISO_NOMES
    except Exception as erro:  # a IA fora do ar não trava a ata: a Presidência redige
        logger.error("Minuta da ata do Núcleo %s sem IA: %s", reuniao["id_reuniao"], erro)
        do_agente, aviso = _vazio(), AVISO_SEM_IA
    ata = {**montar_ata(contexto["blocos"], do_agente, resumida=resumida), "aviso": aviso}
    supabase.table("reunioes").update({"json_ata": ata, "status_ata": "AGUARDANDO_VALIDACAO", "total_acoes": 0}).eq(
        "id_reuniao", reuniao["id_reuniao"]
    ).execute()
    logger.info("Minuta da ata do Núcleo %s pronta para validação", reuniao["id_reuniao"])
    return ata


# ---------------------------------------------------------------------------
# Quem conduz, a revisão e a validação
# ---------------------------------------------------------------------------


def conduz_a_ata(supabase, me: dict | None, recursos: Iterable[str], reuniao: dict) -> bool:
    """A Presidência e o Acesso pleno (`gerir_nucleo`) conduzem a ata; o
    suplente com Termo, só quando estava presente e a Presidência não."""
    recursos = set(recursos)
    if not me or "reunioes" not in recursos:
        return False
    if "gerir_nucleo" in recursos:
        return True
    situacao = situacao_da_pessoa(supabase, me, super_admin=False, hoje=_dia(reuniao))
    if situacao.papel_vigente != "suplente" or not situacao.termo_valido:
        return False
    presenca = _presenca(supabase, reuniao["id_reuniao"])
    if presenca.get(me["id"]) != "presente":
        return False
    presidencia = {
        p["participante_id"] for p in _participacoes(supabase, reuniao["colegiado_id"]) if p["papel"] == "presidencia"
    }
    return not any(presenca.get(pid) == "presente" for pid in presidencia)


def revisar_ata_do_nucleo(
    supabase, reuniao: dict, blocos: dict[str, list[str]], deliberacoes: list[dict[str, Any]]
) -> dict[str, Any]:
    """A Presidência reescreve os blocos do agente. Os do sistema ficam."""
    ata = reuniao["json_ata"]
    do_agente = _do_agente(
        {"blocos": blocos, "deliberacoes": deliberacoes, "trechos_a_conferir": ata.get("trechos_a_conferir")},
        resumida=False,
    )
    do_sistema = {b["chave"]: b["itens"] for b in ata["blocos"] if b["origem"] == "sistema"}
    nova = {**montar_ata(do_sistema, do_agente, resumida=ata.get("resumida", False)), "aviso": None}
    supabase.table("reunioes").update({"json_ata": nova}).eq("id_reuniao", reuniao["id_reuniao"]).execute()
    return nova


def faltas_para_validar(ata: dict[str, Any]) -> list[str]:
    """As deliberações sem responsável ou sem prazo de data."""
    faltas = []
    for i, d in enumerate(ata.get("deliberacoes") or [], start=1):
        if d["responsavel"].lower() == A_DEFINIR:
            faltas.append(f"a deliberação {i} está sem responsável")
        if pendencia_prazo(d["prazo"]) is None:
            faltas.append(f"a deliberação {i} está sem prazo")
    return faltas


def pendencia_prazo(prazo: str) -> str | None:
    """O prazo em AAAA-MM-DD, ou None quando não é uma data."""
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(prazo.strip(), formato).date().isoformat()
        except ValueError:
            continue
    return None


def validar_ata_do_nucleo(supabase, reuniao: dict, me: dict, agora: datetime) -> int:
    """A ata validada: cada deliberação vira pendência (a que já existe, presa
    à reunião), e a reunião fica aprovada. A assinatura dos presentes chega
    com a issue #1776. Devolve quantas pendências nasceram."""
    from app.services.pendencia_service import liberar_pendencias

    ata = dict(reuniao["json_ata"])
    ata["quadro_atribuicoes"] = [
        {"acao": d["texto"], "responsavel": d["responsavel"], "prazo": pendencia_prazo(d["prazo"]), "cargo": None}
        for d in ata.get("deliberacoes") or []
    ]
    supabase.table("reunioes").update({"json_ata": ata, "total_acoes": len(ata["quadro_atribuicoes"])}).eq(
        "id_reuniao", reuniao["id_reuniao"]
    ).execute()
    total = liberar_pendencias(supabase, reuniao["id_reuniao"], origem="VALIDACAO_DA_ATA_DO_NUCLEO")
    ata["validacao"] = {"por": me["id"], "em": agora.isoformat()}
    supabase.table("reunioes").update({"json_ata": ata, "status_ata": "APROVADA"}).eq(
        "id_reuniao", reuniao["id_reuniao"]
    ).execute()
    logger.info("Ata do Núcleo %s validada por %s: %d pendência(s)", reuniao["id_reuniao"], me["id"], total)
    return total
