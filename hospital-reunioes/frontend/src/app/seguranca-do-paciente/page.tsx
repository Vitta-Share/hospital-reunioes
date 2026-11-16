"use client";

import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** Os seis passos da seção 17 da especificação, "Como funciona o Núcleo". */
const PASSOS = [
  "Alguém notifica pelo QR, em 2 minutos.",
  "O sistema sugere a classificação e a coordenação confirma.",
  "O setor investiga, com a página já pré-montada.",
  "As ações viram pendências e só concluem com evidência.",
  "Depois de 90 dias, verificamos se funcionou.",
  "Quem notificou fica sabendo o que mudou.",
];

/**
 * A página inicial de Segurança do Paciente (issue #1765, PRD #1764). O painel
 * do Núcleo chega com a segunda fase; até lá, a página explica o ciclo.
 */
export default function SegurancaDoPacientePage() {
  return (
    <TelaDoNucleo
      titulo="Segurança do Paciente"
      orientacao="O que precisa de você hoje vem primeiro. O resto é acompanhamento."
      recurso="ver_modulo"
    >
      <h2 className="text-base font-semibold text-slate-900 mb-3">Como funciona o Núcleo</h2>
      <ol aria-label="Como funciona o Núcleo" className="space-y-2.5">
        {PASSOS.map((passo, i) => (
          <li
            key={passo}
            className="flex gap-3 items-center bg-white rounded-2xl border border-border shadow-premium px-4 py-3"
          >
            <span
              aria-hidden
              className="flex items-center justify-center shrink-0 w-7 h-7 rounded-full bg-[#EAEAF0] text-[#282760] text-sm font-bold"
            >
              {i + 1}
            </span>
            <span className="text-sm text-slate-700 min-w-0">{passo}</span>
          </li>
        ))}
      </ol>
    </TelaDoNucleo>
  );
}
