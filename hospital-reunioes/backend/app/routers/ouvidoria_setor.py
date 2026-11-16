"""Portal do setor por link tokenizado (issue #326, ADR 0034 decisão 4).

Rotas públicas, sem login: quem chega aqui veio pelo link do email de
acionamento, no padrão do Aceite interno. O token restringe tudo a UMA
manifestação e UM destinatário; a página mostra os três blocos do caso
(resumo, relato integral e a nota da ouvidoria, ADR 0041). Caso sigiloso ou
anônimo sai sem identificação de quem manifestou, e só o sigiloso troca o
relato pelo extrato (RN-79; emenda de 07/10/2026, issue #1051).

Esta é a porta do token da Tela do responsável (issue #1885, ADR 0099): ela só
resolve o caso e o ator a partir do link e chama `ouvidoria_tela_do_responsavel`,
que faz a ação. O uso único do link entra no serviço como a `Trava` do token.
"""

from __future__ import annotations

import datetime as dt
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from httpx import HTTPError
from postgrest.exceptions import APIError
from pydantic import BaseModel, Field

from app.dependencies import get_supabase_client
from app.limiter import limiter
from app.services import (
    ouvidoria_acionamentos,
    ouvidoria_nucleo,
    ouvidoria_porta,
    ouvidoria_prorrogacao,
    ouvidoria_setor_tokens,
    ouvidoria_tela_do_responsavel,
)
from app.services.ouvidoria_tela_do_responsavel import FALHAS_DO_POSTGREST, indisponivel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ouvidoria-setor", tags=["ouvidoria-setor"])

# A leitura do caso pela porta do token é a mesma da Tela do responsável.
_CAMPOS_DO_PORTAL = ouvidoria_tela_do_responsavel.CAMPOS_DO_CASO

# O que o responsável da área ANTERIOR lê ao abrir o link velho depois de o
# caso ter sido acionado em outra área (issue #707, ADR 0055). Ela existe
# separada da frase do link usado porque as duas contam coisas diferentes: lá
# alguém respondeu por este link, aqui o caso mudou de dono.
LINK_REVOGADO = "Este caso foi encaminhado a outra área; este link não vale mais"


def agora_utc() -> dt.datetime:
    """O relógio do módulo, num ponto só (mesmo padrão do painel)."""
    return dt.datetime.now(dt.UTC)


def _carregar_caso(supabase, token: str, agora: dt.datetime) -> tuple[dict, dict]:
    """Valida o token e carrega a manifestação dele. Recusa sem vazar: token
    inválido é 404 seco, e nenhuma recusa diz se o caso existe."""
    try:
        vinculo = ouvidoria_setor_tokens.carregar(supabase, token, agora)
    except ouvidoria_setor_tokens.TokenInvalidoError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link inválido") from None
    except ouvidoria_setor_tokens.TokenUsadoError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="Este link já foi usado: a resposta do setor já entrou"
        ) from None
    except ouvidoria_setor_tokens.TokenExpiradoError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Este link expirou") from None
    except ouvidoria_setor_tokens.TokenRevogadoError:
        # 410 como as outras duas: o link existiu e acabou. A frase diz o que
        # aconteceu sem dizer para qual área o caso foi, que é decisão da
        # Ouvidoria e não assunto de quem já saiu do caso (ADR 0055).
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=LINK_REVOGADO) from None
    except FALHAS_DO_POSTGREST as exc:
        # Falha de leitura não é link acabado: o 404 e o 410 daqui de cima
        # mandariam o responsável conferir um endereço que está certo, ou
        # desistir de um link que continua valendo.
        logger.error("Falha ao ler o token do portal do setor")
        raise indisponivel() from exc

    try:
        result = (
            supabase.table("ouvidoria_protocolos")
            .select(_CAMPOS_DO_PORTAL)
            .eq("id", vinculo["manifestacao_id"])
            .limit(1)
            .execute()
        )
    except FALHAS_DO_POSTGREST as exc:
        logger.error("Falha ao ler a manifestação %s pelo portal do setor", vinculo["manifestacao_id"])
        raise indisponivel() from exc
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link inválido")
    return vinculo, result.data[0]


