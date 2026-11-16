"""A Agenda regulatória do Núcleo (issue #1779, PRD #1764, ADR 0095).

O que a issue promete, um bloco por critério de aceite:

1. a Presidência edita, inclui e desativa a lista (a carga inicial é da
   migration, conferida em `test_seguranca_do_paciente_agenda_migration.py`);
2. o job diário cria o lembrete como Pendência da Presidência, uma vez por
   ocorrência, e nenhum e-mail sai;
3. registrar o resultado guarda o histórico, conclui o lembrete e avança a
   próxima data pela periodicidade;
4. o job não chama IA.

E o que mais pode vazar: o super admin sem papel no Núcleo é recusado em toda
rota da agenda (decisão 4), pelo código e pelo corpo.

O banco é um dublê em memória. Nenhum nome, registro ou e-mail de pessoa real:
as pessoas daqui são de teste. As datas saem de `hoje_em_sao_paulo()` ou de um
dia fixo.
"""

from __future__ import annotations

import inspect
import os
import sys
import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.cron import scheduler  # noqa: E402
from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_agenda as agenda_router  # noqa: E402
from app.services.seguranca_do_paciente import agenda  # noqa: E402
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo  # noqa: E402

ROTA = "/api/nsp/agenda"
RECUSA_DO_CONTEUDO = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}

HOJE = hoje_em_sao_paulo()
DIA = date(2026, 11, 16)
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}

# A chave única de cada tabela, como a migration declara.
_UNICAS = {
    "pendencias": ("id_acao",),
    "nsp_agenda_ocorrencias": ("item_id", "data_prevista"),
}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


# ═══════════════════════════════════════════════════════════════════════════
# O dublê do banco
# ═══════════════════════════════════════════════════════════════════════════


class _Consulta:
    def __init__(self, banco: _Banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._linhas = banco.tabelas.setdefault(nome, [])
        self._filtros: list = []
        self._ordem: tuple[str, bool] | None = None
        self._teto: int | None = None
        self._acao = "select"
        self._valores: Any = None

    def select(self, *_a, **_kw):
        return self

    def insert(self, valores):
        self._acao, self._valores = "insert", valores
        return self

    def update(self, valores):
        self._acao, self._valores = "update", valores
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        self._filtros.append(lambda linha: linha.get(coluna) in list(valores))
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) <= str(valor))
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) >= str(valor))
        return self

    def order(self, coluna, desc=False, **_kw):
        self._ordem = (coluna, desc)
        return self

    def limit(self, n):
        self._teto = n
        return self

    def execute(self):
        self._banco.escritas.append((self._acao, self._nome)) if self._acao != "select" else None
        if self._acao == "insert":
            return SimpleNamespace(data=self._inserir())
        casam = [linha for linha in self._linhas if all(f(linha) for f in self._filtros)]
        if self._acao == "update":
            for linha in casam:
                linha.update(self._valores)
            return SimpleNamespace(data=[dict(linha) for linha in casam])
        casam = [dict(linha) for linha in casam]
        if self._ordem:
            coluna, desc = self._ordem
            casam.sort(key=lambda linha: (linha.get(coluna) is None, str(linha.get(coluna))), reverse=desc)
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)

    def _inserir(self) -> list[dict]:
        novas = self._valores if isinstance(self._valores, list) else [self._valores]
        chave = _UNICAS.get(self._nome)
        prontas = []
        for valores in novas:
            linha = {"id": str(uuid.uuid4()), **valores}
            if chave and any(all(linha.get(c) == outra.get(c) for c in chave) for outra in self._linhas):
                raise APIError({"code": "23505", "message": "duplicate key value violates unique constraint"})
            prontas.append(linha)
        self._linhas.extend(prontas)
        return [dict(linha) for linha in prontas]


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas
        self.escritas: list[tuple[str, str]] = []

    def table(self, nome: str):
        return _Consulta(self, nome)


