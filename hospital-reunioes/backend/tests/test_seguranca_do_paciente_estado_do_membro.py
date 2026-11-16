"""O estado do membro do Núcleo (issue #1766, PRD #1764).

Função pura: entram as datas da Participação e do Termo e o dia de hoje; sai um
dos oito estados. Nada é gravado como coluna editável. As bordas da issue: dia
60 antes do fim (A vencer), dia 30 depois do fim (último dia da carência).
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.seguranca_do_paciente.membros import estado_do_membro  # noqa: E402

FIM = date(2027, 6, 30)
INICIO = date(2026, 7, 1)
ASSINADO = "2026-07-02T10:00:00+00:00"


def _participacao(**campos) -> dict:
    base = {
        "vigencia_inicio": INICIO.isoformat(),
        "vigencia_fim": FIM.isoformat(),
        "encerrada_em": None,
        "termo_assinado_em": None,
    }
    return {**base, **campos}


def _dia(delta: int) -> date:
    return FIM + timedelta(days=delta)


class TestAntesDaAssinatura:
    def test_cadastrado_sem_documento(self):
        assert estado_do_membro(_participacao(), INICIO) == "cadastrado"

    def test_documento_gerado(self):
        p = _participacao(termo_gerado_em="2026-07-01T09:00:00+00:00")
        assert estado_do_membro(p, INICIO) == "documento_gerado"

    def test_aguardando_assinatura_quando_o_documento_foi_enviado(self):
        p = _participacao(termo_gerado_em="2026-07-01T09:00:00+00:00", termo_enviado_em="2026-07-01T09:01:00+00:00")
        assert estado_do_membro(p, INICIO) == "aguardando_assinatura"

    def test_sem_assinatura_e_com_o_fim_da_carencia_passado_e_vencido(self):
        assert estado_do_membro(_participacao(), _dia(31)) == "vencido"

    def test_sem_assinatura_nao_entra_em_carencia(self):
        """Carência é de quem tinha Termo válido: quem nunca assinou segue
        esperando a assinatura até vencer."""
        assert estado_do_membro(_participacao(), _dia(1)) == "cadastrado"


class TestDepoisDaAssinatura:
    @pytest.mark.parametrize(
        ("delta", "estado"),
        [
            (-200, "ativo"),
            (-61, "ativo"),
            (-60, "a_vencer"),  # dia 60 antes do fim
            (-1, "a_vencer"),
            (0, "a_vencer"),  # o último dia da vigência ainda vale
            (1, "em_carencia"),
            (30, "em_carencia"),  # último dia da carência
            (31, "vencido"),
            (400, "vencido"),
        ],
    )
    def test_as_bordas_da_vigencia(self, delta, estado):
        assert estado_do_membro(_participacao(termo_assinado_em=ASSINADO), _dia(delta)) == estado

    def test_assinado_antes_do_inicio_ja_e_ativo(self):
        p = _participacao(termo_assinado_em=ASSINADO)
        assert estado_do_membro(p, INICIO - timedelta(days=10)) == "ativo"


class TestEncerrado:
    @pytest.mark.parametrize("delta", [-100, 0, 15, 90])
    def test_encerrada_e_encerrado_em_qualquer_dia(self, delta):
        p = _participacao(termo_assinado_em=ASSINADO, encerrada_em="2027-01-10")
        assert estado_do_membro(p, _dia(delta)) == "encerrado"

    def test_encerrada_sem_assinatura_tambem(self):
        assert estado_do_membro(_participacao(encerrada_em="2026-08-01"), INICIO) == "encerrado"


class TestKitDeConhecimento:
    """O texto do Produto Segurança do Paciente diz o comportamento novo."""

    KIT = os.path.join(os.path.dirname(__file__), "..", "app", "conhecimento", "seguranca-do-paciente.md")

    def test_o_kit_explica_cada_estado_e_que_membro_nao_se_apaga(self):
        """Mutante: tirar a seção dos membros do kit."""
        with open(self.KIT, encoding="utf-8") as arquivo:
            texto = arquivo.read()
        assert "## Membros e estados" in texto
        rotulos = (
            "Cadastrado",
            "Documento gerado",
            "Aguardando assinatura",
            "Ativo",
            "A vencer",
            "Em carência",
            "Vencido",
            "Encerrado",
        )
        secao = texto.split("## Membros e estados", 1)[1].split("\n## ", 1)[0]
        assert [r for r in rotulos if f"**{r}**" not in secao] == []
        assert "Membro nunca é apagado" in secao
        assert "quem compunha o Núcleo naquele dia" in secao
