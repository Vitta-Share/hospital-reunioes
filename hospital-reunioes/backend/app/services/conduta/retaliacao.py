"""A verificação de retaliação do Canal de Conduta (issue #1839; especificação,
6.11 e 18).

Concluído o caso (o retorno aprovado), a coordenação verifica em 30, 90 e 180
dias se houve mudança desfavorável para quem relatou: desligamento, escala,
transferência, avaliação. Cada verificação entra em MINHA VEZ no dia dela,
contado do encerramento no fuso de São Paulo, e fica lá até ser registrada;
com mais de uma atrasada, a mais antiga vem primeiro.

Só vale quando se sabe quem relatou (o denunciante identificado ouvido na
Apuração, ou o nome da manifestação que a Ouvidoria sinalizou) ou quando quem
relatou informou algo pela página de acompanhamento
(`conduta_casos.denunciante_informou_em`, gravado pela página de
acompanhamento, issue #1845). Caso anônimo sem aviso não gera tarefa.

A resposta é de um clique, houve ou não houve, com observação opcional e
cifrada. "Houve" oferece abrir um caso novo de retaliação, que entra na
triagem da fila comum, ligado à verificação. O banco tem as mesmas travas
(migration 227).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from postgrest.exceptions import APIError

from app.services.conduta import afastamento, casos, cifra, membros, trilha
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import FUSO, agora_utc

TABELA = "conduta_verificacoes_de_retaliacao"
MARCOS = (30, 90, 180)
TAMANHO_DA_OBSERVACAO = 2000
# Conduta e relações: assédio, discriminação, violência, retaliação (4.4).
CATEGORIA_DA_RETALIACAO = "A"


class VerificacaoRecusadaError(Exception):
    """A ação não pode acontecer agora. `status` vai para a resposta, e a
    mensagem diz o motivo numa linha."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


def data_da_verificacao(encerrado_em: str | datetime, marco: int) -> date:
    """O dia da verificação: o dia do encerramento em São Paulo, mais o marco."""
    momento = datetime.fromisoformat(encerrado_em) if isinstance(encerrado_em, str) else encerrado_em
    return momento.astimezone(FUSO).date() + timedelta(days=marco)


def _concluido(caso: dict[str, Any]) -> bool:
    return bool(caso.get("encerrado_em")) and caso.get("desfecho") == "concluido"


def acompanha(supabase, caso: dict[str, Any]) -> bool:
    """O caso concluído em que se sabe quem relatou, ou em que quem relatou
    avisou algo pela página de acompanhamento."""
    if not _concluido(caso):
        return False
    linhas = (
        supabase.table("conduta_casos")
        .select("id, manifestacao_id, denunciante_informou_em")
        .eq("id", caso["id"])
        .limit(1)
        .execute()
        .data
        or []
    )
    if not linhas:
        return False
    return bool(linhas[0].get("denunciante_informou_em")) or bool(afastamento._nomes_de_quem_relatou(supabase, linhas[0]))


def _feitas(supabase, caso_id: str) -> dict[int, dict]:
    linhas = supabase.table(TABELA).select("*").eq("caso_id", caso_id).execute().data or []
    return {linha["marco"]: linha for linha in linhas}


def _chegaram(caso: dict[str, Any], hoje: date) -> list[int]:
    return [m for m in MARCOS if data_da_verificacao(caso["encerrado_em"], m) <= hoje]


def pendente(supabase, caso: dict[str, Any], hoje: date) -> int | None:
    """O marco da verificação que depende da coordenação hoje: o primeiro que
    já chegou e não foi registrado. None fora do acompanhamento."""
    if not _concluido(caso):
        return None
    chegaram = _chegaram(caso, hoje)
    if not chegaram or not acompanha(supabase, caso):
        return None
    feitas = _feitas(supabase, caso["id"])
    return next((m for m in chegaram if m not in feitas), None)
