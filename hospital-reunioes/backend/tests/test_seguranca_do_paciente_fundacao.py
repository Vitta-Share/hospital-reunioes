"""A fundação do módulo Segurança do Paciente (issue #1765, PRD #1764, ADR 0095).

As rotas `/nsp` passam pela permissão efetiva, que lê a Participação vigente no
Núcleo. O que mais pode vazar é o acesso: cada recusa é afirmada pelo código E
pelo corpo da resposta, que não pode trazer nada do Núcleo.

O banco é um dublê em memória com as três tabelas que o gate lê
(`participantes`, `colegiados`, `participacoes`). Nenhum nome, registro ou
e-mail de pessoa real: as pessoas daqui são de teste.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.dependencies import get_current_user, get_supabase_client  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.routers import participantes as participantes_router  # noqa: E402
from app.routers import seguranca_do_paciente as nsp_router  # noqa: E402
from app.services.seguranca_do_paciente.permissao import hoje_em_sao_paulo  # noqa: E402

ROTA_INICIO = "/api/nsp/inicio"
ROTA_CONFIGURACAO = "/api/nsp/configuracao"
ROTA_ME = "/api/participantes/me"

RECUSA_DO_CONTEUDO = {"detail": "Conteúdo restrito ao Núcleo de Segurança do Paciente"}

# O mesmo dia que o gate usa: em UTC (o runner do CI), entre 21h e 24h de
# Brasília, `date.today()` já é amanhã e a Participação vencida ontem passaria.
HOJE = hoje_em_sao_paulo()
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}
OUTRO_COLEGIADO = {"id": "col-etica", "slug": "etica", "nome": "Comissão de Ética", "setor_id": None}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []
        self._teto: int | None = None

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def ilike(self, *_a):
        """O `/me` procura o e-mail no cadastro de responsáveis da Ouvidoria
        (issue #1884); aqui ninguém responde por setor."""
        return self

    def lte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) <= str(valor))
        return self

    def gte(self, coluna, valor):
        self._filtros.append(lambda linha: str(linha.get(coluna)) >= str(valor))
        return self

    def limit(self, n):
        self._teto = n
        return self

    def order(self, *_a, **_kw):
        """Os casos graves do início (issue #1989); aqui não há nenhum."""
        return self

    def execute(self):
        casam = [dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)]
        return SimpleNamespace(data=casam[: self._teto] if self._teto is not None else casam)


class _Banco:
    def __init__(self, tabelas: dict[str, list[dict]]):
        self.tabelas = tabelas

    def table(self, nome: str):
        return _Consulta(self.tabelas.setdefault(nome, []))


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


def _participacao(
    *, papel="membro", inicio=-30, fim=300, termo=True, colegiado=NUCLEO, participante="P1"
) -> dict[str, Any]:
    return {
        "id": f"part-{participante}-{papel}",
        "colegiado_id": colegiado["id"],
        "participante_id": participante,
        "papel": papel,
        "vigencia_inicio": (HOJE + timedelta(days=inicio)).isoformat(),
        "vigencia_fim": (HOJE + timedelta(days=fim)).isoformat(),
        "termo_assinado_em": "2026-01-10T12:00:00+00:00" if termo else None,
    }


def _cliente(pessoa: dict[str, Any], participacoes: list[dict] | None = None) -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(nsp_router.router, prefix="/api")
    app.include_router(participantes_router.router, prefix="/api")
    banco = _Banco(
        {
            "participantes": [pessoa],
            "colegiados": [dict(NUCLEO), dict(OUTRO_COLEGIADO)],
            "participacoes": list(participacoes or []),
        }
    )

    async def _usuario() -> dict[str, Any]:
        return {"id": pessoa["auth_user_id"], "email": pessoa["email"], "metadata": {}}

    app.dependency_overrides[get_current_user] = _usuario
    app.dependency_overrides[get_supabase_client] = lambda: banco
    return TestClient(app)


