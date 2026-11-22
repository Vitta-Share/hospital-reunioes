"""O retorno e a correção de processo do Canal de Conduta (issue #1835;
especificação, 6.3, 6.9, 6.10 e 11; ADR 0097, decisão 7).

No Retorno, a coordenação toca em "GERAR RETORNO" e o agente redige a resposta
a quem relatou e a comunicação ao acusado. A coordenação revisa (cada edição é
versão nova) e aprova. Só a versão aprovada sai: a resposta vai à página de
acompanhamento (`resposta_ao_denunciante`), e a comunicação ao acusado abre
para ser entregue. Aprovado o retorno, o caso é concluído.

O que o aplicativo garante, e não só pede ao agente: a resposta a quem relatou
não cita medida nem nome, e a comunicação ao acusado não cita quem relatou.
Nenhum nome vai ao agente (os nomes viram marcadores). Na volta, a resposta
não recebe nome nenhum, e a comunicação só recebe de volta o nome do acusado;
qualquer outro marcador vira "uma pessoa". O texto da coordenação passa pelas
mesmas conferências.

O caso improcedente ou inconclusivo vai da Ata direto ao Retorno: ele não sai
do Comitê. No procedente, o Retorno vem depois da decisão da medida, e o
agente sugere de uma a três correções de processo; o Comitê escolhe, com
responsável e prazo. O banco tem as mesmas travas (migration 222).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date
from typing import Any

from postgrest.exceptions import APIError

from app.config import settings
from app.services.conduta import afastamento, cifra, depoimentos, direcao, membros, relatorio, trilha
from app.services.conduta.acesso import RESULTADOS_QUE_VAO_A_DIRECAO
from app.services.conduta.marcadores import Marcacao
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import CATEGORIAS, agora_utc, votante
from app.services.ia_chaves import ClienteDaAnthropic
from app.services.prompt_loader import load_prompt
from app.utils.text_sanitizer import sanitizar_estrutura

logger = logging.getLogger(__name__)

RETORNOS = "conduta_retornos"
SUGERIDAS = "conduta_correcoes_sugeridas"
CORRECOES = "conduta_correcoes"
PROMPT_DO_RETORNO = "conduta_retorno"
PROMPT_DA_CORRECAO = "conduta_correcao_de_processo"

TAMANHO_DO_TEXTO = 3000
TAMANHO_DO_RESPONSAVEL = 200
MAX_CORRECOES = 3
_TAMANHO_DO_MATERIAL = 20000
MAX_TOKENS = 2048
TEMPO_LIMITE_S = 90.0
ALGUEM = "uma pessoa"
SEM_MEDIDA = ("improcedente", "inconclusivo")

_MARCADOR = re.compile(r"\[[A-Z_]+_\d+\]")
_CONECTIVOS = frozenset({"de", "da", "do", "das", "dos", "e"})
# O que denuncia a medida ou a punição na resposta a quem relatou (sem acento,
# em minúsculas): a Matriz de Consequências e as palavras em volta dela.
_SINAIS_DA_MEDIDA = (
    "medida",
    "advert",
    "suspens",
    "suspend",
    "dispens",
    "justa causa",
    "rescis",
    "demiss",
    "demiti",
    "puni",
    "desligad",
    "sancao",
    "sancoes",
    "orientacao registrada",
)


class RetornoRecusadoError(Exception):
    """A ação não pode acontecer agora. `status` vai para a resposta, e a
    mensagem diz o motivo numa linha."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ── As conferências do texto ────────────────────────────────────────────────


def _normal(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.casefold().split())


def _cita(texto_normal: str, nome: str) -> bool:
    """O nome inteiro, ou qualquer palavra dele que identifica (três letras ou
    mais, fora os conectivos), como palavra inteira do texto."""
    nome = _normal(nome)
    if len(nome) < 2:
        return False
    formas = {nome} | {p for p in nome.split(" ") if len(p) >= 3 and p not in _CONECTIVOS}
    return any(re.search(rf"(?<!\w){re.escape(forma)}(?!\w)", texto_normal) for forma in formas)


