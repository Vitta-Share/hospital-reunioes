"""A Recomendação do Comitê e a decisão da medida (issue #1835; especificação,
6.3 e 6.8; decisões 8, 9, 10, 15 e 32 do diretor).

Concluída a votação de um caso procedente ou parcialmente procedente, a
coordenação toca em "ENVIAR À DIREÇÃO". A Recomendação do Comitê (a página de
conclusão e a ata assinada) fica liberada para duas pessoas com perfil nominal
do módulo: o Presidente, que só lê, e a diretoria executiva, que lê e registra
a decisão do Presidente: Aplicada, Aplicada com ajuste ou Não aplicada, com a
data e, nas duas últimas, a justificativa. Nenhuma das duas abre o caso: o
relato, os depoimentos, os votos da tela e o Dossiê do caso ficam no portão do
Comitê, que as recusa. Cada leitura entra na trilha.

A execução da medida é do DP, fora do módulo. A diretoria anexa a cópia da
comunicação da medida, que fica cifrada no bucket do Canal e entra na trilha.
Improcedente e inconclusivo nunca saem do Comitê. O banco tem as mesmas
travas (migration 222).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date
from typing import Any

from postgrest.exceptions import APIError

from app.services import storage
from app.services.conduta import assinaturas, cifra, depoimentos, relatorio, trilha
from app.services.conduta.acesso import (
    DIRETORIA_EXECUTIVA,
    PRESIDENTE,
    RESULTADOS_QUE_VAO_A_DIRECAO,
    recomendacoes_da_direcao,
)
from app.services.conduta.portao import CasoAberto, RecomendacaoAberta
from app.services.conduta.ritos import CATEGORIAS, agora_utc

logger = logging.getLogger(__name__)

DECISOES_DA_MEDIDA = "conduta_decisoes_da_medida"
COMUNICACOES_DA_MEDIDA = "conduta_comunicacoes_da_medida"
BUCKET = depoimentos.BUCKET

DECISOES = {
    "aplicada": "Aplicada",
    "aplicada_com_ajuste": "Aplicada com ajuste",
    "nao_aplicada": "Não aplicada",
}
COM_JUSTIFICATIVA = ("aplicada_com_ajuste", "nao_aplicada")
QUE_APLICAM = ("aplicada", "aplicada_com_ajuste")
TAMANHO_DA_JUSTIFICATIVA = 2000
QUEM_LE = {PRESIDENTE: "o Presidente", DIRETORIA_EXECUTIVA: "a diretoria executiva"}
RITOS = {"rapido": "Rápido", "completo": "Completo"}

_MB = 1024 * 1024
LIMITE_DA_COMUNICACAO = 20 * _MB
CONTENT_TYPES_DA_COMUNICACAO = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class DirecaoRecusadaError(Exception):
    """A ação não pode acontecer agora. `status` vai para a resposta, e a
    mensagem diz o motivo numa linha."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ── ENVIAR À DIREÇÃO (o lado do Comitê) ────────────────────────────────────


def bloqueio_do_envio(aberto: CasoAberto) -> str | None:
    caso = aberto.caso
    if caso.get("etapa") != "ata" or caso.get("encerrado_em") or caso.get("rota") != "comum":
        return "O caso vai à Direção depois de concluída a votação."
    if caso.get("resultado") not in RESULTADOS_QUE_VAO_A_DIRECAO:
        return "Caso improcedente ou inconclusivo não sai do Comitê."
    if aberto.pessoa.papel != "coordenacao":
        return "Só a coordenação envia à Direção."
    return None


def enviar_a_direcao(supabase, aberto: CasoAberto) -> dict:
    """Libera a Recomendação do Comitê ao Presidente e à diretoria executiva e
    leva o caso à etapa Medida."""
    bloqueio = bloqueio_do_envio(aberto)
    if bloqueio:
        raise DirecaoRecusadaError(403 if aberto.pessoa.papel != "coordenacao" else 409, bloqueio)
    caso = aberto.caso
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "enviou_a_direcao", "enviou a Recomendação do Comitê à Direção"
    )
    linhas = (
        supabase.table("conduta_casos")
        .update(
            {
                "enviado_a_direcao_em": agora_utc().isoformat(),
                "enviado_a_direcao_por": aberto.autor_id,
                "etapa": "medida",
            }
        )
        .eq("id", caso["id"])
        .eq("etapa", "ata")
        .execute()
        .data
    ) or []
    if not linhas:
        raise DirecaoRecusadaError(409, "O caso mudou enquanto você agia. Abra de novo.")
    return linhas[0]


