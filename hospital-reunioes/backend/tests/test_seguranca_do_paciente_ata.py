"""A ata do Núcleo em dez blocos, validada só pela Presidência (issue #1775,
PRD #1764, ADR 0095, decisão 10).

O que a issue promete, um bloco por critério:

1. com a IA dublada, a ata final traz os quatro blocos do sistema
   (identificação, presenças e quórum, pendências da reunião anterior e
   indicadores) mesmo quando a saída do agente os contradiz;
2. a minuta com nome de membro fora do bloco de presenças é recusada e refeita
   uma vez; se falhar de novo, a tela avisa e deixa a Presidência redigir;
3. membro comum recebe recusa ao tentar validar; a Presidência valida;
4. cada deliberação da ata validada vira pendência com responsável e prazo;
5. a IA só roda depois do clique de importar a transcrição;
6. a ata gerada não tem travessão nem meia-risca;
7. a reunião de apresentação à Diretoria gera a ata resumida;
8. o kit de conhecimento diz o comportamento novo.

O banco é o dublê em memória dos testes das reuniões do Núcleo. A IA, a
assinatura e o Storage são sempre dublados: um fixture autouse faz qualquer
chamada de verdade ao provedor de IA ou à assinatura estourar. Nenhum nome, registro ou e-mail de pessoa real. A reunião
é de outro dia que não hoje, para a data do sistema não coincidir com a de hoje.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from test_seguranca_do_paciente_reunioes import (  # noqa: E402
    HOJE,
    MEMBRO,
    NUCLEO,
    PRESIDENCIA,
    R_COMUM,
    SUPER_ADMIN,
    SUPER_ADMIN_PLENO,
    _assert_recusado,
    _Banco,
    _banco,
    _cliente,
    _Consulta,
    _participacao,
    _pessoa,
    _reuniao,
)

from app.limiter import limiter  # noqa: E402
from app.services import ai_processor, clicksign_service, storage  # noqa: E402

R_ATA = "RD_NUCLEO_ATA"
R_ANTERIOR = "RD_NUCLEO_ANT"
DIA_DA_REUNIAO = HOJE - timedelta(days=3)

SUPLENTE = _pessoa("SUPL1")
MEMBRO_3 = _pessoa("MEMB3")


class _ConsultaComLt(_Consulta):
    def lt(self, coluna, valor):
        return self._filtro(lambda linha: linha.get(coluna) is not None and str(linha[coluna]) < str(valor))


class _BancoDaAta(_Banco):
    def table(self, nome: str) -> _Consulta:
        return _ConsultaComLt(self, nome)


def _cenario(tipo: str = "Ordinária mensal") -> _BancoDaAta:
    """PRES1, SUPL1, MEMB1 e MEMB3 contam para quórum. A reunião foi há três
    dias, com PRES1, MEMB1 e MEMB3 presentes e SUPL1 ausente com justificativa.
    A ordinária anterior deixou a pendência A010, já concluída."""
    base = _banco()
    banco = _BancoDaAta(base.tabelas)
    banco.tabelas["participantes"] += [dict(SUPLENTE), dict(MEMBRO_3)]
    banco.tabelas["participacoes"] += [_participacao("SUPL1", papel="suplente"), _participacao("MEMB3")]
    for p in banco.tabelas["participacoes"]:
        p["vigencia_inicio"] = (HOJE - timedelta(days=60)).isoformat()
    reuniao = _reuniao(R_ATA, titulo="Ordinária de teste", tipo=tipo, colegiado=NUCLEO["id"])
    banco.tabelas["reunioes"].append(
        {
            **reuniao,
            "data": DIA_DA_REUNIAO.isoformat(),
            "hora_fim": "10:30:00",
            "status_ata": "PROGRAMADA",
            "json_ata": None,
        }
    )
    anterior = _reuniao(R_ANTERIOR, titulo="Ordinária anterior", tipo="Ordinária mensal", colegiado=NUCLEO["id"])
    banco.tabelas["reunioes"].append(
        {**anterior, "data": (HOJE - timedelta(days=33)).isoformat(), "status_ata": "APROVADA"}
    )
    banco.tabelas["pendencias"].append(
        {
            "id_acao": "A010",
            "id_reuniao": R_ANTERIOR,
            "descricao_acao": "Revisar o protocolo de quedas",
            "responsavel_nome": "Gerência de Enfermagem",
            "responsavel_id": None,
            "status": "CONCLUIDO",
            "prazo": (HOJE - timedelta(days=10)).isoformat(),
            "deleted_at": None,
        }
    )
    banco.tabelas["reuniao_participantes"].append({"id_reuniao": R_ATA, "participante_id": "PRES1"})
    banco.tabelas["reuniao_presencas"] = [
        {"id_reuniao": R_ATA, "participante_id": pid, "situacao": situacao, "registrada_por": "PRES1"}
        for pid, situacao in (
            ("PRES1", "presente"),
            ("MEMB1", "presente"),
            ("MEMB3", "presente"),
            ("SUPL1", "ausente_justificado"),
        )
    ]
    return banco


# ─── A IA e o Storage dublados ──────────────────────────────────────────────


class _IaDublada:
    """Devolve, em ordem, as minutas da fila; a última se repete."""

    def __init__(self):
        self.minutas: list[Any] = [_minuta()]
        self.chamadas: list[dict] = []

    def __call__(self, client, model, *, system, usuario, ata=False):
        self.chamadas.append({"model": model, "system": system, "usuario": usuario})
        minuta = self.minutas[min(len(self.chamadas), len(self.minutas)) - 1]
        return minuta if isinstance(minuta, str) else json.dumps(minuta, ensure_ascii=False)


def _minuta(**blocos) -> dict[str, Any]:
    """Uma saída do agente que contradiz os quatro blocos do sistema."""
    return {
        "blocos": {
            "identificacao": ["Reunião extraordinária em 01/01/2020"],
            "presencas_e_quorum": ["Todos os membros presentes"],
            "pendencias_anteriores": ["Nenhuma pendência anterior"],
            "indicadores": ["Taxa de quedas de 9 por mil"],
            "casos_analisados": [],
            "plano_de_acao": ["Revisar a sinalização dos leitos de risco de queda"],
            "alertas_sanitarios": ["Alerta da Anvisa sobre bombas de infusão, sem impacto no hospital"],
            "proxima_reuniao": ["Data a confirmar pela Presidência"],
            **blocos,
        },
        "deliberacoes": [
            {
                "texto": "Treinar as equipes no protocolo de quedas",
                "responsavel": "Coordenação de Enfermagem",
                "prazo": (HOJE + timedelta(days=30)).isoformat(),
                "notificacao": None,
            }
        ],
        "trechos_a_conferir": [],
    }


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(autouse=True)
def _ia(monkeypatch) -> _IaDublada:
    def _estoura(*_a, **_kw):
        raise AssertionError("teste chamou a IA de verdade")

    dublada = _IaDublada()
    monkeypatch.setattr(ai_processor, "_llm_provider", lambda: "anthropic")
    monkeypatch.setattr(ai_processor, "_get_llm", lambda: (object(), "modelo-errado"))
    monkeypatch.setattr(ai_processor.anthropic, "Anthropic", _estoura)
    monkeypatch.setattr(ai_processor, "_pedir_json", dublada)
    monkeypatch.setattr(ai_processor, "_pedir_texto", _estoura)
    monkeypatch.setattr(storage, "upload_file", lambda *a, **kw: "https://storage.test/transcricao.txt")
    # A assinatura também nunca sai de verdade.
    monkeypatch.setattr(clicksign_service, "start_signature_flow", _estoura)
    return dublada


def _importar(cliente, rid: str = R_ATA):
    return cliente.post(
        f"/api/reunioes/{rid}/anexar-transcricao",
        files={"file": ("reuniao.txt", "Fala de teste da reunião do Núcleo.".encode(), "text/plain")},
    )


def _ata_gravada(banco: _Banco, rid: str = R_ATA) -> dict[str, Any]:
    return next(r for r in banco.tabelas["reunioes"] if r["id_reuniao"] == rid)["json_ata"]


def _bloco(ata: dict[str, Any], chave: str) -> list[str]:
    return next(b for b in ata["blocos"] if b["chave"] == chave)["itens"]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os quatro blocos do sistema vencem a saída do agente
# ═══════════════════════════════════════════════════════════════════════════


class TestBlocosDoSistema:
    def test_ata_traz_os_blocos_do_sistema_mesmo_quando_o_agente_os_contradiz(self):
        banco = _cenario()

        resposta = _importar(_cliente(PRESIDENCIA, banco))

        assert resposta.status_code == 200, resposta.text
        ata = _ata_gravada(banco)
        assert [b["chave"] for b in ata["blocos"]] == [
            "identificacao",
            "presencas_e_quorum",
            "pendencias_anteriores",
            "indicadores",
            "casos_analisados",
            "deliberacoes",
            "plano_de_acao",
            "alertas_sanitarios",
            "proxima_reuniao",
            "assinaturas",
        ]
        identificacao = " ".join(_bloco(ata, "identificacao"))
        assert DIA_DA_REUNIAO.strftime("%d/%m/%Y") in identificacao
        assert "Ordinária mensal" in identificacao
        assert "2020" not in identificacao
        presencas = _bloco(ata, "presencas_e_quorum")
        assert "Presentes: Pessoa de Teste MEMB1, Pessoa de Teste MEMB3, Pessoa de Teste PRES1." in presencas
        assert "Ausentes com justificativa: Pessoa de Teste SUPL1." in presencas
        assert "Quórum: 3 presentes de 4 que contam, mínimo de 2. Reunião instalada." in presencas
        assert "Todos os membros presentes" not in presencas
        pendencias = " ".join(_bloco(ata, "pendencias_anteriores"))
        assert "Revisar o protocolo de quedas" in pendencias
        assert "Concluída" in pendencias
        assert _bloco(ata, "indicadores") == ["Sem dados nesta fase."]
        assert _bloco(ata, "plano_de_acao") == ["Revisar a sinalização dos leitos de risco de queda"]
        reuniao = next(r for r in banco.tabelas["reunioes"] if r["id_reuniao"] == R_ATA)
        assert reuniao["status_ata"] == "AGUARDANDO_VALIDACAO"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Nome de membro fora das presenças: recusa, uma nova tentativa, e a
#    Presidência redige
# ═══════════════════════════════════════════════════════════════════════════


def _com_nome(nome: str) -> dict[str, Any]:
    return _minuta(plano_de_acao=[f"{nome} vai revisar a sinalização dos leitos"])


class TestNomesForaDasPresencas:
    def test_minuta_com_nome_de_membro_e_refeita_uma_vez(self, _ia):
        _ia.minutas = [_com_nome("Pessoa de Teste MEMB3"), _minuta()]
        banco = _cenario()

        _importar(_cliente(PRESIDENCIA, banco))

        assert len(_ia.chamadas) == 2
        assert "recusada" not in _ia.chamadas[0]["usuario"]
        assert "recusada porque trazia nome de membro" in _ia.chamadas[1]["usuario"]
        ata = _ata_gravada(banco)
        assert _bloco(ata, "plano_de_acao") == ["Revisar a sinalização dos leitos de risco de queda"]
        assert ata["aviso"] is None

    def test_recusada_de_novo_a_tela_avisa_e_deixa_a_presidencia_redigir(self, _ia):
        # A segunda traz o nome curto (primeiro e último), sem acento e em
        # minúsculas: a checagem não depende da grafia.
        _ia.minutas = [_com_nome("Pessoa de Teste MEMB3"), _com_nome("pessoa memb1")]
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)

        _importar(cliente)

        assert len(_ia.chamadas) == 2
        tela = cliente.get(f"/api/nsp/reunioes/{R_ATA}/ata")
        assert tela.status_code == 200, tela.text
        corpo = tela.json()
        assert corpo["ata"]["aviso"] == (
            "A IA escreveu nome de membro fora da lista de presença duas vezes, e a minuta foi descartada. "
            "Redija os blocos do Núcleo abaixo."
        )
        assert corpo["pode_conduzir"] is True
        assert _bloco(corpo["ata"], "plano_de_acao") == []
        assert corpo["status_ata"] == "AGUARDANDO_VALIDACAO"

        redigida = cliente.put(
            f"/api/nsp/reunioes/{R_ATA}/ata",
            json={
                "blocos": {"plano_de_acao": ["Revisar a sinalização"], "alertas_sanitarios": [], "proxima_reuniao": []},
                "deliberacoes": [
                    {"texto": "Treinar as equipes", "responsavel": "Coordenação de Enfermagem", "prazo": "a definir"}
                ],
            },
        )

        assert redigida.status_code == 200, redigida.text
        ata = _ata_gravada(banco)
        assert _bloco(ata, "plano_de_acao") == ["Revisar a sinalização"]
        assert ata["aviso"] is None
        assert ata["deliberacoes"][0]["responsavel"] == "Coordenação de Enfermagem"
        assert "Pessoa de Teste PRES1" in " ".join(_bloco(ata, "presencas_e_quorum"))

    def test_o_nome_no_responsavel_da_deliberacao_nao_recusa_a_minuta(self, _ia):
        minuta = _minuta()
        minuta["deliberacoes"][0]["responsavel"] = "Pessoa de Teste MEMB3"
        _ia.minutas = [minuta]
        banco = _cenario()

        _importar(_cliente(PRESIDENCIA, banco))

        assert len(_ia.chamadas) == 1
        assert _ata_gravada(banco)["deliberacoes"][0]["responsavel"] == "Pessoa de Teste MEMB3"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Quem valida: a Presidência, o suplente em exercício e o Acesso pleno
# ═══════════════════════════════════════════════════════════════════════════


def _validar(cliente, rid: str = R_ATA):
    return cliente.post(f"/api/nsp/reunioes/{rid}/ata/validar")


def _status(banco: _Banco, rid: str = R_ATA) -> str:
    return next(r for r in banco.tabelas["reunioes"] if r["id_reuniao"] == rid)["status_ata"]


def _pendencias_da_ata(banco: _Banco) -> list[dict[str, Any]]:
    return [p for p in banco.tabelas["pendencias"] if p["id_reuniao"] == R_ATA]


def _com_ata() -> _BancoDaAta:
    banco = _cenario()
    _importar(_cliente(PRESIDENCIA, banco))
    assert _status(banco) == "AGUARDANDO_VALIDACAO"
    return banco


def _presenca_de(banco: _Banco, **situacoes: str) -> None:
    for linha in banco.tabelas["reuniao_presencas"]:
        if linha["participante_id"] in situacoes:
            linha["situacao"] = situacoes[linha["participante_id"]]


class TestQuemValida:
    def test_membro_comum_recebe_recusa_ao_validar(self):
        banco = _com_ata()
        cliente = _cliente(MEMBRO, banco)

        resposta = _validar(cliente)

        _assert_recusado(resposta)
        assert _status(banco) == "AGUARDANDO_VALIDACAO"
        assert _pendencias_da_ata(banco) == []
        assert cliente.get(f"/api/nsp/reunioes/{R_ATA}/ata").json()["pode_conduzir"] is False

    def test_membro_comum_nao_valida_pelas_rotas_gerais_da_reuniao(self):
        banco = _com_ata()
        cliente = _cliente(MEMBRO, banco)

        for rota in ("aprovar", "aprovar-sem-assinatura"):
            resposta = cliente.post(f"/api/reunioes/{R_ATA}/{rota}")
            assert resposta.status_code == 409, resposta.text
            assert "Segurança do Paciente" in resposta.json()["detail"]
        assert _status(banco) == "AGUARDANDO_VALIDACAO"
        assert _pendencias_da_ata(banco) == []

    def test_membro_comum_nao_reescreve_a_ata(self):
        banco = _com_ata()

        resposta = _cliente(MEMBRO, banco).put(f"/api/nsp/reunioes/{R_ATA}/ata", json={"deliberacoes": []})

        _assert_recusado(resposta)
        assert len(_ata_gravada(banco)["deliberacoes"]) == 1

    def test_super_admin_sem_acesso_pleno_nao_le_nem_valida(self):
        banco = _com_ata()
        cliente = _cliente(SUPER_ADMIN, banco)

        _assert_recusado(cliente.get(f"/api/nsp/reunioes/{R_ATA}/ata"))
        _assert_recusado(_validar(cliente))
        assert _status(banco) == "AGUARDANDO_VALIDACAO"

    def test_a_presidencia_valida(self):
        banco = _com_ata()

        resposta = _validar(_cliente(PRESIDENCIA, banco))

        assert resposta.status_code == 200, resposta.text
        assert _status(banco) == "APROVADA"
        assert _ata_gravada(banco)["validacao"]["por"] == "PRES1"

    def test_o_acesso_pleno_valida(self):
        banco = _com_ata()

        resposta = _validar(_cliente(SUPER_ADMIN_PLENO, banco))

        assert resposta.status_code == 200, resposta.text
        assert _status(banco) == "APROVADA"

    def test_suplente_valida_so_quando_esta_em_exercicio(self):
        banco = _com_ata()
        _presenca_de(banco, SUPL1="presente")
        cliente = _cliente(SUPLENTE, banco)

        _assert_recusado(_validar(cliente))
        _presenca_de(banco, PRES1="ausente_justificado")
        resposta = _validar(cliente)

        assert resposta.status_code == 200, resposta.text
        assert _ata_gravada(banco)["validacao"]["por"] == "SUPL1"

    def test_membro_comum_nao_importa_a_transcricao_do_nucleo(self, _ia):
        banco = _cenario()

        resposta = _importar(_cliente(MEMBRO, banco))

        _assert_recusado(resposta)
        assert _ia.chamadas == []
        assert _status(banco) == "PROGRAMADA"

    def test_a_ata_guiada_recusa_a_reuniao_do_nucleo(self):
        """A Guiada gravaria a ata comum e a reunião travaria em validação, sem
        rota que a aprove (revisão do PR #1798). Recusa até para a Presidência."""
        banco = _cenario(tipo="Reunião rápida de segurança")
        cliente = _cliente(PRESIDENCIA, banco)
        rascunho = {"resumo_executivo": "Conversa rápida", "quadro_atribuicoes": []}

        chat = cliente.post(
            f"/api/reunioes/{R_ATA}/ata-guiada/chat",
            json={"rascunho": rascunho, "messages": [{"role": "user", "content": "Oi"}]},
        )
        concluir = cliente.post(f"/api/reunioes/{R_ATA}/ata-guiada/concluir", json={"rascunho": rascunho})

        for resposta in (chat, concluir):
            assert resposta.status_code == 409, resposta.text
            assert "Segurança do Paciente" in resposta.json()["detail"]
        assert _status(banco) == "PROGRAMADA"
        assert _ata_gravada(banco) is None

    def test_a_tela_da_reuniao_sabe_que_ela_e_do_nucleo(self):
        cliente = _cliente(SUPER_ADMIN_PLENO, _cenario())

        assert cliente.get(f"/api/reunioes/{R_ATA}").json()["do_nucleo"] is True
        assert cliente.get(f"/api/reunioes/{R_COMUM}").json()["do_nucleo"] is False

    def test_reuniao_comum_nao_passa_pela_rota_da_ata_do_nucleo(self):
        resposta = _validar(_cliente(PRESIDENCIA, _cenario()), rid=R_COMUM)

        assert resposta.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 4. Cada deliberação validada vira pendência com responsável e prazo
# ═══════════════════════════════════════════════════════════════════════════


class TestDeliberacoesViramPendencias:
    def test_cada_deliberacao_vira_pendencia_com_responsavel_e_prazo(self, _ia):
        minuta = _minuta()
        minuta["deliberacoes"].append(
            {"texto": "Trocar as pulseiras de risco", "responsavel": "Farmácia", "prazo": "15/01/2027"}
        )
        _ia.minutas = [minuta]
        banco = _com_ata()

        resposta = _validar(_cliente(PRESIDENCIA, banco))

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["total_pendencias"] == 2
        criadas = {
            p["descricao_acao"]: (p["responsavel_nome"], p["prazo"], p["status"]) for p in _pendencias_da_ata(banco)
        }
        assert criadas == {
            "Treinar as equipes no protocolo de quedas": (
                "Coordenação de Enfermagem",
                (HOJE + timedelta(days=30)).isoformat(),
                "PENDENTE",
            ),
            "Trocar as pulseiras de risco": ("Farmácia", "2027-01-15", "PENDENTE"),
        }

    def test_deliberacao_sem_responsavel_ou_sem_prazo_segura_a_validacao(self, _ia):
        minuta = _minuta()
        minuta["deliberacoes"] = [{"texto": "Trocar as pulseiras", "responsavel": "a definir", "prazo": None}]
        _ia.minutas = [minuta]
        banco = _com_ata()
        cliente = _cliente(PRESIDENCIA, banco)

        recusada = _validar(cliente)

        assert recusada.status_code == 422
        assert "sem responsável" in recusada.json()["detail"]
        assert "sem prazo" in recusada.json()["detail"]
        assert _pendencias_da_ata(banco) == []
        assert _status(banco) == "AGUARDANDO_VALIDACAO"

        cliente.put(
            f"/api/nsp/reunioes/{R_ATA}/ata",
            json={"deliberacoes": [{"texto": "Trocar as pulseiras", "responsavel": "Farmácia", "prazo": "2027-01-15"}]},
        )
        assert _validar(cliente).status_code == 200
        assert [(p["responsavel_nome"], p["prazo"]) for p in _pendencias_da_ata(banco)] == [("Farmácia", "2027-01-15")]

    def test_validar_de_novo_nao_duplica_pendencia(self):
        banco = _com_ata()
        cliente = _cliente(PRESIDENCIA, banco)
        _validar(cliente)

        segunda = _validar(cliente)

        assert segunda.status_code == 409
        assert len(_pendencias_da_ata(banco)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. A IA só roda no clique de importar a transcrição
# ═══════════════════════════════════════════════════════════════════════════

APP = os.path.join(os.path.dirname(__file__), "..", "app")


class TestIaSoNoClique:
    def test_a_ia_so_roda_depois_do_clique_de_importar(self, _ia):
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)
        assert cliente.get(f"/api/nsp/reunioes/{R_ATA}/ata").json()["ata"] is None
        cliente.get(f"/api/nsp/reunioes/{R_ATA}/presenca")
        cliente.get("/api/nsp/reunioes")
        assert _ia.chamadas == []

        _importar(cliente)

        assert len(_ia.chamadas) == 1
        assert _ia.chamadas[0]["model"] == "claude-sonnet-5-5"
        with open(os.path.join(APP, "prompts", "nsp_ata_do_nucleo.md"), encoding="utf-8") as arquivo:
            assert _ia.chamadas[0]["system"] == arquivo.read()
        assert "Fala de teste da reunião do Núcleo." in _ia.chamadas[0]["usuario"]

        cliente.get(f"/api/nsp/reunioes/{R_ATA}/ata")
        _validar(cliente)
        assert len(_ia.chamadas) == 1

    def test_so_o_pipeline_da_importacao_chama_a_minuta(self):
        """Nenhum job, nenhuma outra rota: a única chamada à minuta é a do
        pipeline que a importação da transcrição dispara."""
        chamadores = []
        for raiz, _pastas, arquivos in os.walk(APP):
            for nome in arquivos:
                if not nome.endswith(".py"):
                    continue
                caminho = os.path.join(raiz, nome)
                with open(caminho, encoding="utf-8") as arquivo:
                    if "redigir_minuta_do_nucleo(" in arquivo.read():
                        chamadores.append(os.path.relpath(caminho, APP))
        assert sorted(chamadores) == ["pipeline/orchestrator.py", "services/seguranca_do_paciente/ata.py"]


# ═══════════════════════════════════════════════════════════════════════════
# 6. Sem travessão nem meia-risca
# ═══════════════════════════════════════════════════════════════════════════


class TestSemTravessao:
    def test_a_ata_gerada_nao_tem_travessao_nem_meia_risca(self, _ia):
        minuta = _minuta(
            plano_de_acao=["Revisar a sinalização — leitos de risco", "Turnos 10–15 da manhã"],
            alertas_sanitarios=["Alerta – bombas de infusão"],
        )
        minuta["deliberacoes"][0]["texto"] = "Treinar as equipes — protocolo de quedas"
        minuta["trechos_a_conferir"] = ["Trecho – inaudível"]
        _ia.minutas = [minuta]
        banco = _cenario()
        cliente = _cliente(PRESIDENCIA, banco)

        _importar(cliente)

        texto = json.dumps(_ata_gravada(banco), ensure_ascii=False)
        assert "—" not in texto
        assert "–" not in texto
        assert _bloco(_ata_gravada(banco), "plano_de_acao") == [
            "Revisar a sinalização, leitos de risco",
            "Turnos 10-15 da manhã",
        ]

        cliente.put(
            f"/api/nsp/reunioes/{R_ATA}/ata",
            json={"blocos": {"plano_de_acao": ["Escrito à mão — pela Presidência"]}},
        )
        texto = json.dumps(_ata_gravada(banco), ensure_ascii=False)
        assert "—" not in texto
        assert "Escrito à mão, pela Presidência" in texto


# ═══════════════════════════════════════════════════════════════════════════
# 7. A apresentação à Diretoria gera a ata resumida
# ═══════════════════════════════════════════════════════════════════════════

CINCO_ITENS = [f"Ação {i} do plano" for i in range(1, 6)]


class TestAtaResumida:
    def test_a_apresentacao_a_diretoria_gera_a_ata_resumida(self, _ia):
        _ia.minutas = [_minuta(plano_de_acao=CINCO_ITENS)]
        banco = _cenario(tipo="Apresentação à Diretoria")

        _importar(_cliente(PRESIDENCIA, banco))

        ata = _ata_gravada(banco)
        assert ata["resumida"] is True
        assert "versão resumida da ata" in _ia.chamadas[0]["usuario"]
        assert _bloco(ata, "plano_de_acao") == CINCO_ITENS[:3]
        assert len(ata["blocos"]) == 10

    def test_a_ordinaria_gera_a_ata_inteira(self, _ia):
        _ia.minutas = [_minuta(plano_de_acao=CINCO_ITENS)]
        banco = _cenario()

        _importar(_cliente(PRESIDENCIA, banco))

        ata = _ata_gravada(banco)
        assert ata["resumida"] is False
        assert "resumida" not in _ia.chamadas[0]["usuario"]
        assert _bloco(ata, "plano_de_acao") == CINCO_ITENS


# ═══════════════════════════════════════════════════════════════════════════
# 8. O kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


class TestKitDeConhecimento:
    def test_o_kit_de_conhecimento_diz_o_comportamento_novo(self):
        with open(os.path.join(APP, "conhecimento", "seguranca-do-paciente.md"), encoding="utf-8") as arquivo:
            texto = " ".join(arquivo.read().split())

        assert "A IA escreve a minuta só quando a Presidência importa a transcrição" in texto
        assert "nenhuma rotina automática chama a IA" in texto
        assert "o que a IA escrever sobre eles é descartado" in texto
        assert "o aplicativo pede outra uma vez; se a segunda vier igual, a tela avisa" in texto
        assert "na reunião de apresentação à Diretoria, a ata é a resumida" in texto
        assert "só para eles a tela mostra os botões Revisar e Validar a ata" in texto
        assert "cada deliberação vira uma pendência da reunião, com o responsável e o prazo" in texto
        assert "—" not in texto
        assert "–" not in texto
