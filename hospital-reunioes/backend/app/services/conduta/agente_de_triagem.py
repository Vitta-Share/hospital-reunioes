"""O agente de triagem do Canal de Conduta (issue #1827, PRD #1786, ADR 0097
decisões 6, 7 e 15; especificação, seções 6.1 e 11 e Anexo A).

Todo caso novo vai ao agente uma única vez, em segundo plano, logo depois do
registro (`casos.registrar_caso` com `tarefas`): é a terceira exceção à
decisão 1 da ADR 0082, sem clique de ninguém. O agente só sugere. A
coordenação confirma ou discorda de cada item, e a discordância fica gravada
com o motivo, cifrado.

O que vai ao modelo é o relato pseudonimizado (ADR 0034), com os nomes dos
membros do Comitê trocados por marcador também, a categoria que quem relatou
escolheu e a lista dos casos anteriores da fila comum, sem nome. Nada de
contato, identificação ou anexo: a entrada é montada só com esses campos. O
possível impedimento por nome é conferido aqui, no app, sem IA
(`possivel_impedimento`).

O que pode acontecer com o caso, sempre com uma linha em `conduta_sugestoes`
e outra na trilha:

- a resposta passa na validação: a sugestão fica gravada, cifrada;
- o agente está desligado ou sem chave (`desligado`), não respondeu
  (`agente_fora`), a cota do dia acabou (`teto`) ou a resposta veio fora do
  formato (`validacao`): o caso segue na fila para triagem manual, e a trilha
  diz por quê. O relato nunca fica retido.

Cada chamada gasta uma das `TETO_DIARIO` leituras do dia, contadas no banco à
parte da Ouvidoria e do Núcleo (migration 200). O SDK não repete
(`max_retries=0`).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape

from app.config import settings
from app.services import ai_processor
from app.services.conduta import cifra, membros, trilha
from app.services.ia_chaves import ClienteDaAnthropic
from app.services.ouvidoria_pseudonimizacao import MARCADOR_NOME, pseudonimizar
from app.services.prompt_loader import load_prompt
from app.utils.text_sanitizer import sanitizar_travessao

logger = logging.getLogger(__name__)

PROMPT = "conduta_agente_triagem"
TETO_DIARIO = 100
FUNCAO_DA_COTA = "conduta_agente_reservar_chamada"
MAX_TOKENS = 4096
TEMPO_LIMITE_S = 90.0
CASOS_ANTERIORES = 30

DESLIGADO = "desligado"
AGENTE_FORA = "agente_fora"
TETO = "teto"
VALIDACAO = "validacao"

POR_QUE_SEM_SUGESTAO = {
    DESLIGADO: "o agente está desligado",
    AGENTE_FORA: "o agente está fora do ar",
    TETO: "o teto diário de leituras do agente foi atingido",
    VALIDACAO: "a resposta do agente veio fora do formato",
}

ESCOPOS = ("DENTRO", "FORA", "MISTO")
DESTINOS = ("DP", "OUVIDORIA", "NSP", "GESTAO")
CATEGORIAS = ("A", "B", "C", "D", "E")
RITOS = ("ENCAMINHAMENTO", "RAPIDO", "COMPLETO", "ESPECIAL")
SIM_NAO = ("SIM", "NAO")
CONFIANCAS = ("ALTA", "MEDIA", "BAIXA")
MAXIMO_DE_PERGUNTAS = 3
PALAVRAS_DO_ASSUNTO = 8

# Os itens da sugestão, na ordem da tela, com o título que a tela mostra.
ITENS = {
    "escopo": "É do canal?",
    "categoria": "Categoria",
    "rito": "Rito",
    "especial": "Rota Especial",
    "risco_imediato": "Risco imediato",
    "assunto_para_lista": "Assunto para a lista",
    "resumo": "Resumo",
    "lacunas": "O que falta para apurar",
    "perguntas_ao_denunciante": "Perguntas a quem relatou",
    "casos_parecidos": "Casos parecidos",
    "relatos_repetidos_improcedentes": "Relatos repetidos não confirmados",
    "sinalizar_nsp": "Sinalizar ao Núcleo de Segurança do Paciente",
    "confianca": "Confiança",
}
_ESCOLHAS = {
    "escopo": ESCOPOS,
    "categoria": (*CATEGORIAS, ""),
    "rito": RITOS,
    "especial": SIM_NAO,
    "risco_imediato": SIM_NAO,
    "relatos_repetidos_improcedentes": SIM_NAO,
    "sinalizar_nsp": SIM_NAO,
    "confianca": CONFIANCAS,
}
_LISTAS = ("lacunas", "perguntas_ao_denunciante", "casos_parecidos")
_TEXTOS = ("assunto_para_lista", "resumo")

_ROTULOS = {
    "DENTRO": "Dentro do canal",
    "FORA": "Fora do canal",
    "MISTO": "Misto",
    "DP": "Departamento Pessoal",
    "OUVIDORIA": "Ouvidoria",
    "NSP": "Núcleo de Segurança do Paciente",
    "GESTAO": "Liderança ou gestão",
    "ENCAMINHAMENTO": "Encaminhamento",
    "RAPIDO": "Rápido",
    "COMPLETO": "Completo",
    "ESPECIAL": "Especial",
    "SIM": "Sim",
    "NAO": "Não",
    "ALTA": "Alta",
    "MEDIA": "Média",
    "BAIXA": "Baixa",
}
_NOMES_DAS_CATEGORIAS = {
    "A": "Conduta e relações",
    "B": "Patrimônio",
    "C": "Integridade nos negócios",
    "D": "Registros e informação",
    "E": "Segurança e conformidade",
}


# ═══════════════════════════════════════════════════════════════════════════
# O que é puro: a entrada, a validação e o impedimento por nome
# ═══════════════════════════════════════════════════════════════════════════


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


def _trocar_nomes_conhecidos(relato: str, nomes: list[str]) -> str:
    """Troca por marcador cada nome conhecido (o completo, e o primeiro com o
    último), sem olhar caixa nem acento. A pseudonimização vem depois e pega o
    resto."""
    for nome in sorted(nomes, key=len, reverse=True):
        partes = [p for p in nome.split() if len(p) > 2]
        if len(partes) < 2:
            continue
        for forma in (" ".join(nome.split()), f"{partes[0]} {partes[-1]}"):
            padrao = r"\b" + r"\s+".join(_regex_sem_acento(p) for p in forma.split()) + r"\b"
            relato = re.sub(padrao, MARCADOR_NOME, relato, flags=re.IGNORECASE)
    return relato


_VARIANTES = {"a": "aáàâã", "e": "eéê", "i": "ií", "o": "oóôõ", "u": "uúü", "c": "cç"}


def _regex_sem_acento(palavra: str) -> str:
    saida = []
    for letra in _sem_acento(palavra):
        variantes = _VARIANTES.get(letra)
        saida.append(f"[{variantes}]" if variantes else re.escape(letra))
    return "".join(saida)


def montar_mensagem(
    relato: str, *, categoria: str | None, anteriores: list[dict], nomes_conhecidos: list[str] = ()
) -> str:
    """A mensagem que vai ao modelo: o relato pseudonimizado, a categoria que
    quem relatou escolheu e os casos anteriores, sem nome. Só esses campos."""
    texto = pseudonimizar(_trocar_nomes_conhecidos(relato, list(nomes_conhecidos)))
    escolhida = _NOMES_DAS_CATEGORIAS.get(categoria or "", "não escolheu")
    linhas = [
        f"  - {escape(c['protocolo'])}, {escape(c['data'])}, assunto: {escape(c['assunto'] or 'sem assunto')}, "
        f"categoria {escape(c['categoria'] or 'sem categoria')}, rito {escape(c['rito'] or 'sem rito')}, "
        f"resultado: {escape(c['resultado'] or 'em andamento')}"
        for c in anteriores
    ]
    return (
        "<relato>\n"
        f"  <texto>{escape(texto, quote=False)}</texto>\n"
        f"  <categoria_escolhida>{escape(escolhida)}</categoria_escolhida>\n"
        "</relato>\n"
        "<casos_anteriores>\n" + ("\n".join(linhas) or "  nenhum") + "\n</casos_anteriores>"
    )


def validar_saida(saida) -> list[str]:
    """As violações da resposta do agente; lista vazia quando ela serve."""
    if not isinstance(saida, dict):
        return ["formato:objeto"]
    erros = []
    for item in ITENS:
        bloco = saida.get(item)
        if not isinstance(bloco, dict) or not isinstance(bloco.get("justificativa"), str):
            erros.append(f"formato:{item}")
            continue
        if not bloco["justificativa"].strip() or not isinstance(bloco.get("trecho", ""), str):
            erros.append(f"formato:{item}")
            continue
        valor = bloco.get("valor")
        if item in _ESCOLHAS and valor not in _ESCOLHAS[item]:
            erros.append(f"formato:{item}")
        elif item in _LISTAS and not (isinstance(valor, list) and all(isinstance(v, str) for v in valor)):
            erros.append(f"formato:{item}")
        elif item in _TEXTOS and not (isinstance(valor, str) and valor.strip()):
            erros.append(f"formato:{item}")
    if erros:
        return erros
    escopo, rito = saida["escopo"]["valor"], saida["rito"]["valor"]
    destino = saida["escopo"].get("destino") or ""
    if destino not in (*DESTINOS, "") or (escopo == "DENTRO") != (destino == ""):
        erros.append("destino")
    if (escopo == "FORA") != (rito == "ENCAMINHAMENTO") or (escopo == "FORA") != (saida["categoria"]["valor"] == ""):
        erros.append("fora")
    if (saida["especial"]["valor"] == "SIM") != (rito == "ESPECIAL"):
        erros.append("especial")
    if len(saida["perguntas_ao_denunciante"]["valor"]) > MAXIMO_DE_PERGUNTAS:
        erros.append("perguntas")
    if len(saida["assunto_para_lista"]["valor"].split()) > PALAVRAS_DO_ASSUNTO:
        erros.append("assunto")
    return erros


def possivel_impedimento(relato: str, membros_do_comite: list[dict]) -> list[dict]:
    """Os membros cujo nome aparece no relato: o nome completo, ou o primeiro
    e o último juntos. Conferido aqui, sem IA (ADR 0097, decisão 7)."""
    texto = _sem_acento(relato or "")
    achados = []
    for membro in membros_do_comite:
        partes = [p for p in _sem_acento(membro.get("nome") or "").split() if len(p) > 2]
        if len(partes) < 2:
            continue
        formas = (" ".join(partes), f"{partes[0]} {partes[-1]}")
        if any(re.search(r"\b" + r"\s+".join(map(re.escape, f.split())) + r"\b", texto) for f in formas):
            achados.append({"membro": membro["nome"], "motivo": "O nome aparece no relato."})
    return achados


# ═══════════════════════════════════════════════════════════════════════════
# A chamada ao modelo
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class Leitura:
    """O que o agente devolveu para um caso: a sugestão validada, ou o motivo
    de o caso ficar para triagem manual."""

    sugestao: dict | None = None
    motivo_manual: str | None = None
    violacoes: list[str] = field(default_factory=list)


def _perguntar(cliente, modelo: str, mensagem: str):
    resposta = cliente.messages.create(
        model=modelo,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": load_prompt(PROMPT), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": mensagem}],
    )
    if resposta.stop_reason in ("refusal", "max_tokens"):
        return None
    bruto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text")
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    try:
        objeto = json.loads(bruto[inicio : fim + 1] if 0 <= inicio < fim else bruto)
    except ValueError:
        return None
    return objeto if isinstance(objeto, dict) else None


def _sanitizada(valor):
    if isinstance(valor, str):
        return sanitizar_travessao(valor).strip()
    if isinstance(valor, list):
        return [_sanitizada(item) for item in valor]
    if isinstance(valor, dict):
        return {chave: _sanitizada(item) for chave, item in valor.items()}
    return valor


def ler_o_relato(cliente, mensagem: str, *, modelo: str, reservar: Callable[[], bool] = lambda: True) -> Leitura:
    """Uma leitura do agente, com uma vaga da cota antes. É a mesma função que
    o comando do teste de aceite usa (`scripts/conduta_teste_de_aceite.py`)."""
    if not reservar():
        return Leitura(motivo_manual=TETO)
    try:
        saida = _perguntar(cliente, modelo, mensagem)
    except Exception as exc:
        logger.warning("[CONDUTA] Agente de triagem não respondeu (%s)", type(exc).__name__)
        return Leitura(motivo_manual=AGENTE_FORA)
    violacoes = validar_saida(saida)
    if violacoes:
        return Leitura(motivo_manual=VALIDACAO, violacoes=violacoes)
    return Leitura(sugestao={item: _sanitizada(saida[item]) for item in ITENS})


def versao_do_prompt() -> str:
    achada = re.search(r"^Versão (\d+(?:\.\d+)*)", load_prompt(PROMPT), re.MULTILINE)
    if not achada:
        raise ValueError("o prompt do agente do Canal não diz a versão")
    return achada.group(1)


# ═══════════════════════════════════════════════════════════════════════════
# A triagem no app: o caso recém-registrado
# ═══════════════════════════════════════════════════════════════════════════


def agente_ligado() -> bool:
    """Ligado na configuração e com chave: sem chave (local e CI) o caso entra
    para triagem manual, e nenhuma chamada de IA acontece."""
    return settings.conduta_agente_ligado and bool(settings.anthropic_api_key)


def agendar_triagem_do_caso(tarefas, supabase, caso_id: str) -> None:
    tarefas.add_task(triar_caso_fora_do_loop, supabase, caso_id)


async def triar_caso_fora_do_loop(supabase, caso_id: str) -> None:
    await ai_processor.chamar_ia_fora_do_loop(triar_caso, supabase, caso_id)


def _reservar_chamada(supabase) -> bool:
    """Uma vaga da cota do Canal. Só um `true` explícito do banco libera."""
    dados = supabase.rpc(FUNCAO_DA_COTA, {"p_teto": TETO_DIARIO}).execute().data
    return isinstance(dados, list) and len(dados) == 1 and dados[0].get("reservada") is True


def _ja_lido(supabase, caso_id: str) -> bool:
    return bool(supabase.table("conduta_sugestoes").select("caso_id").eq("caso_id", caso_id).limit(1).execute().data)


def _nomes_dos_membros(supabase) -> list[str]:
    comite_id = membros.id_do_comite(supabase)
    if not comite_id:
        return []
    ids = [p["participante_id"] for p in membros.participacoes(supabase, comite_id)]
    return [nome for nome in membros.nomes(supabase, ids).values() if nome]


def _assunto(supabase, caso_id: str) -> str | None:
    linhas = supabase.table("conduta_sugestoes").select("sugestao_cifrada").eq("caso_id", caso_id).execute().data
    if not linhas or not linhas[0].get("sugestao_cifrada"):
        return None
    return json.loads(cifra.decifrar_texto(linhas[0]["sugestao_cifrada"]))["assunto_para_lista"]["valor"]


def _casos_anteriores(supabase, caso_id: str) -> list[dict]:
    """Os últimos casos da fila comum, sem nome: a Rota Especial fica de fora,
    para o protocolo dela não aparecer na sugestão de um caso comum."""
    linhas = (
        supabase.table("conduta_casos")
        .select("id, protocolo, recebido_em, categoria, rito, desfecho")
        .eq("rota", "comum")
        .order("recebido_em", desc=True)
        .limit(CASOS_ANTERIORES + 1)
        .execute()
        .data
        or []
    )
    return [
        {
            "protocolo": linha["protocolo"],
            "data": str(linha.get("recebido_em") or "")[:10],
            "assunto": _assunto(supabase, linha["id"]),
            "categoria": linha.get("categoria"),
            "rito": linha.get("rito"),
            "resultado": linha.get("desfecho"),
        }
        for linha in linhas
        if linha["id"] != caso_id
    ][:CASOS_ANTERIORES]


def _cliente() -> ClienteDaAnthropic:
    return ClienteDaAnthropic(max_retries=0, timeout=TEMPO_LIMITE_S)


def _ler_o_caso(supabase, caso_id: str, cliente) -> tuple[Leitura, str]:
    modelo = settings.conduta_agente_modelo
    if not agente_ligado():
        return Leitura(motivo_manual=DESLIGADO), modelo
    linhas = supabase.table("conduta_casos").select("relato_cifrado, categoria").eq("id", caso_id).execute().data
    caso = linhas[0]
    mensagem = montar_mensagem(
        cifra.decifrar_texto(caso["relato_cifrado"]),
        categoria=caso.get("categoria"),
        anteriores=_casos_anteriores(supabase, caso_id),
        nomes_conhecidos=_nomes_dos_membros(supabase),
    )
    leitura = ler_o_relato(cliente or _cliente(), mensagem, modelo=modelo, reservar=lambda: _reservar_chamada(supabase))
    return leitura, modelo


def triar_caso(supabase, caso_id: str, *, cliente=None) -> None:
    """A leitura do caso recém-registrado, uma única vez. Nunca levanta: o
    caso já existe e já tem protocolo. Sem sugestão, ele segue na fila para
    triagem manual, e a trilha diz por quê."""
    try:
        if _ja_lido(supabase, caso_id):
            return
        try:
            leitura, modelo = _ler_o_caso(supabase, caso_id, cliente)
        except Exception as exc:
            logger.warning("[CONDUTA] Leitura do caso %s falhou (%s)", caso_id, type(exc).__name__)
            leitura, modelo = Leitura(motivo_manual=AGENTE_FORA), settings.conduta_agente_modelo
        linha = {"caso_id": caso_id, "modelo": modelo, "prompt_versao": versao_do_prompt()}
        if leitura.sugestao is not None:
            trilha.registrar(supabase, caso_id, None, "sugestao_do_agente", "o agente sugeriu a triagem")
            linha |= {"situacao": "sugerida", "sugestao_cifrada": cifra.cifrar_texto(json.dumps(leitura.sugestao))}
        else:
            motivo = leitura.motivo_manual or AGENTE_FORA
            por_que = POR_QUE_SEM_SUGESTAO[motivo]
            trilha.registrar(supabase, caso_id, None, "triagem_manual", f"sem sugestão do agente: {por_que}")
            linha |= {"situacao": "manual", "motivo_manual": motivo}
            logger.warning("[CONDUTA] Caso %s para triagem manual (%s)", caso_id, motivo)
        supabase.table("conduta_sugestoes").insert(linha).execute()
    except Exception as exc:
        logger.error("[CONDUTA] Triagem do agente falhou no caso %s (%s)", caso_id, type(exc).__name__)


# ═══════════════════════════════════════════════════════════════════════════
# A sugestão na tela do caso, e a resposta da coordenação item a item
# ═══════════════════════════════════════════════════════════════════════════

RESPOSTAS = ("confirmo", "discordo")
_TAMANHO_DO_MOTIVO = 500


class RespostaRecusadaError(Exception):
    """A resposta não pode ser gravada agora. `status` vai para a resposta HTTP."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