def problema_da_resposta(texto: str, nomes: list[str] | set[str]) -> str | None:
    """A resposta a quem relatou não cita medida nem nome."""
    normal = _normal(texto)
    if not normal:
        return "Escreva a resposta a quem relatou."
    if any(sinal in normal for sinal in _SINAIS_DA_MEDIDA):
        return "A resposta a quem relatou não cita a medida: informe a conclusão, não a punição."
    if _MARCADOR.search(texto) or any(_cita(normal, nome) for nome in nomes):
        return "A resposta a quem relatou não cita nome de ninguém."
    return None


def problema_da_comunicacao(texto: str, quem_relatou: list[str] | set[str]) -> str | None:
    """A comunicação ao acusado não cita quem relatou."""
    normal = _normal(texto)
    if not normal:
        return "Escreva a comunicação ao acusado."
    if _MARCADOR.search(texto) or any(_cita(normal, nome) for nome in quem_relatou):
        return "A comunicação ao acusado não cita quem relatou."
    return None


def _nomes_do_caso(supabase, caso: dict) -> list[str]:
    from app.services.conduta import termo_de_declaracao

    return termo_de_declaracao._nomes_do_caso(supabase, caso)


def _quem_relatou(supabase, caso: dict) -> set[str]:
    return afastamento._nomes_de_quem_relatou(supabase, caso)


def _acusado(supabase, caso_id: str) -> str | None:
    for depoimento in depoimentos._do_caso(supabase, caso_id):
        if depoimento.get("papel") == "acusado":
            return cifra.decifrar_texto(depoimento["nome_cifrado"])
    return None


def _conferir(supabase, caso: dict, denunciante: str, acusado: str) -> str | None:
    quem_relatou = _quem_relatou(supabase, caso)
    return problema_da_resposta(denunciante, [*_nomes_do_caso(supabase, caso), *quem_relatou]) or (
        problema_da_comunicacao(acusado, quem_relatou)
    )


# ── Leituras ────────────────────────────────────────────────────────────────


def _com_medida(caso: dict) -> bool:
    return caso.get("resultado") in RESULTADOS_QUE_VAO_A_DIRECAO


def em_aberto(caso: dict) -> bool:
    """O retorno pode ser redigido e aprovado agora: na etapa Retorno ou, no
    caso sem medida, já na etapa Ata."""
    if caso.get("encerrado_em") or caso.get("retorno_aprovado_id"):
        return False
    return caso.get("etapa") == "retorno" or (caso.get("etapa") == "ata" and caso.get("resultado") in SEM_MEDIDA)


def _versoes(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(RETORNOS).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda v: v["versao"])


def _aprovada(supabase, caso: dict) -> dict | None:
    if not caso.get("retorno_aprovado_id"):
        return None
    return next((v for v in _versoes(supabase, caso["id"]) if v["id"] == caso["retorno_aprovado_id"]), None)


def _correcoes(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(CORRECOES).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda c: str(c.get("escolhida_em") or ""))


def _sugeridas(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table(SUGERIDAS).select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda s: s["versao"])


def resposta_ao_denunciante(supabase, caso: dict) -> str | None:
    """O que a página de acompanhamento mostra a quem relatou: só a resposta
    aprovada pela coordenação. Antes da aprovação, nada."""
    aprovada = _aprovada(supabase, caso)
    return cifra.decifrar_texto(aprovada["denunciante_cifrado"]) if aprovada else None


def bloqueio_da_aprovacao(supabase, aberto: CasoAberto) -> str | None:
    caso = aberto.caso
    if aberto.pessoa.papel != "coordenacao":
        return "Só a coordenação aprova o retorno."
    if not em_aberto(caso):
        return "O retorno não está em aberto."
    if not _versoes(supabase, caso["id"]):
        return "Gere o retorno antes de aprovar."
    if _com_medida(caso):
        if not direcao.decisao_do_caso(supabase, caso["id"]):
            return "Falta a decisão da Direção sobre a medida."
        if not _correcoes(supabase, caso["id"]):
            return "Escolha ao menos uma correção de processo, com responsável e prazo."
    return None


def pode_escolher_correcao(aberto: CasoAberto) -> bool:
    caso = aberto.caso
    return (
        _com_medida(caso)
        and not caso.get("encerrado_em")
        and votante(aberto.pessoa.papel, aberto.atribuicoes)
        and caso.get("etapa") in ("ata", "medida", "retorno")
    )


