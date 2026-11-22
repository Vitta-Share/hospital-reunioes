#!/usr/bin/env python3
"""As respostas de exemplo do módulo Segurança do Paciente para os prints do
manual (issue #1780, PRD #1764).

Imprime, em JSON, a tabela que o `roteiro.sh` serve no lugar do backend: a
chave é a rota depois de `/api/`, com a consulta quando há
(`nsp/membros?data=2025-10-12`), e o valor é o corpo da resposta. Tudo sai do
`seed.json`, com as datas contadas a partir de hoje, no fuso do hospital:
assim a lista de membros mostra cada estado, a reunião do dia tem pauta e
presença, e a ata em validação é a de dias atrás, em qualquer dia que o
roteiro rodar. Nada aqui é gente, reunião ou ata de verdade.

Uso:
  python3 scripts/manual/seguranca-do-paciente/respostas.py
  python3 scripts/manual/seguranca-do-paciente/respostas.py --roteiro

Com `--roteiro`, imprime só o que o roteiro precisa saber para clicar: o dia
da composição, o título da reunião do dia e os casos e protocolos que ele
abre na notificação e na triagem (issue #2003).

As chaves que começam por `POST ` respondem a um pedido POST: o envio do
formulário de notificação, que devolve um protocolo de exemplo, e a consulta
do acompanhamento. Todo outro pedido que grava recebe 403 do roteiro.
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

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]

TIPOS = ["Ordinária mensal", "Análise de evento", "Apresentação à Diretoria", "Reunião rápida de segurança"]

# As reuniões que o roteiro abre: a do dia (pauta e presença), a que espera a
# validação da ata e a que já tem a ata encerrada.
REUNIAO_DO_DIA = "exemplo-reuniao-do-dia"
REUNIAO_EM_VALIDACAO = "exemplo-reuniao-em-validacao"
REUNIAO_ASSINADA = "exemplo-reuniao-assinada"
REUNIAO_NAO_INSTALADA = "exemplo-reuniao-nao-instalada"


def dia(desloca: int) -> str:
    """O dia `desloca` dias depois de hoje (negativo é antes), em AAAA-MM-DD."""
    return (HOJE + timedelta(days=desloca)).isoformat()


def instante(dias_atras: int, hora: str = "10:00") -> str:
    h, m = (int(p) for p in hora.split(":"))
    return datetime.combine(HOJE - timedelta(days=dias_atras), time(h, m), FUSO).isoformat()


def dia_util_antes(dia_base: date, uteis: int) -> date:
    atual = dia_base
    while uteis:
        atual -= timedelta(days=1)
        if atual.weekday() < 5:
            uteis -= 1
    return atual


def ordinaria(desloca: int) -> str:
    """O título da ordinária, pelo mês do dia: "Ordinária de novembro"."""
    return f"Ordinária de {MESES[(HOJE + timedelta(days=desloca)).month - 1]}"


# A não instalada fica 31 dias antes e a seguinte 35 depois: sempre em outro
# mês, e o título de cada ordinária não se repete na lista.
DESLOCA_NAO_INSTALADA = -31
DESLOCA_SEGUINTE = 35


def dia_da_composicao() -> str:
    return dia(-SEED["abrir"]["composicao_dias_atras"])


# ---------------------------------------------------------------- membros


def membro(m: dict) -> dict:
    """A Participação como a lista da tela a lê."""
    assinou = m.get("assinou_ha")
    enviado = m.get("enviado_ha", assinou)
    return {
        "id": f"exemplo-participacao-{m['id']}",
        "participante_id": m["id"],
        "nome": m["nome"],
        "papel": m["papel"],
        "area": m.get("area"),
        "conselho_profissional": m.get("conselho"),
        "registro_profissional": m.get("registro"),
        "registro_uf": m.get("uf"),
        "vigencia_inicio": dia(-m["inicio_ha"]),
        "vigencia_fim": dia(m["fim_em"]),
        "encerrada_em": dia(-m["encerrada_ha"]) if m.get("encerrada_ha") is not None else None,
        "termo_gerado_em": instante(enviado) if enviado is not None else None,
        "termo_enviado_em": instante(enviado, "10:05") if enviado is not None else None,
        "termo_assinado_em": instante(assinou, "15:40") if assinou is not None else None,
        "estado": m["estado"],
        "termo_pendente": assinou is None and m["estado"] != "encerrado",
    }


def membros() -> dict:
    lista = [membro(m) for m in SEED["membros"]]
    corte = date.fromisoformat(dia_da_composicao())
    naquele_dia = [
        p
        for p in lista
        if date.fromisoformat(p["vigencia_inicio"]) <= corte <= date.fromisoformat(p["vigencia_fim"])
        and (p["encerrada_em"] is None or corte <= date.fromisoformat(p["encerrada_em"]))
    ]
    pessoas = [{"id": m["id"], "nome": m["nome"]} for m in SEED["membros"]] + SEED["pessoas_fora_do_nucleo"]
    tabela: dict[str, object] = {
        "nsp/membros": {"membros": lista},
        f"nsp/membros?data={dia_da_composicao()}": {"membros": naquele_dia},
        "nsp/membros/pessoas": {"pessoas": sorted(pessoas, key=lambda p: p["nome"])},
        "participantes/setores": SEED["setores"],
    }
    for p in lista:
        tabela[f"nsp/membros/{p['id']}/trilha"] = {"trilha": trilha(p)}
        if p["termo_pendente"]:
            tabela[f"nsp/membros/{p['id']}/termo"] = {
                "situacao": "enviado",
                "erro": None,
                "enviado_em": p["termo_enviado_em"],
                "documento_url": None,
            }
    return tabela


def trilha(p: dict) -> list[dict]:
    """O histórico de mudanças da ficha, o mais novo primeiro."""
    presidencia = SEED["presidencia"]["nome"]
    m = next(x for x in SEED["membros"] if x["id"] == p["participante_id"])
    linhas = [
        {
            "acao": "cadastro", "campo": None, "valor_anterior": None, "valor_novo": None,
            "autor": presidencia, "created_at": instante(m["inicio_ha"], "09:30"),
        },
        {
            "acao": "termo_enviado", "campo": None, "valor_anterior": None, "valor_novo": None,
            "autor": presidencia, "created_at": instante(m.get("enviado_ha", m.get("assinou_ha", 0)), "10:05"),
        },
    ]
    if m.get("assinou_ha") is not None:
        linhas.append(
            {
                "acao": "termo_assinado", "campo": None, "valor_anterior": None, "valor_novo": None,
                "autor": m["nome"], "created_at": instante(m["assinou_ha"], "15:40"),
            }
        )
    if m["id"] == SEED["abrir"]["ficha"]:
        linhas.append(
            {
                "acao": "edicao", "campo": "area", "valor_anterior": "Farmácia Satélite", "valor_novo": "Farmácia",
                "autor": presidencia, "created_at": instante(120, "11:20"),
            }
        )
    return sorted(linhas, key=lambda linha: linha["created_at"], reverse=True)


# ------------------------------------------------------------- documentos


def documentos() -> dict:
    presidencia = SEED["presidencia"]["nome"]
    diretoria = SEED["diretoria_executiva"]

    def versao(id_: str, tipo: str, n: int, titulo: str, publicado_ha: int | None, **resto) -> dict:
        return {
            "id": id_,
            "tipo": tipo,
            "versao": n,
            "titulo": titulo,
            "natureza_revisao": resto.get("natureza"),
            "vigente": resto.get("vigente", False),
            "tem_texto": True,
            "tem_arquivo_assinado": resto.get("assinado", False),
            "publicado_em": instante(publicado_ha) if publicado_ha is not None else None,
            "publicado_por": resto.get("por", presidencia) if publicado_ha is not None else None,
        }

    lista = [
        versao("exemplo-doc-ato-1", "ato_designacao", 1, "Ato de designação dos membros do Núcleo", 300,
               vigente=True, assinado=True, por=diretoria),
        versao("exemplo-doc-regimento-1", "regimento", 1, "Regimento Interno do Núcleo de Segurança do Paciente", 720,
               assinado=True),
        versao("exemplo-doc-regimento-2", "regimento", 2,
               "Regimento Interno do Núcleo de Segurança do Paciente, revisão 2", 300,
               natureza="material", vigente=True, assinado=True),
        versao("exemplo-doc-regimento-3", "regimento", 3,
               "Regimento Interno do Núcleo de Segurança do Paciente, revisão 3", None, natureza="material"),
        versao("exemplo-doc-plano-1", "plano_seguranca_paciente", 1, "Plano de Segurança do Paciente 2026", 280,
               vigente=True, assinado=True),
        versao("exemplo-doc-ata-12", "ata", 12, "Ata nº 12 do Núcleo de Segurança do Paciente", 20,
               vigente=True, assinado=True),
    ]
    assinaturas = [
        {
            "documento_id": "exemplo-doc-regimento-3",
            "situacao": "enviado",
            "erro": None,
            "enviado_em": instante(2),
            "assinado_em": None,
            "pode_reenviar": True,
            "signatarios": [
                {"nome": diretoria, "qualidade": "diretoria_executiva", "assinado_em": instante(1, "16:10")},
                {"nome": presidencia, "qualidade": "presidencia", "assinado_em": None},
            ],
        }
    ]
    return {"nsp/documentos": {"documentos": lista}, "nsp/assinaturas-dos-documentos": {"assinaturas": assinaturas}}


# ----------------------------------------------------------- capacitações


def capacitacoes() -> dict:
    temas = [
        {"id": "exemplo-tema-1", "nome": "Higiene das mãos", "ativo": True},
        {"id": "exemplo-tema-2", "nome": "Identificação do paciente", "ativo": True},
        {"id": "exemplo-tema-3", "nome": "Prevenção de quedas", "ativo": True},
        {"id": "exemplo-tema-4", "nome": "Notificação de incidentes", "ativo": True},
        {"id": "exemplo-tema-5", "nome": "Cirurgia segura", "ativo": False},
    ]
    nome = {m["id"]: m["nome"] for m in SEED["membros"]}
    eu = SEED["presidencia"]["id"]

    def participante(pid: str, confirmou_ha: int | None) -> dict:
        return {
            "participante_id": pid,
            "nome": nome[pid],
            "presenca_confirmada_em": instante(confirmou_ha, "17:20") if confirmou_ha is not None else None,
        }

    lista = [
        {
            "id": "exemplo-capacitacao-1",
            "titulo": "Notificação de incidentes no aplicativo",
            "data": dia(0),
            "carga_horaria": 1.5,
            "instrutor": "Marina Couto",
            "publico": "membros",
            "tema_ids": ["exemplo-tema-4"],
            "participantes": [participante(eu, None), participante("P17801", 0), participante("P17803", None)],
        },
        {
            "id": "exemplo-capacitacao-2",
            "titulo": "Prevenção de quedas e identificação do paciente",
            "data": dia(-35),
            "carga_horaria": 3,
            "instrutor": "Juliana Prado",
            "publico": "profissionais",
            "tema_ids": ["exemplo-tema-2", "exemplo-tema-3"],
            "participantes": [participante("P17801", 35), participante("P17802", 35), participante("P17803", 34)],
        },
    ]
    cobertura = [
        {"participante_id": eu, "nome": nome[eu], "papel": "presidencia", "temas_cobertos": ["exemplo-tema-1"]},
        {"participante_id": "P17801", "nome": nome["P17801"], "papel": "suplente",
         "temas_cobertos": ["exemplo-tema-2", "exemplo-tema-3", "exemplo-tema-4"]},
        {"participante_id": "P17802", "nome": nome["P17802"], "papel": "membro",
         "temas_cobertos": ["exemplo-tema-2", "exemplo-tema-3"]},
        {"participante_id": "P17803", "nome": nome["P17803"], "papel": "membro",
         "temas_cobertos": ["exemplo-tema-2", "exemplo-tema-3"]},
    ]
    return {
        "nsp/capacitacoes": {
            "capacitacoes": lista,
            "temas": temas,
            "cobertura": cobertura,
            "pode_editar": True,
            "eu": eu,
            "hoje": dia(0),
        }
    }


# --------------------------------------------------------------- agenda


def agenda() -> dict:
    itens = [
        {
            "id": "exemplo-agenda-1",
            "evento": "Envio das notificações ao Notivisa",
            "periodicidade": "mensal",
            "regra": "Até o 15º dia útil",
            "proxima_data": dia(4),
            "link": None,
            "antecedencia_dias": 7,
            "ativo": True,
            "historico": [
                {"data_prevista": dia(-26), "resultado": "Notificações do mês enviadas, protocolo arquivado.",
                 "realizada_em": dia(-27), "registrado_por": "Marina Couto", "registrado_em": instante(27)},
            ],
            "lembrete": {"id_acao": "A-0412", "prazo": dia(4), "status": "PENDENTE"},
        },
        {
            "id": "exemplo-agenda-2",
            "evento": "Autoavaliação das práticas de segurança do paciente",
            "periodicidade": "anual",
            "regra": "Em outubro",
            "proxima_data": dia(320),
            "link": None,
            "antecedencia_dias": 30,
            "ativo": True,
            "historico": [
                {"data_prevista": dia(-45), "resultado": "Formulário respondido e enviado.",
                 "realizada_em": dia(-47), "registrado_por": "Marina Couto", "registrado_em": instante(47)},
            ],
            "lembrete": None,
        },
        {
            "id": "exemplo-agenda-3",
            "evento": "Revisão do Plano de Segurança do Paciente",
            "periodicidade": "bienal",
            "regra": None,
            "proxima_data": dia(400),
            "link": None,
            "antecedencia_dias": 60,
            "ativo": True,
            "historico": [],
            "lembrete": None,
        },
    ]
    return {"nsp/agenda": {"itens": itens, "pode_editar": True}}


# --------------------------------------------------------------- reuniões


def reunioes() -> dict:
    validacao_ha = 3
    assinada_ha = 24
    nao_instalada = ordinaria(DESLOCA_NAO_INSTALADA)
    calendario = [
        {"id_reuniao": REUNIAO_NAO_INSTALADA, "data": dia(DESLOCA_NAO_INSTALADA), "hora_inicio": "14:00:00",
         "tipo": TIPOS[0], "titulo": nao_instalada, "status_ata": "NAO_INSTALADA"},
        {"id_reuniao": REUNIAO_ASSINADA, "data": dia(-assinada_ha), "hora_inicio": "14:00:00",
         "tipo": TIPOS[0], "titulo": f"{nao_instalada}, reagendada", "status_ata": "ASSINADA"},
        {"id_reuniao": REUNIAO_EM_VALIDACAO, "data": dia(-validacao_ha), "hora_inicio": "10:30:00",
         "tipo": TIPOS[1], "titulo": "Análise da queda no CTI Adulto", "status_ata": "AGUARDANDO_VALIDACAO"},
        {"id_reuniao": "exemplo-reuniao-rapida", "data": dia(-1), "hora_inicio": None,
         "tipo": TIPOS[3], "titulo": "Reunião rápida de segurança, Emergência", "status_ata": None,
         "rapida": True, "texto": "Pulseiras de identificação conferidas na troca de plantão.\nDois leitos sem placa de risco de queda, já corrigidos.",
         "participantes": ["Marina Couto", "Felipe Andrade"]},
        {"id_reuniao": REUNIAO_DO_DIA, "data": dia(0), "hora_inicio": "14:00:00",
         "tipo": TIPOS[0], "titulo": ordinaria(0), "status_ata": "PROGRAMADA"},
        {"id_reuniao": "exemplo-reuniao-seguinte", "data": dia(DESLOCA_SEGUINTE), "hora_inicio": "14:00:00",
         "tipo": TIPOS[0], "titulo": ordinaria(DESLOCA_SEGUINTE), "status_ata": "PROGRAMADA"},
    ]
    calendario.sort(key=lambda r: r["data"])

    nome = {m["id"]: m["nome"] for m in SEED["membros"]}
    vigentes = [m for m in SEED["membros"] if m["estado"] in ("ativo", "a_vencer", "em_carencia")]
    convocados = [
        {"participante_id": m["id"], "nome": m["nome"], "estado": m["estado"], "email_enviado": True} for m in vigentes
    ]
    pauta = {
        "id_reuniao": REUNIAO_DO_DIA,
        "disponivel": True,
        "disponivel_em": dia_util_antes(HOJE, 5).isoformat(),
        "blocos": [
            {"chave": "pendencias", "titulo": "Pendências da reunião anterior", "sem_dados": False, "itens": [
                {"texto": "Trocar as placas de risco de queda do CTI Adulto", "id_acao": "A-0398", "situacao": "Concluída"},
                {"texto": "Treinar a equipe da noite na dupla checagem de medicação", "id_acao": "A-0401", "situacao": "Em andamento"},
                {"texto": "Revisar o protocolo de identificação na Emergência", "id_acao": "A-0405", "situacao": "Atrasada"},
            ]},
            {"chave": "agenda", "titulo": "Agenda regulatória", "sem_dados": False, "itens": [
                {"texto": f"Envio das notificações ao Notivisa, prevista para {datetime.fromisoformat(dia(4)).strftime('%d/%m/%Y')}"},
            ]},
            {"chave": "indicadores", "titulo": "Indicadores", "sem_dados": True, "itens": []},
            {"chave": "casos", "titulo": "Casos", "sem_dados": True, "itens": []},
            {"chave": "planos_vencidos", "titulo": "Planos de ação vencidos", "sem_dados": True, "itens": []},
            {"chave": "alertas_sanitarios", "titulo": "Alertas sanitários", "sem_dados": True, "itens": []},
        ],
        "editada_em": None,
        "pode_editar": True,
        "convocacao": {"convocada_em": instante(dia_util_antes_dias()), "convocados": convocados},
        "pode_convocar": False,
        "recusa_da_convocacao": None,
    }
    situacoes = {"P17800": "presente", "P17801": "presente", "P17802": "presente", "P17803": "ausente_justificado",
                 "P17805": "presente"}
    pessoas = [
        {"participante_id": m["id"], "nome": m["nome"], "papel": m["papel"], "conta_para_quorum": True,
         "situacao": situacoes.get(m["id"])}
        for m in vigentes
    ] + [
        {"participante_id": "P17808", "nome": "Tiago Martins", "papel": None, "conta_para_quorum": False,
         "situacao": "convidado"},
    ]
    presentes = sum(1 for p in pessoas if p["conta_para_quorum"] and p["situacao"] == "presente")
    total = len(vigentes)
    presenca = {
        "id_reuniao": REUNIAO_DO_DIA,
        "data": dia(0),
        "status_ata": "PROGRAMADA",
        "pessoas": pessoas,
        "quorum": {"total": total, "presentes": presentes, "minimo": total // 2 + 1,
                   "presidencia_ou_suplente": True, "instalada": presentes >= total // 2 + 1},
        "pode_registrar": True,
    }

    return {
        "nsp/reunioes": {"reunioes": calendario, "tipos": TIPOS, "pode_abrir": True, "pode_criar": True},
        f"nsp/reunioes/{REUNIAO_DO_DIA}/pauta": pauta,
        f"nsp/reunioes/{REUNIAO_DO_DIA}/presenca": presenca,
        f"reunioes/{REUNIAO_EM_VALIDACAO}": reuniao_geral(REUNIAO_EM_VALIDACAO, dia(-validacao_ha), TIPOS[1],
                                                         "Análise da queda no CTI Adulto", "AGUARDANDO_VALIDACAO"),
        f"nsp/reunioes/{REUNIAO_EM_VALIDACAO}/ata": {
            "id_reuniao": REUNIAO_EM_VALIDACAO,
            "status_ata": "AGUARDANDO_VALIDACAO",
            "ata": ata(dia(-validacao_ha), "10:30", nome, validada=False),
            "pode_conduzir": True,
            "documento_id": None,
        },
        f"reunioes/{REUNIAO_ASSINADA}": reuniao_geral(REUNIAO_ASSINADA, dia(-assinada_ha), TIPOS[0],
                                                     f"{nao_instalada}, reagendada", "ASSINADA"),
        f"nsp/reunioes/{REUNIAO_ASSINADA}/ata": {
            "id_reuniao": REUNIAO_ASSINADA,
            "status_ata": "ASSINADA",
            "ata": {
                **ata(dia(-assinada_ha), "14:00", nome, validada=True, encerrada=True),
                "assinatura": {"enviada_em": instante(assinada_ha - 1), "erro": None, "cancelada_em": None},
                "encerramento": {"em": dia(-assinada_ha + 8), "assinaram": ["Marina Couto", "Rodrigo Teixeira",
                                 "Juliana Prado"], "nao_assinaram": ["Carlos Mendes"]},
                "trechos_a_conferir": [],
            },
            "pode_conduzir": True,
            "documento_id": "exemplo-doc-ata-12",
        },
    }


def dia_util_antes_dias() -> int:
    return (HOJE - dia_util_antes(HOJE, 4)).days


def reuniao_geral(id_reuniao: str, data: str, tipo: str, titulo: str, status: str) -> dict:
    """A reunião como a página geral da reunião a lê. A ata em si vem da rota do Núcleo."""
    return {
        "id_reuniao": id_reuniao,
        "data": data,
        "tipo": tipo,
        "titulo": titulo,
        "objetivo": None,
        "status_ata": status,
        "total_acoes": 3,
        "acoes_concluidas": 0,
        "hora_inicio": "10:30:00" if status == "AGUARDANDO_VALIDACAO" else "14:00:00",
        "hora_fim": None,
        "json_ata": {"modelo": "nsp_dez_blocos"},
        "url_pdf_preliminar": None,
        "url_pdf_assinado": None,
        "url_transcricao": None,
        "envelope_key_clicksign": None,
        "falha_envio_assinatura": None,
        "data_assinatura": None,
        "fonte": "TRANSCRICAO",
        "metodo_geracao": "TRANSCRICAO",
        "do_nucleo": True,
        "created_at": instante(30),
        "facilitador_id": SEED["presidencia"]["id"],
        "participantes_programada": [],
        "participantes_nao_reconhecidos": [],
    }


def ata(data: str, hora: str, nome: dict, *, validada: bool, encerrada: bool = False) -> dict:
    """A ata do Núcleo em dez blocos. Os nomes só aparecem nas presenças e nas assinaturas."""
    d = datetime.fromisoformat(data).strftime("%d/%m/%Y")
    prazo = (datetime.fromisoformat(data) + timedelta(days=30)).date().isoformat()
    blocos = [
        ("identificacao", "Identificação", "sistema", [f"Reunião do Núcleo de Segurança do Paciente em {d}, às {hora}."]),
        ("presencas_e_quorum", "Presenças e quórum", "sistema", [
            f"Presentes: {nome['P17800']} (Presidência), {nome['P17801']} (Suplente), {nome['P17802']}, {nome['P17805']}.",
            f"Ausente com justificativa: {nome['P17803']}.",
            "Quórum atingido: 4 presentes de 5, mínimo de 3.",
        ]),
        ("pendencias_anteriores", "Situação das pendências da reunião anterior", "sistema", [
            "A-0398, Trocar as placas de risco de queda do CTI Adulto: Concluída.",
            "A-0401, Treinar a equipe da noite na dupla checagem de medicação: Em andamento.",
        ]),
        ("indicadores", "Indicadores", "sistema", []),
        ("casos_analisados", "Casos analisados", "sistema", []),
        ("deliberacoes", "Deliberações", "agente", [
            "Reforçar a avaliação de risco de queda na admissão do CTI Adulto. Responsável: Gerência de Enfermagem.",
            "Instalar barras de apoio nos banheiros dos leitos 4 a 8. Responsável: Manutenção.",
        ]),
        ("plano_de_acao", "Plano de ação", "agente", [
            "Auditar a escala de Morse em 20 prontuários do CTI Adulto por mês.",
            "Repetir a orientação sobre quedas aos acompanhantes na visita.",
        ]),
        ("alertas_sanitarios", "Alertas sanitários", "agente", []),
        ("proxima_reuniao", "Próxima reunião", "agente", ["Reunião ordinária mensal, na data do calendário."]),
        ("assinaturas", "Assinaturas", "sistema", [
            f"Assinaram: {nome['P17800']}, {nome['P17801']}, {nome['P17802']}.",
            f"Não assinou até o encerramento: {nome['P17805']}.",
        ] if encerrada else ["Os presentes assinam pelo envio eletrônico, depois da validação."]),
    ]
    return {
        "modelo": "nsp_dez_blocos",
        "resumida": False,
        "blocos": [{"chave": c, "titulo": t, "origem": o, "itens": i} for c, t, o, i in blocos],
        "deliberacoes": [
            {"texto": "Reforçar a avaliação de risco de queda na admissão do CTI Adulto",
             "responsavel": "Gerência de Enfermagem", "prazo": prazo},
            {"texto": "Instalar barras de apoio nos banheiros dos leitos 4 a 8",
             "responsavel": "Manutenção", "prazo": prazo},
        ],
        "trechos_a_conferir": [] if validada else [
            "O prazo das barras de apoio ficou em dúvida na fala sobre a Manutenção.",
        ],
        "aviso": None,
        "validacao": {"por": SEED["presidencia"]["nome"], "em": instante(20)} if validada else None,
    }


# ----------------------------------------------------------- notificações
#
# A notificação de incidente, a triagem e os prazos (issue #2003, PRD #1979).
# O agente de triagem está desligado: toda notificação chega para classificar
# manualmente, sem sugestão, e a concordância do agente fica sem casos.

CASO_DA_TRIAGEM = "exemplo-notificacao-queda"
CASO_ENCAMINHADO = "exemplo-notificacao-perfurocortante"
CASO_CLASSIFICADO = "exemplo-notificacao-medicacao"
CASO_GRAVE = "exemplo-notificacao-compressa"
CASO_DA_OUVIDORIA = "exemplo-notificacao-ouvidoria"

# Os recursos do Acesso pleno (app/services/seguranca_do_paciente/permissao.py):
# a pessoa de exemplo alcança todas as telas do módulo.
RECURSOS_DO_ACESSO_PLENO = [
    "ver_modulo", "painel", "calendario", "agenda", "membros", "documentos", "capacitacoes", "reunioes",
    "casos", "identidade_notificante", "triagem", "notas_do_comite", "gerir_nucleo", "configuracao",
    "tabela_de_prazos", "casos_graves", "ausencia_da_presidencia",
]


def protocolo(numero: int) -> str:
    """O protocolo do aplicativo, NSP-AAAA-NNNN, no ano de hoje."""
    return f"NSP-{HOJE.year}-{numero:04d}"


def setores_publicos() -> list[dict]:
    return [{"id": f"exemplo-setor-{i + 1}", "nome": nome} for i, nome in enumerate(SEED["setores"])]


def id_do_setor(nome: str) -> str:
    return next(s["id"] for s in setores_publicos() if s["nome"] == nome)


def dias_uteis_depois(inicio: datetime, uteis: int) -> datetime:
    atual = inicio
    while uteis:
        atual += timedelta(days=1)
        if atual.weekday() < 5:
            uteis -= 1
    return atual


def decimo_quinto_dia_util_do_mes_seguinte(dia_base: date) -> datetime:
    ano, mes = (dia_base.year + 1, 1) if dia_base.month == 12 else (dia_base.year, dia_base.month + 1)
    atual = date(ano, mes, 1)
    uteis = 1 if atual.weekday() < 5 else 0
    while uteis < 15:
        atual += timedelta(days=1)
        if atual.weekday() < 5:
            uteis += 1
    return datetime.combine(atual, time(23, 59), FUSO)


def caso(id_: str, numero: int, *, estado: str, origem: str, relato: str, setor: str, dias_atras: int,
         turno: str, chegou: str, grave: bool | None = None, notificante: dict | None = None,
         hora: str = "09:15", **resto) -> dict:
    """A notificação como a lista do Núcleo a lê, para a Presidência (com quem notificou)."""
    return {
        "id": id_,
        "protocolo": protocolo(numero),
        "estado": estado,
        "origem": origem,
        "relato": relato,
        "leito_ou_atendimento": resto.get("leito"),
        "setor": setor,
        "data_ocorrencia": dia(-dias_atras),
        "turno": turno,
        "chegou_ao_paciente": chegou,
        "grave_ou_morte": grave,
        "criado_em": instante(dias_atras, hora),
        "anonimo": notificante is None,
        "notificante": notificante,
        "anexos": resto.get("anexos", []),
        **({"ouvidoria": {"estado": resto["ouvidoria"]}} if "ouvidoria" in resto else {}),
    }


def casos() -> dict[str, dict]:
    renata = {"nome": "Renata Alves", "contato": "renata.alves@exemplo.local"}
    livia = {"nome": "Lívia Castro", "contato": "livia.castro@exemplo.local"}
    lista = [
        caso(CASO_GRAVE, 43, estado="recebida", origem="qr", setor="Centro Cirúrgico", dias_atras=0, hora="07:40",
             turno="manha", chegou="com_dano", grave=True,
             relato="Compressa esquecida na cavidade, percebida no raio X de controle depois da cirurgia. "
                    "O paciente voltou à sala para a retirada."),
        caso(CASO_DA_TRIAGEM, 42, estado="recebida", origem="qr", setor="CTI Adulto", dias_atras=1, hora="06:10",
             turno="noite", chegou="com_dano", grave=False, leito="Leito 6",
             anexos=[{"id": "exemplo-anexo-1", "content_type": "image/jpeg", "tamanho_bytes": 870_400}],
             relato="O paciente levantou sozinho para ir ao banheiro e escorregou ao lado da cama. A grade estava "
                    "abaixada e a campainha ficou fora do alcance. Teve um arranhão no joelho, já avaliado pela "
                    "equipe."),
        caso(CASO_ENCAMINHADO, 41, estado="recebida", origem="modulo", setor="Emergência", dias_atras=2,
             hora="10:30", turno="manha", chegou="nao", notificante=renata,
             relato="Uma técnica de enfermagem se feriu com a agulha ao descartar o material da medicação. "
                    "O coletor de perfurocortantes estava cheio acima da linha."),
        caso(CASO_DA_OUVIDORIA, 40, estado="recebida", origem="ouvidoria", setor="Radiologia", dias_atras=5,
             hora="15:20", turno="tarde", chegou="nao_sei", ouvidoria="Em análise",
             relato="A acompanhante conta que o paciente ficou na maca do corredor sem a pulseira de "
                    "identificação durante a espera pela tomografia."),
        caso(CASO_CLASSIFICADO, 39, estado="classificada", origem="endereco", setor="Farmácia", dias_atras=4,
             hora="11:45", turno="tarde", chegou="com_dano", grave=False, notificante=livia,
             relato="O paciente recebeu a mesma dose de dipirona duas vezes no horário das 14h, por falha na "
                    "checagem da prescrição. Teve queda da pressão, revertida, e ficou em observação."),
    ]
    return {c["id"]: c for c in lista}


def prazos_do_caso(c: dict) -> tuple[list[dict], dict]:
    """Os prazos da faixa D, congelados na confirmação, e a notificação ao VigiMed."""
    chegou = datetime.fromisoformat(c["criado_em"])
    confirmado = chegou + timedelta(hours=26)
    prazos = [
        {"marco": "confirmacao_ao_notificante", "rotulo": "Confirmação a quem notificou", "tipo": "interno",
         "valor": 24, "unidade": "horas_corridas", "vence_em": (chegou + timedelta(hours=24)).isoformat()},
        {"marco": "triagem", "rotulo": "Triagem e classificação", "tipo": "interno", "valor": 3,
         "unidade": "dias_uteis", "vence_em": dias_uteis_depois(chegou, 3).isoformat()},
        {"marco": "conclusao_da_investigacao", "rotulo": "Conclusão da investigação e do plano de ação",
         "tipo": "interno", "valor": 10, "unidade": "dias_uteis",
         "vence_em": dias_uteis_depois(chegou, 10).isoformat()},
        {"marco": "notificacao_externa", "rotulo": "Notificação externa à vigilância sanitária", "tipo": "legal",
         "valor": 15, "unidade": "dia_util_do_mes_seguinte",
         "vence_em": decimo_quinto_dia_util_do_mes_seguinte(confirmado.date()).isoformat()},
    ]
    externa = {"sistema": "vigimed", "rotulo": "VigiMed", "prazo_legal": prazos[-1]["vence_em"], "estado": "pendente"}
    return prazos, externa


CATEGORIAS = [
    ("IDP", "Identificação do paciente"), ("MED", "Medicamentos e soluções"), ("SAN", "Sangue e hemocomponentes"),
    ("CIR", "Cirurgia e anestesia"), ("PRO", "Processo clínico e cuidado"), ("QUE", "Quedas"),
    ("LPP", "Lesão por pressão e pele"), ("DIS", "Dispositivos invasivos"), ("INF", "Infecção"),
    ("EXA", "Exames e diagnóstico"), ("EQP", "Equipamentos e materiais"), ("GAS", "Oxigênio e gases medicinais"),
    ("NUT", "Dieta e nutrição"), ("COM", "Comunicação e documentação"), ("ACE", "Acesso, transferência e alta"),
    ("CMP", "Comportamento"), ("EST", "Estrutura e ambiente"), ("MAT", "Materno-infantil"), ("OUT", "Outros"),
]
EVENTOS = [
    (1, "Alta ou liberação de paciente incapaz de tomar decisões para pessoa não autorizada"),
    (2, "Contaminação na administração de oxigênio ou gases medicinais"),
    (7, "Lesão grave associada a queda do paciente durante o atendimento"),
    (8, "Lesão por pressão estágio 3"),
]
CORTES = {"janela_meses": 12, "incomum_a_partir": 1, "ocasional_a_partir": 2, "frequente_a_partir": 4}

# O que o roteiro escolhe na triagem manual da queda: evento adverso leve, faixa D.
CLASSIFICACAO_DA_QUEDA = {"categoria": "QUE", "faixa": "D"}


def contexto(categoria: str | None) -> dict:
    if categoria is None:
        return {"recorrencia": None, "janela_da_recorrencia_dias": 60, "parecidos": [], "anteriores": None,
                "frequencia": None, "prioridade": None, "cortes": CORTES}
    return {
        "recorrencia": 3,
        "janela_da_recorrencia_dias": 60,
        "parecidos": [
            {"id": "exemplo-notificacao-queda-anterior-1", "protocolo": protocolo(31), "data_ocorrencia": dia(-21),
             "estado": "classificada", "assunto": "Queda ao sair da cama sem ajuda"},
            {"id": "exemplo-notificacao-queda-anterior-2", "protocolo": protocolo(27), "data_ocorrencia": dia(-38),
             "estado": "classificada", "assunto": "Queda no banheiro do leito 4"},
        ],
        "anteriores": 2,
        "frequencia": "ocasional",
        "prioridade": "baixa",
        "cortes": CORTES,
    }


def tela_da_triagem(c: dict, encaminhamentos: list[dict] | None = None) -> dict:
    """A tela da triagem com o agente desligado: sem sugestão, para classificar à mão."""
    return {
        "caso": {**c, "percebido_ou_reclamacao": "nao_sei"},
        "sugestao": None,
        "decisao": None,
        "pendente": True,
        "classificar_manualmente": True,
        "motivo_classificar_manualmente": "agente_desligado",
        "conferencia": {"campo_a_campo": False, "motivos": [], "campos": [
            "assunto", "natureza", "grau_de_dano", "categoria", "incidente", "evento", "iras", "risco_de_imagem",
            "protocolo_basico", "canais", "faixa"]},
        "contexto": contexto(None),
        "opcoes": {
            "categorias": [{"codigo": codigo, "nome": nome} for codigo, nome in CATEGORIAS],
            "eventos": [{"item": item, "evento": evento} for item, evento in EVENTOS],
        },
        **({"encaminhamentos": encaminhamentos} if encaminhamentos else {}),
    }


def tabela_de_prazos() -> dict:
    rotulos = {
        "confirmacao_ao_notificante": "Confirmação a quem notificou",
        "comunicacao_a_direcao": "Comunicação à Direção",
        "triagem": "Triagem e classificação",
        "inicio_da_investigacao": "Início da investigação",
        "conclusao_da_investigacao": "Conclusão da investigação e do plano de ação",
        "reuniao_de_analise": "Reunião de análise",
    }
    # A carga do art. 26 (migration 208), com a triagem da faixa E já trocada de 5 para 3 dias úteis.
    valores = {
        "confirmacao_ao_notificante": [(24, "horas_corridas")] * 5,
        "comunicacao_a_direcao": [(2, "horas_corridas"), (24, "horas_corridas")] + [(None, None)] * 3,
        "triagem": [(4, "horas_uteis"), (1, "dias_uteis"), (2, "dias_uteis"), (3, "dias_uteis"), (3, "dias_uteis")],
        "inicio_da_investigacao": [(24, "horas_uteis"), (3, "dias_uteis"), (5, "dias_uteis"), (None, None),
                                   (None, None)],
        "conclusao_da_investigacao": [(45, "dias_corridos"), (30, "dias_corridos"), (20, "dias_uteis"),
                                      (10, "dias_uteis"), (None, None)],
        "reuniao_de_analise": [(7, "dias_uteis"), (15, "dias_uteis")] + [(None, None)] * 3,
    }
    faixas = ["A", "B", "C", "D", "E"]
    internos = [
        {"faixa": faixa, "marco": marco, "rotulo": rotulos[marco], "valor": valor, "unidade": unidade,
         "editavel": True}
        for marco, celulas in valores.items()
        for faixa, (valor, unidade) in zip(faixas, celulas)
    ]
    quinze = "Até o 15º dia útil do mês seguinte"
    legais = [
        {"marco": "notificacao_externa", "rotulo": "Notificação externa à vigilância sanitária", "editavel": False,
         "celulas": {"A": "72 horas corridas do incidente", "B": quinze, "C": quinze, "D": quinze,
                     "E": "Quase erro: até o 15º dia útil do mês seguinte. Circunstância de risco: não se notifica"}},
        {"marco": "complementacao_da_notificacao_externa", "rotulo": "Complementação da notificação externa",
         "editavel": False, "celulas": {"A": "60 dias corridos do incidente"}},
    ]
    historico = [
        {"faixa": "E", "marco": "triagem", "rotulo": rotulos["triagem"], "de": {"valor": 5, "unidade": "dias_uteis"},
         "para": {"valor": 3, "unidade": "dias_uteis"}, "quem": SEED["presidencia"]["nome"],
         "quando": instante(20, "16:30")},
    ]
    return {
        "faixas": faixas,
        "unidades": [{"valor": "horas_corridas", "rotulo": "horas corridas"},
                     {"valor": "horas_uteis", "rotulo": "horas úteis"},
                     {"valor": "dias_corridos", "rotulo": "dias corridos"},
                     {"valor": "dias_uteis", "rotulo": "dias úteis"}],
        "internos": internos,
        "legais": legais,
        "historico": historico,
        "pode_editar": True,
    }


def recalibracao() -> dict:
    """A recalibração de 30 dias à espera da decisão, com o agente desligado."""
    sem_dados = {5, 7, 9, 14, 15, 17, 18, 19}
    linhas = {
        1: (["14 notificações nos últimos 30 dias.", "CTI Adulto: 5", "Emergência: 4", "Centro Cirúrgico: 3",
             "Farmácia: 2", "Setores sem notificação nos últimos 30 dias: Laboratório, Nutrição, Radiologia."], True),
        2: (["Nenhum caso com sugestão do agente e decisão da Presidência ainda."], False),
        3: (["0 casos com o grau de dano subido pela Presidência."], False),
        4: (["Marcados pelo agente como evento que nunca deveria ocorrer: 0 sim e 0 possível.",
             "Graves ou com óbito sem marcação na decisão: 0.",
             "Marcados pela Presidência e não reconhecidos pelo agente: 0."], False),
        6: (["Faixa B: 3,5 horas corridas em média (1 caso)", "Faixa D: 20,2 horas corridas em média (6 casos)",
             "Faixa E: 30,0 horas corridas em média (3 casos)"], False),
        8: (["Nenhuma pergunta de esclarecimento feita ainda."], False),
        10: (["4 de 14 notificações sem identificação nos últimos 30 dias (29%)."], False),
        11: (["Nenhum caso com sugestão do agente ainda."], False),
        12: (["Últimos 30 dias: 14. Os 30 dias anteriores: 0."], False),
        13: (["Nenhum caso leve confirmado nas últimas 4 semanas."], False),
        16: (["2 reuniões do Núcleo nos últimos 60 dias, 1 com ata assinada.",
              "Ordinárias mensais nos últimos 30 dias: 1."], False),
    }
    itens_do_anexo_f = [
        (1, 4, "Volume de notificações", "Setor assistencial com zero notificação"),
        (2, 4, "Concordância agente e coordenação", "Abaixo de 85% em grau de dano"),
        (3, 4, "Erros para baixo", "Qualquer caso grave ou óbito sugerido como menor"),
        (4, 4, "Lista ANVISA", "Item da lista não reconhecido pelo agente"),
        (5, 4, "Prazos legais", "Qualquer atraso"),
        (6, 4, "Tempo de triagem", "Faixa A acima de 4 horas úteis"),
        (7, 4, "Casos parados", "Mais de 10% vencidas"),
        (8, 4, "Perguntas de esclarecimento", "Menos de 30% respondidas: rever a redação"),
        (9, 4, "Roteamento", "Devoluções recorrentes do mesmo tipo"),
        (10, 4, "Anônimas", "Acima de 60% indica medo de identificação"),
        (11, 4, "Amostra de leitura", "Justificativa genérica ou fato inventado"),
        (12, 5, "Tendência do volume", "Queda sem causa conhecida"),
        (13, 5, "Aprovação em lote", "Abaixo de 90%: manter o lote desligado"),
        (14, 5, "Planos de ação", "Mais de 50% dos planos só com ações fracas"),
        (15, 5, "Sinais de conduta", "Queda de notificações após encaminhamento"),
        (16, 5, "Reuniões", "Reunião mensal não realizada"),
        (17, 5, "Efetividade", "Caso encerrado sem verificação quando exigida"),
        (18, 5, "Dossiê", "Documento incompleto"),
        (19, 5, "Carga da coordenação", "Acima do previsto: rever automações"),
    ]
    itens = []
    for numero, secao, titulo, sinal in itens_do_anexo_f:
        texto, alerta = ([], False) if numero in sem_dados else linhas[numero]
        itens.append({"numero": numero, "secao": secao, "titulo": titulo, "sinal": sinal,
                      "com_dados": numero not in sem_dados, "linhas": texto, "alerta": alerta})
    return {
        "recalibracoes": [{"marco": 30, "devida_em": dia(-2), "decisao": None, "decidido_por": None,
                           "decidido_em": None}],
        "decisoes": [{"valor": "manter", "rotulo": "Manter o agente como está"},
                     {"valor": "ajustar", "rotulo": "Ajustar o prompt e a base"},
                     {"valor": "ligar_lote", "rotulo": "Ligar a aprovação em lote"}],
        "itens": itens,
        "pode_decidir": True,
    }


def idades_da_fila(fila: list[dict]) -> list[dict]:
    """As triagens pendentes por idade, contadas como o servidor conta, da mais velha à mais nova."""
    agora = datetime.now(FUSO)
    contagem = [0, 0, 0]
    for c in fila:
        idade = agora - datetime.fromisoformat(c["criado_em"])
        contagem[0 if idade > timedelta(days=3) else 1 if idade >= timedelta(days=1) else 2] += 1
    rotulos = [("há mais de 3 dias", True), ("de 1 a 3 dias", False), ("há menos de 1 dia", False)]
    return [
        {"rotulo": f"{quantos} {rotulo}", "link": "/seguranca-do-paciente/notificacoes/triagem", "urgente": urgente}
        for quantos, (rotulo, urgente) in zip(contagem, rotulos)
        if quantos
    ]


def notificacoes() -> dict:
    lista = casos()
    presidencia = SEED["presidencia"]
    fila = sorted((c for c in lista.values() if c["estado"] == "recebida"), key=lambda c: c["criado_em"])
    classificado = lista[CASO_CLASSIFICADO]
    prazos, externa = prazos_do_caso(classificado)
    vence = datetime.fromisoformat(externa["prazo_legal"])
    encaminhamentos = [{
        "destinos": ["nucleo", "seguranca_do_trabalho"],
        "motivo": "Acidente com perfurocortante na equipe, que é da Segurança do Trabalho.",
        "orientacao": None,
        "criado_em": instante(1, "11:20"),
        "recebimentos": [{
            "destino": "seguranca_do_trabalho", "setor": "Segurança do Trabalho", "destinatario_nome": "Tiago Martins",
            "papel": "titular", "enviado_em": instante(1, "11:20"), "reenviado_em": None,
            "recebido_em": instante(1, "14:05"),
        }],
    }]
    return {
        "participantes/me": {
            "id": presidencia["id"], "nome_completo": presidencia["nome"], "email": presidencia["email"],
            "cargo": presidencia["cargo"], "role": "coordenador", "ativo": True, "is_externo": False,
            "is_super_admin": False, "access_profile": "regular", "perfil_pop": None, "perfil_ouvidoria": None,
            "perfil_contas_medicas": None, "recursos_nsp": RECURSOS_DO_ACESSO_PLENO, "papel_ouvidoria": None,
            "ve_membros_do_comite": False,
        },
        "nsp/inicio": {"casos_graves": [
            {"protocolo": lista[CASO_GRAVE]["protocolo"], "setor": lista[CASO_GRAVE]["setor"],
             "criado_em": lista[CASO_GRAVE]["criado_em"]},
        ]},
        "nsp/acao-de-hoje": {"grupos": [
            {"chave": "casos_abertos", "titulo": "Casos A e B abertos", "link": "/seguranca-do-paciente/notificacoes",
             "ilegivel": False, "total": 0, "itens": []},
            {"chave": "triagens_pendentes", "titulo": "Triagens pendentes",
             "link": "/seguranca-do-paciente/notificacoes/triagem", "ilegivel": False, "total": len(fila),
             "itens": idades_da_fila(fila)},
            {"chave": "prazos_legais", "titulo": "Prazos legais a vencer", "link": "/seguranca-do-paciente/notificacoes",
             "ilegivel": False, "total": 1, "itens": [
                 {"rotulo": f"{classificado['protocolo']}, VigiMed até o 15º dia útil: vence em "
                            f"{vence:%d/%m/%Y} às {vence:%H:%M}",
                  "link": f"/seguranca-do-paciente/notificacoes/{CASO_CLASSIFICADO}", "urgente": False},
             ]},
            {"chave": "termos_pendentes", "titulo": "Termos pendentes", "link": "/seguranca-do-paciente/membros",
             "ilegivel": False, "total": 1, "itens": [
                 {"rotulo": "1 esperando a assinatura", "link": "/seguranca-do-paciente/membros", "urgente": False},
             ]},
        ]},
        "nsp/publico/setores": {"setores": setores_publicos()},
        "nsp/notificacoes": {"notificacoes": list(lista.values())},
        f"nsp/notificacoes/{CASO_CLASSIFICADO}": {**classificado, "prazos": prazos, "notificacao_externa": externa},
        "nsp/triagem": {"fila": [
            {"id": c["id"], "protocolo": c["protocolo"], "criado_em": c["criado_em"],
             "data_ocorrencia": c["data_ocorrencia"], "setor": c["setor"], "grave_ou_morte": c["grave_ou_morte"],
             "faixa": None, "assunto": None, "classificar_manualmente": True, "cabe_no_lote": False}
            for c in fila
        ], "lote_ligado": False},
        f"nsp/triagem/{CASO_DA_TRIAGEM}": tela_da_triagem(lista[CASO_DA_TRIAGEM]),
        f"nsp/triagem/{CASO_DA_TRIAGEM}/contexto?categoria={CLASSIFICACAO_DA_QUEDA['categoria']}"
        f"&faixa={CLASSIFICACAO_DA_QUEDA['faixa']}": contexto(CLASSIFICACAO_DA_QUEDA["categoria"]),
        f"nsp/triagem/{CASO_ENCAMINHADO}": tela_da_triagem(lista[CASO_ENCAMINHADO], encaminhamentos),
        "nsp/configuracao": {"endereco_da_notificacao": "https://app.exemplo.local/notificar"},
        "nsp/configuracao/cortes-de-frequencia": CORTES,
        "nsp/configuracao/prazos": tabela_de_prazos(),
        "nsp/configuracao/concordancia": {
            "versoes": {"prompt": "1", "base": "1"},
            "casos": 0,
            "eixos": [{"eixo": eixo, "rotulo": rotulo, "acatadas": 0, "total": 0, "percentual": None}
                      for eixo, rotulo in [("natureza", "Natureza"), ("grau_de_dano", "Grau de dano"),
                                           ("categoria", "Categoria"), ("faixa", "Faixa"), ("canal", "Canal"),
                                           ("marcadores", "Marcadores")]],
            "erros_para_baixo": [],
        },
        "nsp/recalibracao": recalibracao(),
        # Os dois POST que o roteiro responde: o envio do formulário, que devolve o
        # protocolo de exemplo sem gravar nada, e a consulta do acompanhamento.
        "POST nsp/publico/notificacoes": {
            "protocolo": protocolo(44), "criado_em": instante(0, "08:05"), "codigo_acompanhamento": "K7QM-4TZP-WD82",
        },
        "POST nsp/publico/acompanhamento": {
            "protocolo": classificado["protocolo"], "estado": "Em análise", "orientacao": None,
        },
    }


def tabela() -> dict:
    return {**membros(), **documentos(), **capacitacoes(), **agenda(), **reunioes(), **notificacoes()}


def do_roteiro() -> dict:
    """O que o roteiro lê para clicar e para conferir a tela."""
    return {
        "composicao": dia_da_composicao(),
        "reuniao_do_dia": ordinaria(0),
        "caso_da_triagem": CASO_DA_TRIAGEM,
        "caso_encaminhado": CASO_ENCAMINHADO,
        "caso_classificado": CASO_CLASSIFICADO,
        "protocolo_da_triagem": casos()[CASO_DA_TRIAGEM]["protocolo"],
        "protocolo_classificado": casos()[CASO_CLASSIFICADO]["protocolo"],
        "contato_classificado": casos()[CASO_CLASSIFICADO]["notificante"]["contato"],
    }


if __name__ == "__main__":
    if "--roteiro" in sys.argv:
        print(json.dumps(do_roteiro(), ensure_ascii=False))
    else:
        print(json.dumps(tabela(), ensure_ascii=False))
