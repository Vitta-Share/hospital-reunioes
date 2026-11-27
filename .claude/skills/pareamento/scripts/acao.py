#!/usr/bin/env python3
"""A porta da Ala Pareamento do PedroOS para os dados e as ações do pareamento.

O servidor do PedroOS chama este script e lê o JSON que ele imprime:

  dados                                  os dados da Ala: projetos, PRDs, cards (sem o corpo), filas,
                                         rascunhos de passagem, o que já foi feito e a aderência
  sessao --tipo T --chave K              o pedido da sessão de um card: {projeto, nome, prompt}
  sessao --tipo onda --projeto P         o pedido da onda de um Projeto
  sessao --tipo atualizar                o pedido da sessão que roda o /pareamento
  passar --chave K                       passa o card ao diretor (rascunho JSON na entrada padrão)
  bloqueio --chave K --espera M          grava o bloqueio nativo que só estava no texto

Erro sai como {"erro": "..."} e código 2. O navegador manda só o tipo e o card: o texto de cada
sessão sai do acoes.py, e o que muda no GitHub passa pelas regras de cada ação.

Uso: python3 .claude/skills/pareamento/scripts/acao.py <comando> [--pasta DIR] [...]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import acoes  # noqa: E402
import aderencia  # noqa: E402
import montar  # noqa: E402
import passagem  # noqa: E402

PASTA = AQUI.parents[3] / "local" / "pareamento"


def ler(pasta: Path, nome: str, padrao):
    arq = pasta / nome
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else padrao


def marcar(pasta: Path, chave: str) -> None:
    dados = ler(pasta, "feitos.json", {})
    dados[chave] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (pasta / "feitos.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def repo_de(estado: dict, projeto: str) -> str:
    return next(p["repo"] for p in estado["projetos"] if p["nome"] == projeto)


def dados(pasta: Path, agora: datetime | None = None) -> dict:
    estado = ler(pasta, "estado.json", None)
    if estado is None:
        raise ValueError("o pareamento ainda não foi coletado: clique em Atualizar")
    descricoes, passagens, feitos = ler(pasta, "descricoes.json", {}), ler(pasta, "passagens.json", {}), ler(pasta, "feitos.json", {})
    pagina, sem = montar.dados_da_pagina(estado, descricoes, passagens)
    for k, c in pagina["cards"].items():
        c["extras"] = acoes.acoes_extra(estado["cards"][k])
    rotulos = dict(acoes.TIPOS)
    return {**pagina, "sem_descricao": sem, "feitos": feitos, "rotulos": rotulos,
            "aderencia": aderencia.aderencia(estado, descricoes, passagens, feitos, agora)}


def sessao(pasta: Path, tipo: str, chave: str | None = None, projeto: str | None = None) -> dict:
    if tipo == "atualizar":
        return {"projeto": "Hospital", "nome": "par-atualizar", "prompt": acoes.pedido_da_atualizacao()}
    if tipo == "onda":
        if projeto not in acoes.PASTAS:
            raise ValueError("Projeto desconhecido")
        return {"projeto": projeto, "nome": f"par-{projeto.lower()[:4]}-onda", "prompt": acoes.pedido_da_onda(projeto)}
    estado = ler(pasta, "estado.json", {"cards": {}, "projetos": []})
    card = estado["cards"].get(chave or "")
    if not card:
        raise ValueError("card fora do pareamento; atualize")
    desc = ler(pasta, "descricoes.json", {}).get(chave)
    prompt = acoes.pedido(tipo, card, repo_de(estado, card["projeto"]), desc)
    return {"projeto": card["projeto"], "nome": acoes.nome_da_sessao(tipo, chave), "prompt": prompt}


def passar(pasta: Path, chave: str, rascunho: dict, executar=passagem.passar) -> dict:
    estado = ler(pasta, "estado.json", {"cards": {}, "projetos": []})
    card = estado["cards"].get(chave or "")
    if not card or card["dono"] != "eu":
        raise ValueError("só card seu passa ao diretor")
    r = executar(repo_de(estado, card["projeto"]), card["numero"], rascunho)
    marcar(pasta, f"passado:{chave}")
    return r


def bloqueio(pasta: Path, chave: str, espera: str, gh=passagem._gh) -> dict:
    estado = ler(pasta, "estado.json", {"cards": {}, "projetos": []})
    card = estado["cards"].get(chave or "")
    if not card or espera not in (card.get("no_texto") or []):
        raise ValueError("esse bloqueio não está no texto do card")
    repo = repo_de(estado, card["projeto"])
    alvo = json.loads(gh("api", f"repos/{repo}/issues/{espera.split('#')[1]}"))
    gh("api", "-X", "POST", f"repos/{repo}/issues/{card['numero']}/dependencies/blocked_by", "-F", f"issue_id={alvo['id']}")
    marcar(pasta, f"bloqueio:{chave}:{espera}")
    return {"ok": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("comando", choices=["dados", "sessao", "passar", "bloqueio"])
    ap.add_argument("--pasta", type=Path, default=PASTA)
    ap.add_argument("--tipo")
    ap.add_argument("--chave")
    ap.add_argument("--projeto")
    ap.add_argument("--espera")
    a = ap.parse_args(argv)
    try:
        if a.comando == "dados":
            r = dados(a.pasta)
        elif a.comando == "sessao":
            r = sessao(a.pasta, a.tipo, a.chave, a.projeto)
        elif a.comando == "passar":
            r = passar(a.pasta, a.chave, json.loads(sys.stdin.read() or "{}"))
        else:
            r = bloqueio(a.pasta, a.chave, a.espera)
    except (ValueError, RuntimeError, KeyError, StopIteration) as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
