"""O relatório de apuração do Canal de Conduta e o envio para voto (issue
#1832; especificação, seções 6.3, 6.4, 8 e 11; ADR 0097, decisões 6 e 7).

Num clique, o agente redige o relatório de uma página (fatos, provas, versão
do acusado e a regra do Código de Conduta envolvida) ou a cronologia dos
fatos. Quem apurou revisa e edita, e cada edição vira versão nova: a anterior
fica (migration 209). No rito Rápido apuram a coordenação e um membro; no
Completo, os apuradores designados, e o relatório vai à ClickSign para eles
assinarem. A cópia assinada volta sozinha para a trilha (`assinaturas`).

"ENVIAR PARA VOTO" fecha a Apuração, e só vale com todos os depoimentos
concluídos, com o relatório e, no Completo, com a última versão assinada.

Nenhum nome vai ao agente (decisão 7): cada nome conhecido do caso (quem foi
ouvido, quem foi citado, quem está no caso) vira um marcador numerado na ida,
o resto passa pela pseudonimização da Ouvidoria (ADR 0034), e o marcador volta
a ser nome dentro do app.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from postgrest.exceptions import APIError

from app.config import settings
from app.services import storage
from app.services.conduta import assinaturas, cifra, codigo, depoimentos, membros, trilha
from app.services.conduta.acesso import hoje_em_sao_paulo
from app.services.conduta.impedimento import citados_para_a_tela, membros_do_caso
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc
from app.services.ia_chaves import ClienteDaAnthropic
from app.services.ouvidoria_pseudonimizacao import pseudonimizar
from app.services.prompt_loader import load_prompt
from app.utils.text_sanitizer import sanitizar_travessao

logger = logging.getLogger(__name__)

TABELA = "conduta_relatorios"

# Uma página A4 em corpo 10,5: umas 450 palavras.
TAMANHO_DA_PAGINA = 3000
TAMANHO_DA_CRONOLOGIA = 6000
_TAMANHO_DO_MATERIAL = 60000

MAX_TOKENS = 4096
TEMPO_LIMITE_S = 90.0


@dataclass(frozen=True)
class Tipo:
    rotulo: str
    prompt: str
    limite: int
    gerou: str
    editou: str


TIPOS = {
    "relatorio": Tipo(
        "relatório de apuração",
        "conduta_relatorio_de_apuracao",
        TAMANHO_DA_PAGINA,
        "gerou_relatorio",
        "editou_relatorio",
    ),
    "cronologia": Tipo(
        "cronologia dos fatos",
        "conduta_cronologia_dos_fatos",
        TAMANHO_DA_CRONOLOGIA,
        "montou_cronologia",
        "editou_cronologia",
    ),
}

FALTA_ASSINATURA = "Falta a assinatura dos apuradores no relatório."
FALTA_RELATORIO = "Gere o relatório antes de enviar para voto."


class RelatorioRecusadoError(Exception):
    """A ação não pode acontecer agora. `status` vai para a resposta, e a
    mensagem diz o motivo numa linha."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


# ── Os marcadores dos nomes ─────────────────────────────────────────────────

_LIGACOES = {"de", "da", "do", "das", "dos", "e"}
_MARCADOR = re.compile(r"\[PESSOA_(\d+)\]")


@dataclass
class Marcadores:
    """Cada nome conhecido do caso e o seu marcador. Uma palavra do nome
    sozinha ("a Marlene") também vira o marcador da pessoa."""

    nomes: dict[str, str] = field(default_factory=dict)
    _padroes: list[tuple[re.Pattern, str]] = field(default_factory=list)

    def marcar(self, texto: str) -> str:
        for padrao, marcador in self._padroes:
            texto = padrao.sub(marcador, texto)
        return pseudonimizar(texto)

    def desmarcar(self, texto: str) -> str:
        return _MARCADOR.sub(lambda m: self.nomes.get(m.group(0), m.group(0)), texto)


