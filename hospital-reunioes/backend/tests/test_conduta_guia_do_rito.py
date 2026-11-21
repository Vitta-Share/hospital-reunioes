"""O kit de conhecimento do Canal de Conduta diz o Guia do rito e o primeiro
acesso (issue #1842). As telas e o portão do guia têm teste no frontend
(`src/app/comite-de-conduta/guia.test.tsx`)."""

from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "app" / "conhecimento" / "canal-de-conduta.md"


def test_o_kit_do_canal_diz_o_guia_do_rito_e_os_cartoes_do_primeiro_acesso():
    kit = KIT.read_text(encoding="utf-8")
    assert "O Guia do rito e o primeiro acesso:" in kit
    assert "os quatro ritos (Encaminhamento, Rápido, Completo e Rota Especial)" in kit
    assert 'O botão "Guia do rito" aparece em toda tela do Comitê' in kit
    assert "o membro que ainda não assinou o Termo também abre o guia" in kit
    assert "aparecem cinco cartões apresentando o módulo" in kit
    assert "Eles não voltam depois, nem em outro aparelho" in kit
