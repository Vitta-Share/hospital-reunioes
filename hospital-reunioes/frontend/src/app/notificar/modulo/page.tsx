"use client";

import { FormularioDeNotificacao } from "@/components/seguranca-do-paciente/FormularioDeNotificacao";
import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";

/**
 * Notificar incidente pelo módulo (issue #1987): o mesmo formulário, já
 * identificado pela sessão, com a origem módulo.
 */
export default function NotificarPeloModuloPage() {
  const { participante } = useCurrentParticipante();
  const identificacao = participante
    ? { nome: participante.nome_completo ?? "", contato: participante.email ?? "" }
    : null;

  return (
    <div className="p-4 md:p-8 max-w-lg mx-auto w-full">
      <h1 className="text-2xl font-bold text-slate-900">Notificar incidente</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-5">
        Conte ao Núcleo o que aconteceu. A sua identificação já vem da sua conta.
      </p>
      <FormularioDeNotificacao porta="modulo" identificacao={identificacao} />
    </div>
  );
}
