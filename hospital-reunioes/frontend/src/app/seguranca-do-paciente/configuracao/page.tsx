"use client";

import { QrDaNotificacao } from "@/components/seguranca-do-paciente/QrDaNotificacao";
import { TelaDoNucleo } from "@/components/seguranca-do-paciente/TelaDoNucleo";

/** Configuração do módulo (ADR 0095, decisão 4): por ora, o QR e o endereço da notificação (issue #2046). */
export default function ConfiguracaoPage() {
  return (
    <TelaDoNucleo
      titulo="Configuração"
      orientacao="O que o módulo usa para funcionar no hospital."
      recurso="configuracao"
    >
      <QrDaNotificacao />
    </TelaDoNucleo>
  );
}