def _ator_do_link(vinculo: dict) -> ouvidoria_tela_do_responsavel.Ator:
    """Quem clicou no link: o destinatário do email, pela porta do link."""
    return ouvidoria_tela_do_responsavel.Ator(
        nome=vinculo["destinatario_nome"],
        email=vinculo.get("destinatario_email"),
        porta=ouvidoria_porta.LINK_DE_EMAIL,
    )


class _TravaDoLink:
    """O uso único da porta do token: o claim atômico do link.

    A devolução é sempre a do claim DESTE request (o carimbo `agora`), nunca a
    cega, e nunca deixa a falha da própria devolução escapar: quando o banco
    está fora, insistir aqui só trocaria o 503 (que diz ao responsável para
    tentar de novo) por um 500 cru. O link que volta para um caso que já
    transicionou não abre porta nenhuma: a guarda de estado do serviço recusa a
    segunda resposta com 410."""

    def __init__(self, supabase, vinculo: dict, agora: dt.datetime):
        self._supabase = supabase
        self._vinculo = vinculo
        self._agora = agora

    def consumir(self) -> bool:
        return bool(ouvidoria_setor_tokens.consumir(self._supabase, self._vinculo, self._agora))

    def devolver(self) -> None:
        try:
            ouvidoria_setor_tokens.devolver(self._supabase, self._vinculo, self._agora.isoformat())
        except FALHAS_DO_POSTGREST:
            logger.error(
                "Falha ao devolver o link do portal do setor da manifestação %s", self._vinculo["manifestacao_id"]
            )


@router.get("/{token}")
@limiter.limit("30/minute")
async def abrir_portal(
    request: Request,
    token: str,
    supabase=Depends(get_supabase_client),
):
    """O que o titular vê ao abrir o link do email: extrato, prazo e se o caso
    ainda aceita resposta."""
    agora = agora_utc()
    vinculo, caso = _carregar_caso(supabase, token, agora)
    return await ouvidoria_tela_do_responsavel.abrir(supabase, caso=caso, ator=_ator_do_link(vinculo), agora=agora)


@router.post("/{token}/responder")
@limiter.limit("10/minute")
async def responder(
    request: Request,
    token: str,
    resposta: str = Form(...),
    arquivos: list[UploadFile] = File(default=[]),
    supabase=Depends(get_supabase_client),
):
    """A resposta da área pelo link do email. O token é de uso único, com
    claim atômico: a segunda tentativa pelo mesmo link não duplica resposta nem
    quebra o estado (critério 6)."""
    agora = agora_utc()
    vinculo, caso = _carregar_caso(supabase, token, agora)
    return await ouvidoria_tela_do_responsavel.responder(
        supabase,
        caso=caso,
        ator=_ator_do_link(vinculo),
        trava=_TravaDoLink(supabase, vinculo, agora),
        agora=agora,
        resposta=resposta,
        arquivos=arquivos,
    )


class DevolucaoAOuvidoria(BaseModel):
    """O que a área manda para devolver um caso que não é dela.

    O modelo só recebe: quem decide o que vale como motivo é
    `ouvidoria_devolucao_a_ouvidoria`, no mesmo desenho da resposta e da
    justificativa da prorrogação. O texto chega CRU até lá, e por isso teto,
    vazio e travessão são decididos num lugar só."""

    motivo: str


@router.post("/{token}/devolver")
@limiter.limit("10/minute")
async def devolver_a_ouvidoria(
    request: Request,
    token: str,
    devolucao: DevolucaoAOuvidoria,
    supabase=Depends(get_supabase_client),
):
    """A Devolução à Ouvidoria pelo link do email (issue #600): este caso não é
    do meu setor. O link deixa de valer."""
    agora = agora_utc()
    vinculo, caso = _carregar_caso(supabase, token, agora)
    return await ouvidoria_tela_do_responsavel.devolver_a_ouvidoria(
        supabase,
        caso=caso,
        ator=_ator_do_link(vinculo),
        trava=_TravaDoLink(supabase, vinculo, agora),
        agora=agora,
        motivo=devolucao.motivo,
    )


