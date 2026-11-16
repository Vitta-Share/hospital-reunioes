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
    return hmac.new(SEGREDO.encode(), str(prd).encode(), hashlib.sha256).hexdigest()[
        :20
    ]


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
    assert label["url"].endswith(
        "/repos/pedrorezendefig/hospital-reunioes/issues/1757/labels"
    )
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
    assert set(dados["partes"][0]) == {
        "id",
        "etapa",
        "titulo",
        "muda",
        "vale",
        "saber",
        "pronto",
        "depende",
    }


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


# --- O e-mail: o link com o código que a função de validar aceita ------------


@pytest.fixture
def mac(tmp_path, monkeypatch):
    """A pasta do Mac do Pedro (~/.config/planos-hsm) num diretório de teste."""
    pasta = tmp_path / "planos-hsm"
    (pasta / "site" / ".vercel").mkdir(parents=True)
    (pasta / "segredo").write_text(SEGREDO + "\n", encoding="utf-8")
    (pasta / "site" / ".vercel" / "project.json").write_text(
        '{"projectName":"planos-hsm"}', encoding="utf-8"
    )
    monkeypatch.setenv("PLANOS_HSM_DIR", str(pasta))
    return pasta


def test_rascunho_do_email_leva_o_link_com_o_codigo_que_a_validacao_aceita(mac):
    arquivo = _modulo().email(1757)
    assert RAIZ not in arquivo.parents, (
        "o texto do e-mail traz o código e não pode cair no repositório"
    )
    texto = arquivo.read_text(encoding="utf-8")
    m = re.search(r"https://planos-hsm\.vercel\.app/1757\?c=([0-9a-f]+)", texto)
    assert m, texto
    assert m.group(1) == _hmac(1757)
    r = _validar({"prd": 1757, "c": m.group(1)})
    assert r["status"] == 200
    assert "—" not in texto and "–" not in texto


# --- Publicar: tira o selo antes, deploy de uma cópia fora do repo -----------


@pytest.fixture
def bin_falso(tmp_path):
    """`gh` e `npx` que só anotam; o gh diz que o PRD tem a label se o arquivo existir."""
    pasta = tmp_path / "bin"
    pasta.mkdir()
    log = tmp_path / "log.txt"
    tem_label = tmp_path / "tem-label"
    (pasta / "gh").write_text(
        "#!/bin/sh\n"
        f'echo "gh $*" >> "{log}"\n'
        'case "$*" in\n'
        f'  *"/labels --jq"*) [ -f "{tem_label}" ] && echo "validado:diretor"; echo "type:feature" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    (pasta / "npx").write_text(
        "#!/bin/sh\n"
        f'echo "npx $*" >> "{log}"\n'
        f'(cd "$PWD" && find . -type f | sort | sed "s/^/arquivo /") >> "{log}"\n'
        'echo "https://planos-hsm-abc123.vercel.app"\n',
        encoding="utf-8",
    )
    for f in pasta.iterdir():
        f.chmod(0o755)
    return {
        "path": f"{pasta}{os.pathsep}{os.environ['PATH']}",
        "log": log,
        "tem_label": tem_label,
    }