# ═══════════════════════════════════════════════════════════════════════════
# Pessoas e cenário
# ═══════════════════════════════════════════════════════════════════════════


def _pessoa(pid: str = "P1", **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "auth_user_id": f"auth-{pid}",
        "nome_completo": f"Pessoa de Teste {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "cargo": None,
        "area": None,
        "setor": None,
        "role": None,
        "ativo": True,
        "is_externo": False,
        "is_super_admin": False,
        "access_profile": None,
        "perfil_pop": None,
        "perfil_ouvidoria": None,
        "perfil_contas_medicas": None,
        "perfil_nsp": None,
        "github_login": None,
        "data_cadastro": "2026-01-01",
    }
    return {**base, **campos}


SUPER_ADMIN = {"access_profile": "super_admin", "is_super_admin": True}


def _participacao(participante: str, papel: str, *, termo=True) -> dict[str, Any]:
    """Vigente desde antes de todo dia fixo daqui até depois de hoje."""
    return {
        "id": f"part-{participante}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": participante,
        "papel": papel,
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": (max(HOJE, DIA) + timedelta(days=300)).isoformat(),
        "termo_assinado_em": "2026-01-10T12:00:00+00:00" if termo else None,
    }


def _item(**campos) -> dict[str, Any]:
    base = {
        "id": str(uuid.uuid4()),
        "evento": "Reunião ordinária",
        "periodicidade": "mensal",
        "regra": None,
        "proxima_data": None,
        "link": None,
        "antecedencia_dias": 7,
        "ativo": True,
    }
    return {**base, **campos}


def _banco(pessoas: list[dict], participacoes: list[dict], itens: list[dict] | None = None) -> _Banco:
    return _Banco(
        {
            "participantes": [dict(p) for p in pessoas],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [dict(p) for p in participacoes],
            "nsp_agenda_regulatoria": [dict(i) for i in (itens or [])],
            "nsp_agenda_ocorrencias": [],
            "pendencias": [],
        }
    )


def _cliente(pessoa: dict[str, Any], banco: _Banco) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(agenda_router.router, prefix="/api")

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


PRESIDENTE = _pessoa("P1")
MEMBRO = _pessoa("P2")


def _cenario_da_presidencia(itens: list[dict] | None = None) -> _Banco:
    return _banco(
        [PRESIDENTE, MEMBRO],
        [_participacao("P1", "presidencia"), _participacao("P2", "membro")],
        itens,
    )


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA_DO_CONTEUDO


# ═══════════════════════════════════════════════════════════════════════════
# 0. Super admin sem papel no Núcleo: recusado em toda rota (decisão 4)
# ═══════════════════════════════════════════════════════════════════════════

ITEM_FIXO = _item(id="item-fixo", proxima_data=DIA.isoformat())

TODAS_AS_ROTAS = [
    ("get", ROTA, None),
    ("post", ROTA, {"evento": "Evento novo", "periodicidade": "anual"}),
    ("patch", f"{ROTA}/item-fixo", {"ativo": False}),
    ("post", f"{ROTA}/item-fixo/resultado", {"resultado": "Feito"}),
]


class TestSuperAdmin:
    @pytest.mark.parametrize(("metodo", "rota", "corpo"), TODAS_AS_ROTAS)
    def test_super_admin_sem_papel_no_nucleo_e_recusado(self, metodo, rota, corpo):
        """Mutante: trocar o recurso das rotas por um que o super admin tem."""
        banco = _banco([_pessoa("P9", **SUPER_ADMIN)], [], [ITEM_FIXO])
        cliente = _cliente(_pessoa("P9", **SUPER_ADMIN), banco)

        resposta = getattr(cliente, metodo)(rota, **({"json": corpo} if corpo else {}))

        _assert_recusado(resposta)
        assert banco.escritas == []


# ═══════════════════════════════════════════════════════════════════════════
# 1. A Presidência edita, inclui e desativa
# ═══════════════════════════════════════════════════════════════════════════