class PedidoDeProrrogacao(BaseModel):
    """O que a área manda para pedir mais prazo.

    O modelo só recebe: quem decide o que vale como justificativa é
    `ouvidoria_prorrogacao`, no mesmo desenho da resposta da área. O texto chega
    CRU até lá, e por isso piso, teto e travessão são decididos num lugar só,
    com a recusa saindo como frase que o responsável lê (issue #510)."""

    justificativa: str
    dias_uteis: int = Field(ge=1, le=ouvidoria_prorrogacao.MAX_DIAS_UTEIS_PEDIDOS)


@router.post("/{token}/prorrogacao", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def pedir_prorrogacao(
    request: Request,
    token: str,
    pedido: PedidoDeProrrogacao,
    supabase=Depends(get_supabase_client),
):
    """O pedido de mais prazo, feito pelo próprio link do email (issue #333).

    O token NÃO é consumido: quem pede prorrogação ainda precisa do mesmo link
    para responder depois."""
    # Antes de qualquer leitura, como vinha quando era validador do modelo:
    # corpo que já sabemos recusar não custa nem o token nem o caso.
    justificativa = ouvidoria_tela_do_responsavel.justificativa_valida(pedido.justificativa)

    agora = agora_utc()
    vinculo, caso = _carregar_caso(supabase, token, agora)
    return await ouvidoria_tela_do_responsavel.pedir_prorrogacao(
        supabase,
        caso=caso,
        ator=_ator_do_link(vinculo),
        agora=agora,
        justificativa=justificativa,
        dias_uteis=pedido.dias_uteis,
    )


# =====================================================================
# O botão "Elogio recebido" (issue #1618, ADR 0088, decisão 2)
# =====================================================================

ELOGIO_JA_CONFIRMADO = "Este elogio já foi confirmado. Obrigado por compartilhar com a equipe."
ELOGIO_MOVIMENTADO = "A Ouvidoria já movimentou este caso e este link não vale mais."


def _o_elogio_continua_com_o_setor(supabase, ciencia: dict) -> bool:
    """Se o caso continua em `aguardando_area` no setor da ciência depois de uma
    transição sem resposta. Só a linha lida prova que a transição não entrou;
    leitura que falha não prova nada e devolve False."""
    try:
        result = (
            supabase.table("ouvidoria_protocolos")
            .select("id")
            .eq("id", ciencia["manifestacao_id"])
            .eq("status", "aguardando_area")
            .eq("setor", ciencia.get("setor"))
            .limit(1)
            .execute()
        )
    except FALHAS_DO_POSTGREST:
        logger.warning("Falha ao reler a manifestação %s depois do clique no elogio", ciencia["manifestacao_id"])
        return False
    return bool(result.data)


def _desfazer_o_clique(supabase, ciencia: dict, carimbo: str) -> None:
    """Devolve a ciência a `pendente` sem deixar a falha da própria devolução
    trocar o 503 (que diz para tentar de novo) por um 500 cru."""
    try:
        ouvidoria_acionamentos.desfazer_confirmacao(supabase, ciencia, carimbo)
    except FALHAS_DO_POSTGREST:
        logger.error("Falha ao desfazer a confirmação do elogio da manifestação %s", ciencia["manifestacao_id"])


@router.post("/elogio/{token}/recebido")
@limiter.limit("10/minute")
async def confirmar_elogio(
    request: Request,
    token: str,
    supabase=Depends(get_supabase_client),
):
    """O responsável do setor confirma que o elogio chegou à equipe, sem senha.

    O link vale uma vez: quem decide é a ciência, que só passa de `pendente`
    para `ciente` uma vez. Confirmado, o caso volta ao ouvidor em `respondido`,
    com a marca Pronto para encerrar escrita na trilha.

    É POST, e não o GET do próprio link: leitor de email que abre link sozinho
    para conferir se é seguro gastaria o uso único antes de a pessoa clicar. O
    link do email abre a tela, e é o botão da tela que chama esta rota."""
    from app.routers.ouvidoria import barrar_caso_apagado

    agora = agora_utc()
    try:
        ciencia = ouvidoria_acionamentos.carregar_pelo_token(supabase, token)
    except ouvidoria_acionamentos.LinkInvalidoError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link inválido") from None
    except ouvidoria_acionamentos.JaConfirmadoError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=ELOGIO_JA_CONFIRMADO) from None
    except ouvidoria_acionamentos.ForaDeUsoError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=ELOGIO_MOVIMENTADO) from None
    except FALHAS_DO_POSTGREST as exc:
        logger.error("Falha ao ler o link do elogio")
        raise indisponivel() from exc

    try:
        result = (
            supabase.table("ouvidoria_protocolos")
            .select("id, protocolo, setor, status, anonimizada_em, apagamento_pedido_em")
            .eq("id", ciencia["manifestacao_id"])
            .limit(1)
            .execute()
        )
    except FALHAS_DO_POSTGREST as exc:
        logger.error("Falha ao ler a manifestação %s pelo link do elogio", ciencia["manifestacao_id"])
        raise indisponivel() from exc
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link inválido")
    caso = result.data[0]
    barrar_caso_apagado(caso, "confirmado pelo setor", canal_publico=True)
    if caso.get("status") != "aguardando_area" or caso.get("setor") != ciencia.get("setor"):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=ELOGIO_MOVIMENTADO)

    try:
        confirmou = ouvidoria_acionamentos.confirmar(supabase, ciencia, agora)
    except FALHAS_DO_POSTGREST as exc:
        logger.error("Falha ao confirmar o elogio da manifestação %s", ciencia["manifestacao_id"])
        raise indisponivel() from exc
    if not confirmou:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=ELOGIO_JA_CONFIRMADO)

    nome = ciencia.get("responsavel_nome") or "Responsável do setor"
    try:
        supabase.rpc(
            "ouvidoria_transicionar",
            {
                "p_manifestacao_id": ciencia["manifestacao_id"],
                "p_estado_novo": "respondido",
                "p_autor_id": None,
                "p_autor_nome": nome,
                "p_observacao": (
                    f"Elogio recebido por {nome}, do setor {ciencia.get('setor')}. "
                    f"{ouvidoria_acionamentos.PRONTO_PARA_ENCERRAR}."
                ),
            },
        ).execute()
    except APIError as exc:
        # O servidor respondeu: o caso não andou, e o clique volta a valer.
        ouvidoria_acionamentos.desfazer_confirmacao(supabase, ciencia, agora.isoformat())
        if exc.code == "23514":
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=ELOGIO_MOVIMENTADO) from exc
        logger.error("Erro na RPC ouvidoria_transicionar pelo link do elogio (código %s)", exc.code)
        raise indisponivel() from exc
    except HTTPError as exc:
        # Sem resposta, o caso pode ter andado ou não. Quem decide é onde ele
        # ficou, como o `_limpar_t2` do portal: ainda em `aguardando_area` no
        # mesmo setor, a transição não entrou, e a confirmação é desfeita para o
        # clique voltar a valer. Sem isso o elogio ficava preso para sempre: sem
        # prazo, fora do reenvio (que só vê `pendente`) e com o link dizendo que
        # já foi confirmado.
        logger.error("Falha de rede na transição do elogio da manifestação %s", ciencia["manifestacao_id"])
        if _o_elogio_continua_com_o_setor(supabase, ciencia):
            _desfazer_o_clique(supabase, ciencia, agora.isoformat())
            raise indisponivel() from exc
        # O caso andou, ou a leitura também falhou: a confirmação fica, e a
        # frase não promete que o link continua valendo.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O sistema está instável agora. A confirmação pode já ter sido registrada.",
        ) from exc

    ouvidoria_tela_do_responsavel.registrar_acesso(supabase, ciencia["manifestacao_id"], nome, "elogio_recebido")
    return {"protocolo": caso.get("protocolo"), "setor": ciencia.get("setor"), "confirmado_em": agora.isoformat()}


