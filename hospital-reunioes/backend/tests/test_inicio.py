"""O Início com a Minha Fila das Pendências (issue #1934, PRD #1932, ADR 0104).

Um endpoint monta o Início de quem pede chamando uma função por módulo, a
fonte. Esta fatia tem uma fonte só, a de Pendências: as abertas em que a pessoa
é responsável ou co-responsável, inclusive a Pendência sem Reunião (o lembrete
da Agenda regulatória do Núcleo). O grupo de cada item e a frase do topo são
funções puras; o atraso sai da data, nunca do status gravado.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers import inicio as inicio_router  # noqa: E402
from app.services import inicio  # noqa: E402
from app.services.inicio import fonte_pendencias  # noqa: E402
from app.services.inicio.regras import dias_de_atraso, frase_do_inicio, grupo_do_prazo  # noqa: E402

BRT = ZoneInfo("America/Sao_Paulo")
# Quarta-feira, 18/11/2026, 10h em Brasília.
AGORA = datetime(2026, 11, 18, 10, 0, tzinfo=BRT)
HOJE = AGORA.date()


# ─── O banco de mentira ───────────────────────────────────────────────────


@dataclass
class _Result:
    data: list


class _Consulta:
    def __init__(self, linhas: list[dict]):
        self._linhas = linhas
        self._filtros: list = []

    def select(self, *_a, **_kw):
        return self

    def eq(self, coluna, valor):
        self._filtros.append(lambda linha: linha.get(coluna) == valor)
        return self

    def in_(self, coluna, valores):
        valores = set(valores)
        self._filtros.append(lambda linha: linha.get(coluna) in valores)
        return self

    def is_(self, coluna, valor):
        assert valor == "null"
        self._filtros.append(lambda linha: linha.get(coluna) is None)
        return self

    def execute(self):
        return _Result([dict(linha) for linha in self._linhas if all(f(linha) for f in self._filtros)])


@dataclass
class _Banco:
    pendencias: list = field(default_factory=list)
    reunioes: list = field(default_factory=list)

    def table(self, nome):
        return _Consulta(getattr(self, nome))


def _pendencia(id_acao: str, **campos) -> dict:
    base = {
        "id_acao": id_acao,
        "descricao_acao": f"Ação {id_acao}",
        "responsavel_id": "P_OUTRO",
        "co_responsavel_id": None,
        "id_reuniao": "R1",
        "prazo": (HOJE + timedelta(days=3)).isoformat(),
        "status": "PENDENTE",
        "deleted_at": None,
        "created_at": "2026-11-01T12:00:00+00:00",
    }
    return {**base, **campos}


REUNIAO = {"id_reuniao": "R1", "titulo": "Reunião de Atendimento", "data": "2026-10-28"}
REUNIAO_DO_NUCLEO = {"id_reuniao": "RN", "titulo": "Reunião ordinária do Núcleo", "data": "2026-10-21"}

AURORA = {"id": "P_AURORA", "nome_completo": "Aurora Lima", "access_profile": "regular"}
SECRETARIA = {"id": "P_SEC", "nome_completo": "Selma Souza", "access_profile": "secretaria"}


@pytest.fixture
def nucleo(monkeypatch):
    """O que a pessoa alcança do Núcleo: sem nada, por padrão. Cada teste
    liga o que precisa. A regra de verdade mora em `dependencies` e tem teste
    próprio; aqui ela é a entrada."""
    estado = {"ocultas": [], "recursos": frozenset()}
    monkeypatch.setattr(fonte_pendencias, "reunioes_ocultas", lambda _sb, _me: list(estado["ocultas"]))
    monkeypatch.setattr(fonte_pendencias, "recursos_nsp_da_pessoa", lambda _sb, _me: estado["recursos"])
    return estado


def _rota(monkeypatch, me: dict | None, banco: _Banco, agora: datetime = AGORA):
    async def _participante(_user, _sb, fields=None):
        return me

    monkeypatch.setattr(inicio_router, "get_participante_for_user", _participante)
    monkeypatch.setattr(inicio_router, "agora_em_brasilia", lambda: agora)

    import asyncio

    return asyncio.run(inicio_router.get_inicio(current_user={"id": "u1"}, supabase=banco))


def _ids(resposta) -> list[str]:
    return [item.id for item in resposta.itens]


# ═══════════════════════════════════════════════════════════════════════════
# 1. As Pendências abertas de quem é responsável ou co-responsável
# ═══════════════════════════════════════════════════════════════════════════


class TestFonteDePendencias:
    def test_responsavel_ve_a_pendencia_aberta_dele(self, monkeypatch, nucleo):
        banco = _Banco(pendencias=[_pendencia("A001", responsavel_id="P_AURORA")], reunioes=[REUNIAO])

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A001"]
        item = resposta.itens[0]
        assert item.titulo == "Ação A001"
        assert item.area == "Reuniões"
        assert item.origem == "Reunião de Atendimento, de 28/10/2026."
        assert item.destino == "/pendencias/kanban?highlight=A001"

    def test_co_responsavel_ve_a_pendencia_e_sabe_que_divide(self, monkeypatch, nucleo):
        banco = _Banco(
            pendencias=[_pendencia("A002", responsavel_id="P_OUTRO", co_responsavel_id="P_AURORA")],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A002"]
        assert resposta.itens[0].origem == "Reunião de Atendimento, de 28/10/2026. Você é co-responsável."

    def test_so_as_abertas_e_so_as_dela(self, monkeypatch, nucleo):
        banco = _Banco(
            pendencias=[
                _pendencia("A010", responsavel_id="P_AURORA", status="PENDENTE"),
                _pendencia("A011", responsavel_id="P_AURORA", status="EM_PROGRESSO"),
                _pendencia("A012", responsavel_id="P_AURORA", status="ATRASADO"),
                _pendencia("A013", responsavel_id="P_AURORA", status="REPACTUADA"),
                _pendencia("A014", responsavel_id="P_AURORA", status="CONCLUIDO"),
                _pendencia("A015", responsavel_id="P_AURORA", status="CANCELADO"),
                _pendencia("A016", responsavel_id="P_AURORA", deleted_at="2026-11-10T00:00:00+00:00"),
                _pendencia("A017", responsavel_id="P_OUTRO"),
            ],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert sorted(_ids(resposta)) == ["A010", "A011", "A012", "A013"]

    def test_presidencia_ve_o_lembrete_sem_reuniao_que_abre_a_agenda(self, monkeypatch, nucleo):
        nucleo["recursos"] = frozenset({"agenda", "ver_modulo"})
        banco = _Banco(
            pendencias=[
                _pendencia(
                    "A020",
                    responsavel_id="P_AURORA",
                    id_reuniao=None,
                    descricao_acao="Agenda regulatória: relatório trimestral à vigilância",
                )
            ]
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A020"]
        item = resposta.itens[0]
        assert item.titulo == "Agenda regulatória: relatório trimestral à vigilância"
        assert item.area == "Segurança do Paciente"
        assert item.origem == "Lembrete da Agenda regulatória do Núcleo."
        assert item.destino == "/seguranca-do-paciente/agenda"

    def test_quem_nao_alcanca_a_agenda_nao_ve_o_lembrete(self, monkeypatch, nucleo):
        """O lembrete leva o evento do Núcleo (ADR 0095, decisão 4): quem saiu
        da Presidência e não alcança mais a Agenda não o lê pelo Início."""
        banco = _Banco(pendencias=[_pendencia("A021", responsavel_id="P_AURORA", id_reuniao=None)])

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == []

    def test_pendencia_de_reuniao_do_nucleo_fora_do_alcance_nao_aparece(self, monkeypatch, nucleo):
        nucleo["ocultas"] = ["RN"]
        banco = _Banco(
            pendencias=[
                _pendencia("A030", responsavel_id="P_AURORA", id_reuniao="RN"),
                _pendencia("A031", responsavel_id="P_AURORA", id_reuniao="R1"),
            ],
            reunioes=[REUNIAO, REUNIAO_DO_NUCLEO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A031"]


# ═══════════════════════════════════════════════════════════════════════════
# 2. A Secretária não recebe dado nenhum
# ═══════════════════════════════════════════════════════════════════════════


class TestSecretaria:
    def test_secretaria_e_recusada_sem_dado_nenhum(self, monkeypatch, nucleo):
        banco = _Banco(pendencias=[_pendencia("A040", responsavel_id="P_SEC")], reunioes=[REUNIAO])

        with pytest.raises(HTTPException) as recusa:
            _rota(monkeypatch, SECRETARIA, banco)

        assert recusa.value.status_code == 403
        assert "A040" not in str(recusa.value.detail)


# ═══════════════════════════════════════════════════════════════════════════
# 3. O grupo de cada item, pela hora de Brasília
# ═══════════════════════════════════════════════════════════════════════════

# O prazo de 20/11 vence quando o dia 20 acaba em Brasília: 21/11, 0h.
PRAZO = date(2026, 11, 20)


class TestGrupoDoPrazo:
    def test_a_47_horas_do_prazo_vence_em_ate_48_horas(self):
        agora = datetime(2026, 11, 19, 1, 0, tzinfo=BRT)
        assert grupo_do_prazo(PRAZO, agora) == "ate_48_horas"

    def test_a_49_horas_do_prazo_entra_nos_proximos_7_dias(self):
        agora = datetime(2026, 11, 18, 23, 0, tzinfo=BRT)
        assert grupo_do_prazo(PRAZO, agora) == "proximos_7_dias"

    def test_prazo_de_ontem_passou_do_prazo(self):
        assert grupo_do_prazo(HOJE - timedelta(days=1), AGORA) == "passou_do_prazo"

    def test_prazo_de_hoje_so_vence_no_fim_do_dia_em_brasilia(self):
        # 23h30 de 18/11 em Brasília já é 19/11 em UTC: o prazo de 18/11
        # ainda não venceu.
        agora_utc = datetime(2026, 11, 19, 2, 30, tzinfo=UTC)
        assert grupo_do_prazo(date(2026, 11, 18), agora_utc) == "ate_48_horas"
        # Meia-noite de 19/11 em Brasília: venceu.
        meia_noite = datetime(2026, 11, 19, 3, 0, tzinfo=UTC)
        assert grupo_do_prazo(date(2026, 11, 18), meia_noite) == "passou_do_prazo"

    def test_alem_de_7_dias_e_sem_prazo_ficam_fora_dos_grupos(self):
        assert grupo_do_prazo(HOJE + timedelta(days=8), AGORA) is None
        assert grupo_do_prazo(None, AGORA) is None

    def test_a_rota_agrupa_conta_e_ordena_do_mais_atrasado_ao_mais_distante(self, monkeypatch, nucleo):
        banco = _Banco(
            pendencias=[
                _pendencia("A050", responsavel_id="P_AURORA", prazo=(HOJE + timedelta(days=5)).isoformat()),
                _pendencia("A051", responsavel_id="P_AURORA", prazo=(HOJE - timedelta(days=12)).isoformat()),
                _pendencia("A052", responsavel_id="P_AURORA", prazo=HOJE.isoformat()),
                _pendencia("A053", responsavel_id="P_AURORA", prazo=(HOJE - timedelta(days=2)).isoformat()),
            ],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert _ids(resposta) == ["A051", "A053", "A052", "A050"]
        assert [i.grupo for i in resposta.itens] == [
            "passou_do_prazo",
            "passou_do_prazo",
            "ate_48_horas",
            "proximos_7_dias",
        ]
        assert [i.dias_de_atraso for i in resposta.itens] == [12, 2, None, None]
        assert resposta.contadores.model_dump() == {
            "passou_do_prazo": 2,
            "ate_48_horas": 1,
            "proximos_7_dias": 1,
        }


# ═══════════════════════════════════════════════════════════════════════════
# 4. O atraso sai da data, nunca do status ATRASADO
# ═══════════════════════════════════════════════════════════════════════════


class TestAtrasoPelaData:
    def test_pendente_de_prazo_vencido_esta_atrasada(self, monkeypatch, nucleo):
        """O job ainda não marcou ATRASADO: o Início vê o atraso pela data."""
        banco = _Banco(
            pendencias=[
                _pendencia(
                    "A060", responsavel_id="P_AURORA", status="PENDENTE", prazo=(HOJE - timedelta(days=3)).isoformat()
                )
            ],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert resposta.itens[0].grupo == "passou_do_prazo"
        assert resposta.itens[0].dias_de_atraso == 3
        assert resposta.contadores.passou_do_prazo == 1

    def test_atrasado_gravado_com_prazo_futuro_nao_conta_como_vencido(self, monkeypatch, nucleo):
        banco = _Banco(
            pendencias=[
                _pendencia(
                    "A061", responsavel_id="P_AURORA", status="ATRASADO", prazo=(HOJE + timedelta(days=4)).isoformat()
                )
            ],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert resposta.itens[0].grupo == "proximos_7_dias"
        assert resposta.contadores.passou_do_prazo == 0

    def test_dias_de_atraso_contam_no_calendario_de_brasilia(self):
        # 22h de 18/11 em Brasília (01h de 19/11 em UTC): o prazo de 17/11
        # está a um dia, não a dois.
        agora_utc = datetime(2026, 11, 19, 1, 0, tzinfo=UTC)
        assert dias_de_atraso(date(2026, 11, 17), agora_utc) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. A frase do topo, por regra, sem IA
# ═══════════════════════════════════════════════════════════════════════════


def _frase(**numeros):
    base = {"nome": "Aurora", "vencidos": 0, "maior_atraso": 0, "em_48_horas": 0, "proximo_prazo": None}
    return frase_do_inicio(**{**base, **numeros})


class TestFrase:
    def test_um_vencido(self):
        assert _frase(vencidos=1, maior_atraso=1) == ("Aurora, um prazo seu venceu.", "Ele espera há 1 dia.")

    def test_varios_vencidos_com_o_mais_antigo_e_os_de_48_horas(self):
        assert _frase(vencidos=3, maior_atraso=12, em_48_horas=2) == (
            "Aurora, três prazos seus venceram.",
            "O mais antigo espera há 12 dias. Mais dois vencem em até 48 horas.",
        )

    def test_vencido_com_um_em_48_horas(self):
        assert _frase(vencidos=2, maior_atraso=5, em_48_horas=1)[1] == (
            "O mais antigo espera há 5 dias. Mais um vence em até 48 horas."
        )

    def test_sem_vencido_com_um_item_em_48_horas(self):
        assert _frase(em_48_horas=1) == ("Aurora, nada atrasado.", "Um prazo vence em até 48 horas.")

    def test_sem_vencido_com_varios_itens_em_48_horas(self):
        assert _frase(em_48_horas=4) == ("Aurora, nada atrasado.", "Quatro prazos vencem em até 48 horas.")

    def test_em_dia_com_proximo_prazo(self):
        assert _frase(proximo_prazo=date(2026, 11, 24)) == (
            "Aurora, você está em dia.",
            "O próximo prazo é 24/11.",
        )

    def test_em_dia_sem_prazo_nenhum(self):
        assert _frase() == ("Aurora, você está em dia.", "Nenhum prazo aberto no seu nome.")

    def test_mais_de_dez_vira_numero(self):
        assert _frase(vencidos=14, maior_atraso=30)[0] == "Aurora, 14 prazos seus venceram."

    def test_sem_nome_a_frase_abre_com_maiuscula(self):
        assert _frase(nome=None, vencidos=1, maior_atraso=2)[0] == "Um prazo seu venceu."

    def test_a_rota_escreve_a_frase_com_o_primeiro_nome_e_o_proximo_prazo(self, monkeypatch, nucleo):
        banco = _Banco(
            pendencias=[_pendencia("A070", responsavel_id="P_AURORA", prazo=(HOJE + timedelta(days=20)).isoformat())],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert resposta.frase.titulo == "Aurora, você está em dia."
        assert resposta.frase.apoio == "O próximo prazo é 08/12."

    def test_a_frase_nao_chama_ia(self, monkeypatch, nucleo):
        """Qualquer chamada ao provedor de IA estoura: a rota tem que montar a
        frase do mesmo jeito (ADR 0104, decisão 7)."""
        from app.services import ai_processor

        def _proibido(*_a, **_kw):
            raise AssertionError("o Início chamou a IA")

        for nome in dir(ai_processor):
            if not nome.startswith("_") and callable(getattr(ai_processor, nome)):
                monkeypatch.setattr(ai_processor, nome, _proibido, raising=False)
        banco = _Banco(
            pendencias=[_pendencia("A071", responsavel_id="P_AURORA", prazo=(HOJE - timedelta(days=2)).isoformat())],
            reunioes=[REUNIAO],
        )

        resposta = _rota(monkeypatch, AURORA, banco)

        assert resposta.frase.titulo == "Aurora, um prazo seu venceu."
        fonte = "".join(
            caminho.read_text(encoding="utf-8") for caminho in sorted((Path(inicio.__file__).parent).glob("*.py"))
        )
        assert "ai_processor" not in fonte and "anthropic" not in fonte.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 6. A fonte que lança erro não derruba a resposta
# ═══════════════════════════════════════════════════════════════════════════


class TestFonteQueFalha:
    def test_fonte_que_lanca_erro_vira_aviso_e_as_outras_seguem(self):
        def _quebrada(_sb, _me):
            raise RuntimeError("PostgREST fora do ar")

        def _boa(_sb, _me):
            return [
                {
                    "tipo": "pendencia",
                    "id": "A080",
                    "titulo": "Enviar a escala",
                    "origem": "Reunião de Atendimento, de 17/11/2026.",
                    "prazo": HOJE + timedelta(days=1),
                    "area": "Reuniões",
                    "acao": "Abrir a Pendência",
                    "destino": "/pendencias/kanban?highlight=A080",
                }
            ]

        fontes = (
            inicio.Fonte("ouvidoria", "os casos da Ouvidoria", _quebrada),
            inicio.Fonte("pendencias", "as Pendências", _boa),
        )

        resposta = inicio.montar_inicio(_Banco(), AURORA, AGORA, fontes=fontes)

        assert _ids(resposta) == ["A080"]
        assert [(a.fonte, a.mensagem) for a in resposta.avisos] == [
            ("ouvidoria", "Não foi possível carregar os casos da Ouvidoria agora. Tente de novo em instantes.")
        ]
        assert resposta.frase.titulo == "Aurora, nada atrasado."

    def test_pendencias_fora_do_ar_pela_rota_devolve_aviso(self, monkeypatch, nucleo):
        class _BancoQuebrado:
            def table(self, _nome):
                raise RuntimeError("timeout")

        resposta = _rota(monkeypatch, AURORA, _BancoQuebrado())

        assert resposta.itens == []
        assert [a.fonte for a in resposta.avisos] == ["pendencias"]
