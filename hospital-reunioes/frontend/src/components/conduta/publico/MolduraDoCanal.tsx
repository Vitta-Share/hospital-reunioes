"use client";

/**
 * A moldura de toda tela pública do Canal de Conduta (issue #1846): o logo em
 * cima e o rodapé do canal embaixo, só com o canal aberto.
 *
 * Com o canal fechado a rota de abertura responde 404 e a moldura não mostra
 * nada do canal (decisão 11 da ADR 0097): fica só a tela, que diz que a página
 * não existe. Enquanto a abertura não responde, também nada.
 */

import { useEffect, useState } from "react";

import { Logo } from "@/components/ui/Logo";
import { ROTA_DA_ABERTURA, lerDoCanal } from "@/lib/conduta/publico";

import { RodapeDoCanal } from "./RodapeDoCanal";

export function MolduraDoCanal({ children }: { children: React.ReactNode }) {
  const [aberto, setAberto] = useState(false);

  useEffect(() => {
    let vivo = true;
    lerDoCanal<{ aberto: boolean }>(ROTA_DA_ABERTURA)
      .then((corpo) => {
        if (vivo) setAberto(corpo?.aberto === true);
      })
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, []);

  return (
    <div className="min-h-screen bg-bg">
      <main className="max-w-lg mx-auto px-4 py-8 space-y-5">
        {aberto && (
          <div className="flex items-center justify-center">
            <Logo variant="default" size="sm" />
          </div>
        )}
        {children}
      </main>
      {aberto && <RodapeDoCanal />}
    </div>
  );
}