def _padrao(trecho: str) -> re.Pattern:
    partes = [re.escape(p) for p in trecho.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(partes) + r"(?!\w)", re.IGNORECASE)


def preparar_marcadores(nomes: list[str]) -> Marcadores:
    marcadores = Marcadores()
    vistos: set[str] = set()
    trechos: list[tuple[str, str]] = []
    palavras: list[tuple[str, str]] = []
    for nome in nomes:
        nome = " ".join((nome or "").split())
        if not nome or nome.casefold() in vistos:
            continue
        vistos.add(nome.casefold())
        marcador = f"[PESSOA_{len(marcadores.nomes) + 1}]"
        marcadores.nomes[marcador] = nome
        trechos.append((nome, marcador))
        palavras += [(p, marcador) for p in nome.split() if len(p) >= 3 and p.casefold() not in _LIGACOES]
    usadas: set[str] = set()
    for palavra, marcador in palavras:
        if palavra.casefold() not in usadas:
            usadas.add(palavra.casefold())
            trechos.append((palavra, marcador))
    trechos.sort(key=lambda t: -len(t[0]))
    marcadores._padroes = [(_padrao(trecho), marcador) for trecho, marcador in trechos]
    return marcadores


def marcar_nomes(texto: str, nomes: list[str]) -> tuple[str, Marcadores]:
    marcadores = preparar_marcadores(nomes)
    return marcadores.marcar(texto), marcadores


def desmarcar(texto: str, marcadores: Marcadores) -> str:
    return marcadores.desmarcar(texto)


# ── Quem faz o quê ──────────────────────────────────────────────────────────


def _apurador(aberto: CasoAberto) -> bool:
    return any(a.get("motivo") == "apurador" and not a.get("revogada_em") for a in aberto.atribuicoes)


def quem_apura(aberto: CasoAberto) -> bool:
    """No Completo, os apuradores designados; no Rápido, a coordenação e o
    membro (especificação, 6.3 e 6.4)."""
    if aberto.caso.get("rito") == "completo":
        return _apurador(aberto)
    return aberto.pessoa.papel in ("coordenacao", "membro")


def envia_para_voto(aberto: CasoAberto) -> bool:
    return quem_apura(aberto) or aberto.pessoa.papel == "coordenacao"


def _exigir_apuracao(caso: dict) -> None:
    if caso.get("etapa") != "apuracao" or caso.get("encerrado_em"):
        raise RelatorioRecusadoError(409, "O relatório é da etapa Apuração.")


def _exigir_quem_apura(aberto: CasoAberto) -> None:
    _exigir_apuracao(aberto.caso)
    if quem_apura(aberto):
        return
    if aberto.caso.get("rito") == "completo":
        raise RelatorioRecusadoError(403, "No rito Completo, só os apuradores redigem o relatório.")
    raise RelatorioRecusadoError(403, "Só a coordenação e o membro que apuram redigem o relatório.")


# ── Leituras ────────────────────────────────────────────────────────────────


def _versoes(supabase, caso_id: str, tipo: str) -> list[dict]:
    linhas = supabase.table(TABELA).select("*").eq("caso_id", caso_id).eq("tipo", tipo).execute().data or []
    return sorted(linhas, key=lambda linha: linha["versao"])


def _assinatura_da_versao(supabase, caso_id: str, relatorio_id: str) -> dict | None:
    linhas = (
        supabase.table(assinaturas.TABELA)
        .select("*")
        .eq("tipo", assinaturas.RELATORIO_DE_APURACAO)
        .eq("caso_id", caso_id)
        .eq("relatorio_id", relatorio_id)
        .execute()
        .data
    ) or []
    vivas = [linha for linha in linhas if linha.get("situacao") != "cancelado"]
    return vivas[-1] if vivas else None


