"""O convite do apurador designado e do membro da CIPA, dentro do caso
(issue #1825, ADR 0097, decisão 12; especificação, seções 3.2, 6.4 e 10).

Quem convida é a coordenação, nos casos da fila comum, ou o Grupo Especial, no
caso dele (decisão 17 do diretor). O super admin não participa nem é avisado:
o convite não passa pela administração, não grava no registro dela e não
avisa ninguém além do convidado.

Quem não tem login ganha um cadastro mínimo, só com nome e e-mail, sem papel
nas Reuniões e sem perfil de módulo nenhum (ADR 0007, como o login que nasce
pelo POPs). O que abre o caso é a atribuição do convite, e ela só vale com o
termo de confidencialidade assinado (`acesso`).

O e-mail do convite não leva protocolo, nome nem trecho de relato: diz que há
um convite e aponta para o aplicativo.
"""

from __future__ import annotations

import logging
import re

from app.config import settings
from app.dependencies import foi_desligado
from app.services import auth_provisioning
from app.services.conduta import assinaturas, trilha
from app.services.conduta.membros import nomes
from app.services.conduta.portao import CasoAberto
from app.services.conduta.triagem import AcaoRecusadaError
from app.services.email_service import _enviar_email, jinja_env

logger = logging.getLogger(__name__)

PAPEIS = {"apurador": "Apurador designado", "cipa": "Membro da CIPA"}
# O `role` do login, só para o cadastro do provedor de login. Não dá acesso.
ROLE_DO_LOGIN = "convidado_do_canal"

SO_QUEM_CONVIDA = "Só a coordenação, nos casos da fila comum, ou o Grupo Especial, no caso dele, convida."
SEM_NOME = "Esta pessoa ainda não tem cadastro. Informe o nome completo dela."
DESLIGADA = "Esta pessoa está desligada no cadastro do hospital."
CITADA = "Esta pessoa é citada neste caso e não pode ser convidada."
JA_TEM_ACESSO = "Esta pessoa já assinou o termo e tem acesso a este caso."
FALHA_DO_LOGIN = "O login do convidado não foi criado agora. Tente de novo em instantes."
FALHA_DO_TERMO = "O termo não foi gerado agora. Convide de novo a mesma pessoa para reenviar."

TITULO_DO_EMAIL = "Convite do Comitê de Conduta"
FRASE_DO_EMAIL = (
    "O Comitê de Conduta do Hospital São Matheus convidou você para atuar num caso. O termo de "
    "confidencialidade chega a este e-mail pela ClickSign, e o caso só abre depois que você assinar. "
    "Para entrar no aplicativo, use este e-mail. Se ainda não tem senha, toque em Esqueci a senha na "
    "tela de entrada e crie a sua."
)


def pode_convidar(aberto: CasoAberto) -> bool:
    """A coordenação vigente num caso da fila comum, ou quem é do Grupo
    Especial daquele caso."""
    if aberto.caso.get("rota") == "comum" and aberto.pessoa.papel == "coordenacao" and aberto.pessoa.termo_valido:
        return True
    return any(a.get("motivo") == "grupo_especial" and not a.get("revogada_em") for a in aberto.atribuicoes)


# ---------------------------------------------------------------------------
# A pessoa: achada pelo e-mail, ou o cadastro mínimo
# ---------------------------------------------------------------------------


def _pessoa_do_email(supabase, email: str) -> dict | None:
    # `ilike` acha o e-mail gravado com outra caixa; a comparação exata fica
    # aqui, porque `_` e `%` são curinga no `ilike`.
    linhas = (
        supabase.table("participantes")
        .select("id, nome_completo, email, ativo, auth_user_id")
        .ilike("email", email)
        .execute()
        .data
    ) or []
    return next((p for p in linhas if (p.get("email") or "").strip().lower() == email), None)


def _proximo_id(supabase) -> str:
    """O mesmo P001, P002... da administração."""
    linhas = supabase.table("participantes").select("id").order("id", desc=True).limit(1).execute().data or []
    numero = int(re.sub(r"[^0-9]", "", linhas[0]["id"]) or "0") if linhas else 0
    return f"P{numero + 1:03d}"


def _cadastro_minimo(supabase, nome: str, email: str) -> dict:
    """Nome e e-mail, sem cargo, sem papel nas Reuniões e sem perfil de
    módulo: o convite é o único acesso da pessoa."""
    linha = {
        "id": _proximo_id(supabase),
        "nome_completo": nome,
        "email": email,
        "cargo": None,
        "role": None,
        "access_profile": None,
        "is_super_admin": False,
        "ativo": True,
    }
    return supabase.table("participantes").insert(linha).execute().data[0]


def _dar_login(supabase, pessoa: dict) -> dict:
    """O login de quem não tinha. Ele nasce sem papel nas Reuniões (ADR 0007),
    e a senha é criada pela própria pessoa, pelo Esqueci a senha."""
    auth_uid = auth_provisioning.provision_auth_user(
        supabase, pessoa.get("nome_completo") or "", pessoa["email"], ROLE_DO_LOGIN
    )
    if not auth_uid:
        raise AcaoRecusadaError(503, FALHA_DO_LOGIN)
    campos = {"auth_user_id": auth_uid, "access_profile": None}
    supabase.table("participantes").update(campos).eq("id", pessoa["id"]).execute()
    return {**pessoa, **campos}


