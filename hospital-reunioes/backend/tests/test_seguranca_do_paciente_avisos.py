"""Os avisos do Termo sem assinatura e do fim da vigência (issue #1770, PRD #1764).

O que a issue promete, um bloco por critério de aceite:

1. cada marco avisa os destinatários certos, e rodar o job duas vezes no
   mesmo dia não envia de novo;
2. o aviso de assinatura para depois que o membro assina;
3. os e-mails trazem data absoluta, destinatário nominal e nenhum travessão;
4. o job não chama IA;
5. a falha de envio fica registrada e não derruba os outros avisos do dia;
6. o texto do Produto no Kit de conhecimento diz o comportamento novo.

O banco é um dublê em memória e o e-mail é sempre dublado. Nenhum nome ou
e-mail de pessoa real: as pessoas daqui são de teste. As datas saem de um dia
fixo.
"""

from __future__ import annotations

import inspect
import os
import re
import sys
import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from postgrest.exceptions import APIError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.cron import scheduler  # noqa: E402
from app.services.seguranca_do_paciente import avisos  # noqa: E402

DIA = date(2026, 11, 16)
NUCLEO = {"id": "col-nsp", "slug": "nsp", "nome": "Núcleo de Segurança do Paciente", "setor_id": None}

# A chave única de cada tabela, como a migration declara.
_UNICAS = {"nsp_avisos": ("participacao_id", "marco", "referencia", "destinatario_id")}


# ═══════════════════════════════════════════════════════════════════════════
# O dublê do banco e do e-mail
# ═══════════════════════════════════════════════════════════════════════════


class _Consulta:
    def __init__(self, banco: _Banco, nome: str):
        self._banco = banco
        self._nome = nome
        self._linhas = banco.tabelas.setdefault(nome, [])
        self._filtros: list = []
        self._ordem: tuple[str, bool] | None = None
        self._inicio = 0
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

    def range(self, inicio, fim):
        self._inicio, self._teto = inicio, fim - inicio + 1
        return self

    def execute(self):
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
        casam = casam[self._inicio :]
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

    def table(self, nome: str):
        return _Consulta(self, nome)


@pytest.fixture
def emails(monkeypatch):
    """O e-mail é sempre dublado: guarda o que sairia."""
    enviados: list[dict] = []

    def _falso(destinatario, assunto, html_content, texto_fallback, **_kw):
        enviados.append({"para": destinatario, "assunto": assunto, "html": html_content, "texto": texto_fallback})
        return True

    monkeypatch.setattr(avisos, "_enviar_email", _falso)
    return enviados


# ═══════════════════════════════════════════════════════════════════════════
# Pessoas e cenário
# ═══════════════════════════════════════════════════════════════════════════


def _pessoa(pid: str, **campos) -> dict[str, Any]:
    base = {
        "id": pid,
        "nome_completo": f"Pessoa de Teste {pid}",
        "email": f"{pid.lower()}@hsm.test",
        "ativo": True,
        "perfil_ouvidoria": None,
        "perfil_nsp": None,
        "role": None,
    }
    return {**base, **campos}


PRESIDENTE = _pessoa("P1")
MEMBRO = _pessoa("P2")
DIRETOR = _pessoa("P9", perfil_ouvidoria="diretoria_executiva")


def _participacao(participante: str, papel: str = "membro", **campos) -> dict[str, Any]:
    """Vigente em DIA, com o Termo assinado e o fim longe."""
    base = {
        "id": f"part-{participante}",
        "colegiado_id": NUCLEO["id"],
        "participante_id": participante,
        "papel": papel,
        "vigencia_inicio": "2025-01-01",
        "vigencia_fim": (DIA + timedelta(days=300)).isoformat(),
        "encerrada_em": None,
        "termo_gerado_em": "2025-01-02T12:00:00+00:00",
        "termo_enviado_em": "2025-01-02T12:00:00+00:00",
        "termo_assinado_em": "2025-01-03T12:00:00+00:00",
    }
    return {**base, **campos}


def _sem_assinatura(participante: str, gerado_em: date) -> tuple[dict, dict]:
    """A Participação esperando a assinatura, e o envio aberto do Termo,
    gerado ao meio-dia (horário de Brasília) do dia `gerado_em`."""
    carimbo = f"{gerado_em.isoformat()}T15:00:00+00:00"
    participacao = _participacao(
        participante, termo_gerado_em=carimbo, termo_enviado_em=carimbo, termo_assinado_em=None
    )
    envio = {
        "id": f"envio-{participante}",
        "participacao_id": participacao["id"],
        "situacao": "enviado",
        "created_at": carimbo,
    }
    return participacao, envio