def _documento(supabase, caso: dict, tipo: str) -> dict | None:
    versoes = _versoes(supabase, caso["id"], tipo)
    if not versoes:
        return None
    autores = membros.nomes(supabase, [v["autor_id"] for v in versoes])
    ultima = versoes[-1]
    documento = {
        "texto": cifra.decifrar_texto(ultima["texto_cifrado"]),
        "versao": ultima["versao"],
        "limite": TIPOS[tipo].limite,
        "versoes": [
            {
                "versao": v["versao"],
                "origem": v["origem"],
                "autor": autores.get(v["autor_id"], ""),
                "criado_em": v.get("criado_em"),
                "texto": cifra.decifrar_texto(v["texto_cifrado"]),
            }
            for v in reversed(versoes)
        ],
    }
    if tipo == "relatorio" and caso.get("rito") == "completo":
        assinatura = _assinatura_da_versao(supabase, caso["id"], ultima["id"])
        documento["assinatura"] = (
            {
                "situacao": assinatura["situacao"],
                "erro": assinatura.get("erro"),
                "assinado_em": assinatura.get("assinado_em"),
                "tem_copia": bool(assinatura.get("arquivo_assinado_path")),
            }
            if assinatura
            else None
        )
    return documento


def para_a_tela(supabase, aberto: CasoAberto) -> dict:
    """O relatório e a cronologia do caso, decifrados, com as versões. Levanta
    `CifraIndisponivelError` se a chave não abre."""
    caso = aberto.caso
    return {
        "relatorio": _documento(supabase, caso, "relatorio"),
        "cronologia": _documento(supabase, caso, "cronologia"),
        "pode_redigir_relatorio": caso.get("etapa") == "apuracao" and quem_apura(aberto),
    }


def bloqueio_do_voto(supabase, caso: dict) -> str | None:
    """O motivo de o caso ainda não ir a voto, numa linha, ou None. Na ordem:
    os depoimentos, o relatório e, no Completo, a assinatura dos apuradores."""
    em_aberto = depoimentos.bloqueio_do_avanco(depoimentos.do_caso(supabase, caso["id"]))
    if em_aberto:
        return em_aberto
    versoes = _versoes(supabase, caso["id"], "relatorio")
    if not versoes:
        return FALTA_RELATORIO
    if caso.get("rito") == "completo":
        assinatura = _assinatura_da_versao(supabase, caso["id"], versoes[-1]["id"])
        if not assinatura or assinatura["situacao"] != "assinado":
            return FALTA_ASSINATURA
    return None


def olhar_do_envio(supabase, aberto: CasoAberto) -> dict:
    """O que a caixa "O QUE FAZER AGORA" precisa para mostrar "ENVIAR PARA
    VOTO": se a Apuração chegou ao relatório (já há relatório, ou todos os
    depoimentos estão concluídos), quem pode enviar e o que falta."""
    caso = aberto.caso
    lista = depoimentos.do_caso(supabase, caso["id"])
    tem_relatorio = bool(_versoes(supabase, caso["id"], "relatorio"))
    fase = tem_relatorio or (bool(lista) and all(d.get("concluido_em") for d in lista))
    if not fase:
        return {}
    return {
        "fase_do_relatorio": True,
        "envia_para_voto": envia_para_voto(aberto),
        "bloqueio_do_voto": bloqueio_do_voto(supabase, caso),
    }


# ── O agente ────────────────────────────────────────────────────────────────


def _nomes_do_caso(supabase, caso: dict, material: list[dict]) -> list[str]:
    """Todo nome que o app conhece no caso: quem foi ouvido, primeiro, depois
    quem foi citado e quem está no caso (Comitê, apuradores, convidados)."""
    nomes = [m["nome"] for m in material]
    nomes += [c["nome"] for c in citados_para_a_tela(supabase, caso["id"]) if c.get("nome")]
    atribuicoes = supabase.table("conduta_atribuicoes").select("participante_id").eq("caso_id", caso["id"]).execute()
    ids = set(membros_do_caso(supabase, caso)) | {a["participante_id"] for a in atribuicoes.data or []}
    nomes += [nome for nome in membros.nomes(supabase, sorted(ids)).values() if nome]
    return nomes


