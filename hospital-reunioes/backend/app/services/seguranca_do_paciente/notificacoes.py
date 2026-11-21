"""A Notificação de incidente do Núcleo (issue #1987, PRD #1979, ADR 0107).

Quem notifica conta o que aconteceu e não classifica. O formulário tem três
portas, e a origem vem de qual delas a pessoa usou, nunca de escolha dela: o QR
(`/notificar/qr`), o endereço (`/notificar`) e o botão "Notificar incidente"
do módulo, que já chega identificado pela sessão.

O protocolo NSP-AAAA-NNNN sai do banco no insert (migration 174). A anônima
ganha o código de acompanhamento da Ouvidoria, mostrado uma vez só: aqui só o
hash é guardado. Nada daqui lê ou grava IP ou identificador do aparelho: a
linha é montada só com os campos do envio.
"""

from __future__ import annotations

from typing import Any

from app.services import ouvidoria_acompanhamento

ORIGEM_QR = "qr"
ORIGEM_ENDERECO = "endereco"
ORIGEM_MODULO = "modulo"
# As portas das outras fatias: a ponte da Ouvidoria e o registro rápido.
ORIGENS = (
    ORIGEM_QR,
    ORIGEM_ENDERECO,
    ORIGEM_MODULO,
    "ouvidoria",
    "busca_ativa",
    "ronda",
    "reuniao_rapida",
    "auditoria",
    "outra",
)

RECEBIDA = "Recebida"
EM_ANALISE = "Em análise"
CONCLUIDA = "Concluída"
# Os estados do caso, na língua de quem notificou (PRD #1979).
ESTADO_PUBLICO: dict[str, str] = {
    "recebida": RECEBIDA,
    "em_triagem": EM_ANALISE,
    "classificada": EM_ANALISE,
    "em_analise_agregada": EM_ANALISE,
    "encaminhada": CONCLUIDA,
    "fora_de_escopo": CONCLUIDA,
}

# Os campos do relato que o envio traz, os mesmos nas três portas.
_CAMPOS_DO_RELATO = (
    "relato",
    "leito_ou_atendimento",
    "setor_id",
    "data_ocorrencia",
    "turno",
    "hora_aproximada",
    "chegou_ao_paciente",
    "grave_ou_morte",
    "percebido_ou_reclamacao",
)


def registrar(
    supabase,
    relato: dict[str, Any],
    *,
    origem: str,
    anonimo: bool,
    nome: str | None = None,
    contato: str | None = None,
    notificante_id: str | None = None,
) -> dict[str, Any]:
    """Grava a notificação e devolve o recibo: o id, o protocolo e, na
    anônima, o código de acompanhamento, que não fica guardado em lugar
    nenhum. O id é para ligar os anexos e registrar os avisos da chegada;
    quem notificou não o recebe."""
    if origem not in ORIGENS:
        raise ValueError(f"Origem desconhecida: {origem!r}")
    linha: dict[str, Any] = {campo: relato.get(campo) for campo in _CAMPOS_DO_RELATO}
    linha["origem"] = origem
    linha["anonimo"] = anonimo
    codigo: str | None = None
    if anonimo:
        codigo = ouvidoria_acompanhamento.gerar_codigo()
        linha["codigo_acompanhamento_hash"] = ouvidoria_acompanhamento.hash_do_codigo(codigo)
    else:
        linha["notificante_id"] = notificante_id
        linha["notificante_nome"] = nome
        linha["notificante_contato"] = contato
    gravada = supabase.table("nsp_notificacoes").insert(linha).execute().data[0]
    recibo: dict[str, Any] = {
        "id": gravada["id"],
        "protocolo": gravada["protocolo"],
        "criado_em": gravada.get("criado_em"),
    }
    if codigo:
        recibo["codigo_acompanhamento"] = codigo
    return recibo


ORIGEM_OUVIDORIA = "ouvidoria"
_LIMITE_DO_RELATO = 10000


def criar_caso_da_ouvidoria(
    supabase,
    *,
    manifestacao_id: str,
    relato: str | None,
    justificativa_tecnica: str | None,
    setor_id: str | None,
    data_ocorrencia: str,
    turno: str | None,
    hora_aproximada: str | None,
) -> dict[str, Any]:
    """A notificação de origem Ouvidoria (issue #1997, ADR 0107 decisão 7).
    Devolve o id e o protocolo.

    Quem manifestou não entra: nem nome, nem contato, nem código. Uma
    manifestação vira uma notificação só: o índice único recusa a segunda
    (23505), e a nova tentativa do envio segue com a que ficou."""
    from postgrest.exceptions import APIError

    linha: dict[str, Any] = {
        "origem": ORIGEM_OUVIDORIA,
        "manifestacao_id": manifestacao_id,
        "relato": ((relato or "").strip() or "A Ouvidoria não registrou o relato original.")[:_LIMITE_DO_RELATO],
        "justificativa_tecnica": ((justificativa_tecnica or "").strip() or None),
        "setor_id": setor_id,
        "data_ocorrencia": data_ocorrencia,
        "turno": turno,
        "hora_aproximada": hora_aproximada,
        "anonimo": False,
    }
    try:
        gravada = supabase.table("nsp_notificacoes").insert(linha).execute().data[0]
    except APIError as erro:
        if erro.code != "23505":
            raise
        gravada = caso_da_manifestacao(supabase, manifestacao_id)
        if gravada is None:
            raise
    return {"id": gravada["id"], "protocolo": gravada.get("protocolo")}


