"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { TecnologiaModulo } from "@/components/tecnologia/TecnologiaModulo";

/**
 * `?demanda=<id>` é o link de um aviso do sino ou do e-mail: o Quadro abre com
 * a Demanda (issues #1537 e #2279). O `?pergunta=` do aviso antigo da Pergunta
 * da Vitta só abre a aba, porque a lista Esperando você saiu.
 */
function TecnologiaComADemandaDoSino() {
  const parametros = useSearchParams();
  return <TecnologiaModulo demandaInicial={parametros.get("demanda")} />;
}

export default function TecnologiaPage() {
  return (
    <Suspense fallback={null}>
      <TecnologiaComADemandaDoSino />
    </Suspense>
  );
}
