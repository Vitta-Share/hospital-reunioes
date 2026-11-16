"""A Apresentação do PRD (issue #1891): a página que o diretor valida antes do trabalho.

A skill `apresentar-prd` coleta o PRD e as Fatias, monta a página a partir de
`docs/comunicacao/planos/<PRD>/dados.json` e publica no projeto `planos-hsm` da
Vercel. O botão Validar chama `site/api/validar.js`, que confere o código do
link (HMAC do número do PRD com o segredo) e grava no PRD a label
`validado:diretor` e um comentário com o marcador. Estes testes rodam a função
de validar no Node com o `fetch` simulado (nunca o endpoint de produção) e o
script da skill com um `gh` e um `npx` falsos no PATH.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PLANOS = RAIZ / "docs" / "comunicacao" / "planos"
VALIDAR = PLANOS / "site" / "api" / "validar.js"
SEGREDO = "segredo-de-teste-que-nao-vale-nada"

# Roda o handler da Vercel com req e res de mentira e um fetch que só anota.
HARNESS = r"""
const [validar, corpo] = process.argv.slice(1);
const chamadas = [];
global.fetch = async (url, opt) => {
  chamadas.push({ url, method: opt.method, body: opt.body ? JSON.parse(opt.body) : null });
  return { ok: true, status: 200 };
};
const handler = require(validar);
const res = {
  code: 0,
  status(c) { this.code = c; return this; },
  json(j) { console.log(JSON.stringify({ status: this.code, resposta: j, chamadas })); return this; },
};
handler({ method: 'POST', body: JSON.parse(corpo) }, res);
"""


def _hmac(prd: int) -> str:
    """O código do link pela regra da issue: HMAC-SHA256 do número, 20 primeiros hex."""
    return hmac.new(SEGREDO.encode(), str(prd).encode(), hashlib.sha256).hexdigest()[:20]


def _validar(corpo: dict) -> dict:
    if not shutil.which("node"):
        pytest.fail("o teste da função de validar precisa do node no PATH")
    env = {**os.environ, "SEGREDO": SEGREDO, "GITHUB_TOKEN": "token-falso"}
    out = subprocess.run(
        ["node", "-e", HARNESS, str(VALIDAR), json.dumps(corpo)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(out.stdout)


def test_validar_recusa_codigo_errado_sem_tocar_no_github():
    errado = "0" * 20
    assert errado != _hmac(1757)
    r = _validar({"prd": 1757, "c": errado, "observacao": "ok"})
    assert r["status"] == 403
    assert r["resposta"]["ok"] is False
    assert r["chamadas"] == []


def test_validar_com_codigo_certo_grava_label_e_comentario_com_marcador():
    r = _validar({"prd": 1757, "c": _hmac(1757), "observacao": "Pode seguir."})
    assert r["status"] == 200
    assert r["resposta"]["ok"] is True
    label, comentario = r["chamadas"]
    assert label["method"] == "POST"
    assert label["url"].endswith("/repos/pedrorezendefig/hospital-reunioes/issues/1757/labels")
    assert label["body"] == {"labels": ["validado:diretor"]}
    assert comentario["method"] == "POST"
    assert comentario["url"].endswith("/issues/1757/comments")
    marcador = re.match(
        r"<!-- validacao-diretor: (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z) -->\n",
        comentario["body"]["body"],
    )
    assert marcador, comentario["body"]["body"]
    assert "Pode seguir." in comentario["body"]["body"]


def test_codigo_de_um_prd_nao_vale_para_outro():
    r = _validar({"prd": 1758, "c": _hmac(1757)})
    assert r["status"] == 403
    assert r["chamadas"] == []


# --- O script da skill -------------------------------------------------------

SCRIPT = RAIZ / ".claude" / "skills" / "apresentar-prd" / "scripts" / "apresentar.py"
DADOS_1757 = PLANOS / "1757" / "dados.json"


def _modulo():
    spec = importlib.util.spec_from_file_location("apresentar", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dados_1757() -> dict:
    return json.loads(DADOS_1757.read_text(encoding="utf-8"))


def _dados_da_pagina(html: str) -> dict:
    m = re.search(r"const DADOS = (.*?);\n", html)
    assert m, "a página não traz os dados do plano"
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_pagina_do_1757_tem_a_estrutura_da_referencia():
    html = _modulo().montar(_dados_1757())
    # O que a primeira Apresentação tem e a página precisa manter.
    for marca in (
        'src="/logo-hsm.png"',
        'url("/HPSimplified_Rg.ttf")',
        'As pendências ganham histórico, <span class="hi">e o painel passa a cobrar.</span>',
        "O que você já decidiu",
        "Nas suas respostas de 16/11",
        "Ver a ordem das etapas",
        'id="etapas"',
        'id="detalhe"',
        "Fica de fora",
        'id="validar-b"',
        "fetch('/api/validar'",
    ):
        assert marca in html, marca
    assert re.search(r'data-conta="20">0</div><div class="r">partes<', html)
    dados = _dados_da_pagina(html)
    assert dados["prd"] == 1757
    assert len(dados["etapas"]) == 7
    assert len(dados["partes"]) == 20
    # Só o que a página usa vai embutido: nada de número de issue escondido.
    assert set(dados["partes"][0]) == {"id", "etapa", "titulo", "muda", "vale", "saber", "pronto", "depende"}


def test_rodape_traz_a_versao_do_app():
    pacote = RAIZ / "hospital-reunioes" / "frontend" / "package.json"
    versao = json.loads(pacote.read_text(encoding="utf-8"))["version"]
    html = _modulo().montar(_dados_1757())
    esperado = (
        r"<footer>Reuniões · Hospital São Matheus · apresentação do plano · "
        rf"\w+ de \d{{4}} · versão {re.escape(versao)} do app</footer>"
    )
    assert re.search(esperado, html)


@pytest.mark.parametrize(
    ("onde", "texto"),
    [
        ("resumo", "Um plano — em etapas."),
        ("parte", "Um plano – em etapas."),
        ("resumo", "Esta parte fecha a #1860."),
        ("parte", "Esta parte fecha a #1860."),
        ("resumo", "Sobe no próximo deploy."),
        ("parte", "Muda a migration do banco."),
        ("parte", "Um endpoint novo."),
        ("resumo", "Tudo no Supabase."),
    ],
)
def test_montar_recusa_travessao_numero_de_issue_e_palavra_tecnica(onde, texto):
    dados = _dados_1757()
    if onde == "resumo":
        dados["resumo"] = texto
    else:
        dados["partes"][3]["muda"] = texto
    with pytest.raises(ValueError):
        _modulo().montar(dados)