def _assert_recusado(resposta) -> None:
    assert resposta.status_code == 403, resposta.text
    assert resposta.json() == RECUSA_DO_CONTEUDO


# ═══════════════════════════════════════════════════════════════════════════
# 1. Super admin: só a configuração técnica (ADR 0095, decisão 4)
# ═══════════════════════════════════════════════════════════════════════════


class TestSuperAdmin:
    def test_super_admin_sem_acesso_pleno_recebe_recusa_no_conteudo(self):
        """Mutante: deixar o super admin passar no gate, como nos outros
        módulos. A rota devolveria 200 com o Núcleo."""
        _assert_recusado(_cliente(_pessoa(**SUPER_ADMIN)).get(ROTA_INICIO))

    def test_super_admin_alcanca_a_configuracao_tecnica(self):
        resposta = _cliente(_pessoa(**SUPER_ADMIN)).get(ROTA_CONFIGURACAO)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["colegiado"]["slug"] == "nsp"

    def test_super_admin_com_acesso_pleno_le_o_conteudo(self):
        resposta = _cliente(_pessoa(**SUPER_ADMIN, perfil_nsp="acesso_pleno")).get(ROTA_INICIO)

        assert resposta.status_code == 200, resposta.text


# ═══════════════════════════════════════════════════════════════════════════
# 2. Quem entra pela Participação vigente
# ═══════════════════════════════════════════════════════════════════════════


class TestParticipacao:
    def test_membro_com_participacao_vigente_le_a_pagina_inicial(self):
        resposta = _cliente(_pessoa(), [_participacao()]).get(ROTA_INICIO)

        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        assert corpo["nucleo"] == "Núcleo de Segurança do Paciente"
        assert corpo["membros_vigentes"] == 1
        assert "reunioes" in corpo["recursos"]

    def test_membro_sem_termo_entra_mas_sem_reunioes(self):
        resposta = _cliente(_pessoa(), [_participacao(termo=False)]).get(ROTA_INICIO)

        assert resposta.status_code == 200, resposta.text
        assert sorted(resposta.json()["recursos"]) == ["agenda", "calendario", "painel", "ver_modulo"]

    def test_participacao_vencida_nao_entra(self):
        """Mutante: tirar o filtro do fim da vigência."""
        _assert_recusado(_cliente(_pessoa(), [_participacao(inicio=-400, fim=-1)]).get(ROTA_INICIO))

    def test_participacao_que_ainda_nao_comecou_nao_entra(self):
        """Mutante: tirar o filtro do início da vigência."""
        _assert_recusado(_cliente(_pessoa(), [_participacao(inicio=1, fim=300)]).get(ROTA_INICIO))

    def test_participacao_em_outro_colegiado_nao_abre_o_nucleo(self):
        """Mutante: tirar o filtro do Colegiado."""
        _assert_recusado(_cliente(_pessoa(), [_participacao(colegiado=OUTRO_COLEGIADO)]).get(ROTA_INICIO))

    def test_participacao_de_outra_pessoa_nao_vale(self):
        _assert_recusado(_cliente(_pessoa(), [_participacao(participante="P9")]).get(ROTA_INICIO))

    def test_membro_comum_nao_alcanca_a_configuracao(self):
        _assert_recusado(_cliente(_pessoa(), [_participacao()]).get(ROTA_CONFIGURACAO))


# ═══════════════════════════════════════════════════════════════════════════
# 3. Diretoria, pessoa de fora, pessoa desligada
# ═══════════════════════════════════════════════════════════════════════════


