"use client";

import { NotasDoComite } from "@/components/seguranca-do-paciente/NotasDoComite";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** As notas do Comitê de Conduta ao Núcleo (issue #1850). */
export default function NotasDoComitePage() {
  return (
    <TelaDoNucleo
      titulo="Notas do Comitê de Conduta"
      orientacao="O que o Comitê de Conduta avisou ao Núcleo sobre risco ao paciente. O relato e quem relatou ficam no Canal."
      recurso="notas_do_comite"
    >
      <NotasDoComite />
    </TelaDoNucleo>
  );
}
