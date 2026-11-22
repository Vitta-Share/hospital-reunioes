"""A saída "Sou colaborador" da Ouvidoria para o Canal de Conduta (issue #1847).

A tela tem teste próprio no frontend (`saida-para-o-canal.test.tsx`). Aqui fica
só o critério do kit: o texto do Produto Ouvidoria diz o comportamento novo,
para o Assistente de Tecnologia não responder com a regra de antes.
"""

import pytest

from app.services.conhecimento import CONHECIMENTO_DIR


@pytest.mark.parametrize(
    "trecho",
    [
        "Sou colaborador e quero relatar uma conduta",
        "Com o Canal fechado, a saída não aparece",
        "nunca pelo endereço da página",
        "lembra o ouvidor de indicar o Canal ao colaborador",
        "terminam nela",
        "A numeração do protocolo da Ouvidoria não muda",
    ],
)
def test_o_kit_da_ouvidoria_diz_o_comportamento_novo(trecho):
    assert trecho in (CONHECIMENTO_DIR / "ouvidoria.md").read_text(encoding="utf-8")