def para_a_tela(supabase, aberto: CasoAberto) -> dict[str, Any]:
    """A parte da tela do caso depois da votação: o envio à Direção, a decisão
    da medida, o retorno e a correção de processo."""
    caso = aberto.caso
    if not caso.get("resultado"):
        return {"medida_e_retorno": None}
    coordena = aberto.pessoa.papel == "coordenacao"
    versoes = _versoes(supabase, caso["id"])
    correcoes = _correcoes(supabase, caso["id"])
    sugeridas = _sugeridas(supabase, caso["id"])
    autores = membros.nomes(
        supabase, sorted({v["autor_id"] for v in versoes} | {c["escolhida_por"] for c in correcoes})
    )
    aprovada = _aprovada(supabase, caso)
    aberto_agora = em_aberto(caso)
    envio = direcao.bloqueio_do_envio(aberto) if caso.get("etapa") == "ata" and _com_medida(caso) else None
    return {
        "medida_e_retorno": {
            "com_medida": _com_medida(caso),
            "pode_enviar_a_direcao": caso.get("etapa") == "ata" and _com_medida(caso) and envio is None,
            "bloqueio_do_envio": envio,
            **direcao.para_o_comite(supabase, caso),
            "retorno": {
                "em_aberto": aberto_agora,
                "pode_redigir": aberto_agora and coordena,
                "pode_aprovar": aberto_agora and bloqueio_da_aprovacao(supabase, aberto) is None,
                "bloqueio_da_aprovacao": bloqueio_da_aprovacao(supabase, aberto) if aberto_agora else None,
                "versoes": [
                    {
                        "versao": v["versao"],
                        "origem": v["origem"],
                        "autor": autores.get(v["autor_id"], ""),
                        "criado_em": v.get("criado_em"),
                        "denunciante": cifra.decifrar_texto(v["denunciante_cifrado"]),
                        "acusado": cifra.decifrar_texto(v["acusado_cifrado"]),
                    }
                    for v in reversed(versoes)
                ],
                "aprovado": {
                    "versao": aprovada["versao"],
                    "aprovado_em": caso.get("retorno_aprovado_em"),
                    "aprovado_por": membros.nomes(supabase, [caso["retorno_aprovado_por"]]).get(
                        caso["retorno_aprovado_por"], ""
                    ),
                }
                if aprovada
                else None,
            },
            "correcoes": {
                "sugeridas": json.loads(cifra.decifrar_texto(sugeridas[-1]["itens_cifrado"])) if sugeridas else [],
                "escolhidas": [
                    {
                        "texto": cifra.decifrar_texto(c["texto_cifrado"]),
                        "responsavel": cifra.decifrar_texto(c["responsavel_cifrado"]),
                        "prazo_em": c["prazo_em"],
                        "escolhida_por": autores.get(c["escolhida_por"], ""),
                        "escolhida_em": c.get("escolhida_em"),
                    }
                    for c in correcoes
                ],
                "pode_escolher": pode_escolher_correcao(aberto),
            }
            if _com_medida(caso)
            else None,
        }
    }


# ── O retorno ───────────────────────────────────────────────────────────────


def _exigir_retorno(aberto: CasoAberto, o_que: str) -> None:
    if aberto.pessoa.papel != "coordenacao":
        raise RetornoRecusadoError(403, f"Só a coordenação {o_que}.")
    if not em_aberto(aberto.caso):
        raise RetornoRecusadoError(409, "O retorno não está em aberto neste caso.")


def _gravar_versao(supabase, aberto: CasoAberto, denunciante: str, acusado: str, origem: str) -> dict:
    caso = aberto.caso
    versao = max((v["versao"] for v in _versoes(supabase, caso["id"])), default=0) + 1
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "redigiu_retorno" if origem == "agente" else "editou_retorno",
        f"retorno, versão {versao}, {'pelo agente' if origem == 'agente' else 'pela coordenação'}",
    )
    try:
        return (
            supabase.table(RETORNOS)
            .insert(
                {
                    "caso_id": caso["id"],
                    "versao": versao,
                    "denunciante_cifrado": cifra.cifrar_texto(denunciante),
                    "acusado_cifrado": cifra.cifrar_texto(acusado),
                    "origem": origem,
                    "autor_id": aberto.autor_id,
                    "criado_em": agora_utc().isoformat(),
                }
            )
            .execute()
            .data[0]
        )
    except APIError as erro:
        if getattr(erro, "code", None) == "23505":
            raise RetornoRecusadoError(409, "O retorno mudou enquanto você agia. Abra de novo.") from erro
        raise


