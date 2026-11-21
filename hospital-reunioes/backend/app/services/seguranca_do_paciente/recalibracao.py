"""O período de sombra e a recalibração do agente do Núcleo (issue #2001,
PRD #1979, ADR 0107 decisão 10; Anexo F, seções 4, 5 e 7).

Três peças, todas sem IA:

- a concordância: quanto a decisão da Presidência concordou com a sugestão do
  agente, por eixo, a partir das divergências que a tela de triagem grava na
  linha da pessoa (migration 197). Os casos em que a Presidência subiu o grau
  de dano sugerido ficam à parte: é o erro que mais importa;
- o lembrete: aos 30 e aos 60 dias da primeira notificação registrada, o job
  diário cria a pendência "Recalibrar o agente do NSP" para quem tem Acesso
  pleno, pela porta de Pendência sem Reunião da Fase 1, sem e-mail. Cada marco
  nasce uma vez só (a chave de `nsp_recalibracoes`, migration 206);
- a tela dos itens do Anexo F (seções 4 e 5): o que já tem dado nesta fase sai
  calculado; o resto aparece como "sem dados nesta fase". Concluir grava a
  decisão (manter, ajustar ou ligar a aprovação em lote), quem e quando.
"""

from __future__ import annotations

from typing import Any

from app.services.seguranca_do_paciente import triagem
from app.services.seguranca_do_paciente.agente_de_triagem import BASE, PROMPT, versao

# Cada eixo e os campos conferidos na triagem que ele junta (Anexo F, seção 4,
# item 2). Marcadores são o evento da lista, IRAS, risco de imagem e protocolo
# básico (Anexo A, seção 6).
EIXOS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("natureza", "Natureza", ("natureza",)),
    ("grau_de_dano", "Grau de dano", ("grau_de_dano",)),
    ("categoria", "Categoria", ("categoria",)),
    ("faixa", "Faixa", ("faixa",)),
    ("canal", "Canal", ("canais",)),
    ("marcadores", "Marcadores", ("evento", "iras", "risco_de_imagem", "protocolo_basico")),
)

# A ordem do grau de dano: o erro para baixo é a decisão acima da sugestão.
_ORDEM_DO_DANO = {"nenhum": 0, "leve": 1, "moderado": 2, "grave": 3, "obito": 4}


def _percentual(parte: int, total: int) -> int | None:
    return round(100 * parte / total) if total else None


def _decisoes(supabase) -> list[dict[str, Any]]:
    """As linhas de pessoa (a triagem confirmada), todas, página a página."""
    return triagem._paginas(
        lambda: supabase.table("nsp_triagens").select("*").eq("autor_tipo", "pessoa").order("criado_em")
    )


def _com_sugestao(supabase, decisoes: list[dict[str, Any]]) -> list[tuple[dict, dict]]:
    """Os pares (decisão, sugestão) dos casos que tiveram sugestão do agente.
    O caso para classificar manualmente (divergências nulas) fica de fora."""
    medidas = [d for d in decisoes if d.get("divergencias") is not None]
    linhas = triagem._triagens_por_notificacao(supabase, [d["notificacao_id"] for d in medidas])
    pares = []
    for decisao in medidas:
        sugestao = triagem._sugestao(linhas.get(decisao["notificacao_id"], []))
        if sugestao is not None:
            pares.append((decisao, sugestao))
    return pares


def _eixos(pares: list[tuple[dict, dict]]) -> list[dict[str, Any]]:
    total = len(pares)
    saida = []
    for eixo, rotulo, campos in EIXOS:
        acatadas = sum(1 for decisao, _ in pares if not set(campos) & set(decisao["divergencias"]))
        saida.append(
            {
                "eixo": eixo,
                "rotulo": rotulo,
                "acatadas": acatadas,
                "total": total,
                "percentual": _percentual(acatadas, total),
            }
        )
    return saida


def _erros_para_baixo(supabase, pares: list[tuple[dict, dict]]) -> list[dict[str, Any]]:
    subidos = [
        (decisao, sugestao)
        for decisao, sugestao in pares
        if _ORDEM_DO_DANO.get(decisao.get("grau_de_dano"), -1) > _ORDEM_DO_DANO.get(sugestao.get("grau_de_dano"), 99)
    ]
    protocolos = _protocolos(supabase, [d["notificacao_id"] for d, _ in subidos])
    return [
        {
            "notificacao_id": decisao["notificacao_id"],
            "protocolo": protocolos.get(decisao["notificacao_id"]),
            "sugerido": sugestao["grau_de_dano"],
            "decidido": decisao["grau_de_dano"],
            "grave_ou_obito": decisao["grau_de_dano"] in ("grave", "obito"),
        }
        for decisao, sugestao in subidos
    ]


def _protocolos(supabase, ids: list[str]) -> dict[str, str]:
    protocolos: dict[str, str] = {}
    for inicio in range(0, len(ids), triagem.LOTE_DE_IDS):
        lote = ids[inicio : inicio + triagem.LOTE_DE_IDS]
        for linha in supabase.table("nsp_notificacoes").select("id, protocolo").in_("id", lote).execute().data or []:
            protocolos[linha["id"]] = linha["protocolo"]
    return protocolos


def concordancia(supabase) -> dict[str, Any]:
    """A concordância por eixo desde o primeiro dia, os erros para baixo e as
    versões do prompt e da base em uso."""
    pares = _com_sugestao(supabase, _decisoes(supabase))
    return {
        "versoes": {"prompt": versao(PROMPT), "base": versao(BASE)},
        "casos": len(pares),
        "eixos": _eixos(pares),
        "erros_para_baixo": _erros_para_baixo(supabase, pares),
    }
