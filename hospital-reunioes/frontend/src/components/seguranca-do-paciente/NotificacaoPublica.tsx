"use client";

import { Logo } from "@/components/ui/Logo";
import { FormularioDeNotificacao } from "@/components/seguranca-do-paciente/FormularioDeNotificacao";

/**
 * A página pública da notificação de incidente (issue #1987), sem login. A
 * porta diz a origem: o QR abre `/notificar/qr`, e o endereço (o ícone nos
 * computadores do hospital) abre `/notificar`.
 */
export function NotificacaoPublica({ porta }: { porta: "qr" | "endereco" }) {
  return (
    <main className="min-h-screen bg-bg">
      <div className="max-w-lg mx-auto px-4 py-8 space-y-5">
        <div className="flex items-center justify-center">
          <Logo variant="default" size="sm" />
        </div>
        <div className="text-center space-y-1">
          <h1 className="text-xl font-bold text-slate-900">Notificar incidente</h1>
          <p className="text-sm text-slate-500">
            Conte ao Núcleo de Segurança do Paciente o que aconteceu e receba o protocolo na hora.
          </p>
        </div>
        <FormularioDeNotificacao porta={porta} />
      </div>
    </main>
  );
}