def _relatorio_marcado(supabase, caso: dict, marcacao: Marcacao, nomes: list[str]) -> str | None:
    versoes = relatorio._versoes(supabase, caso["id"], "relatorio")
    if not versoes:
        return None
    return marcacao.marcar(cifra.decifrar_texto(versoes[-1]["texto_cifrado"])[:_TAMANHO_DO_MATERIAL], nomes)


def _cabecalho(caso: dict) -> list[str]:
    from app.services.conduta import voto

    return [
        f"Resultado do caso: {voto.RESULTADOS[caso['resultado']]}.",
        f"Categoria: {CATEGORIAS.get(caso.get('categoria') or '', 'não informada')}.",
    ]


def _mensagem_do_retorno(supabase, caso: dict, marcacao: Marcacao, acusado: str | None) -> str:
    nomes = [*_nomes_do_caso(supabase, caso), *(_quem_relatou(supabase, caso))]
    if acusado:
        nomes.append(acusado)
    partes = _cabecalho(caso)
    if acusado:
        partes.append(f"O acusado é {marcacao.marcar(acusado, [acusado])}.")
    texto = _relatorio_marcado(supabase, caso, marcacao, nomes)
    if texto:
        partes.append(f"<relatorio_de_apuracao>\n{texto}\n</relatorio_de_apuracao>")
    return "\n\n".join(partes)


def _cliente_do_agente_do_retorno() -> ClienteDaAnthropic:
    return ClienteDaAnthropic(max_retries=0, timeout=TEMPO_LIMITE_S)


def _pedir_ao_agente_do_retorno(cliente, sistema: str, mensagem: str) -> str | None:
    """Uma chamada ao modelo. None quando ele recusa ou corta no teto."""
    resposta = cliente.messages.create(
        model=settings.conduta_agente_modelo,
        max_tokens=MAX_TOKENS,
        system=sistema,
        messages=[{"role": "user", "content": mensagem}],
    )
    if resposta.stop_reason in ("refusal", "max_tokens"):
        return None
    return "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()


def _objeto(bruto: str) -> dict:
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    objeto = json.loads(bruto[inicio : fim + 1] if 0 <= inicio < fim else bruto)
    if not isinstance(objeto, dict):
        raise ValueError("a resposta não é um objeto")
    return objeto


def _limpo(valor: Any) -> str:
    return "\n".join(" ".join(linha.split()) for linha in str(valor or "").strip().splitlines() if linha.strip())[
        :TAMANHO_DO_TEXTO
    ]


def _so_o_acusado_volta(texto: str, marcacao: Marcacao, acusado: str | None) -> str:
    """Na comunicação, só o marcador do acusado volta a ser nome; qualquer
    outro (uma testemunha, quem relatou) vira "uma pessoa"."""

    def trocar(achado: re.Match) -> str:
        original = marcacao.originais.get(achado.group(0))
        return original if acusado and original and _normal(original) == _normal(acusado) else ALGUEM

    return _MARCADOR.sub(trocar, texto)


def redigir_retorno_do_caso(supabase, aberto: CasoAberto) -> dict:
    """GERAR RETORNO: o agente redige a resposta a quem relatou e a comunicação
    ao acusado, e a versão nova entra para a coordenação revisar. Roda no
    executor da IA."""
    _exigir_retorno(aberto, "gera o retorno")
    if not settings.anthropic_api_key:
        raise RetornoRecusadoError(503, "O agente está fora do ar agora. Tente de novo em instantes.")
    caso = aberto.caso
    acusado = _acusado(supabase, caso["id"])
    marcacao = Marcacao()
    mensagem = _mensagem_do_retorno(supabase, caso, marcacao, acusado)
    try:
        bruto = _pedir_ao_agente_do_retorno(_cliente_do_agente_do_retorno(), load_prompt(PROMPT_DO_RETORNO), mensagem)
    except Exception as exc:  # noqa: BLE001 (o erro da API vira a recusa da tela)
        logger.warning("[Conduta] Agente do retorno não respondeu (%s)", type(exc).__name__)
        raise RetornoRecusadoError(503, "O agente não respondeu. Tente de novo em instantes.") from exc
    try:
        objeto = _objeto(bruto or "")
        denunciante = _MARCADOR.sub(ALGUEM, _limpo(objeto.get("resposta_ao_denunciante")))
        comunicacao = _so_o_acusado_volta(_limpo(objeto.get("comunicacao_ao_acusado")), marcacao, acusado)
    except (ValueError, KeyError, TypeError) as exc:
        raise RetornoRecusadoError(502, "O agente não devolveu o retorno. Gere de novo.") from exc
    denunciante, comunicacao = sanitizar_estrutura([denunciante, comunicacao])
    problema = _conferir(supabase, caso, denunciante, comunicacao)
    if problema:
        raise RetornoRecusadoError(502, f"O agente errou: {problema} Gere de novo.")
    return _gravar_versao(supabase, aberto, denunciante, comunicacao, "agente")


