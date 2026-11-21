"use client";

import { NotificacaoPublica } from "@/components/seguranca-do-paciente/NotificacaoPublica";

/** O endereço da notificação de incidente (issue #1987): grava a origem endereço. */
export default function NotificarPage() {
  return <NotificacaoPublica porta="endereco" />;
}
