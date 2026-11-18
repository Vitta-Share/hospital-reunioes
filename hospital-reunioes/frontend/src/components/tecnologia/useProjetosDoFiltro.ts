/**
 * As opções do filtro Projeto do Quadro e das Entregas (issue #1967, PRD
 * #1964): o Aplicativo do Hospital, a Ana e cada projeto novo da Vitta que
 * tem Demanda, pela rota `/projetos`. Enquanto ela não responde, ou se falha,
 * ficam os dois de sempre.
 */

import { useEffect, useState } from "react";

import { OpcaoDeProjeto, PROJETOS_FIXOS, projetosValidos, URL_DOS_PROJETOS } from "./demandas";

export function useProjetosDoFiltro(token: string | null): OpcaoDeProjeto[] {
  const [projetos, setProjetos] = useState<OpcaoDeProjeto[]>(PROJETOS_FIXOS);

  useEffect(() => {
    if (!token) return;
    let viva = true;
    (async () => {
      try {
        const resposta = await fetch(URL_DOS_PROJETOS, { headers: { Authorization: `Bearer ${token}` } });
        if (!resposta.ok) return;
        const lidos = projetosValidos(await resposta.json());
        if (viva && lidos) setProjetos(lidos);
      } catch (e) {
        console.error("[admin/tecnologia] falha ao listar os projetos", e);
      }
    })();
    return () => {
      viva = false;
    };
  }, [token]);

  return projetos;
}
