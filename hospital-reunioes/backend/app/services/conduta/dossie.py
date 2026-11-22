"""O Dossiê do caso do Canal de Conduta (issue #1837; especificação, seção
9.2; ADR 0097, decisões 2 e 9).

"BAIXAR DOSSIÊ": um pacote ZIP com o índice, o relato original, todos os
documentos, os áudios, as transcrições dos depoimentos, os votos, a ata, a
decisão da Direção, as mensagens trocadas com o denunciante e o registro de
acessos do caso. Tudo decifrado aqui, dentro do backend, e nada por URL.

Só baixa quem é do Comitê no caso: a coordenação, o membro e o segundo
leitor, ou o suplente convocado no lugar de um deles. Apurador, CIPA,
Presidente, diretoria executiva e super admin, não. Cada download entra na
trilha antes de o pacote ser montado: sem a linha, o pacote não sai.

O índice lista cada arquivo com quem enviou, quando, a origem e o código de
integridade do que está no pacote. Se o arquivo não bate com o código gravado
no envio, o índice diz.
"""

from __future__ import annotations

import json
import re
import tempfile
import unicodedata
import zipfile
from datetime import datetime
from typing import IO

from app.services import storage
from app.services.conduta import ata, cifra, depoimentos, membros, relatorio, trilha, voto
from app.services.conduta.portao import CasoAberto
from app.services.conduta.ritos import FUSO
from app.services.conduta.trilha_do_caso import (
    APLICACAO,
    Documento,
    conferencia,
    documentos_do_caso,
    linhas_da_trilha,
    pessoas_ouvidas,
)

ACAO_DO_DOWNLOAD = "baixou_dossie"
DETALHE_DO_DOWNLOAD = "baixou o Dossiê do caso"
# Até aqui o pacote fica na memória; passou, vai para o disco.
_EM_MEMORIA = 32 * 1024 * 1024

