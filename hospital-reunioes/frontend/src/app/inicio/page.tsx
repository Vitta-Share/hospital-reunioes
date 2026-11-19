"use client";

import { MinhaFila } from "@/components/inicio/MinhaFila";
import { QuemRespondeAVoce } from "@/components/inicio/QuemRespondeAVoce";

/**
 * O Início de cada pessoa (issue #1934, ADR 0104). Nesta etapa a tela já está
 * no menu, e o login ainda cai onde caía antes: a troca do destino vem por
 * último, para ninguém cair num Início pela metade.
 *
 * Quem responde a você (issue #1943) vem embaixo, num pedido próprio: a
 * falha de um não derruba o outro.
 */
export default function InicioPage() {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <MinhaFila />
      <QuemRespondeAVoce />
    </div>
  );
}
