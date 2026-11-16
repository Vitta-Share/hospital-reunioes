"""A ponte com o desenvolvimento (issue #1063, ADR 0069, decisão 2).

Quem desenvolve a Demanda busca os prints pelo app, por uma boca só: o script
`.claude/skills/pegar-issue/scripts/anexos.py` lê o id da Demanda no marcador da
issue e chama esta rota. Os anexos nunca vão para o GitHub (o repositório é
público); daqui sai só a URL assinada de vida curta de cada um.

Autenticação por chave de serviço própria (`X-API-Key` contra
`TECNOLOGIA_AUTOMACAO_API_KEY`), fora do fluxo JWT, no molde da API da Ana.

Desde a ADR 0096 a ponte tambem escreve na Conversa da Demanda: a Mensagem
pelo terminal, no perfil do Desenvolvedor cujo login do GitHub vem no pedido,
e le a resposta do diretor na mesma conversa (decisao 6).
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from app.dependencies import get_supabase_client, require_tecnologia_automacao_api_key
from app.limiter import limiter
from app.models.tecnologia_schemas import LIMITE_DA_MENSAGEM
from app.services import tecnologia_anexos, tecnologia_conversa
from app.services.tecnologia import TABELA_DEMANDAS

# O detail nunca ecoa o login: a resposta nao confirma quem esta no cadastro.
MOTIVO_LOGIN_RECUSADO = "Este login do GitHub não é de um Desenvolvedor ativo no aplicativo."
MOTIVO_DEMANDA_NAO_ENCONTRADA = "Demanda não encontrada."


@limiter.limit("60/minute")
def _teto_por_endereco(request: Request) -> None:
    """60 pedidos por minuto por endereço, no molde da API da Ana.

    Vem como dependência antes da chave, e não no endpoint: o decorador no
    endpoint só conta depois que as dependências passam, e aí a tentativa de
    chave errada (401) não gastaria o teto.
    """


router = APIRouter(
    prefix="/automacao/tecnologia",
    tags=["automacao"],
    dependencies=[Depends(_teto_por_endereco), Depends(require_tecnologia_automacao_api_key)],
)


@router.get("/demandas/{demanda_id}/anexos")
def anexos_da_demanda(demanda_id: UUID, supabase=Depends(get_supabase_client)) -> dict:
    """Nome, tipo e URL assinada de cada anexo não apagado da Demanda.

    O id é UUID na assinatura: lixo no caminho vira 422 aqui, e não 500 no
    PostgREST. Demanda sem anexo, ou que não existe, devolve a lista vazia.
    """
    return {"anexos": tecnologia_anexos.para_quem_desenvolve(supabase, str(demanda_id))}


def _demanda_ou_404(supabase, **filtros) -> dict:
    """A Demanda que casa os filtros, ou 404. A lapide do Apagar (ADR 0084,
    decisao 2) responde como inexistente, como em toda leitura da aba."""
    consulta = supabase.table(TABELA_DEMANDAS).select("*")
    for coluna, valor in filtros.items():
        consulta = consulta.eq(coluna, valor)
    linhas = consulta.is_("apagada_em", "null").execute().data or []
    if not linhas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MOTIVO_DEMANDA_NAO_ENCONTRADA)
    return linhas[0]


@router.get("/projetos/{projeto}/issues/{numero}/demanda")
def demanda_da_issue(
    projeto: str,
    numero: int = Path(ge=1),
    supabase=Depends(get_supabase_client),
) -> dict:
    """O id da Demanda vinculada a esta issue-raiz (ADR 0093: projeto mais
    numero), para a sessao do terminal escrever na conversa dela. Issue sem
    Demanda, ou de um Projeto que nao existe, e 404: a pergunta segue pelo
    WhatsApp (ADR 0096, decisao 5)."""
    demanda = _demanda_ou_404(supabase, projeto=projeto, github_issue_numero=numero)
    return {"id": str(demanda["id"])}


class MensagemPeloTerminalPayload(BaseModel):
    """O texto aprovado na sessao e o login do GitHub de quem a roda."""

    texto: str = Field(min_length=1, max_length=LIMITE_DA_MENSAGEM)
    github_login: str = Field(min_length=1, max_length=100)


@router.post("/demandas/{demanda_id}/conversa", status_code=status.HTTP_201_CREATED)
def escrever_pelo_terminal(
    demanda_id: UUID, payload: MensagemPeloTerminalPayload, supabase=Depends(get_supabase_client)
) -> dict:
    """A Mensagem pelo terminal (ADR 0096): grava no perfil do Desenvolvedor
    dono do login, com a origem `terminal`, e avisa pela regra dos avisos de
    entrega. O id e UUID na assinatura: lixo no caminho vira 422, nao 500."""
    autor = tecnologia_conversa.desenvolvedor_do_login(supabase, payload.github_login)
    if autor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MOTIVO_LOGIN_RECUSADO)
    texto = payload.texto.strip()
    if not texto:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A mensagem está vazia.")
    demanda = _demanda_ou_404(supabase, id=str(demanda_id))
    linha = tecnologia_conversa.escrever(
        supabase, demanda, autor=autor, texto=texto, origem=tecnologia_conversa.ORIGEM_TERMINAL
    )
    return {"id": str(linha["id"]), "criado_em": linha.get("criado_em")}


@router.get("/demandas/{demanda_id}/conversa")
def ler_pelo_terminal(
    demanda_id: UUID,
    depois: datetime | None = Query(default=None),
    supabase=Depends(get_supabase_client),
) -> dict:
    """A resposta do diretor (ADR 0096, decisao 6): as mensagens da Conversa
    da Demanda depois do instante `depois` (a data da pergunta da sessao), ou
    a conversa inteira sem ele. So le. O id e UUID e o instante e data na
    assinatura: lixo vira 422, nao 500."""
    demanda = _demanda_ou_404(supabase, id=str(demanda_id))
    return {"mensagens": tecnologia_conversa.ler(supabase, str(demanda["id"]), depois=depois)}
