"""O teste de aceite do agente de triagem do Canal de Conduta (issue #1827,
ADR 0097 decisão 15, Anexo B da especificação).

Roda os 12 casos fictícios do Anexo B (`tests/fixtures/conduta/`) três vezes
cada, pela mesma função que o app usa na entrada do caso (`ler_o_relato`, com
a mesma mensagem pseudonimizada), e imprime as metas em Markdown, para colar
no corpo do PR. As metas, em cada rodada: escopo e sinal de Rota Especial
certos nos 12, categoria e rito certos em pelo menos 10, e nenhum caso com
termo da regra de proteção classificado como FORA.

Manual e fora do CI: o comando gasta dinheiro de verdade. Antes de chamar a
IA ele mostra quantas chamadas faz e a estimativa de custo, e só segue se a
pessoa digitar `rodar`. Toda mudança no prompt repete o teste.

    cd hospital-reunioes/backend
    uv run python -m scripts.conduta_teste_de_aceite [--modelo claude-sonnet-5-5] [--saida resultado.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.services.conduta import agente_de_triagem as agente
from app.services.ia_chaves import ClienteDaAnthropic
from app.services.prompt_loader import load_prompt

CASOS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "conduta" / "casos-anexo-b.json"
VEZES = 3
CONFIRMACAO = "rodar"
MINIMO_DE_ACERTOS = 10

# Preço por milhão de tokens: entrada, saída, leitura de cache, escrita de cache.
PRECOS = {
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}
CARACTERES_POR_TOKEN = 3.5
TOKENS_DE_SAIDA = 1500


def carregar_casos() -> list[dict]:
    return json.loads(CASOS.read_text(encoding="utf-8"))


def mensagem(caso: dict) -> str:
    return agente.montar_mensagem(caso["relato"], categoria=None, anteriores=[])


def estimativa(casos: list[dict], modelo: str, vezes: int = VEZES) -> dict:
    """Quantas chamadas e quanto custa, sem chamar ninguém."""
    chamadas = len(casos) * vezes
    sistema = len(load_prompt(agente.PROMPT)) / CARACTERES_POR_TOKEN
    entrada = sum(len(mensagem(caso)) for caso in casos) * vezes / CARACTERES_POR_TOKEN
    preco = PRECOS.get(modelo)
    custo = None
    if preco:
        p_entrada, p_saida, p_leitura, p_escrita = preco
        custo = (
            entrada * p_entrada
            + chamadas * TOKENS_DE_SAIDA * p_saida
            + sistema * p_escrita
            + sistema * (chamadas - 1) * p_leitura
        ) / 1_000_000
    return {"chamadas": chamadas, "custo_usd": custo}


def rodar(cliente, casos: list[dict], modelo: str, vezes: int = VEZES) -> list[dict]:
    """Cada caso `vezes` vezes, pela função do app, sem a cota do banco."""
    resultados = []
    for rodada in range(1, vezes + 1):
        for caso in casos:
            leitura = agente.ler_o_relato(cliente, mensagem(caso), modelo=modelo)
            resultados.append(
                {
                    "id": caso["id"],
                    "rodada": rodada,
                    "sugestao": leitura.sugestao,
                    "motivo_manual": leitura.motivo_manual,
                    "violacoes": leitura.violacoes,
                }
            )
    return resultados


def _valor(sugestao: dict | None, item: str) -> str | None:
    return sugestao[item]["valor"] if sugestao else None


def metricas(casos: list[dict], resultados: list[dict]) -> list[dict]:
    """As metas do Anexo B, rodada a rodada. Rodada sem sugestão conta como erro."""
    por_id = {caso["id"]: caso for caso in casos}
    rodadas = sorted({r["rodada"] for r in resultados})

    def erros(item: str) -> dict[int, list[int]]:
        return {
            n: sorted(
                r["id"]
                for r in resultados
                if r["rodada"] == n and _valor(r["sugestao"], item) != por_id[r["id"]]["gabarito"][item]
            )
            for n in rodadas
        }

    def texto(por_rodada: dict[int, list[int]]) -> str:
        return "; ".join(f"rodada {n}: {len(casos) - len(e)} de {len(casos)}" for n, e in por_rodada.items())

    escopo, especial, categoria, rito = erros("escopo"), erros("especial"), erros("categoria"), erros("rito")
    protegidos_fora = sorted(
        {
            r["id"]
            for r in resultados
            if por_id[r["id"]]["termo_de_protecao"] and _valor(r["sugestao"], "escopo") == "FORA"
        }
    )
    nsp = [r for r in resultados if por_id[r["id"]]["gabarito"].get("sinalizar_nsp") == "SIM"]
    nsp_ok = sum(_valor(r["sugestao"], "sinalizar_nsp") == "SIM" for r in nsp)
    risco = sum(
        _valor(r["sugestao"], "risco_imediato") == por_id[r["id"]]["gabarito"]["risco_imediato"] for r in resultados
    )
    sem_sugestao = [r for r in resultados if r["sugestao"] is None]
    return [
        {
            "criterio": "Escopo certo nos 12",
            "resultado": texto(escopo),
            "meta": "12 em cada rodada",
            "bateu": not any(escopo.values()),
            "impede": True,
        },
        {
            "criterio": "Sinal de Rota Especial certo nos 12",
            "resultado": texto(especial),
            "meta": "12 em cada rodada",
            "bateu": not any(especial.values()),
            "impede": True,
        },
        {
            "criterio": "Categoria certa",
            "resultado": texto(categoria),
            "meta": f"{MINIMO_DE_ACERTOS} ou mais em cada rodada",
            "bateu": all(len(casos) - len(e) >= MINIMO_DE_ACERTOS for e in categoria.values()),
            "impede": True,
        },
        {
            "criterio": "Rito certo",
            "resultado": texto(rito),
            "meta": f"{MINIMO_DE_ACERTOS} ou mais em cada rodada",
            "bateu": all(len(casos) - len(e) >= MINIMO_DE_ACERTOS for e in rito.values()),
            "impede": True,
        },
        {
            "criterio": "Caso com termo da regra de proteção classificado como FORA",
            "resultado": f"{len(protegidos_fora)} ({', '.join(map(str, protegidos_fora)) or 'nenhum'})",
            "meta": "0",
            "bateu": not protegidos_fora,
            "impede": True,
        },
        {
            "criterio": "Risco imediato certo",
            "resultado": f"{risco} de {len(resultados)} rodadas",
            "meta": "registrar",
            "bateu": True,
            "impede": False,
        },
        {
            "criterio": "Sinalizar ao Núcleo no caso 10",
            "resultado": f"{nsp_ok} de {len(nsp)} rodadas",
            "meta": "registrar",
            "bateu": True,
            "impede": False,
        },
        {
            "criterio": "Rodadas sem sugestão (fora do formato ou agente fora)",
            "resultado": str(len(sem_sugestao)),
            "meta": "registrar",
            "bateu": True,
            "impede": False,
        },
    ]


def relatorio(linhas: list[dict], modelo: str) -> str:
    cabecalho = [
        f"Teste de aceite do agente de triagem do Canal de Conduta, modelo `{modelo}`, "
        f"prompt {agente.versao_do_prompt()}, {VEZES} rodadas por caso.",
        "",
        "| Critério | Resultado | Meta | Bateu |",
        "|---|---|---|---|",
    ]
    corpo = [
        f"| {linha['criterio']} | {linha['resultado']} | {linha['meta']} | {'sim' if linha['bateu'] else 'não'} |"
        for linha in linhas
    ]
    pode = all(linha["bateu"] for linha in linhas if linha["impede"])
    return "\n".join([*cabecalho, *corpo, "", f"Metas do Anexo B: {'batidas' if pode else 'NÃO batidas'}."])


def main(argv: list[str] | None = None, *, perguntar: Callable[[str], str] = input, cliente=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--modelo", default=settings.conduta_agente_modelo)
    parser.add_argument("--saida", default=f"conduta-teste-de-aceite-{datetime.now():%Y%m%d-%H%M%S}.json")
    args = parser.parse_args(argv)

    casos = carregar_casos()
    conta = estimativa(casos, args.modelo)
    custo = f"US$ {conta['custo_usd']:.2f}" if conta["custo_usd"] is not None else "sem preço cadastrado"
    print(
        f"{len(casos)} casos x {VEZES} rodadas = {conta['chamadas']} chamadas ao modelo {args.modelo}. "
        f"Estimativa: {custo}."
    )
    if perguntar(f'Digite "{CONFIRMACAO}" para chamar a IA e gastar esse valor: ').strip() != CONFIRMACAO:
        print("Nada foi chamado.")
        return 1
    if cliente is None:
        if not settings.anthropic_api_key:
            print("Sem ANTHROPIC_API_KEY no ambiente. Nada foi chamado.")
            return 1
        cliente = ClienteDaAnthropic(max_retries=2, timeout=agente.TEMPO_LIMITE_S)

    resultados = rodar(cliente, casos, args.modelo)
    Path(args.saida).write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    linhas = metricas(casos, resultados)
    print(relatorio(linhas, args.modelo))
    print(f"\nRespostas de cada rodada em {args.saida}.")
    return 0 if all(linha["bateu"] for linha in linhas if linha["impede"]) else 2


if __name__ == "__main__":
    sys.exit(main())
