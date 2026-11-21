"""O Guia em Mesa de trabalho no Kit de conhecimento (issue #1952, PRD #1933).

O Assistente de Tecnologia responde Demanda com este texto: se ele ainda
descreve o Guia de meia tela, com o "Ver evidência" fechado, a pergunta "por
que a tela pulou para outro item?" ou "cadê o botão Ver evidência?" recebe a
resposta da tela antiga.
"""

from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "contas-medicas.md"


def _secao(titulo: str) -> str:
    return KIT.read_text(encoding="utf-8").split(f"## {titulo}")[1].split("\n## ")[0]


class TestOKitDescreveAMesaDeTrabalho:
    def test_o_guia_ocupa_o_monitor_com_a_lista_e_o_item_da_vez(self):
        guia = _secao("O Guia")

        for trecho in (
            "ocupa o monitor inteiro",
            "a partir de 1000 px",
            "a lista fica em cima do Item da vez",
            "Clicar numa Linha da lista",
            "a primeira Linha aberta",
        ):
            assert trecho in guia, trecho
        assert "meia tela" not in guia

    def test_depois_de_marcar_a_tela_passa_para_a_proxima_linha_aberta(self):
        guia = _secao("O Guia")

        for trecho in (
            "passa sozinho para a próxima Linha aberta",
            "todos os itens estão marcados",
            "um item por vez",
        ):
            assert trecho in guia, trecho

    def test_a_evidencia_aparece_sem_clicar_e_o_rodape_fica_fixo(self):
        guia = _secao("O Guia")

        for trecho in (
            "a Evidência aparece sem clicar",
            "rodapé fixo",
            "quantos itens faltam marcar",
        ):
            assert trecho in guia, trecho
        assert "Ver evidência" not in guia


class TestOKitDescreveOSoOQueFaltaEOPainelDoAuditor:
    """Issue #1957: o "Só o que falta" na lista e a conversa com o Auditor num
    painel lateral, em vez do fim do Guia."""

    def test_so_o_que_falta_esconde_as_marcadas_e_vale_so_na_conta_aberta(self):
        guia = _secao("O Guia")

        for trecho in (
            '"Só o que falta"',
            "esconde as Linhas já marcadas",
            "a contagem do grupo inteiro",
            "cada conta abre com a lista inteira",
        ):
            assert trecho in guia, trecho

    def test_a_conversa_com_o_auditor_abre_num_painel_ao_lado(self):
        faltou = _secao("O Faltou isto e o Auditor")

        for trecho in (
            "painel ao lado",
            '"Falar com o auditor"',
            "Esc",
            "sem perder a conversa",
        ):
            assert trecho in faltou, trecho
        assert "no fim do Guia" not in faltou
