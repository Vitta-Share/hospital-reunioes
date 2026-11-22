"""O papel original, a guarda, o congelamento e a eliminação do caso do Canal
de Conduta (issue #1838; especificação, seções 9.3 e 9.4 e Anexo E.2; ADR
0097).

Encerrado o caso, a etapa "ARQUIVAR PAPEL" lista os originais assinados à
caneta que vão para o envelope do caso, imprime a etiqueta (folha A4 do
Anexo E.2, sem nome de pessoa, setor nem assunto) e registra quem lacrou, o
dia e o local de guarda, que vem preenchido das Configurações.

A guarda vai até cinco anos depois do encerramento; um ano, no caso
encaminhado. Vencida, o job diário (`rodada`) elimina o conteúdo do caso:
os arquivos saem do bucket e o banco apaga o resto pela função da migration
226, que confere o prazo de novo e recusa o caso congelado. A eliminação
entra na trilha, que nunca se apaga. Depois, a coordenação recebe o aviso do
vencimento da guarda do papel, sem nada do caso no e-mail.

"Congelar caso" é da coordenação, para caso com processo judicial ou
administrativo: congelado, o caso não é eliminado nem avisado. Nada aqui
chama IA.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.config import settings
from app.services import storage
from app.services.conduta import configuracoes, depoimentos, membros, trilha, trilha_do_caso
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import agora_utc
from app.services.conduta.triagem import AcaoRecusadaError
from app.services.email_service import _enviar_email, jinja_env

logger = logging.getLogger(__name__)

ANOS_DA_GUARDA = 5
ANOS_DO_ENCAMINHADO = 1
BUCKET = depoimentos.BUCKET
MODELO_DA_ETIQUETA = "conduta_etiqueta_do_envelope.html"
CHAVE_DO_LOCAL = "local_guarda_envelopes"
FUNCAO_DE_ELIMINACAO = "conduta_eliminar_conteudo_do_caso"
FRASE_DO_AVISO = "Venceu a guarda de um envelope do Canal de Conduta."
RITOS = {"rapido": "Rápido", "completo": "Completo", "especial": "Especial", "encaminhamento": "Encaminhamento"}
ELIMINADO = "O conteúdo deste caso foi eliminado ao fim da guarda."
CAMPOS = (
    "id, protocolo, rito, rota, desfecho, recebido_em, encerrado_em, papel_lacrado_em, papel_lacrado_por, "
    "papel_local, congelado_em, congelado_por, eliminado_em, guarda_avisada_em"
)
_SAO_PAULO = ZoneInfo("America/Sao_Paulo")


# ── O prazo ─────────────────────────────────────────────────────────────────


def _dia(valor: Any) -> date:
    """O dia em São Paulo de um instante gravado pelo banco."""
    return datetime.fromisoformat(str(valor)).astimezone(_SAO_PAULO).date()


def _mais_anos(dia: date, anos: int) -> date:
    try:
        return dia.replace(year=dia.year + anos)
    except ValueError:  # 29 de fevereiro: o banco também cai no 28
        return dia.replace(year=dia.year + anos, day=28)


def guardar_ate(caso: dict) -> date | None:
    """O último dia da guarda: cinco anos do encerramento; um ano para o
    encaminhado. A mesma conta da função da migration 226."""
    if not caso.get("encerrado_em"):
        return None
    anos = ANOS_DO_ENCAMINHADO if caso.get("desfecho") == "encaminhado" else ANOS_DA_GUARDA
    return _mais_anos(_dia(caso["encerrado_em"]), anos)


def vencida(caso: dict, hoje: date) -> bool:
    ate = guardar_ate(caso)
    return ate is not None and hoje > ate


# ── O papel ─────────────────────────────────────────────────────────────────


def originais(supabase, caso: dict) -> list[dict]:
    """Os originais assinados à caneta que o rito exige: as gavetas que se
    enchem por upload (o termo de declaração de cada pessoa ouvida e a
    ciência do Código). Sem nome de pessoa."""
    return [
        {"rotulo": gaveta["rotulo"], "situacao": gaveta["situacao"]}
        for gaveta in trilha_do_caso.gavetas(supabase, caso)
        if gaveta["origem"] == trilha_do_caso.UPLOAD
    ]


def conteudo_do_envelope(lista: list[dict]) -> list[dict]:
    """O que está dentro, por tipo e quantidade ("Termo de declaração: 3"):
    o tipo sem a pessoa ouvida."""
    contagem = Counter(item["rotulo"].split(",")[0] for item in lista if item["situacao"] == trilha_do_caso.ASSINADO)
    return [{"tipo": tipo, "quantidade": quantidade} for tipo, quantidade in contagem.items()]


def local_padrao(supabase) -> str | None:
    versoes = configuracoes._todas_as_versoes(supabase, [CHAVE_DO_LOCAL])[CHAVE_DO_LOCAL]
    return versoes[0]["texto"] if versoes else None


def _do_comite_no_caso(aberto: CasoAberto) -> bool:
    return trilha_do_caso.pode_baixar_dossie(aberto)


def para_a_tela(supabase, aberto: CasoAberto, hoje: date) -> dict:
    caso = aberto.caso
    eliminado = bool(caso.get("eliminado_em"))
    coordena = aberto.pessoa.papel == "coordenacao"
    lacre = None
    if caso.get("papel_lacrado_em"):
        lacre = {
            "por": membros.nomes(supabase, [caso["papel_lacrado_por"]]).get(caso["papel_lacrado_por"], ""),
            "em": caso["papel_lacrado_em"],
            "local": caso["papel_local"],
        }
    ate = guardar_ate(caso)
    return {
        "guarda": {
            "encerrado": bool(caso.get("encerrado_em")),
            "guardar_ate": ate.isoformat() if ate else None,
            "vencida": vencida(caso, hoje),
            "originais": [] if eliminado or not caso.get("encerrado_em") else originais(supabase, caso),
            "lacre": lacre,
            "local_padrao": local_padrao(supabase),
            "pode_lacrar": bool(caso.get("encerrado_em"))
            and not eliminado
            and not lacre
            and _do_comite_no_caso(aberto),
            "pode_imprimir": bool(caso.get("encerrado_em")) and not eliminado and _do_comite_no_caso(aberto),
            "congelado_em": caso.get("congelado_em"),
            "pode_congelar": coordena and not eliminado,
            "eliminado_em": caso.get("eliminado_em"),
        }
    }


def _recusar_se_nao_pode_lacrar(aberto: CasoAberto) -> None:
    caso = aberto.caso
    if not _do_comite_no_caso(aberto):
        raise AcaoRecusadaError(403, "Só o Comitê no caso arquiva o papel.")
    if not caso.get("encerrado_em"):
        raise AcaoRecusadaError(409, "O papel é arquivado depois do encerramento do caso.")
    if caso.get("eliminado_em"):
        raise AcaoRecusadaError(409, ELIMINADO)


def registrar_lacre(supabase, aberto: CasoAberto, *, dia: date, local: str, hoje: date) -> dict:
    """Quem lacrou (a pessoa logada), o dia e o local de guarda. Uma vez só."""
    _recusar_se_nao_pode_lacrar(aberto)
    caso = aberto.caso
    if caso.get("papel_lacrado_em"):
        raise AcaoRecusadaError(409, "O lacre deste envelope já foi registrado.")
    local = local.strip()
    if not local:
        raise AcaoRecusadaError(422, "Diga onde o envelope fica guardado.")
    if dia > hoje:
        raise AcaoRecusadaError(422, "A data do lacre não pode ser futura.")
    campos = {"papel_lacrado_em": dia.isoformat(), "papel_lacrado_por": aberto.autor_id, "papel_local": local}
    trilha.registrar(
        supabase,
        caso["id"],
        aberto.autor_id,
        "lacrou_o_papel",
        f"envelope dos originais lacrado em {dia.strftime('%d/%m/%Y')}, guardado em: {local}",
    )
    supabase.table("conduta_casos").update(campos).eq("id", caso["id"]).execute()
    return {**caso, **campos}


def dados_da_etiqueta(supabase, caso: dict) -> dict:
    """Os campos do Anexo E.2. Nenhum nome de pessoa, setor nem assunto: o
    espaço do lacre é preenchido à mão."""
    return {
        "protocolo": caso["protocolo"],
        "rito": RITOS.get(caso.get("rito") or "", "Sem rito"),
        "aberto_em": _dia(caso["recebido_em"]).strftime("%d/%m/%Y"),
        "encerrado_em": _dia(caso["encerrado_em"]).strftime("%d/%m/%Y"),
        "conteudo": conteudo_do_envelope(originais(supabase, caso)),
        "guardar_ate": guardar_ate(caso).strftime("%d/%m/%Y"),
    }


def etiqueta(supabase, aberto: CasoAberto) -> tuple[bytes, str]:
    """IMPRIMIR ETIQUETA: o PDF da folha A4 e o nome do arquivo."""
    from app.services.seguranca_do_paciente.termo import gerar_pdf_do_termo

    _recusar_se_nao_pode_lacrar(aberto)
    dados = dados_da_etiqueta(supabase, aberto.caso)
    return gerar_pdf_do_termo({**dados, "modelo": MODELO_DA_ETIQUETA}), f"etiqueta-{dados['protocolo']}.pdf"


# ── O congelamento ──────────────────────────────────────────────────────────


def _recusar_se_nao_coordena(aberto: CasoAberto) -> None:
    if aberto.pessoa.papel != "coordenacao":
        raise AcaoRecusadaError(403, "Só a coordenação congela e descongela o caso.")
    if aberto.caso.get("eliminado_em"):
        raise AcaoRecusadaError(409, ELIMINADO)


def congelar(supabase, aberto: CasoAberto) -> dict:
    _recusar_se_nao_coordena(aberto)
    caso = aberto.caso
    if caso.get("congelado_em"):
        raise AcaoRecusadaError(409, "O caso já está congelado.")
    campos = {"congelado_em": agora_utc().isoformat(), "congelado_por": aberto.autor_id}
    trilha.registrar(supabase, caso["id"], aberto.autor_id, "congelou_o_caso", "caso congelado: nada é eliminado")
    supabase.table("conduta_casos").update(campos).eq("id", caso["id"]).execute()
    return {**caso, **campos}


def descongelar(supabase, aberto: CasoAberto) -> dict:
    _recusar_se_nao_coordena(aberto)
    caso = aberto.caso
    if not caso.get("congelado_em"):
        raise AcaoRecusadaError(409, "O caso não está congelado.")
    campos = {"congelado_em": None, "congelado_por": None}
    trilha.registrar(
        supabase, caso["id"], aberto.autor_id, "descongelou_o_caso", "caso descongelado: a guarda volta a valer"
    )
    supabase.table("conduta_casos").update(campos).eq("id", caso["id"]).execute()
    return {**caso, **campos}


# ── A eliminação e o aviso (o job diário) ──────────────────────────────────


def _caminhos_do_caso(supabase, caso_id: str) -> list[str]:
    """Todo arquivo do caso no bucket do Canal."""
    ids = [
        d["id"] for d in supabase.table("conduta_depoimentos").select("id").eq("caso_id", caso_id).execute().data or []
    ]
    caminhos = [a["storage_path"] for a in depoimentos._arquivos(supabase, ids)] if ids else []
    for tabela, coluna in (
        ("conduta_ciencias_do_codigo", "storage_path"),
        ("conduta_reuniao_transcricoes", "storage_path"),
        ("conduta_comunicacoes_da_medida", "storage_path"),
        ("conduta_assinaturas", "arquivo_assinado_path"),
        ("conduta_afastamentos", "parecer_storage_path"),
    ):
        caminhos += [
            linha[coluna]
            for linha in supabase.table(tabela).select("*").eq("caso_id", caso_id).execute().data or []
            if linha.get(coluna)
        ]
    return caminhos


def _tirar_do_bucket(supabase, caminho: str) -> bool:
    """O Storage diz False tanto para a recusa quanto para o arquivo que já
    saiu: na dúvida, confere se ele ainda está lá."""
    if storage.delete_file(supabase, BUCKET, caminho):
        return True
    return storage.download_file(supabase, BUCKET, caminho) is None


def eliminar(supabase, caso: dict) -> bool:
    """Tira os arquivos do bucket, apaga o conteúdo no banco e registra na
    trilha. Arquivo que o bucket não soltou deixa o caso para a próxima
    rodada, com tudo no lugar."""
    caminhos = _caminhos_do_caso(supabase, caso["id"])
    presos = [c for c in caminhos if not _tirar_do_bucket(supabase, c)]
    if presos:
        logger.error("Caso do Canal sem eliminação: %d arquivo(s) não saíram do bucket", len(presos))
        return False
    supabase.rpc(FUNCAO_DE_ELIMINACAO, {"p_caso_id": caso["id"]}).execute()
    trilha.registrar(
        supabase,
        caso["id"],
        None,
        "eliminou_o_conteudo",
        f"conteúdo do caso eliminado ao fim da guarda ({len(caminhos)} arquivo(s) fora do bucket)",
    )
    return True


def _tem_papel(caso: dict) -> bool:
    return bool(caso.get("papel_lacrado_em")) or (caso.get("rito") or "encaminhamento") != "encaminhamento"


def _coordenacao(supabase, hoje: date) -> list[str]:
    comite_id = membros.id_do_comite(supabase)
    if not comite_id:
        return []
    return sorted(
        {
            p["participante_id"]
            for p in membros.participacoes(supabase, comite_id)
            if p["papel"] == "coordenacao" and membros.situacao(p, hoje) == "vigente"
        }
    )


def link_dos_casos() -> str:
    return f"{settings.frontend_url}/comite-de-conduta/casos"


def avisar_vencimento(supabase, caso: dict, hoje: date) -> bool:
    """O e-mail à coordenação, sem nada do caso. Marca o caso quando ao menos
    um saiu; quem não recebeu tem a próxima rodada."""
    from app.services.email_constants import get_logo_data_uri

    ids = _coordenacao(supabase, hoje)
    if not ids:
        return False
    link = link_dos_casos()
    html = jinja_env.get_template("email_conduta_aviso.html").render(
        frase=FRASE_DO_AVISO, link=link, logo_base64=get_logo_data_uri()
    )
    texto = f"{FRASE_DO_AVISO}\n\nPara ver: {link}\n"
    enderecos = supabase.table("participantes").select("id, email").in_("id", ids).execute().data or []
    saiu = False
    for linha in enderecos:
        if not linha.get("email"):
            continue
        try:
            saiu = _enviar_email(linha["email"], FRASE_DO_AVISO, html, texto, endereco_fora_do_log=True) or saiu
        except Exception:  # noqa: BLE001 (um e-mail que falha não para os outros)
            logger.warning("[conduta_guarda] Aviso da guarda para %s não saiu", linha["id"], exc_info=True)
    if saiu:
        supabase.table("conduta_casos").update({"guarda_avisada_em": agora_utc().isoformat()}).eq(
            "id", caso["id"]
        ).execute()
    return saiu


def rodada(supabase, hoje: date) -> dict[str, int]:
    """O job diário: elimina o conteúdo dos casos com a guarda vencida e avisa
    a coordenação do papel. Caso congelado fica de fora das duas coisas."""
    casos = supabase.table("conduta_casos").select(CAMPOS).execute().data or []
    eliminados = avisados = falhas = 0
    for caso in casos:
        if caso.get("congelado_em") or not vencida(caso, hoje):
            continue
        if not caso.get("eliminado_em"):
            try:
                if not eliminar(supabase, caso):
                    falhas += 1
                    continue
            except Exception:  # noqa: BLE001 (um caso que falha não para os outros)
                logger.error("[conduta_guarda] Eliminação do caso falhou", exc_info=True)
                falhas += 1
                continue
            eliminados += 1
        if _tem_papel(caso) and not caso.get("guarda_avisada_em") and avisar_vencimento(supabase, caso, hoje):
            avisados += 1
    return {"eliminados": eliminados, "avisados": avisados, "falhas": falhas}