def editar_retorno(supabase, aberto: CasoAberto, *, denunciante: str, acusado: str) -> dict:
    """A coordenação revisa o retorno: a edição é versão nova, com as mesmas
    conferências do texto do agente."""
    _exigir_retorno(aberto, "edita o retorno")
    denunciante, acusado = _limpo(denunciante), _limpo(acusado)
    problema = _conferir(supabase, aberto.caso, denunciante, acusado)
    if problema:
        raise RetornoRecusadoError(422, problema)
    return _gravar_versao(supabase, aberto, denunciante, acusado, "coordenacao")


def aprovar_retorno(supabase, aberto: CasoAberto) -> dict:
    """APROVAR RETORNO: a última versão sai, e o caso é concluído."""
    caso = aberto.caso
    bloqueio = bloqueio_da_aprovacao(supabase, aberto)
    if bloqueio:
        raise RetornoRecusadoError(403 if aberto.pessoa.papel != "coordenacao" else 409, bloqueio)
    ultima = _versoes(supabase, caso["id"])[-1]
    problema = _conferir(
        supabase,
        caso,
        cifra.decifrar_texto(ultima["denunciante_cifrado"]),
        cifra.decifrar_texto(ultima["acusado_cifrado"]),
    )
    if problema:
        raise RetornoRecusadoError(409, f"{problema} Edite o retorno antes de aprovar.")
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "aprovou_retorno",
        f"aprovou o retorno, versão {ultima['versao']}, e concluiu o caso",
    )
    agora = agora_utc().isoformat()
    linhas = (
        supabase.table("conduta_casos")
        .update(
            {
                "retorno_aprovado_id": ultima["id"],
                "retorno_aprovado_em": agora,
                "retorno_aprovado_por": aberto.autor_id,
                "encerrado_em": agora,
                "desfecho": "concluido",
                "etapa": "encerrado",
            }
        )
        .eq("id", caso["id"])
        .is_("retorno_aprovado_id", "null")
        .execute()
        .data
    ) or []
    if not linhas:
        raise RetornoRecusadoError(409, "O caso mudou enquanto você agia. Abra de novo.")
    return linhas[0]


def comunicacao_ao_acusado(supabase, aberto: CasoAberto) -> str:
    """A comunicação ao acusado aprovada, para entregar, depois de gravada a
    abertura. Antes da aprovação ela não sai."""
    aprovada = _aprovada(supabase, aberto.caso)
    if not aprovada:
        raise RetornoRecusadoError(409, "A comunicação ao acusado só sai depois da aprovação da coordenação.")
    trilha.registrar(supabase, aberto.caso["id"], aberto.autor_id, "leitura", "abriu a comunicação ao acusado aprovada")
    return cifra.decifrar_texto(aprovada["acusado_cifrado"])


# ── A correção de processo ──────────────────────────────────────────────────


def _exigir_correcao(aberto: CasoAberto) -> None:
    if not _com_medida(aberto.caso) or aberto.caso.get("encerrado_em"):
        raise RetornoRecusadoError(409, "A correção de processo é do caso procedente, antes do encerramento.")
    if not pode_escolher_correcao(aberto):
        raise RetornoRecusadoError(403, "Só os membros votantes do caso cuidam da correção de processo.")


def _cliente_do_agente_da_correcao() -> ClienteDaAnthropic:
    return ClienteDaAnthropic(max_retries=0, timeout=TEMPO_LIMITE_S)


