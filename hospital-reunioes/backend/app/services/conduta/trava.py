"""A trava de robustez do Canal de Conduta (issue #1833; especificação, seções
6.7 e 11; ADR 0097, decisões 6 e 7).

Sete itens. Num clique, o agente preenche a lista: para cada item, se o
material do caso mostra que ele está atendido e onde. Quem confirma cada item
é um membro votante do caso. A defesa do acusado sem depoimento concluído é a
recusa certificada, e pede a confirmação de dois membros. A ciência prévia do
Código é o documento que o DP registra fora do aplicativo e que um membro
anexa ao caso: sem ele, o item não se confirma.

Com item em aberto, a votação não conclui como procedente nem como
parcialmente procedente (`voto.concluir_votacao`), e o banco tem a mesma
trava (migration 216).

O agente nunca recebe o conteúdo de um voto, só quantos já votaram, e nenhum
nome vai a ele: os nomes do caso viram marcadores na ida (`relatorio`).
"""

from __future__ import annotations

import json
import logging
import uuid

from postgrest.exceptions import APIError

from app.config import settings
from app.services import storage
from app.services.conduta import ata, cifra, depoimentos, membros, relatorio, trilha
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc
from app.services.ia_chaves import ClienteDaAnthropic
from app.services.prompt_loader import load_prompt
from app.utils.text_sanitizer import sanitizar_travessao

logger = logging.getLogger(__name__)

PREENCHIMENTOS = "conduta_trava_preenchimentos"
CONFIRMACOES = "conduta_trava_confirmacoes"
CIENCIAS = "conduta_ciencias_do_codigo"
BUCKET = depoimentos.BUCKET

# A lista da especificação (6.7), na ordem da tela. O último item só se
# confirma com os três votos e a ata assinada (issue #1834).
ITENS = (
    ("fato", "Fato descrito, com data e local"),
    ("prova", "Prova além do relato (relato anônimo sozinho não sustenta punição)"),
    ("defesa", "Defesa do acusado registrada, ou recusa certificada por dois membros"),
    ("regra", "Regra violada indicada (item do Código de Conduta)"),
    ("ciencia", "Ciência prévia do Código pelo acusado"),
    ("medida", "Medida recomendada conforme a Matriz e o histórico da pessoa"),
    ("votos", "Votos registrados e ata assinada"),
)
ROTULOS = dict(ITENS)
CERTIFICACOES_DA_RECUSA = 2
TAMANHO_DO_TEXTO = 400

_MB = 1024 * 1024
CONTENT_TYPES_DA_CIENCIA = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
LIMITE_DA_CIENCIA = 30 * _MB

MAX_TOKENS = 2048
TEMPO_LIMITE_S = 90.0


