#!/usr/bin/env python3
"""As respostas de exemplo da aba Tecnologia para os prints do manual (issue
#1727, ADR 0094, decisão 5).

Imprime, em JSON, a tabela que o `roteiro.sh` serve no lugar do backend: a
chave é a rota depois de `/api/admin/tecnologia/`, com a consulta quando há
(`chat?projeto=ana`), e o valor é o corpo da resposta. Com `--sino`, imprime a
tabela do sino (issue #1968), com a chave depois de `/api/notificacoes`. Com
`--envio`, imprime as respostas dos dois cliques do Envio aos desenvolvedores
(issue #2015), interpretar e enviar, e a do Achei um problema (issue #2211), os
únicos pedidos que não são GET a que o roteiro responde; o resto continua
recusado. Tudo sai do `seed.json`,
com as datas contadas a partir de hoje, no fuso do hospital: assim o Quadro
abre com as colunas cheias e as Entregas caem nas últimas semanas, em qualquer
dia que o roteiro rodar. Nada aqui é gente, pedido ou card de verdade.

Uso: python3 scripts/manual/tecnologia/respostas.py [--sino | --envio]
"""

from __future__ import annotations

import json
import sys
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
    projeto_novo = d["projeto"] not in PROJETOS_CONHECIDOS
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
        # O pedido de projeto novo não se apaga pelo aplicativo (issue #1967).
        "pode_apagar": registrada and not projeto_novo,
        "pode_revisar": False,
        "em_revisao": False,
        "implantacao": implantacao_da_demanda(d["id"]),
    }


def implantacao_da_demanda(demanda_id: str) -> dict | None:
    """A seção Implantação do card (issue #2211, ADR 0111, decisão 5), como o
    servidor a manda: os feitos sobre o total e cada Pedido de implantação, só
    Feito ou Aberto, com a espera nula na linha. Nula na Demanda sem Pedido."""
    seed = SEED["implantacao"]
    if demanda_id != seed["demanda"]:
        return None
    pedidos = [
        {
            "titulo": p["assunto"],
            "destinatario": SEED["admin"]["nome"],
            "situacao": "feito" if p["estado"] == "concluida" else "aberto",
            "espera": None,
        }
        for p in seed["pedidos"]
    ]
    feitos = sum(1 for p in pedidos if p["situacao"] == "feito")
    return {"feitos": feitos, "total": len(pedidos), "pedidos": pedidos}


def fala(f: dict) -> dict:
    return {
        "autor": f["autor"],
        "texto": f["texto"],
        "fonte": None,
        "opcoes": f.get("opcoes", []),
        "recomendada": f.get("recomendada"),
        "nao_bateu": False,
        "cartao": f.get("cartao"),
    }


def conversa(demanda_id: str, estado: str, falas: list[dict], **resto) -> dict:
    return {
        "demanda_id": demanda_id,
        "estado": estado,
        "mensagens": [fala(f) for f in falas],
        "resumo": None,
        "resumo_da_melhoria": None,
        "anexos": 0,
        "planejamento": False,
        "aviso_dos_anexos": None,
        "custo": None,
        "anexos_da_demanda": [],
        "responsavel": None,
        "documento": None,
        "revisao": None,
        **resto,
    }


