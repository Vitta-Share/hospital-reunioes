#!/usr/bin/env python3
"""Semeia o Supabase LOCAL com a coordenação de exemplo da página do Canal de
Conduta do manual (issue #1851, PRD #1786).

O portão do Comitê roda no servidor do Next, antes de a página existir, e
pergunta ao backend se a pessoa está no Comitê. Por isso o seed é uma pessoa
só, de verdade no banco local: a coordenação de exemplo do `seed.json`, com a
Participação vigente no Comitê de Conduta e o Termo assinado, na faixa P18510
a P18519, longe das pessoas dos outros roteiros. Os casos, os depoimentos, os
votos e as atas não moram no banco: o roteiro responde no lugar do backend com
o `respostas.py`, e os relatos são os casos fictícios do Anexo B. Nenhum caso
é gravado, nenhum e-mail sai e nada vai à ClickSign. O script recusa qualquer
Supabase que não seja o local.

O login já leva a marca de que a pessoa viu os cinco cartões do primeiro
acesso, para eles não cobrirem o print. Rodar de novo reaproveita o login, a
pessoa e a Participação, sem duplicar.

Uso: python3 scripts/manual/canal-de-conduta/semear.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
SEED = json.loads((AQUI / "seed.json").read_text(encoding="utf-8"))
ENV_LOCAL = AQUI.parents[3] / ".env"
HOJE = datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def credenciais_locais() -> tuple[str, str]:
    """URL e chave de serviço do `.env` local, nunca de produção."""
    env: dict[str, str] = {}
    for linha in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            env[chave] = valor.strip().strip('"')
    url = env.get("SUPABASE_URL", "")
    chave = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if "127.0.0.1" not in url and "localhost" not in url:
        raise SystemExit(f"recusado: '{url}' não é o Supabase local.")
    return url, chave


def cabecalhos(chave: str) -> dict[str, str]:
    return {"apikey": chave, "Authorization": f"Bearer {chave}", "Content-Type": "application/json"}


def pedir(url: str, chave: str, caminho: str, corpo=None, metodo: str = "GET", extra: dict | None = None):
    req = urllib.request.Request(
        f"{url}{caminho}",
        data=json.dumps(corpo).encode() if corpo is not None else None,
        headers={**cabecalhos(chave), **(extra or {})},
        method=metodo,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resposta:
            texto = resposta.read().decode()
            return json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{metodo} {caminho}: {e.code} {e.read().decode()[:300]}") from e


def login_de_exemplo(url: str, chave: str, pessoa: dict) -> str:
    """Cria (ou reaproveita, com a senha do seed) o login da pessoa de exemplo."""
    dados = {"nome": pessoa["nome"], "conduta_apresentacao_vista_em": f"{HOJE.isoformat()}T08:00:00-03:00"}
    corpo = {"email": pessoa["email"], "password": pessoa["senha"], "email_confirm": True, "user_metadata": dados}
    try:
        req = urllib.request.Request(
            f"{url}/auth/v1/admin/users", data=json.dumps(corpo).encode(), headers=cabecalhos(chave)
        )
        with urllib.request.urlopen(req, timeout=20) as resposta:
            return json.load(resposta)["id"]
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        if e.code not in (400, 422) or "already" not in texto:
            raise SystemExit(f"login {pessoa['email']}: {e.code} {texto[:300]}") from e
    pagina = 1
    while True:
        usuarios = pedir(url, chave, f"/auth/v1/admin/users?page={pagina}&per_page=200")["users"]
        for usuario in usuarios:
            if usuario["email"] == pessoa["email"]:
                pedir(
                    url,
                    chave,
                    f"/auth/v1/admin/users/{usuario['id']}",
                    {"password": pessoa["senha"], "user_metadata": dados},
                    "PUT",
                )
                return usuario["id"]
        if not usuarios:
            raise SystemExit(f"login {pessoa['email']} não encontrado depois de criado.")
        pagina += 1


def semear() -> None:
    url, chave = credenciais_locais()
    coordenacao = SEED["coordenacao"]
    linha = {
        "id": coordenacao["id"],
        "nome_completo": coordenacao["nome"],
        "email": coordenacao["email"],
        "cargo": coordenacao["cargo"],
        "role": "coordenador",
        "ativo": True,
        "access_profile": "regular",
        "is_super_admin": False,
        "is_externo": False,
        "auth_user_id": login_de_exemplo(url, chave, coordenacao),
    }
    pedir(url, chave, "/rest/v1/participantes", [linha], "POST", {"Prefer": "resolution=merge-duplicates"})

    comite = pedir(url, chave, "/rest/v1/colegiados?slug=eq.conduta&select=id")
    if not comite:
        raise SystemExit("o banco local não tem o Comitê de Conduta (colegiado 'conduta').")
    filtro = urllib.parse.urlencode(
        {"colegiado_id": f"eq.{comite[0]['id']}", "participante_id": f"eq.{coordenacao['id']}", "select": "id"}
    )
    aberta = pedir(url, chave, f"/rest/v1/participacoes?{filtro}&encerrada_em=is.null")
    participacao = {
        "papel": "coordenacao",
        "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=700)).isoformat(),
        "termo_assinado_em": f"{(HOJE - timedelta(days=29)).isoformat()}T10:00:00-03:00",
    }
    if aberta:
        pedir(url, chave, f"/rest/v1/participacoes?id=eq.{aberta[0]['id']}", participacao, "PATCH")
    else:
        pedir(
            url,
            chave,
            "/rest/v1/participacoes",
            [{**participacao, "colegiado_id": comite[0]["id"], "participante_id": coordenacao["id"]}],
            "POST",
        )
    print("coordenação de exemplo da página do Canal de Conduta pronta.")


if __name__ == "__main__":
    semear()
