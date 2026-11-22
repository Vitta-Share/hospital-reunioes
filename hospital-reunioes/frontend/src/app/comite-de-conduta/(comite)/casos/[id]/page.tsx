"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { LinkDoGuia } from "@/components/conduta/LinkDoGuia";
import { TelaDoCaso } from "@/components/conduta/TelaDoCaso";

/**
 * A tela do caso do Comitê de Conduta (issue #1824). O endereço leva o
 * identificador interno do caso, nunca o protocolo (regra C6).
 */
export default function CasoPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto w-full min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link href="/comite-de-conduta/casos" className="text-sm font-semibold text-[#282760] underline">
          Voltar aos casos
        </Link>
        <LinkDoGuia />
      </div>
      <div className="mt-3">
        <TelaDoCaso casoId={id ?? ""} />
      </div>
    </div>
  );
}
