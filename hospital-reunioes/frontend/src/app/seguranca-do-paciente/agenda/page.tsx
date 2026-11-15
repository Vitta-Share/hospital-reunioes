"use client";

import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** A agenda regulatória do Núcleo (issue #1765). O conteúdo chega na fatia da agenda. */
export default function AgendaRegulatoriaPage() {
  return (
    <TelaDoNucleo
      titulo="Agenda regulatória"
      orientacao="O que a vigilância sanitária cobra do hospital, e até quando."
      recurso="agenda"
    />
  );
}
