"""O papel de quem está logado na Ouvidoria (issue #1884, ADR 0099).

Módulo fundo: `papel_na_ouvidoria` é pura (participante, linhas do cadastro de
responsáveis e o dia entram, um papel sai) e `papel_de` é a casca que lê o
cadastro só quando precisa. O papel maior vence:

1. `perfil_ouvidoria`: ouvidor ou Diretoria Executiva, a fila inteira;
2. `indice_geral`: Secretária ou Super admin sem Perfil da Ouvidoria, o índice
   de todos os casos sem o sigiloso (ADR 0099, decisão 3);
3. `responsavel`: titular, substituto ou gestor vigente de algum setor, com os
   setores em que está vigente (decisões 1 e 2);
4. `nenhum`: não vê a Ouvidoria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.dependencies import foi_desligado, is_secretaria, is_super_admin
from app.services.ouvidoria_responsaveis import PAPEIS, esta_vigente

PERFIL_OUVIDORIA = "perfil_ouvidoria"
INDICE_GERAL = "indice_geral"
RESPONSAVEL = "responsavel"
NENHUM = "nenhum"

PERFIS_OUVIDORIA = ("ouvidor", "diretoria_executiva")


@dataclass(frozen=True)
class PapelNaOuvidoria:
    """O papel e, só para o responsável, os setores vigentes dele."""

    papel: str
    setores: frozenset[str] = field(default_factory=frozenset)


def _normalizar(email: str | None) -> str:
    return (email or "").strip().lower()


def emails_com_login(participantes: list[dict]) -> frozenset[str]:
    """Os e-mails dos participantes, na forma em que o papel os casa.

    O desligado fica de fora: `barrar_desligado` o recusa no portão da fila
    antes do papel, então ele não vê os casos do setor (revisão do PR #1893).
    Só `ativo` gravado como False conta; NULL segue valendo (`foi_desligado`)."""
    return frozenset(
        email for email in (_normalizar(p.get("email")) for p in participantes if not foi_desligado(p)) if email
    )


def tem_login(email: str | None, com_login: frozenset[str]) -> bool:
    """O e-mail de uma linha do cadastro casa com o de um participante.

    É o casamento de `papel_na_ouvidoria`, pela mesma `_normalizar`: a tela do
    cadastro (ADR 0099, decisão 1) não pode dizer "tem login" para quem o papel
    não reconhece, nem o contrário (issue #1887)."""
    chave = _normalizar(email)
    return bool(chave) and chave in com_login


def precisa_do_cadastro(participante: dict | None) -> bool:
    """Só quem não tem papel maior depende do cadastro de responsáveis."""
    return bool(participante) and not (
        participante.get("perfil_ouvidoria") in PERFIS_OUVIDORIA
        or is_secretaria(participante)
        or is_super_admin(participante)
    )


def setores_vigentes(participante: dict | None, responsaveis: list[dict], dia: date) -> frozenset[str]:
    """Os setores em que `participante` é titular, substituto ou gestor
    vigente em `dia`, qualquer que seja o papel maior dele.

    É o recorte da porta do login (issue #1886, ADR 0099, decisão 5): o
    responsável que também é Secretária ou Super admin vê o índice geral e
    responde pelos casos do setor dele."""
    email = _normalizar((participante or {}).get("email"))
    if not email:
        return frozenset()
    return frozenset(
        r["setor"]
        for r in responsaveis
        if _normalizar(r.get("email")) == email and r.get("papel") in PAPEIS and r.get("setor") and esta_vigente(r, dia)
    )


def papel_na_ouvidoria(participante: dict | None, responsaveis: list[dict], dia: date) -> PapelNaOuvidoria:
    """O papel de `participante` na Ouvidoria em `dia`.

    O e-mail casa sem diferenciar maiúsculas e sem os espaços das pontas; a
    vigência é a do acionamento (`esta_vigente`, fim inclusivo)."""
    if not participante:
        return PapelNaOuvidoria(NENHUM)
    if participante.get("perfil_ouvidoria") in PERFIS_OUVIDORIA:
        return PapelNaOuvidoria(PERFIL_OUVIDORIA)
    if is_secretaria(participante) or is_super_admin(participante):
        return PapelNaOuvidoria(INDICE_GERAL)
    setores = setores_vigentes(participante, responsaveis, dia)
    return PapelNaOuvidoria(RESPONSAVEL, setores) if setores else PapelNaOuvidoria(NENHUM)


def papel_de(supabase, participante: dict | None, dia: date) -> PapelNaOuvidoria:
    """O papel com o cadastro lido do banco, e só quando ele decide algo.

    O banco devolve só as linhas do e-mail da pessoa (`ilike`, sem diferenciar
    maiúsculas, com `%` e `_` escapados para não virarem curinga); a vigência e
    o casamento final ficam na função pura. Leitura que falha sobe: virar
    `nenhum` esconderia a Ouvidoria de quem responde por um setor por causa de
    um timeout."""
    linhas = _cadastro_do_email(supabase, participante) if precisa_do_cadastro(participante) else []
    return papel_na_ouvidoria(participante, linhas, dia)


def setores_de(supabase, participante: dict | None, dia: date) -> frozenset[str]:
    """`setores_vigentes` com o cadastro lido do banco. Leitura que falha sobe,
    como em `papel_de`."""
    return setores_vigentes(participante, _cadastro_do_email(supabase, participante), dia)


def _cadastro_do_email(supabase, participante: dict | None) -> list[dict]:
    """As linhas do cadastro de responsáveis com o e-mail da pessoa (`ilike`,
    sem diferenciar maiúsculas, com `%` e `_` escapados para não virarem
    curinga)."""
    email = _normalizar((participante or {}).get("email"))
    if not email:
        return []
    padrao = email.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return (
        supabase.table("ouvidoria_setor_responsaveis")
        .select("setor, papel, email, vigencia_inicio, vigencia_fim")
        .ilike("email", padrao)
        .execute()
        .data
        or []
    )
