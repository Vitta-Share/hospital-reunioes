"""A ata de deliberação e a reunião do Comitê de Conduta (issue #1834;
especificação, seções 6.3, 6.4, 6.7, 7.3, 8 e Anexo D; ADR 0097, decisão 7).

Na etapa Voto, fechada a rodada com maioria, a coordenação toca em GERAR ATA,
e o agente do Anexo D redige a ata: no rito Rápido, do relatório de apuração e
dos votos; no Completo, também da transcrição da reunião do Comitê, que a
coordenação anexa na etapa Voto pelo botão próprio (sem seletor de tipo). O
áudio da reunião não é anexado em nenhum momento.

A parte que decide é do aplicativo, nunca do agente: a deliberação (resultado,
por maioria ou unanimidade), a medida da maioria e os votos de cada membro
saem dos votos registrados. O agente escreve o resto (resumo, provas, defesa,
fundamentos, correção de processo e encaminhamentos) e os "Pontos a
confirmar", que são Sugestão e ficam fora da ata: ali entra a divergência
entre a transcrição e os votos registrados. Nenhum nome vai ao agente: os
nomes viram marcadores na ida e voltam aqui (`marcadores`).

A ata vai à ClickSign para os três votantes, e a cópia assinada volta para a
trilha (`assinaturas`). No Completo, "CONCLUIR REUNIÃO" só libera com os quatro
itens da lista, e ao concluir a transcrição sai do banco e do bucket, com a
eliminação na trilha. O banco tem as mesmas travas (migration 218).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from postgrest.exceptions import APIError

from app.config import settings
from app.services import storage
from app.services.conduta import assinaturas, cifra, depoimentos, membros, relatorio, trilha
from app.services.conduta.acesso import hoje_em_sao_paulo
from app.services.conduta.marcadores import Marcacao
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc
from app.services.ia_chaves import ClienteDaAnthropic
from app.services.prompt_loader import load_prompt
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

ATAS = "conduta_atas"
TRANSCRICOES = "conduta_reuniao_transcricoes"
CONFERENCIA = "conduta_reuniao_conferencia"
BUCKET = depoimentos.BUCKET
PROMPT_DA_ATA = "conduta_ata_de_deliberacao"

_MB = 1024 * 1024
# A transcrição, como a do depoimento. Nenhum tipo de áudio entra (7.3).
CONTENT_TYPES_DA_TRANSCRICAO = dict(depoimentos.TIPOS["transcricao"].content_types)
LIMITE_DA_TRANSCRICAO = 20 * _MB
RECUSA_DA_TRANSCRICAO = "Envie a transcrição em TXT, VTT, DOCX ou PDF. O áudio da reunião não é anexado."

# A lista de conferência da reunião (especificação, 7.3), na ordem da tela.
ITENS_DA_REUNIAO = (
    ("transcricao", "Transcrição anexada"),
    ("ata_assinada", "Ata assinada pelos três"),
    ("gravacao_apagada", "Apaguei a gravação de áudio da plataforma de gravação"),
    ("arquivos_apagados", "Apaguei os arquivos do computador e do celular"),
)
AUTOMATICOS = ("transcricao", "ata_assinada")
DECLARACOES = {item: rotulo for item, rotulo in ITENS_DA_REUNIAO if item not in AUTOMATICOS}

RITOS = {"rapido": "Rápido", "completo": "Completo"}
_TAMANHO_DO_MATERIAL = 60000
_TAMANHO_DO_TEXTO = 3000
_ITENS = 30
MAX_TOKENS = 4096
TEMPO_LIMITE_S = 120.0


class AtaRecusadaError(Exception):
    """A ação não pode acontecer agora. `status` vai para a resposta, e a
    mensagem diz o motivo numa linha."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ── Leituras ────────────────────────────────────────────────────────────────


def _versoes(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(ATAS).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda v: v["versao"])


def _assinaturas_da_ata(supabase, caso_id: str) -> list[dict]:
    linhas = (
        supabase.table(assinaturas.TABELA)
        .select("*")
        .eq("tipo", assinaturas.ATA_DE_DELIBERACAO)
        .eq("caso_id", caso_id)
        .execute()
        .data
    ) or []
    return sorted(linhas, key=lambda a: str(a.get("created_at") or ""))


