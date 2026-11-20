"""O setor escolhido numa tela, casado com a tabela `setores` (issue #1861).

A tela manda o nome que a pessoa escolheu na lista de setores ativos
(`GET /participantes/setores`). Aqui o nome vira a linha canônica, com o id que
vai para `setor_id` e o nome que fica na TEXT `setor`, em sincronia. Setor que
não existe, ou que o Super admin arquivou, não casa: quem chama recusa.
"""

from __future__ import annotations


def setor_ativo(supabase, nome: str | None) -> dict | None:
    """Devolve `{"id", "nome"}` do setor ativo com esse nome, ou None."""
    procurado = " ".join((nome or "").split()).lower()
    if not procurado:
        return None
    linhas = supabase.table("setores").select("id, nome").eq("ativo", True).execute().data or []
    for linha in linhas:
        if " ".join((linha.get("nome") or "").split()).lower() == procurado:
            return {"id": linha["id"], "nome": linha["nome"]}
    return None