class TestListaEditavel:
    def test_membro_sem_termo_le_a_agenda_sem_editar(self):
        banco = _banco([MEMBRO], [_participacao("P2", "membro", termo=False)], [ITEM_FIXO])

        resposta = _cliente(MEMBRO, banco).get(ROTA)

        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert [i["evento"] for i in corpo["itens"]] == ["Reunião ordinária"]
        assert corpo["pode_editar"] is False

    @pytest.mark.parametrize(("metodo", "rota", "corpo"), TODAS_AS_ROTAS[1:])
    def test_membro_nao_edita(self, metodo, rota, corpo):
        """Mutante: abrir a edição pelo recurso `agenda`, que o membro tem."""
        banco = _banco([MEMBRO], [_participacao("P2", "membro")], [ITEM_FIXO])

        _assert_recusado(getattr(_cliente(MEMBRO, banco), metodo)(rota, json=corpo))
        assert banco.escritas == []

    def test_presidencia_inclui_um_evento(self):
        banco = _cenario_da_presidencia()

        resposta = _cliente(PRESIDENTE, banco).post(
            ROTA,
            json={
                "evento": "Inspeção da vigilância",
                "periodicidade": "anual",
                "proxima_data": "2027-03-10",
                "link": "https://www.gov.br/anvisa",
                "antecedencia_dias": 15,
            },
        )

        assert resposta.status_code == 201, resposta.text
        [salvo] = banco.tabelas["nsp_agenda_regulatoria"]
        assert salvo["evento"] == "Inspeção da vigilância"
        assert salvo["proxima_data"] == "2027-03-10"
        assert salvo["antecedencia_dias"] == 15
        assert salvo["ativo"] is True

    def test_presidencia_edita_a_data_e_o_link(self):
        banco = _cenario_da_presidencia([ITEM_FIXO])

        resposta = _cliente(PRESIDENTE, banco).patch(
            f"{ROTA}/item-fixo", json={"proxima_data": "2026-12-10", "link": "https://exemplo.gov.br/x"}
        )

        assert resposta.status_code == 200, resposta.text
        [salvo] = banco.tabelas["nsp_agenda_regulatoria"]
        assert (salvo["proxima_data"], salvo["link"]) == ("2026-12-10", "https://exemplo.gov.br/x")
        assert salvo["evento"] == "Reunião ordinária"

    def test_presidencia_desativa_e_o_evento_some_do_lembrete(self):
        banco = _cenario_da_presidencia([_item(id="item-fixo", proxima_data=DIA.isoformat())])

        resposta = _cliente(PRESIDENTE, banco).patch(f"{ROTA}/item-fixo", json={"ativo": False})

        assert resposta.status_code == 200, resposta.text
        assert banco.tabelas["nsp_agenda_regulatoria"][0]["ativo"] is False

    def test_link_que_nao_e_http_e_recusado(self):
        """Link `javascript:` viraria script no clique da tela."""
        banco = _cenario_da_presidencia([ITEM_FIXO])

        resposta = _cliente(PRESIDENTE, banco).patch(f"{ROTA}/item-fixo", json={"link": "javascript:alert(1)"})

        assert resposta.status_code == 422
        assert banco.tabelas["nsp_agenda_regulatoria"][0]["link"] is None

    def test_editar_evento_que_nao_existe_e_404(self):
        resposta = _cliente(PRESIDENTE, _cenario_da_presidencia()).patch(f"{ROTA}/nao-existe", json={"ativo": False})

        assert resposta.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 2. O lembrete é uma Pendência da Presidência, uma vez por ocorrência
# ═══════════════════════════════════════════════════════════════════════════