def _assinatura_da_versao(supabase, caso_id: str, ata_id: str) -> dict | None:
    vivas = [
        a
        for a in _assinaturas_da_ata(supabase, caso_id)
        if a.get("ata_id") == ata_id and a.get("situacao") != "cancelado"
    ]
    return vivas[-1] if vivas else None


def ata_assinada(supabase, caso_id: str) -> bool:
    """A última versão da ata do caso, assinada pelos três votantes."""
    versoes = _versoes(supabase, caso_id)
    if not versoes:
        return False
    assinatura = _assinatura_da_versao(supabase, caso_id, versoes[-1]["id"])
    return bool(assinatura) and assinatura["situacao"] == "assinado"


def _transcricoes(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(TRANSCRICOES).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda t: t["versao"])


def _marcas(supabase, caso_id: str) -> list[dict]:
    return supabase.table(CONFERENCIA).select("*").eq("caso_id", caso_id).execute().data or []


def _completo(caso: dict) -> bool:
    return caso.get("rito") == "completo"


def lista_da_reuniao(supabase, caso: dict, nomes: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Os quatro itens, cada um `feito` ou `pendente`. O feito diz quem e
    quando. Depois de eliminada, a transcrição segue contando como anexada."""
    nomes = nomes or {}
    transcricoes = _transcricoes(supabase, caso["id"])
    por_item = {m["item"]: m for m in _marcas(supabase, caso["id"])}
    lista = []
    for item, rotulo in ITENS_DA_REUNIAO:
        linha: dict[str, Any] = {
            "item": item,
            "rotulo": rotulo,
            "automatico": item in AUTOMATICOS,
            "estado": "pendente",
        }
        if item == "transcricao":
            if transcricoes:
                ultima = transcricoes[-1]
                linha.update(
                    estado="feito", marcado_por=nomes.get(ultima["enviado_por"], ""), marcado_em=ultima["enviado_em"]
                )
            elif caso.get("transcricao_eliminada_em"):
                linha.update(estado="feito")
        elif item == "ata_assinada":
            if ata_assinada(supabase, caso["id"]):
                linha.update(estado="feito")
        elif item in por_item:
            marca = por_item[item]
            linha.update(
                estado="feito", marcado_por=nomes.get(marca["marcado_por"], ""), marcado_em=marca["marcado_em"]
            )
        lista.append(linha)
    return lista


def _bloqueio_da_lista(lista: list[dict]) -> str | None:
    faltam = [i["rotulo"] for i in lista if i["estado"] == "pendente"]
    return f"Falta marcar: {', '.join(faltam)}." if faltam else None


def bloqueio_da_geracao(supabase, aberto: CasoAberto, situacao_do_voto) -> str | None:
    """O motivo de a ata ainda não poder ser gerada, numa linha, ou None."""
    from app.services.conduta import voto

    caso = aberto.caso
    if aberto.pessoa.papel != "coordenacao":
        return "Só a coordenação gera a ata."
    if not situacao_do_voto.fechada:
        return "A ata sai dos votos registrados: faltam votos."
    apuracao = voto.apurar([voto._conteudo(v) for v in situacao_do_voto.da_rodada(situacao_do_voto.rodada)])
    if not apuracao.tem_maioria:
        return "Não houve maioria. A ata espera a nova rodada de voto."
    if _completo(caso) and not _transcricoes(supabase, caso["id"]):
        return "Anexe a transcrição da reunião do Comitê antes de gerar a ata."
    if ata_assinada(supabase, caso["id"]):
        return "A ata já foi assinada pelos três."
    return None


def _ata_da_versao(versao: dict) -> dict[str, Any]:
    ata = json.loads(cifra.decifrar_texto(versao["ata_cifrada"]))
    pontos = json.loads(cifra.decifrar_texto(versao["pontos_cifrados"])) if versao.get("pontos_cifrados") else []
    return {**ata, "versao": versao["versao"], "pontos": {"rotulo": "Sugestão", "itens": pontos}}


def _eliminar_se_falta(supabase, caso: dict) -> None:
    if caso.get("reuniao_concluida_em") and _transcricoes(supabase, caso["id"]):
        eliminar_transcricao_da_reuniao(supabase, caso)


def para_a_tela(supabase, aberto: CasoAberto, situacao_do_voto) -> dict:
    """A ata e, no rito Completo, a reunião do Comitê, para quem abre o caso."""
    caso = aberto.caso
    em_voto = caso.get("etapa") == "voto" and not caso.get("resultado") and not caso.get("encerrado_em")
    coordena = aberto.pessoa.papel == "coordenacao"
    versoes = _versoes(supabase, caso["id"])
    ata = None
    if versoes:
        ultima = versoes[-1]
        ata = _ata_da_versao(ultima)
        assinatura = _assinatura_da_versao(supabase, caso["id"], ultima["id"])
        ata["assinatura"] = (
            {
                "situacao": assinatura["situacao"],
                "erro": assinatura.get("erro"),
                "assinado_em": assinatura.get("assinado_em"),
                "tem_copia": bool(assinatura.get("arquivo_assinado_path")),
            }
            if assinatura
            else None
        )
    bloqueio = bloqueio_da_geracao(supabase, aberto, situacao_do_voto) if em_voto else None
    assinada = ata_assinada(supabase, caso["id"])
    saida: dict[str, Any] = {
        "ata": {
            "documento": ata,
            "pode_gerar": em_voto and bloqueio is None,
            "bloqueio_da_geracao": bloqueio,
            "pode_enviar": em_voto and coordena and ata is not None and not assinada,
        },
        "reuniao": None,
    }
    if _completo(caso):
        _eliminar_se_falta(supabase, caso)
        transcricoes = _transcricoes(supabase, caso["id"])
        marcas = _marcas(supabase, caso["id"])
        nomes = membros.nomes(
            supabase,
            sorted(
                {t["enviado_por"] for t in transcricoes}
                | {m["marcado_por"] for m in marcas}
                | ({caso["reuniao_concluida_por"]} if caso.get("reuniao_concluida_por") else set())
            ),
        )
        lista = lista_da_reuniao(supabase, caso, nomes)
        aberta = em_voto and not caso.get("reuniao_concluida_em")
        falta = _bloqueio_da_lista(lista)
        saida["reuniao"] = {
            "transcricoes": [
                {"versao": t["versao"], "enviado_em": t["enviado_em"], "enviado_por": nomes.get(t["enviado_por"], "")}
                for t in reversed(transcricoes)
            ],
            "lista": lista,
            "pode_anexar": aberta and coordena,
            "pode_marcar": aberta and coordena,
            "pode_concluir": aberta and coordena and falta is None,
            "bloqueio_da_conclusao": (falta if coordena else "Só a coordenação conclui a reunião.") if aberta else None,
            "concluida_em": caso.get("reuniao_concluida_em"),
            "concluida_por": nomes.get(caso.get("reuniao_concluida_por") or "", "") or None,
            "transcricao_eliminada_em": caso.get("transcricao_eliminada_em"),
        }
    return saida


# ── A reunião do Comitê (rito Completo) ─────────────────────────────────────


def _exigir_voto(caso: dict) -> None:
    if caso.get("etapa") != "voto" or caso.get("encerrado_em") or caso.get("resultado"):
        raise AtaRecusadaError(409, "A ata e a reunião do Comitê são da etapa Voto.")


def _exigir_coordenacao(aberto: CasoAberto, mensagem: str) -> None:
    if aberto.pessoa.papel != "coordenacao":
        raise AtaRecusadaError(403, mensagem)


def _exigir_reuniao_aberta(aberto: CasoAberto) -> None:
    caso = aberto.caso
    _exigir_voto(caso)
    if not _completo(caso):
        raise AtaRecusadaError(409, "No rito Rápido não há reunião do Comitê.")
    if caso.get("reuniao_concluida_em"):
        raise AtaRecusadaError(409, "A reunião do Comitê já foi concluída.")
    _exigir_coordenacao(aberto, "Só a coordenação cuida da reunião do Comitê.")


def conferir_transcricao(nome: str, tamanho: int) -> str:
    """O content-type pela extensão (nunca pelo que o navegador declarou)."""
    nome = (nome or "").strip()
    extensao = nome[nome.rfind(".") :].lower() if "." in nome else ""
    if extensao not in CONTENT_TYPES_DA_TRANSCRICAO:
        raise AtaRecusadaError(422, RECUSA_DA_TRANSCRICAO)
    if tamanho <= 0:
        raise AtaRecusadaError(422, "O arquivo está vazio.")
    if tamanho > LIMITE_DA_TRANSCRICAO:
        raise AtaRecusadaError(413, f"O arquivo passa de {LIMITE_DA_TRANSCRICAO // _MB} MB.")
    return CONTENT_TYPES_DA_TRANSCRICAO[extensao]


def anexar_transcricao_da_reuniao(supabase, aberto: CasoAberto, nome: str, conteudo: bytes) -> dict:
    """ANEXAR TRANSCRIÇÃO DA REUNIÃO DO COMITÊ: cifrada no bucket do Canal.
    Uma versão nova não apaga a anterior até a reunião ser concluída."""
    _exigir_reuniao_aberta(aberto)
    caso = aberto.caso
    content_type = conferir_transcricao(nome, len(conteudo))
    cifrado = cifra.cifrar_arquivo(conteudo)
    versao = max((t["versao"] for t in _transcricoes(supabase, caso["id"])), default=0) + 1
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "anexou_arquivo",
        f"anexou a transcrição da reunião do Comitê, versão {versao}",
    )
    caminho = f"reunioes/{uuid.uuid4().hex}"
    if not storage.upload_private(supabase, BUCKET, caminho, cifrado):
        raise AtaRecusadaError(503, "O arquivo não foi guardado. Tente de novo.")
    try:
        supabase.table(TRANSCRICOES).insert(
            {
                "caso_id": caso["id"],
                "versao": versao,
                "storage_path": caminho,
                "content_type": content_type,
                "tamanho_bytes": len(conteudo),
                "enviado_por": aberto.autor_id,
                "enviado_em": agora_utc().isoformat(),
            }
        ).execute()
    except APIError:
        if not storage.delete_file(supabase, BUCKET, caminho):
            logger.error("Transcrição da reunião órfã no bucket do Canal: %s", caminho)
        raise
    return {"versao": versao}


def marcar_item_da_reuniao(supabase, aberto: CasoAberto, item: str) -> None:
    """A declaração da coordenação, com quem marcou e quando. Não se desfaz."""
    if item not in DECLARACOES:
        raise AtaRecusadaError(422, "Este item é marcado sozinho pelo aplicativo.")
    _exigir_reuniao_aberta(aberto)
    caso = aberto.caso
    if any(m["item"] == item for m in _marcas(supabase, caso["id"])):
        raise AtaRecusadaError(409, "Este item já foi marcado.")
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "declarou_item_da_reuniao", f"declarou: {DECLARACOES[item]}"
    )
    try:
        supabase.table(CONFERENCIA).insert(
            {"caso_id": caso["id"], "item": item, "marcado_por": aberto.autor_id, "marcado_em": agora_utc().isoformat()}
        ).execute()
    except APIError as erro:
        if getattr(erro, "code", None) == "23505":
            raise AtaRecusadaError(409, "Este item já foi marcado.") from erro
        raise


def eliminar_transcricao_da_reuniao(supabase, caso: dict) -> None:
    """Concluída a reunião, a transcrição sai do bucket e do banco, e a
    eliminação fica na trilha. Pode rodar de novo: o que o bucket não apagou
    fica na tabela para a próxima vez, e a trilha não repete."""
    transcricoes = _transcricoes(supabase, caso["id"])
    if not transcricoes:
        return
    ja = (
        supabase.table("conduta_trilha")
        .select("seq")
        .eq("caso_id", caso["id"])
        .eq("acao", "eliminou_transcricao")
        .limit(1)
        .execute()
        .data
    )
    if not ja:
        trilha.registrar(
            supabase,
            caso["id"],
            None,
            "eliminou_transcricao",
            f"transcrição da reunião do Comitê eliminada do banco e do bucket ({len(transcricoes)} versão(ões))",
        )
    sobrou = False
    for transcricao in transcricoes:
        if not storage.delete_file(supabase, BUCKET, transcricao["storage_path"]):
            logger.error("Transcrição da reunião não saiu do bucket do Canal: %s", transcricao["storage_path"])
            sobrou = True
            continue
        supabase.table(TRANSCRICOES).delete().eq("id", transcricao["id"]).execute()
    if not sobrou:
        agora = agora_utc().isoformat()
        supabase.table("conduta_casos").update({"transcricao_eliminada_em": agora}).eq("id", caso["id"]).execute()
        caso["transcricao_eliminada_em"] = agora


def concluir_reuniao(supabase, aberto: CasoAberto) -> dict:
    """CONCLUIR REUNIÃO: só com os quatro itens. Concluída, a transcrição é
    eliminada."""
    _exigir_reuniao_aberta(aberto)
    caso = aberto.caso
    falta = _bloqueio_da_lista(lista_da_reuniao(supabase, caso))
    if falta:
        raise AtaRecusadaError(409, falta)
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "concluiu_reuniao", "concluiu a reunião do Comitê")
    agora = agora_utc().isoformat()
    linhas = (
        supabase.table("conduta_casos")
        .update({"reuniao_concluida_em": agora, "reuniao_concluida_por": aberto.autor_id})
        .eq("id", caso["id"])
        .is_("reuniao_concluida_em", "null")
        .execute()
        .data
    ) or []
    if not linhas:
        raise AtaRecusadaError(409, "O caso mudou enquanto você agia. Abra de novo.")
    caso.update({"reuniao_concluida_em": agora, "reuniao_concluida_por": aberto.autor_id})
    eliminar_transcricao_da_reuniao(supabase, caso)
    return linhas[0]


# ── O agente (Anexo D) ──────────────────────────────────────────────────────


def _texto_da_transcricao(supabase, transcricao: dict) -> str:
    from app.services.transcricao_extractor import extrair_texto

    cifrado = storage.download_file(supabase, BUCKET, transcricao["storage_path"])
    if cifrado is None:
        raise AtaRecusadaError(503, "A transcrição não pôde ser aberta agora. Tente de novo.")
    conteudo = cifra.decifrar_arquivo(cifrado)
    if transcricao["content_type"].startswith("text/"):
        return conteudo.decode("utf-8", errors="replace").strip()
    extensao = ".pdf" if transcricao["content_type"] == "application/pdf" else ".docx"
    try:
        return extrair_texto(f"transcricao{extensao}", conteudo)[0]
    except ValueError as erro:
        raise AtaRecusadaError(422, f"A transcrição não pôde ser lida: {erro}") from erro


def _rotulo_do_voto(conteudo: dict) -> tuple[str, str | None]:
    from app.services.conduta import voto

    return voto.RESULTADOS[conteudo["resultado"]], voto._rotulo_da_medida(
        conteudo.get("medida"), conteudo.get("dias_de_suspensao")
    )


def _parte_do_aplicativo(supabase, caso: dict, situacao_do_voto) -> dict[str, Any]:
    """O que a ata diz e o agente não escreve: quem estava, a deliberação, a
    medida e cada voto, como foram registrados no aplicativo."""
    from app.services.conduta import voto

    votos = situacao_do_voto.da_rodada(situacao_do_voto.rodada)
    conteudos = [voto._conteudo(v) for v in votos]
    apuracao = voto.apurar(conteudos)
    atribuicoes = supabase.table("conduta_atribuicoes").select("*").eq("caso_id", caso["id"]).execute().data or []
    impedidos = [a["participante_id"] for a in atribuicoes if a.get("impedido_em")]
    suplentes = [
        a["participante_id"]
        for a in atribuicoes
        if a.get("motivo") == "suplente_convocado"
        and not a.get("revogada_em")
        and a["participante_id"] in situacao_do_voto.votantes
    ]
    nomes = membros.nomes(supabase, sorted(set(situacao_do_voto.votantes) | set(impedidos) | set(suplentes)))
    unanime = len({c["resultado"] for c in conteudos}) == 1
    registrados = []
    for linha, conteudo in zip(votos, conteudos, strict=True):
        resultado, medida = _rotulo_do_voto(conteudo)
        registrados.append(
            {
                "membro": nomes.get(linha["participante_id"], ""),
                "resultado": resultado,
                "medida": medida,
                "justificativa": conteudo["justificativa"],
            }
        )
    return {
        "identificacao": {
            "rito": RITOS.get(caso.get("rito") or "", caso.get("rito") or ""),
            "data": hoje_em_sao_paulo().strftime("%d/%m/%Y"),
            "presentes": [
                nomes.get(pid, "") for pid in sorted(situacao_do_voto.votantes, key=lambda p: nomes.get(p, ""))
            ],
            "impedimentos": [nomes.get(pid, "") for pid in impedidos],
            "suplentes": [nomes.get(pid, "") for pid in suplentes],
        },
        "deliberacao": f"{voto.RESULTADOS[apuracao.resultado]}, {'por unanimidade' if unanime else 'por maioria'}",
        "medida": voto._rotulo_da_medida(apuracao.medida, apuracao.dias_de_suspensao),
        "votos": registrados,
    }


def _mensagem_da_ata(
    supabase, caso: dict, situacao_do_voto, parte: dict, transcricao: str | None, marcacao: Marcacao
) -> str:
    from app.services.conduta import termo_de_declaracao, trava

    nomes = termo_de_declaracao._nomes_do_caso(supabase, caso)
    nomes += [n for n in parte["identificacao"]["presentes"] + parte["identificacao"]["suplentes"] if n]

    def marcar(texto: str) -> str:
        return marcacao.marcar(texto, nomes)

    ident = parte["identificacao"]
    partes = [
        f"Rito: {ident['rito']}.",
        f"Membros votantes presentes: {', '.join(marcar(n) for n in ident['presentes'])}.",
    ]
    versoes = relatorio._versoes(supabase, caso["id"], "relatorio")
    if versoes:
        texto = cifra.decifrar_texto(versoes[-1]["texto_cifrado"])[:_TAMANHO_DO_MATERIAL]
        partes.append(f"<relatorio_de_apuracao>\n{marcar(texto)}\n</relatorio_de_apuracao>")
    votos = [
        f'<voto membro="{marcar(v["membro"])}" resultado="{v["resultado"]}" medida="{v["medida"] or "sem medida"}">\n'
        f"{marcar(v['justificativa'])}\n</voto>"
        for v in parte["votos"]
    ]
    partes.append(
        "<votos_registrados_no_aplicativo>\n"
        + "\n".join(votos)
        + f"\nDeliberação pelos votos registrados: {parte['deliberacao']}."
        + (f"\nMedida da maioria: {parte['medida']}." if parte["medida"] else "")
        + "\n</votos_registrados_no_aplicativo>"
    )
    por_item, acusado_ouvido = trava._situacao_dos_itens(supabase, caso, situacao_do_voto)
    situacao_da_trava = []
    for item, rotulo in trava.ITENS:
        confirmado = len(por_item[item]) >= trava._confirmacoes_precisas(item, acusado_ouvido)
        situacao_da_trava.append(f"- {rotulo}: {'confirmado' if confirmado else 'em aberto'}")
    partes.append("<trava_de_robustez>\n" + "\n".join(situacao_da_trava) + "\n</trava_de_robustez>")
    if transcricao is None:
        partes.append("Não houve reunião: o rito é Rápido. A ata sai do relatório de apuração e dos votos.")
    else:
        partes.append(
            f"<transcricao_da_reuniao>\n{marcar(transcricao[:_TAMANHO_DO_MATERIAL])}\n</transcricao_da_reuniao>"
        )
    return "\n\n".join(partes)


def _cliente_do_agente_da_ata() -> ClienteDaAnthropic:
    return ClienteDaAnthropic(max_retries=0, timeout=TEMPO_LIMITE_S)


def _pedir_ao_agente_da_ata(cliente, sistema: str, mensagem: str) -> str | None:
    """Uma chamada ao modelo. None quando ele recusa ou corta no teto."""
    resposta = cliente.messages.create(
        model=settings.conduta_agente_modelo,
        max_tokens=MAX_TOKENS,
        system=sistema,
        messages=[{"role": "user", "content": mensagem}],
    )
    if resposta.stop_reason in ("refusal", "max_tokens"):
        return None
    return "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()


def _texto(valor: Any, marcacao: Marcacao) -> str:
    return marcacao.devolver(" ".join(str(valor or "").split()))[:_TAMANHO_DO_TEXTO]


def _lista(valor: Any, marcacao: Marcacao) -> list[str]:
    if not isinstance(valor, list):
        return []
    return [_texto(item, marcacao) for item in valor if isinstance(item, str) and item.strip()][:_ITENS]


def _parte_do_agente_da_ata(bruto: str, marcacao: Marcacao) -> tuple[dict[str, Any], list[str]]:
    """O que o agente escreve, com os nomes de volta. Qualquer outra chave que
    ele devolva (um resultado, um voto) é ignorada: a decisão é do aplicativo."""
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    objeto = json.loads(bruto[inicio : fim + 1] if 0 <= inicio < fim else bruto)
    if not isinstance(objeto, dict):
        raise ValueError("a resposta não é um objeto")
    escrito = {
        "resumo": _texto(objeto.get("resumo"), marcacao),
        "provas": _lista(objeto.get("provas"), marcacao),
        "defesa": _texto(objeto.get("defesa"), marcacao),
        "fundamentos": _texto(objeto.get("fundamentos"), marcacao),
        "correcao": _lista(objeto.get("correcao"), marcacao),
        "encaminhamentos": _lista(objeto.get("encaminhamentos"), marcacao),
    }
    if not escrito["resumo"] or not escrito["fundamentos"]:
        raise ValueError("a resposta veio sem resumo ou sem fundamentos")
    return escrito, _lista(objeto.get("pontos_a_confirmar"), marcacao)


def gerar_ata_de_deliberacao(supabase, aberto: CasoAberto) -> dict:
    """GERAR ATA: o agente do Anexo D redige, e a ata entra como versão nova.
    Roda no executor da IA."""
    from app.services.conduta import voto

    caso = aberto.caso
    _exigir_voto(caso)
    atual = voto.situacao_em_dia(supabase, caso)
    bloqueio = bloqueio_da_geracao(supabase, aberto, atual)
    if bloqueio:
        raise AtaRecusadaError(403 if aberto.pessoa.papel != "coordenacao" else 409, bloqueio)
    if not settings.anthropic_api_key:
        raise AtaRecusadaError(503, "O agente está fora do ar agora. Tente de novo em instantes.")
    parte = _parte_do_aplicativo(supabase, caso, atual)
    transcricao = _texto_da_transcricao(supabase, _transcricoes(supabase, caso["id"])[-1]) if _completo(caso) else None
    marcacao = Marcacao()
    mensagem = _mensagem_da_ata(supabase, caso, atual, parte, transcricao, marcacao)
    try:
        bruto = _pedir_ao_agente_da_ata(_cliente_do_agente_da_ata(), load_prompt(PROMPT_DA_ATA), mensagem)
    except Exception as exc:  # noqa: BLE001 (o erro da API vira a recusa da tela)
        logger.warning("[Conduta] Agente da ata não respondeu (%s)", type(exc).__name__)
        raise AtaRecusadaError(503, "O agente não respondeu. Tente de novo em instantes.") from exc
    try:
        escrito, pontos = _parte_do_agente_da_ata(bruto or "", marcacao)
    except (ValueError, KeyError, TypeError) as exc:
        raise AtaRecusadaError(502, "O agente não devolveu a ata. Gere de novo.") from exc
    ata = sanitizar_estrutura({**parte, **escrito})
    pontos = sanitizar_estrutura(pontos)
    versao = max((v["versao"] for v in _versoes(supabase, caso["id"])), default=0) + 1
    ata_cifrada = cifra.cifrar_texto(json.dumps(ata, ensure_ascii=False))
    pontos_cifrados = cifra.cifrar_texto(json.dumps(pontos, ensure_ascii=False)) if pontos else None
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "gerou_ata", f"ata de deliberação, versão {versao}, pelo agente"
    )
    try:
        return (
            supabase.table(ATAS)
            .insert(
                {
                    "caso_id": caso["id"],
                    "versao": versao,
                    "rodada": atual.rodada,
                    "ata_cifrada": ata_cifrada,
                    "pontos_cifrados": pontos_cifrados,
                    "autor_id": aberto.autor_id,
                    "criado_em": agora_utc().isoformat(),
                }
            )
            .execute()
            .data[0]
        )
    except APIError as erro:
        if getattr(erro, "code", None) == "23505":
            raise AtaRecusadaError(409, "A ata mudou enquanto você agia. Abra de novo.") from erro
        raise


# ── A assinatura dos três votantes ──────────────────────────────────────────


def enviar_para_assinatura(supabase, aberto: CasoAberto) -> dict:
    """A última versão da ata vai à ClickSign para os três votantes."""
    from app.services.conduta import voto

    caso = aberto.caso
    _exigir_voto(caso)
    _exigir_coordenacao(aberto, "Só a coordenação envia a ata para assinatura.")
    versoes = _versoes(supabase, caso["id"])
    if not versoes:
        raise AtaRecusadaError(409, "Gere a ata antes de enviar para assinatura.")
    if ata_assinada(supabase, caso["id"]):
        raise AtaRecusadaError(409, "A ata já foi assinada pelos três.")
    votantes = voto.situacao(supabase, caso).votantes
    if len(votantes) < voto.VOTANTES:
        raise AtaRecusadaError(409, "Falta membro votante no caso: o impedido ainda não tem suplente.")
    pessoas = (
        supabase.table("participantes").select("id, nome_completo, email").in_("id", sorted(votantes)).execute().data
    ) or []
    if len(pessoas) != len(votantes) or not all(p.get("email") for p in pessoas):
        raise AtaRecusadaError(
            409, "Um votante não tem e-mail profissional no cadastro, e a ata vai por e-mail para assinatura."
        )
    ultima = versoes[-1]
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "enviou_ata_para_assinatura",
        f"ata de deliberação, versão {ultima['versao']}, aos três votantes",
    )
    return assinaturas.enviar_ata_de_deliberacao(
        supabase, caso["id"], ultima, json.loads(cifra.decifrar_texto(ultima["ata_cifrada"])), pessoas
    )


def assinatura_aberta(supabase, aberto: CasoAberto) -> dict:
    """O envio à ClickSign que espera assinatura, para o "Reconsultar status"."""
    abertas = [a for a in _assinaturas_da_ata(supabase, aberto.caso["id"]) if a["situacao"] == "enviado"]
    if not abertas:
        raise AtaRecusadaError(404, "Não há ata esperando assinatura.")
    return abertas[-1]


def abrir_assinada(supabase, aberto: CasoAberto) -> bytes:
    """A cópia do PDF assinado da última versão, decifrada, depois de gravada
    a abertura."""
    caso_id = aberto.caso["id"]
    versoes = _versoes(supabase, caso_id)
    assinatura = _assinatura_da_versao(supabase, caso_id, versoes[-1]["id"]) if versoes else None
    if not assinatura or assinatura["situacao"] != "assinado" or not assinatura.get("arquivo_assinado_path"):
        raise AtaRecusadaError(404, "A ata assinada ainda não voltou.")
    trilha.registrar(supabase, caso_id, aberto.autor_id, "abriu_arquivo", "abriu a ata assinada")
    cifrado = storage.download_file(supabase, assinaturas.BUCKET, assinatura["arquivo_assinado_path"])
    if cifrado is None:
        raise AtaRecusadaError(503, "O arquivo não pôde ser aberto agora. Tente de novo.")
    return cifra.decifrar_arquivo(cifrado)
