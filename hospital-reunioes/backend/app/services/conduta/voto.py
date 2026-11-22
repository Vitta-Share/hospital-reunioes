"""O voto do Canal de Conduta (issue #1833; especificação, seções 6.6 e 11).

Na etapa Voto, cada membro votante do caso (a coordenação, o membro e o
segundo leitor, ou o suplente convocado no lugar do impedido) vota uma vez:
o resultado, a medida da Matriz de Consequências e a justificativa de uma a
três linhas, escrita por ele. O agente não redige voto: nada neste módulo
chama a IA, e o agente da trava (`trava.py`) nunca recebe o conteúdo de um
voto.

Cada voto fica cifrado e oculto até todos os votantes do caso votarem na
rodada. Fechada a rodada, vale a maioria. Sem maioria de resultado, ou de
medida quando o resultado pede medida (as três medidas diferentes), o
aplicativo convoca uma reunião curta: avisa os votantes e abre a rodada
seguinte. Os votos da rodada anterior ficam.

"CONCLUIR VOTAÇÃO" é da coordenação: grava o resultado da maioria no caso e
leva o caso à etapa Ata. Só conclui com a ata assinada pelos três votantes e,
no rito Completo, com a reunião do Comitê concluída (`ata`, issue #1834).
Procedente ou parcialmente procedente só concluem com a trava de robustez
inteira confirmada (`trava.bloqueio`), e o banco tem as mesmas travas
(migrations 216 e 218).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

from postgrest.exceptions import APIError

from app.services.conduta import avisos, cifra, membros, trilha
from app.services.conduta.impedimento import membros_do_caso
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc

TABELA = "conduta_votos"

RESULTADOS = {
    "procedente": "Procedente",
    "parcialmente_procedente": "Parcialmente procedente",
    "improcedente": "Improcedente",
    "inconclusivo": "Inconclusivo",
}
COM_MEDIDA = ("procedente", "parcialmente_procedente")
# A Matriz de Consequências (especificação, 6.6).
MEDIDAS = {
    "orientacao_registrada": "Orientação registrada",
    "advertencia_escrita": "Advertência escrita",
    "suspensao": "Suspensão",
    "dispensa_por_justa_causa": "Dispensa por justa causa",
    "rescisao_de_contrato": "Rescisão de contrato (PJ, cooperado, terceiro, fornecedor)",
    "comunicacao_a_autoridade": "Comunicação a autoridade ou conselho profissional",
}
DIAS_DA_SUSPENSAO = (1, 30)
LINHAS_DA_JUSTIFICATIVA = 3
TAMANHO_DA_JUSTIFICATIVA = 600
VOTANTES = 3
MOTIVO_DO_AVISO = "reuniao_curta"


class VotoRecusadoError(Exception):
    """A ação não pode acontecer agora. `status` vai para a resposta, e a
    mensagem diz o motivo numa linha."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ── Regras puras ────────────────────────────────────────────────────────────


def erro_do_voto(resultado: str, medida: str | None, dias: int | None, justificativa: str) -> str | None:
    """O que está errado no voto, numa linha, ou None."""
    if resultado not in RESULTADOS:
        return "Escolha o resultado do voto."
    if resultado in COM_MEDIDA:
        if medida not in MEDIDAS:
            return "Escolha a medida da Matriz de Consequências."
        if medida == "suspensao" and not (dias and DIAS_DA_SUSPENSAO[0] <= dias <= DIAS_DA_SUSPENSAO[1]):
            return "A suspensão vai de 1 a 30 dias."
        if medida != "suspensao" and dias is not None:
            return "Só a suspensão leva dias."
    elif medida is not None or dias is not None:
        return "Improcedente e inconclusivo não levam medida."
    linhas = [linha for linha in justificativa.splitlines() if linha.strip()]
    if not linhas:
        return "Escreva a sua justificativa."
    if len(linhas) > LINHAS_DA_JUSTIFICATIVA or len(justificativa) > TAMANHO_DA_JUSTIFICATIVA:
        return f"A justificativa cabe em até três linhas ({TAMANHO_DA_JUSTIFICATIVA} caracteres)."
    return None


@dataclass(frozen=True)
class Apuracao:
    """A rodada fechada: o resultado e a medida da maioria, ou a falta dela."""

    resultado: str | None
    medida: str | None
    dias_de_suspensao: int | None

    @property
    def tem_maioria(self) -> bool:
        return self.resultado is not None and (self.resultado not in COM_MEDIDA or self.medida is not None)


