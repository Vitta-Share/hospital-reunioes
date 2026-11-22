"""A área "Trilha do caso" do Canal de Conduta (issue #1837; especificação,
seção 9.1; ADR 0097, decisão 9).

Tudo o que foi feito e assinado no caso, numa linha do tempo: cada ato da
trilha (quem, quando, o quê e o código da linha na cadeia) e cada documento
(quem enviou, quando, a origem, ClickSign ou upload, e o código de integridade
do arquivo). A correção de um documento entra como versão nova, e a anterior
continua na linha do tempo.

Cada rito cria as gavetas dos documentos que ele exige, cada uma "Aguardando"
ou "Assinado". Gaveta obrigatória vazia impede concluir o caso como procedente
(`voto.bloqueio_da_conclusao`). As gavetas saem do que o caso já tem: não há
tabela delas.

A conferência da cadeia refaz a trilha inteira a cada abertura e aponta a
linha trocada ou a lacuna da linha apagada (`trilha.linhas_adulteradas`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.conduta import assinaturas, ata, depoimentos, membros, relatorio, trilha
from app.services.conduta.acesso import PAPEIS_DA_FILA_COMUM
from app.services.conduta.portao import CasoAberto

UPLOAD = "Upload"
CLICKSIGN = "ClickSign"
APLICACAO = "Aplicação"

AGUARDANDO = "Aguardando"
ASSINADO = "Assinado"

# Os documentos da ClickSign que são do caso (o Termo de posse é do membro).
TITULOS_DA_CLICKSIGN = {
    assinaturas.TERMO_DO_CONVIDADO: "Termo de confidencialidade do convidado",
    assinaturas.RELATORIO_DE_APURACAO: "Relatório de apuração assinado",
    assinaturas.ATA_DE_DELIBERACAO: "Ata de deliberação assinada",
    assinaturas.CERTIDAO_DE_RECUSA: "Certidão de recusa de assinatura",
}
TITULOS_DO_DEPOIMENTO = {
    "transcricao": "Transcrição do depoimento",
    "audio": "Áudio do depoimento",
    "termo_assinado": "Termo de declaração assinado",
}
RITOS_COM_VOTO = ("rapido", "completo")
CONVIDADOS = {"apurador": "Apurador", "cipa": "Membro da CIPA"}


@dataclass(frozen=True)
class Documento:
    """Um arquivo do caso. `caminho` e `content_type` servem ao Dossiê e
    nunca vão para a tela."""

    titulo: str
    origem: str
    autor: str
    data: str | None
    codigo: str | None
    caminho: str | None
    content_type: str
    versao: int | None = None
    pasta: str = "documentos"
    extras: dict[str, Any] = field(default_factory=dict)


def _pessoas_ouvidas(lista: list[dict]) -> dict[str, str]:
    """Cada pessoa ouvida sem o nome: o papel e o número dela no papel, na
    ordem em que entrou ("Acusado 1", "Testemunha 2")."""
    contagem: dict[str, int] = {}
    rotulos = {}
    for depoimento in lista:
        contagem[depoimento["papel"]] = contagem.get(depoimento["papel"], 0) + 1
        rotulos[depoimento["id"]] = f"{depoimentos.PAPEIS[depoimento['papel']]} {contagem[depoimento['papel']]}"
    return rotulos


def _assinaturas_do_caso(supabase, caso_id: str) -> list[dict]:
    return supabase.table(assinaturas.TABELA).select("*").eq("caso_id", caso_id).execute().data or []


def documentos_do_caso(supabase, caso: dict) -> list[Documento]:
    """Todo arquivo do caso, versão a versão, na ordem em que entrou."""
    caso_id = caso["id"]
    lista = depoimentos.do_caso(supabase, caso_id)
    pessoas = _pessoas_ouvidas(lista)
    arquivos = depoimentos._arquivos(supabase, [d["id"] for d in lista])
    ciencias = supabase.table("conduta_ciencias_do_codigo").select("*").eq("caso_id", caso_id).execute().data or []
    assinadas = [a for a in _assinaturas_do_caso(supabase, caso_id) if a.get("situacao") == "assinado"]
    pareceres = [
        a
        for a in supabase.table("conduta_afastamentos").select("*").eq("caso_id", caso_id).execute().data or []
        if a.get("parecer_storage_path")
    ]
    nomes = membros.nomes(
        supabase,
        sorted(
            {a["enviado_por"] for a in arquivos}
            | {c["enviado_por"] for c in ciencias}
            | {p for a in assinadas for p in a.get("signatarios") or []}
            | {a["parecer_anexado_por"] for a in pareceres}
        ),
    )
    saida: list[Documento] = []
    for arquivo in arquivos:
        titulo = f"{TITULOS_DO_DEPOIMENTO[arquivo['tipo']]}, {pessoas.get(arquivo['depoimento_id'], '')}"
        if arquivo["tipo"] == "termo_assinado" and (arquivo.get("pagina") or 1) > 1:
            titulo += f", página {arquivo['pagina']}"
        saida.append(
            Documento(
                titulo=titulo,
                origem=UPLOAD,
                autor=nomes.get(arquivo["enviado_por"], ""),
                data=arquivo.get("enviado_em"),
                codigo=arquivo.get("codigo_integridade"),
                caminho=arquivo["storage_path"],
                content_type=arquivo["content_type"],
                versao=arquivo["versao"],
                pasta={"audio": "audios", "transcricao": "transcricoes-de-depoimentos"}.get(
                    arquivo["tipo"], "documentos"
                ),
            )
        )
    for ciencia in ciencias:
        saida.append(
            Documento(
                titulo="Ciência do Código pelo acusado",
                origem=UPLOAD,
                autor=nomes.get(ciencia["enviado_por"], ""),
                data=ciencia.get("enviado_em"),
                codigo=ciencia.get("codigo_integridade"),
                caminho=ciencia["storage_path"],
                content_type=ciencia["content_type"],
                versao=ciencia["versao"],
            )
        )
    for assinatura in assinadas:
        if assinatura["tipo"] not in TITULOS_DA_CLICKSIGN:
            continue
        saida.append(
            Documento(
                titulo=TITULOS_DA_CLICKSIGN[assinatura["tipo"]],
                origem=CLICKSIGN,
                autor=", ".join(nomes.get(p, "") for p in assinatura.get("signatarios") or []),
                data=assinatura.get("assinado_em"),
                codigo=assinatura.get("codigo_integridade"),
                caminho=assinatura.get("arquivo_assinado_path"),
                content_type="application/pdf",
            )
        )
    for afastamento in pareceres:
        saida.append(
            Documento(
                titulo="Parecer do Jurídico sobre o afastamento cautelar",
                origem=UPLOAD,
                autor=nomes.get(afastamento["parecer_anexado_por"], ""),
                data=afastamento.get("parecer_anexado_em"),
                codigo=afastamento.get("parecer_codigo_integridade"),
                caminho=afastamento["parecer_storage_path"],
                content_type="application/pdf",
            )
        )
    return sorted(saida, key=lambda d: str(d.data or ""))


def _linhas(supabase, caso_id: str) -> list[dict]:
    linhas = supabase.table("conduta_trilha").select("*").eq("caso_id", caso_id).execute().data or []
    return sorted(linhas, key=lambda x: x["seq"])


def linha_do_tempo(supabase, caso: dict) -> list[dict]:
    """Os atos da trilha e os documentos, juntos, na ordem do tempo."""
    linhas = _linhas(supabase, caso["id"])
    nomes = membros.nomes(supabase, sorted({x["autor_id"] for x in linhas if x.get("autor_id")}))
    itens = [
        {
            "tipo": "ato",
            "acao": linha["acao"],
            "titulo": linha.get("detalhe") or linha["acao"],
            "autor": nomes.get(linha["autor_id"], "") if linha.get("autor_id") else APLICACAO,
            "data": linha["registrado_em"],
            "origem": APLICACAO,
            "codigo": linha["codigo"],
            "versao": None,
        }
        for linha in linhas
    ]
    itens += [
        {
            "tipo": "documento",
            "acao": None,
            "titulo": d.titulo,
            "autor": d.autor,
            "data": d.data,
            "origem": d.origem,
            "codigo": d.codigo,
            "versao": d.versao,
        }
        for d in documentos_do_caso(supabase, caso)
    ]
    return sorted(itens, key=lambda i: (str(i["data"] or ""), i["tipo"] == "documento"))


def _gaveta(rotulo: str, origem: str, cheia: bool) -> dict:
    return {"rotulo": rotulo, "origem": origem, "obrigatoria": True, "situacao": ASSINADO if cheia else AGUARDANDO}


def gavetas(supabase, caso: dict) -> list[dict]:
    """As gavetas que o rito do caso exige, na ordem da tela. O Encaminhamento
    não tem nenhuma. Cada pessoa ouvida pede o termo de declaração assinado
    (ou a certidão de recusa, assinada por dois membros); cada convidado, o
    termo de confidencialidade; o rito com voto, a ciência do Código e a ata;
    o Completo, também o relatório assinado pelos apuradores."""
    if caso.get("rito") == "encaminhamento":
        return []
    caso_id = caso["id"]
    lista = depoimentos.do_caso(supabase, caso_id)
    pessoas = _pessoas_ouvidas(lista)
    ids = [d["id"] for d in lista]
    com_termo = {a["depoimento_id"] for a in depoimentos._arquivos(supabase, ids) if a["tipo"] == "termo_assinado"}
    com_certidao = {c["depoimento_id"] for c in depoimentos._certidoes(supabase, ids) if c["situacao"] == "assinado"}
    saida = []
    for depoimento in lista:
        pela_certidao = depoimento["id"] in com_certidao and depoimento["id"] not in com_termo
        saida.append(
            _gaveta(
                f"Termo de declaração, {pessoas[depoimento['id']]}",
                CLICKSIGN if pela_certidao else UPLOAD,
                depoimento["id"] in com_termo or pela_certidao,
            )
        )
    convidados = sorted(
        (
            a
            for a in supabase.table("conduta_atribuicoes").select("*").eq("caso_id", caso_id).execute().data or []
            if a.get("motivo") in CONVIDADOS and not a.get("revogada_em")
        ),
        key=lambda a: str(a.get("created_at") or ""),
    )
    contagem: dict[str, int] = {}
    for convidado in convidados:
        contagem[convidado["motivo"]] = contagem.get(convidado["motivo"], 0) + 1
        saida.append(
            _gaveta(
                f"Termo de confidencialidade, {CONVIDADOS[convidado['motivo']]} {contagem[convidado['motivo']]}",
                CLICKSIGN,
                bool(convidado.get("termo_assinado_em")),
            )
        )
    if caso.get("rito") == "completo":
        versoes = relatorio._versoes(supabase, caso_id, "relatorio")
        assinatura = relatorio._assinatura_da_versao(supabase, caso_id, versoes[-1]["id"]) if versoes else None
        saida.append(
            _gaveta("Relatório de apuração", CLICKSIGN, bool(assinatura) and assinatura["situacao"] == "assinado")
        )
    if caso.get("rito") in RITOS_COM_VOTO:
        ciencias = supabase.table("conduta_ciencias_do_codigo").select("id").eq("caso_id", caso_id).execute().data
        saida.append(_gaveta("Ciência do Código pelo acusado", UPLOAD, bool(ciencias)))
        saida.append(_gaveta("Ata de deliberação", CLICKSIGN, ata.ata_assinada(supabase, caso)))
    return saida


def bloqueio(supabase, caso: dict) -> str | None:
    """A primeira gaveta obrigatória vazia, numa linha, ou None. Vale para
    concluir como procedente ou parcialmente procedente."""
    for gaveta in gavetas(supabase, caso):
        if gaveta["obrigatoria"] and gaveta["situacao"] != ASSINADO:
            return f"Gaveta obrigatória vazia: {gaveta['rotulo']}."
    return None


def para_a_tela(supabase, aberto: CasoAberto) -> dict:
    caso = aberto.caso
    return {
        "trilha": {
            "linha_do_tempo": linha_do_tempo(supabase, caso),
            "gavetas": gavetas(supabase, caso),
        }
    }
