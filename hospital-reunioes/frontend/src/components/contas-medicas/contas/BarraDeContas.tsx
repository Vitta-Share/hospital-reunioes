"use client";

import type { ReactNode } from "react";

import { Legenda } from "@/components/ui/Legenda";

/**
 * A barra do topo da tela de contas (issue #1951): o título e a Legenda da
 * tela, com o lado direito livre para os comandos que as próximas fatias põem
 * ali (busca, filtro, enviar).
 */
export function BarraDeContas({ children }: { children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold text-slate-900">Contas médicas</h1>
        <Legenda>
          Envie a conta e o prontuário do MV e receba a lista do que corrigir antes de mandar para a operadora.
        </Legenda>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}