# =====================================================================
# O link do Núcleo de Segurança do Paciente (issue #1621, ADR 0088)
# =====================================================================

NUCLEO_JA_RECEBEU = "O Núcleo já confirmou o recebimento deste caso."
NUCLEO_FORA_DE_USO = "Este link não vale mais. Procure a Ouvidoria pelo protocolo."


def _ciencia_do_link_do_nucleo(supabase, token: str) -> dict:
    """A ciência do Núcleo do link, com as recusas do portal: 404 seco para o
    token que não existe (ou que é de outra ciência), 410 para o que perdeu a
    vez, 503 quando o banco não respondeu."""
    try:
        return ouvidoria_nucleo.carregar_pelo_token(supabase, token)
    except ouvidoria_acionamentos.LinkInvalidoError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link inválido") from None
    except ouvidoria_acionamentos.ForaDeUsoError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=NUCLEO_FORA_DE_USO) from None
    except FALHAS_DO_POSTGREST as exc:
        logger.error("Falha ao ler o link do Núcleo")
        raise indisponivel() from exc


def _caso_do_nucleo(supabase, ciencia: dict, acao: str) -> dict:
    """O caso da ciência, barrado quando foi apagado."""
    from app.routers.ouvidoria import barrar_caso_apagado

    try:
        result = (
            supabase.table("ouvidoria_protocolos")
            .select(ouvidoria_nucleo.CAMPOS_DA_TELA)
            .eq("id", ciencia["manifestacao_id"])
            .limit(1)
            .execute()
        )
    except FALHAS_DO_POSTGREST as exc:
        logger.error("Falha ao ler a manifestação %s pelo link do Núcleo", ciencia["manifestacao_id"])
        raise indisponivel() from exc
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link inválido")
    caso = result.data[0]
    barrar_caso_apagado(caso, acao, canal_publico=True)
    return caso


