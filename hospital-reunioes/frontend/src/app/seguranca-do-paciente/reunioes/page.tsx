"use client";

import { ReunioesDoNucleo } from "@/components/seguranca-do-paciente/ReunioesDoNucleo";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** As reuniões do Núcleo (issue #1772): o calendário e a criação pela Presidência. */
export default function ReunioesDoNucleoPage() {
  return (
    <TelaDoNucleo
      titulo="Reuniões do Núcleo"
      orientacao="A pauta é montada pelo sistema. Depois da reunião, importe a transcrição e revise a ata."
      recurso="calendario"
    >
      <ReunioesDoNucleo />
    </TelaDoNucleo>
  );
}
