"use client";

import { Legenda } from "@/components/ui/Legenda";
import { LEGENDA_DA_ETAPA, NOME_DA_ETAPA, type Etapa } from "@/lib/contas-medicas/textos";

/**
 * A Esteira (issue #1951): uma faixa única com o número de cada etapa. O
 * clique troca a lista de baixo; a etapa aberta fica marcada e ganha a Legenda
 * de uma frase. Na tela estreita as etapas quebram linha, sem rolagem lateral.
 */
export function Esteira({
  etapas,
  aberta,
  contagem,
  onAbrir,
}: {
  etapas: Etapa[];
  aberta: Etapa;
  contagem: (etapa: Etapa) => number | null;
  onAbrir: (etapa: Etapa) => void;
}) {
  return (
    <section aria-label="Esteira">
      <div
        role="tablist"
        className="flex flex-wrap overflow-hidden rounded-2xl border border-border bg-white shadow-premium"
      >
        {etapas.map((etapa) => {
          const selecionada = etapa === aberta;
          const numero = contagem(etapa);
          return (
            <button
              key={etapa}
              type="button"
              role="tab"
              aria-selected={selecionada}
              onClick={() => onAbrir(etapa)}
              className={`flex min-w-[7rem] flex-1 flex-col items-start gap-0.5 border-b-2 px-4 py-3 text-left transition-colors ${
                selecionada ? "border-primary bg-primary/5 text-primary" : "border-transparent text-slate-600 hover:bg-slate-50"
              }`}
            >
              <span className="text-xs font-semibold">{NOME_DA_ETAPA[etapa]}</span>{" "}
              <span className="text-2xl font-bold tabular-nums text-slate-900">{numero ?? "..."}</span>
            </button>
          );
        })}
      </div>
      <Legenda className="mt-2">{LEGENDA_DA_ETAPA[aberta]}</Legenda>
    </section>
  );
}