# ── A decisão e a comunicação ───────────────────────────────────────────────


def decisao_do_caso(supabase, caso_id: str) -> dict | None:
    linhas = supabase.table(DECISOES_DA_MEDIDA).select("*").eq("caso_id", caso_id).limit(1).execute().data or []
    return linhas[0] if linhas else None


def _comunicacoes(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(COMUNICACOES_DA_MEDIDA).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda c: c["versao"])


def _vista_da_decisao(decisao: dict | None) -> dict | None:
    if not decisao:
        return None
    return {
        "decisao": DECISOES[decisao["decisao"]],
        "codigo": decisao["decisao"],
        "justificativa": cifra.decifrar_texto(decisao["justificativa_cifrada"])
        if decisao.get("justificativa_cifrada")
        else None,
        "decidida_em": decisao["decidida_em"],
        "registrada_em": decisao.get("registrada_em"),
    }


def para_o_comite(supabase, caso: dict) -> dict[str, Any]:
    """O que a tela do caso mostra da Direção: o envio, a decisão e a cópia da
    comunicação da medida."""
    comunicacoes = _comunicacoes(supabase, caso["id"])
    return {
        "enviado_a_direcao_em": caso.get("enviado_a_direcao_em"),
        "decisao": _vista_da_decisao(decisao_do_caso(supabase, caso["id"])),
        "comunicacoes": [{"versao": c["versao"], "enviado_em": c["enviado_em"]} for c in reversed(comunicacoes)],
    }


def erro_da_decisao(decisao: str, justificativa: str, decidida_em: date, hoje: date) -> str | None:
    """O que está errado na decisão, numa linha, ou None."""
    if decisao not in DECISOES:
        return "Escolha a decisão: Aplicada, Aplicada com ajuste ou Não aplicada."
    if decisao in COM_JUSTIFICATIVA and not justificativa.strip():
        return f"{DECISOES[decisao]} exige justificativa."
    if len(justificativa) > TAMANHO_DA_JUSTIFICATIVA:
        return f"A justificativa cabe em {TAMANHO_DA_JUSTIFICATIVA} caracteres."
    if decidida_em > hoje:
        return "A data da decisão não pode ser futura."
    return None


def _exigir_diretoria(aberta: RecomendacaoAberta, o_que: str) -> None:
    if aberta.perfil != DIRETORIA_EXECUTIVA:
        raise DirecaoRecusadaError(403, f"Só a diretoria executiva {o_que}. O Presidente só lê.")


def registrar_decisao(
    supabase, aberta: RecomendacaoAberta, *, decisao: str, justificativa: str, decidida_em: date, hoje: date
) -> dict:
    """A diretoria executiva registra a decisão do Presidente sobre a medida, e
    o caso segue ao Retorno. Uma vez só."""
    _exigir_diretoria(aberta, "registra a decisão")
    caso = aberta.caso
    if decisao_do_caso(supabase, caso["id"]):
        raise DirecaoRecusadaError(409, "A decisão sobre a medida já foi registrada.")
    if caso.get("etapa") != "medida":
        raise DirecaoRecusadaError(409, "O caso não está esperando a decisão da medida.")
    erro = erro_da_decisao(decisao, justificativa, decidida_em, hoje)
    if erro:
        raise DirecaoRecusadaError(422, erro)
    justificativa = justificativa.strip()
    trilha.registrar(
        supabase,
        caso["id"],
        aberta.autor_id,
        "registrou_decisao_da_medida",
        f"decisão da medida: {DECISOES[decisao]}, de {decidida_em.strftime('%d/%m/%Y')}",
    )
    try:
        linha = (
            supabase.table(DECISOES_DA_MEDIDA)
            .insert(
                {
                    "caso_id": caso["id"],
                    "decisao": decisao,
                    "justificativa_cifrada": cifra.cifrar_texto(justificativa) if justificativa else None,
                    "decidida_em": decidida_em.isoformat(),
                    "registrada_por": aberta.autor_id,
                    "registrada_em": agora_utc().isoformat(),
                }
            )
            .execute()
            .data[0]
        )
    except APIError as erro_do_banco:
        if getattr(erro_do_banco, "code", None) == "23505":
            raise DirecaoRecusadaError(409, "A decisão sobre a medida já foi registrada.") from erro_do_banco
        raise
    supabase.table("conduta_casos").update({"etapa": "retorno"}).eq("id", caso["id"]).eq("etapa", "medida").execute()
    return linha