def apurar(votos: list[dict]) -> Apuracao:
    """Vale o que passa da metade dos votos: o resultado e, quando ele pede
    medida, a medida (com os dias, na suspensão). Três medidas diferentes não
    fazem maioria."""
    metade = len(votos) / 2
    resultados = Counter(v["resultado"] for v in votos)
    resultado = next((r for r, n in resultados.items() if n > metade), None)
    if resultado not in COM_MEDIDA:
        return Apuracao(resultado, None, None)
    medidas = Counter((v["medida"], v.get("dias_de_suspensao")) for v in votos if v.get("medida"))
    medida = next((m for m, n in medidas.items() if n > metade), None)
    return Apuracao(resultado, medida[0] if medida else None, medida[1] if medida else None)


# ── Leituras ────────────────────────────────────────────────────────────────


def rodada_atual(caso: dict) -> int:
    return int(caso.get("rodada_do_voto") or 1)


def _votos(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(TABELA).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda v: (v["rodada"], str(v.get("votado_em") or "")))


def _conteudo(linha: dict) -> dict:
    return json.loads(cifra.decifrar_texto(linha["voto_cifrado"]))


def _da_rodada(votos: list[dict], rodada: int, votantes: dict[str, str]) -> list[dict]:
    """Os votos que contam na rodada: os de quem vota no caso hoje. O voto de
    quem ficou impedido depois de votar sai da conta, e o suplente convocado
    vota no lugar."""
    return [v for v in votos if v["rodada"] == rodada and v["participante_id"] in votantes]


def rodada_fechada(votos_da_rodada: list[dict], votantes: dict[str, str]) -> bool:
    return len(votantes) >= VOTANTES and {v["participante_id"] for v in votos_da_rodada} >= set(votantes)


@dataclass(frozen=True)
class Situacao:
    """A votação do caso: quem vota, os votos de cada rodada e a apuração da
    última rodada fechada."""

    votantes: dict[str, str]
    votos: list[dict]
    rodada: int
    fechada: bool

    def da_rodada(self, rodada: int) -> list[dict]:
        return _da_rodada(self.votos, rodada, self.votantes)


def situacao(supabase, caso: dict) -> Situacao:
    votantes = membros_do_caso(supabase, caso)
    votos = _votos(supabase, caso["id"])
    rodada = rodada_atual(caso)
    return Situacao(votantes, votos, rodada, rodada_fechada(_da_rodada(votos, rodada, votantes), votantes))


def apuracao_da_rodada(supabase, caso: dict) -> Apuracao | None:
    """A apuração da rodada atual, se ela fechou; senão None."""
    atual = situacao(supabase, caso)
    if not atual.fechada:
        return None
    return apurar([_conteudo(v) for v in atual.da_rodada(atual.rodada)])


def olhar_do_voto(supabase, aberto: CasoAberto) -> dict:
    """O que a caixa "O QUE FAZER AGORA" precisa na etapa Voto."""
    atual = situacao(supabase, aberto.caso)
    ja = any(v["participante_id"] == aberto.autor_id for v in atual.votos if v["rodada"] == atual.rodada)
    return {"vota": aberto.autor_id in atual.votantes, "ja_votou": ja}


def _rotulo_da_medida(medida: str | None, dias: int | None) -> str | None:
    if not medida:
        return None
    return f"{MEDIDAS[medida]} de {dias} dia{'s' if dias != 1 else ''}" if medida == "suspensao" else MEDIDAS[medida]