class TestOutrosPerfis:
    @pytest.mark.parametrize("role", ["diretor", "presidente"])
    def test_cargo_de_diretoria_le_a_pagina_inicial(self, role):
        resposta = _cliente(_pessoa(role=role, access_profile="regular")).get(ROTA_INICIO)

        assert resposta.status_code == 200, resposta.text

    def test_gerente_de_fora_do_nucleo_recebe_recusa(self):
        _assert_recusado(_cliente(_pessoa(role="gerente", access_profile="regular")).get(ROTA_INICIO))

    def test_pessoa_desligada_recebe_403_mesmo_membro(self):
        resposta = _cliente(_pessoa(ativo=False), [_participacao()]).get(ROTA_INICIO)

        assert resposta.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# 4. O menu: /participantes/me diz o que a pessoa alcança no módulo
# ═══════════════════════════════════════════════════════════════════════════


class TestParticipanteMe:
    def test_membro_sem_termo_recebe_painel_calendario_e_agenda(self):
        resposta = _cliente(_pessoa(), [_participacao(termo=False)]).get(ROTA_ME)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["recursos_nsp"] == ["agenda", "calendario", "painel", "ver_modulo"]

    def test_super_admin_recebe_so_a_configuracao(self):
        """É o que esconde o item do menu: sem `ver_modulo`, sem Segurança do
        Paciente."""
        resposta = _cliente(_pessoa(**SUPER_ADMIN)).get(ROTA_ME)

        assert resposta.json()["recursos_nsp"] == ["configuracao"]

    def test_pessoa_de_fora_recebe_lista_vazia(self):
        assert _cliente(_pessoa(access_profile="regular")).get(ROTA_ME).json()["recursos_nsp"] == []

    def test_banco_sem_as_tabelas_do_modulo_nao_derruba_o_me(self):
        """Entre o deploy e a migration colada no Studio, a tabela de
        Participação não existe: o `/me` (de que TODA tela depende) segue de pé,
        e o módulo fica fechado."""
        from postgrest.exceptions import APIError

        cliente = _cliente(_pessoa(access_profile="regular"))
        banco = cliente.app.dependency_overrides[get_supabase_client]()
        original = banco.table

        def _table(nome):
            if nome in ("colegiados", "participacoes"):
                raise APIError({"code": "42P01", "message": f'relation "{nome}" does not exist'})
            return original(nome)

        banco.table = _table

        resposta = cliente.get(ROTA_ME)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["recursos_nsp"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 5. O QR e o endereço da notificação na Configuração (issue #2046)
# ═══════════════════════════════════════════════════════════════════════════

ROTA_QR_DA_NOTIFICACAO = "/api/nsp/configuracao/qr-da-notificacao.png"
APP = "https://app.hsm.test"


def _ler_o_qr(png: bytes) -> list[list[bool]]:
    """Lê a grade de módulos do PNG como um leitor de QR leria: acha o canto
    do padrão de localização, mede o tamanho do módulo pelos 7 módulos dele e
    amostra o centro de cada módulo. Não sabe a escala nem a borda que a rota
    usou."""
    import io

    from PIL import Image

    imagem = Image.open(io.BytesIO(png)).convert("L")
    largura, altura = imagem.size
    escuro = [[imagem.getpixel((x, y)) < 128 for x in range(largura)] for y in range(altura)]
    topo = next(y for y in range(altura) if any(escuro[y]))
    esquerda = next(x for x in range(largura) if escuro[topo][x])
    direita = max(x for x in range(largura) if any(escuro[y][x] for y in range(altura)))
    corrida = 0
    while escuro[topo][esquerda + corrida]:
        corrida += 1
    modulo = corrida / 7
    lado = round((direita - esquerda + 1) / modulo)
    return [
        [escuro[int(topo + (i + 0.5) * modulo)][int(esquerda + (j + 0.5) * modulo)] for j in range(lado)]
        for i in range(lado)
    ]


def _o_qr_abre(png: bytes, url: str) -> bool:
    """A grade lida bate com o QR desta URL em algum nível de correção."""
    import segno

    lida = _ler_o_qr(png)
    for nivel in "lmqh":
        esperado = segno.make(url, error=nivel, boost_error=False, micro=False)
        if [[bool(m) for m in linha] for linha in esperado.matrix] == lida:
            return True
    return False


class TestQrEEnderecoDaNotificacao:
    """CA da issue #2046: a Configuração mostra o QR (imagem para baixar, que
    abre `/notificar/qr`) e o endereço de `/notificar`, e só para quem vê a
    Configuração."""

    @pytest.fixture(autouse=True)
    def _app(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "frontend_url", f"{APP}/")

    def test_a_imagem_baixada_abre_a_pagina_do_qr(self):
        """Mutante: o QR apontar para `/notificar` (o endereço), e não para
        `/notificar/qr`. A origem da notificação sairia errada."""
        resposta = _cliente(_pessoa(**SUPER_ADMIN)).get(ROTA_QR_DA_NOTIFICACAO)

        assert resposta.status_code == 200, resposta.text
        assert resposta.headers["content-type"] == "image/png"
        assert resposta.headers["content-disposition"].startswith("attachment;")
        assert _o_qr_abre(resposta.content, "https://app.hsm.test/notificar/qr")
        assert not _o_qr_abre(resposta.content, "https://app.hsm.test/notificar")

    def test_a_configuracao_traz_o_endereco_completo_da_notificacao(self):
        """O endereço que a TI cola no ícone dos computadores: com o esquema e
        o domínio do app, sem `/api`."""
        resposta = _cliente(_pessoa(**SUPER_ADMIN)).get(ROTA_CONFIGURACAO)

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["endereco_da_notificacao"] == "https://app.hsm.test/notificar"

    @pytest.mark.parametrize(
        ("pessoa", "participacoes"),
        [
            pytest.param({}, [_participacao()], id="membro comum"),
            pytest.param({"role": "diretor", "access_profile": "regular"}, [], id="diretoria"),
            pytest.param({"access_profile": "regular"}, [], id="pessoa de fora"),
        ],
    )
    def test_quem_nao_ve_a_configuracao_nao_baixa_o_qr(self, pessoa, participacoes):
        """Mutante: a rota da imagem pedir `ver_modulo` em vez de
        `configuracao`. O membro e a Diretoria baixariam."""
        _assert_recusado(_cliente(_pessoa(**pessoa), participacoes).get(ROTA_QR_DA_NOTIFICACAO))

    def test_a_presidencia_baixa_o_qr(self):
        resposta = _cliente(_pessoa(), [_participacao(papel="presidencia")]).get(ROTA_QR_DA_NOTIFICACAO)

        assert resposta.status_code == 200, resposta.text

    def test_o_kit_de_conhecimento_diz_onde_ficam_o_qr_e_o_endereco(self):
        """O texto do Produto no Kit de conhecimento diz o comportamento novo."""
        from app.services.conhecimento import CONHECIMENTO_DIR

        texto = (CONHECIMENTO_DIR / "seguranca-do-paciente.md").read_text(encoding="utf-8")
        no_ar = texto.split("## O que já está no ar\n", 1)[1].split("\n## ", 1)[0]
        assert "**Configuração**" in no_ar
        assert "Baixar o QR" in no_ar
        assert "Copiar" in no_ar

    def test_o_kit_de_conhecimento_diz_o_link_de_voltar_das_telas(self):
        """O Assistente responde "como volto para a página do Núcleo?" pelo
        kit (issue #2249). Mutante: apagar a frase do link de voltar."""
        from app.services.conhecimento import CONHECIMENTO_DIR

        texto = (CONHECIMENTO_DIR / "seguranca-do-paciente.md").read_text(encoding="utf-8")
        no_ar = texto.split("## O que já está no ar\n", 1)[1].split("\n## ", 1)[0]
        assert "o link Núcleo de Segurança do Paciente, com a seta de voltar" in no_ar
        assert "o caso aberto de uma notificação volta para Notificações" in no_ar