def _citada(supabase, caso_id: str, participante_id: str) -> bool:
    return bool(
        supabase.table("conduta_citados")
        .select("id")
        .eq("caso_id", caso_id)
        .eq("participante_id", participante_id)
        .limit(1)
        .execute()
        .data
    )


def _convite_aberto(supabase, caso_id: str, participante_id: str) -> dict | None:
    linhas = (
        supabase.table("conduta_atribuicoes")
        .select("*")
        .eq("caso_id", caso_id)
        .eq("participante_id", participante_id)
        .in_("motivo", list(assinaturas.MOTIVOS_DO_CONVITE))
        .is_("revogada_em", "null")
        .execute()
        .data
    ) or []
    return linhas[0] if linhas else None


# ---------------------------------------------------------------------------
# O convite
# ---------------------------------------------------------------------------


def convidar(supabase, aberto: CasoAberto, *, email: str, nome: str, motivo: str) -> dict:
    """Atribui a pessoa ao caso, ainda sem acesso, e devolve a pessoa e a
    atribuição. Convidar de novo quem ainda não assinou só registra o reenvio:
    o termo novo sai em `enviar_termo`."""
    if not pode_convidar(aberto):
        raise AcaoRecusadaError(403, SO_QUEM_CONVIDA)
    caso_id = aberto.caso["id"]
    email = email.strip().lower()
    pessoa = _pessoa_do_email(supabase, email)
    if pessoa is None:
        if not nome.strip():
            raise AcaoRecusadaError(422, SEM_NOME)
        pessoa = _cadastro_minimo(supabase, nome.strip(), email)
    elif foi_desligado(pessoa):
        raise AcaoRecusadaError(409, DESLIGADA)
    elif _citada(supabase, caso_id, pessoa["id"]):
        raise AcaoRecusadaError(409, CITADA)
    if not pessoa.get("auth_user_id"):
        pessoa = _dar_login(supabase, pessoa)
    atribuicao = _convite_aberto(supabase, caso_id, pessoa["id"])
    if atribuicao and atribuicao.get("termo_assinado_em"):
        raise AcaoRecusadaError(409, JA_TEM_ACESSO)
    if atribuicao:
        trilha.registrar(supabase, caso_id, aberto.autor_id, "convite", f"termo reenviado a {pessoa['id']}")
    else:
        papel = PAPEIS[motivo].lower()
        trilha.registrar(supabase, caso_id, aberto.autor_id, "convite", f"{papel} convidado: {pessoa['id']}")
        atribuicao = (
            supabase.table("conduta_atribuicoes")
            .insert({"caso_id": caso_id, "participante_id": pessoa["id"], "motivo": motivo})
            .execute()
            .data
        )[0]
    return {"pessoa": pessoa, "atribuicao": atribuicao}


def enviar_termo(supabase, convite: dict) -> str | None:
    """Gera e envia o termo do convidado. O convite já está gravado: a falha
    vira o aviso da resposta."""
    atribuicao = convite["atribuicao"]
    try:
        papel = PAPEIS.get(atribuicao["motivo"], "Convidado")
        return assinaturas.enviar_termo_do_convidado(supabase, atribuicao["caso_id"], convite["pessoa"], papel).get(
            "erro"
        )
    except Exception:  # noqa: BLE001 (o convite não se desfaz por falha do termo)
        logger.exception("Termo do convidado da atribuição %s não gerado", atribuicao.get("id"))
        return FALHA_DO_TERMO


def convites_do_caso(supabase, caso_id: str) -> list[dict]:
    """Quem foi convidado para o caso e em que pé está o termo de cada um."""
    linhas = (
        supabase.table("conduta_atribuicoes")
        .select("*")
        .eq("caso_id", caso_id)
        .in_("motivo", list(assinaturas.MOTIVOS_DO_CONVITE))
        .is_("revogada_em", "null")
        .execute()
        .data
    ) or []
    if not linhas:
        return []
    nome_de = nomes(supabase, [linha["participante_id"] for linha in linhas])
    enviados = assinaturas.termos_enviados_do_caso(supabase, caso_id)
    return [
        {
            "participante_id": linha["participante_id"],
            "nome": nome_de.get(linha["participante_id"]),
            "motivo": linha["motivo"],
            "papel": PAPEIS.get(linha["motivo"], linha["motivo"]),
            "termo": "assinado"
            if linha.get("termo_assinado_em")
            else ("aguardando_assinatura" if linha["participante_id"] in enviados else "nao_enviado"),
        }
        for linha in linhas
    ]


def enviar_email_do_convite(email: str) -> None:
    """Um e-mail só, para o convidado, sem nada do caso. Recebe só o endereço,
    e por isso não tem como citar nome, protocolo ou relato. Best-effort."""
    try:
        from app.services.email_constants import get_logo_data_uri

        link = f"{settings.frontend_url}/comite-de-conduta"
        html = jinja_env.get_template("email_conduta_aviso.html").render(
            frase=FRASE_DO_EMAIL, link=link, logo_base64=get_logo_data_uri()
        )
        texto = f"{FRASE_DO_EMAIL}\n\nPara entrar: {link}\n"
        _enviar_email(email, TITULO_DO_EMAIL, html, texto, endereco_fora_do_log=True)
    except Exception as erro:  # noqa: BLE001
        logger.warning("[conduta_convites] E-mail do convite não saiu: %s", erro)