def conversas(lista: list[dict]) -> dict:
    """A conversa com o Assistente de cada pedido do diretor, e a Conversa da Demanda de cada card."""
    abrir = SEED["abrir"]
    tabela: dict[str, dict] = {}
    for d in lista:
        if d["origem"] != "vitta":
            tabela[f"chat/{d['id']}"] = conversa(
                d["id"], "enviado" if d["tem_vinculo"] else "em_andamento", [], responsavel=d["responsavel"]
            )
        # A Conversa da Demanda aparece em todo pedido aberto, com card ou sem.
        tabela[f"chat/{d['id']}/conversa"] = {"mensagens": [], "mencionaveis": []}

    melhoria = SEED["melhoria"]
    tabela[f"chat/{abrir['melhoria']}"] = conversa(
        abrir["melhoria"],
        "em_andamento",
        melhoria["falas"],
        planejamento=True,
        documento=melhoria["documento"],
        custo=melhoria["custo"],
    )
    bug = SEED["bug"]
    tabela[f"chat/{abrir['bug']}"] = conversa(
        abrir["bug"], "resumido", bug["falas"], resumo=bug["resumo"], custo=bug["custo"]
    )
    problema = conversa_do_problema()
    tabela[f"chat/{problema['demanda_id']}"] = problema
    tabela[f"chat/{abrir['painel']}/conversa"] = conversa_da_demanda(SEED["conversa_da_demanda"])
    # O pedido do Envio aos desenvolvedores (issue #2015): as últimas mensagens são do
    # diretor, e o botão conta só essas.
    falas_do_envio = SEED["envio"]["falas"]
    novas = len(falas_do_envio) - max((i + 1 for i, f in enumerate(falas_do_envio) if not f["minha"]), default=0)
    tabela[f"chat/{abrir['envio']}/conversa"] = {
        **conversa_da_demanda(falas_do_envio, prefixo="exemplo-envio"),
        "envio": {"mensagens_novas": novas},
    }
    # A pergunta da Vitta que pede a resposta do diretor, no pedido do projeto novo (issue #1968).
    # Desde a issue #2116 ela chega como o cartão da Pergunta, no lugar da bolha, e o
    # diretor, que é o Destinatário, responde nele (issue #2123).
    da_pergunta = conversa_da_demanda(SEED["pergunta_do_projeto_novo"]["falas"], prefixo="exemplo-pergunta")
    da_pergunta["mensagens"][-1]["pergunta"] = pergunta_do_diretor(pode_responder=True)
    tabela[f"chat/{abrir['projeto_novo']}/conversa"] = da_pergunta
    return tabela


def conversa_do_problema() -> dict:
    """A conversa que o Achei um problema abre (issue #2211, ADR 0111, decisão
    9): o bug novo, com o texto que o servidor monta do Pedido de implantação e
    da entrega como primeira fala do diretor, e a pergunta do Assistente."""
    seed = SEED["implantacao"]
    entrega = next(d for d in SEED["demandas"] if d["id"] == seed["demanda"])
    pedido = next(p for p in seed["pedidos"] if p.get("espera"))
    inicial = f'Achei um problema no Pedido de implantação "{pedido["assunto"]}", da entrega "{entrega["titulo"]}".'
    falas = [{"autor": "diretor", "texto": inicial}, *seed["falas_do_problema"]]
    return conversa(seed["problema"], "em_andamento", falas)


def _projeto_da(demanda_id: str) -> tuple[dict, str]:
    d = next(d for d in SEED["demandas"] if d["id"] == demanda_id)
    return d, PROJETOS_CONHECIDOS.get(d["projeto"]) or d["projeto_nome"]


def cartao(p: dict, *, projeto: str, criado_em: str, destinatario: str, pode_responder: bool) -> dict:
    """O cartão da Pergunta da Vitta como a rota o manda (issue #2116, ADR 0109, decisão 3)."""
    return {
        "id": p["id"],
        "projeto": projeto,
        "assunto": p["assunto"],
        "texto": p["texto"],
        "por_que_precisa": p["por_que_precisa"],
        "o_que_esta_parado": p["o_que_esta_parado"],
        "o_que_anda_depois": p["o_que_anda_depois"],
        "ganho": p["ganho"],
        "opcoes": p.get("opcoes", []),
        "recomendada": p.get("recomendada"),
        "porque": p.get("porque"),
        "estado": "aberta",
        "criado_em": criado_em,
        "destinatario": destinatario,
        "resposta": None,
        "resolucao": None,
        "cancelamento": None,
        "pode_responder": pode_responder,
    }


def pergunta_do_diretor(pode_responder: bool) -> dict:
    """A Pergunta do pedido do projeto novo, para o diretor: a última fala da conversa dele."""
    seed = SEED["pergunta_do_projeto_novo"]
    _, projeto = _projeto_da(SEED["abrir"]["projeto_novo"])
    ultima = conversa_da_demanda(seed["falas"])["mensagens"][-1]
    return cartao(
        {**seed["pergunta"], "assunto": seed["assunto"], "texto": ultima["texto"]},
        projeto=projeto,
        criado_em=ultima["criado_em"],
        destinatario=SEED["admin"]["nome"],
        pode_responder=pode_responder,
    )


