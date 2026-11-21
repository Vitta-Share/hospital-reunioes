import Link from "next/link";
import { BookOpen } from "lucide-react";

import { ENDERECO_DO_GUIA } from "@/lib/conduta/guia";

/** A porta do Guia do rito, presente em toda tela do Comitê (issue #1842). */
export function LinkDoGuia() {
  return (
    <Link
      href={ENDERECO_DO_GUIA}
      className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-semibold bg-white border border-border text-slate-700"
    >
      <BookOpen className="w-4 h-4" aria-hidden="true" />
      Guia do rito
    </Link>
  );
}
