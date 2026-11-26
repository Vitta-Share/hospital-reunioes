"""A escrita na Conversa da Demanda, pelas duas portas (issue #1805, ADR 0096).

A tela da aba Tecnologia (ADR 0083, decisao 8) e a ponte de automacao, pela
qual a sessao do terminal de um Desenvolvedor escreve no perfil dele (a
Mensagem pelo terminal), gravam a mensagem e avisam por aqui. O que muda entre
as duas e a origem, guardada na linha (migration 161), e quem e avisado:

- pela tela, a regra da conversa (`quem_avisar`): mencao, Responsavel ou autor;
- pelo terminal, a regra dos avisos de entrega (`tecnologia_avisos`): no card
  da Vitta a diretoria, no card do diretor quem abriu a Demanda. O terminal
  nao manda nome de ninguem (ADR 0096, decisao 4);
- pelo terminal com Destinatario, so ele, em qualquer Origem (ADR 0106).

Com "pede resposta" (ADR 0106), o sino diz "Pede sua resposta" com o Assunto
e o e-mail tem o assunto "<Nome> pede sua resposta: <Assunto>".

Sino e e-mail para cada um, como qualquer mensagem da conversa. Nada daqui vai
para o GitHub.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.dependencies import selecionar_participantes
from app.services import tecnologia_avisos, tecnologia_email
from app.services.notificacao_service import criar_notificacao_tecnologia
from app.services.paginacao import ler_tudo
from app.services.tecnologia import TABELA_CONVERSA_DA_DEMANDA, e_desenvolvedor, quem_avisar
from app.services.tecnologia_vinculo import normalizar_github_login

ORIGEM_TERMINAL = "terminal"


def desenvolvedor_do_login(supabase, login: str | None) -> dict[str, Any] | None:
    """O Desenvolvedor ativo dono deste login do GitHub, ou `None`.

    O login chega como a pessoa digitou; o cadastro guarda em minusculas
    (`normalizar_github_login`). Login de quem esta inativo ou nao e Super
    admin nao serve: a ponte so escreve no perfil de um Desenvolvedor
    (ADR 0096, decisao 2).
    """
    normalizado = normalizar_github_login(login)
    if normalizado is None:
        return None
    result = selecionar_participantes(
        supabase,
        "id, nome_completo, access_profile, is_super_admin, github_login, ativo",
        lambda q: q.eq("github_login", normalizado),
    )
    return next((p for p in result.data or [] if p.get("ativo") is not False and e_desenvolvedor(p)), None)


def e_participante_ativo(supabase, participante_id: str) -> bool:
    """O Destinatário da mensagem pela ponte (ADR 0106) existe e está ativo.
    A ponte recusa antes de gravar: a mensagem nunca some num aviso sem dono."""
    result = selecionar_participantes(supabase, "id, ativo", lambda q: q.eq("id", participante_id))
    return any(p.get("ativo") is not False for p in result.data or [])


def _destinatarios(
    supabase,
    demanda: dict[str, Any],
    *,
    autor_id: str,
    origem: str,
    mencoes: Sequence[str],
    destinatario_id: str | None = None,
) -> list[str]:
    if destinatario_id is not None:
        return [destinatario_id]
    if origem == ORIGEM_TERMINAL:
        return [d for d in tecnologia_avisos.destinatarios(supabase, demanda) if d != str(autor_id)]
    ja_escreveram = [
        str(m["autor_id"])
        for m in (
            supabase.table(TABELA_CONVERSA_DA_DEMANDA).select("autor_id").eq("demanda_id", demanda["id"]).execute().data
            or []
        )
        if m.get("autor_id")
    ]
    return quem_avisar(demanda, autor_id=autor_id, mencoes=list(mencoes), ja_escreveram=ja_escreveram)


def escrever(
    supabase,
    demanda: dict[str, Any],
    *,
    autor: dict[str, Any],
    texto: str,
    origem: str,
    mencoes: Sequence[str] = (),
    destinatario_id: str | None = None,
    pede_resposta_sobre: str | None = None,
    pergunta_id: str | None = None,
    pede_acao: bool = False,
) -> dict[str, Any]:
    """Grava a mensagem de `autor` na Demanda e avisa quem a regra da `origem`
    manda. Devolve a linha gravada. Quem e avisado se calcula antes de gravar:
    "quem ja escreveu" nao conta a propria mensagem."""
    autor_id = str(autor["id"])
    destinatarios = _destinatarios(
        supabase, demanda, autor_id=autor_id, origem=origem, mencoes=mencoes, destinatario_id=destinatario_id
    )
    [linha] = (
        supabase.table(TABELA_CONVERSA_DA_DEMANDA)
        .insert(
            {
                "demanda_id": demanda["id"],
                "autor_id": autor["id"],
                "texto": texto,
                "mencoes": list(mencoes),
                "origem": origem,
            }
        )
        .execute()
        .data
    )
    nome = autor.get("nome_completo") or ""
    for destinatario in destinatarios:
        if pede_resposta_sobre and pede_acao:
            # ADR 0110: o Passo a passo da Vitta pede que a pessoa faça.
            aviso = f"{nome} pede sua ação"
            titulo_do_sino, linha_do_sino = "Pede sua ação", pede_resposta_sobre
        elif pede_resposta_sobre:
            # ADR 0106: a pergunta que espera alguém diz isso e o Assunto.
            aviso = f"{nome} pede sua resposta"
            titulo_do_sino, linha_do_sino = "Pede sua resposta", pede_resposta_sobre
        else:
            aviso = f"{nome} mencionou você" if destinatario in mencoes else f"{nome} escreveu na Demanda"
            titulo_do_sino, linha_do_sino = aviso, str(demanda.get("titulo") or "")[:80]
        criar_notificacao_tecnologia(
            supabase,
            destinatario_id=destinatario,
            titulo=titulo_do_sino,
            mensagem=linha_do_sino,
            demanda_id=str(demanda["id"]),
            pergunta_id=pergunta_id,
        )
        # O mesmo aviso, por e-mail (issue #1538): o diretor não fica com o app aberto.
        tecnologia_email.enviar_aviso_da_conversa(
            supabase,
            destinatario_id=destinatario,
            aviso=aviso,
            autor_nome=nome,
            demanda=demanda,
            assunto=pede_resposta_sobre,
            pergunta_id=pergunta_id,
            acao=pede_acao,
        )
    return linha


def ler(supabase, demanda_id: str, *, depois: datetime | None = None) -> list[dict[str, Any]]:
    """As mensagens da Demanda que chegaram depois de `depois` (todas, sem ele),
    na ordem em que chegaram, com o nome do autor, a data e o texto (issue
    #1806, ADR 0096, decisao 6). Só lê: nada aqui grava nem muda a Etapa.

    A conversa cresce sem teto, então a leitura é paginada pelo `ler_tudo`,
    em ordem total (data e id)."""

    def consulta():
        q = (
            supabase.table(TABELA_CONVERSA_DA_DEMANDA)
            .select("id, autor_id, texto, criado_em")
            .eq("demanda_id", demanda_id)
        )
        if depois is not None:
            q = q.gt("criado_em", depois.isoformat())
        return q.order("criado_em").order("id")

    linhas = ler_tudo(consulta, rotulo="mensagens da Conversa da Demanda")
    ids = sorted({str(linha["autor_id"]) for linha in linhas if linha.get("autor_id")})
    nomes: dict[str, str] = {}
    if ids:
        result = selecionar_participantes(supabase, "id, nome_completo", lambda q: q.in_("id", ids))
        nomes = {str(p["id"]): p.get("nome_completo") or "" for p in result.data or []}
    return [
        {
            "autor": nomes.get(str(linha.get("autor_id"))),
            "criado_em": linha.get("criado_em"),
            "texto": linha.get("texto") or "",
        }
        for linha in linhas
    ]