def _banco(participacoes: list[dict], envios: list[dict] | None = None, pessoas: list[dict] | None = None) -> _Banco:
    return _Banco(
        {
            "participantes": [dict(p) for p in (pessoas or [PRESIDENTE, MEMBRO, DIRETOR])],
            "colegiados": [dict(NUCLEO)],
            "participacoes": [_participacao("P1", "presidencia", vigencia_fim=(DIA + timedelta(days=800)).isoformat())]
            + [dict(p) for p in participacoes],
            "nsp_termos_envios": [dict(e) for e in (envios or [])],
            "nsp_avisos": [],
        }
    )


def _para(emails: list[dict]) -> list[str]:
    return sorted(e["para"] for e in emails)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Cada marco avisa os destinatários certos, uma vez só
# ═══════════════════════════════════════════════════════════════════════════


class TestMarcos:
    def test_tres_dias_sem_assinatura_avisa_o_membro(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=3))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p2@hsm.test"]
        assert emails[0]["assunto"].startswith("Assine o Termo de Adesão")

    @pytest.mark.parametrize(
        ("dias", "assunto"),
        [
            (0, "gerado em"),
            (7, "pendente desde"),
        ],
    )
    def test_documento_gerado_e_sete_dias_avisam_so_o_membro(self, emails, dias, assunto):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=dias))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p2@hsm.test"]
        assert assunto in emails[0]["assunto"]

    def test_quatorze_dias_sem_assinatura_avisam_o_membro_e_a_presidencia(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=14))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p1@hsm.test", "p2@hsm.test"]
        para_presidencia = next(e for e in emails if e["para"] == "p1@hsm.test")
        assert para_presidencia["assunto"].startswith("Cobre a assinatura do Termo de Adesão de Pessoa de Teste P2")

    def test_dois_dias_depois_do_documento_gerado_nada_novo_sai(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=2))
        banco = _banco([participacao], [envio])
        avisos.avisar(banco, DIA - timedelta(days=2))
        emails.clear()

        avisos.avisar(banco, DIA)

        assert emails == []

    def test_o_job_parado_uns_dias_manda_so_o_marco_mais_adiantado(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=8))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert len(emails) == 1
        assert [a["marco"] for a in banco.tabelas["nsp_avisos"]] == ["assinatura_7"]

    @pytest.mark.parametrize("faltam", [60, 30])
    def test_sessenta_e_trinta_dias_do_fim_avisam_o_membro_e_a_presidencia(self, emails, faltam):
        banco = _banco([_participacao("P2", vigencia_fim=(DIA + timedelta(days=faltam)).isoformat())])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p1@hsm.test", "p2@hsm.test"]
        fim = (DIA + timedelta(days=faltam)).strftime("%d/%m/%Y")
        assert all(fim in e["assunto"] for e in emails)

    def test_sessenta_e_um_dias_do_fim_ainda_nao_avisam(self, emails):
        banco = _banco([_participacao("P2", vigencia_fim=(DIA + timedelta(days=61)).isoformat())])

        avisos.avisar(banco, DIA)

        assert emails == []

    def test_o_aviso_de_trinta_dias_vem_depois_do_de_sessenta(self, emails):
        fim = DIA + timedelta(days=30)
        banco = _banco([_participacao("P2", vigencia_fim=fim.isoformat())])
        avisos.avisar(banco, fim - timedelta(days=60))

        avisos.avisar(banco, DIA)

        marcos = sorted({a["marco"] for a in banco.tabelas["nsp_avisos"]})
        assert marcos == ["vigencia_30", "vigencia_60"]
        assert len(emails) == 4

    def test_fim_da_carencia_sem_renovacao_avisa_a_presidencia_e_a_diretoria_executiva(self, emails):
        fim = DIA - timedelta(days=31)
        banco = _banco([_participacao("P2", vigencia_fim=fim.isoformat())])

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p1@hsm.test", "p9@hsm.test"]
        fim_da_carencia = (fim + timedelta(days=30)).strftime("%d/%m/%Y")
        assert all(fim_da_carencia in e["assunto"] for e in emails)

    def test_o_ultimo_dia_da_carencia_ainda_nao_avisa(self, emails):
        banco = _banco([_participacao("P2", vigencia_fim=(DIA - timedelta(days=30)).isoformat())])

        avisos.avisar(banco, DIA)

        assert emails == []

    def test_participacao_encerrada_nao_recebe_aviso(self, emails):
        fim = DIA + timedelta(days=30)
        banco = _banco([_participacao("P2", vigencia_fim=fim.isoformat(), encerrada_em=fim.isoformat())])

        avisos.avisar(banco, DIA)

        assert emails == []

    def test_a_presidencia_que_e_o_proprio_membro_recebe_um_aviso_so(self, emails):
        banco = _banco([])
        banco.tabelas["participacoes"][0]["vigencia_fim"] = (DIA + timedelta(days=30)).isoformat()

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p1@hsm.test"]
        assert emails[0]["assunto"].startswith("Renove a sua participação")

    def test_rodar_duas_vezes_no_mesmo_dia_nao_envia_de_novo(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=14))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)
        primeira = len(emails)
        segunda = avisos.avisar(banco, DIA)

        assert primeira == 2
        assert len(emails) == primeira
        assert segunda == {"enviados": 0, "falhas": 0}

    def test_cada_aviso_nasce_registrado_e_nominal(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=14))
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        registros = banco.tabelas["nsp_avisos"]
        assert sorted(a["destinatario_id"] for a in registros) == ["P1", "P2"]
        assert {a["situacao"] for a in registros} == {"enviado"}

    def test_a_renovacao_recomeca_os_avisos_da_vigencia(self, emails):
        banco = _banco([_participacao("P2", vigencia_fim=(DIA + timedelta(days=30)).isoformat())])
        avisos.avisar(banco, DIA)
        banco.tabelas["participacoes"][1]["vigencia_fim"] = (DIA + timedelta(days=395)).isoformat()
        emails.clear()

        avisos.avisar(banco, DIA + timedelta(days=365))

        assert _para(emails) == ["p1@hsm.test", "p2@hsm.test"]

    def test_o_reenvio_do_termo_recomeca_a_contagem(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=3))
        banco = _banco([participacao], [envio])
        avisos.avisar(banco, DIA)
        banco.tabelas["nsp_termos_envios"][0]["situacao"] = "cancelado"
        banco.tabelas["nsp_termos_envios"].append(
            {**envio, "id": "envio-novo", "created_at": f"{(DIA + timedelta(days=1)).isoformat()}T15:00:00+00:00"}
        )
        emails.clear()

        avisos.avisar(banco, DIA + timedelta(days=4))

        assert _para(emails) == ["p2@hsm.test"]
        assert (DIA + timedelta(days=1)).strftime("%d/%m/%Y") in emails[0]["assunto"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. O aviso de assinatura para depois que o membro assina
# ═══════════════════════════════════════════════════════════════════════════


class TestDepoisDaAssinatura:
    def test_o_membro_que_assinou_nao_recebe_mais_o_aviso_de_assinatura(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=3))
        banco = _banco([participacao], [envio])
        avisos.avisar(banco, DIA)
        # A assinatura chega como o retorno da assinatura eletrônica a grava.
        banco.tabelas["participacoes"][1]["termo_assinado_em"] = f"{DIA.isoformat()}T18:00:00+00:00"
        banco.tabelas["nsp_termos_envios"][0]["situacao"] = "assinado"
        emails.clear()

        for dias in (7, 14):
            avisos.avisar(banco, DIA + timedelta(days=dias))

        assert emails == []

    def test_a_liberacao_sem_assinatura_tambem_para_o_aviso(self, emails):
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=14))
        participacao["termo_assinado_em"] = f"{DIA.isoformat()}T12:00:00+00:00"
        banco = _banco([participacao], [envio])

        avisos.avisar(banco, DIA)

        assert emails == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. Data absoluta, destinatário nominal e nenhum travessão