def _acesso_do_nucleo(supabase, ciencia: dict, acao: str) -> None:
    ouvidoria_tela_do_responsavel.registrar_acesso(
        supabase,
        ciencia["manifestacao_id"],
        f"{ciencia.get('responsavel_nome') or 'Responsável'}, Núcleo de Segurança do Paciente",
        acao,
    )


@router.get("/nsp/{token}")
@limiter.limit("30/minute")
async def abrir_o_caso_no_nucleo(
    request: Request,
    token: str,
    supabase=Depends(get_supabase_client),
):
    """A tela que o link do email do Núcleo abre, sem senha (ADR 0088,
    decisões 5 e 7): o relato integral, a justificativa técnica, o paciente com
    a data de nascimento, os profissionais e o quarto, mesmo no caso sigiloso.

    Abrir não confirma nada: o Recebido é o botão da tela, pelo mesmo motivo do
    elogio (leitor de email que abre link sozinho gastaria o uso único)."""
    ciencia = _ciencia_do_link_do_nucleo(supabase, token)
    caso = _caso_do_nucleo(supabase, ciencia, "aberto pelo Núcleo")
    _acesso_do_nucleo(supabase, ciencia, "nucleo_abrir")
    return ouvidoria_nucleo.tela_do_nucleo(caso, ciencia)


@router.post("/nsp/{token}/recebido")
@limiter.limit("10/minute")
async def confirmar_recebido_pelo_nucleo(
    request: Request,
    token: str,
    supabase=Depends(get_supabase_client),
):
    """O botão Recebido pelo NSP, sem senha e uma vez só (ADR 0088, decisão 4).

    Não mexe no estado do caso: a ciência do Núcleo corre em paralelo, e a
    resposta e o encerramento seguem o caminho de sempre. O uso único é da
    ciência, que só passa de `pendente` para `ciente` uma vez."""
    agora = agora_utc()
    ciencia = _ciencia_do_link_do_nucleo(supabase, token)
    if ciencia.get("status") == ouvidoria_acionamentos.CIENTE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=NUCLEO_JA_RECEBEU)
    caso = _caso_do_nucleo(supabase, ciencia, "confirmado pelo Núcleo")
    try:
        confirmou = ouvidoria_acionamentos.confirmar(supabase, ciencia, agora)
    except FALHAS_DO_POSTGREST as exc:
        logger.error("Falha ao confirmar o recebido do Núcleo no caso %s", ciencia["manifestacao_id"])
        raise indisponivel() from exc
    if not confirmou:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=NUCLEO_JA_RECEBEU)
    ouvidoria_nucleo.registrar_o_recebido(supabase, caso, ciencia)
    _acesso_do_nucleo(supabase, ciencia, "nucleo_recebido")
    return {"protocolo": caso.get("protocolo"), "recebido_em": agora.isoformat()}
