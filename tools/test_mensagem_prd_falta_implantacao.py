"""O que falta para usar, na mensagem do PRD entregue (issue #2213, ADR 0111, decisão 11).

O `/mensagem-prd` roda `mensagem-prd/scripts/falta_implantacao.py <PRD>`: o
script pede à ponte os Pedidos de implantação abertos da Demanda do PRD e
imprime a linha "Para começar a usar, falta: ..." com o Assunto de cada um.
Sem Pedido aberto (ou PRD sem Demanda), não imprime nada e a mensagem fica
como era.

O script roda como o agente roda, contra um app falso num servidor HTTP local.
O app de verdade não entra no teste.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SKILL = RAIZ / ".claude" / "skills" / "mensagem-prd"
SCRIPT = SKILL / "scripts" / "falta_implantacao.py"

CHAVE = "chave-falsa-do-teste-2213"
PRD = "2205"
ROTA = f"/api/automacao/tecnologia/projetos/hospital/issues/{PRD}/implantacao"


@pytest.fixture
def app_falso():
    """`estado["pedidos"]` é o que a rota devolve; `estado["status"]` muda a
    resposta dela; `pedidos` guarda cada chamada, com a chave que chegou."""
    chamadas: list[dict] = []
    estado: dict = {"status": 200, "pedidos": []}

    class _Rota(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            chamadas.append({"caminho": self.path, "chave": self.headers.get("X-API-Key")})
            if self.path != ROTA or estado["status"] != 200:
                self.send_response(404 if self.path != ROTA else estado["status"])
                self.end_headers()
                self.wfile.write(b'{"detail": "recusado"}')
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"pedidos": estado["pedidos"]}).encode())

        def log_message(self, *_a):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), _Rota)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_port}/api", chamadas, estado
    servidor.shutdown()


def rodar(base: str, prd: str = PRD) -> subprocess.CompletedProcess:
    ambiente = {**os.environ, "HOSPITAL_API_URL": base, "TECNOLOGIA_AUTOMACAO_API_KEY": CHAVE}
    return subprocess.run([sys.executable, str(SCRIPT), prd], capture_output=True, text=True, env=ambiente)


def test_com_pedido_de_implantacao_aberto_imprime_a_linha_do_que_falta(app_falso):
    base, chamadas, estado = app_falso
    estado["pedidos"] = [
        {"id": "a1", "assunto": "testar o anonimato do Canal de Conduta"},
        {"id": "b2", "assunto": "treinar a recepção"},
        {"id": "c3", "assunto": "divulgar o Canal no hospital"},
    ]

    feito = rodar(base)

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == (
        "Para começar a usar, falta: testar o anonimato do Canal de Conduta, "
        "treinar a recepção e divulgar o Canal no hospital.\n"
    )
    assert chamadas == [{"caminho": ROTA, "chave": CHAVE}]


def test_com_um_pedido_so_a_linha_nao_tem_juncao(app_falso):
    base, _, estado = app_falso
    estado["pedidos"] = [{"id": "a1", "assunto": "testar o anonimato do Canal de Conduta"}]

    feito = rodar(base)

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == "Para começar a usar, falta: testar o anonimato do Canal de Conduta.\n"


def test_sem_pedido_de_implantacao_aberto_nao_imprime_nada(app_falso):
    base, chamadas, _ = app_falso

    feito = rodar(base)

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == ""
    assert chamadas == [{"caminho": ROTA, "chave": CHAVE}]


def test_prd_sem_demanda_no_app_nao_imprime_nada(app_falso):
    base, _, _ = app_falso

    feito = rodar(base, prd="9999")

    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == ""


def test_app_que_nao_responde_sai_1_com_o_motivo_e_sem_a_linha(app_falso):
    """A falha não pode passar por "nada falta": sai 1, e quem chama avisa o
    Pedro em vez de mandar a mensagem como se a entrega estivesse pronta."""
    base, _, estado = app_falso
    estado["status"] = 503

    feito = rodar(base)

    assert feito.returncode == 1
    assert feito.stdout == ""
    assert "ponte está desligada" in feito.stderr
    assert CHAVE not in feito.stderr


def test_a_skill_roda_o_script_e_poe_a_linha_antes_do_fecho():
    texto = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "python3 .claude/skills/mensagem-prd/scripts/falta_implantacao.py <PRD>" in texto
    assert '"Para começar a usar, falta:"' in texto
