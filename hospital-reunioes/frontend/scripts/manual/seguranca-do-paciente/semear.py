#!/usr/bin/env python3
"""Semeia o Supabase LOCAL com a pessoa de exemplo da página de Segurança do
Paciente do manual (issue #1780, PRD #1764).

O módulo abre pela permissão efetiva do servidor (ADR 0095), então o seed é
uma pessoa só: a Presidência de exemplo do `seed.json`, com Acesso pleno ao
NSP, na faixa P17800 a P17809, longe das pessoas dos outros roteiros. Os
membros, os documentos, as reuniões e as atas não moram no banco: o roteiro
responde no lugar do backend com o `respostas.py`, nenhuma ata chega à IA e
nenhum envelope sai para assinatura. Nada aqui é gente de verdade, e o script
recusa qualquer Supabase que não seja o local.

A pessoa entra direto pela API REST com a chave de serviço; rodar de novo
reaproveita o login e devolve a senha do seed, sem duplicar.

Uso: python3 scripts/manual/seguranca-do-paciente/semear.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SEED = json.loads((AQUI / "seed.json").read_text(encoding="utf-8"))
ENV_LOCAL = AQUI.parents[3] / ".env"


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


def login_de_exemplo(url: str, chave: str, email: str, senha: str, nome: str) -> str:
    """Cria (ou reaproveita, com a senha do seed) o login da pessoa de exemplo.
    O nome vai no cadastro do login para o topo da tela mostrar o nome, e não o e-mail."""
    dados = {"nome": nome}
    corpo = json.dumps({"email": email, "password": senha, "email_confirm": True, "user_metadata": dados}).encode()
    try:
        req = urllib.request.Request(f"{url}/auth/v1/admin/users", data=corpo, headers=cabecalhos(chave))
        with urllib.request.urlopen(req, timeout=20) as resposta:
            return json.load(resposta)["id"]
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        if e.code not in (400, 422) or "already" not in texto:
            raise SystemExit(f"login {email}: {e.code} {texto[:300]}") from e
    pagina = 1
    while True:
        busca = urllib.request.Request(
            f"{url}/auth/v1/admin/users?page={pagina}&per_page=200", headers=cabecalhos(chave)
        )
        with urllib.request.urlopen(busca, timeout=20) as resposta:
            usuarios = json.load(resposta)["users"]
        for usuario in usuarios:
            if usuario["email"] == email:
                troca = urllib.request.Request(
                    f"{url}/auth/v1/admin/users/{usuario['id']}",
                    data=json.dumps({"password": senha, "user_metadata": dados}).encode(),
                    headers=cabecalhos(chave),
                    method="PUT",
                )
                urllib.request.urlopen(troca, timeout=20).close()
                return usuario["id"]
        if not usuarios:
            raise SystemExit(f"login {email} não encontrado depois de criado.")
        pagina += 1


def semear() -> None:
    url, chave = credenciais_locais()
    presidencia = SEED["presidencia"]
    linha = {
        "id": presidencia["id"],
        "nome_completo": presidencia["nome"],
        "email": presidencia["email"],
        "cargo": presidencia["cargo"],
        "role": "coordenador",
        "ativo": True,
        "access_profile": "regular",
        "is_super_admin": False,
        "is_externo": False,
        # O Acesso pleno abre todas as telas do módulo, como a Presidência com
        # o Termo assinado, sem precisar de Participação no banco.
        "perfil_nsp": "acesso_pleno",
        "auth_user_id": login_de_exemplo(
            url, chave, presidencia["email"], presidencia["senha"], presidencia["nome"]
        ),
    }
    req = urllib.request.Request(
        f"{url}/rest/v1/participantes",
        data=json.dumps([linha]).encode(),
        headers={**cabecalhos(chave), "Prefer": "resolution=merge-duplicates"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=20).close()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"participantes: {e.code} {e.read().decode()[:300]}") from e
    print("pessoa de exemplo da página de Segurança do Paciente pronta.")


if __name__ == "__main__":
    semear()
