"use client";

import { NotificacaoPublica } from "@/components/seguranca-do-paciente/NotificacaoPublica";

/** Para onde o QR do Núcleo aponta (issue #1987): grava a origem QR. */
export default function NotificarPeloQrPage() {
  return <NotificacaoPublica porta="qr" />;
}
