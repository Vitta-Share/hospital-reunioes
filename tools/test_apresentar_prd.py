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