def conferir_comunicacao(nome: str, tamanho: int) -> str:
    """O content-type pela extensão (nunca pelo que o navegador declarou)."""
    nome = (nome or "").strip()
    extensao = nome[nome.rfind(".") :].lower() if "." in nome else ""
    if extensao not in CONTENT_TYPES_DA_COMUNICACAO:
        raise DirecaoRecusadaError(422, "Envie a cópia da comunicação em PDF, JPG ou PNG.")
    if tamanho <= 0:
        raise DirecaoRecusadaError(422, "O arquivo está vazio.")
    if tamanho > LIMITE_DA_COMUNICACAO:
        raise DirecaoRecusadaError(413, f"O arquivo passa de {LIMITE_DA_COMUNICACAO // _MB} MB.")
    return CONTENT_TYPES_DA_COMUNICACAO[extensao]


def anexar_comunicacao(supabase, aberta: RecomendacaoAberta, nome: str, conteudo: bytes) -> dict:
    """A cópia da comunicação da medida que o DP fez, cifrada no bucket do
    Canal, em versão nova. Só depois de uma decisão que aplica a medida."""
    _exigir_diretoria(aberta, "anexa a comunicação da medida")
    caso = aberta.caso
    decisao = decisao_do_caso(supabase, caso["id"])
    if not decisao or decisao["decisao"] not in QUE_APLICAM:
        raise DirecaoRecusadaError(409, "A comunicação da medida vem depois da decisão que aplica a medida.")
    content_type = conferir_comunicacao(nome, len(conteudo))
    versao = max((c["versao"] for c in _comunicacoes(supabase, caso["id"])), default=0) + 1
    trilha.registrar(
        supabase,
        caso["id"],
        aberta.autor_id,
        "anexou_arquivo",
        f"anexou a cópia da comunicação da medida, versão {versao}",
    )
    caminho = f"medida/{uuid.uuid4().hex}"
    if not storage.upload_private(supabase, BUCKET, caminho, cifra.cifrar_arquivo(conteudo)):
        raise DirecaoRecusadaError(503, "O arquivo não foi guardado. Tente de novo.")
    try:
        supabase.table(COMUNICACOES_DA_MEDIDA).insert(
            {
                "caso_id": caso["id"],
                "versao": versao,
                "storage_path": caminho,
                "content_type": content_type,
                "tamanho_bytes": len(conteudo),
                "enviado_por": aberta.autor_id,
                "enviado_em": agora_utc().isoformat(),
            }
        ).execute()
    except APIError:
        if not storage.delete_file(supabase, BUCKET, caminho):
            logger.error("Comunicação da medida órfã no bucket do Canal: %s", caminho)
        raise
    return {"versao": versao}


def abrir_comunicacao(supabase, caso_id: str, autor_id: str) -> tuple[bytes, str]:
    """A última cópia da comunicação da medida, decifrada, depois de gravada a
    abertura."""
    comunicacoes = _comunicacoes(supabase, caso_id)
    if not comunicacoes:
        raise DirecaoRecusadaError(404, "A cópia da comunicação da medida ainda não foi anexada.")
    ultima = comunicacoes[-1]
    trilha.registrar(supabase, caso_id, autor_id, "abriu_arquivo", "abriu a cópia da comunicação da medida")
    cifrado = storage.download_file(supabase, BUCKET, ultima["storage_path"])
    if cifrado is None:
        raise DirecaoRecusadaError(503, "O arquivo não pôde ser aberto agora. Tente de novo.")
    return cifra.decifrar_arquivo(cifrado), ultima["content_type"]


# ── A Recomendação do Comitê (o lado da Direção) ───────────────────────────


def lista_da_direcao(supabase, autor_id: str) -> list[dict[str, Any]]:
    casos = recomendacoes_da_direcao(supabase, autor_id)
    decisoes = {
        d["caso_id"]: d
        for d in (
            supabase.table(DECISOES_DA_MEDIDA)
            .select("caso_id, decisao")
            .in_("caso_id", [c["id"] for c in casos])
            .execute()
            .data
            if casos
            else []
        )
        or []
    }
    return [
        {
            "id": caso["id"],
            "protocolo": caso["protocolo"],
            "enviado_a_direcao_em": caso.get("enviado_a_direcao_em"),
            "decisao": DECISOES[decisoes[caso["id"]]["decisao"]] if caso["id"] in decisoes else None,
        }
        for caso in casos
    ]


