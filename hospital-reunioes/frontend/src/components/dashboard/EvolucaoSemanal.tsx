"use client";

import { Loader2 } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

/** Uma semana fotografada na segunda (issue #1873). */
export interface SemanaDaEvolucao {
  semana: string; // a segunda-feira, AAAA-MM-DD
  atrasadas: number;
}

export interface EvolucaoSemanalProps {
  semanas: SemanaDaEvolucao[];
  loading: boolean;
}

function diaEMes(semana: string): string {
  const [, mes, dia] = semana.split("-");
  return `${dia}/${mes}`;
}

// ─── Component ───────────────────────────────────────────────────────────────

/** As atrasadas das últimas 8 semanas, só as fotografadas: a semana sem
 * fotografia não aparece, e nada é recalculado do passado (decisão 30 do
 * diretor no PRD #1757). */
export default function EvolucaoSemanal({ semanas, loading }: EvolucaoSemanalProps) {
  const maior = Math.max(1, ...semanas.map((s) => s.atrasadas));

  return (
    <section
      aria-labelledby="evolucao-semanal-titulo"
      className="bg-surface rounded-xl p-6 border border-border shadow-premium flex flex-col mt-6"
    >
      <h2 id="evolucao-semanal-titulo" className="text-lg font-bold text-text mb-1">
        Evolução das atrasadas
      </h2>
      <p className="text-sm text-text-secondary mb-4">
        Últimas 8 semanas, com os números guardados toda segunda.
      </p>

      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="w-6 h-6 animate-spin text-slate-300" />
        </div>
      ) : semanas.length === 0 ? (
        <p className="text-sm text-text-secondary py-6 text-center">
          A evolução começa a contar na próxima segunda, quando os números da semana forem guardados.
        </p>
      ) : (
        <ul className="flex items-end gap-3 h-40">
          {semanas.map((s) => (
            <li
              key={s.semana}
              aria-label={`Semana de ${diaEMes(s.semana)}: ${s.atrasadas} atrasadas`}
              className="flex-1 flex flex-col items-center justify-end h-full"
            >
              <span className="text-xs font-semibold text-text mb-1">{s.atrasadas}</span>
              <div
                className="w-full max-w-12 rounded-t-md bg-[#FC9D9D]"
                style={{ height: `${Math.max(4, (s.atrasadas / maior) * 100)}%` }}
              />
              <span className="text-xs text-text-secondary mt-1">{diaEMes(s.semana)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
