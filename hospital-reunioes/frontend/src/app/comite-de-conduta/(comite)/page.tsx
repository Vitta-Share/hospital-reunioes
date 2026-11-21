"use client";

import { MinhaVez } from "@/components/conduta/MinhaVez";
import { TelaDoComite } from "@/components/conduta/TelaDoComite";

/** MINHA VEZ, a tela inicial do Comitê de Conduta (issue #1824). */
export default function MinhaVezPage() {
  return (
    <TelaDoComite titulo="Minha vez" orientacao="O que depende de você agora, do mais urgente ao menos urgente.">
      <MinhaVez />
    </TelaDoComite>
  );
}
