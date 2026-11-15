"use client";

import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** Membros e vigências do Núcleo (issue #1765). O conteúdo chega na fatia dos membros. */
export default function MembrosDoNucleoPage() {
  return (
    <TelaDoNucleo
      titulo="Membros"
      orientacao="Quem compõe o Núcleo, até quando, e quem ainda precisa assinar."
      recurso="membros"
    />
  );
}
