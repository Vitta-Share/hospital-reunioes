"use client";

import { MinhaFila } from "@/components/inicio/MinhaFila";

/**
 * O Início de cada pessoa (issue #1934, ADR 0104). Nesta etapa a tela já está
 * no menu, e o login ainda cai onde caía antes: a troca do destino vem por
 * último, para ninguém cair num Início pela metade.
 */
export default function InicioPage() {
  return (
    <div className="max-w-5xl mx-auto">
      <MinhaFila />
    </div>
  );
}
