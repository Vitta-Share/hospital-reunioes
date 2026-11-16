"""O quórum da reunião do Núcleo (issue #1774, PRD #1764).

Função pura: entram as Participações do Núcleo, a presença registrada e o dia
da reunião; sai se a reunião foi instalada. Conta para quórum quem, no dia da
reunião, estava em Ativo, A vencer ou Em carência. O quórum é metade deles,
com a Presidência ou o suplente presente.

As bordas da issue: número ímpar de membros, Presidência ausente com suplente
presente, os dois ausentes. Datas fixas: a função não lê o relógio.
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.seguranca_do_paciente.quorum import apurar_quorum, conta_para_quorum  # noqa: E402

DIA = date(2026, 12, 10)


def _p(pid: str, papel: str = "membro", **campos) -> dict:
    base = {
        "participante_id": pid,
        "papel": papel,
        "vigencia_inicio": "2026-01-01",
        "vigencia_fim": "2027-12-31",
        "encerrada_em": None,
        "termo_assinado_em": "2026-01-05T12:00:00+00:00",
    }
    return {**base, **campos}


def _nucleo(n_membros: int) -> list[dict]:
    """Presidência, suplente e mais `n_membros - 2` membros."""
    return [_p("PRES", "presidencia"), _p("SUPL", "suplente")] + [_p(f"M{i}") for i in range(n_membros - 2)]


def _presentes(*ids: str) -> dict[str, str]:
    return {pid: "presente" for pid in ids}


class TestQuemContaParaQuorum:
    def test_ativo_conta(self):
        assert conta_para_quorum(_p("A"), DIA) is True

    def test_a_vencer_conta(self):
        assert conta_para_quorum(_p("A", vigencia_fim="2027-01-15"), DIA) is True

    def test_em_carencia_conta(self):
        """O fim foi há 20 dias: carência de 30."""
        assert conta_para_quorum(_p("A", vigencia_fim="2026-11-20"), DIA) is True

    def test_vencido_nao_conta(self):
        assert conta_para_quorum(_p("A", vigencia_fim="2026-10-01"), DIA) is False

    def test_sem_termo_nao_conta(self):
        assert conta_para_quorum(_p("A", termo_assinado_em=None), DIA) is False

    def test_termo_assinado_depois_da_reuniao_nao_conta(self):
        assert conta_para_quorum(_p("A", termo_assinado_em="2026-12-11T12:00:00+00:00"), DIA) is False

    def test_participacao_que_comecou_depois_da_reuniao_nao_conta(self):
        assert conta_para_quorum(_p("A", vigencia_inicio="2026-12-11"), DIA) is False

    def test_encerrada_antes_da_reuniao_nao_conta(self):
        p = _p("A", encerrada_em="2026-12-01", vigencia_fim="2026-12-01")
        assert conta_para_quorum(p, DIA) is False

    def test_encerrada_depois_da_reuniao_contava_no_dia(self):
        p = _p("A", encerrada_em="2026-12-20", vigencia_fim="2026-12-20")
        assert conta_para_quorum(p, DIA) is True


class TestQuorum:
    def test_metade_com_a_presidencia_instala(self):
        q = apurar_quorum(_nucleo(4), _presentes("PRES", "M0"), DIA)

        assert (q.total, q.presentes, q.minimo, q.instalada) == (4, 2, 2, True)

    def test_numero_impar_exige_mais_da_metade_arredondada_para_cima(self):
        """Cinco membros: metade é 2,5, então dois presentes não bastam."""
        dois = apurar_quorum(_nucleo(5), _presentes("PRES", "M0"), DIA)
        tres = apurar_quorum(_nucleo(5), _presentes("PRES", "M0", "M1"), DIA)

        assert (dois.minimo, dois.instalada) == (3, False)
        assert (tres.minimo, tres.instalada) == (3, True)

    def test_presidencia_ausente_com_suplente_presente_instala(self):
        presenca = {"PRES": "ausente_justificado", "SUPL": "presente", "M0": "presente", "M1": "presente"}

        q = apurar_quorum(_nucleo(5), presenca, DIA)

        assert q.presidencia_ou_suplente is True
        assert q.instalada is True

    def test_presidencia_e_suplente_ausentes_nao_instala_mesmo_com_maioria(self):
        presenca = {"PRES": "ausente", "SUPL": "ausente", "M0": "presente", "M1": "presente", "M2": "presente"}

        q = apurar_quorum(_nucleo(5), presenca, DIA)

        assert q.presentes == 3
        assert q.presidencia_ou_suplente is False
        assert q.instalada is False

    def test_convidado_e_ausente_justificado_nao_contam_como_presentes(self):
        presenca = {"PRES": "presente", "M0": "convidado", "M1": "ausente_justificado"}

        q = apurar_quorum(_nucleo(4), presenca, DIA)

        assert (q.presentes, q.instalada) == (1, False)

    def test_presente_que_nao_conta_para_quorum_nao_entra_na_conta(self):
        """O membro sem Termo veio, mas não soma: nem no total nem nos presentes."""
        participacoes = _nucleo(4) + [_p("SEMTERMO", termo_assinado_em=None)]

        q = apurar_quorum(participacoes, _presentes("PRES", "SEMTERMO"), DIA)

        assert (q.total, q.presentes, q.instalada) == (4, 1, False)

    def test_suplente_sem_termo_nao_supre_a_presidencia(self):
        participacoes = [_p("PRES", "presidencia"), _p("SUPL", "suplente", termo_assinado_em=None), _p("M0"), _p("M1")]
        presenca = {"SUPL": "presente", "M0": "presente", "M1": "presente"}

        q = apurar_quorum(participacoes, presenca, DIA)

        assert q.presidencia_ou_suplente is False
        assert q.instalada is False

    def test_nucleo_sem_ninguem_que_conte_nao_instala(self):
        q = apurar_quorum([], {}, DIA)

        assert (q.total, q.instalada) == (0, False)