def para_a_tela(supabase, aberto: CasoAberto) -> dict:
    """A votação do caso para quem abre. Enquanto a rodada não fecha, só o
    próprio voto e a contagem: o voto dos outros não sai, nem pela API."""
    from app.services.conduta import ata, trava

    caso = aberto.caso
    if caso.get("etapa") != "voto" and not caso.get("resultado"):
        return {"votacao": None, "trava": None, "ata": None, "reuniao": None}
    atual = situacao_em_dia(supabase, caso)
    nomes = membros.nomes(supabase, sorted({v["participante_id"] for v in atual.votos}))
    meu = next(
        (v for v in atual.votos if v["rodada"] == atual.rodada and v["participante_id"] == aberto.autor_id), None
    )
    ultima_fechada = atual.rodada if atual.fechada else atual.rodada - 1
    rodadas = []
    for numero in range(1, ultima_fechada + 1):
        # A rodada anterior fechou com todos os votantes daquela hora.
        linhas = (
            atual.da_rodada(numero) if numero == atual.rodada else [v for v in atual.votos if v["rodada"] == numero]
        )
        votos = [{"membro": nomes.get(v["participante_id"], ""), **_conteudo(v)} for v in linhas]
        apuracao = apurar(votos)
        rodadas.append(
            {
                "rodada": numero,
                "votos": votos,
                "resultado": apuracao.resultado if apuracao.tem_maioria else None,
                "medida": _rotulo_da_medida(apuracao.medida, apuracao.dias_de_suspensao)
                if apuracao.tem_maioria
                else None,
                "reuniao_curta": not apuracao.tem_maioria,
            }
        )
    resultado = rodadas[-1] if atual.fechada and rodadas and not rodadas[-1]["reuniao_curta"] else None
    em_voto = caso.get("etapa") == "voto"
    bloqueio_do_voto = None
    if aberto.autor_id not in atual.votantes:
        bloqueio_do_voto = "Só os três membros votantes votam."
    elif meu:
        bloqueio_do_voto = "Você já votou nesta rodada."
    return {
        "votacao": {
            "rodada": atual.rodada,
            "votantes": len(atual.votantes),
            "votaram": len(atual.da_rodada(atual.rodada)),
            "meu_voto": _conteudo(meu) if meu else None,
            "pode_votar": em_voto and bloqueio_do_voto is None,
            "bloqueio_do_voto": bloqueio_do_voto if em_voto else None,
            "reuniao_curta_convocada": atual.rodada > 1 and not atual.fechada,
            "rodadas": rodadas,
            "resultado": {"resultado": resultado["resultado"], "medida": resultado["medida"]} if resultado else None,
            "concluida": caso.get("resultado"),
            "pode_concluir": em_voto and bloqueio_da_conclusao(supabase, aberto) is None,
            "bloqueio_da_conclusao": bloqueio_da_conclusao(supabase, aberto) if em_voto else None,
        },
        "trava": trava.para_a_tela(supabase, aberto, atual),
        **ata.para_a_tela(supabase, aberto, atual),
    }


# ── Ações ───────────────────────────────────────────────────────────────────


def _exigir_voto(caso: dict) -> None:
    if caso.get("etapa") != "voto" or caso.get("encerrado_em") or caso.get("resultado"):
        raise VotoRecusadoError(409, "O voto é da etapa Voto.")


def _convocar_reuniao_curta(supabase, caso: dict, atual: Situacao) -> None:
    """Sem maioria: avisa os votantes e abre a rodada seguinte. Pode rodar de
    novo sem repetir nada: o aviso não se duplica, e a rodada só avança a
    partir da que fechou."""
    proxima = atual.rodada + 1
    for pid in sorted(atual.votantes):
        avisos._gravar(supabase, caso, pid, MOTIVO_DO_AVISO, f"rodada-{proxima}")
    trilha.registrar(
        supabase,
        caso["id"],
        None,
        "convocou_reuniao_curta",
        f"rodada {atual.rodada} sem maioria; reunião curta e nova rodada de voto",
    )
    (
        supabase.table("conduta_casos")
        .update({"rodada_do_voto": proxima})
        .eq("id", caso["id"])
        .eq("rodada_do_voto", atual.rodada)
        .execute()
    )
    caso["rodada_do_voto"] = proxima


def situacao_em_dia(supabase, caso: dict) -> Situacao:
    """A situação do caso com a reunião curta em dia. Se a convocação caiu
    depois do último voto (a rodada fechou sem maioria e não avançou), ela é
    feita aqui, por quem abre ou age no caso a seguir: o caso não fica parado
    na etapa Voto."""
    atual = situacao(supabase, caso)
    if caso.get("etapa") != "voto" or caso.get("resultado") or not atual.fechada:
        return atual
    if apurar([_conteudo(v) for v in atual.da_rodada(atual.rodada)]).tem_maioria:
        return atual
    _convocar_reuniao_curta(supabase, caso, atual)
    return situacao(supabase, caso)


