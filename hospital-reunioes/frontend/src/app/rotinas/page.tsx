"use client";

import { ListaDeRotinas } from "@/components/rotinas/ListaDeRotinas";

/**
 * As Rotinas de quem está olhando (issue #1874, ADR 0098, decisão 9): as do
 * nome dele e as das reuniões que ele conduz, com os ciclos em aberto.
 */
export default function RotinasPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl text-text">Rotinas</h1>
        <p className="text-sm text-text-secondary mt-1">
          Cada ciclo vale até o último dia da semana, da quinzena ou do mês. Realizada é um clique; Não realizada pede
          uma anotação.
        </p>
      </div>
      <ListaDeRotinas />
    </div>
  );
}
