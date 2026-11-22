"use client";

import { useParams } from "next/navigation";

import { CasoDoNucleo } from "@/components/seguranca-do-paciente/CasoDoNucleo";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** Um caso do Núcleo, a tela que o e-mail de ciência da Ouvidoria abre (issue #1997). */
export default function CasoDoNucleoPage() {
  const params = useParams();
  return (
    <TelaDoNucleo titulo="Caso" orientacao="Leia o caso como ele chegou ao Núcleo." recurso={["casos", "casos_graves"]}>
      <CasoDoNucleo id={params.id as string} />
    </TelaDoNucleo>
  );
}
