"use client";

import { ListaDeRecomendacoes } from "@/components/conduta/RecomendacaoDoComite";

/** As Recomendações do Comitê enviadas à Direção (issue #1835, PRD #1786). */
export default function RecomendacoesDoComitePage() {
  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto w-full min-w-0">
      <h1 className="text-2xl font-bold text-slate-900">Recomendações do Comitê</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-5">
        A conclusão e a ata de cada caso que o Comitê de Conduta enviou à Direção.
      </p>
      <ListaDeRecomendacoes />
    </div>
  );
}
