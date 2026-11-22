"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { TecnologiaModulo } from "@/components/tecnologia/TecnologiaModulo";

/**
 * `?demanda=<id>` é o aviso do sino da Conversa da Demanda (issue #1537), e
 * `?pergunta=<id>` o da Pergunta da Vitta, com o cartão em foco (issue #2118).
 */
function TecnologiaComADemandaDoSino() {
  const parametros = useSearchParams();
  return <TecnologiaModulo demandaInicial={parametros.get("demanda")} perguntaInicial={parametros.get("pergunta")} />;
}

export default function TecnologiaPage() {
  return (
    <Suspense fallback={null}>
      <TecnologiaComADemandaDoSino />
    </Suspense>
  );
}