def caso_da_manifestacao(supabase, manifestacao_id: str) -> dict[str, Any] | None:
    """A notificação que a manifestação virou, ou None (caso confirmado antes
    da Fase 2, que não foi importado)."""
    linhas = (
        supabase.table("nsp_notificacoes")
        .select("id, protocolo, estado")
        .eq("manifestacao_id", manifestacao_id)
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


def consultar(supabase, protocolo: str, codigo: str | None, contato: str | None) -> dict[str, str] | None:
    """O que a página de acompanhamento mostra, ou `None` para toda recusa.

    Reusa as conferências da Ouvidoria: o código pelo hash, o contato pelo
    e-mail sem caixa ou pelos dígitos do telefone. A recusa é uma só, para não
    ensinar quais protocolos existem (`ouvidoria_acompanhamento`)."""
    linhas = (
        supabase.table("nsp_notificacoes")
        .select("protocolo, estado, anonimo, codigo_acompanhamento_hash, notificante_contato")
        .eq("protocolo", (protocolo or "").strip().upper())
        .limit(1)
        .execute()
        .data
    )
    caso = linhas[0] if linhas else None
    if caso is None:
        if codigo:
            # A recusa por protocolo inexistente gasta o tempo de uma conferência.
            ouvidoria_acompanhamento._gastar_o_tempo_de_uma_conferencia(codigo)
        return None
    if caso.get("anonimo"):
        if not codigo or not ouvidoria_acompanhamento.codigo_confere(codigo, caso.get("codigo_acompanhamento_hash")):
            return None
    elif not contato or not ouvidoria_acompanhamento.contato_confere(
        contato, {"manifestante_contato": caso.get("notificante_contato")}
    ):
        return None
    return {"protocolo": caso["protocolo"], "estado": ESTADO_PUBLICO.get(caso.get("estado"), RECEBIDA)}


_CAMPOS_DA_LISTA = (
    "id, protocolo, estado, origem, relato, leito_ou_atendimento, setor_id, data_ocorrencia, turno, "
    "hora_aproximada, chegou_ao_paciente, grave_ou_morte, percebido_ou_reclamacao, criado_em, "
    "anonimo, notificante_nome, notificante_contato"
)
# Abaixo do teto de linhas por resposta do PostgREST (1000 no Supabase).
TAMANHO_DA_PAGINA = 500


def _todas_as_linhas(supabase) -> list[dict[str, Any]]:
    """Toda notificação, página a página: a tela promete todos os casos, e uma
    consulta só pararia no teto do PostgREST sem avisar. Um caso que chegue no
    meio empurra os outros uma posição; o id descarta a repetição."""
    linhas: list[dict[str, Any]] = []
    vistas: set[str] = set()
    inicio = 0
    while True:
        pagina = (
            supabase.table("nsp_notificacoes")
            .select(_CAMPOS_DA_LISTA)
            .order("criado_em", desc=True)
            .order("numero", desc=True)
            .range(inicio, inicio + TAMANHO_DA_PAGINA - 1)
            .execute()
            .data
        ) or []
        for linha in pagina:
            if linha["id"] not in vistas:
                vistas.add(linha["id"])
                linhas.append(linha)
        if len(pagina) < TAMANHO_DA_PAGINA:
            return linhas
        inicio += TAMANHO_DA_PAGINA


def listar(supabase, *, com_identidade: bool) -> list[dict[str, Any]]:
    """Todos os casos, do mais novo ao mais velho. A identidade de quem
    notificou só entra quando `com_identidade` (Presidência e Acesso pleno)."""
    linhas = _todas_as_linhas(supabase)
    setor_ids = sorted({linha["setor_id"] for linha in linhas if linha.get("setor_id")})
    setores = (
        {s["id"]: s["nome"] for s in supabase.table("setores").select("id, nome").in_("id", setor_ids).execute().data}
        if setor_ids
        else {}
    )
    casos = []
    for linha in linhas:
        anonimo = linha.pop("anonimo", None)
        nome = linha.pop("notificante_nome", None)
        contato = linha.pop("notificante_contato", None)
        caso = {**linha, "setor": setores.get(linha.get("setor_id"))}
        if com_identidade:
            caso["anonimo"] = bool(anonimo)
            # O caso da Ouvidoria chega sem quem manifestou (issue #1997).
            sem_quem = anonimo or linha.get("origem") == ORIGEM_OUVIDORIA
            caso["notificante"] = None if sem_quem else {"nome": nome, "contato": contato}
        casos.append(caso)
    return casos
