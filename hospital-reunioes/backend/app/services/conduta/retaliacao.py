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
(migration 229).
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
    return bool(linhas[0].get("denunciante_informou_em")) or bool(
        afastamento._nomes_de_quem_relatou(supabase, linhas[0])
    )


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


def _exigir_coordenacao(aberto: CasoAberto) -> None:
    if aberto.pessoa.papel != "coordenacao":
        raise VerificacaoRecusadaError(403, "Só a coordenação registra a verificação.")


def _exigir_acompanhamento(supabase, caso: dict[str, Any]) -> None:
    if not acompanha(supabase, caso):
        raise VerificacaoRecusadaError(409, "Este caso não tem verificação de retaliação.")


def registrar(supabase, aberto: CasoAberto, *, marco: int, houve: bool, observacao: str, hoje: date) -> dict:
    """REGISTRAR VERIFICAÇÃO: houve ou não houve mudança desfavorável para
    quem relatou, com a observação se a coordenação quiser."""
    _exigir_coordenacao(aberto)
    caso = aberto.caso
    if marco not in MARCOS:
        raise VerificacaoRecusadaError(422, "A verificação é de 30, 90 ou 180 dias.")
    _exigir_acompanhamento(supabase, caso)
    if data_da_verificacao(caso["encerrado_em"], marco) > hoje:
        raise VerificacaoRecusadaError(409, f"A verificação de {marco} dias ainda não chegou.")
    if marco in _feitas(supabase, caso["id"]):
        raise VerificacaoRecusadaError(409, f"A verificação de {marco} dias já foi registrada.")
    observacao = (observacao or "").strip()
    if len(observacao) > TAMANHO_DA_OBSERVACAO:
        raise VerificacaoRecusadaError(422, f"A observação cabe em {TAMANHO_DA_OBSERVACAO} caracteres.")
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "verificou_retaliacao", f"registrou a verificação de {marco} dias"
    )
    try:
        return (
            supabase.table(TABELA)
            .insert(
                {
                    "caso_id": caso["id"],
                    "marco": marco,
                    "houve": houve,
                    "observacao_cifrada": cifra.cifrar_texto(observacao) if observacao else None,
                    "verificada_por": aberto.autor_id,
                    "verificada_em": agora_utc().isoformat(),
                }
            )
            .execute()
            .data[0]
        )
    except APIError as erro:
        if getattr(erro, "code", None) == "23505":
            raise VerificacaoRecusadaError(409, f"A verificação de {marco} dias já foi registrada.") from erro
        raise


def _relato_da_retaliacao(protocolo: str, marco: int, observacao: str | None) -> str:
    relato = (
        f"Caso aberto pela coordenação do Comitê na verificação de retaliação de {marco} dias do caso {protocolo}: "
        "houve mudança desfavorável para quem relatou."
    )
    return f"{relato}\n\nObservação da verificação: {observacao}" if observacao else relato


def abrir_caso_de_retaliacao(supabase, aberto: CasoAberto, *, marco: int) -> dict:
    """ABRIR CASO DE RETALIAÇÃO: a verificação em que houve mudança
    desfavorável vira um caso novo, que entra na triagem da fila comum. Um
    por verificação."""
    if aberto.pessoa.papel != "coordenacao":
        raise VerificacaoRecusadaError(403, "Só a coordenação abre o caso novo de retaliação.")
    caso = aberto.caso
    _exigir_acompanhamento(supabase, caso)
    feita = _feitas(supabase, caso["id"]).get(marco)
    if not feita or not feita["houve"]:
        raise VerificacaoRecusadaError(409, "Só a verificação em que houve mudança desfavorável abre caso novo.")
    if feita.get("caso_novo_id"):
        raise VerificacaoRecusadaError(409, "O caso novo desta verificação já foi aberto.")
    observacao = cifra.decifrar_texto(feita["observacao_cifrada"]) if feita.get("observacao_cifrada") else None
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "abriu_caso_de_retaliacao",
        f"abriu caso novo de retaliação na verificação de {marco} dias",
    )
    novo = casos.registrar_caso(
        supabase,
        relato=_relato_da_retaliacao(caso["protocolo"], marco, observacao),
        categoria=CATEGORIA_DA_RETALIACAO,
    )
    ligadas = (
        supabase.table(TABELA)
        .update({"caso_novo_id": novo["id"]})
        .eq("id", feita["id"])
        .is_("caso_novo_id", "null")
        .execute()
        .data
    )
    if not ligadas:
        raise VerificacaoRecusadaError(409, "O caso novo desta verificação já foi aberto.")
    return {"id": novo["id"], "protocolo": novo["protocolo"]}


def _protocolos(supabase, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    linhas = supabase.table("conduta_casos").select("id, protocolo").in_("id", ids).execute().data or []
    return {linha["id"]: linha["protocolo"] for linha in linhas}


def _marco_na_tela(marco: int, dia: date, hoje: date, feita: dict | None, autores, novos, coordena: bool) -> dict:
    if feita is None:
        return {
            "marco": marco,
            "data": dia.isoformat(),
            "situacao": "pendente" if dia <= hoje else "aguardando",
            "houve": None,
            "observacao": None,
            "verificada_por": None,
            "verificada_em": None,
            "caso_novo": None,
            "pode_abrir_caso_novo": False,
        }
    novo = feita.get("caso_novo_id")
    observacao = feita.get("observacao_cifrada")
    return {
        "marco": marco,
        "data": dia.isoformat(),
        "situacao": "verificada",
        "houve": feita["houve"],
        "observacao": cifra.decifrar_texto(observacao) if observacao else None,
        "verificada_por": autores.get(feita["verificada_por"], ""),
        "verificada_em": feita.get("verificada_em"),
        "caso_novo": {"id": novo, "protocolo": novos.get(novo, "")} if novo else None,
        "pode_abrir_caso_novo": coordena and feita["houve"] and not novo,
    }


def para_a_tela(supabase, aberto: CasoAberto, hoje: date) -> dict[str, Any]:
    """A área "Acompanhamento" da tela do caso concluído: as três
    verificações, cada uma aguardando o dia, pendente ou verificada."""
    caso = aberto.caso
    if not acompanha(supabase, caso):
        return {"verificacao_de_retaliacao": None}
    coordena = aberto.pessoa.papel == "coordenacao"
    feitas = _feitas(supabase, caso["id"])
    autores = membros.nomes(supabase, sorted({f["verificada_por"] for f in feitas.values()}))
    novos = _protocolos(supabase, [f["caso_novo_id"] for f in feitas.values() if f.get("caso_novo_id")])
    marcos = [
        _marco_na_tela(
            marco, data_da_verificacao(caso["encerrado_em"], marco), hoje, feitas.get(marco), autores, novos, coordena
        )
        for marco in MARCOS
    ]
    proximo = next((m["marco"] for m in marcos if m["situacao"] == "pendente"), None)
    return {
        "verificacao_de_retaliacao": {
            "marcos": marcos,
            "marco_pendente": proximo,
            "pode_registrar": coordena and proximo is not None,
        }
    }
