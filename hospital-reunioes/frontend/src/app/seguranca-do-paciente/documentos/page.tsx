"use client";

import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** Os documentos do Núcleo (issue #1765). O conteúdo chega na fatia dos documentos. */
export default function DocumentosDoNucleoPage() {
  return (
    <TelaDoNucleo
      titulo="Documentos"
      orientacao="A versão vigente de cada documento e as anteriores."
      recurso="documentos"
    />
  );
}
