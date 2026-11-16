"use client";

import { DocumentosDoNucleo } from "@/components/seguranca-do-paciente/DocumentosDoNucleo";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";
import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";

/** Os documentos do Núcleo (issue #1767): a vigente de cada tipo e as anteriores. */
export default function DocumentosDoNucleoPage() {
  const { participante } = useCurrentParticipante();
  const podePublicar = participante?.recursos_nsp?.includes("gerir_nucleo") ?? false;

  return (
    <TelaDoNucleo
      titulo="Documentos"
      orientacao="A versão vigente de cada documento e as anteriores."
      recurso="documentos"
    >
      <DocumentosDoNucleo podePublicar={podePublicar} />
    </TelaDoNucleo>
  );
}
