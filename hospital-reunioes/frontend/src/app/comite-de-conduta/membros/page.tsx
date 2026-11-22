"use client";

import { LinkDoGuia } from "@/components/conduta/LinkDoGuia";
import { MembrosDoComite } from "@/components/conduta/MembrosDoComite";

/** A tela Membros do Comitê de Conduta (issue #1822, PRD #1786). */
export default function MembrosDoComitePage() {
  return (
    <div className="p-4 md:p-8 max-w-4xl mx-auto w-full">
      <div className="mb-4">
        <LinkDoGuia />
      </div>
      <h1 className="text-2xl font-bold text-slate-900">Membros</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-5">Quem compõe o Comitê e até quando.</p>
      <MembrosDoComite />
    </div>
  );
}
