"""O Anexo da Demanda (issue #1061, PRD #1056, ADR 0069).

O print de tela que vem junto da Demanda e, desde a issue #1520, o documento
(.md, .txt, .pdf, .docx) e, desde a #1521, a planilha (.csv, .xlsx). Vive SO
no app e nunca vai para o GitHub: o repositorio e publico, e print ou documento
do hospital carrega nome de paciente, de colaborador, protocolo da Ouvidoria.

O print entra pelo bug do Assistente do app (issue #2275, ADR 0113, decisao
8); o chat da aba, que era a porta da ADR 0077, saiu na issue #2279. Um lugar
so decide o que se faz com ele:

- **anexar**: a imagem passa pela regra do print (formatos e teto, com as
  mesmas frases de recusa), sobe ao bucket privado com caminho sorteado e so
  depois ganha a linha no banco;
- **para quem desenvolve**: a rota de automacao entrega a URL assinada de vida
  curta ao agente que pega a issue (issue #1063);
- **apagar os vencidos**: o cron tira os binarios 30 dias depois de a Etapa
  chegar a Em producao, e na rodada seguinte quando ela e Nao sera feita (ADR
  0077, issue #1382). Fica o registro (nome, quem, quando) marcado apagado.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.services import storage
from app.services.assistente_tecnologia import (
    MOTIVO_IMAGEM_GRANDE,
    MOTIVO_TIPO_FORA_DA_LISTA,
    TIPOS_DE_ANEXO,
    TIPOS_DE_DOCUMENTO,
    motivo_documento_grande,
)
from app.services.tecnologia import ESTADOS_FECHADOS, instante_do_banco
from app.services.tecnologia_vinculo import ETAPA_EM_PRODUCAO, ETAPA_NAO_SERA_FEITA

logger = logging.getLogger(__name__)

TABELA_ANEXOS = "tecnologia_anexos"

# Ate dez por Demanda (ADR 0069, decisao 1), somando imagens e documentos
# (emenda de 09/11/2026). O mesmo teto vive no CHECK da coluna `ordem`
# (migration 115): contornar a API nao contorna o teto.
LIMITE_DE_ANEXOS = 10
MOTIVO_ANEXOS_DEMAIS = (
    f"Esta Demanda já tem {LIMITE_DE_ANEXOS} anexos, somando prints e documentos, o máximo por Demanda. "
    "Escolha os que mais ajudam, ou escreva o resto na conversa."
)
MOTIVO_ARQUIVO_VAZIO = "O arquivo chegou vazio: não há o que anexar. Escolha o arquivo de novo."
MOTIVO_DEMANDA_ENCERRADA = "Esta Demanda está encerrada: imagem só entra em Demanda aberta. Reabra antes de anexar."
MOTIVO_NAO_GUARDOU = "Não foi possível guardar a imagem agora. Tente de novo em instantes."

# Dez minutos: o script de quem desenvolve baixa o print logo depois de pedir.
# Link colado fora do app morre antes de virar acesso permanente ao print.
EXPIRACAO_DA_URL_SEGUNDOS = 600

# Em producao, o diretor ainda confere a correcao com o print na mao: o binario
# so sai 30 dias depois da subida (ADR 0077). O relogio e o `entregue_em`, que a
# subida reescreve com a data dela (`tecnologia_sincronizacao`).
PRAZO_DEPOIS_DE_EM_PRODUCAO = timedelta(days=30)


class AnexoRecusadoError(Exception):
    """A recusa, com a frase que a pessoa le e o status HTTP que a rota devolve."""

    def __init__(self, motivo: str, status_code: int = 422):
        super().__init__(motivo)
        self.status_code = status_code


def _bucket() -> str:
    return settings.supabase_storage_bucket_anexos_tecnologia


def anexar(supabase, *, demanda: dict, nome: str, conteudo: bytes, quem_id: str) -> dict:
    """Guarda a imagem junto da Demanda e devolve a linha gravada.

    O binario sobe ANTES da linha: sem binario nao existe anexo, e uma linha que
    aponta para o vazio quebraria o card. Se a linha nao entrar, o binario sai
    na hora, porque nada mais o alcancaria depois.

    Toda recusa vem antes do bucket: arquivo recusado nao deixa rastro.
    """
    if str(demanda.get("estado") or "") in ESTADOS_FECHADOS:
        # O apagamento so roda no ato de encerrar: binario que entrasse depois
        # ficaria no bucket para sempre, dado pessoal sem dono.
        raise AnexoRecusadoError(MOTIVO_DEMANDA_ENCERRADA)
    extensao = os.path.splitext(nome or "")[1].lower()
    tipo = TIPOS_DE_ANEXO.get(extensao)
    if tipo is None:
        raise AnexoRecusadoError(MOTIVO_TIPO_FORA_DA_LISTA)
    if not conteudo:
        raise AnexoRecusadoError(MOTIVO_ARQUIVO_VAZIO)
    if len(conteudo) > tipo.teto_bytes:
        motivo = MOTIVO_IMAGEM_GRANDE if tipo.classe == "imagem" else motivo_documento_grande(extensao)
        raise AnexoRecusadoError(motivo, status_code=413)

    demanda_id = str(demanda["id"])
    existentes = supabase.table(TABELA_ANEXOS).select("ordem").eq("demanda_id", demanda_id).execute().data or []
    # A posicao seguinte a MAIOR, e nao a contagem: as linhas nunca saem do
    # banco (o apagado fica como registro), entao as duas dao o mesmo, mas a
    # maior nao repete posicao se um dia faltar uma no meio.
    ordem = max((int(linha.get("ordem") or 0) for linha in existentes), default=0) + 1
    if ordem > LIMITE_DE_ANEXOS:
        raise AnexoRecusadoError(MOTIVO_ANEXOS_DEMAIS)

    # Caminho sorteado, como na Ouvidoria: o nome original pode carregar dado
    # pessoal ("prontuario do Joao.png") e nao vira parte de caminho.
    path = f"demanda-{demanda_id}/{uuid.uuid4().hex}{extensao}"
    content_type = tipo.content_type
    if not storage.upload_private(supabase, bucket=_bucket(), path=path, content=conteudo, content_type=content_type):
        raise AnexoRecusadoError(MOTIVO_NAO_GUARDOU, status_code=503)

    linha = {
        "demanda_id": demanda_id,
        "ordem": ordem,
        "storage_path": path,
        "nome_original": nome,
        "content_type": content_type,
        "tamanho_bytes": len(conteudo),
        "anexado_por": quem_id,
        "apagado_em": None,
    }
    try:
        return supabase.table(TABELA_ANEXOS).insert(linha).execute().data[0]
    except Exception as exc:
        # Largo de proposito: `APIError`, o `httpx.HTTPError` cru do timeout e a
        # resposta sem linha (`IndexError`) tem o mesmo desfecho. Inclusive a
        # corrida de dois envios na mesma posicao, que o UNIQUE (demanda_id,
        # ordem) recusa. Sem a linha, o binario e orfao que ninguem alcanca:
        # limpar agora e a unica chance, e se falhar o caminho fica no log.
        if not storage.delete_file(supabase, _bucket(), path):
            logger.error("Anexo da Demanda %s órfão no bucket após falha de registro: %s", demanda_id, path)
        logger.exception("Falha ao registrar o anexo da Demanda %s", demanda_id)
        raise AnexoRecusadoError(MOTIVO_NAO_GUARDOU, status_code=503) from exc


def apagar_todos(supabase, demanda_id: str) -> int:
    """Tira do bucket os binarios da Demanda e marca cada registro apagado.

    Chamado pelo cron em `apagar_vencidos` (ADR 0077). A sincronizacao da
    Etapa nunca chega aqui: em Entregue o diretor ainda confere com o print na
    mao.

    A marca de cada anexo entra logo depois da confirmacao DELE, e nao todas no
    fim (a regra do `storage.delete_file`): uma falha no meio deixa marcados so
    os que sairam de verdade. O que o Storage nao confirmou fica sem a marca,
    com o caminho no log, e a passada seguinte tenta de novo.

    Nunca levanta: falha aqui vira log com o caminho do arquivo, e o cron segue
    para a Demanda seguinte.

    Devolve quantos binarios sairam.
    """
    try:
        guardados = [linha for linha in ler(supabase, demanda_id) if not linha.get("apagado_em")]
    except Exception:
        logger.exception("Falha ao ler os anexos da Demanda %s para apagar", demanda_id)
        return 0
    sairam = 0
    for linha in guardados:
        path = linha["storage_path"]
        if not storage.delete_file(supabase, _bucket(), path):
            logger.error("Anexo da Demanda %s não saiu do bucket ao apagar: %s", demanda_id, path)
            continue
        sairam += 1
        try:
            supabase.table(TABELA_ANEXOS).update({"apagado_em": datetime.now(UTC).isoformat()}).eq(
                "id", linha["id"]
            ).execute()
        except Exception:
            logger.exception(
                "Anexo %s da Demanda %s saiu do bucket, mas a marca de apagado não entrou: %s",
                linha["id"],
                demanda_id,
                path,
            )
    return sairam


def _print_venceu(demanda: dict, agora: datetime) -> bool:
    # A Demanda apagada (ADR 0084, decisao 2): o que o bucket nao soltou no
    # Apagar sai agora.
    if demanda.get("apagada_em"):
        return True
    etapa = demanda.get("etapa")
    if etapa == ETAPA_NAO_SERA_FEITA:
        return True
    if etapa != ETAPA_EM_PRODUCAO:
        return False
    # Sem data legivel, fica: apagar e definitivo, e a duvida protege o print.
    subiu_em = instante_do_banco(demanda.get("entregue_em"))
    return subiu_em is not None and agora - subiu_em >= PRAZO_DEPOIS_DE_EM_PRODUCAO


def apagar_vencidos(supabase, agora: datetime | None = None) -> int:
    """A passada do cron: apaga os prints das Demandas em Em producao ha 30
    dias ou mais, das em Nao sera feita (ADR 0077, issue #1382) e das apagadas
    (ADR 0084, issue #1549).

    Parte dos anexos ainda guardados, e nao das Demandas: quase toda Demanda
    entregue ja nao tem o que apagar, e a passada de hora em hora fica do
    tamanho do que sobrou no bucket. Cada Demanda vencida passa pelo
    `apagar_todos`, com a mesma regra de marca e de log.

    Devolve quantos binarios sairam.
    """
    agora = agora or datetime.now(UTC)
    guardados = supabase.table(TABELA_ANEXOS).select("demanda_id").is_("apagado_em", "null").execute().data or []
    ids = sorted({str(linha["demanda_id"]) for linha in guardados})
    if not ids:
        return 0
    demandas = (
        supabase.table("tecnologia_demandas").select("id, etapa, entregue_em, apagada_em").in_("id", ids).execute().data
        or []
    )
    return sum(apagar_todos(supabase, str(d["id"])) for d in demandas if _print_venceu(d, agora))


def e_documento(linha: dict) -> bool:
    """Se o anexo e um documento, pelo tipo gravado. O que nao e documento
    conta como imagem: era o unico tipo antes da issue #1520."""
    return linha.get("content_type") in TIPOS_DE_DOCUMENTO.values()


def quantos_guardados(supabase, demanda_id: str) -> tuple[int, int]:
    """Quantas imagens e quantos documentos a Demanda ainda guarda: os numeros
    da frase "Anexos: 2 imagens e 1 documento na Demanda" da issue (issues
    #1062 e #1520). O apagado nao conta: o binario saiu, e quem desenvolve nao
    teria o que buscar."""
    guardados = [linha for linha in ler(supabase, demanda_id) if not linha.get("apagado_em")]
    documentos = sum(1 for linha in guardados if e_documento(linha))
    return len(guardados) - documentos, documentos


def ler(supabase, demanda_id: str) -> list[dict]:
    """As linhas dos anexos da Demanda, na ordem em que entraram."""
    result = supabase.table(TABELA_ANEXOS).select("*").eq("demanda_id", demanda_id).order("ordem").execute()
    return list(result.data or [])


def para_quem_desenvolve(supabase, demanda_id: str) -> list[dict]:
    """Os anexos que quem desenvolve baixa pela ponte (issue #1063): nome, tipo
    e URL assinada de vida curta de cada imagem ainda guardada.

    O apagado fica de fora: o binario saiu, e nao ha o que baixar. Quem anexou e
    quando ficam no app: o script so precisa do arquivo.
    """
    return [
        {
            "nome": linha.get("nome_original") or "",
            "tipo": linha.get("content_type") or "",
            "url": storage.signed_url(supabase, _bucket(), linha["storage_path"], EXPIRACAO_DA_URL_SEGUNDOS),
        }
        for linha in ler(supabase, demanda_id)
        if not linha.get("apagado_em")
    ]