def _medida_recomendada(caso: dict) -> str | None:
    from app.services.conduta import voto

    if not caso.get("medida_cifrada"):
        return None
    medida = json.loads(cifra.decifrar_texto(caso["medida_cifrada"]))
    return voto._rotulo_da_medida(medida.get("medida"), medida.get("dias_de_suspensao"))


def _ler(supabase, aberta: RecomendacaoAberta, o_que: str) -> None:
    trilha.registrar(supabase, aberta.caso["id"], aberta.autor_id, "leitura", f"{QUEM_LE[aberta.perfil]} {o_que}")


def ler_recomendacao(supabase, aberta: RecomendacaoAberta) -> dict[str, Any]:
    """A página de conclusão, depois de gravada a leitura na trilha. Leva o
    resultado, a medida recomendada e o relatório de uma página; nunca o
    relato, os depoimentos nem os votos de cada membro."""
    from app.services.conduta import voto

    caso = aberta.caso
    versoes = relatorio._versoes(supabase, caso["id"], "relatorio")
    pagina = {
        "id": caso["id"],
        "protocolo": caso["protocolo"],
        "rito": RITOS.get(caso.get("rito") or "", caso.get("rito") or ""),
        "categoria": CATEGORIAS.get(caso.get("categoria") or ""),
        "resultado": voto.RESULTADOS[caso["resultado"]],
        "medida_recomendada": _medida_recomendada(caso),
        "relatorio": cifra.decifrar_texto(versoes[-1]["texto_cifrado"]) if versoes else None,
        "votacao_concluida_em": caso.get("votacao_concluida_em"),
        "enviado_a_direcao_em": caso.get("enviado_a_direcao_em"),
        "tem_ata_assinada": _ata_assinada(supabase, caso["id"]) is not None,
        "decisao": _vista_da_decisao(decisao_do_caso(supabase, caso["id"])),
        "comunicacoes": [
            {"versao": c["versao"], "enviado_em": c["enviado_em"]}
            for c in reversed(_comunicacoes(supabase, caso["id"]))
        ],
        "pode_registrar": aberta.perfil == DIRETORIA_EXECUTIVA
        and caso.get("etapa") == "medida"
        and not decisao_do_caso(supabase, caso["id"]),
    }
    decisao = decisao_do_caso(supabase, caso["id"])
    pagina["pode_anexar_comunicacao"] = (
        aberta.perfil == DIRETORIA_EXECUTIVA and bool(decisao) and decisao["decisao"] in QUE_APLICAM
    )
    _ler(supabase, aberta, "leu a Recomendação do Comitê")
    return pagina


def _ata_assinada(supabase, caso_id: str) -> dict | None:
    """A assinatura da última versão da ata, com a cópia do PDF de volta."""
    atas = sorted(
        supabase.table("conduta_atas").select("*").eq("caso_id", caso_id).execute().data or [],
        key=lambda v: v["versao"],
    )
    if not atas:
        return None
    vivas = [
        a
        for a in supabase.table(assinaturas.TABELA)
        .select("*")
        .eq("tipo", assinaturas.ATA_DE_DELIBERACAO)
        .eq("caso_id", caso_id)
        .execute()
        .data
        or []
        if a.get("ata_id") == atas[-1]["id"] and a.get("situacao") == "assinado" and a.get("arquivo_assinado_path")
    ]
    return vivas[-1] if vivas else None


def abrir_ata_da_recomendacao(supabase, aberta: RecomendacaoAberta) -> bytes:
    """A ata assinada, decifrada, depois de gravada a leitura."""
    assinatura = _ata_assinada(supabase, aberta.caso["id"])
    if not assinatura:
        raise DirecaoRecusadaError(404, "A ata assinada ainda não voltou.")
    _ler(supabase, aberta, "abriu a ata assinada")
    cifrado = storage.download_file(supabase, assinaturas.BUCKET, assinatura["arquivo_assinado_path"])
    if cifrado is None:
        raise DirecaoRecusadaError(503, "O arquivo não pôde ser aberto agora. Tente de novo.")
    return cifra.decifrar_arquivo(cifrado)
