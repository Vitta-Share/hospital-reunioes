"use client";

import { RecalibracaoDoAgente } from "@/components/seguranca-do-paciente/RecalibracaoDoAgente";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";
import { ORIENTACAO_DA_RECALIBRACAO } from "@/lib/seguranca-do-paciente/recalibracao";

/** A recalibração do agente do Núcleo aos 30 e aos 60 dias (issue #2001). */
export default function RecalibracaoPage() {
  return (
    <TelaDoNucleo titulo="Recalibração do agente" orientacao={ORIENTACAO_DA_RECALIBRACAO} recurso="triagem">
      <RecalibracaoDoAgente />
    </TelaDoNucleo>
  );
}