def _pedir_ao_agente_da_correcao(cliente, sistema: str, mensagem: str) -> str | None:
    """Uma chamada ao modelo. None quando ele recusa ou corta no teto."""
    resposta = cliente.messages.create(
        model=settings.conduta_agente_modelo,
        max_tokens=MAX_TOKENS,
        system=sistema,
        messages=[{"role": "user", "content": mensagem}],
    )
    if resposta.stop_reason in ("refusal", "max_tokens"):
        return None
    return "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()


def sugerir_correcoes_de_processo(supabase, aberto: CasoAberto) -> list[str]:
    """SUGERIR CORREÇÕES: o agente sugere de uma a três, e a sugestão fica
    guardada como versão nova. Roda no executor da IA."""
    _exigir_correcao(aberto)
    if not settings.anthropic_api_key:
        raise RetornoRecusadoError(503, "O agente está fora do ar agora. Tente de novo em instantes.")
    caso = aberto.caso
    marcacao = Marcacao()
    nomes = [*_nomes_do_caso(supabase, caso), *_quem_relatou(supabase, caso)]
    partes = _cabecalho(caso)
    texto = _relatorio_marcado(supabase, caso, marcacao, nomes)
    if texto:
        partes.append(f"<relatorio_de_apuracao>\n{texto}\n</relatorio_de_apuracao>")
    try:
        bruto = _pedir_ao_agente_da_correcao(
            _cliente_do_agente_da_correcao(), load_prompt(PROMPT_DA_CORRECAO), "\n\n".join(partes)
        )
    except Exception as exc:  # noqa: BLE001 (o erro da API vira a recusa da tela)
        logger.warning("[Conduta] Agente da correção de processo não respondeu (%s)", type(exc).__name__)
        raise RetornoRecusadoError(503, "O agente não respondeu. Tente de novo em instantes.") from exc
    try:
        lista = _objeto(bruto or "").get("correcoes")
        itens = [
            _MARCADOR.sub(ALGUEM, _limpo(item))
            for item in (lista if isinstance(lista, list) else [])
            if str(item).strip()
        ][:MAX_CORRECOES]
    except (ValueError, KeyError, TypeError) as exc:
        raise RetornoRecusadoError(502, "O agente não devolveu as correções. Peça de novo.") from exc
    if not itens:
        raise RetornoRecusadoError(502, "O agente não devolveu as correções. Peça de novo.")
    itens = sanitizar_estrutura(itens)
    versao = max((s["versao"] for s in _sugeridas(supabase, caso["id"])), default=0) + 1
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "sugeriu_correcoes", f"sugestão de correção de processo, versão {versao}"
    )
    supabase.table(SUGERIDAS).insert(
        {
            "caso_id": caso["id"],
            "versao": versao,
            "itens_cifrado": cifra.cifrar_texto(json.dumps(itens, ensure_ascii=False)),
            "autor_id": aberto.autor_id,
            "criado_em": agora_utc().isoformat(),
        }
    ).execute()
    return itens


def escolher_correcao(
    supabase, aberto: CasoAberto, *, texto: str, responsavel: str, prazo_em: date, hoje: date
) -> dict:
    """O Comitê escolhe a correção de processo, com responsável e prazo."""
    _exigir_correcao(aberto)
    texto, responsavel = _limpo(texto), " ".join((responsavel or "").split())
    if not texto:
        raise RetornoRecusadoError(422, "Escreva a correção de processo.")
    if not responsavel:
        raise RetornoRecusadoError(422, "Diga quem é o responsável pela correção.")
    if len(responsavel) > TAMANHO_DO_RESPONSAVEL:
        raise RetornoRecusadoError(422, f"O responsável cabe em {TAMANHO_DO_RESPONSAVEL} caracteres.")
    if prazo_em < hoje:
        raise RetornoRecusadoError(422, "O prazo da correção não pode estar no passado.")
    caso = aberto.caso
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "escolheu_correcao",
        f"escolheu uma correção de processo, com prazo em {prazo_em.strftime('%d/%m/%Y')}",
    )
    return (
        supabase.table(CORRECOES)
        .insert(
            {
                "caso_id": caso["id"],
                "texto_cifrado": cifra.cifrar_texto(texto),
                "responsavel_cifrado": cifra.cifrar_texto(responsavel),
                "prazo_em": prazo_em.isoformat(),
                "escolhida_por": aberto.autor_id,
                "escolhida_em": agora_utc().isoformat(),
            }
        )
        .execute()
        .data[0]
    )