def votar(
    supabase,
    aberto: CasoAberto,
    *,
    resultado: str,
    medida: str | None,
    dias_de_suspensao: int | None,
    justificativa: str,
) -> dict:
    """O voto do membro, como ele escreveu. Fechada a rodada sem maioria, a
    reunião curta é convocada."""
    caso = aberto.caso
    _exigir_voto(caso)
    atual = situacao_em_dia(supabase, caso)
    if aberto.autor_id not in atual.votantes:
        raise VotoRecusadoError(403, "Só os três membros votantes votam.")
    justificativa = (justificativa or "").strip()
    erro = erro_do_voto(resultado, medida, dias_de_suspensao, justificativa)
    if erro:
        raise VotoRecusadoError(422, erro)
    if any(v["participante_id"] == aberto.autor_id for v in atual.da_rodada(atual.rodada)):
        raise VotoRecusadoError(409, "Você já votou nesta rodada.")
    conteudo = {
        "resultado": resultado,
        "medida": medida,
        "dias_de_suspensao": dias_de_suspensao,
        "justificativa": justificativa,
    }
    cifrado = cifra.cifrar_texto(json.dumps(conteudo, ensure_ascii=False))
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "votou", f"registrou o voto, rodada {atual.rodada}")
    try:
        linha = (
            supabase.table(TABELA)
            .insert(
                {
                    "caso_id": caso["id"],
                    "rodada": atual.rodada,
                    "participante_id": aberto.autor_id,
                    "voto_cifrado": cifrado,
                    "votado_em": agora_utc().isoformat(),
                }
            )
            .execute()
            .data[0]
        )
    except APIError as erro_do_banco:
        if getattr(erro_do_banco, "code", None) == "23505":
            raise VotoRecusadoError(409, "Você já votou nesta rodada.") from erro_do_banco
        raise
    situacao_em_dia(supabase, caso)
    return linha


def bloqueio_da_conclusao(supabase, aberto: CasoAberto) -> str | None:
    """O motivo de a votação ainda não concluir, numa linha, ou None."""
    from app.services.conduta import ata, trava

    caso = aberto.caso
    if aberto.pessoa.papel != "coordenacao":
        return "Só a coordenação conclui a votação."
    atual = situacao_em_dia(supabase, caso)
    if len(atual.votantes) < VOTANTES:
        return "Falta membro votante no caso: o impedido ainda não tem suplente."
    if not atual.fechada:
        return "Faltam votos: a votação conclui depois que os três votarem."
    apuracao = apurar([_conteudo(v) for v in atual.da_rodada(atual.rodada)])
    if not apuracao.tem_maioria:
        return "Não houve maioria. A reunião curta foi convocada."
    if not ata.ata_assinada(supabase, caso["id"]):
        return "Falta a ata assinada pelos três votantes."
    if caso.get("rito") == "completo" and not caso.get("reuniao_concluida_em"):
        return "Falta concluir a reunião do Comitê."
    if apuracao.resultado in COM_MEDIDA:
        return trava.bloqueio(supabase, caso, atual)
    return None


def concluir_votacao(supabase, aberto: CasoAberto) -> dict:
    """CONCLUIR VOTAÇÃO: grava o resultado da maioria e leva o caso à Ata."""
    caso = aberto.caso
    _exigir_voto(caso)
    bloqueio = bloqueio_da_conclusao(supabase, aberto)
    if bloqueio:
        raise VotoRecusadoError(403 if aberto.pessoa.papel != "coordenacao" else 409, bloqueio)
    apuracao = apuracao_da_rodada(supabase, caso)
    medida = (
        cifra.cifrar_texto(json.dumps({"medida": apuracao.medida, "dias_de_suspensao": apuracao.dias_de_suspensao}))
        if apuracao.medida
        else None
    )
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "concluiu_votacao", f"resultado: {RESULTADOS[apuracao.resultado]}"
    )
    linhas = (
        supabase.table("conduta_casos")
        .update(
            {
                "resultado": apuracao.resultado,
                "medida_cifrada": medida,
                "votacao_concluida_em": agora_utc().isoformat(),
                "votacao_concluida_por": aberto.autor_id,
                "etapa": "ata",
            }
        )
        .eq("id", caso["id"])
        .eq("etapa", "voto")
        .execute()
        .data
    ) or []
    if not linhas:
        raise VotoRecusadoError(409, "O caso mudou enquanto você agia. Abra de novo.")
    return linhas[0]
