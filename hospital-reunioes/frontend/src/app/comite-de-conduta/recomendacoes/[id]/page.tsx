"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { RecomendacaoDoComite } from "@/components/conduta/RecomendacaoDoComite";

/**
 * A Recomendação do Comitê de um caso (issue #1835). O endereço leva o
 * identificador interno do caso, nunca o protocolo (regra C6).
 */
export default function RecomendacaoPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto w-full min-w-0">
      <Link href="/comite-de-conduta/recomendacoes" className="text-sm font-semibold text-[#282760] underline">
        Voltar às Recomendações
      </Link>
      <div className="mt-3">
        <RecomendacaoDoComite casoId={id ?? ""} />
      </div>
    </div>
  );
}
