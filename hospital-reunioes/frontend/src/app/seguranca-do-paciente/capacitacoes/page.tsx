"use client";

import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** As capacitações do Núcleo (issue #1765). O conteúdo chega na fatia das capacitações. */
export default function CapacitacoesDoNucleoPage() {
  return (
    <TelaDoNucleo
      titulo="Capacitações"
      orientacao="As capacitações do Núcleo e quem confirmou presença."
      recurso="capacitacoes"
    />
  );
}