class TestLembrete:
    def test_cria_a_pendencia_da_presidencia_quando_a_data_se_aproxima(self):
        banco = _cenario_da_presidencia([_item(proxima_data=(DIA + timedelta(days=5)).isoformat())])

        criados = agenda.lembrar(banco, DIA)

        assert criados == 1
        [pendencia] = banco.tabelas["pendencias"]
        assert pendencia["responsavel_id"] == "P1"
        assert pendencia["prazo"] == "2026-11-21"
        assert pendencia["status"] == "PENDENTE"
        assert pendencia["descricao_acao"] == "Agenda regulatória: Reunião ordinária"
        assert pendencia.get("id_reuniao") is None

    def test_uma_vez_por_ocorrencia(self):
        """Mutante: tirar a leitura das ocorrências já lembradas."""
        banco = _cenario_da_presidencia([_item(proxima_data=(DIA + timedelta(days=5)).isoformat())])

        agenda.lembrar(banco, DIA)
        segunda = agenda.lembrar(banco, DIA + timedelta(days=1))

        assert segunda == 0
        assert len(banco.tabelas["pendencias"]) == 1

    def test_data_longe_ainda_nao_lembra(self):
        """Mutante: ignorar a antecedência."""
        banco = _cenario_da_presidencia([_item(proxima_data=(DIA + timedelta(days=8)).isoformat())])

        assert agenda.lembrar(banco, DIA) == 0
        assert banco.tabelas["pendencias"] == []

    def test_evento_desativado_nao_lembra(self):
        banco = _cenario_da_presidencia([_item(proxima_data=DIA.isoformat(), ativo=False)])

        assert agenda.lembrar(banco, DIA) == 0

    def test_sem_presidencia_vigente_nao_cria_nada(self):
        banco = _banco([MEMBRO], [_participacao("P2", "membro")], [_item(proxima_data=DIA.isoformat())])

        assert agenda.lembrar(banco, DIA) == 0
        assert banco.tabelas["pendencias"] == []

    def test_nenhum_email_sai(self):
        """O lembrete mora no app: o job só escreve a Pendência e a ocorrência,
        sem fila de e-mail."""
        banco = _cenario_da_presidencia([_item(proxima_data=DIA.isoformat())])

        agenda.lembrar(banco, DIA)

        assert {tabela for _acao, tabela in banco.escritas} == {"pendencias", "nsp_agenda_ocorrencias"}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Registrar o resultado guarda o histórico e avança a próxima data
# ═══════════════════════════════════════════════════════════════════════════


class TestResultado:
    def test_registrar_conclui_o_lembrete_guarda_o_historico_e_avanca(self):
        """Mutante: não avançar a próxima data."""
        banco = _cenario_da_presidencia([_item(id="item-fixo", proxima_data="2026-01-31")])
        agenda.lembrar(banco, date(2026, 1, 30))
        cliente = _cliente(PRESIDENTE, banco)

        resposta = cliente.post(
            f"{ROTA}/item-fixo/resultado",
            json={"resultado": "Reunião feita, ata assinada", "realizada_em": "2026-01-30"},
        )

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["proxima_data"] == "2026-02-28"
        assert banco.tabelas["pendencias"][0]["status"] == "CONCLUIDO"
        [historico] = cliente.get(ROTA).json()["itens"][0]["historico"]
        assert historico["data_prevista"] == "2026-01-31"
        assert historico["resultado"] == "Reunião feita, ata assinada"
        assert historico["realizada_em"] == "2026-01-30"
        assert historico["registrado_por"] == "P1"

    def test_registrar_antes_do_lembrete_tambem_guarda(self):
        banco = _cenario_da_presidencia([_item(id="item-fixo", periodicidade="anual", proxima_data="2027-03-15")])

        resposta = _cliente(PRESIDENTE, banco).post(f"{ROTA}/item-fixo/resultado", json={"resultado": "Enviado"})

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["proxima_data"] == "2028-03-15"
        [ocorrencia] = banco.tabelas["nsp_agenda_ocorrencias"]
        assert (ocorrencia["data_prevista"], ocorrencia["resultado"]) == ("2027-03-15", "Enviado")
        assert ocorrencia["realizada_em"] == HOJE.isoformat()

    def test_evento_avulso_fica_sem_proxima_data(self):
        banco = _cenario_da_presidencia([_item(id="item-fixo", periodicidade="avulsa", proxima_data="2026-12-01")])

        resposta = _cliente(PRESIDENTE, banco).post(f"{ROTA}/item-fixo/resultado", json={"resultado": "Feito"})

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["proxima_data"] is None

    def test_sem_proxima_data_nao_ha_o_que_registrar(self):
        banco = _cenario_da_presidencia([_item(id="item-fixo", proxima_data=None)])

        resposta = _cliente(PRESIDENTE, banco).post(f"{ROTA}/item-fixo/resultado", json={"resultado": "Feito"})

        assert resposta.status_code == 409
        assert banco.tabelas["nsp_agenda_ocorrencias"] == []

    @pytest.mark.parametrize(
        ("data", "periodicidade", "esperada"),
        [
            (date(2026, 1, 31), "mensal", date(2026, 2, 28)),
            (date(2026, 11, 15), "mensal", date(2026, 12, 15)),
            (date(2026, 12, 10), "mensal", date(2027, 1, 10)),
            (date(2028, 2, 29), "anual", date(2029, 2, 28)),
            (date(2026, 11, 15), "bienal", date(2028, 11, 15)),
            (date(2026, 11, 15), "avulsa", None),
        ],
    )
    def test_a_proxima_data_pela_periodicidade(self, data, periodicidade, esperada):
        assert agenda.proxima_depois(data, periodicidade) == esperada