def _valor_na_tela(item: str, bloco: dict) -> str:
    valor = bloco["valor"]
    if isinstance(valor, list):
        return "\n".join(valor) or "Nenhum"
    if item == "categoria":
        return f"{valor}. {_NOMES_DAS_CATEGORIAS[valor]}" if valor else "Sem categoria (fora do canal)"
    texto = _ROTULOS.get(valor, valor)
    if item == "escopo" and bloco.get("destino"):
        texto = f"{texto}, parte de fora: {_ROTULOS[bloco['destino']]}"
    if item == "especial" and valor == "SIM" and bloco.get("citados"):
        texto = f"{texto}, cita: {bloco['citados']}"
    return texto


def _membros_vigentes(supabase, hoje) -> list[dict]:
    ids = membros.ids_dos_membros_vigentes(supabase, hoje)
    return [{"nome": nome} for nome in membros.nomes(supabase, ids).values() if nome]


def sugestao_para_a_tela(supabase, caso: dict, relato: str, papel: str | None, hoje) -> dict:
    """O que a tela do caso mostra: cada item como "Sugestão", com a
    justificativa e o trecho, a resposta da coordenação, e o possível
    impedimento por nome, conferido aqui."""
    linhas = supabase.table("conduta_sugestoes").select("*").eq("caso_id", caso["id"]).limit(1).execute().data
    linha = linhas[0] if linhas else None
    respostas = {
        r["item"]: r
        for r in supabase.table("conduta_sugestao_respostas").select("*").eq("caso_id", caso["id"]).execute().data or []
    }
    itens = []
    if linha and linha.get("sugestao_cifrada"):
        sugestao = json.loads(cifra.decifrar_texto(linha["sugestao_cifrada"]))
        for item, titulo in ITENS.items():
            resposta = respostas.get(item)
            itens.append(
                {
                    "item": item,
                    "titulo": titulo,
                    "rotulo": "Sugestão",
                    "valor": _valor_na_tela(item, sugestao[item]),
                    "justificativa": sugestao[item]["justificativa"],
                    "trecho": sugestao[item].get("trecho") or "",
                    "resposta": resposta["resposta"] if resposta else None,
                    "motivo": cifra.decifrar_texto(resposta["motivo_cifrado"])
                    if resposta and resposta.get("motivo_cifrado")
                    else None,
                }
            )
    motivo = None
    if linha and linha["situacao"] == "manual":
        motivo = f"Sem sugestão do agente: {POR_QUE_SEM_SUGESTAO[linha['motivo_manual']]}."
    return {
        "situacao": linha["situacao"] if linha else "aguardando",
        "motivo": motivo,
        "itens": itens,
        "pode_responder": papel == "coordenacao" and not caso.get("encerrado_em") and bool(itens),
        "possivel_impedimento": possivel_impedimento(relato, _membros_vigentes(supabase, hoje)),
    }