def _publicar(bin_falso, mac):
    env = {**os.environ, "PATH": bin_falso["path"], "PLANOS_HSM_DIR": str(mac)}
    r = subprocess.run(
        ["python3", str(SCRIPT), "publicar", "1757"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=RAIZ,
    )
    assert r.returncode == 0, r.stderr
    return r, bin_falso["log"].read_text(encoding="utf-8").splitlines()


def test_republicar_tira_a_label_validado_antes_do_deploy(bin_falso, mac):
    bin_falso["tem_label"].touch()
    r, log = _publicar(bin_falso, mac)
    tira = next(i for i, x in enumerate(log) if x.startswith("gh api -X DELETE"))
    assert log[tira].endswith(
        "repos/pedrorezendefig/hospital-reunioes/issues/1757/labels/validado:diretor"
    )
    sobe = next(i for i, x in enumerate(log) if x.startswith("npx"))
    assert tira < sobe
    assert "deploy --prod --yes" in log[sobe]
    assert "https://planos-hsm.vercel.app/1757" in r.stdout


def test_publicar_leva_a_pagina_a_funcao_e_o_vinculo_sem_a_fonte(bin_falso, mac):
    _r, log = _publicar(bin_falso, mac)
    arquivos = {x.removeprefix("arquivo ./") for x in log if x.startswith("arquivo ")}
    assert {
        "1757/index.html",
        "api/validar.js",
        "index.html",
        "vercel.json",
        "logo-hsm.png",
        "HPSimplified_Rg.ttf",
        ".vercel/project.json",
    } <= arquivos
    assert not any(
        a.endswith(("dados.json", "modelo.html", "segredo")) for a in arquivos
    )
    assert not any(x.startswith("gh api -X DELETE") for x in log), (
        "sem a label, não há o que tirar"
    )


# --- Coleta: etapas pela ordem dos bloqueios ---------------------------------


def _fatia(n, estado="open", labels=("ready-for-agent",), bloqueada_por=(), corpo=""):
    return {
        "numero": n,
        "titulo": f"Fatia {n}",
        "estado": estado,
        "labels": list(labels),
        "corpo": corpo,
        "bloqueada_por": list(bloqueada_por),
        "comentarios": [],
    }


CORPO = """## 👔 Para o diretor

**O que muda:** O calendário fica em ordem.

**Por que vale:** Acha a reunião mais rápido.

**O que você precisa saber:**
- A mais cedo vem primeiro.
- O título aparece no mouse.

---

## Critérios de aceite

- [ ] Reuniões às 14h, 8h e 10h aparecem 8h, 10h e 14h.
- [x] O título longo aparece no mouse.
"""


def test_coleta_numera_as_partes_pela_ordem_dos_bloqueios_e_tira_a_humana_fechada():
    fatias = [
        _fatia(10, estado="closed", labels=["ready-for-human"]),
        _fatia(14, bloqueada_por=[11, 12]),
        _fatia(12, bloqueada_por=[11]),
        _fatia(11, bloqueada_por=[10], corpo=CORPO),
        _fatia(13),
    ]
    plano = _modulo().plano(fatias)
    assert [(p["id"], p["issue"], p["etapa"]) for p in plano["partes"]] == [
        (1, 11, 1),
        (2, 13, 1),
        (3, 12, 2),
        (4, 14, 3),
    ]
    assert [p["depende"] for p in plano["partes"]] == [[], [], [1], [1, 3]]
    assert [d["issue"] for d in plano["decididas"]] == [10]
    um = plano["partes"][0]
    assert um["muda"] == "O calendário fica em ordem."
    assert um["vale"] == "Acha a reunião mais rápido."
    assert um["saber"] == ["A mais cedo vem primeiro.", "O título aparece no mouse."]
    assert um["criterios"] == [
        "Reuniões às 14h, 8h e 10h aparecem 8h, 10h e 14h.",
        "O título longo aparece no mouse.",
    ]


# --- A fonte no repositório público, sem o segredo ---------------------------


def test_fonte_dos_planos_fica_no_repo_sem_o_segredo():
    pastas = (PLANOS, SCRIPT.parent.parent)
    arquivos = [f for p in pastas for f in p.rglob("*") if f.is_file()]
    nomes = {f.name for f in arquivos}
    assert {"modelo.html", "validar.js", "vercel.json", "dados.json"} <= nomes
    assert not {"segredo", "link-1757.txt"} & nomes
    assert not any(".vercel" in f.parts for f in arquivos)
    for f in arquivos:
        if f.suffix in {".html", ".js", ".json", ".py", ".md", ".txt", ""}:
            texto = f.read_text(encoding="utf-8")
            # Segredo e código do link são hex longos; nada disso mora na fonte.
            assert not re.search(r"(?<![0-9a-f])[0-9a-f]{20,}(?![0-9a-f])", texto), f
    validar = VALIDAR.read_text(encoding="utf-8")
    assert "process.env.SEGREDO" in validar
