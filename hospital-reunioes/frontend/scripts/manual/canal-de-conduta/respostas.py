#!/usr/bin/env python3
"""As respostas de exemplo do Comitê de Conduta para os prints do manual
(issue #1851, PRD #1786).

Imprime, em JSON, a tabela que o `roteiro.sh` serve no lugar do backend: a
chave é a rota depois de `/api/` e o valor é o corpo da resposta. Cada caso
fica parado numa etapa (triagem, apuração, voto, ata e envio à Direção), para
o roteiro fotografar a tarefa daquela etapa. O relato de cada caso é um dos
casos fictícios do Anexo B (`backend/tests/fixtures/conduta/casos-anexo-b.json`),
e as pessoas são as do `seed.json`, com as datas contadas a partir de hoje, no
fuso do hospital. Nada aqui é caso, pessoa ou voto de verdade.

Uso: python3 scripts/manual/canal-de-conduta/respostas.py
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
SEED = json.loads((AQUI / "seed.json").read_text(encoding="utf-8"))
ANEXO_B = {
    caso["id"]: caso["relato"]
    for caso in json.loads(
        (AQUI.parents[3] / "backend" / "tests" / "fixtures" / "conduta" / "casos-anexo-b.json").read_text(
            encoding="utf-8"
        )
    )
}
FUSO = ZoneInfo("America/Sao_Paulo")
HOJE = datetime.now(FUSO).date()

COORDENACAO = SEED["coordenacao"]["nome"]
MEMBRO = SEED["membro"]["nome"]
SEGUNDO_LEITOR = SEED["segundo_leitor"]["nome"]
DIAS_DO_RITO = {"rapido": 20, "completo": 30}
TRILHO = ("Triagem", "Apuração", "Voto", "Ata", "Medida", "Acompanhamento")
POSICAO = {"triagem": 0, "apuracao": 1, "voto": 2, "ata": 3}


def instante(dias_atras: int, hora: str = "10:00") -> str:
    h, m = (int(p) for p in hora.split(":"))
    return datetime.combine(HOJE - timedelta(days=dias_atras), time(h, m), FUSO).isoformat()


def dias_uteis_depois(inicio: date, dias: int) -> date:
    dia = inicio
    while dias:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            dias -= 1
    return dia


def caixa(frase: str, botao: str | None, como: list[str], acao: str | None, bloqueio: str | None = None) -> dict:
    return {"frase": frase, "botao": botao, "como_fazer": como, "acao": acao, "bloqueio": bloqueio}


def caso(chave: str, etapa: str, rito: str | None, categoria: str | None, o_que_fazer: dict, **extra) -> dict:
    """O caso aberto como o backend devolve, parado na etapa dada."""
    dados = SEED["casos"][chave]
    recebido = HOJE - timedelta(days=dados["recebido_ha"])
    prazo = recebido + timedelta(days=DIAS_DO_RITO[rito]) if rito else None
    triado = etapa != "triagem"
    return {
        "id": dados["id"],
        "protocolo": dados["protocolo"],
        "etapa": etapa,
        "rito": rito,
        "categoria": categoria,
        "situacao": "em_andamento" if triado else "em_triagem",
        "prazo_em": prazo.isoformat() if prazo else None,
        "prazo_vencido": False,
        "faltam_dias": (prazo - HOJE).days if prazo else None,
        "origem": "canal",
        "membros_do_caso": [
            {"id": SEED["membro"]["id"], "nome": MEMBRO, "papel": "membro"},
            {"id": SEED["segundo_leitor"]["id"], "nome": SEGUNDO_LEITOR, "papel": "segundo_leitor"},
        ],
        "pode_contestar_participacao": True,
        "contestacoes_de_participacao": [],
        "citados": [],
        "relato": ANEXO_B[dados["anexo_b"]],
        "relator_nome": None,
        "anexos": [],
        "escopo": "dentro" if triado else None,
        "destino": None,
        "papel": "coordenacao",
        "trilho": [
            {"nome": nome, "estado": "concluida" if i < POSICAO[etapa] else "atual" if i == POSICAO[etapa] else "pendente"}
            for i, nome in enumerate(TRILHO)
        ],
        "o_que_fazer_agora": o_que_fazer,
        "contestacao": None,
        "pode_contestar": False,
        "prorrogacao": None,
        "orientacao": None,
        "triagem_em": instante(dados["recebido_ha"] - 1) if triado else None,
        "conferida_em": instante(dados["recebido_ha"] - 2, "15:00") if triado else None,
        "encerrado_em": None,
        "desfecho": None,
        "notas_ao_nsp": [],
        "depoimentos": [],
        "avanco_da_apuracao": None,
        "rota": "comum",
        "afastamentos": [],
        "pode_registrar_afastamento": False,
        **extra,
    }


# ── A apuração: o depoimento do acusado, com o termo assinado e o envelope por marcar ──

LISTA_DO_DEPOIMENTO = [
    ("transcricao", "Transcrição anexada", True),
    ("audio", "Áudio anexado", True),
    ("termo_assinado", "Termo assinado anexado", True),
    ("arquivos_corretos", "Abri os arquivos na aplicação e estão corretos", False),
    ("gravacao_apagada", "Apaguei a gravação de áudio da plataforma de gravação", False),
    ("arquivos_apagados", "Apaguei os arquivos do computador e do celular", False),
    ("original_no_envelope", "Guardei o original assinado no envelope do caso", False),
]


def versao(n: int, dias_atras: int, hora: str, tipo: str, tamanho: int) -> dict:
    return {
        "versao": n,
        "enviado_em": instante(dias_atras, hora),
        "enviado_por": COORDENACAO,
        "paginas": [{"id": f"exemplo-{tipo}-{n}", "content_type": "application/pdf", "tamanho_bytes": tamanho}],
    }


def depoimento() -> dict:
    pessoa = SEED["depoente"]
    lista = []
    for item, rotulo, automatico in LISTA_DO_DEPOIMENTO:
        if item == "original_no_envelope":
            lista.append({"item": item, "rotulo": rotulo, "automatico": False, "estado": "pendente"})
        elif automatico:
            lista.append({"item": item, "rotulo": rotulo, "automatico": True, "estado": "feito"})
        else:
            lista.append(
                {
                    "item": item,
                    "rotulo": rotulo,
                    "automatico": False,
                    "estado": "feito",
                    "marcado_por": COORDENACAO,
                    "marcado_em": instante(1, "16:20"),
                }
            )
    return {
        "id": "exemplo-depoimento-1",
        "nome": pessoa["nome"],
        "cargo": pessoa["cargo"],
        "papel": pessoa["papel"],
        "situacao": "Falta a lista de conferência",
        "arquivos": {
            "transcricao": [versao(1, 2, "11:40", "transcricao", 48_000)],
            "audio": [versao(1, 2, "11:42", "audio", 52_000_000)],
            "termo_assinado": [versao(1, 1, "15:05", "termo", 410_000)],
        },
        "sem_gravacao": None,
        "lista": lista,
        "bloqueio_da_conclusao": "Falta marcar: Guardei o original assinado no envelope do caso.",
        "concluido_em": None,
        "concluido_por": None,
        "termo": {
            "versao": 2,
            "origem": "correcao",
            "criado_em": instante(1, "14:10"),
            "criado_por": COORDENACAO,
            "identificacao": {
                "nome": pessoa["nome"],
                "cargo": pessoa["cargo"],
                "cpf": "",
                "data": (HOJE - timedelta(days=2)).isoformat(),
                "hora": "10:30",
                "local": "Sala do Comitê",
                "conduziram": [COORDENACAO, MEMBRO],
            },
            "gravacao": "Gravado na plataforma do hospital, com o consentimento dito no início.",
            "declaracoes": [
                "O depoente disse que trabalha no plantão noturno do centro cirúrgico há três anos.",
                "Disse que não confere o carrinho de medicamentos na troca de plantão.",
            ],
            "documentos": ["Escala do plantão noturno do mês"],
            "lido_em_voz_alta": True,
            "notas": {"rotulo": "Sugestão", "itens": []},
        },
        "roteiro": None,
        "recusa": None,
    }


# ── O voto e a ata: os três votantes ──

def votos() -> list[dict]:
    """Os votos do caso da ata e do envio à Direção, o das próteses."""
    return [
        {
            "membro": COORDENACAO,
            "resultado": "procedente",
            "medida": "advertencia_escrita",
            "dias_de_suspensao": None,
            "justificativa": "Os pedidos do material do fornecedor dobraram no período, e a defesa não explicou a mudança.",
        },
        {
            "membro": MEMBRO,
            "resultado": "procedente",
            "medida": "advertencia_escrita",
            "dias_de_suspensao": None,
            "justificativa": "A prova vai além do relato e a defesa foi ouvida.",
        },
        {
            "membro": SEGUNDO_LEITOR,
            "resultado": "parcialmente_procedente",
            "medida": "orientacao_registrada",
            "dias_de_suspensao": None,
            "justificativa": "Parte dos fatos não teve testemunha.",
        },
    ]


ITENS_DA_TRAVA = [
    ("fato", "Fato com data e local"),
    ("prova", "Prova além do relato"),
    ("defesa", "Defesa do acusado"),
    ("regra", "Regra do Código violada"),
    ("ciencia", "Ciência do Código pelo acusado"),
    ("medida", "Medida conforme a Matriz"),
    ("votos_e_ata", "Votos registrados e ata assinada"),
]


def trava(confirmada: bool) -> dict:
    return {
        "itens": [
            {
                "item": item,
                "rotulo": rotulo,
                "preenchimento": None,
                "confirmacoes": [MEMBRO] if confirmada else [],
                "confirmacoes_precisas": 1,
                "confirmado": confirmada,
                "pode_confirmar": False,
                "bloqueio": None,
            }
            for item, rotulo in ITENS_DA_TRAVA
        ],
        "preenchida_em": instante(3) if confirmada else None,
        "pode_preencher": not confirmada,
        "ciencia": [],
    }


def votacao(votaram: int, concluida: str | None, bloqueio: str | None) -> dict:
    fechada = votaram == 3
    return {
        "rodada": 1,
        "votantes": 3,
        "votaram": votaram,
        "meu_voto": None,
        "pode_votar": votaram == 1,
        "bloqueio_do_voto": None,
        "reuniao_curta_convocada": False,
        "rodadas": (
            [{"rodada": 1, "votos": votos(), "resultado": "procedente", "medida": "advertencia_escrita", "reuniao_curta": False}]
            if fechada
            else []
        ),
        "resultado": {"resultado": "procedente", "medida": "Advertência escrita"} if fechada else None,
        "concluida": concluida,
        "pode_concluir": False,
        "bloqueio_da_conclusao": bloqueio,
    }


def ata(situacao: str) -> dict:
    caso_da_ata = SEED["casos"]["ata"]
    return {
        "documento": {
            "versao": 1,
            "identificacao": {
                "rito": "Completo",
                "data": HOJE.strftime("%d/%m/%Y"),
                "presentes": [COORDENACAO, MEMBRO, SEGUNDO_LEITOR],
                "impedimentos": [],
                "suplentes": [],
            },
            "resumo": f"Caso {caso_da_ata['protocolo']}. Relato de pagamento a um médico pelo uso de material de um fornecedor.",
            "provas": ["Depoimento do acusado", "Depoimento de uma testemunha", "Extrato de pedidos de material do setor"],
            "defesa": "O acusado negou o pagamento e disse que escolhe o material pelo protocolo do setor.",
            "deliberacao": "Por maioria, o Comitê julgou o relato procedente.",
            "fundamentos": "Os pedidos de material do fornecedor dobraram no período do relato, sem mudança no protocolo.",
            "medida": "Advertência escrita",
            "votos": [
                {"membro": v["membro"], "resultado": v["resultado"].replace("_", " ").capitalize(),
                 "medida": "Advertência escrita" if v["medida"] == "advertencia_escrita" else "Orientação registrada",
                 "justificativa": v["justificativa"]}
                for v in votos()
            ],
            "correcao": [],
            "encaminhamentos": [],
            "pontos": {"rotulo": "Sugestão", "itens": []},
            "assinatura": {"situacao": situacao, "erro": None, "assinado_em": None, "tem_copia": situacao == "assinado"},
        },
        "pode_gerar": situacao != "assinado",
        "bloqueio_da_geracao": None,
        "pode_enviar": situacao != "assinado",
    }


def reuniao(concluida: bool) -> dict:
    marca = {"marcado_por": COORDENACAO, "marcado_em": instante(1, "17:00")}
    return {
        "transcricoes": [{"versao": 1, "enviado_em": instante(2, "18:00"), "enviado_por": COORDENACAO}],
        "lista": [
            {"item": "transcricao", "rotulo": "Transcrição anexada", "automatico": True, "estado": "feito"},
            {"item": "ata_assinada", "rotulo": "Ata assinada pelos três", "automatico": True,
             "estado": "feito" if concluida else "pendente"},
            {"item": "gravacao_apagada", "rotulo": "Apaguei a gravação de áudio da plataforma de gravação",
             "automatico": False, "estado": "feito", **marca},
            {"item": "arquivos_apagados", "rotulo": "Apaguei os arquivos do computador e do celular",
             "automatico": False, "estado": "feito", **marca},
        ],
        "pode_anexar": not concluida,
        "pode_marcar": not concluida,
        "pode_concluir": False,
        "bloqueio_da_conclusao": None if concluida else "Falta a ata assinada pelos três.",
        "concluida_em": instante(0, "09:00") if concluida else None,
        "concluida_por": COORDENACAO if concluida else None,
        "transcricao_eliminada_em": instante(0, "09:00") if concluida else None,
    }


def casos() -> dict[str, dict]:
    triagem = caso(
        "triagem",
        "triagem",
        None,
        None,
        caixa(
            "Leia o resumo. Confirme se o caso é do canal e qual o rito.",
            "CONFIRMAR TRIAGEM",
            ["Leia o relato original", "Confira cada sugestão", "Se faltar informação, pergunte ao denunciante"],
            "confirmar_triagem",
        ),
    )
    apuracao = caso(
        "apuracao",
        "apuracao",
        "completo",
        "B",
        caixa(
            "Ouça o acusado e até duas pessoas. Sempre em dupla.",
            "ADICIONAR PESSOA A OUVIR",
            ["Use o roteiro sugerido", "Grave e diga o consentimento no início", "Siga os passos do cartão até concluir o depoimento"],
            "adicionar_pessoa",
        ),
        depoimentos=[depoimento()],
        avanco_da_apuracao="A Apuração só avança com todos os depoimentos concluídos. Falta 1.",
    )
    como_votar = ["Escolha o resultado", "Escolha a medida da Matriz", "Escreva sua justificativa em até três linhas"]
    voto = caso(
        "voto",
        "voto",
        "completo",
        "A",
        caixa("Leia o dossiê e vote. Seu voto fica oculto até todos votarem.", "VOTAR", como_votar, "votar"),
        votacao=votacao(1, None, "Faltam votos: a votação conclui depois que os três votarem."),
        trava=trava(False),
    )
    com_ata = caso(
        "ata",
        "voto",
        "completo",
        "C",
        caixa(
            "Leia o dossiê e vote. Seu voto fica oculto até todos votarem.",
            "VOTAR",
            como_votar,
            "votar",
            "Você já votou. Seu voto fica oculto até todos votarem.",
        ),
        votacao=votacao(3, None, "Falta a ata assinada pelos três votantes."),
        trava=trava(True),
        ata=ata("enviado"),
        reuniao=reuniao(False),
    )
    direcao = caso(
        "direcao",
        "ata",
        "completo",
        "E",
        caixa(
            "A votação foi concluída, com a ata assinada pelos três votantes. Envie a Recomendação à Direção.",
            "ENVIAR À DIREÇÃO",
            ["Confira a ata assinada", "O Presidente só lê a conclusão e a ata", "A diretoria executiva registra a decisão"],
            "enviar_a_direcao",
        ),
        votacao=votacao(3, "procedente", None),
        trava=trava(True),
        ata=ata("assinado"),
        reuniao=reuniao(True),
    )
    return {c["id"]: c for c in (triagem, apuracao, voto, com_ata, direcao)}


def minha_vez(todos: dict[str, dict]) -> dict:
    """Só o que depende da coordenação: confirmar a triagem e enviar à Direção.
    Do prazo que vence antes ao que vence depois; o caso sem rito conta pelo
    prazo do Encaminhamento, como no servidor."""
    itens = []
    for chave, acao in (("triagem", "Confirmar a triagem"), ("direcao", "Enviar à Direção")):
        c = todos[SEED["casos"][chave]["id"]]
        recebido = HOJE - timedelta(days=SEED["casos"][chave]["recebido_ha"])
        urgencia = c["prazo_em"] or dias_uteis_depois(recebido, 5).isoformat()
        item = {k: c[k] for k in ("id", "protocolo", "etapa", "rito", "prazo_em", "prazo_vencido", "faltam_dias")}
        itens.append((urgencia, {**item, "acao": acao}))
    return {"itens": [item for _, item in sorted(itens, key=lambda par: par[0])], "termo_pendente": False}


def tabela() -> dict[str, object]:
    todos = casos()
    respostas: dict[str, object] = {"comite-de-conduta/minha-vez": minha_vez(todos)}
    for caso_id, corpo in todos.items():
        respostas[f"comite-de-conduta/casos/{caso_id}"] = corpo
        respostas[f"comite-de-conduta/casos/{caso_id}/convites"] = {"pode_convidar": False, "convites": []}
    respostas["comite-de-conduta/rota-especial/contagem"] = {"recebidos": 0, "concluidos": 0, "em_aberto": 0}
    respostas["comite-de-conduta/afastamentos/pedidos"] = {"pedidos": []}
    return respostas


if __name__ == "__main__":
    print(json.dumps(tabela(), ensure_ascii=False))
