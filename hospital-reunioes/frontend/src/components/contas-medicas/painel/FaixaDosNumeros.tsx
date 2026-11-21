"use client";

import { useId, type ReactNode } from "react";

import { Dica } from "@/components/ui/Dica";

/**
 * A faixa única dos números da semana no topo do Painel (issue #1953), no
 * molde da Esteira: uma moldura só, com um número por célula. Em tela
 * estreita ela quebra em duas colunas, sem rolagem lateral.
 */
export function FaixaDosNumeros({ children }: { children: ReactNode }) {
  return (
    <section
      aria-label="Números da semana"
      className="grid grid-cols-2 rounded-2xl border border-border bg-white shadow-premium lg:auto-cols-fr lg:grid-flow-col lg:grid-cols-none"
    >
      {children}
    </section>
  );
}

/**
 * Um número da faixa. O nome dele recebe o mouse e o foco do teclado e abre a
 * dica com o que o número mede; o grupo leva o nome, para o leitor de tela e
 * para o teste.
 *
 * A dica (256 px) se prende ao título inteiro da célula, não só ao nome. Na
 * coluna da direita (duas colunas) e no último número (uma linha só) ela abre
 * a partir da borda direita da célula, para dentro da faixa: presa à esquerda,
 * passaria da tela e a página rolaria de lado.
 */
export function NumeroDaFaixa({ titulo, dica, children }: { titulo: string; dica: string; children: ReactNode }) {
  const id = useId();
  return (
    <div
      role="group"
      aria-labelledby={id}
      className="min-w-0 border-border p-4 even:border-l [&:nth-child(n+3)]:border-t lg:border-l lg:first:border-l-0 lg:[&:nth-child(n+3)]:border-t-0 max-lg:even:[&_[role=tooltip]]:left-auto max-lg:even:[&_[role=tooltip]]:right-0 lg:last:[&_[role=tooltip]]:left-auto lg:last:[&_[role=tooltip]]:right-0"
    >
      <h3 id={id} className="relative text-xs font-semibold text-slate-500 [&>span]:static">
        <Dica texto={dica}>
          <span tabIndex={0} className="cursor-help underline decoration-dotted underline-offset-4">
            {titulo}
          </span>
        </Dica>
      </h3>
      <div className="mt-1">{children}</div>
    </div>
  );
}
