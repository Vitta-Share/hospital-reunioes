import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { canalAberto } from "@/lib/conduta/abertura";

export const metadata: Metadata = {
  title: "Canal de Conduta · Hospital São Matheus",
  robots: { index: false, follow: false },
};

// A chave de abertura é lida a cada pedido: abrir ou fechar o canal no
// Coolify vale sem novo build.
export const dynamic = "force-dynamic";

/**
 * As telas públicas do Canal de Conduta (issue #1843). Com a chave de abertura
 * desligada, toda tela daqui responde 404 (ADR 0097, decisão 11).
 */
export default async function CanalDeCondutaLayout({ children }: { children: React.ReactNode }) {
  if (!(await canalAberto())) notFound();
  return children;
}
