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
    """Grava a notificação e devolve o recibo: o protocolo e, na anônima, o
    código de acompanhamento, que não fica guardado em lugar nenhum."""
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
    recibo: dict[str, Any] = {"protocolo": gravada["protocolo"], "criado_em": gravada.get("criado_em")}
    if codigo:
        recibo["codigo_acompanhamento"] = codigo
    return recibo
