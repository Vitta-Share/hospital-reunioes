"""Motor de prazos para os prazos legais do Núcleo (issue #1984, ADR 0107 decisão 2).

O cálculo puro da Ouvidoria (`ouvidoria_prazos`) ganha duas regras que os
prazos do Regimento e da ANVISA pedem: a unidade de dias corridos e o 15º dia
útil do mês seguinte. A Ouvidoria não usa nenhuma das duas; os testes dela
(`test_ouvidoria_prazos.py`) seguem sem mudança.

Calendário de referência: 20/11/2026 é sexta (Consciência Negra), 02/11/2026 é
segunda (Finados) e 01/01/2027 é sexta (Confraternização).
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
UTC = ZoneInfo("UTC")

SEM_FERIADO: frozenset[date] = frozenset()


def _sp(ano: int, mes: int, dia: int, hora: int = 0, minuto: int = 0, segundo: int = 0) -> datetime:
    return datetime(ano, mes, dia, hora, minuto, segundo, tzinfo=FUSO)


class TestDiasCorridos:
    """Dia corrido é dia de calendário: fim de semana e feriado contam."""

    def test_tres_dias_corridos_de_sexta_vencem_na_segunda_mesmo_com_feriado_no_caminho(self):
        """Sexta 20/11 10h mais 3 dias corridos é segunda 23/11, no fim do dia.
        Sábado, domingo e o feriado da própria segunda entram na conta; em dias
        úteis o mesmo prazo cairia na quinta 26/11."""
        from app.services.ouvidoria_prazos import DIAS_CORRIDOS, Prazo, calcular_vencimento

        feriados = frozenset({date(2026, 11, 20), date(2026, 11, 23)})

        vencimento = calcular_vencimento(_sp(2026, 11, 20, 10), Prazo(3, DIAS_CORRIDOS), feriados)

        assert vencimento == _sp(2026, 11, 23, 23, 59, 59)

    def test_sessenta_dias_corridos_atravessam_a_virada_de_ano(self):
        """O prazo legal de 60 dias corridos, contado de 20/11/2026, vence em
        19/01/2027."""
        from app.services.ouvidoria_prazos import DIAS_CORRIDOS, Prazo, calcular_vencimento

        vencimento = calcular_vencimento(_sp(2026, 11, 20, 10), Prazo(60, DIAS_CORRIDOS), SEM_FERIADO)

        assert vencimento == _sp(2027, 1, 19, 23, 59, 59)

    def test_dias_corridos_nao_viram_minutos_de_expediente(self):
        """Como as horas corridas, não existe conversão honesta para tempo útil."""
        import pytest

        from app.services.ouvidoria_prazos import DIAS_CORRIDOS, Prazo, minutos_do_prazo

        with pytest.raises(ValueError):
            minutos_do_prazo(Prazo(60, DIAS_CORRIDOS))


class TestDecimoQuintoDiaUtilDoMesSeguinte:
    """O 15º dia útil do mês que vem, pelo calendário útil e pelos feriados.
    Dia útil é dia de expediente: vence no fechamento, às 17h."""

    def test_sem_feriado_o_decimo_quinto_dia_util_de_novembro_e_o_dia_20(self):
        from app.services.ouvidoria_prazos import DIA_UTIL_DO_MES_SEGUINTE, Prazo, calcular_vencimento

        vencimento = calcular_vencimento(_sp(2026, 10, 10, 9), Prazo(15, DIA_UTIL_DO_MES_SEGUINTE), SEM_FERIADO)

        assert vencimento == _sp(2026, 11, 20, 17)

    def test_fim_de_semana_e_feriado_empurram_o_decimo_quinto_dia_util(self):
        """Com Finados (02/11) e Consciência Negra (20/11) cadastrados, o 15º
        dia útil de novembro de 2026 passa de sexta 20 para terça 24."""
        from app.services.ouvidoria_prazos import DIA_UTIL_DO_MES_SEGUINTE, Prazo, calcular_vencimento

        feriados = frozenset({date(2026, 11, 2), date(2026, 11, 20)})

        vencimento = calcular_vencimento(_sp(2026, 10, 10, 9), Prazo(15, DIA_UTIL_DO_MES_SEGUINTE), feriados)

        assert vencimento == _sp(2026, 11, 24, 17)

    def test_ocorrido_em_dezembro_vence_em_janeiro_do_ano_seguinte(self):
        """Com o feriado de 01/01/2027, o 15º dia útil de janeiro é sexta 22."""
        from app.services.ouvidoria_prazos import DIA_UTIL_DO_MES_SEGUINTE, Prazo, calcular_vencimento

        feriados = frozenset({date(2027, 1, 1)})

        vencimento = calcular_vencimento(_sp(2026, 12, 15, 9), Prazo(15, DIA_UTIL_DO_MES_SEGUINTE), feriados)

        assert vencimento == _sp(2027, 1, 22, 17)

    def test_o_mes_do_ocorrido_e_o_de_sao_paulo_e_nao_o_do_utc(self):
        """31/12 às 22h em São Paulo já é 01/01 em UTC. O mês seguinte é janeiro,
        e não fevereiro."""
        from app.services.ouvidoria_prazos import DIA_UTIL_DO_MES_SEGUINTE, Prazo, calcular_vencimento

        feriados = frozenset({date(2027, 1, 1)})
        ocorrido_em_utc = datetime(2027, 1, 1, 1, 0, tzinfo=UTC)

        vencimento = calcular_vencimento(ocorrido_em_utc, Prazo(15, DIA_UTIL_DO_MES_SEGUINTE), feriados)

        assert vencimento == _sp(2027, 1, 22, 17)


class _ConsultaDeFeriados:
    """O pedaço do PostgREST que a leitura por intervalo usa."""

    def __init__(self, linhas: list[dict]):
        self.linhas = linhas
        self.filtros: list[tuple[str, str, str]] = []

    def select(self, _colunas: str):
        return self

    def gte(self, coluna: str, valor: str):
        self.filtros.append(("gte", coluna, valor))
        return self

    def lte(self, coluna: str, valor: str):
        self.filtros.append(("lte", coluna, valor))
        return self

    def execute(self):
        def _passa(linha: dict) -> bool:
            return all(linha["data"] >= v if op == "gte" else linha["data"] <= v for op, _c, v in self.filtros)

        dentro = [linha for linha in self.linhas if _passa(linha)]
        return type("Resposta", (), {"data": dentro})()


class _BancoDeFeriados:
    def __init__(self, linhas: list[dict]):
        self.linhas = linhas
        self.tabelas_lidas: list[str] = []

    def table(self, nome: str):
        self.tabelas_lidas.append(nome)
        return _ConsultaDeFeriados(self.linhas)


class TestCarregadorDeFeriadosComum:
    """O carregador de feriados saiu do router da Ouvidoria para um serviço
    comum (ADR 0107, decisão 2). Ouvidoria e Núcleo leem pelo mesmo lugar."""

    def test_a_ouvidoria_carrega_os_feriados_pelo_servico_comum(self):
        """O router da Ouvidoria não tem cópia própria: os nomes que os jobs e
        a tela do responsável importam de lá são os do serviço."""
        from app.routers import ouvidoria as ouvidoria_router
        from app.services import feriados

        assert ouvidoria_router.carregar_feriados_ou_degradado is feriados.carregar_feriados_ou_degradado
        assert ouvidoria_router.carregar_feriados is feriados.carregar_feriados

    def test_o_servico_le_os_feriados_cadastrados_no_intervalo(self):
        from app.services import feriados

        banco = _BancoDeFeriados(
            [{"data": "2026-11-02"}, {"data": "2026-11-20"}, {"data": "2026-12-25"}, {"data": "2027-01-01"}]
        )

        lidos = feriados.feriados_entre(banco, date(2026, 11, 1), date(2026, 12, 31))

        assert lidos == frozenset({date(2026, 11, 2), date(2026, 11, 20), date(2026, 12, 25)})
        assert banco.tabelas_lidas == ["ouvidoria_feriados"]

    def test_a_pauta_do_nucleo_le_os_feriados_pelo_servico_comum(self, monkeypatch):
        from app.services import feriados
        from app.services.seguranca_do_paciente import pauta

        do_servico = frozenset({date(2027, 3, 10)})
        monkeypatch.setattr(feriados, "feriados_entre", lambda _sb, _inicio, _fim: do_servico)

        assert pauta.feriados_entre(None, date(2027, 1, 1), date(2027, 12, 31)) == do_servico

    def test_o_encerramento_da_ata_do_nucleo_le_os_feriados_pelo_servico_comum(self, monkeypatch):
        from app.services import feriados
        from app.services.seguranca_do_paciente import assinatura_da_ata

        do_servico = frozenset({date(2026, 11, 20)})
        monkeypatch.setattr(feriados, "feriados_entre", lambda _sb, _inicio, _fim: do_servico)

        assert assinatura_da_ata._feriados(None, date(2026, 11, 18), date(2027, 1, 17)) == do_servico

    def test_a_pauta_do_nucleo_segue_contando_sem_feriado_quando_a_leitura_falha(self, monkeypatch):
        """A pauta é fail-open (erra para o lado de mostrar antes); o
        encerramento da ata segue deixando a falha subir."""
        import httpx
        import pytest

        from app.services import feriados
        from app.services.seguranca_do_paciente import assinatura_da_ata, pauta

        def _falha(_sb, _inicio, _fim):
            raise httpx.ConnectTimeout("banco fora")

        monkeypatch.setattr(feriados, "feriados_entre", _falha)

        assert pauta.feriados_entre(None, date(2027, 1, 1), date(2027, 12, 31)) == frozenset()
        with pytest.raises(httpx.HTTPError):
            assinatura_da_ata._feriados(None, date(2026, 11, 18), date(2027, 1, 17))
