import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RodapeDoCanal } from "@/components/conduta/publico/RodapeDoCanal";
import { Logo } from "@/components/ui/Logo";
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
 *
 * Toda tela debaixo de `/conduta` ganha o rodapé com a página de proteção, o
 * Código de Conduta e as portas "Não é aqui" (issue #1846).
 */
export default async function CanalDeCondutaLayout({ children }: { children: React.ReactNode }) {
  if (!(await canalAberto())) notFound();
  return (
    <div className="min-h-screen bg-bg">
      <main className="max-w-lg mx-auto px-4 py-8 space-y-5">
        <div className="flex items-center justify-center">
          <Logo variant="default" size="sm" />
        </div>
        {children}
      </main>
      <RodapeDoCanal />
    </div>
  );
}
