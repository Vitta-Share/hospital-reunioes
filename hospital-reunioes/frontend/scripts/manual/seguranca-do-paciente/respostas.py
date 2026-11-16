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
da composição e o título da reunião do dia.
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


def tabela() -> dict:
    return {**membros(), **documentos(), **capacitacoes(), **agenda(), **reunioes()}


if __name__ == "__main__":
    if "--roteiro" in sys.argv:
        print(json.dumps({"composicao": dia_da_composicao(), "reuniao_do_dia": ordinaria(0)}, ensure_ascii=False))
    else:
        print(json.dumps(tabela(), ensure_ascii=False))
