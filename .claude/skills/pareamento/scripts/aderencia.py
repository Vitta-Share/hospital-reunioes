"""A aderência do pareamento: o quanto a troca de cards entre o Pedro e o diretor segue a ADR 0113.

Cada checagem olha um card (ou a coleta) e diz se está ok, justificado ou faltando. O que falta
vem com a recomendação e a ação que resolve, que a Ala Pareamento do PedroOS mostra como botão.
Justificado é o que o Pedro decidiu segurar (próximo passo "esperar" com o motivo escrito): conta
a favor, porque é uma decisão e não um esquecimento.
"""

from __future__ import annotations

from datetime import datetime, timezone

HORAS_DA_COLETA = 12
DIAS_PARADO = 3
EXPLICACAO = ("🔁 Por que este card", "👔 Para o diretor")
# A ordem em que a Ala mostra o que falta: o que destrava mais gente primeiro.
PESO = {"voltou": 0, "bloqueio": 1, "explicar": 2, "cobrar": 3, "diretor": 4, "limpar": 5, "atualizar": 6}


def _quando(iso: str) -> datetime | None:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _item(chave, regra, estado, titulo, motivo, recomendacao="", acao=None):
    return {"chave": chave, "regra": regra, "estado": estado, "titulo": titulo, "motivo": motivo,
            "recomendacao": recomendacao, "acao": acao}


def checagens(estado: dict, descricoes: dict, passagens: dict, feitos: dict, agora: datetime | None = None) -> list[dict]:
    agora = agora or datetime.now(timezone.utc)
    itens = []
    gerado = _quando(estado.get("gerado_em", ""))
    horas = (agora - gerado).total_seconds() / 3600 if gerado else 999
    fresco = horas <= HORAS_DA_COLETA
    itens.append(_item(None, "coleta", "ok" if fresco else "falta", "Os dados são de agora",
                       f"Coletados há {horas:.0f} h." if gerado else "Nunca coletado.",
                       "Atualize: a sessão lê o GitHub de novo e descreve o que mudou.", {"tipo": "atualizar"}))
    for k, c in sorted(estado["cards"].items()):
        if c.get("satelite") or c["dono"] not in ("eu", "diretor", "agente"):
            continue
        d = descricoes.get(k) or {}
        corpo = c.get("corpo") or ""
        if c["dono"] == "diretor":
            explicado = any(m in corpo for m in EXPLICACAO)
            itens.append(_item(k, "explicado", "ok" if explicado else "falta", "O diretor sabe por que tem o card",
                               "A descrição diz por que está com ele." if explicado else "A descrição não diz por que o card está com ele.",
                               "Escreva no card a parte \"Por que este card passou para você\", para o Claude dele explicar.",
                               {"tipo": "explicar", "chave": k}))
            if c["livre"] and explicado:
                mexido = _quando(c.get("atualizado", ""))
                dias = (agora - mexido).days if mexido else 0
                itens.append(_item(k, "andando", "ok" if dias < DIAS_PARADO else "falta", "O card do diretor está andando",
                                   f"Parado há {dias} dias." if dias else "Mexido hoje.",
                                   "Lembre o diretor no próprio card, com uma menção e o que falta, sem mensagem por fora.",
                                   {"tipo": "cobrar", "chave": k}))
        if c["dono"] == "eu" and c.get("voltou"):
            itens.append(_item(k, "voltou", "falta", "A resposta do diretor foi gravada",
                               "Ele respondeu e devolveu o card, que ainda está como pergunta.",
                               "Grave a resposta dele no card e solte para o time.", {"tipo": "voltou", "chave": k}))
        for m in c.get("no_texto") or []:
            if feitos.get(f"bloqueio:{k}:{m}"):
                continue
            itens.append(_item(k, "bloqueio", "falta", "O GitHub sabe o que o card espera",
                               f"O texto diz que espera o {m}, mas o bloqueio não está gravado.",
                               "Grave o bloqueio: o card passa a aparecer preso até o outro fechar.",
                               {"tipo": "bloqueio", "chave": k, "espera": m}))
        if c["dono"] == "eu" and c["livre"] and not c.get("voltou"):
            tem = bool(d.get("proximo"))
            itens.append(_item(k, "proximo", "ok" if tem else "falta", "O card tem próximo passo",
                               d.get("proximo_porque", "") if tem else "Ninguém disse ainda qual é o próximo passo.",
                               "Atualize: o Claude classifica o card e diz o caminho.", {"tipo": "atualizar"}))
            if d.get("proximo") == "diretor" and not feitos.get(f"passado:{k}"):
                pronto = (passagens.get(k) or {}).get("versao") == c.get("versao")
                itens.append(_item(k, "passagem", "ok" if pronto else "falta", "A passagem ao diretor está escrita",
                                   "O rascunho está pronto para mandar." if pronto else "O card precisa ir ao diretor e não tem rascunho.",
                                   "Prepare a passagem com o Claude e mande.", {"tipo": "diretor", "chave": k}))
        com = [lab for lab in c.get("labels") or [] if lab.startswith("com:")]
        if com:
            segura = d.get("proximo") == "esperar" and d.get("proximo_porque")
            itens.append(_item(k, "comunicacao", "justificado" if segura else "falta", "Sem card de comunicação solto",
                               d["proximo_porque"] if segura else f"Ainda tem a etiqueta {com[0]}, que a ADR 0113 aposentou.",
                               "Pela ADR 0113, o card de comunicação vira card do diretor, se ainda vale, ou fecha com o motivo.",
                               {"tipo": "limpar", "chave": k}))
    return itens


def aderencia(estado: dict, descricoes: dict, passagens: dict, feitos: dict, agora: datetime | None = None) -> dict:
    itens = checagens(estado, descricoes, passagens, feitos, agora)
    bons = sum(1 for i in itens if i["estado"] != "falta")
    faltam = sorted((i for i in itens if i["estado"] == "falta"), key=lambda i: (PESO.get(i["acao"]["tipo"], 9), i["chave"] or ""))
    return {
        "nota": round(100 * bons / len(itens)) if itens else 100,
        "total": len(itens),
        "ok": sum(1 for i in itens if i["estado"] == "ok"),
        "justificados": [i for i in itens if i["estado"] == "justificado"],
        "faltam": faltam,
    }
