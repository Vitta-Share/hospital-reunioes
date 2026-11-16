"""Os documentos do Núcleo (issue #1767, PRD #1764, ADR 0095).

Cada tipo de documento (ato de designação, Regimento, Plano de Segurança do
Paciente, Termo, ata, outro) tem versões e uma única vigente. Publicar uma
versão nova troca a vigente e guarda a anterior; não existe exclusão, e a
correção é sempre uma versão nova.

A troca da vigente é atômica numa função do banco (`nsp_publicar_documento`,
migration 147). Os testes da rota usam um dublê em memória que faz o mesmo que
a função; o que a função faz de verdade é conferido no texto da migration, na
última seção deste arquivo.

Nenhum nome, registro ou e-mail de pessoa real: as pessoas daqui são de teste,
e o texto do Regimento é de mentira (o de verdade entra pela tela).
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import seguranca_do_paciente_documentos as documentos_router  # noqa: E402
from app.services.seguranca_do_paciente import termo  # noqa: E402
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo  # noqa: E402

ROTA = "/api/nsp/documentos"

RECUSA_DO_CONTEUDO = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}

# O mesmo dia que o gate usa: em UTC (o runner do CI), entre 21h e 24h de
# Brasília, `date.today()` já é amanhã e a Participação vencida ontem passaria.
HOJE = hoje_em_sao_paulo()
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "147_nsp_documentos.sql"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def termos_da_revisao(monkeypatch) -> list[str]:
    """A revisão material gera o Termo dos membros (issue #1769), o que os
    testes do Termo provam com a assinatura eletrônica dublada. Aqui ela só é
    anotada: nenhum teste deste arquivo chega à assinatura de verdade."""
    autores: list[str] = []
    monkeypatch.setattr(termo, "termos_da_revisao_material", lambda _sb, *, autor_id: autores.append(autor_id))
    return autores


# ═══════════════════════════════════════════════════════════════════════════
# O dublê do banco
# ═══════════════════════════════════════════════════════════════════════════


def _e_uuid(valor) -> bool:
    try:
        uuid.UUID(str(valor))
    except ValueError:
        return False
    return True


class _Consulta:
    """`id_uuid`: a coluna `id` da tabela é UUID, como a da `nsp_documentos`.
    Filtrar por texto que não é UUID faz o PostgREST recusar com 22P02, e o
    dublê faz o mesmo, senão o teste do 404 passa onde o banco daria erro."""

    def __init__(self, linhas: list[dict], *, id_uuid: bool = False):
        self._linhas = linhas
        self._id_uuid = id_uuid
        self._id_invalido = False
        self._filtros: list = []
        self._teto: int | None = None
        self._ordem: list[tuple[str, bool]] = []

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        if self._id_uuid and coluna == "id" and not _e_uuid(valor):
            self._id_invalido = True
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        valores = list(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) <= str(valor))
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) >= str(valor))
        return self

    def order(self, coluna, desc=False):
        self._ordem.append((coluna, desc))
        return self

    def limit(self, n):
        self._teto = n
        return self

    def execute(self):
        if self._id_invalido:
            raise APIError({"code": "22P02", "message": "invalid input syntax for type uuid"})
        casam = [dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)]
        for coluna, desc in reversed(self._ordem):
            casam.sort(key=lambda linha: linha.get(coluna), reverse=desc)
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)


class _Rpc:
    def __init__(self, resultado):
        self._resultado = resultado

    def execute(self):
        return SimpleNamespace(data=self._resultado)


class _Banco:
    """As tabelas do gate e a `nsp_documentos`, com a função de publicar.

    O `rpc` faz o que a `nsp_publicar_documento` faz: a versão é a seguinte do
    tipo, a vigente anterior do mesmo tipo deixa de ser, a nova nasce vigente.
    """

    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas
        self.chamadas_rpc: list[tuple[str, dict]] = []

    def table(self, nome: str):
        return _Consulta(self.tabelas.setdefault(nome, []), id_uuid=nome == "nsp_documentos")

    def rpc(self, nome: str, params: dict):
        self.chamadas_rpc.append((nome, params))
        assert nome == "nsp_publicar_documento", nome
        documentos = self.tabelas.setdefault("nsp_documentos", [])
        do_tipo = [d for d in documentos if d["tipo"] == params["p_tipo"]]
        for anterior in do_tipo:
            anterior["vigente"] = False
        novo = {
            "id": str(uuid.uuid4()),
            "tipo": params["p_tipo"],
            "versao": max((d["versao"] for d in do_tipo), default=0) + 1,
            "titulo": params["p_titulo"],
            "texto": params["p_texto"],
            "natureza_revisao": params["p_natureza_revisao"],
            "vigente": True,
            "arquivo_assinado_path": None,
            "publicado_por": params["p_publicado_por"],
            "publicado_em": f"2026-11-{len(documentos) + 1:02d}T12:00:00+00:00",
        }
        documentos.append(novo)
        return _Rpc(dict(novo))


def _pessoa(**campos) -> dict[str, Any]:
    base = {
        "id": "P1",
        "auth_user_id": "auth-p1",
        "nome_completo": "Pessoa de Teste",
        "email": "p1@hsm.test",
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
ACESSO_PLENO = {"perfil_nsp": "acesso_pleno"}


def _participacao(*, papel="membro", termo=True, participante="P1") -> dict[str, Any]:
    return {
        "id": f"part-{participante}-{papel}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": participante,
        "papel": papel,
        "vigencia_inicio": (HOJE - timedelta(days=30)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=300)).isoformat(),
        "termo_assinado_em": "2026-01-10T12:00:00+00:00" if termo else None,
    }


PRESIDENCIA = [_participacao(papel="presidencia")]
MEMBRO = [_participacao()]
MEMBRO_SEM_TERMO = [_participacao(termo=False)]


def _cliente(
    pessoa: dict[str, Any], participacoes: list[dict] | None = None, documentos: list[dict] | None = None
) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(documentos_router.router, prefix="/api")
    banco = _Banco(
        {
            "participantes": [pessoa],
            "colegiados": [dict(NUCLEO)],
            "participacoes": list(participacoes or []),
            "nsp_documentos": [dict(d) for d in (documentos or [])],
        }
    )

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    cliente = TestClient(app)
    cliente.banco = banco  # type: ignore[attr-defined]
    return cliente


def _publicar(cliente: TestClient, **corpo):
    return cliente.post(ROTA, json=corpo)


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA_DO_CONTEUDO


PLANO_V1 = {"tipo": "plano_seguranca_paciente", "titulo": "Plano de Segurança do Paciente", "texto": "Plano de teste."}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Publicar troca a vigente e guarda as anteriores
# ═══════════════════════════════════════════════════════════════════════════


class TestPublicacao:
    def test_publicar_versao_nova_deixa_so_ela_vigente_e_mantem_as_anteriores(self):
        cliente = _cliente(_pessoa(), PRESIDENCIA)

        assert _publicar(cliente, **PLANO_V1).status_code == 201
        resposta = _publicar(cliente, **{**PLANO_V1, "texto": "Plano de teste, revisto."})
        assert resposta.status_code == 201, resposta.text
        assert resposta.json()["versao"] == 2

        lista = cliente.get(ROTA)
        assert lista.status_code == 200, lista.text
        do_plano = [d for d in lista.json()["documentos"] if d["tipo"] == "plano_seguranca_paciente"]
        assert [(d["versao"], d["vigente"]) for d in do_plano] == [(2, True), (1, False)]

    def test_a_versao_anterior_continua_legivel_na_integra(self):
        cliente = _cliente(_pessoa(), PRESIDENCIA)
        primeira = _publicar(cliente, **PLANO_V1).json()
        _publicar(cliente, **{**PLANO_V1, "texto": "Plano de teste, revisto."})

        resposta = cliente.get(f"{ROTA}/{primeira['id']}")

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["texto"] == "Plano de teste."
        assert resposta.json()["vigente"] is False

    def test_publicar_um_tipo_nao_mexe_na_vigente_de_outro_tipo(self):
        cliente = _cliente(_pessoa(), PRESIDENCIA)
        _publicar(cliente, **PLANO_V1)
        _publicar(cliente, tipo="ato_designacao", titulo="Ato de designação")

        vigentes = {d["tipo"] for d in cliente.get(ROTA).json()["documentos"] if d["vigente"]}

        assert vigentes == {"plano_seguranca_paciente", "ato_designacao"}

    def test_a_trilha_diz_quem_publicou(self):
        cliente = _cliente(_pessoa(), PRESIDENCIA)
        _publicar(cliente, **PLANO_V1)

        (documento,) = cliente.get(ROTA).json()["documentos"]

        assert documento["publicado_por"] == "Pessoa de Teste"
        assert cliente.banco.chamadas_rpc[0][1]["p_publicado_por"] == "P1"

    def test_tipo_fora_da_lista_e_recusado(self):
        cliente = _cliente(_pessoa(), PRESIDENCIA)

        resposta = _publicar(cliente, tipo="contrato", titulo="Contrato")

        assert resposta.status_code == 422
        assert cliente.banco.chamadas_rpc == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. O Regimento: a natureza da revisão é obrigatória e fica gravada
# ═══════════════════════════════════════════════════════════════════════════

REGIMENTO = {"tipo": "regimento", "titulo": "Regimento Interno do Núcleo", "texto": "Art. 1º Texto de teste."}


class TestRegimento:
    def test_publicar_o_regimento_sem_dizer_a_natureza_e_recusado(self):
        cliente = _cliente(_pessoa(), PRESIDENCIA)

        resposta = _publicar(cliente, **REGIMENTO)

        assert resposta.status_code == 422, resposta.text
        assert "material ou só de redação" in resposta.text
        assert cliente.banco.chamadas_rpc == []

    @pytest.mark.parametrize("natureza", ["material", "redacao"])
    def test_a_natureza_escolhida_fica_gravada(self, natureza):
        cliente = _cliente(_pessoa(), PRESIDENCIA)

        resposta = _publicar(cliente, **REGIMENTO, natureza_revisao=natureza)

        assert resposta.status_code == 201, resposta.text
        assert cliente.banco.chamadas_rpc[0][1]["p_natureza_revisao"] == natureza
        (documento,) = cliente.get(ROTA).json()["documentos"]
        assert documento["natureza_revisao"] == natureza

    def test_natureza_fora_das_duas_e_recusada(self):
        cliente = _cliente(_pessoa(), PRESIDENCIA)

        resposta = _publicar(cliente, **REGIMENTO, natureza_revisao="parcial")

        assert resposta.status_code == 422
        assert cliente.banco.chamadas_rpc == []

    def test_regimento_sem_texto_e_recusado(self):
        """O texto do Regimento vive no banco: sem ele não há o que ler."""
        cliente = _cliente(_pessoa(), PRESIDENCIA)

        resposta = _publicar(cliente, **{**REGIMENTO, "texto": "   "}, natureza_revisao="material")

        assert resposta.status_code == 422
        assert cliente.banco.chamadas_rpc == []

    def test_outro_tipo_publica_sem_natureza(self):
        cliente = _cliente(_pessoa(), PRESIDENCIA)

        assert _publicar(cliente, tipo="ata", titulo="Ata de teste").status_code == 201


# ═══════════════════════════════════════════════════════════════════════════
# 3. Quem lê e quem publica (ADR 0095, decisão 4)
# ═══════════════════════════════════════════════════════════════════════════

REGIMENTO_VIGENTE = {
    "id": "5d1f3c2a-0000-4000-8000-000000000001",
    "tipo": "regimento",
    "versao": 1,
    "titulo": "Regimento Interno do Núcleo",
    "texto": "Art. 1º Texto de teste do Regimento.",
    "natureza_revisao": "material",
    "vigente": True,
    "arquivo_assinado_path": None,
    "publicado_por": "P9",
    "publicado_em": "2026-11-01T12:00:00+00:00",
}
PLANO_VIGENTE = {
    **REGIMENTO_VIGENTE,
    "id": "5d1f3c2a-0000-4000-8000-000000000002",
    "tipo": "plano_seguranca_paciente",
    "titulo": "Plano de Segurança do Paciente",
    "texto": "Texto de teste do Plano.",
    "natureza_revisao": None,
}
DOCUMENTOS_VIGENTES = [REGIMENTO_VIGENTE, PLANO_VIGENTE]

QUEM_LE = {
    "membro com Termo válido": (_pessoa(), MEMBRO),
    "suplente com Termo válido": (_pessoa(), [_participacao(papel="suplente")]),
    "Presidência": (_pessoa(), PRESIDENCIA),
    "Acesso pleno": (_pessoa(**ACESSO_PLENO), []),
}

QUEM_NAO_LE = {
    "membro sem Termo": (_pessoa(), MEMBRO_SEM_TERMO),
    "Diretoria": (_pessoa(role="diretor", access_profile="regular"), []),
    "super admin": (_pessoa(**SUPER_ADMIN), []),
    "pessoa de fora": (_pessoa(access_profile="regular"), []),
}


class TestQuemLe:
    @pytest.mark.parametrize("quem", QUEM_LE)
    @pytest.mark.parametrize("documento", DOCUMENTOS_VIGENTES, ids=lambda d: d["tipo"])
    def test_le_o_regimento_e_o_plano_vigentes(self, quem, documento):
        pessoa, participacoes = QUEM_LE[quem]
        cliente = _cliente(pessoa, participacoes, DOCUMENTOS_VIGENTES)

        lista = cliente.get(ROTA)
        leitura = cliente.get(f"{ROTA}/{documento['id']}")

        assert lista.status_code == 200, lista.text
        assert leitura.status_code == 200, leitura.text
        assert leitura.json()["texto"] == documento["texto"]
        assert leitura.json()["vigente"] is True

    @pytest.mark.parametrize("quem", QUEM_NAO_LE)
    def test_nao_le_a_lista_nem_o_texto(self, quem):
        """Mutante: deixar o super admin passar no gate, como nos outros
        módulos. A leitura devolveria 200 com o texto do Regimento."""
        pessoa, participacoes = QUEM_NAO_LE[quem]
        cliente = _cliente(pessoa, participacoes, DOCUMENTOS_VIGENTES)

        _assert_recusado(cliente.get(ROTA))
        leitura = cliente.get(f"{ROTA}/{REGIMENTO_VIGENTE['id']}")
        _assert_recusado(leitura)
        assert "Texto de teste" not in leitura.text

    def test_documento_inexistente_e_404(self):
        cliente = _cliente(_pessoa(), MEMBRO, DOCUMENTOS_VIGENTES)

        resposta = cliente.get(f"{ROTA}/5d1f3c2a-0000-4000-8000-0000000000ff")

        assert resposta.status_code == 404, resposta.text

    def test_id_que_nao_e_uuid_e_404_e_nao_indisponivel(self, caplog):
        """Link velho ou URL digitada: o PostgREST recusa o filtro com 22P02.
        Mutante: tirar o tratamento do 22P02 da rota. Ela devolveria 503
        "indisponíveis agora", com warning no log, para um documento que só
        não existe."""
        cliente = _cliente(_pessoa(), MEMBRO, DOCUMENTOS_VIGENTES)

        resposta = cliente.get(f"{ROTA}/doc-nenhum")

        assert resposta.status_code == 404, resposta.text
        assert resposta.json() == {"detail": "Documento não encontrado."}
        assert "ilegível" not in caplog.text


class TestQuemPublica:
    @pytest.mark.parametrize("quem", ["Presidência", "Acesso pleno"])
    def test_presidencia_e_acesso_pleno_publicam(self, quem):
        pessoa, participacoes = QUEM_LE[quem]

        assert _publicar(_cliente(pessoa, participacoes), **PLANO_V1).status_code == 201

    @pytest.mark.parametrize(
        "quem",
        [("membro com Termo válido", QUEM_LE), *((q, QUEM_NAO_LE) for q in QUEM_NAO_LE)],
        ids=lambda par: par[0],
    )
    def test_os_demais_nao_publicam(self, quem):
        nome, tabela = quem
        pessoa, participacoes = tabela[nome]
        cliente = _cliente(pessoa, participacoes)

        _assert_recusado(_publicar(cliente, **PLANO_V1))
        assert cliente.banco.chamadas_rpc == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. Não existe exclusão nem edição: a correção é versão nova
# ═══════════════════════════════════════════════════════════════════════════


class TestSemExclusao:
    def test_nenhuma_rota_de_documento_apaga_ou_edita(self):
        """Mutante: um DELETE (ou PATCH) em /nsp/documentos/{id}."""
        metodos = {
            metodo
            for rota in documentos_router.router.routes
            if rota.path.startswith("/nsp/documentos")
            for metodo in rota.methods
        }

        assert metodos == {"GET", "POST"}

    @pytest.mark.parametrize("metodo", ["delete", "patch", "put"])
    def test_apagar_ou_editar_um_documento_nao_existe(self, metodo):
        cliente = _cliente(_pessoa(**ACESSO_PLENO), [], DOCUMENTOS_VIGENTES)

        resposta = cliente.request(metodo.upper(), f"{ROTA}/{REGIMENTO_VIGENTE['id']}")

        assert resposta.status_code == 405
        assert len(cliente.banco.tabelas["nsp_documentos"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# 5. A migration 147, lida como texto
# ═══════════════════════════════════════════════════════════════════════════


def _sql() -> str:
    return re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))


def _funcao() -> str:
    corpo = re.search(r"FUNCTION nsp_publicar_documento\(.*?\$\$(.*?)\$\$;", _sql(), re.DOTALL)
    assert corpo
    return corpo.group(1)


class TestMigration:
    def test_cria_so_a_tabela_dos_documentos(self):
        assert re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", _sql()) == ["nsp_documentos"]

    def test_rls_ligado_e_nenhuma_politica(self):
        assert "ALTER TABLE nsp_documentos ENABLE ROW LEVEL SECURITY;" in _sql()
        assert re.search(r"CREATE\s+POLICY", _sql(), re.IGNORECASE) is None

    def test_uma_unica_vigente_por_tipo(self):
        """Mutante: tirar o índice único parcial."""
        assert re.search(
            r"CREATE UNIQUE INDEX IF NOT EXISTS \w+\s+ON nsp_documentos\s*\(tipo\)\s+WHERE vigente;", _sql()
        )

    def test_a_funcao_tira_a_vigente_anterior_do_tipo_antes_de_gravar_a_nova(self):
        """Mutante: tirar o UPDATE que desmarca a vigente anterior. A nova
        bateria no índice único, ou pior, sem o índice, viriam duas vigentes."""
        funcao = _funcao()
        desmarca = re.search(r"UPDATE nsp_documentos SET vigente = false WHERE tipo = p_tipo AND vigente;", funcao)
        grava = re.search(
            r"INSERT INTO nsp_documentos\s*\(.*?\bvigente\b.*?\)\s*VALUES\s*\(.*?\btrue\b", funcao, re.DOTALL
        )
        assert desmarca and grava
        assert desmarca.start() < grava.start()

    def test_a_versao_e_a_seguinte_do_tipo(self):
        assert re.search(
            r"COALESCE\(MAX\(versao\), 0\) \+ 1 INTO v_versao\s+FROM nsp_documentos WHERE tipo = p_tipo;", _funcao()
        )
        assert "UNIQUE (tipo, versao)" in _sql()

    def test_a_funcao_nao_apaga_nada(self):
        assert re.search(r"\bDELETE\s+FROM\b|\bTRUNCATE\b", _sql(), re.IGNORECASE) is None

    def test_os_seis_tipos_e_as_duas_naturezas(self):
        tipos = re.search(r"nsp_documentos_tipo_check\s+CHECK \(tipo IN \((.*?)\)\)", _sql())
        naturezas = re.search(r"natureza_revisao IN \((.*?)\)\)", _sql())
        assert tipos and naturezas
        assert sorted(re.findall(r"'(\w+)'", tipos.group(1))) == [
            "ata",
            "ato_designacao",
            "outro",
            "plano_seguranca_paciente",
            "regimento",
            "termo",
        ]
        assert sorted(re.findall(r"'(\w+)'", naturezas.group(1))) == ["material", "redacao"]

    def test_o_regimento_exige_natureza_e_texto_no_banco(self):
        assert re.search(r"CHECK \(tipo <> 'regimento' OR \(natureza_revisao IS NOT NULL AND texto IS NOT NULL", _sql())

    def test_a_funcao_e_so_do_backend(self):
        assert re.search(
            r"REVOKE EXECUTE ON FUNCTION nsp_publicar_documento\([^)]*\)\s+FROM PUBLIC, anon, authenticated;", _sql()
        )
        assert re.search(r"GRANT EXECUTE ON FUNCTION nsp_publicar_documento\([^)]*\) TO service_role;", _sql())

    def test_nenhum_documento_nem_pessoa_na_migration(self):
        """O texto do Regimento entra pela tela, nunca por migration."""
        assert re.search(r"INSERT INTO nsp_documentos", _sql().replace(_funcao(), "")) is None
        assert re.search(r"INSERT INTO participantes|UPDATE participantes", _sql(), re.IGNORECASE) is None
        assert re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", MIGRATION.read_text(encoding="utf-8")) is None

    def test_o_recibo_e_o_147(self):
        assert "INSERT INTO migracoes_aplicadas (numero) VALUES (147)" in _sql()
