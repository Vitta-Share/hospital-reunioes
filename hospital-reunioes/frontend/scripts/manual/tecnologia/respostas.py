#!/usr/bin/env python3
"""As respostas de exemplo da aba Tecnologia para os prints do manual (issue
#1727, ADR 0094, decisão 5; refeitas na issue #2282, ADR 0113).

Imprime, em JSON, a tabela que o `roteiro.sh` serve no lugar do backend: a
chave é a rota depois de `/api/admin/tecnologia/`, com a consulta quando há
(`chat?projeto=ana`), e o valor é o corpo da resposta. Desde a issue #2279 a
aba só lê, e a tabela só tem as rotas de leitura: quem está logado, os
Desenvolvedores, os Projetos, a lista do Quadro e as Entregas. Tudo sai do
`seed.json`, com as datas contadas a partir de hoje, no fuso do hospital:
assim o Quadro abre com as colunas cheias e as Entregas caem nas últimas
semanas, em qualquer dia que o roteiro rodar. Nada aqui é gente, pedido ou
card de verdade.

Uso: python3 scripts/manual/tecnologia/respostas.py
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
SEED = json.loads((AQUI / "seed.json").read_text(encoding="utf-8"))
FUSO = ZoneInfo("America/Sao_Paulo")
HOJE = datetime.now(FUSO).date()
SEMANAS_DO_GRAFICO = 12
# Os dois Projetos cujo repositório o app lê; o resto é projeto novo da Vitta (issue #1967).
PROJETOS_CONHECIDOS = {"hospital": "Aplicativo do Hospital", "ana": "Ana"}


def instante(dias_atras: int, hora: str = "10:00") -> str:
    """O instante de `dias_atras` dias antes de hoje, na hora dada, no fuso do hospital."""
    h, m = (int(p) for p in hora.split(":"))
    return datetime.combine(HOJE - timedelta(days=dias_atras), time(h, m), FUSO).isoformat()


def segunda(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def demanda(d: dict) -> dict:
    """A Demanda como a lista do chat a manda, vista pelo diretor que pediu."""
    registrada = d["etapa"] == "registrada"
    entregue = d.get("entregue_ha")
    entregues, total = d.get("partes", [None, None])
    # Cada parte com o número, a Onda e o que ainda a trava (issue #1903, ADR 0100).
    partes = [
        {
            "o_que_muda": p["o_que_muda"],
            "situacao": "em_producao" if i < entregues else ("em_desenvolvimento" if i == entregues else "planejada"),
            "fechada_em": instante(10 - 3 * i) if i < entregues else None,
            "numero": p["numero"],
            "onda": p["onda"],
            "bloqueadoras": [{"numero": n, "de_outro_pedido": False} for n in p.get("espera", [])]
            + [{"numero": n, "de_outro_pedido": True} for n in p.get("espera_de_outro_pedido", [])],
        }
        for i, p in enumerate(d.get("partes_da_entrega", []))
    ]
    return {
        "id": d["id"],
        "numero": d["numero"],
        "titulo": d["titulo"],
        "criado_em": instante(d["dias"], d["hora"]),
        "etapa": d["etapa"],
        "classificacao": d["classificacao"],
        "projeto": d["projeto"],
        "projeto_nome": d.get("projeto_nome"),
        "raiz_url": d.get("raiz_url"),
        "origem": d["origem"],
        "minha": d["origem"] == "diretor",
        "tem_vinculo": not registrada,
        "responsavel": d.get("responsavel"),
        "partes_entregues": entregues,
        "partes_total": total,
        "partes": partes,
        "o_que_muda": d.get("o_que_muda"),
        "versao": d.get("versao") if d["etapa"] == "em_producao" else None,
        "fechada_em": instante(entregue) if entregue is not None else None,
        "em_producao_em": instante(entregue, "18:00") if d["etapa"] == "em_producao" else None,
        "demonstracao_url": d.get("demonstracao"),
        "demonstracao_em": instante(entregue) if d.get("demonstracao") else None,
        # O atalho Ver o plano (issue #2010): só a página dos planos, com caminho de exemplo.
        "apresentacao_url": d.get("apresentacao"),
        "plano_validado": d.get("plano_validado", False),
        "autor": None,
        "raiz_numero": d.get("raiz_numero"),
        "issue_numero": None,
        "issue_url": None,
        "envio_falhou": False,
        "designacao_falhou": False,
        "envio_motivo": None,
        "implantacao": implantacao_da_demanda(d["id"]),
    }


def implantacao_da_demanda(demanda_id: str) -> dict | None:
    """A seção Implantação do card (issue #2266, ADR 0113, decisão 9), como o
    servidor a manda: um Card de implantação por linha, Feito quando fechado no
    GitHub e Aberto enquanto não, com o dono do card e a espera nula, e os
    feitos sobre o total. Nula na Demanda sem Card de implantação."""
    seed = SEED["implantacao"]
    if demanda_id != seed["demanda"]:
        return None
    pedidos = [
        {
            "titulo": c["titulo"],
            "destinatario": c["dono"],
            "situacao": "feito" if c["fechado"] else "aberto",
            "espera": None,
        }
        for c in seed["cards"]
    ]
    feitos = sum(1 for p in pedidos if p["situacao"] == "feito")
    return {"feitos": feitos, "total": len(pedidos), "pedidos": pedidos}


def entregas(lista: list[dict]) -> dict:
    """O ritmo das 12 semanas e a lista por semana, como a aba Entregas os lê."""
    corrente = segunda(HOJE)
    inicios = [corrente - timedelta(weeks=atras) for atras in range(SEMANAS_DO_GRAFICO - 1, -1, -1)]

    anteriores = [
        {
            **demanda(
                {
                    "id": f"exemplo-entrega-{i}",
                    "numero": 30 + i,
                    "dias": e["entregue_ha"] + 10,
                    "hora": "10:00",
                    "etapa": "em_producao" if e.get("versao") else "entregue",
                    "origem": "diretor" if e["projeto"] == "hospital" else "vitta",
                    **e,
                }
            ),
            "tamanho": e["tamanho"],
        }
        for i, e in enumerate(SEED["entregas_anteriores"], start=1)
    ]
    do_quadro = [{**demanda(d), "tamanho": d["tamanho"]} for d in SEED["demandas"] if "tamanho" in d]
    entregues = sorted(do_quadro + anteriores, key=lambda e: e["fechada_em"], reverse=True)

    def semana_de(e: dict) -> date:
        return segunda(datetime.fromisoformat(e["fechada_em"]).date())

    semanas = []
    for inicio, ritmo in zip(inicios, SEED["ritmo"]):
        saiu = [e for e in entregues if semana_de(e) == inicio]
        contagem = {t.lower(): sum(1 for e in saiu if e["tamanho"] == t) for t in "GMP"} if saiu else {
            t: ritmo[t] for t in "gmp"
        }
        semanas.append(
            {
                "inicio": inicio.isoformat(),
                "pedidos": ritmo["pedidos"],
                **contagem,
                "entregas": [{"titulo": e["titulo"], "tamanho": e["tamanho"], "projeto": e["projeto"]} for e in saiu],
            }
        )

    def soma(trecho: list[dict], *chaves: str) -> int:
        return sum(s[c] for s in trecho for c in chaves)

    topo, antes = semanas[-4:], semanas[-8:-4]
    pedidos = soma(topo, "pedidos")
    bugs = round(pedidos * 0.3)
    grupos = [
        {"inicio": inicio.isoformat(), "entregas": [e for e in entregues if semana_de(e) == inicio]}
        for inicio in reversed(inicios)
        if any(semana_de(e) == inicio for e in entregues)
    ]
    return {
        "topo": {
            "pedidos": {"total": pedidos, "anteriores": soma(antes, "pedidos"), "bugs": bugs, "melhorias": pedidos - bugs},
            "entregas": {
                "total": soma(topo, "g", "m", "p"),
                "anteriores": soma(antes, "g", "m", "p"),
                "g": soma(topo, "g"),
                "m": soma(topo, "m"),
                "p": soma(topo, "p"),
            },
        },
        "semanas": semanas,
        "grupos": grupos,
        "proximo_corte": inicios[0].isoformat(),
        "responsaveis": [{"valor": dev["id"], "nome": dev["nome"]} for dev in SEED["desenvolvedores"]],
    }


def tabela() -> dict:
    lista = [demanda(d) for d in SEED["demandas"]]
    return {
        "eu": {"desenvolvedor": False},
        "desenvolvedores": SEED["desenvolvedores"],
        "chat": lista,
        "chat?projeto=ana": [d for d in lista if d["projeto"] == "ana"],
        "chat?projeto=hospital": [d for d in lista if d["projeto"] == "hospital"],
        "projetos": [{"valor": v, "nome": n} for v, n in PROJETOS_CONHECIDOS.items()]
        + [{"valor": d["projeto"], "nome": d["projeto_nome"]} for d in lista if d["projeto"] not in PROJETOS_CONHECIDOS],
        "entregas": entregas(lista),
    }


if __name__ == "__main__":
    print(json.dumps(tabela(), ensure_ascii=False))
