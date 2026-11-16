"use client";

import { CapacitacoesDoNucleo } from "@/components/seguranca-do-paciente/CapacitacoesDoNucleo";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** As capacitações do Núcleo (issues #1765 e #1778). */
export default function CapacitacoesDoNucleoPage() {
  return (
    <TelaDoNucleo
      titulo="Capacitações"
      orientacao="As capacitações do Núcleo e quem confirmou presença."
      recurso="capacitacoes"
    >
      <CapacitacoesDoNucleo />
    </TelaDoNucleo>
  );
}
