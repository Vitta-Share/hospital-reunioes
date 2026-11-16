"use client";

import { AgendaRegulatoria } from "@/components/seguranca-do-paciente/AgendaRegulatoria";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** A agenda regulatória do Núcleo (issues #1765 e #1779). */
export default function AgendaRegulatoriaPage() {
  return (
    <TelaDoNucleo
      titulo="Agenda regulatória"
      orientacao="O que a vigilância sanitária cobra do hospital, e até quando."
      recurso="agenda"
    >
      <AgendaRegulatoria />
    </TelaDoNucleo>
  );
}
