"""As ações da Pendência pela API (ADR 0098, decisão 5; issue #1862).

`POST /pendencias/{id}/acoes` é a única porta que muda estado e prazo, sempre
com anotação. O `PATCH` genérico e as rotas force saem. A gravação vai para a
função do Postgres (`registrar_acao_da_pendencia`, migration 169), que aqui é
um banco de mentira que só aplica o que recebe; a prova da função de verdade
está em `test_pendencia_historico_banco.py`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_supabase_client, require_acesso_reunioes
from app.main import app
from app.routers import pendencias as pendencias_router
from app.services.pendencias_recorte import recorte_das_pendencias

HOJE = date(2026, 11, 19)
ONTEM = HOJE - timedelta(days=1)
AMANHA = HOJE + timedelta(days=1)


@dataclass
class _Result:
    data: list
    count: int | None = None


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []

    def select(self, *_a, **_kw):
        return self

    def eq(self, col, val):
        self._filtros.append(lambda r: r.get(col) == val)
        return self

    def in_(self, col, vals):
        vals = set(vals)
        self._filtros.append(lambda r: r.get(col) in vals)
        return self

    def is_(self, col, val):
        self._filtros.append(lambda r: r.get(col) is None if val == "null" else True)
        return self

    def order(self, *_a, **_kw):
        return self

    def range(self, *_a, **_kw):
        return self

    def execute(self):
        return _Result([dict(r) for r in self._linhas if all(f(r) for f in self._filtros)])


@dataclass
class _Banco:
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)
    participantes: list = field(default_factory=list)
    pendencia_historico: list = field(default_factory=list)
    chamadas: list = field(default_factory=list)

    def table(self, nome):
        if nome == "comentarios_pendencias":
            return _Consulta([])
        if nome == "colegiados":
            return _Consulta([])
        return _Consulta(getattr(self, nome))

    def rpc(self, nome, params):
        self.chamadas.append((nome, params))
        banco = self

        class _Exec:
            def execute(self_inner):  # noqa: N805
                assert nome == "registrar_acao_da_pendencia"
                p = next(x for x in banco.pendencias if x["id_acao"] == params["p_id_acao"])
                p["status"] = params["p_status_novo"]
                if params["p_prazo_novo"]:
                    p["prazo"] = params["p_prazo_novo"]
                banco.pendencia_historico.append(
                    {
                        "id": len(banco.pendencia_historico) + 1,
                        "id_acao": params["p_id_acao"],
                        "comando": params["p_comando"],
                        "anotacao": params["p_anotacao"],
                        "autor_id": params["p_autor_id"],
                        "autor_nome": params["p_autor_nome"],
                        "conta_atraso": params["p_conta_atraso"],
                        "criado_em": "2026-11-19T10:00:00+00:00",
                    }
                )
                return _Result([len(banco.pendencia_historico)])

        return _Exec()


PESSOAS = {
    "resp": {"id": "P_RESP", "nome_completo": "Rita Responsável", "access_profile": "regular"},
    "coresp": {"id": "P_CO", "nome_completo": "Caio Co", "access_profile": "regular"},
    "facil": {"id": "P_FAC", "nome_completo": "Fábio Facilitador", "access_profile": "regular"},
    "admin": {"id": "P_ADM", "nome_completo": "Ana Admin", "access_profile": "super_admin"},
    "outro": {"id": "P_OUT", "nome_completo": "Otto Participante", "access_profile": "regular"},
}


def _banco(status="PENDENTE", prazo=AMANHA) -> _Banco:
    return _Banco(
        pendencias=[
            {
                "id_acao": "A001",
                "id_reuniao": "R1",
                "descricao_acao": "Comprar luvas",
                "responsavel_id": "P_RESP",
                "responsavel_nome": "Rita Responsável",
                "co_responsavel_id": "P_CO",
                "prazo": prazo.isoformat() if prazo else None,
                "status": status,
                "deleted_at": None,
            }
        ],
        reunioes=[{"id_reuniao": "R1", "facilitador_id": "P_FAC", "deleted_at": None}],
        participantes=[{"id": "P_RESP", "is_externo": False}],
    )


@pytest.fixture
def cliente(monkeypatch):
    estado: dict = {"quem": "resp", "banco": _banco()}

    async def _participante(_user, _sb, fields=None):
        return PESSOAS[estado["quem"]]

    async def _recorte(_user, _sb):
        # O recorte pelo vínculo (issue #1863), com a função pura de verdade:
        # o Fábio facilita a R1; o Otto só participou dela.
        quem = estado["quem"]
        return recorte_das_pendencias(
            PESSOAS[quem]["id"],
            super_admin=quem == "admin",
            facilitadas=["R1"] if quem == "facil" else [],
            do_nucleo=[],
            ocultas=[],
        )

    monkeypatch.setattr(pendencias_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(pendencias_router, "get_recorte_das_pendencias", _recorte)
    monkeypatch.setattr(pendencias_router, "hoje_em_brasilia", lambda: HOJE)

    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "email": "x@x"}
    app.dependency_overrides[get_supabase_client] = lambda: estado["banco"]
    app.dependency_overrides[require_acesso_reunioes] = lambda: None
    try:
        yield TestClient(app), estado
    finally:
        app.dependency_overrides.clear()


# ── Nenhuma rota muda Pendência sem anotação ────────────────────────────────


def test_patch_generico_e_rotas_force_da_pendencia_nao_existem(cliente):
    client, _ = cliente
    assert client.patch("/api/pendencias/A001", json={"status": "CONCLUIDO"}).status_code in (404, 405)
    assert client.patch("/api/pendencias/A001/force", json={"status": "CONCLUIDO"}).status_code in (404, 405)
    assert client.request("DELETE", "/api/pendencias/A001/force", json={"reason": "x"}).status_code in (404, 405)


def test_a_unica_escrita_em_pendencia_pela_api_e_a_rota_de_acoes():
    escritas = sorted(
        (caminho, metodo.upper())
        for caminho, metodos in app.openapi()["paths"].items()
        if caminho.startswith("/api/pendencias")
        for metodo in metodos
        if metodo.lower() not in ("get", "head", "options")
    )
    # Comentário é conversa, não muda estado, prazo nem responsável.
    assert [e for e in escritas if "/comentarios" not in e[0]] == [("/api/pendencias/{id_acao}/acoes", "POST")]


# Sem exceção: desde a issue #1866 os lembretes do Núcleo (Pendência sem
# Reunião) também passam pelo comando de ação. Apagar (`deleted_at`) conta como
# mudança: nada apaga Pendência (ADR 0098, decisão 6).
_RE_ESCRITA = re.compile(
    r'table\("pendencias"\)\s*\.\s*update\(\s*\{[^}]*"(status|prazo|responsavel_id|deleted_at)"', re.S
)


def test_codigo_nao_grava_estado_prazo_ou_responsavel_direto_na_pendencia():
    raiz = os.path.join(os.path.dirname(__file__), "..", "app")
    achados = []
    for pasta, _dirs, arquivos in os.walk(raiz):
        for arquivo in arquivos:
            if not arquivo.endswith(".py"):
                continue
            caminho = os.path.join(pasta, arquivo)
            relativo = os.path.relpath(caminho, raiz)
            with open(caminho, encoding="utf-8") as f:
                if _RE_ESCRITA.search(f.read()):
                    achados.append(relativo)
    assert achados == [], f"Gravação de estado, prazo ou responsável fora da função de ações: {achados}"


def test_o_detector_de_escrita_direta_enxerga_a_forma_de_varias_linhas():
    trecho = 'supabase.table("pendencias")\n    .update({"status": "ATRASADO"})\n    .eq("x", 1)'
    assert _RE_ESCRITA.search(trecho)


def test_o_detector_de_escrita_direta_enxerga_o_apagar_da_pendencia():
    trecho = 'supabase.table("pendencias").update({"deleted_at": agora}).eq("id_acao", x)'
    assert _RE_ESCRITA.search(trecho)


# ── A rota de ações ─────────────────────────────────────────────────────────


def test_responsavel_inicia_com_anotacao_e_o_evento_vai_para_o_historico(cliente):
    client, estado = cliente
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "iniciar", "anotacao": "Comecei hoje"})

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "EM_PROGRESSO"
    nome, params = estado["banco"].chamadas[0]
    assert nome == "registrar_acao_da_pendencia"
    assert params["p_anotacao"] == "Comecei hoje"
    assert params["p_autor_id"] == "P_RESP"
    assert params["p_autor_nome"] == "Rita Responsável"
    assert params["p_status_esperado"] == "PENDENTE"


@pytest.mark.parametrize("anotacao", ["", "   "])
def test_acao_sem_anotacao_e_recusada_e_nada_e_gravado(cliente, anotacao):
    client, estado = cliente
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "concluir", "anotacao": anotacao})
    assert r.status_code == 422
    assert estado["banco"].chamadas == []


def test_acao_sem_o_campo_anotacao_e_recusada(cliente):
    client, estado = cliente
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "concluir"})
    assert r.status_code == 422
    assert estado["banco"].chamadas == []


@pytest.mark.parametrize(
    "quem,comando,esperado",
    [
        ("coresp", "concluir", 200),
        ("facil", "cancelar", 200),
        ("facil", "concluir", 403),
        ("resp", "cancelar", 403),
        ("outro", "anotar", 404),
        ("admin", "cancelar", 200),
    ],
)
def test_quem_age_sai_do_vinculo_com_a_pendencia(cliente, quem, comando, esperado):
    client, estado = cliente
    estado["quem"] = quem
    r = client.post("/api/pendencias/A001/acoes", json={"comando": comando, "anotacao": "motivo"})
    assert r.status_code == esperado, r.text


def test_reabrir_pendencia_aberta_e_conflito(cliente):
    client, estado = cliente
    estado["quem"] = "facil"
    r = client.post(
        "/api/pendencias/A001/acoes",
        json={"comando": "reabrir", "anotacao": "voltar", "prazo": AMANHA.isoformat()},
    )
    assert r.status_code == 409


def test_repactuar_antes_do_vencimento_nao_conta_atraso(cliente):
    client, estado = cliente
    novo = (HOJE + timedelta(days=10)).isoformat()
    r = client.post(
        "/api/pendencias/A001/acoes", json={"comando": "repactuar", "anotacao": "fornecedor", "prazo": novo}
    )

    assert r.status_code == 200, r.text
    assert r.json()["prazo"] == novo
    params = estado["banco"].chamadas[0][1]
    assert params["p_prazo_novo"] == novo
    assert params["p_conta_atraso"] is False


def test_repactuar_depois_do_vencimento_conta_atraso_e_o_prazo_novo_vale_na_hora(cliente):
    client, estado = cliente
    estado["banco"] = _banco(prazo=ONTEM)
    novo = (HOJE + timedelta(days=10)).isoformat()
    r = client.post("/api/pendencias/A001/acoes", json={"comando": "repactuar", "anotacao": "atrasou", "prazo": novo})

    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["prazo"] == novo
    assert corpo["atrasada"] is False
    assert corpo["repactuada"] is True
    assert estado["banco"].chamadas[0][1]["p_conta_atraso"] is True


# ── Atrasada é calculada ────────────────────────────────────────────────────


def test_pendencia_aberta_com_prazo_vencido_aparece_atrasada_sem_job(cliente):
    client, estado = cliente
    estado["banco"] = _banco(status="EM_PROGRESSO", prazo=ONTEM)
    corpo = client.get("/api/pendencias/A001").json()
    assert corpo["status"] == "EM_PROGRESSO"
    assert corpo["atrasada"] is True
    assert corpo["situacao"] == "ATRASADO"


def test_o_job_que_marcava_atraso_saiu_do_agendador():
    from app.cron import scheduler

    assert not hasattr(scheduler, "marcar_atrasadas")
    with open(scheduler.__file__, encoding="utf-8") as f:
        assert '"ATRASADO"' not in f.read()


# ── O histórico na tela ─────────────────────────────────────────────────────


def test_historico_vem_em_ordem_com_as_acoes_que_quem_olha_pode_fazer(cliente):
    client, estado = cliente
    estado["banco"].pendencia_historico = [
        {
            "id": 2,
            "id_acao": "A001",
            "comando": "anotar",
            "anotacao": "segunda",
            "autor_nome": "Rita",
            "criado_em": "2026-11-18T10:00:00+00:00",
            "conta_atraso": False,
        },
        {
            "id": 1,
            "id_acao": "A001",
            "comando": "iniciar",
            "anotacao": "primeira",
            "autor_nome": "Rita",
            "criado_em": "2026-11-17T10:00:00+00:00",
            "conta_atraso": False,
        },
    ]
    corpo = client.get("/api/pendencias/A001/historico").json()
    assert [e["anotacao"] for e in corpo["eventos"]] == ["primeira", "segunda"]
    assert corpo["acoes_permitidas"] == ["iniciar", "anotar", "concluir", "repactuar"]


# ── O kit de conhecimento diz o comportamento novo ──────────────────────────


def test_o_texto_de_reunioes_no_kit_diz_o_ciclo_novo_da_pendencia():
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "reunioes.md").read_text(encoding="utf-8")
    assert "## Como a pendência anda" in texto
    assert "Toda mudança pede uma anotação" in texto
    assert "Atrasada não é um estado que alguém marca" in texto
    assert "Repactuar antes do prazo vencer não conta como atraso; depois de vencer, conta" in texto
    assert "Ninguém edita nem apaga uma linha do histórico" in texto
    # O comportamento antigo saiu do texto.
    assert "marcada como a repactuar" not in texto
    assert "antes de o aplicativo marcá-la como atrasada" not in texto
