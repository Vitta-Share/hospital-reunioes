"use client";

import { useState } from "react";
import Link from "next/link";
import { ListChecks } from "lucide-react";

import { NotificacoesDoNucleo } from "@/components/seguranca-do-paciente/NotificacoesDoNucleo";
import { RegistroRapido } from "@/components/seguranca-do-paciente/RegistroRapido";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";
import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";

const RECURSOS_DOS_CASOS = ["casos", "casos_graves"] as const;

/** Notificações: os casos do Núcleo (issue #1987), a entrada da fila de
 * triagem (issue #1992) e, no alto, o registro rápido (issue #1998).
 * Registrar recarrega a lista. */
export default function NotificacoesPage() {
  const { participante } = useCurrentParticipante();
  const triagem = participante?.recursos_nsp?.includes("triagem") ?? false;
  // A Diretoria só lê os casos graves: sem o registro rápido (issue #1999).
  const todosOsCasos = participante?.recursos_nsp?.includes("casos") ?? false;
  const [versaoDaLista, setVersaoDaLista] = useState(0);
  return (
    <TelaDoNucleo
      titulo="Notificações"
      orientacao={
        todosOsCasos || !participante
          ? "Toda notificação de incidente que chegou ao Núcleo, da mais nova à mais antiga."
          : "Os casos graves, das faixas A e B, da mais nova à mais antiga. Só para leitura."
      }
      recurso={RECURSOS_DOS_CASOS}
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
      <div className="space-y-4">
        {todosOsCasos && <RegistroRapido aoRegistrar={() => setVersaoDaLista((n) => n + 1)} />}
        <NotificacoesDoNucleo key={versaoDaLista} />
      </div>
    </TelaDoNucleo>
  );
}