def _texto_do_codigo(supabase) -> str | None:
    """O Código de Conduta vigente, em texto, se der para ler. Sem ele o
    agente escreve que a regra fica a indicar."""
    from app.services.transcricao_extractor import extrair_texto

    try:
        vigente = codigo.pdf_vigente_em(supabase, hoje_em_sao_paulo())
        if vigente is None:
            return None
        return extrair_texto("codigo.pdf", vigente[1])[0][:_TAMANHO_DO_MATERIAL]
    except Exception as exc:  # noqa: BLE001 (o relatório sai sem o Código)
        logger.warning("Código de Conduta fora do relatório de apuração (%s)", type(exc).__name__)
        return None


def _atributo(valor: str) -> str:
    return valor.replace('"', "'")


def montar_mensagem(supabase, caso: dict) -> tuple[str, Marcadores]:
    """O texto que vai ao agente, já sem nomes, e os marcadores para a volta."""
    material = depoimentos.material_da_apuracao(supabase, caso["id"])
    marcadores = preparar_marcadores(_nomes_do_caso(supabase, caso, material))
    partes = [f"<relato>\n{marcadores.marcar(cifra.decifrar_texto(caso['relato_cifrado']))}\n</relato>"]
    for numero, item in enumerate(material, 1):
        pessoa = marcadores.marcar(item["nome"])
        cargo = _atributo(marcadores.marcar(item["cargo"]))
        partes.append(
            f'<depoimento numero="{numero}" papel="{item["papel"]}" pessoa="{pessoa}" cargo="{cargo}">\n'
            f"{marcadores.marcar(item['texto'])[:_TAMANHO_DO_MATERIAL]}\n</depoimento>"
        )
    texto_do_codigo = _texto_do_codigo(supabase)
    if texto_do_codigo:
        partes.append(f"<codigo_de_conduta>\n{marcadores.marcar(texto_do_codigo)}\n</codigo_de_conduta>")
    return "\n\n".join(partes), marcadores


def _cliente_do_agente_da_apuracao() -> ClienteDaAnthropic:
    return ClienteDaAnthropic(max_retries=0, timeout=TEMPO_LIMITE_S)


def _pedir_ao_agente_da_apuracao(cliente, sistema: str, mensagens: list[dict]) -> str | None:
    """Uma chamada ao modelo. None quando ele recusa ou corta no teto."""
    resposta = cliente.messages.create(
        model=settings.conduta_agente_modelo, max_tokens=MAX_TOKENS, system=sistema, messages=mensagens
    )
    if resposta.stop_reason in ("refusal", "max_tokens"):
        return None
    return "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()


def _texto_do_agente_da_apuracao(tipo: str, mensagem: str, marcadores: Marcadores) -> str:
    """O texto do agente, com os nomes de volta, que cabe no limite do tipo. O
    que passa é pedido de novo uma vez, mais curto."""
    regra = TIPOS[tipo]
    if not settings.anthropic_api_key:
        raise RelatorioRecusadoError(503, "O agente está fora do ar agora. Tente de novo em instantes.")
    cliente = _cliente_do_agente_da_apuracao()
    sistema = load_prompt(regra.prompt)
    mensagens = [{"role": "user", "content": mensagem}]
    for _ in range(2):
        try:
            bruto = _pedir_ao_agente_da_apuracao(cliente, sistema, list(mensagens))
        except Exception as exc:  # noqa: BLE001 (o erro da API vira a recusa da tela)
            logger.warning("[Conduta] Agente da apuração não respondeu (%s)", type(exc).__name__)
            raise RelatorioRecusadoError(503, "O agente não respondeu. Tente de novo em instantes.") from exc
        if not bruto:
            raise RelatorioRecusadoError(502, "O agente não devolveu o texto. Gere de novo.")
        texto = sanitizar_travessao(marcadores.desmarcar(bruto)).strip()
        if len(texto) <= regra.limite:
            return texto
        mensagens = [
            *mensagens,
            {"role": "assistant", "content": bruto},
            {
                "role": "user",
                "content": f"O texto passou de uma página. Reescreva com no máximo {regra.limite} caracteres, "
                "mantendo as mesmas partes.",
            },
        ]
    raise RelatorioRecusadoError(502, "O agente devolveu um texto maior que uma página. Gere de novo.")


