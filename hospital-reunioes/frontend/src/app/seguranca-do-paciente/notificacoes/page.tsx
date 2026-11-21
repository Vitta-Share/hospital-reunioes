"use client";

import { NotificacoesDoNucleo } from "@/components/seguranca-do-paciente/NotificacoesDoNucleo";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** Notificações: os casos do Núcleo (issue #1987). */
export default function NotificacoesPage() {
  return (
    <TelaDoNucleo
      titulo="Notificações"
      orientacao="Toda notificação de incidente que chegou ao Núcleo, da mais nova à mais antiga."
      recurso="casos"
    >
      <NotificacoesDoNucleo />
    </TelaDoNucleo>
  );
}
