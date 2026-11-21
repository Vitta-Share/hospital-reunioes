"use client";

import { CortesDeFrequencia } from "@/components/seguranca-do-paciente/CortesDeFrequencia";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** Configuração do módulo (ADR 0095, decisão 4): os cortes de frequência da matriz de prioridade (issue #1992). */
export default function ConfiguracaoPage() {
  return (
    <TelaDoNucleo
      titulo="Configuração"
      orientacao="O que o módulo usa para funcionar no hospital."
      recurso="configuracao"
    >
      <CortesDeFrequencia />
    </TelaDoNucleo>
  );
}