# ═══════════════════════════════════════════════════════════════════════════

_TRAVESSOES = re.compile("[–—]")
_DATA_ABSOLUTA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
_DATA_RELATIVA = re.compile(r"\b(amanhã|ontem|hoje|daqui a|em \d+ dias)\b", re.IGNORECASE)


def _todos_os_emails(emails: list[dict]) -> list[dict]:
    """Um cenário que dispara todos os marcos de uma vez, com nomes que trazem
    travessão do cadastro."""
    com_travessao = [
        _pessoa("P1", nome_completo="Presidente — de Teste"),
        _pessoa("P2", nome_completo="Membro – de Teste"),
        _pessoa("P3"),
        _pessoa("P4"),
        _pessoa("P5"),
        _pessoa("P9", perfil_ouvidoria="diretoria_executiva", nome_completo="Diretoria — de Teste"),
    ]
    participacoes, envios = [], []
    for pid, dias in (("P2", 0), ("P3", 14)):
        participacao, envio = _sem_assinatura(pid, DIA - timedelta(days=dias))
        participacoes.append(participacao)
        envios.append(envio)
    participacoes.append(_participacao("P4", vigencia_fim=(DIA + timedelta(days=60)).isoformat()))
    participacoes.append(_participacao("P5", vigencia_fim=(DIA - timedelta(days=40)).isoformat()))
    banco = _banco(participacoes, envios, com_travessao)
    avisos.avisar(banco, DIA)
    assert {a["marco"] for a in banco.tabelas["nsp_avisos"]} == {
        "documento_gerado",
        "assinatura_14",
        "vigencia_60",
        "fim_da_carencia",
    }
    return emails


