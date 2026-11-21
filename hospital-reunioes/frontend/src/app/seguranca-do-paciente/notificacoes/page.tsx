"use client";

import Link from "next/link";
import { ListChecks } from "lucide-react";

import { NotificacoesDoNucleo } from "@/components/seguranca-do-paciente/NotificacoesDoNucleo";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";
import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";

/** Notificações: os casos do Núcleo (issue #1987), com a entrada da fila de triagem (issue #1992). */
export default function NotificacoesPage() {
  const { participante } = useCurrentParticipante();
  const triagem = participante?.recursos_nsp?.includes("triagem") ?? false;
  return (
    <TelaDoNucleo
      titulo="Notificações"
      orientacao="Toda notificação de incidente que chegou ao Núcleo, da mais nova à mais antiga."
      recurso="casos"
    >
      {triagem && (
        <Link
          href="/seguranca-do-paciente/notificacoes/triagem"
          className="mb-4 inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90"
        >
          <ListChecks className="w-4 h-4" aria-hidden />
          Fila de triagem
        </Link>
      )}
      <NotificacoesDoNucleo />
    </TelaDoNucleo>
  );
}