class TravaRecusadaError(Exception):
    """A ação não pode acontecer agora. `status` vai para a resposta, e a
    mensagem diz o motivo numa linha."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ── Leituras ────────────────────────────────────────────────────────────────


def _linhas(supabase, tabela: str, caso_id: str) -> list[dict]:
    return supabase.table(tabela).select("*").eq("caso_id", caso_id).execute().data or []


def _ciencias(supabase, caso_id: str) -> list[dict]:
    return sorted(_linhas(supabase, CIENCIAS, caso_id), key=lambda c: c["versao"])


def _acusado_ouvido(supabase, caso_id: str) -> bool:
    return any(d.get("papel") == "acusado" and d.get("concluido_em") for d in depoimentos.do_caso(supabase, caso_id))


def _confirmacoes_precisas(item: str, acusado_ouvido: bool) -> int:
    return CERTIFICACOES_DA_RECUSA if item == "defesa" and not acusado_ouvido else 1


def _situacao_dos_itens(supabase, caso: dict, situacao_do_voto) -> tuple[dict[str, list[dict]], bool]:
    """As confirmações que contam, por item: as de quem vota no caso hoje. A
    de quem depois ficou impedido ou virou Citado sai da conta, como o voto
    dele (`voto._da_rodada`). A do item dos votos só conta com a ata dos
    votos de hoje assinada: a ata de votos que não valem mais não confirma."""
    por_item: dict[str, list[dict]] = {item: [] for item, _ in ITENS}
    com_ata = ata.ata_assinada(supabase, caso, situacao_do_voto)
    for linha in sorted(_linhas(supabase, CONFIRMACOES, caso["id"]), key=lambda c: str(c.get("confirmado_em") or "")):
        if linha["item"] == "votos" and not com_ata:
            continue
        if linha["participante_id"] in situacao_do_voto.votantes:
            por_item.setdefault(linha["item"], []).append(linha)
    return por_item, _acusado_ouvido(supabase, caso["id"])


def bloqueio(supabase, caso: dict, situacao_do_voto) -> str | None:
    """O primeiro item em aberto, numa linha, ou None com a trava inteira."""
    por_item, acusado_ouvido = _situacao_dos_itens(supabase, caso, situacao_do_voto)
    for item, rotulo in ITENS:
        if len(por_item[item]) < _confirmacoes_precisas(item, acusado_ouvido):
            return f"A trava de robustez tem item em aberto: {rotulo}."
    return None


def _requisito(supabase, caso: dict, item: str, situacao_do_voto) -> str | None:
    """O que falta no caso para o item poder ser confirmado."""
    if item == "ciencia" and not _ciencias(supabase, caso["id"]):
        return "Anexe a ciência do Código registrada pelo DP antes de confirmar."
    if item == "votos" and not situacao_do_voto.fechada:
        return "Faltam votos: o item se confirma depois que os três votarem."
    if item == "votos" and not ata.ata_assinada(supabase, caso, situacao_do_voto):
        return "Falta a ata assinada pelos três: o item se confirma depois da assinatura."
    return None


def _ultimo_preenchimento(supabase, caso_id: str) -> dict | None:
    linhas = sorted(_linhas(supabase, PREENCHIMENTOS, caso_id), key=lambda p: p["versao"])
    return linhas[-1] if linhas else None


def para_a_tela(supabase, aberto: CasoAberto, situacao_do_voto) -> dict:
    caso = aberto.caso
    por_item, acusado_ouvido = _situacao_dos_itens(supabase, caso, situacao_do_voto)
    ultimo = _ultimo_preenchimento(supabase, caso["id"])
    preenchidos = {i["item"]: i for i in json.loads(cifra.decifrar_texto(ultimo["itens_cifrado"]))} if ultimo else {}
    ids = {c["participante_id"] for linhas in por_item.values() for c in linhas}
    ciencias = _ciencias(supabase, caso["id"])
    nomes = membros.nomes(supabase, sorted(ids | {c["enviado_por"] for c in ciencias}))
    vota = aberto.autor_id in situacao_do_voto.votantes
    em_voto = caso.get("etapa") == "voto" and not caso.get("resultado")
    itens = []
    for item, rotulo in ITENS:
        linhas = por_item[item]
        precisas = _confirmacoes_precisas(item, acusado_ouvido)
        bloqueio_do_item = None
        if not vota:
            bloqueio_do_item = "Só os membros votantes confirmam a trava."
        elif any(c["participante_id"] == aberto.autor_id for c in linhas):
            bloqueio_do_item = "Você já confirmou este item."
        else:
            bloqueio_do_item = _requisito(supabase, caso, item, situacao_do_voto)
        sugestao = preenchidos.get(item)
        itens.append(
            {
                "item": item,
                "rotulo": rotulo,
                "preenchimento": {"atendido": sugestao["atendido"], "texto": sugestao["texto"]} if sugestao else None,
                "confirmacoes": [nomes.get(c["participante_id"], "") for c in linhas],
                "confirmacoes_precisas": precisas,
                "confirmado": len(linhas) >= precisas,
                "pode_confirmar": em_voto and bloqueio_do_item is None and len(linhas) < precisas,
                "bloqueio": bloqueio_do_item if em_voto else None,
            }
        )
    return {
        "itens": itens,
        "preenchida_em": ultimo["criado_em"] if ultimo else None,
        "pode_preencher": em_voto and vota,
        "ciencia": [
            {"versao": c["versao"], "enviado_em": c["enviado_em"], "enviado_por": nomes.get(c["enviado_por"], "")}
            for c in reversed(ciencias)
        ],
    }


# ── Ações dos membros ───────────────────────────────────────────────────────


def _exigir_votante(supabase, aberto: CasoAberto):
    from app.services.conduta import voto

    caso = aberto.caso
    if caso.get("etapa") != "voto" or caso.get("encerrado_em") or caso.get("resultado"):
        raise TravaRecusadaError(409, "A trava de robustez é da etapa Voto.")
    atual = voto.situacao_em_dia(supabase, caso)
    if aberto.autor_id not in atual.votantes:
        raise TravaRecusadaError(403, "Só os membros votantes cuidam da trava.")
    return atual


def confirmar(supabase, aberto: CasoAberto, item: str) -> dict:
    """A confirmação do membro num item da trava. Não se desfaz."""
    if item not in ROTULOS:
        raise TravaRecusadaError(422, "Item da trava inexistente.")
    atual = _exigir_votante(supabase, aberto)
    caso = aberto.caso
    falta = _requisito(supabase, caso, item, atual)
    if falta:
        raise TravaRecusadaError(409, falta)
    por_item, acusado_ouvido = _situacao_dos_itens(supabase, caso, atual)
    if any(c["participante_id"] == aberto.autor_id for c in por_item[item]):
        raise TravaRecusadaError(409, "Você já confirmou este item.")
    if len(por_item[item]) >= _confirmacoes_precisas(item, acusado_ouvido):
        raise TravaRecusadaError(409, "Este item já está confirmado.")
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "confirmou_item_da_trava", ROTULOS[item])
    try:
        return (
            supabase.table(CONFIRMACOES)
            .insert(
                {
                    "caso_id": caso["id"],
                    "item": item,
                    "participante_id": aberto.autor_id,
                    "confirmado_em": agora_utc().isoformat(),
                }
            )
            .execute()
            .data[0]
        )
    except APIError as erro:
        if getattr(erro, "code", None) == "23505":
            raise TravaRecusadaError(409, "Você já confirmou este item.") from erro
        raise


def conferir_ciencia(nome: str, tamanho: int) -> str:
    """O content-type pela extensão (nunca pelo que o navegador declarou)."""
    nome = (nome or "").strip()
    extensao = nome[nome.rfind(".") :].lower() if "." in nome else ""
    if extensao not in CONTENT_TYPES_DA_CIENCIA:
        raise TravaRecusadaError(422, "Envie a ciência do Código em PDF ou foto (JPG, PNG, WEBP ou HEIC).")
    if tamanho <= 0:
        raise TravaRecusadaError(422, "O arquivo está vazio.")
    if tamanho > LIMITE_DA_CIENCIA:
        raise TravaRecusadaError(413, f"O arquivo passa de {LIMITE_DA_CIENCIA // _MB} MB.")
    return CONTENT_TYPES_DA_CIENCIA[extensao]


def anexar_ciencia(supabase, aberto: CasoAberto, nome: str, conteudo: bytes) -> dict:
    """A ciência do Código registrada pelo DP, cifrada no bucket do Canal. Uma
    versão nova não apaga a anterior."""
    _exigir_votante(supabase, aberto)
    caso = aberto.caso
    content_type = conferir_ciencia(nome, len(conteudo))
    cifrado = cifra.cifrar_arquivo(conteudo)
    versao = max((c["versao"] for c in _ciencias(supabase, caso["id"])), default=0) + 1
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "anexou_arquivo", f"anexou a ciência do Código, versão {versao}"
    )
    caminho = f"ciencias/{uuid.uuid4().hex}"
    if not storage.upload_private(supabase, BUCKET, caminho, cifrado):
        raise TravaRecusadaError(503, "O arquivo não foi guardado. Tente de novo.")
    try:
        supabase.table(CIENCIAS).insert(
            {
                "caso_id": caso["id"],
                "versao": versao,
                "storage_path": caminho,
                "content_type": content_type,
                "tamanho_bytes": len(conteudo),
                "enviado_por": aberto.autor_id,
                "enviado_em": agora_utc().isoformat(),
            }
        ).execute()
    except APIError:
        if not storage.delete_file(supabase, BUCKET, caminho):
            logger.error("Ciência do Código órfã no bucket do Canal: %s", caminho)
        raise
    return {"versao": versao}


def abrir_ciencia(supabase, aberto: CasoAberto) -> tuple[bytes, str]:
    """A última versão da ciência, decifrada, depois de gravada a abertura."""
    ciencias = _ciencias(supabase, aberto.caso["id"])
    if not ciencias:
        raise TravaRecusadaError(404, "A ciência do Código ainda não foi anexada.")
    ultima = ciencias[-1]
    trilha.registrar(
        supabase,
        aberto.caso["id"],
        aberto.autor_id,
        "abriu_arquivo",
        f"abriu a ciência do Código, versão {ultima['versao']}",
    )
    cifrado = storage.download_file(supabase, BUCKET, ultima["storage_path"])
    if cifrado is None:
        raise TravaRecusadaError(503, "O arquivo não pôde ser aberto agora. Tente de novo.")
    return cifra.decifrar_arquivo(cifrado), ultima["content_type"]


# ── O agente ────────────────────────────────────────────────────────────────


def montar_mensagem_da_trava(supabase, caso: dict, situacao_do_voto) -> tuple[str, relatorio.Marcadores]:
    """O material do caso, sem nomes, e os fatos que o agente não lê no texto.
    Do voto vai só a contagem."""
    texto, marcadores = relatorio.montar_mensagem_da_apuracao(supabase, caso)
    partes = [texto]
    versoes = relatorio._versoes(supabase, caso["id"], "relatorio")
    if versoes:
        partes.append(
            "<relatorio_de_apuracao>\n"
            f"{marcadores.marcar(cifra.decifrar_texto(versoes[-1]['texto_cifrado']))}\n"
            "</relatorio_de_apuracao>"
        )
    votaram = len(situacao_do_voto.da_rodada(situacao_do_voto.rodada))
    partes.append(
        "<fatos_do_caso>\n"
        f"Ciência do Código pelo acusado anexada: {'sim' if _ciencias(supabase, caso['id']) else 'não'}.\n"
        f"Depoimento do acusado concluído: {'sim' if _acusado_ouvido(supabase, caso['id']) else 'não'}.\n"
        f"Votos registrados: {votaram} de {len(situacao_do_voto.votantes)}.\n"
        f"Ata assinada pelos três: {'sim' if ata.ata_assinada(supabase, caso, situacao_do_voto) else 'não'}.\n"
        "</fatos_do_caso>"
    )
    return "\n\n".join(partes), marcadores


def _cliente_do_agente_da_trava() -> ClienteDaAnthropic:
    return ClienteDaAnthropic(max_retries=0, timeout=TEMPO_LIMITE_S)


def _pedir_ao_agente_da_trava(cliente, sistema: str, mensagem: str) -> str | None:
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


def _itens_do_agente_da_trava(bruto: str, marcadores: relatorio.Marcadores) -> list[dict]:
    """Os sete itens, na ordem da lista, com os nomes de volta. Item que falta
    ou vem torto derruba a resposta inteira."""
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    objeto = json.loads(bruto[inicio : fim + 1] if 0 <= inicio < fim else bruto)
    por_item = {i.get("item"): i for i in objeto["itens"] if isinstance(i, dict)}
    itens = []
    for item, _ in ITENS:
        dado = por_item[item]
        texto = sanitizar_travessao(marcadores.desmarcar(str(dado["texto"]))).strip()[:TAMANHO_DO_TEXTO]
        itens.append({"item": item, "atendido": dado["atendido"] is True, "texto": texto})
    return itens


def preencher_trava_de_robustez(supabase, aberto: CasoAberto) -> dict:
    """O botão PREENCHER TRAVA: o agente preenche a lista, e o preenchimento
    entra como versão nova. Roda no executor da IA."""
    atual = _exigir_votante(supabase, aberto)
    if not settings.anthropic_api_key:
        raise TravaRecusadaError(503, "O agente está fora do ar agora. Tente de novo em instantes.")
    caso = aberto.caso
    mensagem, marcadores = montar_mensagem_da_trava(supabase, caso, atual)
    try:
        bruto = _pedir_ao_agente_da_trava(
            _cliente_do_agente_da_trava(), load_prompt("conduta_trava_de_robustez"), mensagem
        )
    except Exception as exc:  # noqa: BLE001 (o erro da API vira a recusa da tela)
        logger.warning("[Conduta] Agente da trava não respondeu (%s)", type(exc).__name__)
        raise TravaRecusadaError(503, "O agente não respondeu. Tente de novo em instantes.") from exc
    try:
        itens = _itens_do_agente_da_trava(bruto or "", marcadores)
    except (ValueError, KeyError, TypeError) as exc:
        raise TravaRecusadaError(502, "O agente não devolveu a lista. Preencha de novo.") from exc
    ultimo = _ultimo_preenchimento(supabase, caso["id"])
    versao = (ultimo["versao"] if ultimo else 0) + 1
    cifrado = cifra.cifrar_texto(json.dumps(itens, ensure_ascii=False))
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "preencheu_trava", f"pelo agente, versão {versao}")
    try:
        return (
            supabase.table(PREENCHIMENTOS)
            .insert(
                {
                    "caso_id": caso["id"],
                    "versao": versao,
                    "itens_cifrado": cifrado,
                    "autor_id": aberto.autor_id,
                    "criado_em": agora_utc().isoformat(),
                }
            )
            .execute()
            .data[0]
        )
    except APIError as erro:
        if getattr(erro, "code", None) == "23505":
            raise TravaRecusadaError(409, "A trava mudou enquanto você agia. Abra de novo.") from erro
        raise
