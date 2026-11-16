"use client";

import { MembrosDoNucleo } from "@/components/seguranca-do-paciente/MembrosDoNucleo";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** Membros e vigências do Núcleo (issues #1765 e #1766). */
export default function MembrosDoNucleoPage() {
  return (
    <TelaDoNucleo
      titulo="Membros"
      orientacao="Quem compõe o Núcleo, até quando, e quem ainda precisa assinar."
      recurso="membros"
    >
      <MembrosDoNucleo />
    </TelaDoNucleo>
  );
}
