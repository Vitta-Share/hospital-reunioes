"use client";

import Link from "next/link";

import type { ItemDaFila } from "@/lib/contas-medicas/envio";
import { CONTINUE_DE_ONDE_PAROU } from "@/lib/contas-medicas/textos";

import { NumeroEPaciente } from "./ListaDeContas";

/**
 * O bloco "Continue de onde parou" (issue #1951): na etapa Fila, antes da
 * lista, as contas em análise da própria pessoa, com os itens feitos do total
 * e o botão "Continuar". Sem nenhuma, o bloco não aparece.
 */
export function ContinueDeOndeParou({ contas }: { contas: ItemDaFila[] }) {
  if (contas.length === 0) return null;
  return (
    <section
      aria-label={CONTINUE_DE_ONDE_PAROU}
      className="rounded-2xl border border-[#BFDBFE] bg-[#EFF6FF] px-5 py-4"
    >
      <h2 className="text-sm font-semibold text-slate-900">{CONTINUE_DE_ONDE_PAROU}</h2>
      <ul className="mt-2 divide-y divide-[#BFDBFE]">
        {contas.map((conta) => (
          <li key={conta.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2">
            <div className="min-w-0 flex-1">
              <NumeroEPaciente conta={conta} />
            </div>
            <span className="text-xs tabular-nums text-slate-600">
              {conta.itens_feitos} de {conta.itens_total} {conta.itens_total === 1 ? "item feito" : "itens feitos"}
            </span>
            <Link
              href={`/contas-medicas/guia/${conta.id}`}
              className="inline-flex items-center rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-white hover:bg-primary/90"
            >
              Continuar
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