def perguntas() -> dict:
    """A lista Esperando você (issue #2118) e o Me explique da Pergunta do diretor
    (issue #2122). Os pedidos do diretor vêm primeiro, o Passo a passo e a Pergunta, e
    se respondem no cartão da lista (issues #2145 e #2184); a de outra pessoa depois,
    só para ler."""
    minha = pergunta_do_diretor(pode_responder=True)
    demanda, _ = _projeto_da(SEED["abrir"]["projeto_novo"])
    outra = SEED["outra_pergunta"]
    da_outra, projeto = _projeto_da(outra["demanda"])
    return {
        "perguntas/esperando": [
            # Do diretor, a mais antiga primeiro: os Pedidos de implantação e o Passo a
            # passo nasceram ontem (issues #2184 e #2211).
            *pedidos_de_implantacao(),
            passo_a_passo(),
            {**minha, "demanda_id": demanda["id"], "demanda": demanda["titulo"], "minha": True},
            {
                **cartao(
                    outra,
                    projeto=projeto,
                    criado_em=instante(outra["dias"], "15:40"),
                    destinatario=outra["destinatario"],
                    pode_responder=False,
                ),
                "demanda_id": da_outra["id"],
                "demanda": da_outra["titulo"],
                "minha": False,
            },
        ],
        f"perguntas/{minha['id']}/me-explique": {
            "mensagens": [
                {"papel": f["papel"], "texto": f["texto"], "rascunho": f.get("rascunho")}
                for f in SEED["pergunta_do_projeto_novo"]["me_explique"]
            ]
        },
    }


def passo_a_passo() -> dict:
    """O Passo a passo da Vitta que espera o diretor (issue #2184, ADR 0110), na lista
    Esperando você: o primeiro passo já marcado por ele, e os outros sem check, para o
    print mostrar o cartão no meio, com o Concluir ainda preso."""
    seed = SEED["passo_a_passo"]
    demanda, projeto = _projeto_da(seed["demanda"])
    diretor = SEED["admin"]["nome"]
    return {
        **cartao(
            seed,
            projeto=projeto,
            criado_em=instante(seed["dias"], "16:20"),
            destinatario=diretor,
            pode_responder=True,
        ),
        "tipo": "passo_a_passo",
        "passos": [
            {
                "texto": p["texto"],
                "marcado": p["marcado"],
                "por": diretor if p["marcado"] else None,
                "em_nome_de": None,
                "em": instante(seed["dias"], "17:05") if p["marcado"] else None,
            }
            for p in seed["passos"]
        ],
        "conclusao": None,
        "fechamento": None,
        "pode_reenviar": False,
        "demanda_id": demanda["id"],
        "demanda": demanda["titulo"],
        "minha": True,
    }


def pedidos_de_implantacao() -> list[dict]:
    """Os Pedidos de implantação abertos da entrega Em produção (issue #2211, ADR
    0111), na lista Esperando você: o que espera outro, com todos os checks e o
    Concluir preso, e o que espera a Demanda de bug, com um check só."""
    seed = SEED["implantacao"]
    demanda, projeto = _projeto_da(seed["demanda"])
    diretor = SEED["admin"]["nome"]
    por_id = {p["id"]: p for p in seed["pedidos"]}
    numero_de = {d["id"]: d["numero"] for d in SEED["demandas"]}
    return [
        {
            **cartao(
                p,
                projeto=projeto,
                criado_em=instante(p["dias"], p["hora"]),
                destinatario=diretor,
                pode_responder=True,
            ),
            "tipo": "implantacao",
            "passos": [
                {
                    "texto": passo["texto"],
                    "marcado": passo["marcado"],
                    "por": diretor if passo["marcado"] else None,
                    "em_nome_de": None,
                    "em": instante(p["dias"], "16:40") if passo["marcado"] else None,
                }
                for passo in p["passos"]
            ],
            "espera": (
                {"pedido_id": p["espera"], "assunto": por_id[p["espera"]]["assunto"]} if p.get("espera") else None
            ),
            "espera_demanda": (
                {"demanda_id": p["espera_a_demanda"], "numero": numero_de[p["espera_a_demanda"]]}
                if p.get("espera_a_demanda")
                else None
            ),
            "conclusao": None,
            "fechamento": None,
            "pode_reenviar": False,
            "demanda_id": demanda["id"],
            "demanda": demanda["titulo"],
            "minha": True,
        }
        for p in seed["pedidos"]
        if p["estado"] == "aberta"
    ]


