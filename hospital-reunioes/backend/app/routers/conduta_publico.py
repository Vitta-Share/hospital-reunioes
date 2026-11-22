"""Canal de Conduta, o lado público (issue #1820, ADR 0097, decisões 10 e 11).

Sem login. O canal nasce fechado: com `CONDUTA_CANAL_ABERTO` desligada, toda
rota daqui responde 404, como se não existisse. A chave fica no Coolify, e
quem abre é o Pedro, depois do aditivo de sigilo assinado, do layout aprovado
e do teste de anonimato.

A trava vale para o router inteiro (`dependencies`), então rota nova aqui
nasce fechada sem depender de quem a escreve. O log das rotas do módulo sai
sem IP (`app.middleware.request_context`).
"""

import json
from datetime import date

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from postgrest.exceptions import APIError
from supabase import Client

from app.config import settings
from app.dependencies import get_supabase_client
from app.routers.conduta_codigo import resposta_em_pdf
from app.services import limite_sem_ip
from app.services.conduta import anexos, cifra, codigo, configuracoes, protecao, relato_publico
from app.services.conduta.acesso import hoje_em_sao_paulo


def exigir_canal_aberto() -> None:
    if not settings.conduta_canal_aberto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(prefix="/conduta", tags=["canal-de-conduta-publico"], dependencies=[Depends(exigir_canal_aberto)])


@router.get("/abertura")
async def abertura() -> dict:
    """Se o canal está aberto. Fechado, a rota nem aparece (404)."""
    return {"aberto": True}


@router.get("/textos")
@limite_sem_ip.limitar("60/minute")
async def textos(request: Request, supabase: Client = Depends(get_supabase_client)) -> dict:
    """Os textos vigentes das telas públicas (issue #1826), cada um com o
    identificador da versão, para a tela dizer qual versão mostrou. Lê o banco
    a cada chamada, então tem limite por aparelho, sem guardar o endereço
    (decisão 10 da ADR 0097)."""
    return {"textos": configuracoes.vigentes_publicas(supabase)}


@router.get("/codigo-de-conduta")
@limite_sem_ip.limitar("60/minute")
async def codigo_de_conduta(request: Request, supabase: Client = Depends(get_supabase_client)) -> Response:
    """O PDF do Código de Conduta vigente hoje (issue #1841), num endereço que
    não muda de uma versão para a outra. O número da versão vai no cabeçalho
    `X-Codigo-De-Conduta-Versao`."""
    try:
        achada = codigo.pdf_vigente_em(supabase, hoje_em_sao_paulo())
    except codigo.RecusaDoCodigo as recusa:
        raise HTTPException(status_code=recusa.status_code, detail=recusa.motivo) from recusa
    if achada is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="O Código de Conduta ainda não foi publicado")
    return resposta_em_pdf(*achada)


# O relato em passos (issue #1843). Rajada do mesmo aparelho para no limite,
# contado pela chave sem endereço (decisão 10 da ADR 0097).
LIMITE_DOS_RELATOS = "3/minute;10/hour"
SEM_CACHE = {"Cache-Control": "no-store"}
FALHA_DO_ENVIO = "Não deu para registrar o relato agora. Nada foi gravado. Tente de novo em alguns minutos."


async def _corpo(request: Request):
    """O corpo lido à mão: a recusa padrão do FastAPI devolveria o que foi
    enviado, e aqui isso é relato e nome (regra C6)."""
    try:
        return await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Envio ilegível.") from erro


@router.post("/relatos", status_code=status.HTTP_201_CREATED)
@limite_sem_ip.limitar(LIMITE_DOS_RELATOS)
async def relatar(
    request: Request,
    response: Response,
    tarefas: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client),
) -> dict:
    """Recebe o relato inteiro, do passo 1 ao 5, e devolve o protocolo e o
    código, uma vez só, com a data para voltar. Sem login: o cabeçalho de
    sessão do app, se vier, é ignorado."""
    response.headers.update(SEM_CACHE)
    try:
        envio = relato_publico.validar(await _corpo(request))
        return relato_publico.registrar(supabase, envio, tarefas)
    except relato_publico.EnvioRecusadoError as recusa:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=recusa.motivo) from None
    except (cifra.CifraIndisponivelError, APIError, httpx.HTTPError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=FALHA_DO_ENVIO) from None


# Cada anexo é uma chamada, depois do relato, com o protocolo e o código que a
# tela ainda tem na memória (issue #1844).
LIMITE_DOS_ANEXOS = "10/minute;40/hour"


@router.post("/relatos/anexos", status_code=status.HTTP_201_CREATED)
@limite_sem_ip.limitar(LIMITE_DOS_ANEXOS)
async def anexar(request: Request, response: Response, supabase: Client = Depends(get_supabase_client)) -> dict:
    """Um anexo do relato: imagem, PDF ou áudio. O backend apaga os dados de
    origem do arquivo antes de cifrar e guardar. O nome do arquivo é
    ignorado. Código que não confere responde 404, sem dizer se o protocolo
    existe."""
    response.headers.update(SEM_CACHE)
    try:
        formulario = await request.form(max_files=1, max_fields=3)
    except Exception as erro:  # noqa: BLE001 - corpo ilegível: recusa sem devolver nada do envio
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Envio ilegível.") from erro
    protocolo, codigo, arquivo = (formulario.get(campo) for campo in ("protocolo", "codigo", "arquivo"))
    if not isinstance(protocolo, str) or not isinstance(codigo, str) or isinstance(arquivo, str) or arquivo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Envie o protocolo, o código e o arquivo."
        )
    if (arquivo.size or 0) > anexos.LIMITE_DO_ARQUIVO:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="O arquivo passa de 50 MB.")
    try:
        caso_id = relato_publico.caso_pelo_codigo(supabase, protocolo[:20], codigo[:40])
        if caso_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relato não encontrado.")
        return anexos.guardar(supabase, caso_id, await arquivo.read())
    except anexos.AnexoRecusadoError as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.mensagem) from None
    except (cifra.CifraIndisponivelError, APIError, httpx.HTTPError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não deu para guardar o anexo agora. O relato está registrado. Tente de novo em alguns minutos.",
        ) from None


@router.post("/relatos/confianca", status_code=status.HTTP_204_NO_CONTENT)
@limite_sem_ip.limitar("10/minute")
async def responder_confianca(request: Request, supabase: Client = Depends(get_supabase_client)) -> Response:
    """A pergunta opcional do P6, de 1 a 5. Vale uma vez por relato. Código
    que não confere responde 404, sem dizer se o protocolo existe."""
    try:
        nota = relato_publico.validar_nota(await _corpo(request))
        achado = relato_publico.registrar_confianca(supabase, nota)
    except relato_publico.EnvioRecusadoError as recusa:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=recusa.motivo) from None
    except (APIError, httpx.HTTPError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Não deu para gravar a nota."
        ) from None
    if not achado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relato não encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=SEM_CACHE)


@router.get("/protecao")
@limite_sem_ip.limitar("60/minute")
async def pagina_de_protecao(
    request: Request, em: date | None = None, supabase: Client = Depends(get_supabase_client)
) -> dict:
    """A página "Como este canal protege você" (issue #1846), bloco a bloco,
    com os textos vigentes das Configurações. Com `em`, a versão arquivada
    daquele dia."""
    return protecao.pagina(supabase, em)
