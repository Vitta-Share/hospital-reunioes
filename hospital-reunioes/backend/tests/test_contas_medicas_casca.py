"""O texto da casca de Contas médicas no Kit de conhecimento (issue #1950).

O Assistente de Tecnologia responde Demanda com este texto: sem as abas e as
Legendas nele, a pergunta "por que não vejo a aba Validação?" ou "sumiram as
frases embaixo dos títulos" fica sem resposta.
"""

from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "contas-medicas.md"


def _secao(titulo: str) -> str:
    return KIT.read_text(encoding="utf-8").split(f"## {titulo}")[1].split("\n## ")[0]


class TestOKitDescreveAsAbasEAsLegendas:
    def test_a_secao_diz_as_abas_quem_ve_cada_uma_e_a_dica(self):
        abas = _secao("As abas e as Legendas")

        for trecho in (
            "Contas, Painel, Validação, Coordenação, Contratos, Operadoras e Habilitação",
            "a aba da tela aberta fica marcada",
            "No Guia de uma conta, a marcada é Contas",
            "pela mesma permissão que abre a tela",
            "quem não tem nenhuma delas vê só Contas",
            "pelo teclado",
            "quebram linha",
        ):
            assert trecho in abas, trecho

    def test_a_secao_diz_o_interruptor_das_legendas_e_que_a_escolha_fica_guardada(self):
        legendas = _secao("As abas e as Legendas")

        for trecho in (
            'interruptor "Legendas"',
            "desligado, nenhuma Legenda aparece no módulo",
            "depois de recarregar a página",
            "as Legendas aparecem ligadas",
        ):
            assert trecho in legendas, trecho

    def test_o_que_ja_esta_no_ar_inclui_as_abas(self):
        assert 'as abas no topo de todas as telas do módulo, descritas em "As abas e as Legendas"' in _secao(
            "O que já está no ar"
        )
