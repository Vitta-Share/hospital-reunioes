"use client";

import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** As reuniões do Núcleo (issue #1765). O conteúdo chega na fatia das reuniões. */
export default function ReunioesDoNucleoPage() {
  return (
    <TelaDoNucleo
      titulo="Reuniões do Núcleo"
      orientacao="A pauta é montada pelo sistema. Depois da reunião, importe a transcrição e revise a ata."
      recurso="calendario"
    />
  );
}