def _gravar_versao(supabase, aberto: CasoAberto, tipo: str, texto: str, origem: str) -> dict:
    regra = TIPOS[tipo]
    caso_id = aberto.caso["id"]
    versao = max((v["versao"] for v in _versoes(supabase, caso_id, tipo)), default=0) + 1
    cifrado = cifra.cifrar_texto(texto)
    acao = regra.gerou if origem == "agente" else regra.editou
    detalhe = f"{regra.rotulo}, versão {versao}" + (", pelo agente" if origem == "agente" else "")
    trilha.registrar(supabase, caso_id, aberto.autor_id, acao, detalhe)
    try:
        return (
            supabase.table(TABELA)
            .insert(
                {
                    "caso_id": caso_id,
                    "tipo": tipo,
                    "versao": versao,
                    "texto_cifrado": cifrado,
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
            raise RelatorioRecusadoError(409, "O relatório mudou enquanto você agia. Abra de novo.") from erro
        raise


def redigir_documento_da_apuracao(supabase, aberto: CasoAberto, tipo: str) -> dict:
    """O botão GERAR RELATÓRIO (ou MONTAR CRONOLOGIA): o agente redige, e o
    texto entra como versão nova. Roda no executor da IA."""
    _exigir_quem_apura(aberto)
    mensagem, marcadores = montar_mensagem(supabase, aberto.caso)
    texto = _texto_do_agente_da_apuracao(tipo, mensagem, marcadores)
    return _gravar_versao(supabase, aberto, tipo, texto, "agente")


# ── Ações ───────────────────────────────────────────────────────────────────


def editar(supabase, aberto: CasoAberto, tipo: str, texto: str) -> dict:
    """A edição de quem apurou, que vira versão nova. A anterior fica."""
    _exigir_quem_apura(aberto)
    texto = sanitizar_travessao((texto or "").strip())
    if not texto:
        raise RelatorioRecusadoError(422, "O texto não pode ficar em branco.")
    if len(texto) > TIPOS[tipo].limite:
        raise RelatorioRecusadoError(422, f"O texto cabe em uma página: até {TIPOS[tipo].limite} caracteres.")
    return _gravar_versao(supabase, aberto, tipo, texto, "edicao")


def _apuradores(supabase, caso_id: str) -> list[dict]:
    linhas = (
        supabase.table("conduta_atribuicoes")
        .select("*")
        .eq("caso_id", caso_id)
        .eq("motivo", "apurador")
        .is_("revogada_em", "null")
        .execute()
        .data
    ) or []
    ids = [a["participante_id"] for a in linhas if a.get("termo_assinado_em")]
    if not ids:
        return []
    pessoas = (supabase.table("participantes").select("id, nome_completo, email").in_("id", ids).execute().data) or []
    por_id = {p["id"]: p for p in pessoas}
    return [por_id[i] for i in ids if i in por_id]


def enviar_para_assinatura(supabase, aberto: CasoAberto) -> dict:
    """No rito Completo, a última versão vai à ClickSign para os apuradores."""
    caso = aberto.caso
    _exigir_apuracao(caso)
    if caso.get("rito") != "completo":
        raise RelatorioRecusadoError(409, "No rito Rápido o relatório não vai à assinatura.")
    if not envia_para_voto(aberto):
        raise RelatorioRecusadoError(403, "Só os apuradores e a coordenação enviam o relatório para assinatura.")
    versoes = _versoes(supabase, caso["id"], "relatorio")
    if not versoes:
        raise RelatorioRecusadoError(409, "Gere o relatório antes de enviar para assinatura.")
    pessoas = _apuradores(supabase, caso["id"])
    if not pessoas:
        raise RelatorioRecusadoError(409, "O caso ainda não tem apurador com o termo assinado.")
    if not all(p.get("email") for p in pessoas):
        raise RelatorioRecusadoError(
            409, "Um apurador não tem e-mail profissional no cadastro, e o relatório vai por e-mail para assinatura."
        )
    ultima = versoes[-1]
    texto = cifra.decifrar_texto(ultima["texto_cifrado"])
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "enviou_relatorio_para_assinatura",
        f"relatório de apuração, versão {ultima['versao']}, aos apuradores",
    )
    return assinaturas.enviar_relatorio_de_apuracao(supabase, caso["id"], ultima, texto, pessoas)


def _assinada(supabase, caso_id: str) -> dict:
    linhas = (
        supabase.table(assinaturas.TABELA)
        .select("*")
        .eq("tipo", assinaturas.RELATORIO_DE_APURACAO)
        .eq("caso_id", caso_id)
        .eq("situacao", "assinado")
        .execute()
        .data
    ) or []
    com_copia = [linha for linha in linhas if linha.get("arquivo_assinado_path")]
    if not com_copia:
        raise RelatorioRecusadoError(404, "O relatório assinado ainda não voltou.")
    return com_copia[-1]


def abrir_assinado(supabase, aberto: CasoAberto) -> bytes:
    """A cópia do PDF assinado, decifrada, depois de gravada a abertura."""
    assinatura = _assinada(supabase, aberto.caso["id"])
    trilha.registrar(supabase, aberto.caso["id"], aberto.autor_id, "abriu_arquivo", "abriu o relatório assinado")
    cifrado = storage.download_file(supabase, assinaturas.BUCKET, assinatura["arquivo_assinado_path"])
    if cifrado is None:
        raise RelatorioRecusadoError(503, "O arquivo não pôde ser aberto agora. Tente de novo.")
    return cifra.decifrar_arquivo(cifrado)


def assinatura_aberta(supabase, aberto: CasoAberto) -> dict:
    """O envio à ClickSign que espera assinatura, para o "Reconsultar status"."""
    linhas = (
        supabase.table(assinaturas.TABELA)
        .select("*")
        .eq("tipo", assinaturas.RELATORIO_DE_APURACAO)
        .eq("caso_id", aberto.caso["id"])
        .eq("situacao", "enviado")
        .execute()
        .data
    ) or []
    if not linhas:
        raise RelatorioRecusadoError(404, "Não há relatório esperando assinatura.")
    return linhas[-1]


def enviar_para_voto(supabase, aberto: CasoAberto) -> dict:
    """O botão ENVIAR PARA VOTO: fecha a Apuração. O banco tem a mesma trava
    dos depoimentos (migration 193) e do relatório (migration 209)."""
    caso = aberto.caso
    _exigir_apuracao(caso)
    if not envia_para_voto(aberto):
        raise RelatorioRecusadoError(403, "Só quem apurou ou a coordenação envia para voto.")
    bloqueio = bloqueio_do_voto(supabase, caso)
    if bloqueio:
        raise RelatorioRecusadoError(409, bloqueio)
    versao = _versoes(supabase, caso["id"], "relatorio")[-1]["versao"]
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "enviou_para_voto", f"relatório de apuração, versão {versao}"
    )
    linhas = (
        supabase.table("conduta_casos")
        .update({"etapa": "voto"})
        .eq("id", caso["id"])
        .eq("etapa", "apuracao")
        .execute()
        .data
    ) or []
    if not linhas:
        raise RelatorioRecusadoError(409, "O caso mudou enquanto você agia. Abra de novo.")
    return linhas[0]