def conversa_da_demanda(falas: list[dict], prefixo: str = "exemplo-mensagem") -> dict:
    return {
        "mensagens": [
            {
                "id": f"{prefixo}-{i}",
                "autor": m["autor"],
                "texto": m["texto"],
                "criado_em": instante(m["dias"], f"{9 + i}:15"),
                "minha": m["minha"],
            }
            for i, m in enumerate(falas)
        ],
        "mencionaveis": [{"id": dev["id"], "nome": dev["nome"]} for dev in SEED["desenvolvedores"]],
    }


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
        **conversas(lista),
        **perguntas(),
        "entregas": entregas(lista),
    }


def sino() -> dict:
    """O sino do diretor (issue #1968): o aviso Pede sua resposta, com o Assunto,
    que abre o pedido do projeto novo, e um aviso antigo, já lido."""
    agora = datetime.now(FUSO).replace(microsecond=0)
    pergunta = SEED["pergunta_do_projeto_novo"]
    painel = next(d for d in SEED["demandas"] if d["id"] == SEED["abrir"]["painel"])
    return {
        "/count": {"nao_lidas": 1},
        "?limit=20": [
            {
                "id": "exemplo-aviso-1",
                "destinatario_id": SEED["admin"]["id"],
                "tipo": "TECNOLOGIA",
                "titulo": "Pede sua resposta",
                "mensagem": pergunta["assunto"],
                # O aviso da Pergunta guarda "pergunta:<id>" e abre a aba no cartão dela (issue #2118).
                "referencia_id": f"pergunta:{pergunta['pergunta']['id']}",
                "lida": False,
                "created_at": (agora - timedelta(minutes=5)).isoformat(),
            },
            {
                "id": "exemplo-aviso-2",
                "destinatario_id": SEED["admin"]["id"],
                "tipo": "TECNOLOGIA",
                "titulo": f"{SEED['conversa_da_demanda'][-1]['autor']} escreveu na Demanda",
                "mensagem": painel["titulo"],
                "referencia_id": painel["id"],
                "lida": True,
                "created_at": (agora - timedelta(hours=3)).isoformat(),
            },
        ],
    }


def envio() -> dict:
    """Os dois cliques do Envio aos desenvolvedores (issue #2015, ADR 0108): o
    interpretar devolve o "Entendi assim:" do seed, e o enviar devolve a linha
    do envio no formato do backend. Nada chega à IA nem ao GitHub. O envio sai
    meia hora depois da última mensagem do seed, e não na hora do roteiro: rodado
    de manhã, o print mostraria o envio antes das mensagens que ele resume."""
    chave = f"chat/{SEED['abrir']['envio']}/conversa"
    entendi = SEED["envio"]["entendi"]
    ultima = conversa_da_demanda(SEED["envio"]["falas"])["mensagens"][-1]["criado_em"]
    agora = datetime.fromisoformat(ultima) + timedelta(minutes=30)
    linha = "\n".join(
        [f"Enviado aos desenvolvedores em {agora:%d/%m/%Y}, às {agora:%H:%M}:", *[f"- {t}" for t in entendi["topicos"]]]
    )
    return {
        # O Achei um problema (issue #2211): o POST do chat com o Pedido devolve o bug novo.
        "chat": conversa_do_problema(),
        f"{chave}/interpretar": {"id": "exemplo-envio-1", **entendi},
        f"{chave}/enviar": {
            "id": "exemplo-envio-linha",
            "autor": None,
            "texto": linha,
            "criado_em": agora.isoformat(),
            "minha": False,
            "sistema": True,
        },
    }


if __name__ == "__main__":
    if "--sino" in sys.argv[1:]:
        print(json.dumps(sino(), ensure_ascii=False))
    elif "--envio" in sys.argv[1:]:
        print(json.dumps(envio(), ensure_ascii=False))
    else:
        print(json.dumps(tabela(), ensure_ascii=False))
