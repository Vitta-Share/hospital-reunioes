"use client";

import { CasosDoComite } from "@/components/conduta/CasosDoComite";
import { TelaDoComite } from "@/components/conduta/TelaDoComite";

/** Casos do Comitê de Conduta (issue #1824). */
export default function CasosPage() {
  return (
    <TelaDoComite titulo="Casos" orientacao="Todos os casos a que você tem acesso.">
      <CasosDoComite />
    </TelaDoComite>
  );
}