class TestOEmail:
    def test_o_detector_de_travessao_pega_o_travessao_e_a_meia_risca(self):
        """Piso do detector."""
        assert _TRAVESSOES.search("a — b") and _TRAVESSOES.search("a – b")

    def test_nenhum_email_sai_com_travessao(self, emails):
        for email in _todos_os_emails(emails):
            for parte in ("assunto", "html", "texto"):
                assert not _TRAVESSOES.search(email[parte]), (email["para"], parte)

    def test_todo_assunto_traz_data_absoluta_e_nenhuma_relativa(self, emails):
        for email in _todos_os_emails(emails):
            assert _DATA_ABSOLUTA.search(email["assunto"]), email["assunto"]
            assert not _DATA_RELATIVA.search(email["assunto"] + email["texto"]), email["assunto"]

    def test_todo_email_abre_com_o_nome_de_quem_recebe(self, emails):
        nomes = {"p1@hsm.test": "Presidente", "p2@hsm.test": "Membro", "p9@hsm.test": "Diretoria"}
        for email in _todos_os_emails(emails):
            esperado = nomes.get(email["para"], f"Pessoa de Teste {email['para'][:2].upper()}")
            assert email["texto"].startswith(f"Olá, {esperado}"), email["texto"][:40]
            assert esperado in email["html"]

    def test_o_assunto_diz_a_acao_pedida(self, emails):
        acoes = ("Assine ", "Cobre ", "Renove ", "Recomponha ")
        for email in _todos_os_emails(emails):
            assert email["assunto"].startswith(acoes), email["assunto"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. A falha de envio fica registrada e não derruba os outros avisos
# ═══════════════════════════════════════════════════════════════════════════


class TestFalhaDeEnvio:
    def _cenario(self) -> _Banco:
        participacoes, envios = [], []
        for pid in ("P2", "P3"):
            participacao, envio = _sem_assinatura(pid, DIA - timedelta(days=3))
            participacoes.append(participacao)
            envios.append(envio)
        return _banco(participacoes, envios, [PRESIDENTE, MEMBRO, _pessoa("P3"), DIRETOR])

    def test_o_provedor_que_explode_num_aviso_nao_para_o_outro(self, monkeypatch):
        enviados: list[str] = []

        def _explode_no_p2(destinatario, *_a, **_kw):
            if destinatario == "p2@hsm.test":
                raise RuntimeError("provedor fora do ar")
            enviados.append(destinatario)
            return True

        monkeypatch.setattr(avisos, "_enviar_email", _explode_no_p2)
        banco = self._cenario()

        resultado = avisos.avisar(banco, DIA)

        assert enviados == ["p3@hsm.test"]
        assert resultado == {"enviados": 1, "falhas": 1}
        situacao = {a["destinatario_id"]: a for a in banco.tabelas["nsp_avisos"]}
        assert situacao["P2"]["situacao"] == "falhou"
        assert situacao["P2"]["erro"]
        assert situacao["P3"]["situacao"] == "enviado"

    def test_o_provedor_que_recusa_fica_registrado(self, monkeypatch):
        monkeypatch.setattr(avisos, "_enviar_email", lambda *_a, **_kw: False)
        banco = self._cenario()

        avisos.avisar(banco, DIA)

        assert {a["situacao"] for a in banco.tabelas["nsp_avisos"]} == {"falhou"}

    def test_a_pessoa_sem_email_fica_registrada_e_os_outros_saem(self, emails):
        banco = self._cenario()
        banco.tabelas["participantes"][1]["email"] = None

        avisos.avisar(banco, DIA)

        assert _para(emails) == ["p3@hsm.test"]
        situacao = {a["destinatario_id"]: a["situacao"] for a in banco.tabelas["nsp_avisos"]}
        assert situacao == {"P2": "falhou", "P3": "enviado"}


# ═══════════════════════════════════════════════════════════════════════════
# 4. O job não chama IA
# ═══════════════════════════════════════════════════════════════════════════

# O que denuncia IA no código: os módulos do app que falam com provedor de
# modelo e os SDKs.
_MARCAS_DE_IA = ("ai_processor", "anthropic", "openai", "openrouter")


def _marcas(codigo: str) -> list[str]:
    return [marca for marca in _MARCAS_DE_IA if marca in codigo.lower()]


class TestSemIa:
    def test_o_detector_reconhece_um_modulo_que_chama_ia(self):
        """Piso do detector: o módulo de IA do app tem marca."""
        from app.services import ai_processor

        assert _marcas(inspect.getsource(ai_processor))

    def test_o_servico_dos_avisos_nao_fala_com_ia(self):
        """Mutante: importar o `ai_processor` no serviço dos avisos."""
        assert _marcas(inspect.getsource(avisos)) == []

    def test_o_job_do_scheduler_so_chama_o_servico(self):
        assert _marcas(inspect.getsource(scheduler.avisar_termo_e_vigencia_nsp)) == []
        assert "avisos.avisar(" in inspect.getsource(scheduler.avisar_termo_e_vigencia_nsp)

    def test_o_job_esta_registrado_uma_vez_por_dia(self):
        assert 'avisar_termo_e_vigencia_nsp,\n        "cron"' in inspect.getsource(scheduler.start_scheduler)

    def test_os_avisos_saem_com_o_provedor_de_ia_fora_do_ar(self, emails, monkeypatch):
        import anthropic

        def _explode(*_a, **_kw):
            raise AssertionError("o job dos avisos chamou IA")

        monkeypatch.setattr(anthropic, "Anthropic", _explode)
        monkeypatch.setattr(anthropic, "AsyncAnthropic", _explode)
        participacao, envio = _sem_assinatura("P2", DIA - timedelta(days=14))

        resultado = avisos.avisar(_banco([participacao], [envio]), DIA)

        assert resultado == {"enviados": 2, "falhas": 0}

    def test_o_job_le_o_dia_em_sao_paulo_e_chama_o_servico(self, monkeypatch):
        chamadas: list[date] = []
        monkeypatch.setattr(scheduler, "_supabase", lambda: "banco")
        monkeypatch.setattr(scheduler, "_hoje_em_sao_paulo", lambda: DIA)
        monkeypatch.setattr(avisos, "avisar", lambda _banco, hoje: chamadas.append(hoje) or {"enviados": 0})

        scheduler.avisar_termo_e_vigencia_nsp()

        assert chamadas == [DIA]

    def test_o_job_que_falha_nao_derruba_o_scheduler(self, monkeypatch):
        monkeypatch.setattr(scheduler, "_supabase", lambda: "banco")

        def _explode(*_a):
            raise RuntimeError("banco fora do ar")

        monkeypatch.setattr(avisos, "avisar", _explode)

        scheduler.avisar_termo_e_vigencia_nsp()


# ═══════════════════════════════════════════════════════════════════════════
# 6. O texto do Produto no Kit de conhecimento diz o comportamento novo
# ═══════════════════════════════════════════════════════════════════════════


def _secao_do_kit(titulo: str) -> str:
    from app.services.conhecimento import CONHECIMENTO_DIR

    texto = (CONHECIMENTO_DIR / "seguranca-do-paciente.md").read_text(encoding="utf-8")
    partes = texto.split(f"## {titulo}\n", 1)
    assert len(partes) == 2, f"a seção {titulo!r} sumiu do kit"
    return partes[1].split("\n## ", 1)[0]


class TestKitDeConhecimento:
    def test_os_avisos_estao_no_que_ja_esta_no_ar(self):
        """Mutante: deixar o kit dizendo que os avisos chegam depois."""
        secao = _secao_do_kit("O que já está no ar")
        assert "3 e 7 dias" in secao
        assert "14 dias" in secao
        assert "60 e 30 dias" in secao
        assert "carência" in secao
        assert "Diretoria Executiva" in secao

    def test_os_avisos_sairam_do_que_ele_ainda_nao_faz(self):
        assert "aviso" not in _secao_do_kit("O que ele ainda não faz").lower()
