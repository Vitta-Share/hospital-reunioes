"""O relato em passos da página pública do Canal de Conduta (issue #1843,
especificação seção 4, passos P1 a P6, regras C1, C2 e C6).

O envio chega de uma vez, no fim do passo 5. O que a pessoa escreveu no passo
4 vira o relato do caso, cifrado, com os campos opcionais como linhas
rotuladas embaixo do texto: é o que o Comitê lê e o que o agente de triagem
lê, depois da pseudonimização. O nome de quem relata com identificação fica
fora do relato, cifrado numa coluna própria, porque nenhum nome vai à IA
(ADR 0097, decisão 7).

A recusa nunca devolve o que foi enviado: a mensagem diz só quais campos
conferir, para nenhum trecho de relato nem nome voltar num erro (regra C6).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

import httpx
from postgrest.exceptions import APIError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.conduta import casos, cifra
from app.services.conduta.configuracoes import vigentes_publicas
from app.services.conduta.ritos import CATEGORIAS, FUSO, agora_utc
from app.services.feriados import feriados_entre
from app.services.ouvidoria_acompanhamento import _gastar_o_tempo_de_uma_conferencia, codigo_confere

LIMITE_DO_RELATO = 10_000
# O Comitê lê o relato em até 5 dias úteis (P5); a data para voltar (P6) é o
# fim desse prazo.
DIAS_UTEIS_PARA_VOLTAR = 5
AVISOS_DO_PASSO_1 = ("aviso_p1_anonimato", "aviso_p1_protocolo", "aviso_p1_boa_fe")

_POSICOES = {"sofreu": "sofreu", "presenciou": "presenciou", "ficou_sabendo": "ficou sabendo"}
_SIM_NAO = {"sim": "Sim", "nao": "Não", "nao_sei": "Não sei"}


class EnvioRecusadoError(Exception):
    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


class Ciencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ciente: bool
    # A versão de cada aviso que a tela mostrou; nulo é o texto padrão da página,
    # quando a coordenação ainda não salvou nenhum.
    versoes: dict[Literal["aviso_p1_anonimato", "aviso_p1_protocolo", "aviso_p1_boa_fe"], int | None]


class Envio(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ciencia: Ciencia
    identificacao: Literal["anonimo", "identificado"]
    nome: str | None = Field(default=None, max_length=200)
    assunto: Literal["A", "B", "C", "D", "E", "F"] | None = None
    direcao: Literal["sim", "nao", "nao_sei"]
    posicao: Literal["sofreu", "presenciou", "ficou_sabendo"] | None = None
    relato: str = Field(min_length=1, max_length=LIMITE_DO_RELATO)
    quando: str | None = Field(default=None, max_length=200)
    ainda_acontece: bool = False
    onde: str | None = Field(default=None, max_length=200)
    quem: str | None = Field(default=None, max_length=500)
    testemunhas: str | None = Field(default=None, max_length=500)
    lideranca_sabe: Literal["sim", "nao", "nao_sei"] | None = None
    o_que_foi_feito: str | None = Field(default=None, max_length=1000)
    evidencias: str | None = Field(default=None, max_length=1000)


def validar(dados: Any) -> Envio:
    """O envio conferido. A recusa cita os campos, nunca o valor."""
    try:
        envio = Envio.model_validate(dados)
    except ValidationError as erro:
        campos = sorted({str(e["loc"][0]) for e in erro.errors(include_input=False) if e.get("loc")})
        raise EnvioRecusadoError("Confira os campos: " + ", ".join(campos) + ".") from None
    if not envio.ciencia.ciente:
        raise EnvioRecusadoError("Marque a caixa de ciência do passo 1 para enviar.")
    if envio.identificacao == "identificado" and not envio.nome:
        raise EnvioRecusadoError("Escreva o seu nome ou escolha relatar sem se identificar.")
    return envio


def texto_do_relato(envio: Envio) -> str:
    """O relato que o caso guarda: o texto da pessoa e, embaixo, o que ela
    preencheu dos campos opcionais. O nome de quem relata não entra."""
    linhas = [envio.relato]
    extras = []
    if envio.posicao:
        extras.append(f"Quem relata: {_POSICOES[envio.posicao]}")
    if envio.quando or envio.ainda_acontece:
        quando = envio.quando or ""
        if envio.ainda_acontece:
            quando = f"{quando} (ainda está acontecendo)" if quando else "Ainda está acontecendo"
        extras.append(f"Quando: {quando}")
    if envio.onde:
        extras.append(f"Onde: {envio.onde}")
    if envio.quem:
        extras.append(f"Quem: {envio.quem}")
    if envio.testemunhas:
        extras.append(f"Testemunhas: {envio.testemunhas}")
    if envio.lideranca_sabe:
        lideranca = f"Alguma liderança já sabe: {_SIM_NAO[envio.lideranca_sabe]}"
        if envio.lideranca_sabe == "sim" and envio.o_que_foi_feito:
            lideranca += f". O que foi feito: {envio.o_que_foi_feito}"
        extras.append(lideranca)
    if envio.evidencias:
        extras.append(f"Evidências: {envio.evidencias}")
    if extras:
        linhas += ["", *extras]
    return "\n".join(linhas)


def _versoes_aceitas(supabase, versoes: dict[str, int | None]) -> dict[str, int | None]:
    """A versão de cada aviso, conferida contra as que existem. Versão que
    nunca existiu é envio forjado e é recusada; versão antiga vale, porque a
    pessoa aceitou o que a tela mostrou."""
    vigentes = vigentes_publicas(supabase)
    aceitas: dict[str, int | None] = {}
    for chave in AVISOS_DO_PASSO_1:
        versao = versoes.get(chave)
        vigente = vigentes.get(chave)
        if versao is not None and (vigente is None or not 1 <= versao <= vigente["versao"]):
            raise EnvioRecusadoError("Os avisos do passo 1 mudaram. Volte ao passo 1 e confira.")
        aceitas[chave] = versao
    return aceitas


def data_para_voltar(supabase, hoje: date) -> date:
    """O fim do prazo de leitura do Comitê, em dias úteis, sem contar feriado
    cadastrado. Sem o calendário, conta só os fins de semana."""
    try:
        feriados = feriados_entre(supabase, hoje, hoje + timedelta(days=30))
    except (APIError, httpx.HTTPError):
        feriados = frozenset()
    dia, faltam = hoje, DIAS_UTEIS_PARA_VOLTAR
    while faltam:
        dia += timedelta(days=1)
        if dia.weekday() < 5 and dia not in feriados:
            faltam -= 1
    return dia


def registrar(supabase, envio: Envio, tarefas=None) -> dict[str, Any]:
    """Grava o caso e devolve o protocolo, o código (uma vez só) e a data para
    voltar."""
    versoes = _versoes_aceitas(supabase, dict(envio.ciencia.versoes))
    agora = agora_utc()
    extras: dict[str, Any] = {"ciencia_em": agora.isoformat(), "ciencia_versoes": versoes}
    if envio.identificacao == "identificado":
        extras["relator_nome_cifrado"] = cifra.cifrar_texto(envio.nome)
    novo = casos.registrar_caso(
        supabase,
        relato=texto_do_relato(envio),
        categoria=envio.assunto if envio.assunto in CATEGORIAS else None,
        tarefas=tarefas,
        direcao_envolvida=envio.direcao,
        extras=extras,
    )
    return {
        "protocolo": novo["protocolo"],
        "codigo": novo["codigo"],
        "voltar_a_partir_de": data_para_voltar(supabase, agora.astimezone(FUSO).date()).isoformat(),
    }


class NotaDeConfianca(BaseModel):
    """A pergunta opcional do P6. Vem com o protocolo e o código, que a tela
    ainda tem na memória, para valer uma vez por relato e só para quem relatou."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    protocolo: str = Field(max_length=20)
    codigo: str = Field(max_length=40)
    nota: int = Field(ge=1, le=5)


def validar_nota(dados: Any) -> NotaDeConfianca:
    try:
        return NotaDeConfianca.model_validate(dados)
    except ValidationError:
        raise EnvioRecusadoError("Escolha uma nota de 1 a 5.") from None


def registrar_confianca(supabase, nota: NotaDeConfianca) -> bool:
    """Grava a nota no caso, se o código confere e se ainda não há nota.
    Devolve se o relato foi achado com aquele código."""
    linhas = (
        supabase.table("conduta_casos")
        .select("id, codigo_hash")
        .eq("protocolo", nota.protocolo.upper())
        .limit(1)
        .execute()
        .data
    ) or []
    if not linhas:
        # O mesmo tempo de um código errado, para a resposta não dizer se o
        # protocolo existe.
        _gastar_o_tempo_de_uma_conferencia(nota.codigo)
        return False
    if not codigo_confere(nota.codigo, linhas[0]["codigo_hash"]):
        return False
    (
        supabase.table("conduta_casos")
        .update({"confianca": nota.nota})
        .eq("id", linhas[0]["id"])
        .is_("confianca", "null")
        .execute()
    )
    return True