EXTENSOES = {
    "application/pdf": ".pdf",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "text/plain; charset=utf-8": ".txt",
    "text/vtt; charset=utf-8": ".vtt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
# O que já vem comprimido vai como está.
_SEM_COMPRESSAO = ("audio/", "image/", "application/pdf")

SECOES = (
    ("01-relato-original.txt", "Relato original"),
    ("05-votos.txt", "Votos"),
    ("06-ata-de-deliberacao.txt", "Ata de deliberação"),
    ("07-decisao-da-direcao.txt", "Decisão da Direção"),
    ("08-mensagens-com-o-denunciante.txt", "Mensagens trocadas com o denunciante"),
    ("09-registro-de-acessos.txt", "Registro de acessos e trilha do caso"),
)
PASTAS = {
    "documentos": "02-documentos",
    "audios": "03-audios",
    "transcricoes-de-depoimentos": "04-transcricoes-de-depoimentos",
}


def registrar_download(supabase, aberto: CasoAberto) -> None:
    """A linha da trilha do download, com quem e quando. Levanta se não
    gravar: o pacote não sai sem ela."""
    trilha.registrar(supabase, aberto.caso["id"], aberto.autor_id, ACAO_DO_DOWNLOAD, DETALHE_DO_DOWNLOAD)


# ── O texto ─────────────────────────────────────────────────────────────────


def _quando(valor: str | None) -> str:
    if not valor:
        return "sem data"
    return datetime.fromisoformat(str(valor)).astimezone(FUSO).strftime("%d/%m/%Y %H:%M:%S")


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def _relato(caso: dict) -> str:
    return (
        f"Relato original do caso {caso['protocolo']}, recebido em {_quando(caso.get('recebido_em'))}.\n\n"
        f"{cifra.decifrar_texto(caso['relato_cifrado'])}\n"
    )


def _votos(supabase, caso: dict) -> str:
    """Só as rodadas fechadas: o voto fica oculto até os três votarem, e o
    Dossiê segue o mesmo sigilo da tela."""
    atual = voto.situacao(supabase, caso)
    ultima_fechada = atual.rodada if atual.fechada else atual.rodada - 1
    if ultima_fechada < 1:
        return "Nenhuma rodada de voto fechada neste caso.\n"
    nomes = membros.nomes(supabase, sorted({v["participante_id"] for v in atual.votos}))
    partes = []
    for numero in range(1, ultima_fechada + 1):
        linhas = (
            atual.da_rodada(numero) if numero == atual.rodada else [v for v in atual.votos if v["rodada"] == numero]
        )
        partes.append(f"Rodada {numero}")
        for linha in linhas:
            conteudo = voto._conteudo(linha)
            medida = voto._rotulo_da_medida(conteudo.get("medida"), conteudo.get("dias_de_suspensao"))
            rotulo = voto.RESULTADOS[conteudo["resultado"]] + (f", {medida}" if medida else "")
            partes.append(
                f"{nomes.get(linha['participante_id'], '')}: {rotulo}. Votou em {_quando(linha.get('votado_em'))}."
            )
            partes.append(f"  Justificativa: {conteudo['justificativa']}")
        partes.append("")
    if caso.get("resultado"):
        partes.append(f"Resultado da votação: {voto.RESULTADOS[caso['resultado']]}.")
    return "\n".join(partes).rstrip() + "\n"


def _lista(valor) -> list[str]:
    if isinstance(valor, list):
        return [str(item) for item in valor]
    return [str(valor)] if valor else []


def _ata(supabase, caso: dict) -> str:
    versoes = ata._versoes(supabase, caso["id"])
    if not versoes:
        return "A ata de deliberação ainda não foi gerada neste caso.\n"
    ultima = versoes[-1]
    conteudo = json.loads(cifra.decifrar_texto(ultima["ata_cifrada"]))
    assinada = ata._assinatura_da_versao(supabase, caso["id"], ultima["id"])
    partes = [f"Ata de deliberação, versão {ultima['versao']}."]
    if assinada and assinada.get("situacao") == "assinado":
        partes.append(f"Assinada pelos três votantes em {_quando(assinada.get('assinado_em'))}.")
    else:
        partes.append("Ainda sem as três assinaturas.")
    for chave, titulo in (
        ("resumo", "Resumo dos fatos"),
        ("provas", "Provas"),
        ("defesa", "Defesa"),
        ("deliberacao", "Deliberação"),
        ("fundamentos", "Fundamentos"),
        ("medida", "Medida"),
        ("correcao", "Correção do processo"),
        ("encaminhamentos", "Encaminhamentos"),
    ):
        itens = _lista(conteudo.get(chave))
        if itens:
            partes.append(f"\n{titulo}\n" + "\n".join(itens))
    return "\n".join(partes) + "\n"


def _decisao_da_direcao(caso: dict) -> str:
    # A decisão da Direção chega com a issue #1835; até lá o caso não a tem.
    return "A decisão da Direção ainda não foi registrada neste caso.\n"


def _mensagens(supabase, caso: dict) -> str:
    """As perguntas da coordenação e os complementos de quem relatou (issue
    #1845), em ordem, e a orientação do Encaminhamento."""
    partes = []
    linhas = supabase.table("conduta_mensagens").select("*").eq("caso_id", caso["id"]).execute().data or []
    for linha in sorted(linhas, key=lambda m: datetime.fromisoformat(str(m["enviada_em"]))):
        quem = "Pergunta do Comitê" if linha["tipo"] == "pergunta" else "Complemento de quem relatou"
        partes.append(f"{quem} em {_quando(linha['enviada_em'])}:\n" + cifra.decifrar_texto(linha["texto_cifrado"]))
    if caso.get("orientacao_cifrada"):
        partes.append(
            "Orientação enviada pela página de acompanhamento:\n" + cifra.decifrar_texto(caso["orientacao_cifrada"])
        )
    if not partes:
        return "Nenhuma mensagem trocada com o denunciante neste caso.\n"
    return "\n\n".join(partes) + "\n"


def _registro(supabase, linhas: list[dict]) -> str:
    nomes = membros.nomes(supabase, sorted({x["autor_id"] for x in linhas if x.get("autor_id")}))
    partes = [conferencia(linhas)["texto"], "", "Linha | Quando | Quem | O quê | Código da linha"]
    for linha in linhas:
        quem = nomes.get(linha["autor_id"], linha["autor_id"]) if linha.get("autor_id") else APLICACAO
        partes.append(
            f"{linha['seq']} | {_quando(linha['registrado_em'])} | {quem} | "
            f"{linha.get('detalhe') or linha['acao']} | {linha['codigo']}"
        )
    return "\n".join(partes) + "\n"


def _textos_da_apuracao(supabase, caso: dict) -> list[tuple[str, str]]:
    """Os documentos em texto: os pontos do depoimento sem gravação e a última
    versão do relatório de apuração e da cronologia."""
    lista = depoimentos.do_caso(supabase, caso["id"])
    pessoas = pessoas_ouvidas(lista)
    textos = []
    for depoimento in lista:
        if depoimento.get("sem_gravacao_em"):
            texto = (
                f"Depoimento sem gravação, {pessoas[depoimento['id']]}.\n"
                f"Motivo: {cifra.decifrar_texto(depoimento['sem_gravacao_motivo_cifrado'])}\n\n"
                f"{cifra.decifrar_texto(depoimento['pontos_cifrados'])}\n"
            )
            textos.append(
                (f"{PASTAS['transcricoes-de-depoimentos']}/pontos-{_slug(pessoas[depoimento['id']])}.txt", texto)
            )
    for tipo, titulo in (("relatorio", "Relatório de apuração"), ("cronologia", "Cronologia dos fatos")):
        versoes = relatorio._versoes(supabase, caso["id"], tipo)
        if versoes:
            ultima = versoes[-1]
            texto = f"{titulo}, versão {ultima['versao']}.\n\n{cifra.decifrar_texto(ultima['texto_cifrado'])}\n"
            textos.append((f"{PASTAS['documentos']}/{_slug(titulo)}-v{ultima['versao']}.txt", texto))
    return textos


# ── O pacote ────────────────────────────────────────────────────────────────


def _nome_do_arquivo(documento: Documento, numero: int) -> str:
    versao = f"-v{documento.versao}" if documento.versao else ""
    extensao = EXTENSOES.get(documento.content_type, ".bin")
    return f"{PASTAS[documento.pasta]}/{numero:02d}-{_slug(documento.titulo)}{versao}{extensao}"


class _Ilegivel:
    """O objeto do bucket que a chave configurada não abre: corrompido, ou
    trocado por quem não tem a chave."""


def _entrada_do_indice(numero: int, nome: str, documento: Documento, conteudo: bytes | None | _Ilegivel) -> str:
    linhas = [
        f"{numero:02d}. {nome}",
        f"    O quê: {documento.titulo}",
        f"    Enviado por: {documento.autor or 'sem registro'}",
        f"    Quando: {_quando(documento.data)}",
        f"    Origem: {documento.origem}",
    ]
    if conteudo is None or isinstance(conteudo, _Ilegivel):
        if conteudo is None:
            linhas.append("    Atenção: o arquivo não pôde ser lido do armazenamento e não está no pacote.")
        else:
            linhas.append(
                "    Atenção: o arquivo no armazenamento não abre com a chave do caso (corrompido ou trocado) "
                "e não está no pacote."
            )
        if documento.codigo:
            linhas.append(f"    Código de integridade registrado no envio: {documento.codigo}")
        return "\n".join(linhas)
    codigo = trilha.codigo_de_integridade(conteudo)
    linhas.append(f"    Código de integridade: {codigo}")
    if documento.codigo is None:
        linhas.append("    Sem código registrado no envio.")
    elif documento.codigo != codigo:
        linhas.append(f"    Atenção: não confere com o código registrado no envio ({documento.codigo}).")
    return "\n".join(linhas)


def _ler(supabase, documento: Documento) -> bytes | None | _Ilegivel:
    if not documento.caminho:
        return None
    cifrado = storage.download_file(supabase, depoimentos.BUCKET, documento.caminho)
    if cifrado is None:
        return None
    try:
        return cifra.decifrar_arquivo(cifrado)
    except cifra.CifraIndisponivelError:
        # Sem a chave, o caso inteiro não abre: o erro sobe e vira 503.
        if not cifra.chave_configurada():
            raise
        return _Ilegivel()


def montar(supabase, aberto: CasoAberto) -> tuple[IO[bytes], str]:
    """O pacote ZIP e o nome do arquivo. Chame depois de `registrar_download`:
    o registro de acessos do pacote já traz o próprio download. Levanta
    `CifraIndisponivelError` se a chave falta ou não abre o caso; o arquivo do
    bucket que a chave não abre entra no índice, sem derrubar o pacote."""
    caso = aberto.caso
    linhas = linhas_da_trilha(supabase, caso["id"])
    baixou = membros.nomes(supabase, [aberto.autor_id]).get(aberto.autor_id, "")
    destino = tempfile.SpooledTemporaryFile(max_size=_EM_MEMORIA)
    indice = [
        f"Dossiê do caso {caso['protocolo']}",
        f"Baixado por {baixou} em {_quando(datetime.now(FUSO).isoformat())}.",
        f"Rito: {caso.get('rito') or 'sem rito'}. Etapa: {caso.get('etapa')}.",
        conferencia(linhas)["texto"],
        "",
        "Seções",
    ]
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as pacote:
        textos = {
            "01-relato-original.txt": _relato(caso),
            "05-votos.txt": _votos(supabase, caso),
            "06-ata-de-deliberacao.txt": _ata(supabase, caso),
            "07-decisao-da-direcao.txt": _decisao_da_direcao(caso),
            "08-mensagens-com-o-denunciante.txt": _mensagens(supabase, caso),
            "09-registro-de-acessos.txt": _registro(supabase, linhas),
        }
        for nome, titulo in SECOES:
            pacote.writestr(nome, textos[nome].encode("utf-8"))
            indice.append(f"{nome}: {titulo}")
        apuracao = _textos_da_apuracao(supabase, caso)
        for nome, texto in apuracao:
            pacote.writestr(nome, texto.encode("utf-8"))
            indice.append(f"{nome}: documento em texto, decifrado pelo aplicativo")
        indice += ["", "Arquivos do caso"]
        for numero, documento in enumerate(documentos_do_caso(supabase, caso), 1):
            nome = _nome_do_arquivo(documento, numero)
            conteudo = _ler(supabase, documento)
            if isinstance(conteudo, bytes):
                sem_compressao = documento.content_type.startswith(_SEM_COMPRESSAO)
                pacote.writestr(nome, conteudo, compress_type=zipfile.ZIP_STORED if sem_compressao else None)
            indice.append(_entrada_do_indice(numero, nome, documento, conteudo))
        pacote.writestr("00-indice.txt", ("\n".join(indice) + "\n").encode("utf-8"))
    destino.seek(0)
    return destino, f"dossie-{caso['protocolo']}.zip"
