"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { LinkDoGuia } from "./LinkDoGuia";

const ABAS = [
  { href: "/comite-de-conduta", rotulo: "Minha vez" },
  { href: "/comite-de-conduta/casos", rotulo: "Casos" },
];

/**
 * A moldura das telas do Comitê de Conduta (issue #1824): título, a frase do
 * topo da seção 18 da especificação e as abas MINHA VEZ e Casos. Quem entra é
 * o portão do servidor, no layout.
 */
export function TelaDoComite({
  titulo,
  orientacao,
  children,
}: {
  titulo: string;
  orientacao: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto w-full min-w-0">
      <nav aria-label="Comitê de Conduta" className="flex flex-wrap gap-2 mb-4">
        {ABAS.map((aba) => {
          const atual = aba.href === "/comite-de-conduta" ? pathname === aba.href : pathname.startsWith(aba.href);
          return (
            <Link
              key={aba.href}
              href={aba.href}
              aria-current={atual ? "page" : undefined}
              className={`rounded-xl px-3 py-1.5 text-sm font-semibold ${
                atual ? "bg-[#282760] text-white" : "bg-white border border-border text-slate-700"
              }`}
            >
              {aba.rotulo}
            </Link>
          );
        })}
        <LinkDoGuia />
      </nav>
      <h1 className="text-2xl font-bold text-slate-900">{titulo}</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-5">{orientacao}</p>
      {children}
    </div>
  );
}
