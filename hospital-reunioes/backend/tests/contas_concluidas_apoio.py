"""As Contas concluídas da ALFA que os testes do Auditor e do Revisor semeiam.

Doze Contas concluídas da ALFA, cada uma com o item, os eventos que a IA leu e
o Guia, no dublê do banco da carga da operadora. Saiu do teste da prova nas
últimas Contas quando ela foi retirada (issue #1920, ADR 0102).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from test_contas_medicas_memoria_tela import _operadora_id, _versao

MIGRATION_126 = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "126_contas_medicas_auditor.sql"
KIT = Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "contas-medicas.md"


def _dia(n: int) -> str:
    return f"2026-10-{n:02d}"


def _semear(banco) -> None:
    """Doze Contas concluídas da ALFA, uma por dia de 01 a 12/10, cada uma no
    seu atendimento e com o item M0nn; mais uma A fazer da ALFA e uma
    concluída da BETA, as duas mais novas que todas."""
    alfa, beta = _operadora_id(banco, "ALFA"), _operadora_id(banco, "BETA")
    versao = _versao(banco, "ALFA", "1.0")["id"]
    atendimentos, contas, itens, eventos = [], [], [], []

    def conta(n: int, operadora: str, situacao: str, concluida_em: str | None) -> None:
        atendimento = f"at-{n:02d}"
        atendimentos.append({"id": atendimento, "numero_atendimento": f"31{n:03d}", "operadora_id": operadora})
        contas.append(
            {
                "id": f"c{n:02d}",
                "atendimento_id": atendimento,
                "numero_conta": f"N{n:02d}",
                "situacao": situacao,
                "periodo_inicio": _dia(n),
                "periodo_fim": _dia(n),
                "concluida_em": concluida_em,
                "memoria_versao_id": versao,
                "nota_entrada": 90.0,
                "custo_usd": 0.5,
            }
        )
        itens.append(
            {
                "id": f"i{n:02d}",
                "conta_id": f"c{n:02d}",
                "ordem": 1,
                "data": _dia(n),
                "grupo_conta": "MATERIAL",
                "setor": "UTI",
                "grupo_procedimento": None,
                "codigo": f"M{n:03d}",
                "descricao": f"Item M{n:03d}",
                "quantidade": 1,
                "unidade": "UN",
                "valor_unitario": 10.0,
                "valor_total": 10.0,
                "percentual": 100.0,
            }
        )
        eventos.append(
            {
                "id": f"ev{n:02d}",
                "atendimento_id": atendimento,
                "criado_em": f"{_dia(n)}T08:00:00+00:00",
                "eventos_json": {
                    "arquivo_id": f"arq-{n:02d}",
                    "ia": {"movimentacoes": [], "prescricoes": [], "observacoes": [f"evento do dia {n}"]},
                },
            }
        )

    for n in range(1, 13):
        conta(n, alfa, "CONCLUIDA", f"{_dia(n)}T18:00:00+00:00")
    conta(13, alfa, "A_FAZER", None)
    conta(14, beta, "CONCLUIDA", f"{_dia(14)}T18:00:00+00:00")
    banco.tabelas["cm_atendimento"] = atendimentos
    banco.tabelas["cm_conta"] = contas
    banco.tabelas["cm_conta_item"] = itens
    banco.tabelas["cm_eventos"] = eventos
    banco.tabelas["cm_guia_linha"] = []


def _linha_do_guia(conta: str, codigo: str, dia: str, devida: float, estado: str = "ABERTA") -> dict[str, Any]:
    return {
        "id": f"g-{conta}-{codigo}",
        "conta_id": conta,
        "acao": "INCLUIR",
        "data": dia,
        "data_fim": None,
        "setor": "UTI",
        "codigo": codigo,
        "descricao": f"Item {codigo}",
        "quantidade_lancada": 1.0,
        "quantidade_devida": devida,
        "regra_codigo": "ALFA-DIA-01",
        "motivo": "Dado na evolução.",
        "estado": estado,
        "origem": "IA",
    }


def _passos_do_check() -> set[str]:
    sql = MIGRATION_126.read_text(encoding="utf-8")
    bloco = re.search(r"cm_chamada_ia_passo_check\s+CHECK \(passo IN \(([^)]*)\)\)", sql)
    return set(re.findall(r"'(\w+)'", bloco.group(1)))
