"""A permissão efetiva do módulo Segurança do Paciente (ADR 0095, decisões 3 e 4).

Uma função pura decide o que a pessoa alcança no módulo: entram o perfil do
módulo (Acesso pleno ao NSP), o papel da Participação vigente no Núcleo, o
estado do Termo de Adesão, o cargo de Diretoria e a flag de super admin; sai o
conjunto de recursos. Toda rota do módulo passa por ela (o gate
`require_recurso_nsp` em `app.dependencies`).

O que muda em relação aos outros módulos: o super admin NÃO passa por cima.
Ele só alcança a configuração técnica (decisão 4). Quem lê tudo é o Acesso
pleno, nominal, do Diretor Executivo.

A leitura do banco (a Participação vigente) fica em `situacao_da_pessoa`, ao
lado, para a função de regra continuar sem banco nos testes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from postgrest.exceptions import APIError

from app.services import colegiados
from app.services.colegiados import Colegiado

logger = logging.getLogger(__name__)

# O slug do Núcleo na tabela `colegiados` (a migration 146 o cria).
SLUG_DO_NUCLEO = "nsp"

PERFIL_ACESSO_PLENO = "acesso_pleno"

PAPEIS_DO_NUCLEO = ("presidencia", "suplente", "membro")

# O Núcleo para o serviço compartilhado de membros e de Termo (issue #1819).
NUCLEO = Colegiado(
    slug=SLUG_DO_NUCLEO,
    nome="Núcleo",
    sigla="NSP",
    papeis=PAPEIS_DO_NUCLEO,
    termos_envios="nsp_termos_envios",
    documentos="nsp_documentos",
    documentos_envios="nsp_documentos_envios",
    bucket_dos_documentos="supabase_storage_bucket_nsp_documentos",
    modelo_do_termo="nsp_termo_adesao.html",
)

# O cargo de Diretoria no cadastro (o `role` da pessoa).
ROLES_DA_DIRETORIA = ("diretor", "presidente")

RECURSOS_NSP = (
    # O item do menu e a página inicial do módulo.
    "ver_modulo",
    "painel",
    "calendario",
    # A agenda regulatória.
    "agenda",
    "membros",
    "documentos",
    "capacitacoes",
    # Reuniões e atas do Núcleo.
    "reunioes",
    # Notificações de incidente e investigações (a partir da Fase 2).
    "casos",
    # Quem notificou: só a Presidência e o Acesso pleno (seção 3).
    "identidade_notificante",
    # Confirmar ou ajustar a triagem: só a Presidência e o Acesso pleno (issue #1992).
    "triagem",
    # As notas do Comitê de Conduta ao Núcleo (issue #1850): só a Presidência
    # e o Acesso pleno.
    "notas_do_comite",
    # Cadastrar membro, publicar documento, validar ata.
    "gerir_nucleo",
    # A configuração técnica do módulo, a única coisa que o super admin alcança.
    "configuracao",
    # Editar os prazos internos da tabela do Núcleo: só a Presidência e o
    # Acesso pleno (issue #1993). O super admin lê a tabela na configuração.
    "tabela_de_prazos",
    # Editar os cortes de frequência da matriz de prioridade: só a Presidência
    # e o Acesso pleno (issue #2154). O corte muda a prioridade do caso; o
    # super admin lê os cortes na configuração.
    "cortes_de_frequencia",
    # A leitura dos casos das faixas A e B, sem quem notificou e sem editar:
    # a Diretoria (ADR 0107, decisão 5).
    "casos_graves",
    # Registrar a ausência da Presidência, que põe o suplente em exercício: só
    # a Presidência e o Acesso pleno (ADR 0107, decisão 4).
    "ausencia_da_presidencia",
)

# As faixas dos casos que a Diretoria lê (ADR 0107, decisão 5).
FAIXAS_DA_DIRETORIA = frozenset({"A", "B"})

# Membro sem Termo válido vê painel, calendário e agenda (glossário, "Membro do
# Núcleo"), e nada sobre casos, investigações ou atas.
_SEM_TERMO = frozenset({"ver_modulo", "painel", "calendario", "agenda"})
_MEMBRO = _SEM_TERMO | {"membros", "documentos", "capacitacoes", "reunioes", "casos"}
_DIRETORIA = _SEM_TERMO | {"membros", "casos_graves"}
_TUDO = frozenset(RECURSOS_NSP)
# O suplente em exercício responde pela Presidência, mas não estende o próprio
# período: quem registra a ausência é a Presidência ou o Acesso pleno.
_EM_EXERCICIO = _TUDO - {"ausencia_da_presidencia"}


@dataclass(frozen=True)
class SituacaoNsp:
    acesso_pleno: bool
    papel_vigente: str | None
    termo_valido: bool
    diretoria: bool
    super_admin: bool
    # O suplente dentro de um período de ausência da Presidência registrado.
    em_exercicio: bool = False


def recursos_nsp(situacao: SituacaoNsp) -> frozenset[str]:
    """O que a pessoa alcança no módulo. A união do que cada fonte dá."""
    if situacao.acesso_pleno:
        return _TUDO
    recursos: set[str] = set()
    if situacao.papel_vigente in PAPEIS_DO_NUCLEO:
        if not situacao.termo_valido:
            recursos |= _SEM_TERMO
        elif situacao.papel_vigente == "presidencia":
            recursos |= _TUDO
        elif situacao.papel_vigente == "suplente" and situacao.em_exercicio:
            recursos |= _EM_EXERCICIO
        else:
            recursos |= _MEMBRO
    if situacao.diretoria:
        recursos |= _DIRETORIA
    if situacao.super_admin:
        recursos.add("configuracao")
    return frozenset(recursos)


def hoje_em_sao_paulo() -> date:
    return datetime.now(tz=ZoneInfo("America/Sao_Paulo")).date()


def id_do_nucleo(supabase) -> str | None:
    """O id do Núcleo em `colegiados`, ou None quando a migration não rodou."""
    return colegiados.id_do_colegiado(supabase, NUCLEO)


# As Participações vigentes de um Colegiado, sem executar (o serviço compartilhado).
participacoes_vigentes = colegiados.participacoes_vigentes


def situacao_da_pessoa(
    supabase, participante: dict[str, Any], *, super_admin: bool, hoje: date | None = None
) -> SituacaoNsp:
    """Monta a entrada da função de regra a partir do cadastro e do banco.

    Falha ao ler a Participação (tabela que ainda não existe entre o deploy e a
    migration, ou o PostgREST fora do ar) vale como "sem Participação": o
    módulo fica fechado e o resto do app segue de pé.
    """
    hoje = hoje or hoje_em_sao_paulo()
    try:
        papel, termo = colegiados.vinculo_vigente(supabase, NUCLEO, participante["id"], hoje)
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Participação no Núcleo ilegível; o módulo fica fechado para a pessoa: %s", erro)
        papel, termo = None, False
    return SituacaoNsp(
        acesso_pleno=participante.get("perfil_nsp") == PERFIL_ACESSO_PLENO,
        papel_vigente=papel,
        termo_valido=termo,
        diretoria=participante.get("role") in ROLES_DA_DIRETORIA,
        super_admin=super_admin,
        em_exercicio=papel == "suplente" and termo and suplente_em_exercicio(supabase, participante["id"], hoje),
    )


def suplente_em_exercicio(supabase, participante_id: str, hoje: date) -> bool:
    """Se hoje cai numa ausência da Presidência registrada na Participação
    vigente de suplente da pessoa (ADR 0107, decisão 4).

    Ausência ilegível (a tabela que ainda não existe entre o deploy e a
    migration 212, ou o PostgREST fora do ar) vale como "fora do período": o
    suplente segue membro.
    """
    try:
        nucleo_id = id_do_nucleo(supabase)
        if not nucleo_id:
            return False
        suplencias = [
            linha["id"]
            for linha in (
                participacoes_vigentes(supabase, nucleo_id, hoje)
                .eq("participante_id", participante_id)
                .eq("papel", "suplente")
                .execute()
                .data
            )
            or []
        ]
        if not suplencias:
            return False
        no_periodo = (
            supabase.table("nsp_ausencias_da_presidencia")
            .select("id")
            .in_("participacao_id", suplencias)
            .lte("inicio", hoje.isoformat())
            .gte("fim", hoje.isoformat())
            .limit(1)
            .execute()
            .data
        )
    except (APIError, httpx.HTTPError) as erro:
        logger.warning("Ausência da Presidência ilegível; o suplente segue membro: %s", type(erro).__name__)
        return False
    return bool(no_periodo)