def responder_item(supabase, aberto, *, item: str, resposta: str, motivo: str = "") -> dict:
    """A coordenação confirma ou discorda de um item da sugestão. Discordar
    exige o motivo em uma linha, que fica cifrado. Um item, uma resposta."""
    caso = aberto.caso
    if aberto.pessoa.papel != "coordenacao":
        raise RespostaRecusadaError(403, "Só a coordenação confirma ou discorda da sugestão do agente.")
    if item not in ITENS or resposta not in RESPOSTAS:
        raise RespostaRecusadaError(422, "Item ou resposta inexistente.")
    motivo = (motivo or "").strip()
    if resposta == "discordo" and not motivo:
        raise RespostaRecusadaError(422, "Escreva o motivo da discordância em uma linha.")
    if len(motivo) > _TAMANHO_DO_MOTIVO:
        raise RespostaRecusadaError(422, "O motivo cabe em uma linha.")
    sugerida = (
        supabase.table("conduta_sugestoes")
        .select("caso_id")
        .eq("caso_id", caso["id"])
        .eq("situacao", "sugerida")
        .limit(1)
        .execute()
        .data
    )
    if not sugerida or caso.get("encerrado_em"):
        raise RespostaRecusadaError(409, "Não há sugestão do agente a responder neste caso.")
    ja = supabase.table("conduta_sugestao_respostas").select("id").eq("caso_id", caso["id"]).eq("item", item)
    if ja.execute().data:
        raise RespostaRecusadaError(409, "Este item já foi respondido.")
    if resposta == "confirmo":
        acao, detalhe = "sugestao_confirmada", f"confirmou a sugestão do agente: {ITENS[item]}"
    else:
        acao, detalhe = "sugestao_discordada", f"discordou da sugestão do agente: {ITENS[item]}"
    trilha.registrar(supabase, caso["id"], aberto.autor_id, acao, detalhe)
    supabase.table("conduta_sugestao_respostas").insert(
        {
            "caso_id": caso["id"],
            "item": item,
            "resposta": resposta,
            "motivo_cifrado": cifra.cifrar_texto(motivo) if resposta == "discordo" else None,
            "autor_id": aberto.autor_id,
        }
    ).execute()
    return caso
