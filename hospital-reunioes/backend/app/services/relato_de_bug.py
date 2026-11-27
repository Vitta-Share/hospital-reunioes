"""O Roteiro do bug no Assistente do app (issue #2275, PRD #2262, ADR 0113,
decisao 8).

O robo do canto da tela faz as cinco perguntas do roteiro, uma por vez, sem IA:
Onde, O que aconteceu, O que esperava, Como repetir e o print. Pergunta fixa
nao custa chamada nem inventa o que a pessoa nao disse, e o roteiro so tem
estas cinco.

Tres passos, cada um uma funcao:

- **registrar**: as quatro respostas viram a Demanda Registrada, de Origem
  "Relato no app", com o resumo guardado na linha da conversa
  (`tecnologia_planejamentos`, a mesma do bug do chat da aba, ADR 0077,
  decisao 2). Resposta em branco sai "nao informado";
- **anexar o print**: a imagem vira Anexo da Demanda, no bucket privado, e
  nunca vai ao GitHub (ADR 0069);
- **enviar**: o clique cria a issue pela porta unica do envio
  (`tecnologia_envio`), a mesma do "Criar o card". Super admin nasce
  `ready-for-agent`; os demais, `needs-triage`. O corpo leva o marcador da
  Demanda, e a Demanda ja sai vinculada: o espelho reconhece a issue e nao cria
  a segunda. A falha fica gravada como "Envio falhou", e so outro clique tenta
  de novo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.dependencies import is_super_admin
from app.services import tecnologia_anexos, tecnologia_envio
from app.services.assistente_tecnologia import TIPOS_DE_IMAGEM
from app.services.modelo_dos_agentes import MODELO_DOS_AGENTES_DO_APP
from app.services.tecnologia import ORIGEM_RELATO, TABELA_DEMANDAS, TABELA_PRODUTOS
from app.services.tecnologia_vinculo import (
    ETAPA_REGISTRADA,
    LABEL_DO_TIPO,
    LABEL_PRONTA_PARA_AGENTE,
    LABEL_TRIAGEM,
    NAO_INFORMADO,
    ROTULOS_DO_BUG,
    corpo_da_issue_do_bug,
    link_da_demanda,
    login_para_publicar,
)
from app.utils.text_sanitizer import sanitizar_travessao

TABELA_DA_CONVERSA = "tecnologia_planejamentos"
ESTADO_RESUMIDO = "resumido"
ESTADO_ENVIADO = "enviado"

LIMITE_DO_TITULO = 120
TITULO_SEM_RESPOSTA = "Bug relatado no Assistente do app"

# O criterio de aceite sai do "O que esperava"; sem ele, a frase nao inventa
# comportamento: so diz que o problema deixa de acontecer.
CRITERIO_SEM_O_ESPERADO = "O problema descrito em O que aconteceu deixa de acontecer."

QUEM_RELATOU = "Bug relatado por uma pessoa do hospital no Assistente do app"
COMO_CHEGOU = (
    "Relatado no Assistente do app, o robô do canto da tela do aplicativo do hospital, e mandado para o "
    "desenvolvimento por quem relatou, depois de conferir o resumo."
)

MOTIVO_NAO_ENCONTRADO = "Este relato não foi encontrado. Comece o relato de novo."
MOTIVO_JA_ENVIADO = "Este bug já foi enviado à Vitta."
MOTIVO_SO_IMAGEM = "O print entra como imagem (PNG, JPG ou WebP). Escolha outro arquivo."
MOTIVO_SEM_PRODUTO = "O aplicativo não tem Produto ativo para guardar o relato. Avise a equipe de Tecnologia."
MOTIVO_GITHUB_FORA = (
    "O GitHub não respondeu agora, e o bug não chegou à Vitta. O relato ficou guardado: clique em Tentar de novo."
)
MOTIVO_GITHUB_DESLIGADO = (
    "O envio de bugs não está configurado neste ambiente. O relato ficou guardado: avise a equipe de Tecnologia."
)
MOTIVO_ENVIANDO = "Este bug já está sendo enviado. Espere alguns segundos."


class RelatoRecusadoError(Exception):
    """A recusa, com a frase da tela e o status HTTP que a rota devolve."""

    def __init__(self, motivo: str, status_code: int):
        super().__init__(motivo)
        self.status_code = status_code


@dataclass(frozen=True)
class Respostas:
    onde: str = ""
    o_que_aconteceu: str = ""
    o_que_esperava: str = ""
    como_repetir: str = ""


def _limpo(valor: str | None) -> str:
    return sanitizar_travessao(" ".join((valor or "").split()))


def _titulo(respostas: Respostas) -> str:
    texto = _limpo(respostas.o_que_aconteceu) or _limpo(respostas.onde)
    if not texto:
        return TITULO_SEM_RESPOSTA
    return texto if len(texto) <= LIMITE_DO_TITULO else texto[: LIMITE_DO_TITULO - 3].rstrip() + "..."


def resumo(respostas: Respostas) -> dict[str, Any]:
    """O resumo que a pessoa confere antes de enviar: os quatro rotulos, o
    titulo e o criterio de aceite. Rotulo sem resposta sai "nao informado"."""
    saida: dict[str, Any] = {"titulo": _titulo(respostas)}
    for campo in ROTULOS_DO_BUG:
        saida[campo] = _limpo(getattr(respostas, campo)) or NAO_INFORMADO
    esperado = saida["o_que_esperava"]
    saida["criterios"] = [esperado if esperado != NAO_INFORMADO else CRITERIO_SEM_O_ESPERADO]
    return saida


def _produto_padrao(supabase) -> dict[str, Any] | None:
    produtos = [p for p in (supabase.table(TABELA_PRODUTOS).select("*").execute().data or []) if p.get("ativo")]
    return min(produtos, key=lambda p: p.get("ordem") or 0) if produtos else None


def registrar(supabase, *, pessoa: dict[str, Any], respostas: Respostas) -> tuple[dict[str, Any], dict[str, Any]]:
    """A Demanda Registrada do relato e o resumo dela."""
    produto = _produto_padrao(supabase)
    if produto is None:
        raise RelatoRecusadoError(MOTIVO_SEM_PRODUTO, 503)
    dados = resumo(respostas)
    demanda = (
        supabase.table(TABELA_DEMANDAS)
        .insert(
            {
                "titulo": dados["titulo"],
                "descricao": None,
                "tipo": "defeito",
                "produto_id": produto["id"],
                "estado": "nova",
                "responsavel_id": None,
                "autor_id": pessoa["id"],
                "prioridade": "normal",
                "origem": ORIGEM_RELATO,
                "etapa": ETAPA_REGISTRADA,
            }
        )
        .execute()
        .data[0]
    )
    supabase.table(TABELA_DA_CONVERSA).insert(
        {
            "demanda_id": demanda["id"],
            "estado": ESTADO_RESUMIDO,
            "mensagens": [],
            "resumo": dados,
            "modelo": MODELO_DOS_AGENTES_DO_APP,
        }
    ).execute()
    return demanda, dados


def _relato_aberto(supabase, demanda_id: str, pessoa: dict[str, Any]) -> dict[str, Any]:
    """A Demanda do relato desta pessoa, ainda sem issue."""
    linhas = supabase.table(TABELA_DEMANDAS).select("*").eq("id", demanda_id).execute().data or []
    demanda = linhas[0] if linhas else None
    if (
        demanda is None
        or demanda.get("origem") != ORIGEM_RELATO
        or str(demanda.get("autor_id")) != str(pessoa["id"])
        or demanda.get("apagada_em")
    ):
        raise RelatoRecusadoError(MOTIVO_NAO_ENCONTRADO, 404)
    if demanda.get("github_issue_numero"):
        raise RelatoRecusadoError(MOTIVO_JA_ENVIADO, 409)
    return demanda


def anexar_print(supabase, *, demanda_id: str, pessoa: dict[str, Any], nome: str, conteudo: bytes) -> int:
    """O print vira Anexo da Demanda. Devolve quantos prints ela guarda."""
    demanda = _relato_aberto(supabase, demanda_id, pessoa)
    extensao = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    if f".{extensao}" not in TIPOS_DE_IMAGEM:
        raise RelatoRecusadoError(MOTIVO_SO_IMAGEM, 422)
    try:
        tecnologia_anexos.anexar(supabase, demanda=demanda, nome=nome, conteudo=conteudo, quem_id=str(pessoa["id"]))
    except tecnologia_anexos.AnexoRecusadoError as recusa:
        raise RelatoRecusadoError(str(recusa), recusa.status_code) from recusa
    return tecnologia_anexos.quantos_guardados(supabase, demanda_id)[0]


def labels_do_relato(pessoa: dict[str, Any]) -> list[str]:
    """Super admin entra direto na fila; os demais passam pela triagem."""
    fila = LABEL_PRONTA_PARA_AGENTE if is_super_admin(pessoa) else LABEL_TRIAGEM
    return [fila, LABEL_DO_TIPO["defeito"]]


def enviar(supabase, *, demanda_id: str, pessoa: dict[str, Any]) -> dict[str, Any]:
    """Cria a issue do relato e devolve a Demanda vinculada."""
    demanda = _relato_aberto(supabase, demanda_id, pessoa)
    conversa = (supabase.table(TABELA_DA_CONVERSA).select("*").eq("demanda_id", demanda_id).execute().data or [{}])[0]
    dados = conversa.get("resumo") or resumo(Respostas())
    produtos = supabase.table(TABELA_PRODUTOS).select("id, nome").eq("id", demanda.get("produto_id")).execute()
    produto_nome = (produtos.data or [{}])[0].get("nome") or ""
    imagens, documentos = tecnologia_anexos.quantos_guardados(supabase, demanda_id)

    def corpo(_titulo: str) -> str:
        return corpo_da_issue_do_bug(
            demanda_id=demanda_id,
            resumo=dados,
            produto_nome=produto_nome,
            link=link_da_demanda(demanda_id),
            anexos=imagens,
            documentos=documentos,
            quem_relatou=QUEM_RELATOU,
            como_chegou=COMO_CHEGOU,
        )

    dono = login_para_publicar(settings.github_login_dono)
    try:
        envio = tecnologia_envio.enviar(
            supabase,
            demanda=demanda,
            ator=pessoa,
            corpo=corpo,
            assignees=[dono] if dono else [],
            labels=labels_do_relato(pessoa),
            responsavel_id=None,
        )
    except tecnologia_envio.EnvioEmAndamentoError as exc:
        raise RelatoRecusadoError(MOTIVO_ENVIANDO, 409) from exc
    except tecnologia_envio.DemandaSumiuError as exc:
        raise RelatoRecusadoError(MOTIVO_NAO_ENCONTRADO, 404) from exc
    if envio.integracao_desligada:
        raise RelatoRecusadoError(MOTIVO_GITHUB_DESLIGADO, 503)
    if not envio.criado:
        raise RelatoRecusadoError(MOTIVO_GITHUB_FORA, 502)
    supabase.table(TABELA_DA_CONVERSA).update({"estado": ESTADO_ENVIADO}).eq("demanda_id", demanda_id).execute()
    return envio.demanda
