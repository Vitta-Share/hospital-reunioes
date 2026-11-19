#!/usr/bin/env python3
"""Semeia o Supabase LOCAL com os dados de exemplo da página do Início do
manual (issue #1947, ADR 0094, decisão 5) e guarda os prints do dado real.

Tudo vem do `seed.json` ao lado: a Facilitadora de exemplo e as três pessoas
que respondem a ela, na faixa P19470 a P19479, longe das pessoas dos outros
roteiros (o `merge-duplicates` reescreve a linha inteira de quem tem o mesmo
id). A Reunião passada, conduzida por ela, solta as Pendências: as dela fazem
a Minha Fila, as das outras fazem o Quem responde a você. A Reunião futura vai
para as Próximas Reuniões. O prazo de cada Pendência e o último acesso de cada
pessoa são dias contados a partir de hoje, para o print sair igual em qualquer
dia.

Nada aqui é gente de verdade, e o script recusa qualquer Supabase que não seja
o local. As linhas entram direto pela API REST com a chave de serviço; rodar
de novo devolve tudo ao estado semeado, sem duplicar.

Uso: python3 scripts/manual/inicio/semear.py
     python3 scripts/manual/inicio/semear.py --guarda <textos.json>
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SEED = json.loads((AQUI / "seed.json").read_text(encoding="utf-8"))
ENV_LOCAL = AQUI.parents[3] / ".env"


# --------------------------------------------------------------------------
# A guarda do dado real
# --------------------------------------------------------------------------


def nomes_de_fora_no_texto(texto: str, nomes_de_fora: list[str]) -> list[str]:
    """Os nomes de fora do seed que aparecem no texto de um print.

    A conta é em casefold: o app põe título, botão e etiqueta em caixa alta pelo
    CSS, e o texto lido da tela já vem transformado. Nome de uma palavra só fica
    de fora, porque casaria com qualquer texto da tela.
    """
    tela = texto.casefold()
    return sorted({n for n in nomes_de_fora if len(n.split()) >= 2 and n.casefold() in tela})


# --------------------------------------------------------------------------
# O banco local
# --------------------------------------------------------------------------


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


def rest(url: str, chave: str, caminho: str, metodo: str = "GET", corpo=None, prefer=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    extra = {"Prefer": prefer} if prefer else {}
    req = urllib.request.Request(
        f"{url}/rest/v1/{caminho}", data=dados, headers={**cabecalhos(chave), **extra}, method=metodo
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resposta:
            texto = resposta.read().decode()
            return json.loads(texto) if texto.strip() else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{metodo} {caminho}: {e.code} {e.read().decode()[:300]}") from e


def rest_tudo(url: str, chave: str, caminho: str, por_pagina: int = 500) -> list:
    """Todas as linhas de um GET: o PostgREST corta cada resposta sem aviso."""
    linhas: list = []
    while True:
        pagina = rest(url, chave, f"{caminho}&limit={por_pagina}&offset={len(linhas)}")
        linhas.extend(pagina)
        if len(pagina) < por_pagina:
            return linhas


def login_de_exemplo(url: str, chave: str, email: str, senha: str) -> str:
    """Cria (ou reaproveita, com a senha do seed) o login da pessoa de exemplo."""
    corpo = json.dumps({"email": email, "password": senha, "email_confirm": True}).encode()
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
                    data=json.dumps({"password": senha}).encode(),
                    headers=cabecalhos(chave),
                    method="PUT",
                )
                urllib.request.urlopen(troca, timeout=20).close()
                return usuario["id"]
        if not usuarios:
            raise SystemExit(f"login {email} não encontrado depois de criado.")
        pagina += 1


def dia(delta: int) -> str:
    return (dt.date.today() + dt.timedelta(days=delta)).isoformat()


def semear() -> None:
    url, chave = credenciais_locais()
    facilitadora = SEED["facilitadora"]
    todas = [facilitadora, *SEED["pessoas"]]

    # Só a Facilitadora entra no app: as outras pessoas não precisam de login.
    rest(
        url,
        chave,
        "participantes",
        "POST",
        [
            {
                "id": p["id"],
                "nome_completo": p["nome"],
                "email": p["email"],
                "cargo": p["cargo"],
                "setor": p["setor"],
                "ativo": True,
                "access_profile": "regular",
                "is_super_admin": False,
                "is_externo": False,
                "auth_user_id": login_de_exemplo(url, chave, p["email"], p["senha"]) if p is facilitadora else None,
            }
            for p in todas
        ],
        prefer="resolution=merge-duplicates",
    )

    reunioes = SEED["reunioes"].values()
    rest(
        url,
        chave,
        "reunioes",
        "POST",
        [
            {
                "id_reuniao": r["id"],
                "titulo": r["titulo"],
                "data": dia(r["data"]),
                "hora_inicio": r["hora_inicio"],
                "hora_fim": r["hora_fim"],
                "tipo": "Coordenação",
                "facilitador_id": r["facilitador"],
                "setor": facilitadora["setor"],
                "objetivo": "Acompanhar os indicadores de qualidade e as ações combinadas.",
                "status_ata": r["status_ata"],
                "fonte": "MOCK",
                "deleted_at": None,
            }
            for r in reunioes
        ],
        prefer="resolution=merge-duplicates",
    )
    for r in reunioes:
        ja_estao = {
            linha["participante_id"]
            for linha in rest(url, chave, f"reuniao_participantes?id_reuniao=eq.{r['id']}&select=participante_id")
        }
        novos = [{"id_reuniao": r["id"], "participante_id": p["id"]} for p in todas if p["id"] not in ja_estao]
        if novos:
            rest(url, chave, "reuniao_participantes", "POST", novos)

    por_id = {p["id"]: p for p in todas}
    passada = SEED["reunioes"]["passada"]["id"]
    rest(
        url,
        chave,
        "pendencias",
        "POST",
        [
            {
                "id_acao": p["id"],
                "id_reuniao": passada,
                "descricao_acao": p["descricao"],
                "responsavel_id": p["responsavel"],
                "co_responsavel_id": None,
                "responsavel_nome": por_id[p["responsavel"]]["nome"],
                "cargo": por_id[p["responsavel"]]["cargo"],
                "prazo": dia(p["prazo"]),
                "meta_entregavel": p["entregavel"],
                "status": p["status"],
                "created_at": f"{dia(p['aberta'])}T12:00:00+00:00",
                "deleted_at": None,
            }
            for p in SEED["pendencias"]
        ],
        prefer="resolution=merge-duplicates",
    )

    # O Registro de acesso (ADR 0104, decisão 10): o último dia de cada pessoa.
    for p in SEED["pessoas"]:
        rest(url, chave, f"registro_de_acesso?participante_id=eq.{p['id']}", "DELETE")
        if p["ultimo_acesso"] is not None:
            rest(
                url,
                chave,
                "registro_de_acesso",
                "POST",
                [{"participante_id": p["id"], "dia": dia(p["ultimo_acesso"])}],
            )

    print("dados de exemplo da página do Início prontos.")


def nomes_de_fora() -> list[str]:
    """Os nomes e títulos do banco local que o seed não pôs lá."""
    url, chave = credenciais_locais()
    pessoas_do_seed = {SEED["facilitadora"]["id"], *(p["id"] for p in SEED["pessoas"])}
    reunioes_do_seed = {r["id"] for r in SEED["reunioes"].values()}
    pessoas = rest_tudo(url, chave, "participantes?select=id,nome_completo&order=id")
    reunioes = rest_tudo(url, chave, "reunioes?select=id_reuniao,titulo&order=id_reuniao")
    return [p["nome_completo"] for p in pessoas if p["id"] not in pessoas_do_seed and p.get("nome_completo")] + [
        r["titulo"] for r in reunioes if r["id_reuniao"] not in reunioes_do_seed and r.get("titulo")
    ]


def guardar(arquivo_dos_textos: str) -> int:
    """Confere o texto de cada print. Devolve 1 quando algum mostra dado de fora."""
    textos = json.loads(Path(arquivo_dos_textos).read_text(encoding="utf-8"))
    de_fora = nomes_de_fora()
    recusados = 0
    for print_ in textos:
        achados = nomes_de_fora_no_texto(print_["texto"], de_fora)
        if achados:
            recusados += 1
            print(
                f"{print_['arquivo']}: a tela mostra {', '.join(achados)}, que não é dado de exemplo. "
                "O repositório é público: o print não sai.",
                file=sys.stderr,
            )
    return 1 if recusados else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--guarda"]:
        sys.exit(guardar(sys.argv[2]))
    semear()