# ═══════════════════════════════════════════════════════════════════════════
# 4. O job não chama IA
# ═══════════════════════════════════════════════════════════════════════════

# O que denuncia IA (ou e-mail) no código: os módulos do app que falam com
# provedor de modelo e os SDKs.
_MARCAS_DE_IA_E_EMAIL = ("ai_processor", "anthropic", "openai", "openrouter", "email_service", "resend")


def _marcas(codigo: str) -> list[str]:
    return [marca for marca in _MARCAS_DE_IA_E_EMAIL if marca in codigo.lower()]


class TestSemIa:
    def test_o_detector_reconhece_um_modulo_que_chama_ia(self):
        """Piso do detector: o módulo de IA do app tem marca."""
        from app.services import ai_processor

        assert _marcas(inspect.getsource(ai_processor))

    def test_o_servico_da_agenda_nao_fala_com_ia_nem_com_email(self):
        """Mutante: importar o `ai_processor` no serviço da agenda."""
        assert _marcas(inspect.getsource(agenda)) == []

    def test_o_job_do_scheduler_so_chama_o_servico(self):
        assert _marcas(inspect.getsource(scheduler.lembrar_agenda_regulatoria)) == []
        assert "agenda.lembrar(" in inspect.getsource(scheduler.lembrar_agenda_regulatoria)

    def test_o_job_esta_registrado_uma_vez_por_dia(self):
        assert 'lembrar_agenda_regulatoria,\n        "cron"' in inspect.getsource(scheduler.start_scheduler)


# ═══════════════════════════════════════════════════════════════════════════
# 5. O texto do Produto no Kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def _secao_do_kit(titulo: str) -> str:
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "seguranca-do-paciente.md").read_text(encoding="utf-8")
    partes = texto.split(f"## {titulo}\n", 1)
    assert len(partes) == 2, f"a seção {titulo!r} sumiu do kit"
    return partes[1].split("\n## ", 1)[0]


class TestKitDeConhecimento:
    def test_a_agenda_esta_no_que_ja_esta_no_ar(self):
        """Mutante: deixar o kit dizendo que a agenda chega depois."""
        secao = _secao_do_kit("O que já está no ar")
        assert "Agenda regulatória" in secao
        assert "pendência" in secao.lower()
        assert "e-mail" in secao

    def test_a_agenda_saiu_do_que_ele_ainda_nao_faz(self):
        assert "agenda" not in _secao_do_kit("O que ele ainda não faz").lower()
