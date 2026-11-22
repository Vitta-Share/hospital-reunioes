#!/usr/bin/env python3
"""Roteiro dos prints da página de Reuniões e Pendências do manual (issue #1721).

A página mora em `hospital-reunioes/frontend/public/manual/reunioes-e-pendencias/`
(ADR 0094, decisões 4 e 5), e cada PNG dela sai daqui: tela real do app local,
capturada pelo `playwright-cli`, com balões numerados que apontam onde clicar.
Quando a tela muda, este roteiro roda de novo e refaz todas as imagens.

Receita:

1. Supabase local e a stack do app no ar (`/atualizar-app`).
2. `python3 tools/prints_manual_reunioes.py --semear`: as pessoas, a reunião e
   as Pendências de exemplo. É idempotente e recusa qualquer banco que não seja
   o local.
3. `python3 tools/prints_manual_reunioes.py`: refaz todos os prints (ou um só,
   com `--print <nome>`).

**Nenhum dado real.** O repositório é público. As pessoas de exemplo vivem numa
faixa de ids só deste módulo (`P17210` a `P17214`, a issue com um dígito), com
e-mail em `exemplo.local`, para não trocar as pessoas dos roteiros dos outros
módulos (o `merge-duplicates` reescreve a linha inteira de quem tem o mesmo
id). Antes de cada captura, a guarda lê o texto visível da tela e recusa o
print que mostre o nome de alguém de fora do seed ou o título de uma reunião
que não é a de exemplo.

Uso: python3 tools/prints_manual_reunioes.py [--semear] [--print <nome>]
     [--base http://localhost:3000]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENV_LOCAL = RAIZ / "hospital-reunioes" / ".env"
PASTA_DA_PAGINA = (
    RAIZ / "hospital-reunioes" / "frontend" / "public" / "manual" / "reunioes-e-pendencias"
)

SESSAO = "manual-reunioes-1721"
COMPUTADOR = {"width": 1440, "height": 900}
SENHA = "ManualReunioes1721!"
DOMINIO_DE_EXEMPLO = "exemplo.local"

# (id, nome, cargo, setor, perfil de acesso)
FACILITADORA = ("P17210", "Clara Mendonça", "Coordenadora de Enfermagem", "Coordenação de Enfermagem", "regular")
PESSOAS = [
    FACILITADORA,
    ("P17211", "Rodrigo Saldanha", "Farmacêutico", "Farmácia", "regular"),
    ("P17212", "Patrícia Vilela", "Enfermeira", "UTI Adulto", "regular"),
    ("P17213", "Fábio Guimarães", "Técnico de Manutenção", "Engenharia Clínica", "regular"),
    ("P17214", "Simone Furtado", "Nutricionista", "Nutrição", "regular"),
    # O ranking com nomes é só do Super admin (issue #2144): o print dele entra
    # por ela (issue #1880).
    ("P17215", "Laura Pacheco", "Gerente de Qualidade", "Qualidade", "super_admin"),
]


def email_de(nome: str) -> str:
    """O e-mail inventado da pessoa de exemplo, sem acento."""
    import unicodedata

    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return f"{sem_acento.lower().replace(' ', '.')}@{DOMINIO_DE_EXEMPLO}"


# A reunião de exemplo que atravessa a página inteira: ela é marcada, recebe a
# Transcrição, vira Ata e solta as Pendências. O roteiro muda o estado dela
# antes de cada print, porque é a mesma reunião em momentos diferentes.
REUNIAO = "MRP1721A"
TITULO_REUNIAO = "Indicadores da UTI Adulto"
# A reunião já assinada, de onde vêm as Pendências da lista.
REUNIAO_ASSINADA = "MRP1721B"
TITULO_ASSINADA = "Comissão de Controle de Infecção"
# A reunião com a Ata em assinatura, de outra Facilitadora: é nela que a
# Clara, como responsável, contesta o item dela (issue #1880).
REUNIAO_EM_ASSINATURA = "MRP1721C"
TITULO_EM_ASSINATURA = "Comissão de Farmácia e Terapêutica"
FACILITADORA_DA_FARMACIA = "P17214"
REUNIOES_DO_SEED = {
    REUNIAO: TITULO_REUNIAO,
    REUNIAO_ASSINADA: TITULO_ASSINADA,
    REUNIAO_EM_ASSINATURA: TITULO_EM_ASSINATURA,
}

# (id, descrição, responsável, prazo em dias a partir de hoje, estado, entregável)
# O estado é o gravado; atrasada é calculada (prazo vencido e aberta).
PENDENCIAS = [
    ("PE1721A", "Revisar o protocolo de troca de curativos", "P17212", 6, "PENDENTE", "Protocolo revisado no mural"),
    ("PE1721B", "Conferir o estoque de antissépticos", "P17211", 3, "EM_PROGRESSO", "Planilha de estoque conferida"),
    ("PE1721C", "Calibrar as bombas de infusão do leito 4 ao 8", "P17213", -2, "PENDENTE", "Laudo de calibração"),
    ("PE1721D", "Ajustar a dieta dos pacientes em jejum prolongado", "P17214", -5, "CONCLUIDO", "Cardápio ajustado"),
    # A da própria Facilitadora: o print do Início mostra a fila dela.
    ("PE1721E", "Mandar a pauta da próxima reunião da UTI", "P17210", 4, "PENDENTE", "Pauta enviada aos participantes"),
    # A da Clara na Ata em assinatura da Farmácia: a que ela contesta.
    ("PE1721F", "Atualizar a lista de antibióticos padronizados", "P17210", 10, "PENDENTE", "Lista publicada"),
]
REUNIAO_DA_PENDENCIA = {"PE1721F": REUNIAO_EM_ASSINATURA}

# A Contestação já aberta, que a Clara responde como Facilitadora.
CONTESTADA = "PE1721B"
MOTIVO_DA_CONTESTACAO = (
    "O estoque de antissépticos é da Farmácia Central, e o fornecedor só entrega "
    "na semana que vem. O prazo de 3 dias não fecha."
)

# A Rotina das linhas da Ata assinada, com as Verificações das últimas semanas.
ROTINA = "17210000-0000-4000-8000-000000001880"
DESCRICAO_DA_ROTINA = "Conferir o carrinho de emergência da UTI"
RESPONSAVEL_DA_ROTINA = "P17212"
# (semanas antes da atual, resultado, anotação, marcada com atraso)
VERIFICACOES = [
    (5, "REALIZADA", None, False),
    (4, "NAO_REALIZADA", "O carrinho estava em uso numa intercorrência; conferido no dia seguinte.", False),
    (3, "REALIZADA", None, False),
    (2, "REALIZADA", None, True),
    # A semana passada fica sem marcação: aparece como ciclo atrasado.
]

DEFINICAO_DE_PROCESSO = "17210000-0000-4000-8000-000000001881"
TRECHO_DO_PROCESSO = (
    "O curativo do cateter central é trocado a cada 7 dias, ou antes se estiver "
    "úmido ou solto, e cada troca é registrada no prontuário."
)

# O link pessoal da pessoa que nunca entrou (issue #1878). O token é de
# exemplo e só abre as Pendências de exemplo do Fábio no banco local.
TOKEN_DO_LINK = "manual-reunioes-1880-link-de-exemplo"
DONO_DO_LINK = "P17213"

# Quem entra no app para cada print; o resto sai pela Facilitadora.
QUEM_TIRA = {"ranking": "P17215"}


# --------------------------------------------------------------------------
# A guarda do dado real
# --------------------------------------------------------------------------


class DadoRealNoPrint(Exception):
    """O print ia para o repositório público com dado de fora do seed."""


def exigir_so_dado_de_exemplo(texto_visivel: str, nomes_de_fora: list[str], nome: str) -> None:
    """Recusa a captura quando o texto da tela traz nome ou título de fora do seed.

    `nomes_de_fora` são os nomes completos dos participantes e os títulos das
    reuniões do banco local que este roteiro não semeou. Nome de uma palavra só
    fica de fora da conta: casaria com qualquer texto de tela. A conta é em
    caixa normalizada: o CSS põe botão, cabeçalho e etiqueta em caixa alta e o
    `innerText` devolve o texto já transformado.
    """
    tela = texto_visivel.casefold()
    achados = sorted(
        {n for n in nomes_de_fora if len(n.split()) >= 2 and n.casefold() in tela}
    )
    if achados:
        raise DadoRealNoPrint(
            f"{nome}: a tela mostra {', '.join(achados)}, que não é dado de "
            "exemplo. O repositório é público: o print não sai."
        )


# --------------------------------------------------------------------------
# O banco local
# --------------------------------------------------------------------------


def credenciais_locais(env: Path = ENV_LOCAL) -> tuple[str, str]:
    """URL e chave de serviço do `.env` local. Banco que não é local, recusa."""
    campos = {}
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            campos[chave.strip()] = valor.strip().strip('"')
    url = campos.get("SUPABASE_URL", "")
    chave = campos.get("SUPABASE_SERVICE_KEY") or campos.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if "127.0.0.1" not in url and "localhost" not in url:
        raise SystemExit(f"recusado: '{url}' não é o Supabase local.")
    return url, chave


def _pedir(caminho: str, metodo: str = "GET", corpo=None, prefer: str | None = None):
    url, chave = credenciais_locais()
    cabecalhos = {
        "apikey": chave,
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
    }
    if prefer:
        cabecalhos["Prefer"] = prefer
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(f"{url}{caminho}", data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=20) as resposta:
            texto = resposta.read().decode()
            return json.loads(texto) if texto.strip() else None
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        if metodo == "POST" and caminho == "/auth/v1/admin/users" and "already" in texto:
            return None
        raise SystemExit(f"{metodo} {caminho}: {e.code} {texto[:300]}")


def _rest(caminho: str, metodo: str = "GET", corpo=None, prefer: str | None = None):
    return _pedir(f"/rest/v1/{caminho}", metodo, corpo, prefer)


def _rest_tudo(caminho: str, por_pagina: int = 500) -> list:
    """Todas as linhas de um GET, de página em página.

    O PostgREST corta cada resposta em `max_rows` (1000 no `config.toml`
    local), sem aviso. A página fica abaixo do teto e o laço só para na
    página que veio incompleta.
    """
    linhas: list = []
    while True:
        pagina = _rest(f"{caminho}&limit={por_pagina}&offset={len(linhas)}")
        linhas.extend(pagina)
        if len(pagina) < por_pagina:
            return linhas


def _login_de_exemplo(email: str, nome: str) -> str:
    """Cria (ou reaproveita) o login da pessoa de exemplo no Supabase local."""
    criado = _pedir(
        "/auth/v1/admin/users",
        "POST",
        {"email": email, "password": SENHA, "email_confirm": True, "user_metadata": {"nome": nome}},
    )
    if criado:
        return criado["id"]
    pagina = 1
    while True:
        usuarios = _pedir(f"/auth/v1/admin/users?page={pagina}&per_page=200")["users"]
        for usuario in usuarios:
            if usuario["email"] == email:
                _pedir(
                    f"/auth/v1/admin/users/{usuario['id']}",
                    "PUT",
                    {"password": SENHA, "user_metadata": {"nome": nome}},
                )
                return usuario["id"]
        if len(usuarios) < 200:
            raise SystemExit(f"login {email} não encontrado depois de criado.")
        pagina += 1


def _dia(delta: int) -> str:
    return (dt.date.today() + dt.timedelta(days=delta)).isoformat()


def _dia_no_mes(delta: int) -> str:
    """Um dia a `delta` de hoje, rebatido para dentro do mês de hoje.

    O Calendário abre no mês de hoje: reunião marcada no mês seguinte some do
    print da virada do mês.
    """
    hoje = dt.date.today()
    dia = hoje + dt.timedelta(days=delta)
    if dia.month != hoje.month:
        dia = hoje - dt.timedelta(days=delta)
    return dia.isoformat()


def json_da_ata() -> dict:
    """A Ata que o assistente escreveria a partir da Transcrição de exemplo."""
    return {
        "objetivo": "Acompanhar os indicadores da UTI Adulto e combinar as ações do mês.",
        "hora_inicio": "09:00",
        "hora_fim": "10:00",
        "participantes": [
            {"nome": nome, "cargo": cargo, "setor": setor, "presente": True}
            for _, nome, cargo, setor, _ in PESSOAS
        ],
        "discussao": [
            {
                "titulo": "Infecção de cateter",
                "descricao": "A equipe mostrou a taxa do mês e os leitos com mais troca de curativo.",
                "decisao": "Revisar o protocolo de troca de curativos até a próxima reunião.",
                "responsavel": "Patrícia Vilela",
                "contribuicoes": [
                    {
                        "nome": "Patrícia Vilela",
                        "funcao": "Enfermeira - UTI Adulto",
                        "conteudo": "Mostrou a taxa do mês e os leitos com mais troca.",
                    }
                ],
                "divergencias": [],
            },
            {
                "titulo": "Bombas de infusão",
                "descricao": "Duas bombas deram alarme falso na semana.",
                "decisao": "Calibrar as bombas dos leitos 4 a 8.",
                "responsavel": "Fábio Guimarães",
                "contribuicoes": [
                    {
                        "nome": "Fábio Guimarães",
                        "funcao": "Técnico de Manutenção - Engenharia Clínica",
                        "conteudo": "Combinou a calibração com a equipe do plantão.",
                    }
                ],
                "divergencias": [],
            },
        ],
        "quadro_atribuicoes": [
            {
                "acao": descricao,
                "responsavel": {p[0]: p[1] for p in PESSOAS}[responsavel],
                "cargo": {p[0]: p[2] for p in PESSOAS}[responsavel],
                "prazo": _dia(prazo),
                "entregavel": entregavel,
                "objetivo_meta": "Reduzir a infecção de cateter na UTI",
                "status": "ABERTO",
                "tipo": "ACAO",
            }
            for _, descricao, responsavel, prazo, _, entregavel in PENDENCIAS[:3]
        ]
        + [
            {
                "acao": DESCRICAO_DA_ROTINA,
                "responsavel": "Patrícia Vilela",
                "cargo": "Enfermeira",
                "prazo": None,
                "entregavel": "Carrinho conferido e lacrado",
                "objetivo_meta": "Carrinho pronto em toda intercorrência",
                "status": "ABERTO",
                "tipo": "ROTINA",
                "frequencia": "SEMANAL",
            },
            {
                "acao": TRECHO_DO_PROCESSO,
                "responsavel": "",
                "cargo": "",
                "prazo": None,
                "entregavel": "",
                "objetivo_meta": "Reduzir a infecção de cateter na UTI",
                "status": "ABERTO",
                "tipo": "PROCESSO",
            },
        ],
    }


def semear() -> None:
    """As pessoas, as duas reuniões e as Pendências de exemplo."""
    credenciais_locais()
    for pid, nome, cargo, setor, perfil in PESSOAS:
        email = email_de(nome)
        _rest(
            "participantes",
            "POST",
            [
                {
                    "id": pid,
                    "nome_completo": nome,
                    "email": email,
                    "cargo": cargo,
                    "setor": setor,
                    "ativo": True,
                    "access_profile": perfil,
                    "is_super_admin": perfil == "super_admin",
                    "is_externo": False,
                    "auth_user_id": _login_de_exemplo(email, nome),
                }
            ],
            prefer="resolution=merge-duplicates",
        )

    setor = _rest("setores?nome=eq.UTI%20Adulto&select=id")
    comum = {
        "hora_inicio": "09:00:00",
        "hora_fim": "10:00:00",
        "tipo": "Coordenação",
        "facilitador_id": FACILITADORA[0],
        "setor": "UTI Adulto",
        # As Definições de processo se agrupam pelo setor da reunião (issue #1875).
        "setor_id": setor[0]["id"] if setor else None,
        "fonte": "MOCK",
        "deleted_at": None,
    }
    _rest(
        "reunioes",
        "POST",
        [{**comum, "id_reuniao": REUNIAO, "titulo": TITULO_REUNIAO, "data": _dia_no_mes(2),
          "objetivo": "Acompanhar os indicadores da UTI Adulto e combinar as ações do mês.",
          "status_ata": "PROGRAMADA", "json_ata": None}],
        prefer="resolution=merge-duplicates",
    )
    _rest(
        "reunioes",
        "POST",
        [{**comum, "id_reuniao": REUNIAO_ASSINADA, "titulo": TITULO_ASSINADA, "data": _dia_no_mes(-9),
          "objetivo": "Rever os indicadores de infecção do mês.",
          "status_ata": "ASSINADA", "json_ata": json_da_ata()}],
        prefer="resolution=merge-duplicates",
    )
    _rest(
        "reunioes",
        "POST",
        [{**comum, "id_reuniao": REUNIAO_EM_ASSINATURA, "titulo": TITULO_EM_ASSINATURA,
          "data": _dia_no_mes(-3), "facilitador_id": FACILITADORA_DA_FARMACIA, "setor": "Farmácia",
          "setor_id": None, "objetivo": "Rever a padronização de antibióticos.",
          "status_ata": "AGUARDANDO_ASSINATURA", "json_ata": None}],
        prefer="resolution=merge-duplicates",
    )

    for id_reuniao in REUNIOES_DO_SEED:
        ja_estao = {
            linha["participante_id"]
            for linha in _rest(f"reuniao_participantes?id_reuniao=eq.{id_reuniao}&select=participante_id")
        }
        novos = [
            {"id_reuniao": id_reuniao, "participante_id": pid}
            for pid, *_ in PESSOAS
            if pid not in ja_estao
        ]
        if novos:
            _rest("reuniao_participantes", "POST", novos)

    nomes = {p[0]: p[1] for p in PESSOAS}
    cargos = {p[0]: p[2] for p in PESSOAS}
    _rest(
        "pendencias",
        "POST",
        [
            {
                "id_acao": pid,
                "id_reuniao": REUNIAO_DA_PENDENCIA.get(pid, REUNIAO_ASSINADA),
                "descricao_acao": descricao,
                "responsavel_id": responsavel,
                "responsavel_nome": nomes[responsavel],
                "cargo": cargos[responsavel],
                "prazo": _dia(prazo),
                "meta_entregavel": entregavel,
                "status": estado,
                "deleted_at": None,
            }
            for pid, descricao, responsavel, prazo, estado, entregavel in PENDENCIAS
        ],
        prefer="resolution=merge-duplicates",
    )
    semear_contestacao()
    semear_rotina()
    semear_definicao_de_processo()
    semear_link_pessoal()
    semear_fotografias()
    print("dados de exemplo de Reuniões e Pendências prontos.")


def _segunda(semanas_antes: int) -> dt.date:
    hoje = dt.date.today()
    return hoje - dt.timedelta(days=hoje.weekday() + 7 * semanas_antes)


def semear_contestacao() -> None:
    """A Contestação aberta do Rodrigo, que a Clara responde (issue #1870).

    O Histórico só cresce (o banco recusa UPDATE e DELETE): o evento entra uma
    vez e o roteiro nunca responde a ele.
    """
    ja_tem = _rest(f"pendencia_historico?id_acao=eq.{CONTESTADA}&comando=eq.contestar&select=id")
    if ja_tem:
        return
    pid, _, responsavel, prazo, estado, _ = next(p for p in PENDENCIAS if p[0] == CONTESTADA)
    _rest(
        "pendencia_historico",
        "POST",
        [
            {
                "id_acao": pid,
                "comando": "contestar",
                "anotacao": MOTIVO_DA_CONTESTACAO,
                "autor_id": responsavel,
                "autor_nome": {p[0]: p[1] for p in PESSOAS}[responsavel],
                "status_antes": estado,
                "status_depois": estado,
                "prazo_antes": _dia(prazo),
                "prazo_depois": _dia(prazo),
            }
        ],
    )


def semear_rotina() -> None:
    """A Rotina semanal da Ata assinada, com as Verificações das últimas semanas."""
    _rest(
        "rotinas",
        "POST",
        [
            {
                "id": ROTINA,
                "id_reuniao": REUNIAO_ASSINADA,
                "quadro_pos": 3,
                "descricao": DESCRICAO_DA_ROTINA,
                "responsavel_id": RESPONSAVEL_DA_ROTINA,
                "responsavel_nome": {p[0]: p[1] for p in PESSOAS}[RESPONSAVEL_DA_ROTINA],
                "frequencia": "SEMANAL",
                "comeca_em": _segunda(5).isoformat(),
                "status": "ATIVA",
            }
        ],
        prefer="resolution=merge-duplicates",
    )
    _rest(
        "rotina_verificacoes",
        "POST",
        [
            {
                "id": f"17210000-0000-4000-8000-0000000019{semanas:02d}",
                "rotina_id": ROTINA,
                "ciclo_inicio": _segunda(semanas).isoformat(),
                "ciclo_fim": (_segunda(semanas) + dt.timedelta(days=6)).isoformat(),
                "resultado": resultado,
                "anotacao": anotacao,
                "atrasada": atrasada,
                "marcada_por_id": RESPONSAVEL_DA_ROTINA,
                "marcada_por_nome": {p[0]: p[1] for p in PESSOAS}[RESPONSAVEL_DA_ROTINA],
            }
            for semanas, resultado, anotacao, atrasada in VERIFICACOES
        ],
        prefer="resolution=merge-duplicates",
    )


def semear_definicao_de_processo() -> None:
    """A linha de Processo da Ata assinada, na lista do setor (issue #1875)."""
    _rest(
        "definicoes_processo",
        "POST",
        [
            {
                "id": DEFINICAO_DE_PROCESSO,
                "id_reuniao": REUNIAO_ASSINADA,
                "quadro_pos": 4,
                "trecho": TRECHO_DO_PROCESSO,
                "objetivo": "Reduzir a infecção de cateter na UTI",
                "status": "ATIVA",
            }
        ],
        prefer="resolution=merge-duplicates",
    )


def semear_link_pessoal() -> None:
    """O link pessoal do Fábio, com o hash do token, como o app grava."""
    token_hash = hashlib.sha256(TOKEN_DO_LINK.encode("utf-8")).hexdigest()
    expira = (dt.datetime.now(dt.UTC) + dt.timedelta(days=14)).isoformat()
    if _rest(f"pendencias_links_pessoais?token_hash=eq.{token_hash}&select=id"):
        _rest(
            f"pendencias_links_pessoais?token_hash=eq.{token_hash}",
            "PATCH",
            {"expira_em": expira, "revogado_em": None},
        )
        return
    _rest(
        "pendencias_links_pessoais",
        "POST",
        [{"participante_id": DONO_DO_LINK, "token_hash": token_hash, "expira_em": expira}],
    )


def semear_fotografias() -> None:
    """As 8 segundas da Facilitadora: a evolução e a seta dos cards (issue #1873)."""
    atrasadas = [6, 5, 5, 4, 4, 3, 2, 2]
    _rest(
        "painel_fotografias",
        "POST",
        [
            {
                "participante_id": FACILITADORA[0],
                "semana": _segunda(semanas).isoformat(),
                "atrasadas": atrasadas[7 - semanas],
                "vencem_em_3_dias": 1,
                "aguardam_assinatura": 0,
                "atas_paradas": 1,
                "conformidade": 60 + 4 * (7 - semanas),
                "ativas": 6,
            }
            for semanas in range(8)
        ],
        prefer="resolution=merge-duplicates",
    )


def por_reuniao(**campos) -> None:
    """Põe a reunião de exemplo no momento que o próximo print mostra."""
    _rest(f"reunioes?id_reuniao=eq.{REUNIAO}", "PATCH", campos)


def nomes_de_fora_do_seed() -> list[str]:
    """Os nomes e títulos do banco local que não são deste roteiro."""
    meus = {p[0] for p in PESSOAS}
    pessoas = _rest_tudo("participantes?select=id,nome_completo&order=id")
    reunioes = _rest_tudo("reunioes?select=id_reuniao,titulo&order=id_reuniao")
    return [p["nome_completo"] for p in pessoas if p["id"] not in meus and p["nome_completo"]] + [
        r["titulo"]
        for r in reunioes
        if r["id_reuniao"] not in REUNIOES_DO_SEED and r["titulo"]
    ]


def ata_pronta() -> None:
    """A reunião de exemplo com a Ata escrita, esperando a revisão."""
    por_reuniao(
        status_ata="AGUARDANDO_VALIDACAO",
        json_ata=json_da_ata(),
        url_pdf_preliminar="http://localhost:3000/manual/ata-de-exemplo.pdf",
        falha_envio_assinatura=None,
    )


def reuniao_programada() -> None:
    """A reunião de exemplo de volta ao começo do caminho."""
    por_reuniao(
        status_ata="PROGRAMADA", json_ata=None, url_pdf_preliminar=None, falha_envio_assinatura=None
    )


# --------------------------------------------------------------------------
# O navegador: o `playwright-cli`
# --------------------------------------------------------------------------


def navegador(*args: str) -> str:
    """Um comando do `playwright-cli` na sessão do roteiro; erro para tudo."""
    if not shutil.which("playwright-cli"):
        raise SystemExit("o playwright-cli não está instalado (npm i -g @playwright/cli).")
    proc = subprocess.run(["playwright-cli", f"-s={SESSAO}", *args], capture_output=True, text=True)
    if proc.returncode != 0 or proc.stdout.startswith("### Error"):
        raise SystemExit(f"playwright-cli {args[0]}: {proc.stdout[:600]}{proc.stderr[:300]}")
    return proc.stdout


# Funções que todo print usa, coladas no começo de cada `run-code` (ele não
# aceita import). O balão é um `div` por cima da tela, sem clique, que some na
# próxima navegação: nada disto fica no app.
AJUDANTES = r"""
const balao = async (alvo, numero) => {
  await alvo.scrollIntoViewIfNeeded();
  const caixa = await alvo.boundingBox();
  if (!caixa) throw new Error('balão ' + numero + ': o elemento não está na tela');
  await page.evaluate(([x, y, n]) => {
    const b = document.createElement('div');
    b.className = 'balao-do-manual';
    b.textContent = String(n);
    Object.assign(b.style, {
      position: 'absolute', left: (x + window.scrollX) + 'px', top: (y + window.scrollY) + 'px',
      width: '28px', height: '28px', borderRadius: '9999px', background: '#2B2E7E', color: '#fff',
      font: '700 15px/28px system-ui, sans-serif', textAlign: 'center',
      boxShadow: '0 2px 6px rgba(0,0,0,0.35)', pointerEvents: 'none', zIndex: '2147483647',
    });
    document.body.appendChild(b);
  }, [Math.max(0, caixa.x - 22), Math.max(0, caixa.y - 22), numero]);
};
const recorte = async (alvos, margem = 32) => {
  const caixas = [];
  for (const a of alvos) {
    const c = await a.boundingBox();
    if (!c) throw new Error('recorte: um bloco não está na tela');
    caixas.push(c);
  }
  const [sx, sy] = await page.evaluate(() => [window.scrollX, window.scrollY]);
  const x = Math.max(0, Math.min(...caixas.map((c) => c.x)) + sx - margem);
  const y = Math.max(0, Math.min(...caixas.map((c) => c.y)) + sy - margem);
  const direita = Math.max(...caixas.map((c) => c.x + c.width)) + sx + margem;
  const baixo = Math.max(...caixas.map((c) => c.y + c.height)) + sy + margem;
  return { x, y, width: direita - x, height: baixo - y };
};
const abrir = async (caminho, largura = 1440, altura = 900) => {
  await page.setViewportSize({ width: largura, height: altura });
  await page.goto(BASE + caminho, { waitUntil: 'networkidle' });
};
const cartao = (titulo) =>
  page.getByRole('heading', { name: titulo, exact: true })
    .locator("xpath=ancestor::div[contains(@class,'rounded-2xl')][1]");
const abrirPendencia = async (descricao) => {
  // Tela alta: a janela da Pendência ocupa 85% da altura e não rola por dentro.
  await abrir('/pendencias', 1440, 1700);
  const linha = page.locator('tbody tr').filter({ hasText: descricao }).first();
  await linha.waitFor();
  await linha.getByRole('button', { name: 'Abrir detalhes da pendência' }).click();
  const janela = page.locator('div.max-w-5xl.rounded-2xl').first();
  await janela.getByRole('heading', { name: descricao }).waitFor();
  await janela.getByLabel('Histórico da pendência').or(janela.getByText('Nenhuma ação registrada ainda.')).first().waitFor();
  await page.waitForTimeout(600);
  return janela;
};
const anotar = async (janela, texto) => {
  await janela.getByPlaceholder('Conte o que foi feito ou por que esta ação.').fill(texto);
};
const pronto = async (clip) => {
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  // O selo do Next em modo de desenvolvimento não é do app.
  await page.evaluate(() => document.querySelectorAll('nextjs-portal').forEach((e) => e.remove()));
  await page.waitForTimeout(400);
  return { texto: await page.evaluate(() => document.body.innerText), clip };
};
"""


def rodar(corpo: str, base: str = ""):
    """Roda `corpo` como função `async page => {...}` e devolve o que ela devolve."""
    ajudantes = AJUDANTES.replace("BASE + caminho", f"{json.dumps(base)} + caminho")
    saida = navegador("run-code", "async page => {\n" + ajudantes + corpo + "\n}")
    if "### Result\n" not in saida:
        return None
    resultado = saida.split("### Result\n", 1)[1].split("\n###", 1)[0].strip()
    return json.loads(resultado) if resultado else None


def entrar(base: str, pessoa: str = FACILITADORA[0]) -> None:
    """Entra no app como a pessoa de exemplo (a Facilitadora, se não disser outra)."""
    nome = {p[0]: p[1] for p in PESSOAS}[pessoa]
    rodar(
        f"""
        await page.setViewportSize({{ width: 1440, height: 900 }});
        await page.context().clearCookies();
        await page.goto('{base}/login', {{ waitUntil: 'networkidle' }});
        await page.evaluate(() => {{ localStorage.clear(); sessionStorage.clear(); }});
        await page.goto('{base}/login', {{ waitUntil: 'networkidle' }});
        await page.getByPlaceholder('seu@email.com').fill({json.dumps(email_de(nome))});
        await page.getByPlaceholder('••••••••').fill({json.dumps(SENHA)});
        await page.getByRole('button', {{ name: 'Entrar' }}).click();
        await page.waitForURL((u) => !u.toString().includes('/login'), {{ timeout: 30000 }});
        """,
        base,
    )


# --------------------------------------------------------------------------
# Os prints, um por imagem da página
# --------------------------------------------------------------------------


def inicio() -> str:
    """A primeira tela depois do login (issue #1948).

    Entra pelo endereço principal e espera o app levar ao Início: se o login
    deixar de cair lá, o print não sai.
    """
    reuniao_programada()
    return """
    await abrir('/');
    await page.waitForURL((u) => new URL(u).pathname === '/inicio', { timeout: 30000 });
    await page.getByRole('heading', { name: 'Início' }).first().waitFor();
    await page.waitForTimeout(1500);
    await balao(page.getByRole('link', { name: 'Início', exact: true }).first(), 1);
    // O grupo Reuniões e metas já começa aberto: o balão vai direto no Dashboard.
    await balao(page.getByRole('link', { name: 'Dashboard', exact: true }).first(), 2);
    await page.evaluate(() => window.scrollTo(0, 0));
    return await pronto({ x: 0, y: 0, width: 1440, height: 900 });
    """


def calendario() -> str:
    reuniao_programada()
    return f"""
    await abrir('/reunioes/calendario');
    await page.getByRole('heading', {{ name: 'Calendário de Reuniões' }}).waitFor();
    await page.locator('a[href^="/reunioes/{REUNIAO}"]').first().waitFor();
    await page.waitForTimeout(1200);
    await balao(page.getByRole('link', {{ name: 'Calendário', exact: true }}).first(), 1);
    const mes = page.getByRole('heading', {{ level: 2 }}).filter({{ hasText: /\\d{{4}}/ }}).first();
    await balao(mes.locator('xpath=../../button[1]'), 2);
    await balao(page.locator('a[href^="/reunioes/{REUNIAO}"]').first(), 3);
    await page.evaluate(() => window.scrollTo(0, 0));
    const altura = await page.evaluate(() => document.documentElement.scrollHeight);
    return await pronto({{ x: 0, y: 0, width: 1440, height: altura }});
    """


def agendar_reuniao() -> str:
    """A janela de agendar, preenchida e NÃO enviada (a reunião de exemplo já existe)."""
    return f"""
    await abrir('/reunioes/calendario', 1440, 1500);
    await page.getByRole('heading', {{ name: 'Calendário de Reuniões' }}).waitFor();
    await page.getByRole('button', {{ name: 'Agendar Reunião' }}).first().click();
    const janela = page.getByRole('heading', {{ name: 'Agendar Reunião' }})
      .locator("xpath=ancestor::div[contains(@class,'max-w-2xl')][1]");
    await janela.waitFor();
    await page.getByPlaceholder('Ex: Reunião de Diretoria, Abril 2026').fill({json.dumps(TITULO_REUNIAO)});
    await janela.getByRole('combobox').first().click();
    await page.getByRole('option', {{ name: 'Coordenação' }}).click();
    await janela.getByRole('button', {{ name: '09:00', exact: true }}).click();
    await page.getByPlaceholder('Descreva a pauta da reunião...')
      .fill('Indicadores do mês e as ações da última reunião.');
    // A busca casa só gente de exemplo: em branco, a lista abre o cadastro
    // inteiro, que é gente de verdade.
    for (const [nome, sobrenome] of [['Patrícia Vilela', 'Vilela'], ['Fábio Guimarães', 'Guimarães']]) {{
      await page.getByPlaceholder('Buscar participante...').fill(sobrenome);
      await janela.getByRole('button', {{ name: new RegExp(nome) }}).first().click();
    }}
    await page.getByPlaceholder('Buscar participante...').fill('Saldanha');
    await janela.getByText('Rodrigo Saldanha').first().waitFor();
    await page.evaluate((el) => el.scrollTop = 0, await janela.elementHandle());
    await balao(page.getByPlaceholder('Ex: Reunião de Diretoria, Abril 2026'), 1);
    await balao(janela.getByRole('button', {{ name: '09:00', exact: true }}), 2);
    await balao(page.getByPlaceholder('Buscar participante...'), 3);
    await balao(janela.getByRole('button', {{ name: 'Agendar Reunião' }}), 4);
    const rolou = await page.evaluate((el) => el.scrollTop, await janela.elementHandle());
    if (rolou) throw new Error('agendar-reuniao: a janela rolou por dentro; abra uma tela mais alta');
    return await pronto(await recorte([janela]));
    """


def anexar_transcricao() -> str:
    reuniao_programada()
    return f"""
    await abrir('/reunioes/{REUNIAO}');
    await page.getByRole('heading', {{ name: 'Transcrição', exact: true }}).waitFor();
    await page.waitForTimeout(1000);
    await balao(page.getByRole('heading', {{ name: 'Transcrição', exact: true }}), 1);
    await balao(page.getByRole('button', {{ name: /Anexar Transcrição/i }}), 2);
    return await pronto(await recorte([cartao('Transcrição')]));
    """


def _validacao(baloes: str) -> str:
    ata_pronta()
    return f"""
    await abrir('/reunioes/{REUNIAO}');
    await page.getByRole('heading', {{ name: 'Validação Necessária' }}).waitFor();
    await page.waitForTimeout(1200);
    {baloes}
    """


def revisar_ata() -> str:
    return _validacao(
        """
    await balao(page.getByRole('heading', { name: 'Validação Necessária' }), 1);
    await balao(page.getByText('Baixar PDF').first(), 2);
    await balao(page.getByRole('button', { name: 'Solicitar Correção' }), 3);
    await page.evaluate(() => window.scrollTo(0, 0));
    return await pronto(await recorte([page.getByText('Baixar PDF').first(), cartao('Validação Necessária')]));
    """
    )


def enviar_para_assinatura() -> str:
    # O roteiro nunca clica em "Enviar para assinatura": o envio sai na hora,
    # sem confirmação, e chamaria a ClickSign.
    return _validacao(
        """
    await balao(page.getByRole('button', { name: 'Enviar para assinatura' }), 1);
    await balao(page.getByRole('button', { name: 'Finalizar sem assinatura' }), 2);
    return await pronto(await recorte([cartao('Validação Necessária')]));
    """
    )


def ata_assinada() -> str:
    return f"""
    await abrir('/reunioes/{REUNIAO_ASSINADA}');
    const selo = page.getByText('Ata Assinada Digitalmente');
    await selo.waitFor();
    await page.waitForTimeout(1000);
    await balao(selo, 3);
    const faixa = selo.locator("xpath=ancestor::div[contains(@class,'rounded-2xl')][1]");
    const linhaDoTempo = page.getByText('Processando IA').first()
      .locator("xpath=ancestor::div[contains(@class,'rounded-2xl')][1]");
    return await pronto(await recorte([linhaDoTempo, faixa]));
    """


def pendencias() -> str:
    atrasada = json.dumps(PENDENCIAS[2][1])
    return f"""
    await abrir('/pendencias', 1680, 900);
    await page.getByText('Ação / Tarefa').waitFor();
    await page.getByText({atrasada}).waitFor();
    await page.waitForTimeout(1200);
    const linha = page.locator('tbody tr').filter({{ hasText: {atrasada} }}).first();
    await balao(page.getByRole('link', {{ name: 'Lista', exact: true }}).first(), 1);
    await balao(page.getByText('Filtros Dinâmicos'), 2);
    // Mudar o estado pede Anotação: o selo abre as ações (issue #1862).
    await balao(linha.getByRole('button', {{ name: 'Abrir as ações da pendência' }}), 3);
    await balao(linha.getByRole('button', {{ name: 'Abrir detalhes da pendência' }}), 4);
    await page.evaluate(() => window.scrollTo(0, 0));
    return await pronto({{ x: 0, y: 0, width: 1680, height: 900 }});
    """


# --------------------------------------------------------------------------
# O ciclo de vida, o painel e a Rotina (issue #1880)
# --------------------------------------------------------------------------


def _descricao(pid: str) -> str:
    return json.dumps(next(p[1] for p in PENDENCIAS if p[0] == pid))


def minha_fila() -> str:
    """O Início da Facilitadora: a frase, os três números e a Contestação na fila."""
    reuniao_programada()
    return """
    await abrir('/inicio', 1440, 1300);
    const resumo = page.getByRole('list', { name: 'Resumo dos prazos' });
    await resumo.waitFor();
    const fila48 = page.locator('#grupo-ate_48_horas');
    await fila48.waitFor();
    await page.waitForTimeout(1500);
    await balao(page.getByTestId('abertura').locator('[aria-live] p').first(), 1);
    await balao(resumo, 2);
    await balao(fila48.locator('li').first(), 3);
    await page.evaluate(() => window.scrollTo(0, 0));
    return await pronto({ x: 0, y: 0, width: 1440, height: 1300 });
    """


def painel() -> str:
    """O painel da Facilitadora: cards com a seta, gráficos, evolução e atrasos por setor."""
    reuniao_programada()
    return """
    await abrir('/dashboard', 1440, 900);
    await page.getByRole('heading', { name: 'Evolução das atrasadas' }).waitFor();
    await page.getByRole('heading', { name: 'Atrasos por setor' }).waitFor();
    await page.waitForTimeout(2500);
    await page.evaluate(() => window.scrollTo(0, 0));
    await balao(page.locator('#conformidade'), 1);
    await balao(page.getByRole('heading', { name: 'Status das Pendências' }), 2);
    await balao(page.getByRole('heading', { name: 'Pendências por Setor' }), 3);
    await balao(page.getByRole('heading', { name: 'Evolução das atrasadas' }), 4);
    await balao(page.getByRole('heading', { name: 'Atrasos por setor' }), 5);
    await page.evaluate(() => window.scrollTo(0, 0));
    const altura = await page.evaluate(() => document.documentElement.scrollHeight);
    return await pronto({ x: 0, y: 0, width: 1440, height: altura });
    """


def ranking() -> str:
    """O ranking de atrasos, que só o Super admin vê (issue #2144).

    O ranking lista o hospital inteiro: antes da guarda, o roteiro tira da
    tela as linhas de quem não é do seed. A guarda lê o texto depois disso e
    recusa o print se sobrar alguém de fora.
    """
    reuniao_programada()
    nomes = json.dumps([nome for _, nome, *_ in PESSOAS], ensure_ascii=False)
    return f"""
    await abrir('/dashboard', 1440, 900);
    const secao = page.locator('section[aria-labelledby="ranking-de-atrasos"]');
    await secao.waitFor();
    await page.waitForTimeout(2000);
    const doSeed = {nomes};
    await secao.locator('tbody tr').evaluateAll((linhas, nomes) => {{
      for (const tr of linhas) if (!nomes.includes(tr.cells[0].innerText.trim())) tr.remove();
    }}, doSeed);
    const linha = secao.locator('tbody tr').first();
    await linha.waitFor();
    await balao(linha.locator('td').nth(2), 1);
    await balao(linha.locator('td').nth(5), 2);
    await balao(secao.getByRole('columnheader', {{ name: 'Rotinas não cumpridas' }}), 3);
    // O resto do painel é do hospital inteiro: a tela fica só com o ranking.
    const texto = await secao.innerText();
    const {{ clip }} = await pronto(await recorte([secao], 16));
    return {{ texto, clip }};
    """


def classificar_linhas() -> str:
    """O quadro de atribuições na validação, com o tipo de cada linha (issue #1872)."""
    ata_pronta()
    return f"""
    await abrir('/reunioes/{REUNIAO}', 1440, 900);
    const titulo = page.getByRole('heading', {{ name: /Quadro de Atribuições/ }});
    await titulo.waitFor();
    await page.getByLabel('Tipo da linha 1').waitFor();
    await page.waitForTimeout(1000);
    await page.getByLabel('Tipo da linha 1').scrollIntoViewIfNeeded();
    await balao(page.getByLabel('Tipo da linha 1'), 1);
    await balao(page.getByLabel('Frequência da linha 4'), 2);
    const quadro = titulo.locator("xpath=ancestor::div[contains(@class,'rounded-2xl')][1]");
    return await pronto(await recorte([quadro]));
    """


def contestar() -> str:
    """A Clara contesta o item dela na Ata em assinatura da Farmácia. Não confirma."""
    return f"""
    const janela = await abrirPendencia({_descricao("PE1721F")});
    await janela.getByRole('button', {{ name: 'Contestar', exact: true }}).click();
    await anotar(janela, 'A lista é da Comissão de Farmácia, e eu só recebo a versão final. Peço para passar o item para a Farmácia.');
    await balao(janela.getByRole('button', {{ name: 'Contestar', exact: true }}), 1);
    await balao(janela.getByPlaceholder('Conte o que foi feito ou por que esta ação.'), 2);
    await balao(janela.getByRole('button', {{ name: 'Confirmar' }}), 3);
    return await pronto(await recorte([janela], 0));
    """


def responder_contestacao() -> str:
    """A Clara, Facilitadora, abre o ajuste da Contestação do Rodrigo. Não confirma."""
    return f"""
    const janela = await abrirPendencia({_descricao(CONTESTADA)});
    await janela.getByRole('button', {{ name: 'Ajustar', exact: true }}).click();
    await anotar(janela, 'Prazo ajustado para a entrega do fornecedor.');
    await balao(janela.getByRole('button', {{ name: 'Ajustar', exact: true }}), 1);
    await balao(janela.getByText('Prazo novo (opcional)'), 2);
    await balao(janela.getByPlaceholder('Digite o nome da pessoa certa'), 3);
    await balao(janela.getByRole('button', {{ name: 'Recusar contestação' }}), 4);
    return await pronto(await recorte([janela], 0));
    """


def _acao_na_pendencia(pid: str, botao: str, anotacao: str, baloes: str) -> str:
    return f"""
    const janela = await abrirPendencia({_descricao(pid)});
    await janela.getByRole('button', {{ name: {json.dumps(botao)}, exact: true }}).click();
    await anotar(janela, {json.dumps(anotacao)});
    await balao(janela.getByRole('button', {{ name: {json.dumps(botao)}, exact: true }}), 1);
    {baloes}
    return await pronto(await recorte([janela], 0));
    """


def concluir_pendencia() -> str:
    """A conclusão da Clara com o campo da prova. Não confirma nem anexa."""
    return _acao_na_pendencia(
        "PE1721E",
        "Concluir",
        "Pauta enviada por e-mail aos participantes na segunda.",
        """
    await balao(janela.getByPlaceholder('Conte o que foi feito ou por que esta ação.'), 2);
    await balao(janela.getByLabel('Anexo (opcional)'), 3);
    await balao(janela.getByRole('button', { name: 'Confirmar' }), 4);
    """,
    )


def repactuar() -> str:
    return _acao_na_pendencia(
        "PE1721E",
        "Repactuar",
        "A reunião da UTI mudou de data; a pauta sai junto com o convite novo.",
        """
    await balao(janela.getByText('Prazo novo', { exact: true }), 2);
    await balao(janela.getByRole('button', { name: 'Confirmar' }), 3);
    """,
    )


def cancelar_pendencia() -> str:
    return _acao_na_pendencia(
        "PE1721C",
        "Cancelar pendência",
        "As bombas dos leitos 4 a 8 foram trocadas por equipamento novo, já calibrado.",
        "",
    )


def reabrir_pendencia() -> str:
    return _acao_na_pendencia(
        "PE1721D",
        "Reabrir",
        "O cardápio novo ainda não chegou à copa do 3º andar.",
        """
    await balao(janela.getByText('Prazo novo', { exact: true }), 2);
    """,
    )


def rotinas() -> str:
    """A tela Rotinas da Facilitadora, que marca pela responsável."""
    descricao = json.dumps(DESCRICAO_DA_ROTINA)
    return f"""
    await abrir('/rotinas', 1440, 900);
    const rotina = page.locator('section').filter({{ has: page.getByRole('heading', {{ name: {descricao} }}) }});
    await rotina.waitFor();
    await page.waitForTimeout(800);
    const ciclos = rotina.getByRole('list', {{ name: /^Ciclos em aberto/ }});
    const agora = ciclos.locator('li').last();
    await balao(agora.getByRole('button', {{ name: 'Realizada', exact: true }}), 1);
    await balao(agora.getByRole('button', {{ name: 'Não realizada' }}), 2);
    await balao(ciclos.getByText('Atrasado').first(), 3);
    await balao(rotina.getByRole('list', {{ name: /^Verificações/ }}), 4);
    await balao(rotina.getByRole('button', {{ name: 'Encerrar a Rotina' }}), 5);
    const titulo = page.getByRole('heading', {{ name: 'Rotinas', exact: true }});
    return await pronto(await recorte([titulo, rotina]));
    """


def definicoes_de_processo() -> str:
    return """
    await abrir('/reunioes/processos', 1440, 900);
    const titulo = page.getByRole('heading', { name: 'Definições de processo', exact: true });
    await titulo.waitFor();
    const lista = page.getByRole('list', { name: /^Definições de processo de / }).first();
    await lista.waitFor();
    await page.waitForTimeout(800);
    await balao(page.getByRole('link', { name: 'Definições de processo', exact: true }).first(), 1);
    const setor = lista.locator('xpath=preceding-sibling::h2[1]');
    await balao(setor, 2);
    await balao(lista.getByRole('button', { name: 'Tirar da lista' }).first(), 3);
    await page.evaluate(() => window.scrollTo(0, 0));
    return await pronto({ x: 0, y: 0, width: 1440, height: 900 });
    """


def link_pessoal() -> str:
    """A página do link pessoal do Fábio, aberta sem senha (issue #1878)."""
    descricao = _descricao("PE1721C")
    return f"""
    await abrir('/minhas-pendencias/{TOKEN_DO_LINK}', 1100, 900);
    const cartao = page.locator('li, article, section').filter({{ hasText: {descricao} }}).last();
    await cartao.waitFor();
    await page.waitForTimeout(800);
    await balao(cartao.getByText({descricao}), 1);
    await balao(cartao.getByRole('button', {{ name: 'Concluir', exact: true }}), 2);
    await page.evaluate(() => window.scrollTo(0, 0));
    const altura = await page.evaluate(() => document.documentElement.scrollHeight);
    return await pronto({{ x: 0, y: 0, width: 1100, height: Math.min(altura, 1200) }});
    """


# O nome de cada print é o nome do PNG ao lado do Markdown. O teste do roteiro
# confere que esta lista é exatamente a das imagens citadas na página: print
# novo na página sem função aqui fica vermelho.
PRINTS = {
    "inicio": inicio,
    "minha-fila": minha_fila,
    "painel": painel,
    "ranking": ranking,
    "calendario": calendario,
    "agendar-reuniao": agendar_reuniao,
    "anexar-transcricao": anexar_transcricao,
    "revisar-ata": revisar_ata,
    "classificar-linhas": classificar_linhas,
    "enviar-para-assinatura": enviar_para_assinatura,
    "ata-assinada": ata_assinada,
    "contestar": contestar,
    "responder-contestacao": responder_contestacao,
    "pendencias": pendencias,
    "concluir-pendencia": concluir_pendencia,
    "repactuar": repactuar,
    "cancelar-pendencia": cancelar_pendencia,
    "reabrir-pendencia": reabrir_pendencia,
    "rotinas": rotinas,
    "definicoes-de-processo": definicoes_de_processo,
    "email-de-segunda": email_de_segunda,
    "link-pessoal": link_pessoal,
}


def capturar(nome: str, base: str, de_fora: list[str]) -> Path:
    """Monta a tela, passa a guarda do dado real e só então grava o PNG."""
    tela = rodar(PRINTS[nome](), base)
    exigir_so_dado_de_exemplo(tela["texto"], de_fora, nome)
    caminho = PASTA_DA_PAGINA / f"{nome}.png"
    rodar(
        f"await page.screenshot({{ path: {json.dumps(str(caminho))}, "
        f"clip: {json.dumps(tela['clip'])}, fullPage: true }});"
    )
    return caminho


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--semear", action="store_true", help="cria os dados de exemplo e sai.")
    ap.add_argument("--print", dest="escolhido", choices=list(PRINTS), help="refaz só um print.")
    args = ap.parse_args()
    if args.semear:
        semear()
        return 0

    base = args.base.rstrip("/")
    de_fora = nomes_de_fora_do_seed()
    entrar(base)
    try:
        for nome in [args.escolhido] if args.escolhido else list(PRINTS):
            print(f"print: {capturar(nome, base, de_fora).relative_to(RAIZ)}")
    finally:
        reuniao_programada()
        navegador("close")
    return 0


if __name__ == "__main__":
    sys.exit(main())
